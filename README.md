# Ambient AI Call Copilot

A real-time **voice copilot that listens** to a live call between two humans (a
veterinary care coordinator and a pet family), transcribes it, extracts
appointment + clinical fields as the call runs, and writes them into a scheduling
form via a **Chrome extension**. Second workstream: a pre-visit briefing email.
It never speaks.

Companion to [`voice-demo`](https://github.com/raphabruno7/voice-demo) — six
*talking* voice bots. Framing: "bots that talk" vs "a copilot that listens".

A portfolio piece exploring **ambient AI** — the category of clinical software
that listens and writes the record instead of talking. Built hands-on to learn
where the hard problems actually are: streaming STT, real-time structured
extraction, golden-set accuracy evals, Langfuse tracing, concurrency +
data-isolation, per-call cost. **`EVIDENCE.md`** is the claim → evidence map with
the real numbers.

## Pipeline

```
LiveKit room (VCC + family + 1 silent listener)
        │  one audio track per speaker
        ▼
AWS Transcribe streaming ──► running transcript, per-speaker
        ▼
extraction — Gemini 3.6 Flash (Vertex AI)  ⇄  Claude Haiku 4.5 (Bedrock)
        │  EXTRACT_BACKEND toggle · forced emit_fields tool / JSON
        │  merge by confidence · debounced ~12s · finalize() at call end
        ▼
Supabase (extracted_fields, call_costs)  +  WebSocket ──► Chrome extension ──► scheduling form
        ▼
AWS SES ──► pre-visit briefing email (listener/briefing.py, per session)
```

Plain `rtc.Room`, **not** the livekit-agents worker framework — the listener
joins one named room and never publishes audio. The extension talks to a
WebSocket **on the listener process**, not through the web app.

## Layout

| Dir | What |
|---|---|
| `listener/` | Python 3.12 — LiveKit listener, Transcribe streaming, extraction (Vertex/Bedrock), per-call cost, SES briefing, health check, latency bench. Deploys to Railway. |
| `web/` | Next.js 16 — dashboard (`/`, `/session/[id]`, `/eval`, `/costs`), `/api/health`, `/demo-scheduler`, `/login`. Deploys to Vercel. |
| `extension/` | Chrome MV3 — subscribes to the listener's WS, fills `[data-copilot-field]` inputs (React-safe). |
| `eval/` | Golden-set A/B: Claude Haiku 4.5 vs Gemini 3.6 Flash on phonetic name/email accuracy (WER / Levenshtein / metaphone). |
| `loadtest/` | N concurrent LiveKit rooms; extraction p50/p95 under load + cross-session isolation assert. |
| `supabase/migrations/` | `sessions`, `extracted_fields`, `call_costs`, `eval_runs`, `005` RLS policies. |

## Status

**The pipeline is proven end to end** (2026-09-07): two live runs of LiveKit →
Transcribe → Gemini (Vertex AI) → Supabase, 7/7 fields extracted, real `call_costs`
row ($0.050 for a 113s call), clean teardown. Bedrock Haiku 4.5 is wired and
benchmarked but in "sleep mode" — `EXTRACT_BACKEND` toggles at runtime.

| Phase | State |
|---|---|
| 0 scaffold + migrations 001–005 | ✅ |
| 1 listener + Transcribe (reconnect-resilient) | ✅ verified e2e |
| 2 incremental extraction (Vertex + Bedrock backends) | ✅ **live e2e verified** — 7/7 fields into `extracted_fields` + real `call_costs` |
| 3 Langfuse tracing | ✅ v4 — listener `extract_turn` + eval traces, token + cost |
| 4 SES briefing | ✅ real email sent + received |
| 5 golden-set A/B | ✅ Haiku vs Gemini, 25 samples — see `EVIDENCE.md` |
| 6 Chrome extension + WS fan-out | ✅ WS+fill verified (`extension/VERIFY.md`); MV3 shell needs one manual load-unpacked |
| 7 load test | ✅ 6 concurrent rooms, isolation PASS |
| 8 cost + debounce + latency bench | ✅ `OPTIMIZATION.md`, `listener/bench_latency.py` |
| — dashboard, `/api/health`, `HEALTH.md`, RLS | ✅ |

## Setup

1. `cp .env.example .env` and fill it in.
2. AWS: `listener/AWS.md`. Google Cloud (extraction): enable Vertex AI API,
   `gcloud auth application-default login`, set `GCP_PROJECT` / `GCP_LOCATION=global`.
3. Supabase: run `supabase/migrations/00{1..5}` in the SQL editor, in order.
4. `cd listener && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`
5. `cd web && npm install && ln -sf ../.env .env.local && npm run dev`

## Verify / demo

```bash
cd listener
.venv/bin/python healthcheck.py              # STS + Transcribe + SES + Supabase
.venv/bin/python smoke_aws.py                # Bedrock reachable?
.venv/bin/python smoke_langfuse.py           # one trace to Langfuse
.venv/bin/python extract.py                  # merge + parser self-checks
.venv/bin/python bench_latency.py --demo     # time-to-first-value bench
.venv/bin/python ws_push.py --session demo-1 # drive the extension, no cloud

cd eval && ../listener/.venv/bin/python run.py         # full A/B → report.md + /eval
cd web && npm run build && npm start                   # dashboard on :3000
```

## Docs

| File | Purpose |
|---|---|
| `EVIDENCE.md` | Requirement → evidence map + the real numbers (the pitch). |
| `DEMO.md` | How to present it — 5-min walkthrough, talking points, fallbacks. |
| `GLOSSARY.md` | Every technical term used, explained (pt-PT). |
| `OPTIMIZATION.md` | Cost & latency plan — done vs next, with measurements. |
| `HEALTH.md` | Incident runbook — each failure mode → symptom → check → fix. |
| `CLAUDE.md` | Instructions for Claude Code working in this repo. |
| `listener/AWS.md` | AWS account setup, IAM policy, model access. |
| `extension/VERIFY.md` | How the extension was verified + the one-time manual pass. |

## Contributing

Solo project. Work goes on a branch → PR → merge to `main` → push. No remote CI yet.
