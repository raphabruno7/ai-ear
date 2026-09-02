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

## Next
- **Prompt caching** (Bedrock): the system prompt + tool schema are constant —
  cache them, pay input tokens only for the growing transcript delta.
- **Sliding-window transcript**: send the last ~40s, not the whole call. Caps
  input-token growth on long calls.
- **Skip stable fields**: once a field is confirmed by the VCC (or high-confidence
  twice), stop re-extracting it — shrink the schema per turn.
- **Cheaper model for trivial fields**: visit_type / preferred_time don't need a
  frontier model; route only name/email (phonetic-hard) to the better one.
- **The real lever for accuracy is STT** — eval shows every miss is AWS Transcribe
  mangling non-English names. Add a Transcribe custom vocabulary of common
  owner/pet names, or evaluate a multilingual STT (Deepgram, Whisper).
