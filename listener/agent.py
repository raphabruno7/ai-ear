"""call-copilot listener — joins a LiveKit room as a SILENT participant, subscribes
to every human's audio track, streams each to AWS Transcribe, and feeds the
running transcript to the incremental field extractor.

No TTS. No audio published. This agent never speaks.

    python agent.py --room demo-1 [--vcc vcc-1] [--language en-US]

Deploys to Railway (Dockerfile). In production a room is assigned via an HTTP
trigger; for the demo the room name is a CLI arg.
"""

import argparse
import asyncio
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv
from livekit import rtc

from extract import Extractor
from lktoken import listener_token
from transcribe_stream import TranscribeSession
from ws_server import FieldsWS

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("copilot-listener")

REGION = os.environ.get("AWS_REGION", "us-east-1")
LIVEKIT_URL = os.environ["LIVEKIT_URL"]
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
EXTRACT_BACKEND = os.environ.get("EXTRACT_BACKEND", "bedrock")  # bedrock | gemini
GEMINI_MODEL = os.environ.get("GEMINI_MODEL_ID", "gemini-3.6-flash")
WS_PORT = int(os.environ.get("FIELDS_WS_PORT", 8765))


def _supabase():
    from supabase import create_client
    return create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


async def run_listener(room_name: str, vcc_id: str, language: str) -> str:
    sb = _supabase()
    row = sb.table("sessions").upsert(
        {"room_name": room_name, "vcc_id": vcc_id, "call_source": "sim"},
        on_conflict="room_name",
    ).execute().data[0]
    session_id = row["id"]
    logger.info("session %s (room=%s vcc=%s)", session_id, room_name, vcc_id)

    fields_ws = FieldsWS(port=WS_PORT)
    await fields_ws.start()

    extractor = Extractor(
        room_name=room_name,
        session_id=session_id,
        vcc_id=vcc_id,
        region=REGION,
        model_id=BEDROCK_MODEL_ID,
        backend=EXTRACT_BACKEND,
        gemini_model=GEMINI_MODEL,
        supabase=sb,
        ws_broadcast=fields_ws.broadcast,
    )
    logger.info("extraction backend: %s", EXTRACT_BACKEND)
    sessions: dict[str, TranscribeSession] = {}
    done = asyncio.Event()
    room = rtc.Room()
    last_activity = 0.0  # monotonic ts of the last transcript turn

    async def _on_turn(speaker: str, text: str) -> None:
        nonlocal last_activity
        last_activity = time.monotonic()
        await extractor.on_turn(speaker, text)

    def _start(track: rtc.Track, participant: rtc.RemoteParticipant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        speaker = participant.identity  # "vcc" | "family"
        stream = rtc.AudioStream(track, sample_rate=16_000, num_channels=1)
        ts = TranscribeSession(speaker, _on_turn, REGION, language)
        sessions[participant.sid] = ts
        logger.info("transcribing track from %s", speaker)
        asyncio.create_task(ts.run(stream))

    @room.on("track_subscribed")
    def _(track, pub, participant):
        _start(track, participant)

    @room.on("participant_disconnected")
    def _(participant):
        # end the call once every human has left
        if not [p for p in room.remote_participants.values()]:
            done.set()

    @room.on("disconnected")
    def _(*_a):
        done.set()

    async def _idle_watch() -> None:
        # LiveKit can swallow participant_disconnected on a signalling resume, leaving
        # the call hanging forever. End it once transcripts stop arriving.
        # ponytail: fixed idle threshold; a real call with a long pause could trip it —
        # raise CALL_IDLE_END_S if that happens in production.
        idle_s = float(os.environ.get("CALL_IDLE_END_S", 30))
        while not done.is_set():
            await asyncio.sleep(3)
            if sessions and last_activity and time.monotonic() - last_activity > idle_s:
                logger.info("no transcript for %.0fs — ending call", idle_s)
                done.set()
                return

    await room.connect(LIVEKIT_URL, listener_token(room_name))
    logger.info("connected, listening")
    # pick up tracks already present
    for p in room.remote_participants.values():
        for pub in p.track_publications.values():
            if pub.track:
                _start(pub.track, p)

    watchdog = asyncio.create_task(_idle_watch())
    await done.wait()
    watchdog.cancel()
    for ts in sessions.values():
        try:
            await ts.close()
        except BaseException:  # noqa: BLE001 — best-effort teardown; never skip finalize/flush below
            pass
    total_audio = sum(ts.audio_seconds for ts in sessions.values())
    extractor.add_stt_seconds(total_audio)
    # best-effort teardown — a network blip at end-of-call must not crash the process
    for step in (extractor.finalize(), extractor.flush(), fields_ws.stop()):
        try:
            await step
        except Exception:  # noqa: BLE001
            logger.warning("teardown step failed", exc_info=True)
    try:
        sb.table("sessions").update({"ended_at": "now()"}).eq("id", session_id).execute()
    except Exception:  # noqa: BLE001
        logger.warning("could not mark session ended_at")
    logger.info("session %s ended — %.1fs audio, %d turns, fields=%s",
                session_id, total_audio, len(extractor.turns), extractor.snapshot())
    await room.disconnect()
    return session_id


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--vcc", default="vcc-1")
    ap.add_argument("--language", default="en-US")
    ap.add_argument("--health-port", type=int, default=int(os.environ.get("PORT", 8081)))
    args = ap.parse_args()

    _start_health_server(args.health_port)
    asyncio.run(run_listener(args.room, args.vcc, args.language))


if __name__ == "__main__":
    main()
