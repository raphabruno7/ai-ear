"""Integration check: LiveKit publish -> subscribe -> AWS Transcribe -> final text.

Runs the listener wiring in-process and publishes the family fixture from a
SEPARATE process (isolated WebRTC peer connection — one process with two
rtc.Room instances is flaky). Asserts the transcript picked up key content.

    python test_transcribe_wiring.py      # needs .env (LIVEKIT_*, AWS_*)

Hits real LiveKit + AWS Transcribe (~20s of streaming audio).
"""

import asyncio
import os
import sys
import uuid

from dotenv import load_dotenv
from livekit import rtc

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from lktoken import listener_token  # noqa: E402
from transcribe_stream import TranscribeSession  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")
LIVEKIT_URL = os.environ["LIVEKIT_URL"]
HERE = os.path.dirname(__file__)
SECONDS = 30


async def main() -> None:
    room_name = f"wiring-{uuid.uuid4().hex[:8]}"
    finals: list[tuple[str, str]] = []
    errors: list[BaseException] = []

    async def on_final(speaker: str, text: str) -> None:
        finals.append((speaker, text))
        print(f"  [{speaker}] {text}")

    async def _run_ts(track, identity: str) -> None:
        try:
            stream = rtc.AudioStream(track, sample_rate=16_000, num_channels=1)
            await TranscribeSession(identity, on_final, REGION).run(stream)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    room = rtc.Room()
    tasks: list[asyncio.Task] = []

    @room.on("track_subscribed")
    def _(track, pub, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            tasks.append(asyncio.create_task(_run_ts(track, participant.identity)))

    await room.connect(LIVEKIT_URL, listener_token(room_name))
    print(f"listener connected to {room_name}")
    await asyncio.sleep(1)

    proc = await asyncio.create_subprocess_exec(
        sys.executable, os.path.join(HERE, "sim_call.py"),
        "--room", room_name, "--track", "family", "--seconds", str(SECONDS),
    )
    await proc.wait()
    await asyncio.sleep(4)  # drain trailing transcripts

    await room.disconnect()
    for t in tasks:
        t.cancel()

    if errors:
        e = errors[0]
        if "SubscriptionRequired" in repr(e):
            raise SystemExit(f"AWS Transcribe not activated yet: {e!r}")
        raise e

    blob = " ".join(t.lower() for _, t in finals)
    assert len(finals) >= 3, f"too few transcripts: {finals}"
    assert "kathleen" in blob, f"missing 'kathleen' in: {blob!r}"
    assert {s for s, _ in finals} == {"family"}, "speaker label wrong"
    print(f"\nOK — {len(finals)} finals, speaker label + key content present")


if __name__ == "__main__":
    asyncio.run(main())
