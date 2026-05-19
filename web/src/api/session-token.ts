// F2.22.2.G: session-token adapter — now backed by the Supabase session.
//
// Before F2.22.2.G this module was an in-memory holder fed by a legacy
// `POST /auth/login` token. That endpoint is gone. The access token now
// lives in the Supabase session (persisted + auto-refreshed by the
// Supabase client), and this module is a thin read/clear façade over it
// so `src/api/client.ts` does not import the Supabase client directly.
//
// The token is NOT cached in module memory: every call reads the live
// session so a refreshed token is always picked up.

import { supabase } from "@/lib/supabase";

/**
 * Current Supabase access token, or `null` when there is no session.
 *
 * Async because the token is read from the Supabase session. Callers
 * (only `apiRequest`) await it before attaching the Bearer header.
 */
export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/**
 * End the Supabase session. Used by the logout flow; after this resolves
 * `getAccessToken()` returns `null` and `apiRequest` sends no Bearer.
 */
export async function clearAccessToken(): Promise<void> {
  await supabase.auth.signOut();
}
