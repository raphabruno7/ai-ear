# call-copilot — instructions for Claude Code

Portfolio project for Raphael Bruno. A real-time voice **copilot that listens** to
a live call between two humans (a veterinary care coordinator and a pet family),
transcribes it, extracts appointment/clinical fields as the call runs, and writes
them into a scheduling form via a **Chrome extension**. Second workstream: a
pre-visit briefing email via AWS SES.

Companion to `~/voice-demo` (six *talking* voice bots). **Keep the two repos
separate** — different narratives, different repos. Do not pull `voice-demo` code
in; clone patterns by hand if useful.

## Language

Raphael lives in Portugal. **Communicate in European Portuguese (pt-PT), never
pt-BR.** Code, comments, commit messages in English.

## Why this exists (read before suggesting commercialisation)

Built to demo for the **Neurons Lab "Voice Copilot Architect" role** — the client
is a US veterinary hospice network, PE-sponsored. This project deliberately mirrors
their product. As a portfolio piece shown to them: strong. As a product to sell:
conflict of interest + likely non-compete/confidentiality exposure. If Raphael
asks about selling it, flag the timing risk and suggest a *different vertical*.

## Architecture

```
listener/agent.py   LiveKit room (2 humans + 1 silent listener, no TTS)
  → transcribe_stream.py   one AWS Transcribe stream per speaker; reopens on
                           silence-close / connection blip
  → extract.py   Extractor — debounced (~12s), backend = bedrock | gemini
                 (EXTRACT_BACKEND env). Forced emit_fields tool (Bedrock) /
                 JSON (Gemini). merge() only overwrites on higher confidence.
  → Supabase (extracted_fields, call_costs)  +  ws_server.py fan-out
extension/   MV3 — connects to ws://<listener>:8765, fills [data-copilot-field]
web/         Next.js 16 dashboard, reads Supabase (service_role)
eval/        golden-set A/B harness (Transcribe + Bedrock + Gemini + metrics)
briefing.py  per-session pre-visit email via SES
```

Plain `rtc.Room`, **not** the livekit-agents worker framework — the listener joins
one named room (CLI `--room`), never publishes audio.

## Key patterns

- **`.env` at repo root.** `web/.env.local` is a symlink to it. `listener/` scripts
  `load_dotenv("../.env")`. Never commit `.env`.
- **`listener/.venv`** is Python 3.12 (livekit-agents needs <3.13). Run scripts as
  `.venv/bin/python …`.
- **Supabase writes** use the service_role key (bypasses RLS). The `005` migration
  adds per-`vcc_id` SELECT policies for a future scoped client (the extension).
- **Extraction errors are swallowed** (`logger.warning`, return False) so a
  throttle / 429 never kills a live call. The transcript keeps flowing.
- **Debounce**: `Extractor.min_extract_gap_s` (12s) + turn count. `finalize()` does
  one full-transcript pass at end of call. Don't revert to per-turn extraction —
  it burns the Gemini daily quota in one call.
- **Model IDs**: Bedrock `us.anthropic.claude-haiku-4-5-20251001-v1:0` (inference
  profile — the plain `anthropic.…` on-demand id is "Not supported" for 4.5).
  Gemini `gemini-3.6-flash` (`gemini-2.5-flash` is gone for new API users).
- **Fixtures** (`listener/fixtures/*.wav`) are committed; `eval/dataset/audio/*.wav`
  are gitignored — regenerate with `eval/make_dataset.py` (macOS `say` + ffmpeg).

## Verify / demo commands

```bash
cd listener
.venv/bin/python smoke_aws.py                 # Bedrock reachable? (currently: daily throttle)
.venv/bin/python healthcheck.py               # STS + Transcribe + SES + Supabase
.venv/bin/python test_transcribe_wiring.py    # LiveKit → Transcribe → text, e2e (~50s)
.venv/bin/python test_ws_server.py            # WS routing + isolation
.venv/bin/python extract.py                   # merge + parser self-checks
.venv/bin/python ws_push.py --session demo-1  # drive the extension with fake fields

cd eval && ../listener/.venv/bin/python run.py --models gemini-flash --sleep 12
cd loadtest && ../listener/.venv/bin/python run.py --rooms 6
cd web && npm run build && npm start          # dashboard on :3000
```

## Blocked on external quota (not code)

- **Bedrock**: `ThrottlingException: Too many tokens per day` since account
  creation (>48h). New-account daily cap. Needs an AWS Support case ("Account
  and billing", free) — TPM/RPM quota defaults are fine (5M), it's a separate
  daily limit. Until then run `EXTRACT_BACKEND=gemini`.
- **Gemini**: free tier = 20 requests/day/model. Enable billing on the AI Studio
  project (Flash is ~free) to lift it.
- **Migration `005`** not yet run in the Supabase SQL editor.
- **Langfuse** keys not in `.env` yet (`trace.py` no-ops without them).

When either model unblocks: run `eval/run.py` for the full A/B, run the listener
e2e with real fields into the dashboard, then finish `INTERVIEW.md` numbers.

## Deploy

- Push `main` → nothing auto-deploys yet (no remote configured). Local only.
- Intended: `listener/` → Railway (Dockerfile + railway.toml), `web/` → Vercel.

## Git

```
No remote yet. Branch: main (solo greenfield — commits go to main).
Commit style: feat(listener): … / fix(web): … / docs: …
```

## Reference

- Full session history & decisions: `HANDOFF.md`
- Requirement → evidence + numbers: `INTERVIEW.md`
- Incident runbook: `HEALTH.md`
- Cost/latency plan: `OPTIMIZATION.md`
- AWS setup: `listener/AWS.md`
- Original plan: `~/.claude/plans/crie-um-plano-de-witty-pond.md`
