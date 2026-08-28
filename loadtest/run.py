"""Concurrency + data-isolation load test.

Opens N LiveKit rooms at once, each with its own audio (a distinct name from the
eval dataset), runs the full listen -> transcribe -> extract -> persist path, then:

  - reports extraction latency p50/p95 under load (from extracted_fields.latency_ms)
  - asserts no session's extracted_fields contain another session's value

    python run.py --rooms 5

The LiveKit fan-out (connect/publish/subscribe for N rooms) works today; the
Transcribe + Bedrock legs need the AWS new-account window to clear.
"""

import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "listener"))

from extract import Extractor  # noqa: E402
from lktoken import listener_token  # noqa: E402
from sim_call import publish_track  # noqa: E402
from transcribe_stream import TranscribeSession  # noqa: E402
from livekit import rtc  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL = os.environ.get("BEDROCK_MODEL_ID", "")
LIVEKIT_URL = os.environ["LIVEKIT_URL"]
AUDIO = ROOT / "eval" / "dataset" / "audio"
NAMES = ["n01", "n02", "n03", "n04", "n05", "n06", "n07", "n08", "n09", "n10"]


def _supabase():
    from supabase import create_client
    return create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


async def one_room(sb, idx: int, sample_id: str) -> dict:
    room_name = f"load-{uuid.uuid4().hex[:6]}-{idx}"
    vcc_id = f"vcc-{idx}"
    row = sb.table("sessions").upsert(
        {"room_name": room_name, "vcc_id": vcc_id, "call_source": "sim"}, on_conflict="room_name"
    ).execute().data[0]
    session_id = row["id"]

    ex = Extractor(room_name=room_name, session_id=session_id, vcc_id=vcc_id,
                   region=REGION, model_id=MODEL, supabase=sb)
    room = rtc.Room()
    tasks: list[asyncio.Task] = []

    @room.on("track_subscribed")
    def _(track, pub, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            st = rtc.AudioStream(track, sample_rate=16_000, num_channels=1)
            ts = TranscribeSession(participant.identity, ex.on_turn, REGION)
            tasks.append(asyncio.create_task(ts.run(st)))

    t0 = time.monotonic()
    await room.connect(LIVEKIT_URL, listener_token(room_name))
    await asyncio.sleep(0.5)
    await publish_track(room_name, "family", AUDIO / f"{sample_id}.wav")
    await asyncio.sleep(3)
    await room.disconnect()
    for t in tasks:
        t.cancel()
    await ex.flush()

    return {"idx": idx, "session_id": session_id, "sample": sample_id,
            "wall_s": round(time.monotonic() - t0, 1), "fields": ex.snapshot()}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", type=int, default=5)
    args = ap.parse_args()
    sb = _supabase()

    samples = NAMES[: args.rooms]
    print(f"opening {args.rooms} rooms concurrently...")
    results = await asyncio.gather(*(one_room(sb, i, s) for i, s in enumerate(samples)))

    session_ids = [r["session_id"] for r in results]
    rows = sb.table("extracted_fields").select("*").in_("session_id", session_ids).execute().data
    lat = sorted(r["latency_ms"] for r in rows if r["latency_ms"] is not None)

    def pct(p):
        return lat[min(len(lat) - 1, int(len(lat) * p))] if lat else None

    # isolation: a session's values must not equal another sample's expected name
    import json
    expected = {json.loads(l)["id"]: json.loads(l)["expected"]
                for l in (ROOT / "eval" / "dataset" / "samples.jsonl").read_text().splitlines() if l.strip()}
    leaks = []
    for r in results:
        mine = expected[r["sample"]]
        for other_id, other_val in expected.items():
            if other_id != r["sample"] and other_val != mine:
                if other_val.lower() in " ".join(r["fields"].values()).lower():
                    leaks.append((r["session_id"], other_val))

    report = [
        f"# Load test — {args.rooms} concurrent rooms",
        "",
        f"- extraction rows: {len(rows)}",
        f"- latency_ms  p50 {pct(0.5)}  p95 {pct(0.95)}  max {lat[-1] if lat else None}",
        f"- wall time per room: {[r['wall_s'] for r in results]}",
        f"- data isolation: {'PASS' if not leaks else 'FAIL — ' + repr(leaks)}",
    ]
    (Path(__file__).parent / "report.md").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    assert not leaks, "data isolation broken"


if __name__ == "__main__":
    asyncio.run(main())
