"""AWS Transcribe streaming — one instance per human participant's audio track.

The LiveKit AudioStream is created already resampled to 16 kHz mono s16le, so we
forward raw PCM chunks to Transcribe and surface stabilised final results.

Transcribe closes a streaming session on its own after a stretch of silence; the
LiveKit connection can also drop and resume. Either way the send fails — we
reopen a fresh Transcribe stream and keep going, so a call survives quiet gaps
and network blips.
"""

from __future__ import annotations

import asyncio
import bisect
import logging
import time
from typing import Awaitable, Callable

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

logger = logging.getLogger("copilot-listener.stt")

# (speaker, text, spoken_end_ts, stt_lag_ms):
#   spoken_end_ts — time.monotonic() when we *had* the audio the speaker's last
#     word ended on (i.e. when that frame arrived from LiveKit). None if unknown.
#   stt_lag_ms — wall ms from there to this stabilised final arriving. This is
#     Transcribe's processing + network lag, isolated from bursty frame delivery.
OnFinal = Callable[[str, str, "float | None", "int | None"], Awaitable[None]]


class _Handler(TranscriptResultStreamHandler):
    def __init__(self, output_stream, speaker: str, on_final: OnFinal, session: "TranscribeSession"):
        super().__init__(output_stream)
        self._speaker = speaker
        self._on_final = on_final
        self._session = session

    async def handle_transcript_event(self, event: TranscriptEvent) -> None:
        for result in event.transcript.results:
            if result.is_partial or not result.alternatives:
                continue
            text = result.alternatives[0].transcript.strip()
            if not text:
                continue
            spoken_end_ts = self._session._recv_ts_for(result.end_time)
            stt_lag_ms = (max(0, int((time.monotonic() - spoken_end_ts) * 1000))
                          if spoken_end_ts is not None else None)
            await self._on_final(self._speaker, text, spoken_end_ts, stt_lag_ms)


class TranscribeSession:
    def __init__(self, speaker: str, on_final: OnFinal, region: str, language: str = "en-US"):
        self.speaker = speaker
        self.on_final = on_final
        self.region = region
        self.language = language
        self._total_seconds = 0.0
        self._stream = None
        self._handler_task: asyncio.Task | None = None
        self._stopped = False
        self._reopens = 0
        # (audio_seconds_into_current_stream, monotonic_ts_frame_arrived), bounded.
        # result.end_time is per-stream, so this resets on every _open().
        self._marks: list[tuple[float, float]] = []
        self._stream_audio_s = 0.0

    @property
    def audio_seconds(self) -> float:
        return self._total_seconds

    def _recv_ts_for(self, end_time: float | None) -> float | None:
        """Wall ts at which we received the audio frame covering `end_time`."""
        if end_time is None or not self._marks:
            return None
        i = bisect.bisect_left(self._marks, (end_time,))
        return self._marks[min(i, len(self._marks) - 1)][1]

    async def run(self, audio_stream) -> None:
        """audio_stream: rtc.AudioStream, 16 kHz mono. Returns when the track ends."""
        await self._open()
        try:
            async for ev in audio_stream:
                if self._stopped:
                    break
                frame = ev.frame
                dur = frame.samples_per_channel / frame.sample_rate
                self._total_seconds += dur
                self._stream_audio_s += dur
                self._marks.append((self._stream_audio_s, time.monotonic()))
                if len(self._marks) > 6000:      # ~60s at 10ms frames — plenty
                    del self._marks[:2000]
                for _ in range(2):
                    try:
                        await self._stream.input_stream.send_audio_event(audio_chunk=bytes(frame.data))
                        break
                    except Exception as e:  # stream closed (silence timeout) or connection blip
                        if self._stopped:
                            return
                        self._reopens += 1
                        logger.info("transcribe reopen #%d for %s (%s)", self._reopens, self.speaker, e)
                        await self._open()
        finally:
            self._stopped = True
            await self._safe_end()
            if self._handler_task:
                self._handler_task.cancel()

    async def _open(self) -> None:
        await self._safe_end()
        if self._handler_task:
            self._handler_task.cancel()
        client = TranscribeStreamingClient(region=self.region)
        self._stream = await client.start_stream_transcription(
            language_code=self.language, media_sample_rate_hz=16_000, media_encoding="pcm",
        )
        # result.end_time restarts at 0 for the new stream — reset the mark table.
        # ponytail: mid-stream trim above can drop marks for a >60s continuous
        # monologue; then _recv_ts_for understates lag for that one result.
        self._marks.clear()
        self._stream_audio_s = 0.0
        self._handler_task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        try:
            await _Handler(self._stream.output_stream, self.speaker,
                           self.on_final, self).handle_events()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — stream ended; run()'s send will reopen
            logger.debug("transcribe output stream ended for %s (%s)", self.speaker, e)

    async def _safe_end(self) -> None:
        if self._stream is not None:
            try:
                await self._stream.input_stream.end_stream()
            except Exception:
                pass

    async def close(self) -> None:
        self._stopped = True
        await self._safe_end()
        if self._handler_task:
            # let the output stream drain naturally before cancelling — avoids an
            # awscrt "set_result on CANCELLED future" during teardown
            try:
                await asyncio.wait_for(asyncio.shield(self._handler_task), 1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                # CancelledError is BaseException, not Exception — must be named
                # explicitly or teardown (finalize/flush) is skipped upstream
                self._handler_task.cancel()
