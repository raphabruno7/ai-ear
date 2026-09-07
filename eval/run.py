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
import pricing  # noqa: E402
from metrics import score  # noqa: E402
from models import EXTRACTORS, LAST_USAGE, transcribe_file  # noqa: E402
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
    ap.add_argument("--sleep", type=float, default=0, help="seconds between samples (free-tier pacing)")
    ap.add_argument("--vocab", default=os.environ.get("TRANSCRIBE_VOCAB"),
                    help="Transcribe custom vocabulary name (default: $TRANSCRIBE_VOCAB)")
    ap.add_argument("--no-vocab", action="store_true", help="force vocabulary off (before-run)")
    args = ap.parse_args()
    vocab = None if args.no_vocab else (args.vocab or None)
    print(f"custom vocabulary: {vocab or 'none'}")

    rows = [json.loads(l) for l in SAMPLES.read_text().splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    run_id = time.strftime("%Y%m%d-%H%M%S")
    sb = _supabase()
    results: list[dict] = []
    transcripts: dict[str, str] = {}   # sample_id -> what AWS Transcribe heard

    for s in rows:
        wav = AUDIO / f"{s['id']}.wav"
        if not wav.exists():
            print(f"skip {s['id']} (no audio — run make_dataset.py)")
            continue
        try:
            transcript = await transcribe_file(str(wav), REGION, vocab=vocab)
        except Exception as e:  # noqa: BLE001 — network blip, skip this sample
            print(f"  {s['id']:>4} transcribe ERROR {e!r}"[:160])
            continue
        transcripts[s["id"]] = transcript
        for model in args.models:
            with span(f"eval:{model}", input={"transcript": transcript, "kind": s["kind"]}) as sp:
                try:
                    got = EXTRACTORS[model](transcript, s["kind"])
                except Exception as e:  # one bad call must not kill the run
                    got = ""
                    print(f"  {s['id']:>4} {model:<13} ERROR {e!r}"[:160])
                up = {"output": got, "metadata": {"expected": s["expected"], "sample": s["id"]}}
                if LAST_USAGE:
                    tin, tout = LAST_USAGE["input"], LAST_USAGE["output"]
                    usd = pricing.llm_cost(tin, tout, LAST_USAGE["backend"])
                    up.update(model=LAST_USAGE.get("model"),
                              usage_details={"input": tin, "output": tout},
                              cost_details={"total": usd})
                sp.update(**up)
            sc = score(s["expected"], got, s["kind"])
            rec = {"run_id": run_id, "model": model, "sample_id": s["id"], "kind": s["kind"],
                   "expected": s["expected"], "got": got, **sc}
            results.append(rec)
            print(f"  {s['id']:>4} {model:<13} {'OK ' if sc['phonetic_ok'] else 'MISS'} "
                  f"exp={s['expected']!r} got={got!r}")
        if args.sleep:
            await asyncio.sleep(args.sleep)

    trace_flush()
    _report(run_id, args.models, results, transcripts, vocab)  # always, from memory

    # Supabase is best-effort — a network blip must not lose the run.
    if sb and results:
        try:
            sb.table("eval_runs").insert(results).execute()
            print(f"wrote {len(results)} rows to eval_runs")
        except Exception as e:  # noqa: BLE001
            print(f"eval_runs write skipped: {e!r}")


def _report(run_id: str, models: list[str], results: list[dict],
            transcripts: dict[str, str] | None = None, vocab: str | None = None) -> None:
    lines = [f"# Eval run {run_id}", "", f"custom vocabulary: {vocab or 'none'}", ""]
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
    # Where every model missed the same sample: the LLM is faithful to the
    # transcript — the miss is upstream in the STT. This section makes that visible.
    if transcripts and len(models) > 1:
        by_sample: dict[str, dict[str, str]] = {}
        for r in results:
            by_sample.setdefault(r["sample_id"], {})[r["model"]] = r["got"]
        shared = [sid for sid, gm in by_sample.items()
                  if len(gm) == len(models)
                  and all(not x["phonetic_ok"] for x in results if x["sample_id"] == sid)]
        if shared:
            lines += ["", "## STT is the bottleneck", "",
                      "Samples **every** model got wrong — because AWS Transcribe "
                      "mis-heard the audio and both models faithfully returned what "
                      "they were given:", "",
                      "| sample | expected | Transcribe heard | " +
                      " | ".join(models) + " |",
                      "|---|---|---|" + "---|" * len(models)]
            def _cell(s: str) -> str:
                return (s or "").replace("`", "").replace("|", "\\|").strip()
            for sid in sorted(shared):
                exp = next(r["expected"] for r in results if r["sample_id"] == sid)
                heard = _cell(transcripts.get(sid, ""))
                got = " | ".join(f"`{_cell(by_sample[sid][m])}`" for m in models)
                lines.append(f'| {sid} | `{_cell(exp)}` | "{heard}" | {got} |')

    lines += ["", "## Misses", ""]
    for r in results:
        if not r["phonetic_ok"]:
            lines.append(f"- `{r['model']}` {r['sample_id']} — expected `{r['expected']}`, got `{r['got']}`")
    out = HERE / "report.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
