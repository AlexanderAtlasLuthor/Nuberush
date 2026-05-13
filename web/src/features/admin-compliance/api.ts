// F2.20.4: admin-compliance API layer.
//
// Two thin async functions over the backend admin-compliance endpoints
// (F2.20.2). Both go through `apiRequest` from `@/api` so error
// normalisation, Bearer attach and FastAPI detail parsing stay
// centralised.
//
// Hard rules baked in:
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports (that's the hook layer).
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No client-side compliance summary / queue derivation. The
//     backend is the source of truth for every count and every queue
//     row.
//   - No store context. Product is global on the backend (F2.20.0 §4).
//
// URL alignment with backend/app/api/routes/admin_compliance.py +
// `app.include_router(admin_compliance_router)` in app/main.py (no
// extra prefix):
//
//   GET /admin/compliance
//   GET /admin/compliance/products?limit=&offset=&q=&compliance_status=&allowed_for_sale=&is_active=
//
// Serialisation rules for the products endpoint (locked by F2.20.4):
//   - undefined values are dropped.
//   - q is trimmed; empty / whitespace-only is dropped so the
//     backend never sees a wildcard `%%` match.
//   - offset=0 and limit=0 ARE serialised (limit=0 reaches the
//     server which 422s it — we never silently swallow caller bugs).
//   - `false` booleans ARE serialised (allowed_for_sale=false and
//     is_active=false are meaningful filters).
//   - compliance_status is forwarded as the enum literal.
//   - No `store_id` is accepted or serialised.

import { apiRequest } from "@/api";
import type {
  AdminComplianceProductsFilters,
  AdminComplianceProductsListResponse,
  AdminComplianceSummary,
} from "./types";

// --------------------------------------------------------------------- //
// GET /admin/compliance — summary
// --------------------------------------------------------------------- //

/**
 * GET /admin/compliance
 *
 * Returns the full `AdminComplianceSummary` envelope (products counts,
 * recent-reviews tail, queue cardinalities). Backend-computed; the
 * frontend never derives summary values. Throws ApiError on any
 * non-2xx (401 unauthenticated, 403 non-admin, 5xx server failure).
 *
 * No query parameters: the endpoint is parameter-free by contract.
 */
export function getAdminComplianceSummary(
  signal?: AbortSignal,
): Promise<AdminComplianceSummary> {
  return apiRequest<AdminComplianceSummary>("/admin/compliance", {
    signal,
  });
}

// --------------------------------------------------------------------- //
// GET /admin/compliance/products — queue
// --------------------------------------------------------------------- //

function normalizeText(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function buildQueueQueryString(
  filters: AdminComplianceProductsFilters,
): string {
  const query = new URLSearchParams();

  // limit / offset preserve 0 explicitly. `undefined` means "server
  // default"; 0 means "the caller chose 0" and must reach the server.
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }

  const q = normalizeText(filters.q);
  if (q !== undefined) {
    query.set("q", q);
  }

  if (filters.compliance_status !== undefined) {
    query.set("compliance_status", filters.compliance_status);
  }

  // Booleans preserve `false`. We never collapse "explicit false
  // filter" into "no filter".
  if (filters.allowed_for_sale !== undefined) {
    query.set("allowed_for_sale", String(filters.allowed_for_sale));
  }
  if (filters.is_active !== undefined) {
    query.set("is_active", String(filters.is_active));
  }

  return query.toString();
}

/**
 * GET /admin/compliance/products
 *
 * Returns the paginated `AdminComplianceProductsListResponse` envelope.
 * Default queue rule (F2.20.0 §7): when neither `compliance_status`
 * nor `allowed_for_sale` is provided, the backend applies the shared
 * blocker predicate and returns only products that are blocked. Either
 * explicit filter disables the default so callers can intentionally
 * inspect allowed / allowed_for_sale rows.
 *
 * Throws ApiError on any non-2xx (401, 403, 422, 5xx). See the module
 * docstring for the serialisation rules — in particular that
 * `limit=0`, `offset=0`, and explicit `false` booleans are forwarded
 * verbatim. Whitespace-only `q` is dropped client-side.
 */
export function getAdminComplianceProducts(
  filters: AdminComplianceProductsFilters = {},
  signal?: AbortSignal,
): Promise<AdminComplianceProductsListResponse> {
  const qs = buildQueueQueryString(filters);
  const path = `/admin/compliance/products${qs.length > 0 ? `?${qs}` : ""}`;
  return apiRequest<AdminComplianceProductsListResponse>(path, { signal });
}
