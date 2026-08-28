"""Integration check: LiveKit publish -> subscribe -> AWS Transcribe -> final text.

Publishes the family fixture track into a real LiveKit room, runs the listener
wiring, and asserts the transcript picked up the key spoken content.

    python test_transcribe_wiring.py      # needs .env (LIVEKIT_*, AWS_*)

Not a pytest suite — one runnable assert. Hits real LiveKit + AWS Transcribe
(~15s of streaming audio, well inside the free tier).
"""

import asyncio
import os
import uuid

from dotenv import load_dotenv
from livekit import rtc

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from lktoken import listener_token  # noqa: E402
from sim_call import publish_track, FIX  # noqa: E402
from transcribe_stream import TranscribeSession  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")
LIVEKIT_URL = os.environ["LIVEKIT_URL"]


async def main() -> None:
    room_name = f"wiring-{uuid.uuid4().hex[:8]}"
    finals: list[tuple[str, str]] = []

    async def on_final(speaker: str, text: str) -> None:
        finals.append((speaker, text))
        print(f"  [{speaker}] {text}")

    room = rtc.Room()
    tasks: list[asyncio.Task] = []

    errors: list[BaseException] = []

    async def _run_ts(track, identity: str) -> None:
        try:
            stream = rtc.AudioStream(track, sample_rate=16_000, num_channels=1)
            await TranscribeSession(identity, on_final, REGION).run(stream)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    @room.on("track_subscribed")
    def _(track, pub, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            tasks.append(asyncio.create_task(_run_ts(track, participant.identity)))

    await room.connect(LIVEKIT_URL, listener_token(room_name))
    print(f"listener connected to {room_name}")

    await asyncio.sleep(1)
    await publish_track(room_name, "family", FIX / "family.wav")
    await asyncio.sleep(3)  # drain trailing transcripts

    await room.disconnect()
    for t in tasks:
        t.cancel()

    if errors:
        e = errors[0]
        if "SubscriptionRequired" in repr(e) or "403" in repr(e):
            raise SystemExit(
                "AWS Transcribe not activated yet (SubscriptionRequiredException). "
                "New-account activation gates it, same as Bedrock — retry in a few hours.\n"
                f"  {e!r}"
            )
        raise e

    blob = " ".join(t.lower() for _, t in finals)
    assert finals, "no transcripts received"
    assert "kathleen" in blob, f"missing 'kathleen' in: {blob!r}"
    assert "luna" in blob, f"missing 'luna' in: {blob!r}"
    assert {s for s, _ in finals} == {"family"}, "speaker label wrong"
    print(f"\nOK — {len(finals)} finals, speaker label + key content present")


if __name__ == "__main__":
    asyncio.run(main())
