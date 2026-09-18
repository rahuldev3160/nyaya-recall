import { createClient } from "@supabase/supabase-js";

// TODO: fill in when Supabase project created (supabase.com → Settings → API)
// Falls back to a placeholder so createClient() doesn't throw when unconfigured —
// AuthGuard already skips all auth checks in that case (single-user / local dev mode).
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://placeholder.supabase.co";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "placeholder-anon-key";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
