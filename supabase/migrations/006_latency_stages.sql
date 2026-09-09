-- Speech->screen latency, broken into stages. `latency_ms` (002) is only the LLM
-- leg; these add the rest so the dashboard can show where the time goes.
--
-- All three are per-extraction-pass values, written identically onto every field
-- that pass persisted (same as latency_ms). They are "time from the last
-- utterance ending to this field appearing", NOT per-field independent samples.
-- Rows written before this migration stay NULL.
--
--   stt_lag_ms   end of speech            -> stabilised final transcript (AWS Transcribe)
--   debounce_ms  final transcript         -> extraction pass fires (min_extract_gap_s)
--   latency_ms   extraction pass fires    -> LLM response (existing column)
--   e2e_ms       end of speech            -> field persisted  (~ sum of the above)

alter table extracted_fields add column stt_lag_ms  integer;
alter table extracted_fields add column debounce_ms integer;
alter table extracted_fields add column e2e_ms      integer;

-- RLS is per-table (005), not per-column — nothing to add.
