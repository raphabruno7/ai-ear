import { createClient, SupabaseClient } from "@supabase/supabase-js";

// Lazy singletons — never instantiate at module level (breaks the build when
// env vars are absent at collect-page-data time). Cloned from voice-demo.

function getUrl() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (!url) throw new Error("NEXT_PUBLIC_SUPABASE_URL is not set");
  return url;
}

let _admin: SupabaseClient | null = null;
export function getSupabaseAdmin() {
  if (!_admin) {
    _admin = createClient(getUrl(), process.env.SUPABASE_SERVICE_ROLE_KEY!);
  }
  return _admin;
}
