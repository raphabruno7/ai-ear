-- Data isolation between coordinators. The service_role key (listener, web
-- server) bypasses RLS; these policies govern any client that authenticates as a
-- specific VCC (e.g. the Chrome extension using a scoped anon+JWT).
--
-- The JWT is expected to carry the coordinator id in claim `vcc_id`.

create policy sessions_own on sessions
  for select using (vcc_id = (auth.jwt() ->> 'vcc_id'));

create policy extracted_fields_own on extracted_fields
  for select using (vcc_id = (auth.jwt() ->> 'vcc_id'));

-- costs and eval data are operator-only: no VCC-scoped access at all.
-- (service_role still reads/writes everything.)
create policy call_costs_none on call_costs for select using (false);
create policy eval_runs_none on eval_runs for select using (false);
