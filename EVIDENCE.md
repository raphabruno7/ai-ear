# call-copilot — what this demonstrates

A real-time voice **copilot that listens** to a live call between a veterinary
care coordinator (VCC) and a pet family, extracts appointment + clinical fields
as the call runs, and writes them into the scheduling form via a Chrome
extension. Companion piece: [`voice-demo`](../voice-demo) — six *talking* voice
bots. This one never speaks.

Explores **ambient AI** hands-on: streaming STT, real-time structured extraction,
golden-set accuracy evals, Langfuse tracing, concurrency + data-isolation, per-call
cost. Stack: AWS (Transcribe / Bedrock / SES), Google Cloud (Vertex AI), Supabase,
Next.js.

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

## What an ambient copilot needs → evidence

| Capability | In this repo |
|---|---|
| Agent-assist / live transcription copilot | the whole system — `listener/agent.py` |
| Streaming STT, turn handling, low-latency | `listener/transcribe_stream.py` — AWS Transcribe streaming, per-speaker, reopen-on-silence |
| LLM field extraction, structured output, guardrails | `listener/extract.py` — forced `emit_fields` tool (Bedrock) / JSON (Gemini), confidence merge |
| **Model A/B** (Claude Haiku 4.5 vs Gemini 3.6 Flash) | `EXTRACT_BACKEND=bedrock\|gemini` at runtime + `eval/` golden-set harness; real numbers below |
| Golden-set eval — phonetic name/email accuracy | `eval/` — 25 hard samples, WER / Levenshtein / metaphone, `report.md` + `/eval` dashboard |
| Observability (Langfuse) | `listener/trace.py` (v4) — spans on every extract + eval call; 59 traces landed (smoke + full A/B), input/output/metadata per call |
| Cost per call | `listener/pricing.py` + `call_costs` + `/costs` dashboard (STT vs LLM, 1k/mo projection) |
| Concurrency (5–10+ calls) | `loadtest/run.py` — N LiveKit rooms in parallel |
| Data isolation between users | `vcc_id` on every row + `005_rls_policies.sql` + `test_ws_server.py` cross-session check + loadtest isolation assert |
| Incident handling, monitoring, rollback | `HEALTH.md`, `/api/health`, `listener/healthcheck.py` |
| Chrome extension delivery | `extension/` — MV3, WS client, React-safe form fill; WS→contract→fill verified end-to-end against `/demo-scheduler` (7/7 fields incl. textarea, values survive re-render) — `extension/VERIFY.md` |
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
- **Debounced extraction:** one model call per utterance (~13 / call on the 49 s
  fixture) → ~4 / call + one final pass = **−69% LLM invocations**, same field
  coverage. Token-cost ≈ −67% on the fixture (short transcript, fixed
  prompt+schema dominates); on a real 8-min call the saving shrinks (later calls
  carry a bigger transcript) — not yet measured, no real LLM `call_costs` rows.
  Also buys rate-limit headroom (16 → ~5 RPM) and fewer slow-call stalls in the
  time-to-fields UX.
- **Debounce is not a latency tax** (`listener/bench_latency.py` — replays the
  call turn-by-turn, records time-to-first-value per field; single run each,
  directional). Debounce 12s vs per-turn: first-value times a wash or better
  under debounce, call wall-time ~110s vs ~140s, −65% LLM calls. The "~1 min lag
  on one field type" is *transcript position* — `preferred_time` is only agreed
  near call-end; `finalize()` is the backstop. The bench also surfaced
  `visit_type` never being extracted → fixed with a prompt allowed-value list.
- **Per-call cost model:** ≈ $0.26 for an 8-min call — $0.19 Transcribe +
  $0.07 Bedrock Haiku (`pricing.py`, self-checked; real `call_costs` rows for
  the STT leg).
- **Concurrency:** 6 LiveKit rooms opened in parallel — all connect + publish,
  no failures, wall 14–19 s each, cross-session data-isolation assert passes.
- **Eval — full A/B, Haiku 4.5 vs Gemini 3.6 Flash, 25 hard samples:**

  | model (fast tier — not frontier) | names exact | names phonetic | emails exact |
  |---|--:|--:|--:|
  | Gemini 3.6 Flash (Vertex AI) | ~40–47% | ~60–67% | 30% |
  | Claude Haiku 4.5 (Bedrock)   | 40% | 60% | 30% |

  **The two models — different vendor, different architecture — miss the same
  samples.** "Seán Mac Cárthaigh" → "Sean McCarvey" on both, because the input
  transcript is identical and already wrong. `eval/report.md` → "STT is the
  bottleneck" prints the proof: `expected | what Transcribe heard | each model's
  output`. The model columns just echo a broken transcript. Recovering the
  original would be hallucination, not reasoning. **The accuracy lever is the
  transcription layer** — `OPTIMIZATION.md` has the vendor comparison + ranked plan.
- **Extraction runs on Vertex AI** (`GCP_PROJECT` set → Vertex, else AI Studio
  key). Bedrock left wired for the A/B — `EXTRACT_BACKEND` toggles at runtime.
  The `_emit → merge → _persist → extracted_fields` path is verified end-to-end.

## Demo-ready now

- `listener/ws_push.py` + extension + `/demo-scheduler` — the form fills live
  (no cloud needed).
- Full listener run against `sim_call.py` — session → transcript → cost →
  dashboard.
- `eval/run.py` — full A/B (both models), `/eval` dashboard, `eval_runs` rows.
- `briefing.py` — real SES email.

## Pending (not code)

- **Listener e2e with real fields into the dashboard** — needs a stable Wi-Fi;
  LiveKit media (WebRTC UDP) fails on cellular/CGNAT. Extraction + persist path
  already verified without LiveKit.
- **STT accuracy lever** — Transcribe custom vocabulary, then benchmark Deepgram
  Nova-3 as a second STT (same A/B method as the LLMs). `OPTIMIZATION.md`.
- **3rd model in the A/B** — add gpt-4o-mini so "swap the model, same misses"
  holds across 3 vendors.
- **Extension MV3 shell** — one manual load-unpacked pass (the WS+fill logic is
  already verified programmatically).

## What this is not

A deployed product with real users. It's a hands-on model of the problem, verified
in fixtures + programmatic tests. The live LiveKit call e2e is the one piece not
yet run end to end (blocked on a stable network, not code).
