-- Golden-set A/B results. One row per (run, model, sample).
create table eval_runs (
  id            uuid primary key default gen_random_uuid(),
  run_id        text not null,                 -- timestamp-ish batch id
  model         text not null,                 -- bedrock-haiku | gemini-flash
  sample_id     text not null,
  kind          text not null,                 -- name | email
  expected      text not null,
  got           text not null,
  exact         boolean not null,
  wer           real not null,                 -- word error rate
  lev_norm      real not null,                 -- normalised Levenshtein distance
  phonetic_ok   boolean not null,              -- metaphone match
  created_at    timestamptz not null default now()
);

alter table eval_runs enable row level security;
create index eval_runs_run on eval_runs (run_id, model);
