import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Cheap liveness: Supabase reachable + required env present. Deeper checks
// (AWS STS, Transcribe, SES) live in listener/healthcheck.py so this route
// never spends money or burns a model quota.
export async function GET() {
  const checks: Record<string, string> = {};

  try {
    await getSupabaseAdmin().from("sessions").select("id", { count: "exact", head: true }).throwOnError();
    checks.supabase = "ok";
  } catch (e) {
    checks.supabase = `fail: ${e instanceof Error ? e.message : e}`;
  }

  for (const [k, v] of Object.entries({
    aws: process.env.AWS_ACCESS_KEY_ID,
    livekit: process.env.LIVEKIT_URL,
    gemini: process.env.GEMINI_API_KEY,
    ses: process.env.SES_FROM_EMAIL,
  })) {
    checks[k] = v ? "configured" : "MISSING";
  }

  const ok = Object.values(checks).every((s) => s === "ok" || s === "configured");
  return NextResponse.json({ ok, checks }, { status: ok ? 200 : 503 });
}
