"""AWS Transcribe streaming — one instance per human participant's audio track.

The LiveKit AudioStream is created already resampled to 16 kHz mono s16le, so we
just forward raw PCM chunks to Transcribe and surface stabilised final results.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

logger = logging.getLogger("copilot-listener.stt")

OnFinal = Callable[[str, str], Awaitable[None]]  # (speaker, text)


class _Handler(TranscriptResultStreamHandler):
    def __init__(self, output_stream, speaker: str, on_final: OnFinal):
        super().__init__(output_stream)
        self._speaker = speaker
        self._on_final = on_final

    async def handle_transcript_event(self, event: TranscriptEvent) -> None:
        for result in event.transcript.results:
            if result.is_partial or not result.alternatives:
                continue
            text = result.alternatives[0].transcript.strip()
            if text:
                await self._on_final(self._speaker, text)


class TranscribeSession:
    def __init__(self, speaker: str, on_final: OnFinal, region: str, language: str = "en-US"):
        self.speaker = speaker
        self.on_final = on_final
        self.region = region
        self.language = language
        self._total_seconds = 0.0
        self._stream = None

    @property
    def audio_seconds(self) -> float:
        return self._total_seconds

    async def run(self, audio_stream) -> None:
        """audio_stream: rtc.AudioStream, 16 kHz mono. Returns when the track ends."""
        client = TranscribeStreamingClient(region=self.region)
        self._stream = await client.start_stream_transcription(
            language_code=self.language,
            media_sample_rate_hz=16_000,
            media_encoding="pcm",
        )
        handler = _Handler(self._stream.output_stream, self.speaker, self.on_final)
        await asyncio.gather(self._pump(audio_stream), handler.handle_events())

    async def _pump(self, audio_stream) -> None:
        try:
            async for ev in audio_stream:
                frame = ev.frame
                self._total_seconds += frame.samples_per_channel / frame.sample_rate
                await self._stream.input_stream.send_audio_event(audio_chunk=bytes(frame.data))
        finally:
            await self._stream.input_stream.end_stream()

    async def close(self) -> None:
        if self._stream is not None:
            try:
                await self._stream.input_stream.end_stream()
            except Exception:
                pass
