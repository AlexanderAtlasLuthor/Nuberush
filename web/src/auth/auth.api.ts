// F2.3: thin wrappers over the FastAPI auth endpoints.
//
// All HTTP goes through `apiRequest` from src/api so error normalisation,
// header/body building and Bearer-token attachment stay centralised. No
// fetch, no axios, no React, no UI imports here.
//
// Endpoint coverage matches what the backend actually exposes today:
//   POST /auth/login   — returns { access_token, token_type }
//   GET  /auth/me      — returns UserRead (Bearer required)
//
// There is intentionally NO logout(). Backend JWT is stateless: the
// server has no session record to invalidate, so logout is purely
// client-side (clearAccessToken() + drop user from React state). When
// token revocation lands on the server (Redis denylist or DB flag), add
// a logout() here that POSTs the revocation and only THEN clears local
// state.

import { apiRequest } from "@/api";
import type { AuthUser, LoginCredentials, LoginResponse } from "./types";

export function login(credentials: LoginCredentials): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: credentials,
  });
}

export function getMe(signal?: AbortSignal): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/me", { method: "GET", signal });
}
