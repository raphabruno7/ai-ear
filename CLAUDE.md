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

## Why this exists

A portfolio piece exploring **ambient AI** — a copilot that listens to a live
two-party call (a veterinary care coordinator + a pet family in an end-of-life
context), transcribes it, and extracts scheduling/clinical fields in real time.
Companion to `~/voice-demo` (voice *bots that talk*); this one never speaks.
Raphael modelled the product to learn the problem hands-on; it is not tied to any
employer or client. If he asks about turning it into a product, it's viable in
several verticals (real-estate showings, recruiting screens, insurance FNOL) —
the code is domain-light.

## Architecture

```
listener/agent.py   LiveKit room (2 humans + 1 silent listener, no TTS)
  → audio_apm.py   optional WebRTC pre-processing (NS/HPF/AGC) — AUDIO_APM env
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
  Gemini `gemini-3.6-flash` via Vertex AI (`GCP_LOCATION=global`; `us-central1`
  is 2.5-flash only).
- **Fixtures** (`listener/fixtures/*.wav`) are committed; `eval/dataset/audio/*.wav`
  and `eval/dataset/audio_noisy/**` are gitignored — regenerate with
  `eval/make_dataset.py` (macOS `say` + ffmpeg) then `eval/make_noisy.py`.

## Verify / demo commands

```bash
cd listener
.venv/bin/python smoke_aws.py                 # Bedrock reachable? (currently: daily throttle — sleep mode)
.venv/bin/python healthcheck.py               # STS + Transcribe + SES + Supabase
.venv/bin/python test_transcribe_wiring.py    # LiveKit → Transcribe → text, e2e (~50s)
.venv/bin/python test_ws_server.py            # WS routing + isolation
.venv/bin/python extract.py                   # merge + parser self-checks
.venv/bin/python ws_push.py --session demo-1  # drive the extension with fake fields

cd eval && ../listener/.venv/bin/python run.py --models gemini-flash --sleep 12
cd loadtest && ../listener/.venv/bin/python run.py --rooms 6
cd web && npm run build && npm start          # dashboard on :3000
```

## Extraction backend — Gemini via Vertex AI (current)

`EXTRACT_BACKEND=gemini`. `_genai_client()` uses **Vertex AI** when `GCP_PROJECT`
is set (`.env`: `GCP_PROJECT`, `GCP_LOCATION=global`) — ADC auth
(`gcloud auth application-default login`), billed to the GCP project, no
free-tier daily cap. Falls back to the `GEMINI_API_KEY` (AI Studio) path when
`GCP_PROJECT` is unset. `GCP_LOCATION=global` is required for `gemini-3.6-flash`
— `us-central1` only serves `gemini-2.5-flash`.

The `_emit_gemini` → `merge` → `_persist` → `extracted_fields` path is verified
end-to-end (2026-09-01). `pricing.py` `LLM_RATES` has per-backend rates.

## State

- **Live e2e** — ✅ verified 2026-09-07 (needs real Wi-Fi, not an iPhone hotspot —
  CGNAT breaks WebRTC UDP; signalling connects, media doesn't).
- **Bedrock** — throttle cleared ~2026-09-02; **sleep mode** (default is Gemini).
  Set `EXTRACT_BACKEND=bedrock` for the Haiku-vs-Gemini A/B.
- **Migrations `005`** ✅ 2026-09-02, **`006`** (latency stage columns) ✅ 2026-09-09.
  **Langfuse** — ✅ listener + eval trace (v4).
- **Speech→screen latency** — `extracted_fields` has `stt_lag_ms` / `debounce_ms`
  / `e2e_ms` per pass (`transcribe_stream` measures STT lag against a frame-arrival
  mark table; `extract._latency_stages` does the rest). Shown on `/session/<id>`.
- **STT custom vocabulary** — ✅ 2026-09-07. `eval/build_vocab.py` + `TRANSCRIBE_VOCAB`
  env (`transcribe_stream.py`, `agent.py`, `eval/run.py --vocab`). Fixes seeded
  surnames at the source; downstream accuracy within noise. Deep phonetic misses
  need `SoundsLike` (S3 table) or a 2nd STT.
- **Deepgram Nova-3 A/B** — ✅ measured 2026-09-09 (`DEEPGRAM_API_KEY` in `.env`).
  Names phonetic ~60% → 67% (Haiku) / 80% (Gemini), ~5× cheaper than Transcribe.
- **Audio DSP** — ✅ 2026-09-09. `audio_apm.py` (WebRTC NS/HPF/AGC, `AUDIO_APM` env);
  `eval/make_noisy.py` cohort + `run.py --noise/--apm`. Finding: noise halves
  accuracy, but the APM effect is within n=15 wobble — not a reliable lever.
- **Next:** port the live listener (`transcribe_stream.py`) from AWS to Deepgram
  Nova-3 streaming.

## Deploy

- Remote: `origin` → `github.com/raphabruno7/ai-ear`. Push `main` →
  nothing auto-deploys yet (no Railway/Vercel hookup).
- Intended: `listener/` → Railway (Dockerfile + railway.toml), `web/` → Vercel.

## Git

```
Remote: origin → github.com/raphabruno7/ai-ear.
Workflow: branch per task → push → `gh pr create` → user merges to main.
  (one-line fixes may still go straight to main).
Commit style: feat(listener): … / fix(web): … / docs: …
```

## Tooling

- `langfuse` CLI installed globally (`npm i -g langfuse-cli`). `langfuse api
  observations list` reads the eval traces; `traces list` is the deprecated v3
  endpoint — don't use it.

## Reference

- Claim → evidence + numbers: `EVIDENCE.md`
- Incident runbook: `HEALTH.md`
- Cost/latency plan: `OPTIMIZATION.md`
- AWS setup: `listener/AWS.md`
