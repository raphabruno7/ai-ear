# call-copilot — handoff

> **STATUS** — 2026-09-07
> · repo: `github.com/raphabruno7/ai-ear` (private) · branch `main` · 0 open PRs
> · pipeline: **e2e verified end to end** (LiveKit → Transcribe → LLM → Supabase)
> · self-checks: passing · dashboard: renders · Langfuse: live
> · **next:** STT custom vocabulary (needs an IAM change) — see START HERE
> · blockers: none (all remaining work is a credential or a chore)

Resume in a fresh Claude Code session opened **inside `~/call-copilot`**.
This file: `~/call-copilot/HANDOFF.md`.

---

## START HERE

**What it is:** a portfolio piece exploring **ambient AI** — a copilot that
*listens* to a live two-party call (veterinary care coordinator + pet family in an
end-of-life context), transcribes it per-speaker, extracts scheduling/clinical
fields in real time, fills a scheduling form via a Chrome extension, and sends a
pre-visit briefing email. It never speaks. Not tied to any employer or client.
Companion repo `~/voice-demo` = voice *bots that talk*; keep them separate.

**Repo:** `github.com/raphabruno7/ai-ear` (private). Branch per task → push →
`gh pr create` → user merges. One-line fixes may go straight to `main`.

**Current state — the pipeline is proven end to end.**

| Piece | State |
|---|---|
| Listener e2e (LiveKit → Transcribe → LLM → Supabase) | ✅ **verified 2026-09-07** — 2 live runs, 7/7 fields, real `call_costs` ($0.050 / 113s call), clean teardown |
| Extraction backend | ✅ Gemini 3.6 Flash on **Vertex AI** (default). Bedrock Haiku 4.5 wired, in "sleep mode". `EXTRACT_BACKEND` toggles at runtime |
| Golden-set A/B (25 hard names/emails) | ✅ Haiku vs Gemini. **Both miss the same samples** → `eval/report.md` "STT is the bottleneck" section. Phonetic ~60% both (stable); exact wobbles ±1–2/15 |
| Langfuse tracing | ✅ v4, live. `extract_turn` (listener) + `eval:*` observations, with token + cost |
| Cost model | ✅ `pricing.py` per-backend rates; real `call_costs` rows; `/costs` dashboard |
| Chrome extension | ✅ WS→contract→fill verified against the real `/demo-scheduler` page (`extension/VERIFY.md`). MV3 shell needs one manual `load unpacked` |
| SES briefing | ✅ real email sent + received; `briefing.py --dry-run` pulls the 7 fields |
| Concurrency + RLS | ✅ 6 rooms parallel, isolation assert PASS; migration 005 applied |
| Dashboard | ✅ `/`, `/session/[id]`, `/eval`, `/costs`, `/login`, `/api/health` |

**Nothing left is an engineering blocker.** Remaining, by priority:

| # | Item | Blocked on | Effort |
|---|---|---|---|
| 1 | **STT custom vocabulary** — the fix for the accuracy bottleneck. Create a vocab of hard owner/pet names + golden-set terms, wire `VocabularyName` into `transcribe_stream.py` + `eval/models.transcribe_file`, re-run the eval, show the before/after delta | add `transcribe:CreateVocabulary` / `GetVocabulary` / `ListVocabularies` / `DeleteVocabulary` to IAM policy `call-copilot-policy` (AWS console) | ~1 h after IAM |
| 2 | **Benchmark a 2nd STT** — same A/B method as the LLMs but for transcription: Deepgram Nova-3 vs AWS Transcribe on the golden set. Mirrors the LLM A/B story | a Deepgram key (free tier) | ~2 h |
| 3 | **3rd model in the A/B** — add `extract_openai` (gpt-4o-mini) to `eval/models.py` so "swap the model, same misses" holds across 3 vendors | `OPENAI_API_KEY` | 30 min |
| 4 | **Langfuse screenshot** — open an `extract_turn` trace, screenshot for `EVIDENCE.md` | nothing | 2 min |
| 5 | **Extension manual pass** — `chrome://extensions` → Load unpacked `extension/` → set `ws://localhost:8765` + a session id → confirm badge ● + fill | nothing | 10 min |
| 6 | **Deploy** — `listener/` → Railway (Dockerfile + `railway.toml` ready), `web/` → Vercel, add CI | Railway + Vercel accounts | ½ day |
| 7 | **Clean public repo** — fork the code without the strategy `.md`s if a linkable repo is wanted instead of screenshots | decision | 30 min |

---

## Run / verify

```bash
cd listener
.venv/bin/python healthcheck.py              # STS + Transcribe + SES + Supabase (4/4)
.venv/bin/python smoke_aws.py                # Bedrock reachable? (pong)
.venv/bin/python smoke_langfuse.py           # one trace to Langfuse
.venv/bin/python extract.py                  # merge + parser self-checks
.venv/bin/python bench_latency.py --demo     # time-to-first-value bench (short)
.venv/bin/python ws_push.py --session demo-1 # drive the extension, no cloud

# full listener e2e (needs a stable Wi-Fi — see gotchas):
.venv/bin/python agent.py --room demoX &     # wait for "transcribing track from vcc/family"
.venv/bin/python sim_call.py --room demoX --track both
#   → check /session/<id>, /costs, and extracted_fields in Supabase

cd ../eval && ../listener/.venv/bin/python run.py   # full A/B → report.md + eval_runs + /eval
cd ../web && npm run dev                            # dashboard on :3000 (or :3001)
```

`langfuse api observations list` (via the global `langfuse-cli`) reads the traces
— use `observations`, not the deprecated v3 `traces list`.

---

## Key gotchas (bites you if you don't know)

- **`trace.py` loads `../.env` itself** — it evaluates `_ENABLED` at import, and
  `agent.py` imports `extract → trace` *before* its own `load_dotenv`. Without the
  self-load, the listener silently no-ops all Langfuse spans. Fixed 2026-09-07.
- **LiveKit media e2e needs real Wi-Fi.** On an iPhone hotspot (gateway
  `172.20.10.1`, `en0`/`en14` marked `constrained`) CGNAT breaks WebRTC UDP —
  signalling connects, media never does. 8 attempts failed on hotspot before one
  finally worked; don't burn attempts, switch networks.
- **Two listener failure modes, both handled:** (a) `CancelledError` (a
  `BaseException`) from `TranscribeSession.close()` slipped past `except Exception`
  and skipped `finalize()`/`flush()` — now caught explicitly + best-effort
  teardown; (b) LiveKit swallows `participant_disconnected` on a signalling
  resume → hang — now ended by an idle watchdog (`CALL_IDLE_END_S`, default 30s).
- **Vertex AI:** `_genai_client()` uses Vertex when `GCP_PROJECT` is set (ADC:
  `gcloud auth application-default login`). `GCP_LOCATION=global` is **required**
  for `gemini-3.6-flash` — `us-central1` only serves 2.5-flash.
- **Gemini 3.x narrates instead of answering** on the hardest spelled-out emails.
  Eval uses `response_mime_type=json` + a `{"value": …}` envelope; `_clean()`
  drops any output > 60 chars as a clean miss. `max_output_tokens` must be ~2000
  (thinking tokens count against it; a low cap truncates to fragments).
- **Bedrock Haiku 4.5 needs the inference profile** — `us.anthropic.claude-haiku-4-5-20251001-v1:0`,
  not the plain on-demand id ("Not supported"). Was throttled (`Too many tokens
  per day`) for days on a new account; cleared ~2026-09-02.
- **Plain `rtc.Room`, not the livekit-agents worker framework** — one named room,
  never publishes audio. Extension ↔ listener via a WebSocket **on the listener
  process** (`ws_server.py`), not through Next.
- **Transcribe closes streams on silence** — a speaker's track goes quiet during
  the other's turn. `TranscribeSession` reopens on the next failed send.
- **`web/.env.local` is a symlink → `../.env`.** If missing: `cd web && ln -sf ../.env .env.local`.
- **`ADMIN_SECRET` blank** → `proxy.ts` fails open, dashboard reachable locally.
- **Python 3.12 venv** at `listener/.venv` — livekit needs <3.13; system is 3.14.
  Run scripts as `.venv/bin/python …`.
- **awscrt "CANCELLED future" traceback on shutdown** — cosmetic, the session
  still ends cleanly (`ended —` line + `call_costs` written).
- **`report.md` is regenerated each run** — a `--limit` run shortens it; always
  re-run the full A/B before committing.

---

## Infrastructure — `.env` at repo root (gitignored)

| Service | Non-secret identifiers | `.env` keys |
|---|---|---|
| **AWS** | account `441541653312`, `us-east-1`. IAM user `call-copilot-listener`, policy `call-copilot-policy` (bedrock InvokeModel*, transcribe StartStream*, ses:SendEmail). Pay-as-you-go. | `AWS_ACCESS_KEY_ID/SECRET`, `AWS_REGION` |
| **Bedrock** | Haiku 4.5 access granted. | `BEDROCK_MODEL_ID` |
| **Google Cloud** | project `project-f785b239-de2b-43c7-b98`, Vertex AI API on, ADC. | `GCP_PROJECT`, `GCP_LOCATION=global` |
| **Gemini** | model `gemini-3.6-flash`. AI Studio key is a fallback when `GCP_PROJECT` unset. | `GEMINI_API_KEY`, `GEMINI_MODEL_ID` |
| **SES** | identity `raphaelbruno.dev@gmail.com` verified; sandbox (verified recipients only). | `SES_FROM_EMAIL`, `SES_TO_EMAIL` |
| **LiveKit Cloud** | project `copilot-aws-1s7p7hzj`, EU. | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| **Supabase** | ref `qtynypkfbwdstnnfiuuw`. Migrations 001–005 applied. | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` |
| **Langfuse** | EU cloud, project `cmtk3gub6013qad0cxmnpkjmf`. | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |

Also: `EXTRACT_BACKEND=gemini`, `WEB_BASE_URL=http://localhost:3000`, `ADMIN_SECRET`
(blank), `CALL_IDLE_END_S` (unset → 30).

---

## File map

### `listener/` (Python 3.12, `.venv`)
| File | Purpose |
|---|---|
| `agent.py` | Entry. `--room X`. Session row → `FieldsWS` → one `TranscribeSession`/participant → `Extractor` → health server. Ends on all-participants-left **or** idle watchdog → `finalize()` → `flush()`. |
| `transcribe_stream.py` | `TranscribeSession` — LiveKit `AudioStream` 16kHz → AWS Transcribe → `on_final`. Reopens on failed send. |
| `extract.py` | `Extractor` — debounced (~12s). `_emit_bedrock` (forced tool) / `_emit_gemini` (JSON). `merge()` confidence gate → `_persist()` → `extracted_fields`. `flush()` → `call_costs`. Spans → Langfuse. `_SYSTEM`, `_TOOL` here. |
| `pricing.py` | `LLM_RATES` per backend (bedrock 0.80/4.00, gemini 0.75/3.75 per 1M); `stt_cost`, `llm_cost(in, out, backend)`. Self-checked. |
| `trace.py` | Langfuse v4 wrapper. `span()` → a `generation` observation (so token/cost attach). Loads `../.env`. No-ops without keys. |
| `bench_latency.py` | Replays the fixture call turn-by-turn, records time-to-first-value per field. `--demo` for a short self-check. |
| `ws_server.py` / `ws_push.py` | `FieldsWS` fan-out by `session_id` / dev tool to drive the extension with fake fields. |
| `briefing.py` | Per-session briefing email via SES. `--dry-run`, `--session`, `--hours`, `--demo`. |
| `sim_call.py` / `make_fixture.py` | Publish `fixtures/{vcc,family}.wav` as 2 participants / regenerate the fixtures. |
| `smoke_aws.py` / `smoke_langfuse.py` / `healthcheck.py` | STS+Bedrock / one Langfuse trace / STS+Transcribe+SES+Supabase. |
| `test_transcribe_wiring.py` / `test_ws_server.py` | e2e transcribe (passes) / WS routing + isolation (passes). |
| `AWS.md`, `SCHEDULE.md`, `Dockerfile`, `railway.toml` | setup / cron / Railway deploy. |

### `web/` (Next.js 16, App Router, Tailwind v4)
`app/page.tsx` (sessions), `app/session/[id]` (fields + agent-assist metrics +
latency p50/p95 + cost), `app/eval` (latest A/B + misses), `app/costs` (avg USD,
STT vs LLM, 1k/mo), `app/demo-scheduler` (`[data-copilot-field]` form),
`app/login`, `app/api/health`. `proxy.ts` (cookie gate, fail-open).
`lib/supabase.ts` (`getSupabaseAdmin()` service_role singleton). `.env.local` →
symlink to `../.env`. `web/AGENTS.md` / `web/CLAUDE.md` are auto-generated by
`next dev` — leave them.

### `extension/` (Chrome MV3)
`manifest.json`, `background.js` (WS client, subscribes one session), `content.js`
(fills `[data-copilot-field]` — native setter + bubbling `input`/`change` for
React), `popup.html/js` (WS URL + session id). `VERIFY.md` = how it was verified.

### `eval/`
`dataset/samples.jsonl` (25 hard: 15 names, 10 emails), `make_dataset.py` (`say`
+ ffmpeg → gitignored wavs), `models.py` (`transcribe_file`, `extract_bedrock`,
`extract_gemini`, `_clean`, `LAST_USAGE`), `metrics.py` (exact/lev/wer/phonetic,
self-checked), `run.py` (transcribe once → extract per model → score →
`eval_runs` + `report.md`; the "STT is the bottleneck" section).

### `loadtest/run.py`
N concurrent LiveKit rooms; extraction p50/p95 + cross-session isolation assert.

### `supabase/migrations/`
`001` sessions · `002` extracted_fields (history kept, latest per (session,field)
wins) · `003` call_costs · `004` eval_runs · `005` per-`vcc_id` SELECT RLS.

---

## Docs

`EVIDENCE.md` (claim → evidence + real numbers — the pitch) · `OPTIMIZATION.md`
(cost/latency + the STT vendor comparison & ranked plan) · `DEMO.md` (5–8 min
walkthrough + talking points) · `GLOSSARY.md` (every term, pt-PT) · `HEALTH.md`
(incident runbook) · `PROFILE.md` (CV / portfolio positioning) · `CLAUDE.md`
(instructions for Claude Code) · `listener/AWS.md` · `extension/VERIFY.md`.

## Changelog (terse — `git log` for detail)

- **2026-09-07** — first successful listener e2e (7/7 fields, real cost); fixed
  `trace.py` import-order bug (listener never traced); prompt-audit F1–F3 +
  `_clean` ramble guard.
- **2026-09-03** — dropped client/job framing → `INTERVIEW.md` renamed
  `EVIDENCE.md`; `report.md` "STT is the bottleneck" section; Gemini eval → JSON
  mode; `OPTIMIZATION.md` STT vendor comparison; `langfuse-cli` installed.
- **2026-09-02** — Langfuse token+cost per observation; extension WS+fill
  verified; migration 005 run; PENDING list consolidated.
- **2026-09-01** — extraction moved to Vertex AI; per-backend pricing; full A/B
  Haiku vs Gemini; `bench_latency.py`; Langfuse v4 SDK fix; GitHub repo +
  PR workflow; `GLOSSARY.md`; `DEMO.md`.
- **2026-08-31** — teardown-persist bug + idle watchdog fixes; diagnosed
  hotspot/CGNAT as the e2e blocker.
- **2026-08-28→31** — scaffold, 9 phases, all infra created live.
