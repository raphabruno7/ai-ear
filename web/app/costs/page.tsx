import { getSupabaseAdmin } from "@/lib/supabase";
import { fmtUSD } from "@/lib/stats";
import { Stat } from "@/components/stat";

export const dynamic = "force-dynamic";

type Cost = {
  session_id: string;
  stt_seconds: number;
  llm_input_tokens: number;
  llm_output_tokens: number;
  usd_stt: number;
  usd_llm: number;
  usd_total: number;
};

export default async function CostsPage() {
  let rows: Cost[] = [];
  let error: string | null = null;
  try {
    const { data } = await getSupabaseAdmin().from("call_costs").select("*").limit(1000).throwOnError();
    rows = data ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const n = rows.length;
  const sum = (f: (c: Cost) => number) => rows.reduce((a, c) => a + Number(f(c)), 0);
  const avgTotal = n ? sum((c) => c.usd_total) / n : 0;
  const avgStt = n ? sum((c) => c.usd_stt) / n : 0;
  const avgLlm = n ? sum((c) => c.usd_llm) / n : 0;

  return (
    <div>
      <h1 className="text-lg font-semibold">Per-call cost</h1>
      <p className="mt-1 text-sm text-zinc-500">
        AWS Transcribe streaming + Bedrock Claude Haiku. Prices: <code>listener/pricing.py</code>.
      </p>

      {error && <p className="mt-4 text-sm text-red-600">Supabase: {error}</p>}
      {!error && n === 0 && (
        <p className="mt-6 text-sm text-zinc-500">No calls costed yet — run the listener.</p>
      )}

      {n > 0 && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <Stat label="Calls" value={String(n)} />
            <Stat label="Avg / call" value={fmtUSD(avgTotal)} />
            <Stat label="Avg STT" value={fmtUSD(avgStt)} />
            <Stat label="Avg LLM" value={fmtUSD(avgLlm)} />
          </div>
          <p className="mt-4 text-sm text-zinc-500">
            Projection at 1,000 calls/month: <strong>{fmtUSD(avgTotal * 1000)}</strong>
          </p>

          <table className="mt-6 w-full text-sm">
            <thead className="text-left text-zinc-500">
              <tr>
                <th className="py-2 font-medium">Session</th>
                <th className="py-2 font-medium">STT s</th>
                <th className="py-2 font-medium">Tokens in/out</th>
                <th className="py-2 font-medium">USD</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.session_id} className="border-t border-zinc-200 dark:border-zinc-800">
                  <td className="py-2 font-mono text-xs text-zinc-500">{c.session_id.slice(0, 8)}</td>
                  <td className="py-2 text-zinc-500">{c.stt_seconds}</td>
                  <td className="py-2 text-zinc-500">
                    {c.llm_input_tokens} / {c.llm_output_tokens}
                  </td>
                  <td className="py-2">{fmtUSD(Number(c.usd_total))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
