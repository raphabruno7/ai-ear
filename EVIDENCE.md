# call-copilot — what this demonstrates

A real-time voice **copilot that listens** to a live call between a veterinary
care coordinator (VCC) and a pet family, extracts appointment + clinical fields
as the call runs, and writes them into the scheduling form via a Chrome
extension. Companion piece: [`voice-agent-stacks`](https://github.com/raphabruno7/voice-agent-stacks) — six *talking* voice
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
| Observability (Langfuse) | `listener/trace.py` (v4) — `generation` observation on every extract + eval call (listener `extract_turn` + eval `eval:*`), with input/output, tokens + cost |
| Cost per call | `listener/pricing.py` + `call_costs` + `/costs` dashboard (STT vs LLM, 1k/mo projection) |
| Concurrency (5–10+ calls) | `loadtest/run.py` — N LiveKit rooms in parallel |
| Data isolation between users | `vcc_id` on every row + `005_rls_policies.sql` + `test_ws_server.py` cross-session check + loadtest isolation assert |
| Incident handling, monitoring, rollback | `HEALTH.md`, `/api/health`, `listener/healthcheck.py` |
| Chrome extension delivery | `extension/` — MV3, WS client, React-safe form fill; WS→contract→fill verified end-to-end against `/demo-scheduler` (7/7 fields incl. textarea, values survive re-render) — `extension/VERIFY.md` |
| Telephony / streaming stacks | LiveKit (rooms + SIP), AWS Transcribe; Twilio in `voice-agent-stacks` |
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
- **Per-call cost — real, both legs** (first live e2e, 2026-09-07): a ~113s call
  → `call_costs` row `$0.050` total = `$0.045` Transcribe + `$0.0047` Gemini
  (1829 in / 894 out tokens). Scales to ≈ $0.20–0.26 for an 8-min call — STT is
  ~90% of it. `pricing.py` + `/costs` dashboard.
- **Concurrency:** 6 LiveKit rooms in parallel — all connect + publish + run the
  full transcribe→extract→persist path, cross-session data-isolation assert
  passes. Per-room wall 15–43 s (each waits out its audio + a `finalize()` pass);
  extraction `latency_ms` p50 ~6.5 s under 6-way contention on a single event
  loop. (Before 2026-09-09 the harness skipped extraction — the old "14–19 s,
  no failures" line described connect/publish only.)
- **Eval — full A/B, Haiku 4.5 vs Gemini 3.6 Flash, 25 hard samples:**

  | model (fast tier — not frontier) | names phonetic | names exact | emails exact |
  |---|--:|--:|--:|
  | Gemini 3.6 Flash (Vertex AI) | ~60% | 33–47% | 30% |
  | Claude Haiku 4.5 (Bedrock)   | ~60% | 33–40% | 30% |

  Phonetic accuracy sits at ~60% for both, stable across runs; exact-match
  wobbles ±1–2 samples (this is 15 items, and neither model is fully
  deterministic). **The invariant is *which* samples fail — and they are the same
  for both models, every run.** "Seán Mac Cárthaigh" → "Sean McCarvey" on both,
  because the input transcript is identical and already wrong. `eval/report.md` →
  "STT is the bottleneck" prints the proof: `expected | what Transcribe heard |
  each model's output`. The model columns just echo a broken transcript.
  Recovering the original would be hallucination, not reasoning. **The accuracy
  lever is the
  transcription layer** — `OPTIMIZATION.md` has the vendor comparison + ranked plan.
- **STT custom vocabulary — measured, 2026-09-07.** `eval/build_vocab.py` seeds
  AWS Transcribe with the golden-set owner surnames (in production: the clinic's
  patient roster). Phrases-list format — it biases what Transcribe *hears*.
  Where it lands, it fixes the transcript at the source:

  | sample | Transcribe heard — before | with vocabulary |
  |---|---|---|
  | n07 `Michał Wojciechowski` | "Mitchell **Wozkowski**" | "Mitchell **Wojciechowski**" |
  | n05 `Nguyen Thi Hoa` | "**Nguyenihoa**" | "**Nguyen** … **Hoa**" |
  | e06 `…@icloud.com` | "@**iCloud**.com" | "@**icloud**.com" |

  Downstream field accuracy moved but within noise: names phonetic flat at ~60%
  (both models), names exact 33–47% → 33–53% across runs — the metric wobbles
  ±2 samples on n=15 with non-deterministic formatting. Emails (**not** seeded —
  control) stayed flat at 30%. The residual phonetic misses ("Aoife Ní
  Bhraonáin", "Xiuying Zhang", first-name "Michał"→"Mitchell") are acoustic, not
  spelling — a Phrases list can't reach them.
- **Second STT — Deepgram Nova-3 vs AWS Transcribe (2026-09-09).** Same 25
  samples, same two LLMs, same method as the model A/B — only the transcription
  engine swaps. Nova-3 keyterm prompting carries the same seeded names as the
  AWS vocabulary.

  | names, phonetic | AWS Transcribe + vocab | Deepgram Nova-3 + keyterms |
  |---|--:|--:|
  | Claude Haiku 4.5 | ~60% | **67%** |
  | Gemini 3.6 Flash | ~60% | **80%** |
  | names exact (both) | 33–53% | **60%** |
  | emails exact (control) | 30% | 30% |
  | shared STT misses | 12–13 | **10** |

  Nova-3 recovers what a Phrases list couldn't: "Nguyen Thi Hoa", "Priya
  Rajagopalan", "Xiuying Zhang", "Rhys Llewellyn" all land exact. The 3 residual
  name misses ("Aoife Ní Bhraonáin", "Seán Mac Cárthaigh", "Björn Andersson")
  are Gaelic/Nordic and hard for any engine. Spelled-out emails stay bad on both
  — no STT parses "s underscore gallagher at yahoo dot co dot uk" reliably.
  **And it's ~5× cheaper**: Nova-3 $0.0048/min streaming vs Transcribe
  $0.024/min — a win on accuracy *and* cost. `eval/run.py --stt deepgram`.
- **Full live e2e — verified 2026-09-07.** LiveKit room → 2 simulated speakers →
  per-speaker AWS Transcribe → Gemini extraction (Vertex AI) → `extracted_fields`
  + `call_costs` in Supabase → `/session/<id>` + `/costs`. Two consecutive runs:
  14 turns each, **7/7 fields** (`owner_name` "Kathleen O'Brien", phone, email,
  `pet_name` "Luna", `visit_type` "sick" inferred, `preferred_time`,
  `clinical_notes`), clean teardown. `EXTRACT_BACKEND` toggles Vertex ⇄ Bedrock
  at runtime. (The live listener streams AWS Transcribe; Deepgram Nova-3 is wired
  in the eval harness, not yet in the listener.)
- **Speech → screen latency, by stage (2026-09-09).** Each extraction pass now
  records where the time goes — end of speech → stabilised transcript (`stt_lag`),
  → pass fires (`debounce`), → LLM response (`latency_ms`), → field persisted
  (`e2e`). Written to `extracted_fields`, shown on `/session/<id>`. Two live runs
  (49 s fixture, Gemini 3.6 Flash):

  | stage | p50 | p95 |
  |---|--:|--:|
  | STT lag (AWS Transcribe) | ~0.6 s | ~0.6–1.4 s |
  | Debounce wait | ~0 s | ~0 s |
  | LLM extraction call | ~3–4.5 s | ~6–7 s |
  | **End to end** (speech → field in DB) | **~3.7–5 s** | **~6.4–7.5 s** |

  The LLM call dominates. Debounce ≈ 0 **on this fixture** because the 4-turns
  gate trips before the 12 s timer (turns ~3.5 s apart), so a pass fires on the
  turn that trips it — its cost here is *staleness of earlier turns*, not delay
  on the triggering one. A slower call where the 12 s timer wins would show a
  real debounce leg; `bench_latency.py` measures that separately. Stage values
  are per-pass, replicated onto every field of that pass, not per-field
  independent samples, and `stt_lag + debounce + llm` reconciles with `e2e` to
  ±200 ms (mark-timestamp vs turn-timestamp capture gap). Browser fill adds a
  few ms on top (`[copilot] ws->browser` console log; localhost, no clock skew).

## Demo-ready now

- `listener/ws_push.py` + extension + `/demo-scheduler` — the form fills live
  (no cloud needed).
- Full listener run against `sim_call.py` — session → transcript → cost →
  dashboard.
- `eval/run.py` — full A/B (both models), `/eval` dashboard, `eval_runs` rows.
- `briefing.py` — real SES email.

## Pending (not code)

- **STT accuracy lever** — ✅ Transcribe custom vocabulary + ✅ Deepgram Nova-3
  A/B, both measured (see Real numbers). Nova-3 wins on names and cost — porting
  the live listener to it is the next step. `OPTIMIZATION.md`.
- **3rd model in the A/B** — add gpt-4o-mini so "swap the model, same misses"
  holds across 3 vendors.
- **Extension MV3 shell** — one manual load-unpacked pass (the WS+fill logic is
  already verified programmatically).

## What this is not

A deployed product with real users. It's a hands-on model of the problem —
verified end to end against a simulated call, not tested on live production
traffic.
