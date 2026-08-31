# call-copilot — what this demonstrates

A real-time voice **copilot that listens** to a live call between a veterinary
care coordinator (VCC) and a pet family, extracts appointment + clinical fields
as the call runs, and writes them into the scheduling form via a Chrome
extension. Companion piece: [`voice-demo`](../voice-demo) — six *talking* voice
bots. This one never speaks.

Built to mirror the target stack: **AWS Bedrock / Transcribe / SES**, golden-set
evals, Langfuse, concurrency + data-isolation testing, per-call cost.

## Pipeline

```
LiveKit room (VCC + family + 1 silent listener)
   │  one audio track per speaker
   ▼
AWS Transcribe streaming ──► running transcript, per-speaker
   ▼
extraction (AWS Bedrock Claude Haiku  ⇄  Gemini — EXTRACT_BACKEND toggle)
   │  forced tool / JSON, merge by confidence, debounced ~12s
   ▼
Supabase (extracted_fields, call_costs)  +  WebSocket ──► Chrome extension ──► form
   ▼
AWS SES ──► pre-visit briefing email (per session)
```

## Requirement → evidence

| Job asks for | In this repo |
|---|---|
| Agent-assist / live transcription copilot | the whole system — `listener/agent.py` |
| Streaming STT, turn handling, low-latency | `listener/transcribe_stream.py` — AWS Transcribe streaming, per-speaker, reopen-on-silence |
| LLM field extraction, structured output, guardrails | `listener/extract.py` — forced `emit_fields` tool (Bedrock) / JSON (Gemini), confidence merge |
| **Model A/B** (Claude Haiku vs GPT) | `EXTRACT_BACKEND=bedrock\|gemini` at runtime + `eval/` golden-set harness |
| Golden-set eval — phonetic name/email accuracy | `eval/` — 25 hard samples, WER / Levenshtein / metaphone, `report.md` + `/eval` dashboard |
| Observability (Langfuse) | `listener/trace.py` — spans on every extract + eval call |
| Cost per call | `listener/pricing.py` + `call_costs` + `/costs` dashboard (STT vs LLM, 1k/mo projection) |
| Concurrency (5–10+ calls) | `loadtest/run.py` — N LiveKit rooms in parallel |
| Data isolation between users | `vcc_id` on every row + `005_rls_policies.sql` + `test_ws_server.py` cross-session check + loadtest isolation assert |
| Incident handling, monitoring, rollback | `HEALTH.md`, `/api/health`, `listener/healthcheck.py` |
| Chrome extension delivery | `extension/` — MV3, WS client, React-safe form fill |
| Telephony / streaming stacks | LiveKit (rooms + SIP), AWS Transcribe; Twilio in `voice-demo` |
| SES epic end to end | `listener/briefing.py` — verified: real email sent + received |
| AWS: Bedrock, serverless, SES, token economics | all three wired; `pricing.py` + debounce + `OPTIMIZATION.md` |
| Empathy-sensitive domain | modelled on veterinary end-of-life care |

## Real numbers

- **Transcription, end to end:** 49 s two-speaker fixture → 14 final transcripts,
  both speaker labels correct, "Kathleen O'Brien" + "Luna" + phone + clinical
  notes. (`test_transcribe_wiring.py`)
- **Reliability fix — Transcribe silence close:** before, the call was
  effectively dead after ~2 utterances (~15 s); after the reopen-on-failure
  change, the full 49 s transcribes. Call-completion 30% → 100% on the fixture.
- **Cost reduction — debounce:** one model call per utterance (~13 / call) →
  ~4 / call + one final pass. ~70% fewer LLM calls, same field coverage.
- **Per-call cost model:** ≈ $0.26 for an 8-min call — $0.19 Transcribe +
  $0.07 Bedrock Haiku (`pricing.py`, self-checked; real `call_costs` rows for
  the STT leg).
- **Concurrency:** 6 LiveKit rooms opened in parallel — all connect + publish,
  no failures, wall 14–19 s each, cross-session data-isolation assert passes.
  (Job bar: 5–10+ concurrent calls.)
- **Eval — Gemini 3.6 Flash, 25 samples:** names 40% exact / 60% phonetic,
  emails ~40%. **Every miss is AWS Transcribe (en-US) mangling non-English
  phonemes** — "Aoife Ní Bhraonáin" → "Aoife Ibra Oman", "Seán Mac Cárthaigh" →
  "Sean McCarvey". The LLM output is faithful to the transcript. **Conclusion:
  the lever for phonetic accuracy is STT (custom vocabulary / multilingual
  model), not LLM choice.**

## Demo-ready now

- `listener/ws_push.py` + extension + `/demo-scheduler` — the form fills live
  (no cloud needed).
- Full listener run against `sim_call.py` — session → transcript → cost →
  dashboard.
- `eval/run.py` (Gemini side), `/eval` dashboard.
- `briefing.py` — real SES email.

## Pending external quota (not code)

- **Bedrock daily token cap** on the new AWS account — Support case to be filed
  ("Account and billing", free). Blocks the Haiku side of the A/B and Fase 2
  with real fields.
- **Gemini free tier** = 20 req/day — blocks repeated full runs until billing
  is enabled.

## Honest gaps (interview, not repo)

6+ yrs AI/ML history · consulting seniority under UAT · PE-rollout experience ·
US/ET overlap · "shipped to real users at scale" (these are strong *artifacts*,
not a deployed product with a user base).
