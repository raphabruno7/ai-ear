import Link from "next/link";
import { getSupabaseAdmin } from "@/lib/supabase";

export const dynamic = "force-dynamic";

type Session = {
  id: string;
  room_name: string;
  vcc_id: string;
  started_at: string;
  ended_at: string | null;
};

export default async function SessionsPage() {
  let sessions: Session[] = [];
  let error: string | null = null;
  try {
    const { data } = await getSupabaseAdmin()
      .from("sessions")
      .select("id, room_name, vcc_id, started_at, ended_at")
      .order("started_at", { ascending: false })
      .limit(50);
    sessions = data ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <div>
      <h1 className="text-lg font-semibold">Sessions</h1>
      <p className="mt-1 text-sm text-zinc-500">Calls the copilot has listened to.</p>

      {error && <p className="mt-4 text-sm text-red-600">Supabase: {error}</p>}

      {!error && sessions.length === 0 && (
        <p className="mt-6 text-sm text-zinc-500">
          No sessions yet. Run the listener: <code>python agent.py --room demo-1</code>
        </p>
      )}

      {sessions.length > 0 && (
        <table className="mt-6 w-full text-sm">
          <thead className="text-left text-zinc-500">
            <tr>
              <th className="py-2 font-medium">Room</th>
              <th className="py-2 font-medium">VCC</th>
              <th className="py-2 font-medium">Started</th>
              <th className="py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="py-2">
                  <Link href={`/session/${s.id}`} className="text-blue-600 hover:underline">
                    {s.room_name}
                  </Link>
                </td>
                <td className="py-2 text-zinc-500">{s.vcc_id}</td>
                <td className="py-2 text-zinc-500">{new Date(s.started_at).toLocaleString()}</td>
                <td className="py-2 text-zinc-500">{s.ended_at ? "ended" : "live"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
