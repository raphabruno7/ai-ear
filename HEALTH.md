# Health checks & incident runbook

## Checks

| What | Command | Covers |
|---|---|---|
| Liveness | `curl $WEB_URL/api/health` | Supabase reachable, env present |
| Deep | `python listener/healthcheck.py` | AWS STS, Transcribe open, SES, Supabase |
| Bedrock quota | `python listener/smoke_aws.py` | Bedrock InvokeModel actually works |
| End-to-end | `python listener/test_transcribe_wiring.py` | LiveKit → Transcribe → text |

Run `healthcheck.py --json` from a cron/monitor; non-zero exit = page.

## Incidents seen, and the fix

### `ThrottlingException: Too many tokens per day` (Bedrock)
New/just-upgraded AWS accounts get a near-zero daily Bedrock token cap.
**Check:** `smoke_aws.py`. **Fix:** AWS Support case ("Account and billing"),
or Service Quotas → Bedrock → the per-model *tokens per day* quota. **Mitigation
in place:** `EXTRACT_BACKEND=gemini` switches the listener to Gemini with no code
change; extraction errors are swallowed so the call keeps transcribing.

### `429 RESOURCE_EXHAUSTED` (Gemini)
Free tier = 20 requests/day/model. **Check:** the error names the quota id.
**Fix:** enable billing on the AI Studio project. **Mitigation:** debounce
(`Extractor.min_extract_gap_s`) — ~4 calls/conversation instead of ~13.

### LiveKit `ping timeout` / `pc_state failed`
Signal WS or peer connection dropped. The client auto-resumes; if it escalates
to a full reconnect, `track_subscribed` fires again and a new `TranscribeSession`
starts. **Mitigation:** the listener never holds call state in the connection —
transcript + fields live in the `Extractor`, persisted to Supabase per change.

### Transcribe stops returning finals mid-call
Transcribe closes a streaming session after a stretch of silence (per-speaker
tracks go quiet during the other party's turn). **Fixed:** `TranscribeSession`
reopens the stream on the next failed send. Before: ~2 finals then dead at ~15s.
After: full 49s fixture, 14 finals.

### Supabase `ConnectError: nodename nor servname` (DNS blip)
Transient. **Mitigation:** `eval/run.py` keeps results in memory and writes
`report.md` regardless; the `eval_runs` insert is one best-effort batch at the
end. The listener persists per-field, so a blip loses at most one field write.

### `SubscriptionRequiredException` (Transcribe/Bedrock)
Account still in the AWS activation window (minutes–24h) or on the Free Plan
sandbox. **Fix:** wait, or upgrade off the Free Plan (Billing → Upgrade plan).

## Safe rollback

- Listener: revert to the previous Railway image (or `git revert` + push).
- Backend swap: set `EXTRACT_BACKEND` back and redeploy — no schema change.
- Web: Vercel → promote the previous deployment.
- No migration is destructive; all are additive.
