"""Incremental structured field extraction.

Fase 2: on each final turn, call Bedrock (Claude Haiku) `converse` with the
accumulated transcript + a forced tool call `emit_fields`, then merge each
field into state (only overwrite when new confidence > stored confidence).
Persist every change to `extracted_fields` with latency_ms and POST it to the
web dashboard. `@observe` (Langfuse) goes on `on_turn` in Fase 3.

Stub for now: accumulates transcript, exposes the merge logic (which IS
unit-testable) and leaves the model call unimplemented.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field as dc_field

from pydantic import BaseModel


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
    web_base_url: str = ""
    fields_secret: str = ""
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

    async def on_turn(self, speaker: str, text: str) -> None:
        self._transcript.append((speaker, text))
        _turn_ts = time.monotonic()
        # Fase 2: call Bedrock, iterate emitted fields -> self.merge(...) ->
        # persist changed ones with latency_ms = (now - _turn_ts) * 1000.
        raise NotImplementedError("Fase 2: Bedrock converse + merge + persist")

    async def flush(self) -> None:
        pass


def demo() -> None:
    e = Extractor(room_name="t")
    assert e.merge("owner_name", "Kathleen", 0.7) is True
    assert e.merge("owner_name", "Cathlyn", 0.5) is False   # lower confidence ignored
    assert e.merge("owner_name", "Kathleen", 0.9) is False  # same value, no change
    assert e.merge("owner_name", "Katherine", 0.95) is True # correction wins
    assert e.snapshot()["owner_name"] == "Katherine"
    print("extract merge demo ok")


if __name__ == "__main__":
    demo()
