// F2.24.C6 — public store-application intake API layer.
//
// Pure async function over the backend public intake endpoint. Goes
// through `apiRequest` from `@/api` so error normalisation and FastAPI
// detail parsing stay centralised. Same hard rules as features/store/api:
//   - No fetch() directly.
//   - No React / TanStack Query imports.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic, no Supabase, no snake_case → camelCase mapping.
//
// URL alignment (verified against backend/app/api/routes/public.py and
// `app.include_router(public_router)` in app/main.py, prefix `/public`):
//
//   POST /public/store-applications   (unauthenticated; no Bearer needed)
//
// The request is unauthenticated by design — a public visitor has no
// Supabase session, so apiRequest attaches no Authorization header.

import { apiRequest } from "@/api";
import type {
  StoreApplicationSubmitRequest,
  StoreApplicationSubmitResponse,
} from "./types";

/**
 * POST /public/store-applications
 *
 * Submits a merchant store application. Returns the minimal
 * `{ id, status, message }` envelope. Throws ApiError on:
 *   - 409 (an active/pending/approved application already exists for the
 *          owner email)
 *   - 422 (invalid payload — the backend schema is `extra="forbid"`)
 *   - 0   (network failure)
 */
export function submitStoreApplication(
  payload: StoreApplicationSubmitRequest,
  signal?: AbortSignal,
): Promise<StoreApplicationSubmitResponse> {
  return apiRequest<StoreApplicationSubmitResponse>(
    "/public/store-applications",
    { method: "POST", body: payload, signal },
  );
}
