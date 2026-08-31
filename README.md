# call-copilot

A real-time **voice copilot that listens** to a live call between two humans (a
care coordinator and a customer), extracts appointment/clinical fields as the
call runs, and writes them into a scheduling form via a **Chrome extension**.

Companion to `../voice-demo` (six *talking* voice bots). This one never speaks.
Built to demonstrate the stack a production agent-assist copilot needs — AWS
Bedrock/Transcribe/SES, golden-set evals, Langfuse tracing, concurrency +
data-isolation testing, per-call cost. See **`INTERVIEW.md`** for the
requirement → evidence map and the real numbers.

## Pipeline

```
LiveKit room (2 humans + 1 silent listener)
        │  one audio track per speaker
        ▼
AWS Transcribe streaming ──► running transcript, per-speaker
        ▼
extraction — AWS Bedrock Claude Haiku 4.5  ⇄  Gemini 3.6 Flash   (EXTRACT_BACKEND toggle)
        │  forced emit_fields tool / JSON, merge by confidence, debounced ~12s
        ▼
Supabase (extracted_fields, call_costs)  +  WebSocket ──► Chrome extension ──► scheduling form
        ▼
AWS SES ──► pre-visit briefing email (listener/briefing.py, per session)
```

## Layout

| Dir | What |
|---|---|
| `listener/` | Python — LiveKit listener, Transcribe, extraction (Bedrock/Gemini), cost, SES briefing, health check. Deploys to Railway. |
| `web/` | Next.js 16 — dashboard (`/`, `/session/[id]`, `/eval`, `/costs`), `/api/health`, `/demo-scheduler`, `/login`. Deploys to Vercel. |
| `extension/` | Chrome MV3 — subscribes to the listener's WS, fills `[data-copilot-field]` inputs. |
| `eval/` | Golden-set A/B: Claude Haiku 4.5 (Bedrock) vs Gemini 3.6 Flash on phonetic name/email accuracy. |
| `loadtest/` | N concurrent LiveKit rooms; extraction P95 under load + cross-session isolation assert. |
| `supabase/migrations/` | `sessions`, `extracted_fields`, `call_costs`, `eval_runs`, `005` RLS policies. |

## Status

All phases have code; **extraction with real fields is blocked on external quota**
(Bedrock daily token cap on the new AWS account; Gemini free tier = 20 req/day).
Everything else is verified. Details: `INTERVIEW.md` + `HANDOFF.md`.

| | |
|---|---|
| Fase 0 scaffold + migrations | ✅ |
| Fase 1 listener + Transcribe (reconnect-resilient) | ✅ verified e2e (49s / 2 speakers / 14 finals) |
| Fase 2 incremental extraction (Bedrock + Gemini backends) | ✅ code; real fields pending quota |
| Fase 3 Langfuse tracing | ~ wired, needs keys + one run |
| Fase 4 SES briefing | ✅ real email sent + received |
| Fase 5 golden-set eval | ✅ Gemini side: 25 samples, 60% phonetic on names |
| Fase 6 Chrome extension + WS fan-out | ✅ |
| Fase 7 load test | ✅ 6 concurrent rooms, isolation PASS |
| Fase 8 cost + debounce + `OPTIMIZATION.md` | ✅ |
| Dashboard, `/api/health`, `HEALTH.md`, RLS, `INTERVIEW.md` | ✅ |

## Setup

1. `cp .env.example .env` and fill it in.
2. AWS: `listener/AWS.md`.
3. Supabase: run `supabase/migrations/00{1..5}` in the SQL editor, in order.
4. `cd listener && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`
5. `cd web && npm install && ln -sf ../.env .env.local && npm run dev`

## Resume this project

Read **`HANDOFF.md`** — full context, what's verified, what's blocked, exact
commands to continue.
