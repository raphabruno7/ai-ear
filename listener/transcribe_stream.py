"""AWS Transcribe streaming — one instance per human participant's audio track.

Fase 1: implement `run()` — pump LiveKit AudioFrames (resample to 16 kHz PCM16
mono) into `amazon-transcribe` TranscribeStreamingClient.start_stream_transcription,
and call `on_final(speaker, text)` for each stabilised final result.

Left as a stub so the rest of the pipeline (agent wiring, extractor) can be
written and unit-tested without AWS credentials.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

logger = logging.getLogger("copilot-listener.stt")

OnFinal = Callable[[str, str], Awaitable[None]]  # (speaker, text)


class TranscribeSession:
    def __init__(self, speaker: str, on_final: OnFinal) -> None:
        self.speaker = speaker
        self.on_final = on_final
        self._total_seconds = 0.0

    @property
    def audio_seconds(self) -> float:
        return self._total_seconds

    async def run(self, audio_stream) -> None:  # audio_stream: rtc.AudioStream
        raise NotImplementedError("Fase 1: wire AWS Transcribe streaming here")

    async def close(self) -> None:
        pass
