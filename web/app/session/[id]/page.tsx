import { notFound } from "next/navigation";
import { getSupabaseAdmin } from "@/lib/supabase";
import { percentile, fmtUSD } from "@/lib/stats";
import { Stat } from "@/components/stat";

export const dynamic = "force-dynamic";

type Field = {
  field_name: string;
  field_value: string;
  confidence: number;
  model: string;
  latency_ms: number | null;
  stt_lag_ms: number | null;
  debounce_ms: number | null;
  e2e_ms: number | null;
  extracted_at: string;
};

type Session = { room_name: string; vcc_id: string; started_at: string; ended_at: string | null };
type Cost = { usd_total: number } | null;

export default async function SessionPage({ params }: PageProps<"/session/[id]">) {
  const { id } = await params;

  let session: Session | null = null;
  let rows: Field[] = [];
  let cost: Cost = null;
  let error: string | null = null;

  try {
    const sb = getSupabaseAdmin();
    const s = await sb
      .from("sessions")
      .select("room_name, vcc_id, started_at, ended_at")
      .eq("id", id)
      .maybeSingle()
      .throwOnError();
    session = s.data;

    if (session) {
      const f = await sb
        .from("extracted_fields")
        .select("field_name, field_value, confidence, model, latency_ms, stt_lag_ms, debounce_ms, e2e_ms, extracted_at")
        .eq("session_id", id)
        .order("extracted_at", { ascending: true })
        .throwOnError();
      rows = f.data ?? [];

      const c = await sb.from("call_costs").select("usd_total").eq("session_id", id).maybeSingle().throwOnError();
      cost = c.data;
    }
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  if (error) {
    return (
      <div>
        <h1 className="text-lg font-semibold">Session</h1>
        <p className="mt-4 text-sm text-red-600">Supabase: {error}</p>
      </div>
    );
  }
  if (!session) notFound();

  const latest = new Map<string, Field>();
  for (const r of rows) latest.set(r.field_name, r);
  const sortedNums = (key: keyof Field) =>
    rows
      .map((r) => r[key])
      .filter((n): n is number => typeof n === "number")
      .sort((a, b) => a - b);
  const lat = sortedNums("latency_ms"); // LLM leg only
  const sttLag = sortedNums("stt_lag_ms");
  const debounce = sortedNums("debounce_ms");
  const e2e = sortedNums("e2e_ms");

  // agent-assist metric: how fast the copilot gets fields onto the VCC's screen
  const start = new Date(session.started_at).getTime();
  const times = rows.map((r) => new Date(r.extracted_at).getTime()).sort((a, b) => a - b);
  const secsFromStart = (t: number | undefined) =>
    t != null ? Math.round((t - start) / 1000) : null;
  const timeToFirst = secsFromStart(times[0]);
  const timeToAll = secsFromStart(times[times.length - 1]);

  return (
    <div>
      <h1 className="font-mono text-lg font-semibold">{session.room_name}</h1>
      <p className="mt-1 text-sm text-zinc-500">
        VCC {session.vcc_id} · started {new Date(session.started_at).toLocaleString()} ·{" "}
        {session.ended_at ? "ended" : "live"}
      </p>

      <section className="mt-6">
        <h2 className="text-sm font-semibold text-zinc-500">Extracted fields</h2>
        {latest.size === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">Nothing extracted yet.</p>
        ) : (
          <table className="mt-2 w-full text-sm">
            <tbody>
              {[...latest.values()].map((f) => (
                <tr key={f.field_name} className="border-t border-zinc-200 dark:border-zinc-800">
                  <td className="py-2 pr-4 text-zinc-500">{f.field_name}</td>
                  <td className="py-2 pr-4 font-medium">{f.field_value}</td>
                  <td className="py-2 pr-4 text-zinc-400">conf {f.confidence.toFixed(2)}</td>
                  <td className="py-2 text-zinc-400">{f.latency_ms != null ? `${f.latency_ms} ms` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Fields on screen" value={`${latest.size}/7`} />
        <Stat label="Time to first field" value={timeToFirst != null ? `${timeToFirst}s` : "—"} />
        <Stat label="Time to all fields" value={timeToAll != null ? `${timeToAll}s` : "—"} />
        <Stat label="Extraction p50" value={fmtMs(percentile(lat, 0.5))} />
        <Stat label="Extraction p95" value={fmtMs(percentile(lat, 0.95))} />
        <Stat label="Call cost" value={cost ? fmtUSD(Number(cost.usd_total)) : "—"} />
      </section>

      {e2e.length > 0 && (
        <section className="mt-4">
          <h2 className="text-sm font-semibold text-zinc-500">
            Speech → screen latency (per pass, p50 / p95)
          </h2>
          <div className="mt-2 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <Stat label="STT lag" value={`${fmtMs(percentile(sttLag, 0.5))} / ${fmtMs(percentile(sttLag, 0.95))}`} />
            <Stat label="Debounce" value={`${fmtMs(percentile(debounce, 0.5))} / ${fmtMs(percentile(debounce, 0.95))}`} />
            <Stat label="LLM" value={`${fmtMs(percentile(lat, 0.5))} / ${fmtMs(percentile(lat, 0.95))}`} />
            <Stat label="End to end" value={`${fmtMs(percentile(e2e, 0.5))} / ${fmtMs(percentile(e2e, 0.95))}`} />
          </div>
          <p className="mt-2 text-xs text-zinc-400">
            One value per extraction pass, replicated onto each field of that pass — not
            per-field independent samples. The browser fill adds a few ms on top (localhost).
          </p>
        </section>
      )}
    </div>
  );
}

function fmtMs(n: number | null): string {
  return n != null ? `${n} ms` : "—";
}
