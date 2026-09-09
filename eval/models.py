"""Transcription + per-model field extraction for the eval harness.

- transcribe_file: AWS Transcribe streaming, fed from a local 16 kHz wav
- transcribe_deepgram: Deepgram Nova-3 prerecorded API (2nd-STT A/B)
- extract_bedrock: Claude Haiku via Bedrock converse, forced emit_field tool
- extract_gemini: Gemini 2.5 Flash via google-genai, JSON response

All read creds from env (.env). Each raises a clear error if unconfigured.
"""

from __future__ import annotations

import asyncio
import json
import os
import wave

_PROMPT = (
    "You are extracting one field from a phone-call transcript. The caller is "
    "spelling or dictating their {kind}. Return ONLY the {kind} itself, correctly "
    "formatted:\n"
    '- name: proper capitalisation, real spelling (e.g. "Nadia Osei-Bonsu")\n'
    '- email: a valid address, expanding "at"/"dot"/"underscore"/"hyphen"/digits '
    '(e.g. "jane.doe@gmail.com")\n\n'
    "Transcript:\n{transcript}\n"
)


async def transcribe_file(path: str, region: str, language: str = "en-US",
                          vocab: str | None = None, apm=None) -> str:
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent

    parts: list[str] = []

    class H(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, event: TranscriptEvent):
            for r in event.transcript.results:
                if not r.is_partial and r.alternatives:
                    parts.append(r.alternatives[0].transcript)

    client = TranscribeStreamingClient(region=region)
    stream = await client.start_stream_transcription(
        language_code=language, media_sample_rate_hz=16_000, media_encoding="pcm",
        vocabulary_name=vocab or None,
    )

    async def pump():
        import audio_apm
        with wave.open(path) as w:
            assert w.getframerate() == 16_000 and w.getnchannels() == 1
            # APM needs exactly 10 ms frames; without it, 50 ms is fine.
            step = 16_000 * (audio_apm.FRAME_MS if apm else 50) // 1000
            while chunk := w.readframes(step):
                if apm:                              # no-ops a short trailing frame
                    chunk = audio_apm.process_pcm(apm, chunk)
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
                await asyncio.sleep(0.01)
        await stream.input_stream.end_stream()

    await asyncio.gather(pump(), H(stream.output_stream).handle_events())
    return " ".join(parts).strip()


DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


async def transcribe_deepgram(path: str, model: str = "nova-3",
                              keyterms: list[str] | None = None) -> str:
    """Deepgram prerecorded transcription — the 2nd STT in the A/B.

    Nova-3 keyterm prompting is the Deepgram analogue of the AWS custom
    vocabulary: pass the same seeded names via `keyterms`.
    """
    import httpx

    key = os.environ.get("DEEPGRAM_API_KEY")
    if not key:
        raise RuntimeError("DEEPGRAM_API_KEY not set (free tier at deepgram.com)")

    params = [("model", model), ("smart_format", "true"), ("punctuate", "true")]
    for kt in keyterms or []:                       # nova-3 only, English only
        params.append(("keyterm", kt))
    with open(path, "rb") as f:
        audio = f.read()

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(DEEPGRAM_URL, params=params, content=audio,
                         headers={"Authorization": f"Token {key}",
                                  "Content-Type": "audio/wav"})
        r.raise_for_status()
        return _deepgram_transcript(r.json())


def _deepgram_transcript(payload: dict) -> str:
    return (payload["results"]["channels"][0]["alternatives"][0]
            .get("transcript", "").strip())


# token usage of the most recent extract call, for Langfuse span enrichment.
# {input, output, backend} — read by run.py right after the call.
LAST_USAGE: dict = {}


def extract_bedrock(transcript: str, kind: str) -> str:
    import boto3

    LAST_USAGE.clear()
    model_id = os.environ["BEDROCK_MODEL_ID"]
    br = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = br.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": _PROMPT.format(kind=kind, transcript=transcript)}]}],
        inferenceConfig={"maxTokens": 100, "temperature": 0},
    )
    u = resp.get("usage", {})
    LAST_USAGE.update(input=u.get("inputTokens", 0), output=u.get("outputTokens", 0),
                      backend="bedrock", model=model_id)
    return _clean(resp["output"]["message"]["content"][0]["text"].strip())


def extract_gemini(transcript: str, kind: str) -> str:
    import time

    from google import genai
    from google.genai import types

    _proj = os.environ.get("GCP_PROJECT")
    client = (
        genai.Client(vertexai=True, project=_proj,
                     location=os.environ.get("GCP_LOCATION", "global"))
        if _proj else
        genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    )
    # Gemini 3.x counts thinking tokens against max_output_tokens and rejects
    # thinking_budget=0 for flash — so give it room. JSON mode + an explicit
    # envelope stops it from narrating instead of answering (seen on hard emails).
    cfg = types.GenerateContentConfig(
        temperature=0, max_output_tokens=2000, response_mime_type="application/json",
    )
    model = os.environ.get("GEMINI_MODEL_ID", "gemini-3.6-flash")
    prompt = _PROMPT.format(kind=kind, transcript=transcript) + '\nReturn {"value": "<the value>"}.'

    LAST_USAGE.clear()
    last: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
            m = getattr(resp, "usage_metadata", None)
            if m:
                LAST_USAGE.update(input=getattr(m, "prompt_token_count", 0) or 0,
                                  output=getattr(m, "candidates_token_count", 0) or 0,
                                  backend="gemini", model=model)
            txt = (resp.text or "").strip()
            try:
                txt = json.loads(txt).get("value", txt)
            except (json.JSONDecodeError, AttributeError):
                pass
            return _clean(str(txt))
        except Exception as e:
            last = e
            r = repr(e)
            if "429" in r or "RESOURCE_EXHAUSTED" in r:
                time.sleep(30 * (attempt + 1))  # free-tier RPM/RPD limits
            elif "503" in r or "UNAVAILABLE" in r:
                time.sleep(3 * (attempt + 1))
            else:
                raise
    raise last  # type: ignore[misc]


def _clean(s: str) -> str:
    s = s.strip().strip("`\"'").strip()
    if s.startswith("-> "):
        s = s[3:]
    s = s.strip("`\"'? ").strip()
    for pre in ("the name is", "the email is", "name:", "email:", "answer:"):
        if s.lower().startswith(pre):
            s = s[len(pre):].strip()
    s = s.splitlines()[0].strip() if s else s
    # A name or email is short. Anything long is the model narrating instead of
    # answering (Gemini 3.x does this on the hardest spelled-out samples) — score
    # it as a clean miss, don't dump a paragraph into the report table.
    return "" if len(s) > 60 else s


EXTRACTORS = {"bedrock-haiku": extract_bedrock, "gemini-flash": extract_gemini}


if __name__ == "__main__":  # offline self-checks (no network / creds)
    assert _clean("The name is Jane Doe") == "Jane Doe"
    assert _clean("x" * 80) == ""
    _dg = {"results": {"channels": [{"alternatives": [{"transcript": "  hello world "}]}]}}
    assert _deepgram_transcript(_dg) == "hello world"
    assert _deepgram_transcript({"results": {"channels": [{"alternatives": [{}]}]}}) == ""
    if not os.environ.get("DEEPGRAM_API_KEY"):
        import asyncio as _a
        try:
            _a.run(transcribe_deepgram("/dev/null"))
            raise SystemExit("expected RuntimeError without DEEPGRAM_API_KEY")
        except RuntimeError:
            pass
    print("models demo ok")
