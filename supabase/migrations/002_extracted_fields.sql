-- One row per (session, field) change. History kept: a field re-extracted with
-- higher confidence inserts a new row rather than mutating. Latest row per
-- (session_id, field_name) wins in the UI.
create table extracted_fields (
  id            uuid primary key default gen_random_uuid(),
  session_id    uuid not null references sessions(id) on delete cascade,
  vcc_id        text not null,                 -- denormalised for the isolation check
  field_name    text not null,                 -- owner_name | owner_email | pet_name | visit_type | ...
  field_value   text not null,
  confidence    real not null default 0,       -- 0..1, from the extraction model
  model         text not null,                 -- bedrock-haiku | gemini-flash
  -- latency from the user turn that produced this value -> extraction response.
  -- This is the P95 we report (the job's "~1min lag on one field type" target).
  latency_ms    integer,
  extracted_at  timestamptz not null default now()
);

alter table extracted_fields enable row level security;
create index extracted_fields_session on extracted_fields (session_id, field_name, extracted_at desc);
create index extracted_fields_vcc on extracted_fields (vcc_id);
