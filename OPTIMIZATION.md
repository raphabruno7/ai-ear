# Cost & latency optimisation plan

Real numbers: `listener/pricing.py` (snapshot), `/costs` dashboard, `eval/report.md`.

## Done
- **Debounce extraction** (`Extractor.min_extract_gap_s`, default 12s + turn count).
  Was: one model call per utterance (~13/call). Now: ~3–4/call + one `finalize()`
  pass at end. ~70% fewer LLM calls, same field coverage.
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
