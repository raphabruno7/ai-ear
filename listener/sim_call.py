"""Dev-only: publish a two-speaker WAV into a LiveKit room so the listener has
audio to transcribe without real telephony.

Fase 1: given a stereo (or two mono) WAV, join the room as two participants
("vcc", "family") and publish each channel as an audio track in real time.

Usage: python sim_call.py fixtures/kathleen.wav --room demo-1
"""

import argparse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--room", default="demo-1")
    ap.parse_args()
    raise SystemExit("Fase 1: implement WAV -> LiveKit track publishing")


if __name__ == "__main__":
    main()
