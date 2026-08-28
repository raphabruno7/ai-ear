"""Dev-only: publish fixture WAV(s) into a LiveKit room so the listener has audio
to transcribe without real telephony.

    python sim_call.py --room demo-1 --track both      # vcc + family, two participants
    python sim_call.py --room demo-1 --track family     # just the family track

Each track is published by its own participant whose identity ("vcc" / "family")
becomes the speaker label in the listener.
"""

import argparse
import asyncio
import os
import wave
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from livekit import rtc

from lktoken import publisher_token

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
FIX = Path(__file__).parent / "fixtures"
FRAME_MS = 10


async def publish_track(room_name: str, identity: str, wav_path: Path) -> None:
    with wave.open(str(wav_path)) as w:
        assert w.getframerate() == 16_000 and w.getnchannels() == 1
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)

    room = rtc.Room()
    await room.connect(LIVEKIT_URL, publisher_token(room_name, identity))

    source = rtc.AudioSource(16_000, 1)
    track = rtc.LocalAudioTrack.create_audio_track(f"{identity}-audio", source)
    await room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )

    step = 16_000 * FRAME_MS // 1000
    for i in range(0, len(pcm), step):
        chunk = pcm[i:i + step]
        if len(chunk) < step:
            chunk = np.pad(chunk, (0, step - len(chunk)))
        frame = rtc.AudioFrame(chunk.tobytes(), 16_000, 1, step)
        await source.capture_frame(frame)
        await asyncio.sleep(FRAME_MS / 1000)

    await asyncio.sleep(1.0)  # let the tail flush
    await room.disconnect()
    print(f"{identity}: done ({len(pcm) / 16_000:.1f}s)")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--track", choices=["vcc", "family", "both"], default="both")
    args = ap.parse_args()

    jobs = []
    if args.track in ("vcc", "both"):
        jobs.append(publish_track(args.room, "vcc", FIX / "vcc.wav"))
    if args.track in ("family", "both"):
        jobs.append(publish_track(args.room, "family", FIX / "family.wav"))
    await asyncio.gather(*jobs)


if __name__ == "__main__":
    asyncio.run(main())
