"""Golden-set A/B: Claude Haiku (Bedrock) vs Gemini 2.5 Flash on phonetic name /
email accuracy.

    python run.py                       # both models, all samples
    python run.py --models bedrock-haiku
    python run.py --limit 5

For each sample: transcribe the audio once (AWS Transcribe), then extract the
field with each model, score with metrics.py, write eval_runs rows + report.md.
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env")

import sys  # noqa: E402
sys.path.insert(0, str(HERE.parent / "listener"))
from metrics import score  # noqa: E402
from models import EXTRACTORS, transcribe_file  # noqa: E402
from trace import span, flush as trace_flush  # noqa: E402

SAMPLES = HERE / "dataset" / "samples.jsonl"
AUDIO = HERE / "dataset" / "audio"
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _supabase():
    try:
        from supabase import create_client
        url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
        return create_client(url, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    except Exception:
        return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=list(EXTRACTORS), choices=list(EXTRACTORS))
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    rows = [json.loads(l) for l in SAMPLES.read_text().splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    run_id = time.strftime("%Y%m%d-%H%M%S")
    sb = _supabase()
    results: list[dict] = []

    for s in rows:
        wav = AUDIO / f"{s['id']}.wav"
        if not wav.exists():
            print(f"skip {s['id']} (no audio — run make_dataset.py)")
            continue
        transcript = await transcribe_file(str(wav), REGION)
        for model in args.models:
            with span(f"eval:{model}", input={"transcript": transcript, "kind": s["kind"]}) as sp:
                got = EXTRACTORS[model](transcript, s["kind"])
                sp.update(output=got, metadata={"expected": s["expected"], "sample": s["id"]})
            sc = score(s["expected"], got, s["kind"])
            rec = {"run_id": run_id, "model": model, "sample_id": s["id"], "kind": s["kind"],
                   "expected": s["expected"], "got": got, **sc}
            results.append(rec)
            print(f"  {s['id']:>4} {model:<13} {'OK ' if sc['phonetic_ok'] else 'MISS'} "
                  f"exp={s['expected']!r} got={got!r}")
            if sb:
                sb.table("eval_runs").insert(rec).execute()

    trace_flush()
    _report(run_id, args.models, results)


def _report(run_id: str, models: list[str], results: list[dict]) -> None:
    lines = [f"# Eval run {run_id}", ""]
    lines.append("| model | kind | n | exact | phonetic | mean WER | mean lev |")
    lines.append("|---|---|--:|--:|--:|--:|--:|")
    for model in models:
        for kind in ("name", "email"):
            rs = [r for r in results if r["model"] == model and r["kind"] == kind]
            if not rs:
                continue
            n = len(rs)
            lines.append(
                f"| {model} | {kind} | {n} | "
                f"{sum(r['exact'] for r in rs)/n:.0%} | "
                f"{sum(r['phonetic_ok'] for r in rs)/n:.0%} | "
                f"{sum(r['wer'] for r in rs)/n:.3f} | "
                f"{sum(r['lev_norm'] for r in rs)/n:.3f} |"
            )
    lines += ["", "## Misses", ""]
    for r in results:
        if not r["phonetic_ok"]:
            lines.append(f"- `{r['model']}` {r['sample_id']} — expected `{r['expected']}`, got `{r['got']}`")
    out = HERE / "report.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
