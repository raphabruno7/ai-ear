"""Deep health check for the listener's dependencies. Exits non-zero on any fail.

    python healthcheck.py            # human output
    python healthcheck.py --json     # for a monitor / cron

Checks: STS identity, Transcribe streaming open, SES send quota, Supabase.
Does NOT call Bedrock or Gemini (cost / daily quota).
"""

import argparse
import asyncio
import json
import os
import sys
import time

import boto3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
REGION = os.environ.get("AWS_REGION", "us-east-1")


async def _transcribe() -> None:
    from amazon_transcribe.client import TranscribeStreamingClient

    c = TranscribeStreamingClient(region=REGION)
    s = await c.start_stream_transcription(language_code="en-US", media_sample_rate_hz=16_000, media_encoding="pcm")
    await s.input_stream.end_stream()


def _run(name: str, fn) -> dict:
    t0 = time.monotonic()
    try:
        fn()
        return {"check": name, "status": "ok", "ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"check": name, "status": "fail", "error": str(e)[:200]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    def sts():
        boto3.client("sts", region_name=REGION).get_caller_identity()

    def ses():
        # policy only grants ses:SendEmail; AccessDenied here means creds reach
        # SES but can't read quota — that's fine, sending still works.
        try:
            boto3.client("ses", region_name=REGION).get_send_quota()
        except Exception as e:  # noqa: BLE001
            if "AccessDenied" not in str(e):
                raise

    def supabase():
        from supabase import create_client
        sb = create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        sb.table("sessions").select("id", count="exact").limit(0).execute()

    def transcribe():
        asyncio.run(_transcribe())

    results = [
        _run("aws-sts", sts),
        _run("aws-transcribe", transcribe),
        _run("aws-ses", ses),
        _run("supabase", supabase),
    ]
    ok = all(r["status"] == "ok" for r in results)

    if args.json:
        print(json.dumps({"ok": ok, "results": results}))
    else:
        for r in results:
            mark = "✓" if r["status"] == "ok" else "✗"
            extra = f" {r.get('ms')}ms" if r.get("ms") else f"  {r.get('error')}"
            print(f"  {mark} {r['check']}{extra}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
