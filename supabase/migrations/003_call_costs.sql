-- Real per-call cost, accumulated by the listener over the session and upserted
-- on shutdown. Prices are a manual snapshot in listener/pricing.py.
create table call_costs (
  session_id        uuid primary key references sessions(id) on delete cascade,
  stt_seconds       real not null default 0,
  llm_input_tokens  integer not null default 0,
  llm_output_tokens integer not null default 0,
  usd_stt           numeric(10,5) not null default 0,
  usd_llm           numeric(10,5) not null default 0,
  usd_total         numeric(10,5) not null default 0,
  updated_at        timestamptz not null default now()
);

alter table call_costs enable row level security;
