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
import logging
import time
from dataclasses import dataclass, field as dc_field

from pydantic import BaseModel

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
    "as digits. Only include a field the transcript actually supports. confidence is 0..1."
)

_TOOL = {
    "toolSpec": {
        "name": "emit_fields",
        "description": "Report the currently-known appointment/clinical fields.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "enum": FIELD_NAMES},
                            "value": {"type": "string"},
                            "confidence": {"type": "number"},
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
    model_id: str = ""
    supabase: "object | None" = None          # supabase client (persist changed fields)
    ws_broadcast: "callable | None" = None     # async (session_id, fields_dict) -> None
    _transcript: list[tuple[str, str]] = dc_field(default_factory=list)
    _state: dict[str, _FieldState] = dc_field(default_factory=dict)
    _bedrock: "object | None" = None
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
        logger.info("[%s] %s", speaker, text)
        turn_ts = time.monotonic()
        changed = await self._extract(turn_ts)
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
            "model": self.model_id or "bedrock-haiku",
            "latency_ms": latency_ms,
        }).execute()

    def _client(self):
        if self._bedrock is None:
            import boto3
            self._bedrock = boto3.client("bedrock-runtime", region_name=self.region)
        return self._bedrock

    async def _extract(self, turn_ts: float) -> bool:
        if not self.model_id:
            return False
        convo = "\n".join(f"{spk}: {txt}" for spk, txt in self._transcript)
        with span("extract_turn", input=convo) as sp:
            try:
                resp = await asyncio.to_thread(
                    self._client().converse,
                    modelId=self.model_id,
                    system=[{"text": _SYSTEM}],
                    messages=[{"role": "user", "content": [{"text": convo}]}],
                    toolConfig={"tools": [_TOOL], "toolChoice": {"tool": {"name": "emit_fields"}}},
                    inferenceConfig={"maxTokens": 400, "temperature": 0},
                )
            except Exception as e:  # throttling during new-account window, transient 5xx
                logger.warning("bedrock extract skipped: %s", e)
                sp.update(level="WARNING", status_message=str(e))
                return False

            usage = resp.get("usage", {})
            self._in_tokens += usage.get("inputTokens", 0)
            self._out_tokens += usage.get("outputTokens", 0)
            emitted = _parse_emitted(resp)
            latency_ms = int((time.monotonic() - turn_ts) * 1000)
            sp.update(output=emitted, metadata={
                "input_tokens": usage.get("inputTokens", 0),
                "output_tokens": usage.get("outputTokens", 0),
                "latency_ms": latency_ms,
            })

        changed = False
        for f in emitted:
            name, value, conf = f.get("name"), (f.get("value") or "").strip(), float(f.get("confidence", 0))
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
            import pricing
            usd_stt = pricing.stt_cost(self._stt_seconds)
            usd_llm = pricing.llm_cost(self._in_tokens, self._out_tokens)
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
    print("extract demo ok")


if __name__ == "__main__":
    demo()
