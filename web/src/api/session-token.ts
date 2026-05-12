// F2.2: minimal in-memory access-token holder.
//
// This is NOT auth. The api/client only reads from `getAccessToken()`
// to attach an `Authorization: Bearer <token>` header when one is
// present. Storage is intentionally in-memory (process-local) so a
// reload always returns null — the prototype must NOT pretend to keep a
// session around.
//
// F2.3 will replace this with the real AuthProvider/session flow,
// including secure storage decisions, refresh handling and logout
// cleanup. Until then, treat any caller of `setAccessToken` as
// experimental.

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}
