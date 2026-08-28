"""Generate golden-set audio from eval/dataset/samples.jsonl (macOS `say` + ffmpeg).

    python make_dataset.py            # writes dataset/audio/<id>.wav (16 kHz mono)
    python make_dataset.py --only n01

Drop real recordings into dataset/audio/ with the same <id>.wav name to override
a synthetic sample — run.py doesn't care how the audio was made.
"""

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
SAMPLES = HERE / "dataset" / "samples.jsonl"
AUDIO = HERE / "dataset" / "audio"


def gen(sample: dict) -> None:
    out = AUDIO / f"{sample['id']}.wav"
    aiff = AUDIO / f"_{sample['id']}.aiff"
    subprocess.run(["say", "-v", sample["voice"], "-o", str(aiff), sample["text"]],
                   check=True, timeout=60)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff),
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(out)],
                   check=True, timeout=60)
    aiff.unlink()
    print(f"  {sample['id']:>4}  {sample['kind']:<5}  {sample['expected']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="single sample id")
    args = ap.parse_args()
    AUDIO.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in SAMPLES.read_text().splitlines() if l.strip()]
    if args.only:
        rows = [r for r in rows if r["id"] == args.only]
    for r in rows:
        gen(r)
    print(f"done — {len(rows)} samples in {AUDIO}")


if __name__ == "__main__":
    main()
