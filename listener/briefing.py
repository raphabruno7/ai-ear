"""Vet Visit Copilot — pre-visit briefing by email (AWS SES).

For each session that ended in the last N hours and hasn't been briefed, compose
a briefing from the extracted fields and send it to the vet. Marks
sessions.briefed_at so it only goes out once.

    python briefing.py                 # send for the last 24h
    python briefing.py --hours 48 --dry-run
    python briefing.py --session <id>  # one session, ignores briefed_at

Run on a schedule (Railway cron / GitHub Action). Needs .env: AWS_*, SES_*,
SUPABASE_*.
"""

from __future__ import annotations

import argparse
import os

import boto3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REGION = os.environ.get("AWS_REGION", "us-east-1")
FROM = os.environ["SES_FROM_EMAIL"]
TO = os.environ["SES_TO_EMAIL"]

FIELD_ORDER = ["owner_name", "owner_phone", "owner_email", "pet_name",
               "visit_type", "preferred_time", "clinical_notes"]
FIELD_LABEL = {
    "owner_name": "Owner", "owner_phone": "Phone", "owner_email": "Email",
    "pet_name": "Pet", "visit_type": "Visit type", "preferred_time": "Preferred time",
    "clinical_notes": "Clinical notes",
}


def _supabase():
    from supabase import create_client
    return create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def latest_fields(sb, session_id: str) -> dict[str, str]:
    rows = (sb.table("extracted_fields")
            .select("field_name, field_value, extracted_at")
            .eq("session_id", session_id)
            .order("extracted_at", desc=False)
            .execute().data or [])
    out: dict[str, str] = {}
    for r in rows:
        out[r["field_name"]] = r["field_value"]
    return out


def build_email(room_name: str, fields: dict[str, str]) -> tuple[str, str, str]:
    pet = fields.get("pet_name", "the patient")
    owner = fields.get("owner_name", "the owner")
    subject = f"Pre-visit briefing — {pet} ({owner})"

    rows_txt = "\n".join(f"  {FIELD_LABEL[k]}: {fields[k]}" for k in FIELD_ORDER if fields.get(k))
    text = (
        f"Pre-visit briefing for the upcoming appointment.\n\n"
        f"{rows_txt}\n\n"
        f"Extracted by the call copilot from session {room_name}. "
        f"Please verify against the scheduling system before the visit.\n"
    )
    rows_html = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#666'>{FIELD_LABEL[k]}</td>"
        f"<td style='padding:4px 0'>{fields[k]}</td></tr>"
        for k in FIELD_ORDER if fields.get(k)
    )
    html = (
        f"<div style='font:14px system-ui,sans-serif'>"
        f"<h2 style='font-size:16px'>Pre-visit briefing</h2>"
        f"<table>{rows_html}</table>"
        f"<p style='color:#888;font-size:12px'>Extracted by the call copilot from "
        f"session {room_name}. Verify against the scheduling system before the visit.</p></div>"
    )
    return subject, text, html


def send(subject: str, text: str, html: str) -> str:
    ses = boto3.client("ses", region_name=REGION)
    resp = ses.send_email(
        Source=FROM,
        Destination={"ToAddresses": [TO]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": text}, "Html": {"Data": html}},
        },
    )
    return resp["MessageId"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--session")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sb = _supabase()

    q = sb.table("sessions").select("id, room_name, ended_at, briefed_at")
    if args.session:
        q = q.eq("id", args.session)
    else:
        cutoff = f"now() - interval '{args.hours} hours'"
        q = q.not_.is_("ended_at", "null").is_("briefed_at", "null").gte("ended_at", cutoff)
    sessions = q.execute().data or []
    if not sessions:
        print("no sessions to brief")
        return

    for s in sessions:
        fields = latest_fields(sb, s["id"])
        if not fields:
            print(f"skip {s['room_name']} — no extracted fields")
            continue
        subject, text, html = build_email(s["room_name"], fields)
        if args.dry_run:
            print(f"--- {s['room_name']} ---\n{subject}\n{text}")
            continue
        mid = send(subject, text, html)
        sb.table("sessions").update({"briefed_at": "now()"}).eq("id", s["id"]).execute()
        print(f"sent {s['room_name']} -> {mid}")


def demo() -> None:
    subject, text, html = build_email("demo-1", {
        "owner_name": "Kathleen O'Brien", "pet_name": "Luna",
        "visit_type": "Not eating, lethargic", "clinical_notes": "2 days, golden retriever",
    })
    assert "Luna" in subject and "Kathleen O'Brien" in subject
    assert "Not eating, lethargic" in text and "Luna" in html
    assert "owner_phone" not in text  # absent fields omitted
    print("briefing demo ok")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        demo()
    else:
        main()
