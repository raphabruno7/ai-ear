import { getSupabaseAdmin } from "@/lib/supabase";

export const dynamic = "force-dynamic";

type Run = {
  run_id: string;
  model: string;
  kind: string;
  exact: boolean;
  phonetic_ok: boolean;
  wer: number;
  lev_norm: number;
  expected: string;
  got: string;
  sample_id: string;
};

export default async function EvalPage() {
  let rows: Run[] = [];
  let error: string | null = null;
  try {
    const { data } = await getSupabaseAdmin()
      .from("eval_runs")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(2000);
    rows = data ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const latestRun = rows[0]?.run_id;
  const run = rows.filter((r) => r.run_id === latestRun);
  const models = [...new Set(run.map((r) => r.model))];
  const kinds = ["name", "email"];

  const agg = (model: string, kind: string) => {
    const rs = run.filter((r) => r.model === model && r.kind === kind);
    if (!rs.length) return null;
    const n = rs.length;
    return {
      n,
      exact: rs.filter((r) => r.exact).length / n,
      phonetic: rs.filter((r) => r.phonetic_ok).length / n,
      wer: rs.reduce((a, r) => a + r.wer, 0) / n,
      lev: rs.reduce((a, r) => a + r.lev_norm, 0) / n,
    };
  };

  return (
    <div>
      <h1 className="text-lg font-semibold">Eval — phonetic name / email accuracy</h1>
      <p className="mt-1 text-sm text-zinc-500">
        {latestRun ? `Latest run ${latestRun}` : "No runs yet"} · Claude Haiku (Bedrock) vs Gemini 2.5 Flash
      </p>

      {error && <p className="mt-4 text-sm text-red-600">Supabase: {error}</p>}
      {!error && !latestRun && (
        <p className="mt-6 text-sm text-zinc-500">
          Run <code>cd eval &amp;&amp; python run.py</code> once AWS + GEMINI_API_KEY are set.
        </p>
      )}

      {latestRun && (
        <>
          <table className="mt-6 w-full text-sm">
            <thead className="text-left text-zinc-500">
              <tr>
                <th className="py-2 font-medium">Model</th>
                <th className="py-2 font-medium">Kind</th>
                <th className="py-2 font-medium">n</th>
                <th className="py-2 font-medium">Exact</th>
                <th className="py-2 font-medium">Phonetic</th>
                <th className="py-2 font-medium">WER</th>
                <th className="py-2 font-medium">Lev</th>
              </tr>
            </thead>
            <tbody>
              {models.flatMap((m) =>
                kinds.map((k) => {
                  const a = agg(m, k);
                  if (!a) return null;
                  return (
                    <tr key={`${m}-${k}`} className="border-t border-zinc-200 dark:border-zinc-800">
                      <td className="py-2">{m}</td>
                      <td className="py-2 text-zinc-500">{k}</td>
                      <td className="py-2 text-zinc-500">{a.n}</td>
                      <td className="py-2">{(a.exact * 100).toFixed(0)}%</td>
                      <td className="py-2">{(a.phonetic * 100).toFixed(0)}%</td>
                      <td className="py-2 text-zinc-500">{a.wer.toFixed(3)}</td>
                      <td className="py-2 text-zinc-500">{a.lev.toFixed(3)}</td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </table>

          <h2 className="mt-8 text-sm font-semibold text-zinc-500">Misses</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {run
              .filter((r) => !r.phonetic_ok)
              .map((r, i) => (
                <li key={i} className="text-zinc-600 dark:text-zinc-400">
                  <span className="text-zinc-400">{r.model}</span> {r.sample_id}: expected{" "}
                  <code>{r.expected}</code>, got <code>{r.got}</code>
                </li>
              ))}
          </ul>
        </>
      )}
    </div>
  );
}
