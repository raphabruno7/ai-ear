# call-copilot

A real-time **voice copilot that listens** to a live call between two humans (a
care coordinator and a customer), extracts appointment/clinical fields as the
call runs, and writes them into a scheduling form via a **Chrome extension**.

Companion to [`voice-demo`](../voice-demo) (six *talking* voice bots). This one
is the opposite pattern: it never speaks. Built to demonstrate the stack a
production agent-assist copilot needs — AWS Bedrock/Transcribe/SES, golden-set
evals, Langfuse tracing, concurrency + data-isolation testing, per-call cost.

## Pipeline

```
LiveKit room (2 humans + 1 silent listener)
        │  audio track per speaker
        ▼
AWS Transcribe streaming ──► running transcript
        ▼
AWS Bedrock (Claude 3.5 Haiku) ──► incremental structured extraction
        ▼
Supabase (extracted_fields, call_costs)  +  WebSocket ──► Chrome extension ──► scheduling form
        ▼
AWS SES ──► pre-visit briefing email (daily cron)
```

## Layout

| Dir | What |
|---|---|
| `listener/` | Python — LiveKit listener agent, Transcribe, Bedrock extraction, cost tracking. Deploys to Railway. See `listener/AWS.md`. |
| `web/` | Next.js 16 — dashboard (`/session/[id]`, `/eval`, `/costs`), field + briefing webhooks. Deploys to Vercel. |
| `extension/` | Chrome MV3 — reads field updates over WS, fills the target form. |
| `eval/` | Golden-set + A/B harness: Claude Haiku (Bedrock) vs Gemini 2.5 Flash on phonetic name/email accuracy. |
| `loadtest/` | 10 concurrent rooms; measures extraction P95 under load + asserts cross-session data isolation. |
| `supabase/migrations/` | `sessions`, `extracted_fields`, `call_costs`, `eval_runs`. All RLS, service-role only. |

## Status

- [x] **Fase 0** — scaffold, migrations, `.env.example`, AWS setup guide
- [~] **Fase 1** — listener + AWS Transcribe streaming — code done, LiveKit wiring verified; Transcribe call blocked on new-account activation
- [~] **Fase 2** — incremental Bedrock extraction — code done (forced tool, merge, persist, cost); blocked on AWS activation
- [~] **Fase 3** — Langfuse tracing — `listener/trace.py` wired into extract + eval (no-ops without keys)
- [ ] **Fase 4** — SES briefing (cron)
- [~] **Fase 5** — golden-set A/B eval — metrics + 25-sample dataset + harness done; runs once AWS + `GEMINI_API_KEY`
- [x] **Fase 6** — Chrome extension + demo-scheduler + WS fan-out (demo via `listener/ws_push.py`)
- [~] **Fase 7** — load test — `loadtest/run.py`; N-room LiveKit concurrency verified, extraction/isolation pending AWS
- [x] **Fase 8** — cost tracking + debounce + `OPTIMIZATION.md`
- [x] **Dashboard** — `/` · `/session/[id]` (fields, time-to-fields, latency, cost) · `/eval` · `/costs` · `/api/health`
- [x] **Incident handling** — `HEALTH.md` runbook, `/api/health`, `listener/healthcheck.py`
- [x] **RLS policies** — `005_rls_policies.sql` (per-`vcc_id`)
- [x] **Fase 9** — `INTERVIEW.md` (requirement → evidence + real numbers)

Full plan: `~/.claude/plans/crie-um-plano-de-witty-pond.md`

## Setup

1. `cp .env.example .env` and fill it in (needs AWS, LiveKit, Supabase, Langfuse, Gemini).
2. AWS: follow `listener/AWS.md`.
3. Supabase: create a project, run the migrations in `supabase/migrations/` in order.
4. `listener/`: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
5. `web/`: `npm install && npm run dev`
