"""Transcription + per-model field extraction for the eval harness.

- transcribe_file: AWS Transcribe streaming, fed from a local 16 kHz wav
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
    '- name: proper capitalisation, real spelling (e.g. "Kathleen O\'Brien")\n'
    '- email: a valid address, expanding "at"/"dot"/"underscore"/"hyphen"/digits '
    '(e.g. "jane.doe@gmail.com")\n\n'
    "Transcript:\n{transcript}\n"
)


async def transcribe_file(path: str, region: str, language: str = "en-US") -> str:
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
        language_code=language, media_sample_rate_hz=16_000, media_encoding="pcm"
    )

    async def pump():
        with wave.open(path) as w:
            assert w.getframerate() == 16_000 and w.getnchannels() == 1
            step = 16_000 * 50 // 1000  # 50 ms
            while chunk := w.readframes(step):
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
                await asyncio.sleep(0.01)
        await stream.input_stream.end_stream()

    await asyncio.gather(pump(), H(stream.output_stream).handle_events())
    return " ".join(parts).strip()


def extract_bedrock(transcript: str, kind: str) -> str:
    import boto3

    model_id = os.environ["BEDROCK_MODEL_ID"]
    br = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = br.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": _PROMPT.format(kind=kind, transcript=transcript)}]}],
        inferenceConfig={"maxTokens": 60, "temperature": 0},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


def extract_gemini(transcript: str, kind: str) -> str:
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL_ID", "gemini-2.5-flash"),
        contents=_PROMPT.format(kind=kind, transcript=transcript),
        config={"temperature": 0, "max_output_tokens": 60},
    )
    return (resp.text or "").strip()


EXTRACTORS = {"bedrock-haiku": extract_bedrock, "gemini-flash": extract_gemini}
