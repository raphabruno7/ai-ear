"""call-copilot listener — joins a LiveKit room as a SILENT participant, subscribes
to every human's audio track, streams each to AWS Transcribe, and feeds the
running transcript to the incremental field extractor.

No TTS. No audio published. This agent never speaks.

    python agent.py --room demo-1              # one room, exit when it ends
    python agent.py --watch call-              # service mode: join every new
                                              # room whose name starts with the prefix

Deploys to Railway (Dockerfile) in --watch mode. One shared fields WebSocket
serves all concurrent rooms, keyed by session id.
"""

import argparse
import asyncio
import logging
import os
import time

from dotenv import load_dotenv
from livekit import rtc

import audio_apm
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
EXTRACT_BACKEND = os.environ.get("EXTRACT_BACKEND", "gemini")  # gemini | bedrock (sleep mode)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL_ID", "gemini-3.6-flash")
# one port for the fields WS + /health. Railway sets $PORT; default 8765 locally.
WS_PORT = int(os.environ.get("FIELDS_WS_PORT") or os.environ.get("PORT") or 8765)
TRANSCRIBE_VOCAB = os.environ.get("TRANSCRIBE_VOCAB") or None
AUDIO_APM = os.environ.get("AUDIO_APM") or ""   # e.g. "ns,hpf,agc"; empty = passthrough


def _supabase():
    from supabase import create_client
    return create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


async def run_listener(room_name: str, vcc_id: str, language: str,
                       fields_ws: FieldsWS | None = None) -> str:
    sb = _supabase()
    row = sb.table("sessions").upsert(
        {"room_name": room_name, "vcc_id": vcc_id, "call_source": "sim"},
        on_conflict="room_name",
    ).execute().data[0]
    session_id = row["id"]
    logger.info("session %s (room=%s vcc=%s)", session_id, room_name, vcc_id)

    own_ws = fields_ws is None      # --room path owns its WS; --watch shares one
    if own_ws:
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
    logger.info("extraction backend: %s | audio APM: %s", EXTRACT_BACKEND, AUDIO_APM or "off")
    sessions: dict[str, TranscribeSession] = {}
    done = asyncio.Event()
    room = rtc.Room()
    last_activity = 0.0  # monotonic ts of the last transcript turn

    async def _on_turn(speaker: str, text: str,
                       spoken_end_ts: float | None = None, stt_lag_ms: int | None = None) -> None:
        nonlocal last_activity
        last_activity = time.monotonic()
        await extractor.on_turn(speaker, text, spoken_end_ts, stt_lag_ms)

    def _start(track: rtc.Track, participant: rtc.RemoteParticipant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        speaker = participant.identity  # "vcc" | "family"
        apm = audio_apm.build_apm(AUDIO_APM)  # None unless AUDIO_APM is set
        stream = rtc.AudioStream(track, sample_rate=16_000, num_channels=1,
                                 frame_size_ms=audio_apm.FRAME_MS if apm else None)
        ts = TranscribeSession(speaker, _on_turn, REGION, language,
                               vocabulary=TRANSCRIBE_VOCAB, apm=apm)
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
    teardown = [extractor.finalize(), extractor.flush()]
    if own_ws:
        teardown.append(fields_ws.stop())
    for step in teardown:
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


async def watch(prefix: str, vcc_id: str, language: str, poll_s: float = 3.0) -> None:
    """Service mode: poll LiveKit for new rooms matching `prefix`, run a listener
    for each. One shared fields WebSocket for all of them."""
    from livekit import api

    fields_ws = FieldsWS(port=WS_PORT)
    await fields_ws.start()
    lkapi = api.LiveKitAPI(LIVEKIT_URL)
    seen: dict[str, asyncio.Task] = {}   # every room name ever served — LiveKit keeps
                                         # an empty room alive for minutes; don't re-join it
    logger.info("watching for rooms '%s*' (poll %.0fs)", prefix, poll_s)
    try:
        while True:
            try:
                resp = await lkapi.room.list_rooms(api.ListRoomsRequest())
                for room in resp.rooms:
                    if room.name.startswith(prefix) and room.name not in seen:
                        logger.info("new room %s — starting listener", room.name)
                        seen[room.name] = asyncio.create_task(
                            run_listener(room.name, vcc_id, language, fields_ws)
                        )
            except Exception as e:  # noqa: BLE001 — a poll blip must not kill the service
                logger.warning("room poll failed: %s", e)
            for name, t in seen.items():
                if t.done() and not getattr(t, "_logged_done", False):
                    t._logged_done = True  # type: ignore[attr-defined]
                    if t.exception():
                        logger.warning("listener for %s crashed: %r", name, t.exception())
            await asyncio.sleep(poll_s)
    finally:
        await lkapi.aclose()
        await fields_ws.stop()


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--room", help="join one room, exit when it ends")
    g.add_argument("--watch", metavar="PREFIX",
                   help="service mode: join every new room whose name starts with PREFIX")
    ap.add_argument("--vcc", default="vcc-1")
    ap.add_argument("--language", default="en-US")
    args = ap.parse_args()

    if args.watch:
        asyncio.run(watch(args.watch, args.vcc, args.language))
    else:
        asyncio.run(run_listener(args.room, args.vcc, args.language))


if __name__ == "__main__":
    main()
