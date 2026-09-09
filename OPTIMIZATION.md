# Cost & latency optimisation plan

Real numbers: `listener/pricing.py` (snapshot), `/costs` dashboard, `eval/report.md`.

## Done
- **Debounce extraction** (`Extractor.min_extract_gap_s`, default 12s + turn count).
  Was: one model call per utterance (~13/call). Now: ~3–4/call + one `finalize()`
  pass at end. ~70% fewer LLM calls, same field coverage.

  **Debounce is not a latency tax** — `listener/bench_latency.py` replays the
  fixture call turn-by-turn at a realistic cadence and records when each field
  first gets a value (single run each, Gemini 3.6 Flash on Vertex, after the
  `visit_type` prompt fix below):

  | field | debounce 12s | per-turn (gap=0) |
  |---|--:|--:|
  | clinical_notes | 29s | 22s |
  | visit_type | 29s | 22s |
  | owner_name | 40s | 38s |
  | owner_phone | 53s | 56s |
  | owner_email | 67s | 74s |
  | pet_name | 81s | 95s |
  | preferred_time | 100s | 126s |
  | call wall-time | ~110s | ~140s |

  First-value times are a wash (±5s early, debounce *ahead* on the later fields),
  and the call finishes ~25s sooner: per-turn extraction serialises ~14 LLM calls
  and fires them on fragments that lack context, so it is both slower and pricier.
  Single run each — the later-field deltas carry LLM-nondeterminism noise; the
  direction (debounce ≥ per-turn on latency, −65% on calls) is the robust claim.

- **The "~1 min lag on one field type" is transcript position, not the extractor.**
  `preferred_time` cannot appear before ~100s because the appointment slot is
  only agreed near the end of the call. The mitigation is the `finalize()`
  full-transcript pass (guarantees capture by end-of-call) plus surfacing
  `clinical_notes` provisionally from ~29s and letting it update.
- **`visit_type` gap found by the bench and fixed** — it was never extracted
  (the model didn't infer a type from "not eating / lethargic"). Added an
  allowed-value list + inference hint to `_SYSTEM`; now lands at ~29s.
- **Swappable backend** (`EXTRACT_BACKEND=bedrock|gemini`) — run the cheaper/faster
  model per deployment; the A/B eval picks the winner per field type.
- **STT stream reopen on silence** instead of holding one stream open (Transcribe
  bills per second of audio sent, not wall-clock).

## The accuracy lever is STT, not the LLM

The A/B (`eval/report.md` → "STT is the bottleneck") shows Claude Haiku 4.5 and
Gemini 3.6 Flash **miss the same samples** — because the transcript is identical
and already wrong. `"Seán Mac Cárthaigh"` arrives as `"Sean McCarvey"`; no model
recovers the original without hallucinating. Swapping or upgrading the LLM does
not move the number. The transcription layer does.

**Why AWS Transcribe is in this build:** it's the AWS-native managed STT, so
"is the cloud default good enough?" is a fair question to answer in practice.
The answer, on hard non-English names: no.

**The landscape** (from testing, not just reading):

| Option | Streaming | Non-English names / accent | Notes |
|---|---|---|---|
| **AWS Transcribe** (live listener) | ✅ | weak — ~60% names phonetic | custom vocabulary helps spelling, not acoustics; $0.024/min |
| **Deepgram Nova-3** (eval, benchmarked) | ✅ (built for it) | **better — 67% Haiku / 80% Gemini names phonetic** | keyterm prompting; $0.0048/min streaming (~5× cheaper) |
| **Speechmatics** | ✅ (sub-500ms) | best on accented English | one model per language covers all regional variants |
| **gpt-4o-transcribe** | ✅ (Realtime API) | good | OpenAI-hosted |
| **Whisper** (`whisper-1`) | ❌ batch | good accuracy | too slow for a live call; deployable on SageMaker if latency budget allows |

**Ranked plan:**
1. ✅ **AWS Transcribe custom vocabulary** (done 2026-09-07) — `eval/build_vocab.py`,
   Phrases list from the golden-set surnames, `TRANSCRIBE_VOCAB` env. Fixes
   seeded surnames in the transcript ("Wozkowski"→"Wojciechowski"); downstream
   field accuracy within noise (`EVIDENCE.md`). `SoundsLike`/IPA would reach the
   acoustic misses but needs the S3 table format (extra IAM + a bucket).
2. ✅ **Deepgram Nova-3 A/B** (done 2026-09-09) — `eval/run.py --stt deepgram`,
   `transcribe_deepgram` prerecorded API, Nova-3 keyterms = the seeded names.
   Result: names phonetic ~60% → **67% (Haiku) / 80% (Gemini)**, names exact
   33–53% → **60%**, emails flat (control). **Cost**: Nova-3 streaming
   $0.0048/min vs Transcribe $0.024/min — **~5× cheaper**. Both directions win.
3. **Port the live listener to Nova-3** — `transcribe_stream.py` currently
   streams AWS. Deepgram has a streaming WS API; the eval used prerecorded.
   This is the next real change.
4. Custom language model on Transcribe, or Speechmatics, if 2–3 fall short.

## Next (cost / latency)
- **Prompt caching** (Bedrock): the system prompt + tool schema are constant —
  cache them, pay input tokens only for the growing transcript delta.
- **Sliding-window transcript**: send the last ~40s, not the whole call. Caps
  input-token growth on long calls.
- **Skip stable fields**: once a field is confirmed by the VCC (or high-confidence
  twice), stop re-extracting it — shrink the schema per turn.
- **Cheaper model for trivial fields**: visit_type / preferred_time don't need a
  frontier model; route only name/email (phonetic-hard) to the better one.
