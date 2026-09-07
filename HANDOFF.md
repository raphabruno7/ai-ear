# call-copilot — session handoff

Complete context to continue this project in a fresh Claude Code session opened
**inside `~/call-copilot`**. Everything below reflects state as of 2026-09-02.

---

## 0.0 PENDING — start here next cycle (as of 2026-09-07)

**Done since 2026-09-02:**
- #5 prompt-audit F1–F3 (PR #7) + a `_clean` ramble guard. Phonetic ~60% both
  models (stable); exact-match wobbles ±1–2 on 15 samples.
- **#1 Listener e2e — DONE 2026-09-07.** Two live runs (`e2e-1` = `c3b4e90d…`,
  `e2e-2` = `e046010f…`): LiveKit → 2 speakers → Transcribe → Gemini → 7/7 fields
  in `extracted_fields`, real `call_costs` row ($0.050 for a 113s call). Ran on
  the hotspot despite the CGNAT history — got lucky / better link.
- **#2 briefing** — verified via `--dry-run` on the real session (pulls all 7
  fields into the email body). Not sent (SES = real email; run without
  `--dry-run` to send).
- **Bug fixed** — `trace.py` evaluated `_ENABLED` at import, before `agent.py`
  called `load_dotenv` → the **listener never traced to Langfuse** (eval did).
  `trace.py` now loads `../.env` itself. Verified: `extract_turn` GENERATIONs
  now land.

Remaining:

Nothing left is an engineering blocker. Each item is a credential or a chore.

| # | Item | Blocked on | Effort |
|---|---|---|---|
| 3 | **Langfuse screenshot** — open an `extract_turn` or `eval:gemini-flash` trace, screenshot for `EVIDENCE.md` | nothing (traces are live) | 2 min |
| 4 | **STT custom vocabulary** (the accuracy lever) — create a vocab of hard owner/pet names, wire `VocabularyName` into `transcribe_stream.py` + `eval/models.py`, re-run eval, show the delta | add `transcribe:CreateVocabulary` / `GetVocabulary` / `ListVocabularies` / `DeleteVocabulary` to the `call-copilot-policy` IAM policy (AWS console) | ~1 h after IAM |
| 5 | **3rd model in the A/B** — add an `openai` backend to `eval/models.py` (gpt-4o-mini) so the "swap the model, same misses" point holds across 3 vendors, not 2. | `OPENAI_API_KEY` | 30 min |
| 4b | **Benchmark a 2nd STT** — same A/B method as the LLMs, but for transcription: Deepgram Nova-3 / Speechmatics / gpt-4o-transcribe vs AWS Transcribe on the golden set. This is the *real* accuracy lever (see `OPTIMIZATION.md`). | a Deepgram key (free tier) | ~2 h |
| 7 | **Deploy** — `listener/` → Railway (Dockerfile + railway.toml ready), `web/` → Vercel. Add CI. | Railway + Vercel accounts/tokens | half a day |
| 8 | **Extension MV3 manual pass** — one `chrome://extensions` → Load unpacked → confirm badge ● + fill (WS+fill logic already verified programmatically, `extension/VERIFY.md`) | nothing | 10 min |
| 9 | **Bedrock support case** — still open? if the throttle cleared (it did on 2026-09-02), nothing to do; the A/B already ran both sides | — | — |

**Workflow from here:** branch per task → push → `gh pr create` → user merges.
One-line fixes may go straight to `main`.

**PRs merged this cycle:** #1 (README refresh + PR workflow), #2 (Langfuse
token+cost), #3 (DEMO.md + PROFILE.md refresh).

---

## 0. Session log

### 2026-09-07
- **Listener e2e finally runs.** See §0.0. First successful full-pipeline run in
  the project's history; the teardown fix, idle watchdog, Vertex swap and
  token/cost work all paid off. 7/7 fields, real `call_costs`, clean teardown.
- **`trace.py` import-order bug** — the listener's Langfuse spans were a silent
  no-op because `_ENABLED` was read before `agent.py`'s `load_dotenv`. Fixed
  (trace.py loads `../.env`). The "59 traces" before this were all eval + smoke.
- Prompt-audit F1–F3 + `_clean` guard merged (PR #7).

### 2026-09-03
- **Reframe** — the project is no longer positioned around a specific job/company.
  Client name removed from all docs. It's a hands-on portfolio piece on **ambient
  AI**. `INTERVIEW.md` → `EVIDENCE.md`.
- **`eval/report.md` now proves the STT-bottleneck finding** — new
  `## STT is the bottleneck` section: `sample | expected | what Transcribe heard
  | each model's output`. The model columns just echo a broken transcript.
- **`eval/models.extract_gemini` → JSON mode** (`response_mime_type` + `{"value"}`
  envelope). Gemini 3.6 Flash was occasionally narrating instead of answering on
  hard emails; matches how the listener's `_emit_gemini` already works.
- **`OPTIMIZATION.md`** — STT section rewritten: vendor comparison (Deepgram /
  Speechmatics / gpt-4o-transcribe / Whisper-is-batch) + ranked plan.
- **`langfuse` CLI installed** (`npm i -g langfuse-cli`, official). Use
  `langfuse api observations list` (v4); `traces list` is the deprecated v3 path.
- PRs #4 (PENDING list), #5 (STT-bottleneck section) merged.

### 2026-08-31 → 09-02

- **Extraction now runs on Vertex AI (Google Cloud).** `_genai_client()` in
  `extract.py` + `eval/models.py` use Vertex when `GCP_PROJECT` is set (ADC auth,
  `gcloud auth application-default login`) — billed to the GCP project, no
  free-tier daily cap. `EXTRACT_BACKEND=gemini` is still the value; Vertex is
  transparent. `.env`: `GCP_PROJECT=project-f785b239-de2b-43c7-b98`,
  `GCP_LOCATION=global`, `GEMINI_MODEL_ID=gemini-3.6-flash` (only `global`
  serves 3.6; `us-central1` is 2.5-flash only). Verified: real fields extracted
  through the `Extractor` path and through `eval/models.extract_gemini`.
- `pricing.py` now has per-backend LLM rates (`LLM_RATES`); `llm_cost(..., backend)`.
  Gemini 3.6 Flash on Vertex ≈ $0.75/$3.75 per 1M (introductory, to 2026-12-31).
- **Bedrock is in sleep mode, not removed.** `_emit_bedrock`, `_bedrock_client`,
  `extract_bedrock`, the Bedrock rate in `LLM_RATES` all untouched. The day the
  AWS support case clears: set `EXTRACT_BACKEND=bedrock` and it works again.
- **Gemini (AI Studio key)** — daily free-tier quota had also reset, but the
  Vertex path makes that irrelevant now. Bedrock still
  `ThrottlingException: Too many tokens per day` (support case still needed —
  §7 / §0 checklist).
- **Bug found + fixed + committed** (`9e76a7a`): `TranscribeSession.close()`'s
  shielded wait raises `CancelledError` (a `BaseException`), which slipped past
  the `except Exception` guards in `agent.py` teardown → `finalize()` / `flush()`
  were **never reached**, so `extracted_fields` / `call_costs` never landed even
  on a clean full transcript. Now: `CancelledError` caught explicitly in
  `transcribe_stream.py`; each teardown step (`finalize`/`flush`/`ws.stop`/
  `sessions.update`) wrapped best-effort in `agent.py`. Verified — run
  `demo-real-2` completed teardown cleanly and wrote a `call_costs` row.
- **Second fix, committed** (`fix(listener): idle watchdog…`): LiveKit swallows
  `participant_disconnected` on a signalling resume → the listener hung forever
  with the full transcript in memory but `finalize()` never called (runs
  `demo-real-6`). Added an idle watchdog: end the call after `CALL_IDLE_END_S`
  (default 30s) with no new transcript turn. Self-checked.
- **Real extraction numbers still NOT captured.** 8 e2e attempts this session.
  Two distinct failure modes, both environmental (this machine ↔ LiveKit media):
  1. **tracks never subscribe** — subscriber PeerConnection can't complete ICE
     (`signal_event taking too much time`, no `transcribing track` line). Runs
     4, 5, 7, 8. Intermittent — run 6 subscribed fine at 20:55.
  2. **tracks subscribe, full transcript, then hang** on a `ping timeout` /
     resume that eats the disconnect. Runs 1–3, 6. Now handled by the watchdog.
  `extracted_fields` table is **still empty** — no run has survived subscribe →
  full transcript → `finalize()` in one go.
  **Next:** retry the §8 e2e on a stable network (mode 1 is pure connectivity);
  the code path is now robust once a run completes. Then `/session/<id>` +
  fill `EVIDENCE.md`.
- **Root cause of the connectivity failure:** default route gateway `172.20.10.1`
  + `en14` marked `constrained` = the machine was on an **iPhone Personal
  Hotspot**. CGNAT on cellular breaks WebRTC UDP hole-punching — signalling
  connects, media never does. Fix is a normal Wi-Fi, not code.

(Consolidated do-now/on-the-Wi-Fi checklist moved to **§0.0 PENDING** above.
Migration 005 ✅, Langfuse ✅, Bedrock throttle cleared ✅, A/B ran both sides ✅.)

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

**A portfolio piece exploring ambient AI** — clinical software that listens and
writes the record instead of talking. Raphael modelled the product to learn the
problem hands-on; it is **not tied to any employer or client**.

Companion repo: `~/voice-demo` — six *talking* voice bots (Hume, LiveKit/Gemini
Live, ElevenLabs, Vapi, Retell, Twilio). Framing: "bots that talk" (voice-demo)
vs "a copilot that listens" (call-copilot). **Keep them separate.**

### Commercialisation note
The code is domain-light and viable in several verticals (real-estate showings,
recruiting screens, insurance FNOL). No client data or roadmap is involved.

---

## 2. How it was built

This session started in the `~/voice-demo` terminal. Claude planned the work
(9 phases, plan file at `~/.claude/plans/crie-um-plano-de-witty-pond.md`), then
scaffolded `~/call-copilot` as a **new git repo** (no remote) and built it out
across ~21 commits. All infra accounts were created live during the session.

Original plan decisions (all still hold):
- **New repo**, cloning patterns from voice-demo by hand (not a dependency).
- **AWS Transcribe** for STT (AWS-native managed service; benchmarked against alternatives in `OPTIMIZATION.md`).
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
| 3 | Langfuse tracing | ✅ `trace.py` (v4) wired into extract + eval; keys in `.env`; 59 traces landed (smoke + full A/B). Screenshot pending. |
| 4 | SES pre-visit briefing | ✅ **verified** — real email sent and received (`briefing.py`) |
| 5 | golden-set A/B eval | ✅ Gemini side: 25 samples run, `report.md` + `/eval` dashboard + `eval_runs` rows. Bedrock side blocked. |
| 6 | Chrome extension + demo-scheduler | ✅ MV3 + WS fan-out; WS+fill path verified against the real page 2026-09-02 (`extension/VERIFY.md`, `docs/extension-fill-verified.jpg`); MV3 shell still needs one manual load-unpacked pass |
| 7 | load test + isolation | ✅ 6 concurrent LiveKit rooms, no failures, isolation assert PASS; extraction rows 0 (Gemini quota) |
| 8 | cost tracking + optimisation | ✅ `call_costs`, `/costs`, debounce (~70% fewer LLM calls), `OPTIMIZATION.md` |
| 9 | evidence writeup | ✅ `EVIDENCE.md` (claim → evidence + real numbers) |
| — | incident handling | ✅ `HEALTH.md`, `web/api/health`, `listener/healthcheck.py` (4/4 ok) |
| — | RLS policies | ✅ `005_rls_policies.sql` **run 2026-09-02** in Supabase |
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
- `005_rls_policies.sql` — per-`vcc_id` SELECT on sessions + extracted_fields; deny-all on costs/eval. **Run 2026-09-02.**

---

## 5. Infrastructure (all live, created this session)

Secrets are in `~/call-copilot/.env` (gitignored). Non-secret identifiers:

| Service | What | Where |
|---|---|---|
| **AWS** | account `441541653312`, region `us-east-1`. IAM user `call-copilot-listener` (policy `call-copilot-policy`: bedrock InvokeModel*, aws-marketplace View/Subscribe, transcribe StartStream*, ses:SendEmail). **Upgraded off the Free Plan** to pay-as-you-go. | `.env`: `AWS_ACCESS_KEY_ID/SECRET`, `AWS_REGION` |
| **Bedrock** | model access granted (Anthropic Claude Haiku 4.5 + 3 Haiku). Model id `us.anthropic.claude-haiku-4-5-20251001-v1:0` (US inference profile). | `.env`: `BEDROCK_MODEL_ID` |
| **SES** | identity `raphaelbruno.dev@gmail.com` **verified**. Sandbox (send only to verified). | `.env`: `SES_FROM_EMAIL`, `SES_TO_EMAIL` (both the gmail) |
| **LiveKit Cloud** | project `copilot-aws-1s7p7hzj`, EU region. Agent observability disabled. | `.env`: `LIVEKIT_URL` (`wss://copilot-aws-1s7p7hzj.livekit.cloud`), `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| **Supabase** | project ref `qtynypkfbwdstnnfiuuw`. URL `https://qtynypkfbwdstnnfiuuw.supabase.co`. Migrations 001–005 applied. | `.env`: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` |
| **Gemini API** | key from AI Studio (`AQ.…` format — authenticates fine). Model `gemini-3.6-flash`. Free tier = 20 req/day/model. | `.env`: `GEMINI_API_KEY`, `GEMINI_MODEL_ID` |
| **Langfuse** | EU cloud, project `cmtk3gub6013qad0cxmnpkjmf`. Traces flowing. | `.env`: `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` |

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

### Migration 005 — done (2026-09-02).

### Langfuse — DONE (2026-09-02)
`trace.py` updated for langfuse **v4** (`start_as_current_observation`). Keys in
`.env` (EU region, project `cmtk3gub6013qad0cxmnpkjmf`). **59 traces landed** —
1 smoke + a full A/B (33 `eval:gemini-flash` + 25 `eval:bedrock-haiku`), each
with input (transcript+kind), output, and metadata (expected, sample id).
`smoke_langfuse.py` sends one on demand.
Traces: https://cloud.langfuse.com/project/cmtk3gub6013qad0cxmnpkjmf/traces
**Left:** screenshot one opened trace for `EVIDENCE.md`.
**To finish (~10 min, no Wi-Fi needed):**
1. Free project at https://cloud.langfuse.com → Settings → API Keys.
2. In `.env`: `LANGFUSE_PUBLIC_KEY=pk-lf-…`, `LANGFUSE_SECRET_KEY=sk-lf-…`
   (`LANGFUSE_HOST` is already `https://cloud.langfuse.com`).
3. `cd listener && .venv/bin/python smoke_langfuse.py` → prints a trace URL.
4. `cd eval && ../listener/.venv/bin/python run.py --models gemini-flash` →
   traces populate. Screenshot for `EVIDENCE.md`.

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
   `EVIDENCE.md` (currently marked "pending quota").

---

## 9. Remaining work, ranked

1. **Unblock a model** (Bedrock support case OR Gemini billing) → real
   extraction numbers. *Highest value — it's the one gap in the demo.*
2. ~~Run migration 005~~ ✅ done.
3. **Langfuse** — keys + one run + screenshot (~30 min).
4. **Full A/B** once Bedrock is back — Haiku vs Gemini on the 25-sample set,
   write the comparison into `EVIDENCE.md`.
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
