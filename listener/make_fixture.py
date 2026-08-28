"""Generate a two-speaker call fixture for the listener pipeline.

Uses macOS `say` + ffmpeg. Produces, in fixtures/:
  vcc.wav      — care-coordinator track (16 kHz mono s16le), silent during family turns
  family.wav   — pet-family track, silent during VCC turns
  mix.wav      — both summed (quick single-track testing)

sim_call.py publishes vcc.wav / family.wav as two LiveKit participants.

    python make_fixture.py
"""

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 16_000
GAP_S = 0.25
FIX = Path(__file__).parent / "fixtures"

# (speaker, macOS voice, line)
DIALOG = [
    ("vcc", "Samantha", "Thank you for calling the veterinary care team, my name is Sarah. How can I help you today?"),
    ("family", "Moira", "Hi, I'd like to book a visit for my dog. She hasn't been eating."),
    ("vcc", "Samantha", "I'm sorry to hear that. Can I get your full name please?"),
    ("family", "Moira", "Yes, it's Kathleen O'Brien."),
    ("vcc", "Samantha", "Thank you Kathleen. And the best phone number to reach you?"),
    ("family", "Moira", "Six one seven, five five five, zero one four two."),
    ("vcc", "Samantha", "And an email address for the confirmation?"),
    ("family", "Moira", "kathleen dot o brien at gmail dot com."),
    ("vcc", "Samantha", "Great. What's your dog's name and breed?"),
    ("family", "Moira", "Her name is Luna, she's a four year old golden retriever."),
    ("vcc", "Samantha", "And how long has she not been eating?"),
    ("family", "Moira", "About two days now, and she seems very tired and lethargic."),
    ("vcc", "Samantha", "Okay. I can get you in tomorrow afternoon at three o'clock. Does that work?"),
    ("family", "Moira", "Yes, three o'clock tomorrow is perfect. Thank you."),
]


def say_to_samples(voice: str, text: str, tmp: Path) -> np.ndarray:
    aiff, wav = tmp / "l.aiff", tmp / "l.wav"
    subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff),
         "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
        check=True,
    )
    with wave.open(str(wav)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(samples.astype(np.int16).tobytes())


def main() -> None:
    FIX.mkdir(exist_ok=True)
    tmp = FIX / "_tmp"
    tmp.mkdir(exist_ok=True)
    gap = np.zeros(int(GAP_S * SR), dtype=np.int16)

    clips = [(spk, say_to_samples(v, t, tmp)) for spk, v, t in DIALOG]
    total = sum(len(s) + len(gap) for _, s in clips)
    vcc = np.zeros(total, dtype=np.int16)
    fam = np.zeros(total, dtype=np.int16)

    cur = 0
    for spk, s in clips:
        (vcc if spk == "vcc" else fam)[cur:cur + len(s)] = s
        cur += len(s) + len(gap)

    write_wav(FIX / "vcc.wav", vcc)
    write_wav(FIX / "family.wav", fam)
    write_wav(FIX / "mix.wav", np.clip(vcc.astype(np.int32) + fam.astype(np.int32), -32768, 32767))

    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    print(f"wrote {FIX}/vcc.wav family.wav mix.wav  ({total / SR:.1f}s)")


if __name__ == "__main__":
    main()
