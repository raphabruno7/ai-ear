-- A call the copilot listened to (VCC <-> pet family). One row per call.
create table sessions (
  id            uuid primary key default gen_random_uuid(),
  room_name     text not null unique,          -- LiveKit room name
  vcc_id        text not null,                 -- which coordinator owns this call (data-isolation key)
  call_source   text not null default 'sim',   -- sim | sip | web
  started_at    timestamptz not null default now(),
  ended_at      timestamptz,
  briefed_at    timestamptz,                   -- set when the SES pre-visit email went out
  created_at    timestamptz not null default now()
);

alter table sessions enable row level security;
-- Operational/internal — service_role only, no public policy (PII: pet-family calls).
create index sessions_vcc_id on sessions (vcc_id, started_at desc);
