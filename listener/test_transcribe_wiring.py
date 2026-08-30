"""Integration check: LiveKit (2 participants) -> subscribe -> AWS Transcribe -> text.

Publishes the vcc + family fixture tracks from a SEPARATE process (isolated
WebRTC), runs the listener wiring in-process with one TranscribeSession per
participant, and asserts both speakers + key content came through — across the
per-track silence gaps that force Transcribe stream reopens.

    python test_transcribe_wiring.py      # needs .env (LIVEKIT_*, AWS_*)

Hits real LiveKit + AWS Transcribe (~50s of streaming audio).
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
        "--room", room_name, "--track", "both",
    )
    await proc.wait()
    await asyncio.sleep(5)

    await room.disconnect()
    for t in tasks:
        t.cancel()

    if errors:
        e = errors[0]
        if "SubscriptionRequired" in repr(e):
            raise SystemExit(f"AWS Transcribe not activated yet: {e!r}")
        raise e

    blob = " ".join(t.lower() for _, t in finals)
    speakers = {s for s, _ in finals}
    assert len(finals) >= 6, f"too few transcripts ({len(finals)}): {finals}"
    assert speakers == {"vcc", "family"}, f"speaker labels wrong: {speakers}"
    assert "kathleen" in blob, f"missing 'kathleen': {blob!r}"
    assert "luna" in blob, f"missing 'luna': {blob!r}"
    print(f"\nOK — {len(finals)} finals, both speakers, key content present")


if __name__ == "__main__":
    asyncio.run(main())
