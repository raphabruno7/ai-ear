# call-copilot — session handoff

Complete context to continue this project in a fresh Claude Code session opened
**inside `~/call-copilot`**. Everything below reflects state as of 2026-08-31.

---

## 0. Latest session (2026-08-31, afternoon)

- **Gemini unblocked** — daily free-tier quota reset; `smoke` returns `pong`.
  Bedrock still `ThrottlingException: Too many tokens per day` (support case
  still needed).
- **Bug found + fixed + committed** (`9e76a7a`): `TranscribeSession.close()`'s
  shielded wait raises `CancelledError` (a `BaseException`), which slipped past
  the `except Exception` guards in `agent.py` teardown → `finalize()` / `flush()`
  were **never reached**, so `extracted_fields` / `call_costs` never landed even
  on a clean full transcript. Now: `CancelledError` caught explicitly in
  `transcribe_stream.py`; each teardown step (`finalize`/`flush`/`ws.stop`/
  `sessions.update`) wrapped best-effort in `agent.py`. Verified — run
  `demo-real-2` completed teardown cleanly and wrote a `call_costs` row.
- **Real extraction numbers still NOT captured.** 5 e2e attempts this session:
  2 got a full transcript (one pre-fix crash, one lost network mid-call), 3
  failed because the **listener's LiveKit subscriber PeerConnection would not
  complete ICE** (`signal_event taking too much time`, no `transcribing track`
  line ever) — a degraded media path from this machine that afternoon, not a
  code issue. `extracted_fields` table is still empty.
  **Next:** retry the section-8 e2e on a stable network; then `/session/<id>` +
  fill `INTERVIEW.md`.

---

## 1. What this is and why

A real-time voice **copilot that listens** to a live phone call between a
veterinary care coordinator (VCC) and a pet family. It never speaks. It:

1. joins the LiveKit room as a silent participant,
2. streams each speaker's audio to AWS Transcribe,
3. extracts appointment + clinical fields from the running transcript with an
   LLM (AWS Bedrock Claude Haiku 4.5, or Gemini 3.6 Flash — runtime toggle),
4. pushes each field to a Chrome extension that fills the scheduling form,
5. sends the vet a pre-visit briefing email via AWS SES after the call.

**Built as a portfolio piece for the Neurons Lab "Voice Copilot Architect"
role.** The client is a US veterinary hospice network, PE-sponsored. The project
deliberately mirrors their product so the demo says "I understand your problem".

Companion repo: `~/voice-demo` — six *talking* voice bots (Hume, LiveKit/Gemini
Live, ElevenLabs, Vapi, Retell, Twilio). Framing: "bots that talk" (voice-demo)
vs "a copilot that listens" (call-copilot). **Keep them separate.**

### Commercialisation note
Selling this as a product while pursuing / during the Neurons Lab engagement is a
conflict of interest + likely non-compete/confidentiality exposure. Safe path if
Raphael wants a product: a *different vertical* (real-estate showings, recruiting
screens, insurance FNOL intake), own research, no client data or roadmap.

---

## 2. How it was built

This session started in the `~/voice-demo` terminal. Claude planned the work
(9 phases, plan file at `~/.claude/plans/crie-um-plano-de-witty-pond.md`), then
scaffolded `~/call-copilot` as a **new git repo** (no remote) and built it out
across ~21 commits. All infra accounts were created live during the session.

Original plan decisions (all still hold):
- **New repo**, cloning patterns from voice-demo by hand (not a dependency).
- **AWS Transcribe** for STT (maximises the AWS story the role wants).
- **Prova de portfolio** depth — one small real artifact per gap + numbers.
- **Golden-set** = ~25 TTS-synthesised hard names/emails + a few real.
- A/B second model was "Gemini 2.5 Flash" → now **Gemini 3.6 Flash** (2.5 retired
  for new API users).

Architecture change from the plan: the listener uses **plain `rtc.Room`**, not the
livekit-agents worker framework (simpler for a single-room silent listener). The
extension connects to a **WebSocket on the listener process** (`ws_server.py`),
not through the Next app.

---

## 3. The 9 phases — status

| Fase | What | Status |
|---|---|---|
| 0 | scaffold, 4 migrations, `.env.example`, `AWS.md` | ✅ done |
| 1 | listener + AWS Transcribe streaming | ✅ **verified e2e** — 49s two-speaker fixture → 14 final transcripts, both speaker labels, "Kathleen O'Brien" + "Luna" + phone + clinical notes |
| 2 | incremental extraction + per-call cost | ✅ code + teardown-persist bug fixed (`9e76a7a`); Gemini backend unblocked; **real fields still not captured — e2e blocked on flaky LiveKit media path, see §0** |
| 3 | Langfuse tracing | ~ `listener/trace.py` wired into extract + eval; no-ops without keys; needs keys + one run + screenshot |
| 4 | SES pre-visit briefing | ✅ **verified** — real email sent and received (`briefing.py`) |
| 5 | golden-set A/B eval | ✅ Gemini side: 25 samples run, `report.md` + `/eval` dashboard + `eval_runs` rows. Bedrock side blocked. |
| 6 | Chrome extension + demo-scheduler | ✅ MV3 + WS fan-out; demo via `ws_push.py` |
| 7 | load test + isolation | ✅ 6 concurrent LiveKit rooms, no failures, isolation assert PASS; extraction rows 0 (Gemini quota) |
| 8 | cost tracking + optimisation | ✅ `call_costs`, `/costs`, debounce (~70% fewer LLM calls), `OPTIMIZATION.md` |
| 9 | interview writeup | ✅ `INTERVIEW.md` (requirement → evidence + real numbers) |
| — | incident handling | ✅ `HEALTH.md`, `web/api/health`, `listener/healthcheck.py` (4/4 ok) |
| — | RLS policies | ✅ `005_rls_policies.sql` written — **not yet run in Supabase SQL editor** |
| — | agent-assist metrics | ✅ `/session/[id]` shows fields-on-screen, time-to-first-field, time-to-all-fields |

---

## 4. File map

### `listener/` (Python 3.12, `.venv` present)
| File | Purpose |
|---|---|
| `agent.py` | Entry. `--room X [--vcc] [--language]`. Creates Supabase session row, starts `FieldsWS`, one `TranscribeSession` per participant, `Extractor`, health HTTP server. Ends on participant-disconnect → `finalize()` → `flush()` (call_costs). |
| `transcribe_stream.py` | `TranscribeSession` — LiveKit `AudioStream` (16kHz mono) → AWS Transcribe streaming → `on_final(speaker, text)`. **Reopens the Transcribe stream** when a send fails (silence-close or blip). |
| `extract.py` | `Extractor` — debounced. `_emit_bedrock` (converse + forced `emit_fields` tool) / `_emit_gemini` (JSON). `merge()` confidence gate. `_persist()` → `extracted_fields`. `flush()` → `call_costs` (uses `pricing.py`). `EXTRACT_BACKEND` picks backend. |
| `ws_server.py` | `FieldsWS` — WebSocket fan-out, subscribe by `session_id`, broadcast `{type:"fields",…}`. |
| `ws_push.py` | Dev tool — standalone `FieldsWS` + fake Kathleen/Luna extraction to demo the extension without cloud. |
| `lktoken.py` | LiveKit tokens — `listener_token` (subscribe-only), `publisher_token`. |
| `sim_call.py` | Dev — publishes `fixtures/vcc.wav` + `family.wav` as two participants (`--track both`, `--seconds N`). |
| `make_fixture.py` | Generates `fixtures/{vcc,family,mix}.wav` from a scripted 2-speaker dialogue via macOS `say` + ffmpeg. |
| `pricing.py` | USD constants (Transcribe $0.024/min, Bedrock Haiku $0.80/$4.00 per 1M). `stt_cost`, `llm_cost`. Self-checked. |
| `trace.py` | Thin Langfuse wrapper — `span()` context mgr, no-ops without `LANGFUSE_PUBLIC_KEY`. |
| `briefing.py` | Per-session pre-visit briefing email via SES. `--dry-run`, `--session <id>`, `--hours N`, `--demo`. |
| `smoke_aws.py` | STS identity + one Bedrock `converse`. Currently: STS ✅, Bedrock ✗ (daily throttle). |
| `healthcheck.py` | STS + Transcribe open + SES + Supabase. `--json`. Non-zero exit on fail. Currently 4/4 ok. |
| `test_transcribe_wiring.py` | e2e — publishes both fixture tracks (subprocess), asserts ≥6 finals, both speakers, "kathleen" + "luna". **Passes.** |
| `test_ws_server.py` | `FieldsWS` routing + cross-session isolation. Passes. |
| `AWS.md` | Account setup, IAM policy JSON, Bedrock model access, SES verify, quota notes. |
| `SCHEDULE.md` | How to cron `briefing.py` (Railway cron / GitHub Action). |
| `Dockerfile`, `railway.toml` | Railway deploy (python:3.12-slim). |
| `requirements.txt` | `livekit`, `livekit-api`, `amazon-transcribe`, `boto3`, `langfuse`, `websockets`, `supabase`, `google-genai` (implied), `pydantic`, `numpy`, `python-dotenv`. |

### `web/` (Next.js 16, App Router, Tailwind v4)
| File | Purpose |
|---|---|
| `app/page.tsx` | Recent sessions list. |
| `app/session/[id]/page.tsx` | Session detail — extracted fields (latest per name), agent-assist metrics, latency p50/p95, cost. Full try/catch, `.throwOnError()`. |
| `app/eval/page.tsx` | Latest A/B run — exact/phonetic/WER/Lev per model×kind + misses. |
| `app/costs/page.tsx` | Avg USD/call, STT vs LLM split, 1k/mo projection, per-session table. |
| `app/demo-scheduler/page.tsx` | Stand-in scheduling form with `[data-copilot-field]` inputs. |
| `app/login/page.tsx` | Server-action login — sets `admin_token` cookie == `ADMIN_SECRET`. |
| `app/api/health/route.ts` | Liveness — Supabase + env presence. `{ok, checks}`. |
| `proxy.ts` | (was `middleware.ts`, renamed for Next 16) — cookie gate; fail-open when `ADMIN_SECRET` unset. |
| `lib/supabase.ts` | `getSupabaseAdmin()` lazy singleton (service_role). |
| `lib/stats.ts` | `percentile`, `fmtUSD`. |
| `components/stat.tsx` | Shared stat tile. |
| `.env.local` | **symlink → `../.env`** (gitignored). |

### `extension/` (Chrome MV3)
`manifest.json`, `background.js` (WS client, subscribes one session, relays to
content script), `content.js` (fills `[data-copilot-field]` with native setter +
bubbling input event for React), `popup.html/js` (config: WS URL + session id).
Default WS URL `ws://localhost:8765`.

### `eval/`
| File | Purpose |
|---|---|
| `dataset/samples.jsonl` | 25 hard samples (15 names, 10 emails) — Siobhan, Cholmondeley, Featherstonehaugh, spelled-out emails. |
| `make_dataset.py` | `say` + ffmpeg → `dataset/audio/<id>.wav` (gitignored). Real recordings override by id. |
| `models.py` | `transcribe_file` (Transcribe streaming from wav), `extract_bedrock` (converse), `extract_gemini` (google-genai, max_output_tokens=2000, retry 429/503). Shared `_PROMPT`, `_clean`. |
| `metrics.py` | `normalize`, `exact_match`, `levenshtein`, `lev_norm`, `wer`, `phonetic_ok` (metaphone / email key), `score`. Self-checked. |
| `run.py` | Per sample: transcribe once → extract per model → `score` → `eval_runs` + `report.md`. `--models`, `--limit`, `--sleep`. Resilient to per-sample failures + network blips. |
| `requirements.txt` | `jellyfish`, `google-genai`. |

### `loadtest/run.py`
Opens N LiveKit rooms concurrently (each a distinct name from the eval set),
runs listen→transcribe→extract→persist, reports extraction latency p50/p95,
asserts no cross-session value leak. `--rooms N`.

### `supabase/migrations/`
- `001_sessions.sql` — `sessions` (room_name unique, vcc_id, call_source, started/ended/briefed_at). RLS on.
- `002_extracted_fields.sql` — `extracted_fields` (session_id FK, vcc_id, field_name, field_value, confidence, model, latency_ms, extracted_at). History kept — latest row per (session, field) wins.
- `003_call_costs.sql` — `call_costs` (session_id PK, stt_seconds, llm tokens, usd_*).
- `004_eval_runs.sql` — `eval_runs` (run_id, model, sample_id, kind, expected, got, exact, wer, lev_norm, phonetic_ok).
- `005_rls_policies.sql` — per-`vcc_id` SELECT on sessions + extracted_fields; deny-all on costs/eval. **NOT YET RUN.**

---

## 5. Infrastructure (all live, created this session)

Secrets are in `~/call-copilot/.env` (gitignored). Non-secret identifiers:

| Service | What | Where |
|---|---|---|
| **AWS** | account `441541653312`, region `us-east-1`. IAM user `call-copilot-listener` (policy `call-copilot-policy`: bedrock InvokeModel*, aws-marketplace View/Subscribe, transcribe StartStream*, ses:SendEmail). **Upgraded off the Free Plan** to pay-as-you-go. | `.env`: `AWS_ACCESS_KEY_ID/SECRET`, `AWS_REGION` |
| **Bedrock** | model access granted (Anthropic Claude Haiku 4.5 + 3 Haiku). Model id `us.anthropic.claude-haiku-4-5-20251001-v1:0` (US inference profile). | `.env`: `BEDROCK_MODEL_ID` |
| **SES** | identity `raphaelbruno.dev@gmail.com` **verified**. Sandbox (send only to verified). | `.env`: `SES_FROM_EMAIL`, `SES_TO_EMAIL` (both the gmail) |
| **LiveKit Cloud** | project `copilot-aws-1s7p7hzj`, EU region. Agent observability disabled. | `.env`: `LIVEKIT_URL` (`wss://copilot-aws-1s7p7hzj.livekit.cloud`), `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| **Supabase** | project ref `qtynypkfbwdstnnfiuuw`. URL `https://qtynypkfbwdstnnfiuuw.supabase.co`. Migrations 001–004 applied; 005 not. | `.env`: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` |
| **Gemini API** | key from AI Studio (`AQ.…` format — authenticates fine). Model `gemini-3.6-flash`. Free tier = 20 req/day/model. | `.env`: `GEMINI_API_KEY`, `GEMINI_MODEL_ID` |
| **Langfuse** | not set up. | `.env`: `LANGFUSE_*` blank |

Other `.env`: `ADMIN_SECRET` (blank = dashboard open locally), `FIELDS_WEBHOOK_SECRET`,
`CRON_SECRET`, `WEB_BASE_URL=http://localhost:3000`, `EXTRACT_BACKEND=gemini`.

---

## 6. What's verified (with evidence)

- **Fase 1 e2e** — `test_transcribe_wiring.py` passes: `OK — 14 finals, both
  speakers, key content present`. Full 49s conversation, "Kathleen O'Brien",
  "Luna", "617-555-0142", clinical notes. Speaker labels vcc/family correct.
- **Transcribe reliability fix** — before the reopen-on-failure change, the call
  died at ~2 finals / ~15s (Transcribe silence-close, initially misdiagnosed as
  a network drop). After: full call. Call-completion 30% → 100% on the fixture.
- **Fase 4** — real SES email sent (`MessageId 010001a0537d1649-…`) and received
  at `raphaelbruno.dev@gmail.com`, subject "Pre-visit briefing — Luna (Kathleen
  O'Brien)".
- **Fase 5 (Gemini)** — 25 samples: names 40% exact / **60% phonetic**, emails
  ~40%. Finding: **every miss is AWS Transcribe (en-US) mangling non-English
  phonemes** ("Aoife Ní Bhraonáin"→"Aoife Ibra Oman", "Seán Mac Cárthaigh"→"Sean
  McCarvey"); the LLM output is faithful to the transcript. **Lever for phonetic
  accuracy is STT, not LLM.**
- **Fase 7** — 6 LiveKit rooms concurrent, all connect + publish, no failures,
  wall 14–19s each, `data isolation: PASS`.
- **Debounce** — was ~13 LLM calls/call, now ~4 + one `finalize()`. ~70% fewer.
- **Cost model** — `pricing.py` demo: ≈$0.26 for an 8-min call ($0.19 Transcribe
  + $0.07 Bedrock Haiku). Real `call_costs` rows exist for the STT leg.
- **healthcheck.py** — STS ✅ Transcribe ✅ SES ✅ Supabase ✅.
- **web** — builds clean; `/`, `/session/[id]`, `/eval`, `/costs`, `/login`,
  `/api/health` all render; error path (bad Supabase creds) shows the error UI.

---

## 7. What's blocked — and exactly how to unblock

### Bedrock — `ThrottlingException: Too many tokens per day`
Persisted >48h since account creation. **Not** a TPM/RPM quota (those default to
5M, plenty) — a separate new-account **daily token cap**. Does not self-resolve.
**Unblock:** AWS Console → Support → Create case → "Account and billing" (free on
Basic support): *"New account upgraded from Free Plan, persistent
ThrottlingException: Too many tokens per day on Bedrock InvokeModel for all
Anthropic models since [date]. TPM/RPM quotas show defaults."* Resolves in hours
to ~1 day.
**Meanwhile:** `EXTRACT_BACKEND=gemini` (already set).

### Gemini — `429 RESOURCE_EXHAUSTED`
Free tier = **20 requests/day/model** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`).
**As of 2026-08-31 the daily quota had reset — Gemini works.** It will re-exhaust
after ~20 requests. **Permanent unblock:** https://aistudio.google.com → Billing →
enable (Flash is ~free — cents for the whole eval). Then remove/lower the
`--sleep` in eval runs.

### Migration 005 not applied
Run `supabase/migrations/005_rls_policies.sql` in the Supabase SQL editor.

### Langfuse not wired
Create a free project at cloud.langfuse.com, put `LANGFUSE_PUBLIC_KEY` /
`LANGFUSE_SECRET_KEY` in `.env`, run any eval or listener session, screenshot the
traces for `INTERVIEW.md`.

---

## 8. When a model unblocks — do this

1. `cd listener && .venv/bin/python smoke_aws.py` (Bedrock) — expect `pong`.
2. Full A/B eval:
   `cd eval && ../listener/.venv/bin/python run.py` (both models) →
   updates `report.md`, `eval_runs`, `/eval`.
3. Listener e2e with real fields:
   - terminal A: `cd listener && .venv/bin/python agent.py --room demo1`
   - terminal B: `cd listener && .venv/bin/python sim_call.py --room demo1 --track both`
   - then open `web` `/session/<id>` — fields should populate; `/costs` shows a
     real LLM cost line.
4. Briefing for that session: `.venv/bin/python briefing.py --session <id>`.
5. Fill in the real extraction-latency p50/p95 and A/B accuracy numbers in
   `INTERVIEW.md` (currently marked "pending quota").

---

## 9. Remaining work, ranked

1. **Unblock a model** (Bedrock support case OR Gemini billing) → real
   extraction numbers. *Highest value — it's the one gap in the demo.*
2. **Run migration 005** (2 min).
3. **Langfuse** — keys + one run + screenshot (~30 min).
4. **Full A/B** once Bedrock is back — Haiku vs Gemini on the 25-sample set,
   write the comparison into `INTERVIEW.md`.
5. **Playwright E2E** for the extension (`webapp-testing` skill) — load unpacked,
   push via WS, assert `demo-scheduler` fills. (Deferred — Playwright-for-extension
   setup is heavy.)
6. **Deploy** — Railway (listener) + Vercel (web), add a GitHub remote.
7. **P95 reduction narrative** — apply one real optimisation from
   `OPTIMIZATION.md` (prompt caching / sliding window) with before/after numbers.
8. **Custom Transcribe vocabulary** — the eval shows this is the real accuracy
   lever; add common owner/pet names, re-run the eval, show the delta.

---

## 10. Key decisions & gotchas

- **Plain `rtc.Room`, not livekit-agents worker** — the listener joins one named
  room via CLI. Simpler; no dispatch/scaling machinery.
- **Extension ↔ listener WS directly** — not through Next. The listener already
  has all field state in-process.
- **Transcribe closes streams on silence** — per-speaker tracks go quiet during
  the other party's turn. `TranscribeSession` reopens on the next failed send.
  This was misdiagnosed as a LiveKit network drop for several test runs.
- **Gemini 3.x burns `max_output_tokens` on thinking** — set 2000, not 60, or you
  get truncated fragments (`"Kathleen O"`, `"Z"`). `thinking_budget=0` is
  rejected by flash (400).
- **Bedrock Haiku 4.5 needs the inference profile** — `us.anthropic.…`, not the
  plain on-demand id ("Not supported").
- **AWS Free Plan is a sandbox** — new accounts land on it; Bedrock/Transcribe
  are gated. Had to "Upgrade plan" (Billing console) to pay-as-you-go. Credits
  still cover it.
- **`web/.env.local` must be a symlink to `../.env`** — Next only auto-loads env
  from its own dir. If it's missing: `cd web && ln -sf ../.env .env.local`.
- **`ADMIN_SECRET` blank in `.env`** — `proxy.ts` fails open, dashboard is
  reachable locally. Set it (+ create `/login` works) for a deployed instance.
- **Python 3.12 venv** — livekit-agents/livekit needs <3.13; system python is 3.14.
- **awscrt "CANCELLED future" noise on shutdown** — cosmetic; `TranscribeSession.
  close()` now drains before cancelling to reduce it.

---

## 11. Commits (newest first)

```
9e76a7a fix(listener): persist fields/costs on teardown despite CancelledError
eacbf14 docs: PROFILE.md — skills demonstrated + CV update guidance
0cf7112 docs: CLAUDE.md + HANDOFF.md + refreshed README
5129825 test(loadtest): 6 concurrent rooms — no failures, isolation holds
60347b8 feat: incident handling, RLS, agent-assist metrics, interview writeup
250c695 feat(listener): swappable extract backend + debounce; OPTIMIZATION.md
3646fa2 feat(listener): Fase 1 reconnect-resilient + Fase 4 SES briefing
f11675f eval: first full Gemini 3.6 Flash run — 25 samples
e5839c1 fix(eval): survive network blips
11e605c fix(eval): Gemini 3.x config + resilience; first real numbers
da7d842 fix(web): address code-review findings on the dashboard
8a45e05 chore(web): .env.local symlink; clear placeholder ADMIN_SECRET
35d4c0e feat(web): dashboard — sessions, session detail, eval, costs
6cecc18 feat: Fase 3 Langfuse tracing + Fase 7 load test
51e13a8 docs: update phase status
ce692bf feat(listener): Fase 2 — incremental Bedrock extraction + per-call cost
065b132 feat(eval): Fase 5 — golden-set A/B harness
25e7b1e feat(listener): fields WebSocket fan-out + extension rewire
3df0b10 feat(listener): Fase 1 — LiveKit listener + AWS Transcribe streaming
9026e0d feat(listener): AWS smoke test + Haiku 4.5 model id
b601623 docs: mark Fase 0/6 done, note blockers
c47a297 feat: eval metrics + Chrome extension
6a3639c chore: scaffold call-copilot (Fase 0)
```
