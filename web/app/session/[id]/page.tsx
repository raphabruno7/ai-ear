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
        .select("field_name, field_value, confidence, model, latency_ms, extracted_at")
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
  const lat = rows
    .map((r) => r.latency_ms)
    .filter((n): n is number => n != null)
    .sort((a, b) => a - b);

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

      <section className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
        <Stat label="Field updates" value={String(rows.length)} />
        <Stat label="Extraction p50" value={fmtMs(percentile(lat, 0.5))} />
        <Stat label="Extraction p95" value={fmtMs(percentile(lat, 0.95))} />
        <Stat label="Call cost" value={cost ? fmtUSD(Number(cost.usd_total)) : "—"} />
      </section>
    </div>
  );
}

function fmtMs(n: number | null): string {
  return n != null ? `${n} ms` : "—";
}
