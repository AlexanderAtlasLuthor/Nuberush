// F2.20.3: admin-products API layer.
//
// One thin async function over `GET /admin/products`. Goes through
// `apiRequest` from `@/api` so error normalisation, Bearer attach and
// FastAPI detail parsing stay centralised.
//
// Hard rules baked in:
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports (that's the hook layer).
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No client-side compliance / sellable derivation.
//   - No store context. Product is global on the backend (F2.20.0 §4).
//
// URL alignment with backend/app/api/routes/admin_products.py +
// `app.include_router(admin_products_router)` in app/main.py (no
// extra prefix):
//
//   GET /admin/products?limit=&offset=&q=&compliance_status=&allowed_for_sale=&is_active=&category=
//
// Serialisation rules (locked by the F2.20.3 brief):
//   - undefined values are dropped from the query string.
//   - q and category are trimmed; empty / whitespace-only strings are
//     dropped so the backend doesn't see a wildcard `%%` match.
//   - offset=0 and limit=0 ARE serialised (limit=0 is intentionally
//     forwarded so the backend can return 422 — we never silently
//     swallow caller bugs here).
//   - `false` booleans ARE serialised (allowed_for_sale=false /
//     is_active=false are meaningful filters, not absence).
//   - compliance_status is forwarded as the enum literal.
//   - No `store_id` is accepted or serialised.

import { apiRequest } from "@/api";
import type {
  AdminProductsFilters,
  AdminProductsListResponse,
} from "./types";

function normalizeText(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function buildQueryString(filters: AdminProductsFilters): string {
  const query = new URLSearchParams();

  // limit and offset preserve 0 explicitly. `undefined` means "let the
  // server pick the default"; 0 means "the caller chose 0" and must
  // reach the server (which will 422 a limit of 0 — exactly the
  // boundary signal we want).
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

  if (filters.approval_status !== undefined) {
    query.set("approval_status", filters.approval_status);
  }

  // Booleans preserve `false`. We never want to collapse "explicit
  // false filter" into "no filter".
  if (filters.allowed_for_sale !== undefined) {
    query.set("allowed_for_sale", String(filters.allowed_for_sale));
  }
  if (filters.is_active !== undefined) {
    query.set("is_active", String(filters.is_active));
  }

  const category = normalizeText(filters.category);
  if (category !== undefined) {
    query.set("category", category);
  }

  return query.toString();
}

/**
 * GET /admin/products
 *
 * Returns the paginated `AdminProductsListResponse` envelope. Throws
 * ApiError on any non-2xx (401 when unauthenticated, 403 for non-admin,
 * 422 on out-of-range pagination params, 5xx on server failure).
 *
 * Every filter is optional. See the module docstring for the
 * serialisation rules — in particular that `limit=0`, `offset=0`, and
 * explicit `false` booleans are forwarded verbatim. Whitespace-only
 * `q` and `category` are dropped client-side.
 */
export function getAdminProducts(
  filters: AdminProductsFilters = {},
  signal?: AbortSignal,
): Promise<AdminProductsListResponse> {
  const qs = buildQueryString(filters);
  const path = `/admin/products${qs.length > 0 ? `?${qs}` : ""}`;
  return apiRequest<AdminProductsListResponse>(path, { signal });
}
