// F2.22.2.G: Supabase client singleton — the frontend's identity layer.
//
// Scope of what Supabase does in NubeRush:
//   - Authentication ONLY. signInWithPassword / signOut / session
//     persistence + token refresh.
//   - It is NEVER used to read or write business data. Orders,
//     inventory, products, stores, users — every business read/write
//     goes through `apiRequest` → FastAPI. There is no `supabase.from()`
//     / `supabase.rpc()` anywhere in this app, and there must not be.
//
// The access token from this session is attached as
// `Authorization: Bearer <token>` by `src/api/client.ts`; FastAPI
// verifies it against the Supabase JWKS. role / store_id / is_active
// still come from `public.users` via GET /auth/me — never from a token
// claim.
//
// Env contract (build-time, Vite). Only the public anon key belongs in
// the frontend; the service-role key is server-only and must never
// appear here.
//   VITE_SUPABASE_URL       — project URL
//   VITE_SUPABASE_ANON_KEY  — public anonymous key

import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as
  | string
  | undefined;

if (!supabaseUrl || !supabaseAnonKey) {
  // Fail loud and early. A silently mis-configured client would surface
  // much later as confusing 401s. Tests set both vars in
  // `src/test/setup.ts`; dev/prod builds must provide a real project.
  throw new Error(
    "Supabase is not configured. Set VITE_SUPABASE_URL and " +
      "VITE_SUPABASE_ANON_KEY in the environment (see web/.env.example).",
  );
}

// Single shared client. `persistSession` + `autoRefreshToken` keep the
// session alive across reloads so the app no longer loses auth on a
// hard refresh. `detectSessionInUrl` is on (F2.25.4) so Supabase auth
// links — owner activation / password setup that land on /auth/callback —
// are consumed automatically. It only acts when the URL carries auth
// params, so password sign-in (no URL params) is unaffected.
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
