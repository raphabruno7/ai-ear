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

import logging
import time
from dataclasses import dataclass, field as dc_field

from pydantic import BaseModel

logger = logging.getLogger("copilot-listener.extract")


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

    async def _extract(self, turn_ts: float) -> bool:
        # Fase 2: Bedrock converse over self._transcript -> emitted fields ->
        # self.merge(...) -> self._persist(...) with
        # latency_ms = int((time.monotonic() - turn_ts) * 1000)
        return False

    async def flush(self) -> None:
        pass


def demo() -> None:
    e = Extractor(room_name="t")
    assert e.merge("owner_name", "Kathleen", 0.7) is True
    assert e.merge("owner_name", "Cathlyn", 0.5) is False
    assert e.merge("owner_name", "Kathleen", 0.9) is False
    assert e.merge("owner_name", "Katherine", 0.95) is True
    assert e.snapshot()["owner_name"] == "Katherine"
    print("extract merge demo ok")


if __name__ == "__main__":
    demo()
