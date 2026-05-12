// F2.18.2A: admin stores (platform-wide) wire types.
//
// `features/stores/` (plural) — admin global stores management
// (list / create / lifecycle / detail).
// `features/store/` (singular) — own-store settings page (kept separate;
// already exists from F2.14).
//
// Two namespaces, ONE source of truth for shared types:
// `StoreProfile` (the wire mirror of backend `StoreRead`) and
// `StoreUpdateRequest` live in `@/features/store/types` and are
// re-exported here so the admin module can reference them without
// declaring a parallel type. Re-exporting (not redeclaring) keeps the
// two features in lockstep with the backend schema — see the
// F2.18.0/F2.18.1A contract lock §5.1.
//
// Sources of truth (do not diverge without updating both sides):
//   - backend/app/schemas/stores.py
//       StoreRead, StoreUpdate, StoreCreate, StoreListResponse
//   - backend/app/api/routes/stores.py
//       GET /stores, POST /stores,
//       GET /stores/{store_id}, PATCH /stores/{store_id},
//       POST /stores/{store_id}/deactivate,
//       POST /stores/{store_id}/reactivate
//   - backend/app/services/stores.py
//       list_stores, create_store, deactivate_store, reactivate_store
//
// Type-design decisions (mirror features/users / features/store):
//   - Datetime fields are strings from the wire (ISO-8601).
//   - UUIDs are strings.
//   - Snake_case wire contract — no camelCase here.
//   - No business logic, no permission flags. Backend matrix is
//     authoritative for who can list / create / deactivate / reactivate;
//     the frontend forwards the request and surfaces the resulting 403.

import type {
  StoreProfile,
  StoreUpdateRequest,
} from "@/features/store/types";

// Re-exported so admin-feature consumers can import store types from a
// single place — `@/features/stores` — without reaching across into
// the singular own-store module.
export type { StoreProfile, StoreUpdateRequest };

/**
 * Filter set for `GET /stores` (and the matching cache key).
 * Every field is optional. Backend `list_stores` is admin-only —
 * non-admins get 403 before any filter is read.
 *
 * Field bounds (backend authoritative, F2.17.2):
 *   - `limit`: 1..100, default 25 server-side.
 *   - `offset`: >= 0, default 0 server-side.
 *   - `is_active`: optional bool. Explicit `false` means
 *     "deactivated stores only" — a meaningful filter, NOT equivalent
 *     to omitting the field.
 *   - `q`: ILIKE on name and code (case-insensitive, trimmed,
 *     whitespace-only collapses to none server-side).
 */
export interface StoreListFilters {
  limit?: number;
  offset?: number;
  is_active?: boolean;
  q?: string;
}

/**
 * Paginated envelope returned by `GET /stores`.
 * Mirrors backend `StoreListResponse` exactly.
 */
export interface StoreListResponse {
  items: StoreProfile[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Body accepted by `POST /stores` (admin-only).
 *
 * Mirrors backend `StoreCreate` (with `extra="forbid"`). The backend
 * defaults `timezone` to "America/New_York" when omitted; only `name`
 * and `code` are strictly required client-side.
 *
 * Reminders (backend authoritative; these notes exist so the UI can
 * mirror the constraints as a UX guard, not as authoritative checks):
 *   - `name`: trimmed, non-empty.
 *   - `code`: trimmed, non-empty. Duplicate codes are surfaced as 422.
 *   - `timezone`: optional, trimmed, non-empty when provided.
 *
 * Forbidden fields (would 422 server-side via `extra="forbid"`):
 *   - id / is_active / created_at / updated_at.
 */
export interface StoreCreateRequest {
  name: string;
  code: string;
  timezone?: string;
}
