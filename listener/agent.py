"""call-copilot listener — joins a LiveKit room as a SILENT participant, subscribes
to every human's audio track, streams each to AWS Transcribe, and feeds the
running transcript to the incremental field extractor.

No TTS. No RealtimeModel. No AgentSession. This agent never speaks.

Forked from voice-demo/livekit-agent/agent.py (worker options + health server).
"""

import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli

from transcribe_stream import TranscribeSession  # Fase 1
from extract import Extractor                    # Fase 2

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("copilot-listener")

WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "http://localhost:3000")
FIELDS_SECRET = os.environ.get("FIELDS_WEBHOOK_SECRET", "")


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect(auto_subscribe=rtc.AutoSubscribe.AUDIO_ONLY)
    room = ctx.room
    logger.info("listening on room=%s", room.name)

    extractor = Extractor(
        room_name=room.name,
        web_base_url=WEB_BASE_URL,
        fields_secret=FIELDS_SECRET,
    )

    # one Transcribe stream per human participant; speaker label comes from
    # which participant the track belongs to (cleaner than Transcribe diarization).
    sessions: dict[str, TranscribeSession] = {}

    async def on_track(track: rtc.Track, participant: rtc.RemoteParticipant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        speaker = participant.identity  # "vcc" | "family"
        ts = TranscribeSession(speaker=speaker, on_final=extractor.on_turn)
        sessions[participant.sid] = ts
        await ts.run(rtc.AudioStream(track))

    @room.on("track_subscribed")
    def _(track, pub, participant):
        asyncio.create_task(on_track(track, participant))

    @room.on("disconnected")
    def _(*_a):
        asyncio.create_task(extractor.flush())

    # keep the job alive until the room ends
    await ctx.wait_for_disconnect()
    await extractor.flush()
    for ts in sessions.values():
        await ts.close()


# ── health server (Railway) ──────────────────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_a):
        pass


def _start_health_server(port: int) -> None:
    srv = HTTPServer(("", port), _HealthHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    logger.info("health server on :%d", port)


if __name__ == "__main__":
    _start_health_server(int(os.environ.get("PORT", 8081)))
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="copilot-listener",
        num_idle_processes=2,
        load_threshold=0.75,
    ))
