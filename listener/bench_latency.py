"""Time-to-first-value per field — debounce vs per-turn.

Replays the fixture dialogue turn-by-turn through the Extractor at a realistic
speaking cadence and records the wall-clock second at which each field first
gets a value (incremental pass) plus what the end-of-call finalize() adds.

Answers the job-spec line "remove ~1min lag on one field type": clinical_notes
is that field — it is spoken early but keeps growing, so with the 12s debounce
its first *complete* value only lands at finalize().

    .venv/bin/python bench_latency.py            # prod debounce (12s)
    .venv/bin/python bench_latency.py --gap 0    # per-turn baseline

Needs the extraction backend reachable (EXTRACT_BACKEND, GCP_PROJECT/…).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from extract import FIELD_NAMES, Extractor  # noqa: E402
from make_fixture import DIALOG  # noqa: E402

WORDS_PER_SEC = 2.6      # ~157 wpm, unhurried phone speech
PAUSE_S = 0.9            # gap between turns


async def run(gap_s: float, turns: int | None = None) -> dict[str, tuple[float, str]]:
    """Returns {field: (seconds_from_call_start, "incremental" | "finalize")}."""
    e = Extractor(
        room_name="bench",
        backend=os.environ.get("EXTRACT_BACKEND", "gemini"),
        gemini_model=os.environ.get("GEMINI_MODEL_ID", "gemini-3.6-flash"),
        model_id=os.environ.get("BEDROCK_MODEL_ID", ""),
        min_extract_gap_s=gap_s,
    )
    seen: dict[str, tuple[float, str]] = {}
    t0 = time.monotonic()

    for speaker, _voice, line in DIALOG[:turns]:
        await asyncio.sleep(len(line.split()) / WORDS_PER_SEC + PAUSE_S)
        await e.on_turn(speaker, line)
        for f, v in e.snapshot().items():
            if f not in seen and v:
                seen[f] = (round(time.monotonic() - t0, 1), "incremental")

    before = set(seen)
    await e.finalize()
    for f, v in e.snapshot().items():
        if f not in before and v:
            seen[f] = (round(time.monotonic() - t0, 1), "finalize")
    return seen


def _print(label: str, seen: dict[str, tuple[float, str]]) -> None:
    print(f"\n{label}")
    for f in FIELD_NAMES:
        if f in seen:
            secs, pass_ = seen[f]
            print(f"  {f:<15} {secs:6.1f}s  ({pass_})")
        else:
            print(f"  {f:<15}     —    (never)")


async def _demo() -> None:
    """Self-check: the first few turns yield owner_name. Short — makes real LLM calls."""
    seen = await run(0.0, turns=4)
    assert "owner_name" in seen and seen["owner_name"][1] == "incremental", seen
    _print("first 4 turns (gap=0)", seen)
    print("\nbench_latency demo ok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=float, default=12.0, help="min_extract_gap_s (debounce)")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        asyncio.run(_demo())
        return
    seen = asyncio.run(run(a.gap))
    _print(f"debounce gap={a.gap}s", seen)


if __name__ == "__main__":
    main()
