# Scheduled jobs

## briefing.py — pre-visit briefing email (Fase 4)

Sends a briefing per newly-ended session. Run daily.

**Railway cron** (add to the listener service): `0 8 * * *` → `python briefing.py`
**Or GitHub Action**: schedule + `python listener/briefing.py` with the repo secrets.

`python briefing.py --dry-run` to preview. Needs AWS_* + SES_* + SUPABASE_* in env.
