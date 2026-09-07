"""Incremental structured field extraction.

Fase 1: `on_turn` just accumulates the transcript and reports turns (so the
Transcribe wiring is testable end to end).
Fase 2: `_extract` calls Bedrock (Claude Haiku) `converse` with the accumulated
transcript + a forced `emit_fields` tool call, merges each field (only overwrite
when new confidence > stored), persists changes to `extracted_fields` with
latency_ms, and POSTs them to the web dashboard. `@observe` (Langfuse) goes on
`on_turn` in Fase 3.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field as dc_field

from pydantic import BaseModel

import pricing
from trace import span

logger = logging.getLogger("copilot-listener.extract")

FIELD_NAMES = [
    "owner_name", "owner_phone", "owner_email",
    "pet_name", "visit_type", "preferred_time", "clinical_notes",
]

_SYSTEM = (
    "You are a silent copilot listening to a live call between a veterinary care "
    "coordinator and a pet owner. Extract appointment and clinical fields from the "
    "transcript so far. Call emit_fields with every field you are reasonably sure of. "
    "Use proper formatting: names with real spelling and capitalisation; emails as "
    "valid addresses, expanding spoken 'at' / 'dot' / 'underscore' / 'hyphen'; phone "
    "as digits. visit_type: infer one of 'wellness', 'sick', 'urgent', 'follow-up', "
    "'end-of-life' from the reason for the call (e.g. not eating / lethargic -> 'sick'). "
    "Only include a field the transcript actually supports. confidence is 0..1."
)

_TOOL = {
    "toolSpec": {
        "name": "emit_fields",
        "description": (
            "Report every appointment/clinical field the transcript currently "
            "supports. Called once per extraction pass over the running transcript; "
            "re-report each field every pass with your best current value."
        ),
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "enum": FIELD_NAMES},
                            "value": {"type": "string", "description":
                                      "Formatted per the system prompt — real spelling, valid email, digits-only phone."},
                            "confidence": {"type": "number", "description":
                                           "0..1: how directly the transcript supports this value."},
                        },
                        "required": ["name", "value", "confidence"],
                    },
                }
            },
            "required": ["fields"],
        }},
    }
}


class AppointmentFields(BaseModel):
    owner_name: str | None = None
    owner_phone: str | None = None
    owner_email: str | None = None
    pet_name: str | None = None
    visit_type: str | None = None
    preferred_time: str | None = None
    clinical_notes: str | None = None


@dataclass
class _FieldState:
    value: str
    confidence: float


@dataclass
class Extractor:
    room_name: str
    session_id: str = ""
    vcc_id: str = "vcc-1"
    region: str = "us-east-1"
    model_id: str = ""                          # bedrock model / inference profile id
    backend: str = "bedrock"                    # "bedrock" | "gemini"
    gemini_model: str = "gemini-3.6-flash"
    supabase: "object | None" = None            # supabase client (persist changed fields)
    ws_broadcast: "callable | None" = None      # async (session_id, fields_dict) -> None
    _transcript: list[tuple[str, str]] = dc_field(default_factory=list)
    _state: dict[str, _FieldState] = dc_field(default_factory=dict)
    min_extract_gap_s: float = 12.0            # debounce — don't re-extract on every turn
    _bedrock: "object | None" = None
    _genai: "object | None" = None
    _last_extract: float = 0.0
    _turns_since_extract: int = 0
    _in_tokens: int = 0
    _out_tokens: int = 0
    _stt_seconds: float = 0.0

    def merge(self, name: str, value: str, confidence: float) -> bool:
        """Returns True if the field changed (new or higher-confidence value)."""
        cur = self._state.get(name)
        if cur and (confidence <= cur.confidence or value == cur.value):
            return False
        self._state[name] = _FieldState(value=value, confidence=confidence)
        return True

    def snapshot(self) -> dict[str, str]:
        return {k: v.value for k, v in self._state.items()}

    @property
    def turns(self) -> list[tuple[str, str]]:
        return list(self._transcript)

    async def on_turn(self, speaker: str, text: str) -> None:
        self._transcript.append((speaker, text))
        self._turns_since_extract += 1
        logger.info("[%s] %s", speaker, text)

        now = time.monotonic()
        # debounce: extract once the call has settled a bit, not on every utterance
        if now - self._last_extract < self.min_extract_gap_s and self._turns_since_extract < 4:
            return
        self._last_extract = now
        self._turns_since_extract = 0

        changed = await self._extract(now)
        if changed and self.ws_broadcast:
            await self.ws_broadcast(self.session_id, self.snapshot())

    async def finalize(self) -> None:
        """One last extraction over the full transcript at end of call."""
        if self._transcript:
            changed = await self._extract(time.monotonic())
            if changed and self.ws_broadcast:
                await self.ws_broadcast(self.session_id, self.snapshot())

    async def _persist(self, name: str, value: str, confidence: float, latency_ms: int) -> None:
        if not self.supabase or not self.session_id:
            return
        self.supabase.table("extracted_fields").insert({
            "session_id": self.session_id,
            "vcc_id": self.vcc_id,
            "field_name": name,
            "field_value": value,
            "confidence": confidence,
            "model": self.backend,
            "latency_ms": latency_ms,
        }).execute()

    def _bedrock_client(self):
        if self._bedrock is None:
            import boto3
            self._bedrock = boto3.client("bedrock-runtime", region_name=self.region)
        return self._bedrock

    def _genai_client(self):
        if self._genai is None:
            from google import genai
            proj = os.environ.get("GCP_PROJECT")
            if proj:  # Vertex AI — billed to the GCP project, no free-tier daily cap
                self._genai = genai.Client(
                    vertexai=True, project=proj,
                    location=os.environ.get("GCP_LOCATION", "global"),
                )
            else:
                self._genai = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return self._genai

    async def _emit_bedrock(self, convo: str) -> list[dict]:
        resp = await asyncio.to_thread(
            self._bedrock_client().converse,
            modelId=self.model_id,
            system=[{"text": _SYSTEM}],
            messages=[{"role": "user", "content": [{"text": convo}]}],
            toolConfig={"tools": [_TOOL], "toolChoice": {"tool": {"name": "emit_fields"}}},
            inferenceConfig={"maxTokens": 400, "temperature": 0},
        )
        usage = resp.get("usage", {})
        self._in_tokens += usage.get("inputTokens", 0)
        self._out_tokens += usage.get("outputTokens", 0)
        return _parse_emitted(resp)

    async def _emit_gemini(self, convo: str) -> list[dict]:
        from google.genai import types

        prompt = (
            _SYSTEM + "\n\nTranscript:\n" + convo + "\n\n"
            f"Return a JSON array of {{name, value, confidence}} objects — "
            f"name one of {FIELD_NAMES}; omit fields the transcript does not support."
        )
        resp = await asyncio.to_thread(
            self._genai_client().models.generate_content,
            model=self.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0, max_output_tokens=2000, response_mime_type="application/json",
            ),
        )
        u = getattr(resp, "usage_metadata", None)
        if u:
            self._in_tokens += getattr(u, "prompt_token_count", 0) or 0
            self._out_tokens += getattr(u, "candidates_token_count", 0) or 0
        return _parse_json_fields(resp.text or "")

    async def _extract(self, turn_ts: float) -> bool:
        if self.backend == "bedrock" and not self.model_id:
            return False
        convo = "\n".join(f"{spk}: {txt}" for spk, txt in self._transcript)
        tin0, tout0 = self._in_tokens, self._out_tokens
        with span("extract_turn", input=convo) as sp:
            try:
                emit = self._emit_gemini if self.backend == "gemini" else self._emit_bedrock
                emitted = await emit(convo)
            except Exception as e:  # throttling / transient 5xx — keep listening
                logger.warning("%s extract skipped: %s", self.backend, e)
                sp.update(level="WARNING", status_message=str(e))
                return False

            latency_ms = int((time.monotonic() - turn_ts) * 1000)
            d_in, d_out = self._in_tokens - tin0, self._out_tokens - tout0
            sp.update(
                output=emitted,
                model=self.gemini_model if self.backend == "gemini" else self.model_id,
                metadata={"latency_ms": latency_ms, "backend": self.backend},
                usage_details={"input": d_in, "output": d_out},
                cost_details={"total": pricing.llm_cost(d_in, d_out, self.backend)},
            )

        changed = False
        for f in emitted:
            name = f.get("name")
            value = (f.get("value") or "").strip()
            conf = float(f.get("confidence", 0) or 0)
            if name in FIELD_NAMES and value and self.merge(name, value, conf):
                changed = True
                await self._persist(name, value, conf, latency_ms)
        return changed

    def add_stt_seconds(self, seconds: float) -> None:
        self._stt_seconds += seconds

    async def flush(self) -> None:
        """Write accumulated per-call cost."""
        from trace import flush as trace_flush
        trace_flush()
        if not self.supabase or not self.session_id:
            return
        try:
            usd_stt = pricing.stt_cost(self._stt_seconds)
            usd_llm = pricing.llm_cost(self._in_tokens, self._out_tokens, self.backend)
            self.supabase.table("call_costs").upsert({
                "session_id": self.session_id,
                "stt_seconds": round(self._stt_seconds, 2),
                "llm_input_tokens": self._in_tokens,
                "llm_output_tokens": self._out_tokens,
                "usd_stt": round(usd_stt, 5),
                "usd_llm": round(usd_llm, 5),
                "usd_total": round(usd_stt + usd_llm, 5),
                "updated_at": "now()",
            }).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning("cost flush failed: %s", e)


def _parse_emitted(resp: dict) -> list[dict]:
    for block in resp.get("output", {}).get("message", {}).get("content", []):
        if "toolUse" in block:
            return block["toolUse"]["input"].get("fields", [])
    return []


def _parse_json_fields(text: str) -> list[dict]:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if isinstance(data, dict):  # {"fields": [...]} or {name: {value, confidence}}
        if "fields" in data:
            return data["fields"]
        return [{"name": k, **v} if isinstance(v, dict) else {"name": k, "value": v, "confidence": 0.7}
                for k, v in data.items()]
    return data if isinstance(data, list) else []


def demo() -> None:
    e = Extractor(room_name="t")
    assert e.merge("owner_name", "Kathleen", 0.7) is True
    assert e.merge("owner_name", "Cathlyn", 0.5) is False
    assert e.merge("owner_name", "Kathleen", 0.9) is False
    assert e.merge("owner_name", "Katherine", 0.95) is True
    assert e.snapshot()["owner_name"] == "Katherine"

    resp = {"output": {"message": {"content": [
        {"text": "ok"},
        {"toolUse": {"name": "emit_fields", "input": {"fields": [
            {"name": "owner_name", "value": "Kathleen O'Brien", "confidence": 0.9},
            {"name": "pet_name", "value": "Luna", "confidence": 0.8},
        ]}}},
    ]}}}
    got = _parse_emitted(resp)
    assert [f["name"] for f in got] == ["owner_name", "pet_name"], got
    assert _parse_emitted({"output": {"message": {"content": [{"text": "hi"}]}}}) == []

    j = _parse_json_fields('```json\n[{"name":"pet_name","value":"Luna","confidence":0.8}]\n```')
    assert j == [{"name": "pet_name", "value": "Luna", "confidence": 0.8}], j
    j2 = _parse_json_fields('{"owner_name": {"value": "Kathleen", "confidence": 0.9}}')
    assert j2 == [{"name": "owner_name", "value": "Kathleen", "confidence": 0.9}], j2
    assert _parse_json_fields("not json") == []
    print("extract demo ok")


if __name__ == "__main__":
    demo()
