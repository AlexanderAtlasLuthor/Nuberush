// F2.22.2.G: auth API — Supabase Auth for credentials, FastAPI for the
// app user.
//
// Split of responsibilities:
//   - Supabase Auth owns identity + credentials. `login` calls
//     `signInWithPassword`; `logout` calls `signOut`. The legacy
//     `POST /auth/login` endpoint no longer exists.
//   - FastAPI still owns the app user. `getMe` calls `GET /auth/me`
//     through `apiRequest` (which attaches the Supabase access token as
//     a Bearer header). role / store_id / is_active come from
//     `public.users`, never from a Supabase token claim.
//
// No `supabase.from()` / `supabase.rpc()`: this module touches Supabase
// only for auth.

import { apiRequest } from "@/api";
import { supabase } from "@/lib/supabase";
import type { AuthUser, LoginCredentials } from "./types";

/**
 * Sign in with email + password via Supabase Auth, then resolve the app
 * user from FastAPI `GET /auth/me`.
 *
 * Throws an `Error` with a user-readable message when Supabase rejects
 * the credentials; `getApiErrorMessage` surfaces it in the login UI.
 */
export async function login(
  credentials: LoginCredentials,
): Promise<AuthUser> {
  const { error } = await supabase.auth.signInWithPassword({
    email: credentials.email,
    password: credentials.password,
  });
  if (error) {
    throw new Error(error.message);
  }
  // Identity established; the app user (role/store/is_active) is the
  // FastAPI source of truth.
  return getMe();
}

/** End the Supabase session. */
export async function logout(): Promise<void> {
  await supabase.auth.signOut();
}

/** Fetch the current app user from FastAPI. Bearer token attached by apiRequest. */
export function getMe(signal?: AbortSignal): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/me", { method: "GET", signal });
}
