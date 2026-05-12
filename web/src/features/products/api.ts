// F2.8.1: products API layer.
//
// Pure async functions over the backend products endpoints. Every call
// goes through `apiRequest` from `@/api` so error normalisation, Bearer
// attach and FastAPI detail parsing stay centralised.
//
// Hard rules baked in:
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the next subphase.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: no client-side compliance / sellable derivation,
//     no permission checks. The backend is the source of truth.
//
// URL alignment (verified against backend/app/api/routes/products.py and
// the bare `app.include_router(products_router)` +
// `app.include_router(variants_router)` in app/main.py — no extra
// prefix):
//
//   GET    /products                          (list, filterable)
//   GET    /products/{product_id}             (read one)
//   GET    /products/{product_id}/variants    (list variants)
//   GET    /products/{product_id}/sellable    (compliance + active gate)
//   POST   /products                          (admin)
//   PATCH  /products/{product_id}             (admin, non-compliance fields)
//   DELETE /products/{product_id}?hard=...    (admin; soft by default)
//   POST   /products/{product_id}/variants    (admin)
//   PATCH  /variants/{variant_id}             (admin; mounted under /variants)
//   DELETE /variants/{variant_id}?hard=...    (admin; soft by default)
//   PATCH  /products/{product_id}/compliance  (admin; writes audit row)
//   GET    /products/{product_id}/compliance-audit  (admin)
//
// Variant detail/update/delete deliberately live at /variants/{variant_id}
// instead of nested under the parent product, because a variant has its
// own globally-unique id and routing through the parent would force
// callers (inventory, orders) to know the parent_id when they already
// have just the variant id.
//
// `GET /products` returns a BARE `list[ProductRead]` on the wire, NOT
// the `PaginatedResponse<T>` envelope used by inventory/orders. We
// preserve that asymmetry here — wrapping it would invent a `total` the
// backend never sent. If pagination is added server-side later, this
// shape changes in lockstep.

import { apiRequest } from "@/api";
import type {
  Product,
  ProductComplianceAuditLog,
  ProductComplianceStatus,
  ProductComplianceUpdateRequest,
  ProductCreateRequest,
  ProductUpdateRequest,
  ProductVariant,
  VariantCreateRequest,
  VariantUpdateRequest,
} from "./types";

// --------------------------------------------------------------------- //
// List
// --------------------------------------------------------------------- //

export interface ProductListFilters {
  /** If true, only `is_active === true` products are returned. */
  only_active?: boolean;
  /**
   * If true, only sellable products (active AND allowed_for_sale AND
   * compliance_status !== "banned") are returned. Server-evaluated; the
   * frontend never re-derives this rule.
   */
  only_sellable?: boolean;
  /** Optional compliance filter. */
  compliance_status?: ProductComplianceStatus;
  /** Optional category filter. Backend bound: max 100 chars. */
  category?: string;
  /** Page size. Backend bounds: 1 <= limit <= 500 (default 100 server-side). */
  limit?: number;
  /** Zero-based offset. Backend bound: offset >= 0 (default 0 server-side). */
  offset?: number;
}

/**
 * GET /products
 *
 * Returns a bare `Product[]` — the backend route's `response_model` is
 * `list[ProductRead]`, NOT a paginated envelope. Throws ApiError on any
 * non-2xx (401, 422 on bad params, 5xx).
 *
 * All filter params are optional; omitting them lets the backend apply
 * its own defaults (`only_active=false`, `only_sellable=false`,
 * `limit=100`, `offset=0`, no category / compliance filter).
 */
export function listProducts(
  filters: ProductListFilters = {},
  signal?: AbortSignal,
): Promise<Product[]> {
  const query = new URLSearchParams();
  if (filters.only_active !== undefined) {
    query.set("only_active", String(filters.only_active));
  }
  if (filters.only_sellable !== undefined) {
    query.set("only_sellable", String(filters.only_sellable));
  }
  if (filters.compliance_status !== undefined) {
    query.set("compliance_status", filters.compliance_status);
  }
  if (filters.category !== undefined) {
    query.set("category", filters.category);
  }
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }
  const qs = query.toString();
  const path = `/products${qs.length > 0 ? `?${qs}` : ""}`;
  return apiRequest<Product[]>(path, { signal });
}

// --------------------------------------------------------------------- //
// Read single
// --------------------------------------------------------------------- //

export interface GetProductParams {
  /** Product UUID. */
  productId: string;
}

/**
 * GET /products/{product_id}
 *
 * Returns the full `Product`. Throws ApiError 404 if the product does
 * not exist.
 */
export function getProduct(
  params: GetProductParams,
  signal?: AbortSignal,
): Promise<Product> {
  const path = `/products/${encodeURIComponent(params.productId)}`;
  return apiRequest<Product>(path, { signal });
}

// --------------------------------------------------------------------- //
// Variants — list for a product
// --------------------------------------------------------------------- //

export interface GetProductVariantsParams {
  /** Product UUID. Goes into the URL path. */
  productId: string;
  /** Optional. If true, only `is_active === true` variants are returned. */
  only_active?: boolean;
}

/**
 * GET /products/{product_id}/variants
 *
 * Returns a bare `ProductVariant[]`. Backend response_model is
 * `list[VariantRead]`, no envelope. Throws ApiError 404 if the parent
 * product does not exist.
 */
export function getProductVariants(
  params: GetProductVariantsParams,
  signal?: AbortSignal,
): Promise<ProductVariant[]> {
  const query = new URLSearchParams();
  if (params.only_active !== undefined) {
    query.set("only_active", String(params.only_active));
  }
  const qs = query.toString();
  const path =
    `/products/${encodeURIComponent(params.productId)}/variants` +
    (qs.length > 0 ? `?${qs}` : "");
  return apiRequest<ProductVariant[]>(path, { signal });
}

// --------------------------------------------------------------------- //
// Sellable check
// --------------------------------------------------------------------- //

export interface GetProductSellableParams {
  /** Product UUID. */
  productId: string;
}

/**
 * Backend response shape for `GET /products/{product_id}/sellable`.
 *
 * Successful response is always `{ product_id, sellable: true }` — the
 * route only ever returns 200 when the product passes
 * `assert_product_sellable`. A non-sellable product comes back as 422
 * with the failing flags inside `ApiError.details`; callers handle that
 * via the standard error pathway, no client-side derivation here.
 */
export interface ProductSellableResponse {
  product_id: string;
  sellable: true;
}

/**
 * GET /products/{product_id}/sellable
 *
 * Throws ApiError 404 if the product does not exist; throws ApiError
 * 422 with the failing flags in `details` if the product exists but is
 * not sellable. Callers MUST inspect ApiError; this function never
 * resolves to `sellable: false` because the backend never sends that.
 */
export function getProductSellable(
  params: GetProductSellableParams,
  signal?: AbortSignal,
): Promise<ProductSellableResponse> {
  const path = `/products/${encodeURIComponent(params.productId)}/sellable`;
  return apiRequest<ProductSellableResponse>(path, { signal });
}

// --------------------------------------------------------------------- //
// Create product (admin)
// --------------------------------------------------------------------- //

export interface CreateProductParams {
  /**
   * Validated payload. The backend enforces the banned + allowed_for_sale
   * invariant (422 on violation); the frontend mirrors this only as a
   * UX guard, never as authoritative validation.
   */
  body: ProductCreateRequest;
}

/**
 * POST /products
 *
 * Admin-only. Returns the persisted `Product` (201 Created) including
 * server-generated id and timestamps.
 */
export function createProduct(
  params: CreateProductParams,
  signal?: AbortSignal,
): Promise<Product> {
  return apiRequest<Product>("/products", {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Update product (admin) — non-compliance fields only
// --------------------------------------------------------------------- //

export interface UpdateProductParams {
  /** Product UUID. */
  productId: string;
  /**
   * Validated payload. Compliance fields are intentionally absent from
   * `ProductUpdateRequest` — use `updateProductCompliance` so the audit
   * log fires server-side.
   */
  body: ProductUpdateRequest;
}

/**
 * PATCH /products/{product_id}
 *
 * Admin-only. Returns the updated `Product`. Sending an empty body is
 * a server-side no-op.
 */
export function updateProduct(
  params: UpdateProductParams,
  signal?: AbortSignal,
): Promise<Product> {
  const path = `/products/${encodeURIComponent(params.productId)}`;
  return apiRequest<Product>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Delete product (admin)
// --------------------------------------------------------------------- //

export interface DeleteProductParams {
  /** Product UUID. */
  productId: string;
  /**
   * If true, hard-deletes the row (and cascades). Default false →
   * soft-delete: sets `is_active = false` while preserving FK history.
   * Mirrors the backend `?hard=` query param.
   */
  hard?: boolean;
}

/**
 * DELETE /products/{product_id}?hard=...
 *
 * Admin-only. Returns 204 No Content; the client wrapper resolves to
 * `void`. Default behaviour is a soft delete (deactivation) so audit /
 * historical references stay intact.
 */
export function deleteProduct(
  params: DeleteProductParams,
  signal?: AbortSignal,
): Promise<void> {
  const query = new URLSearchParams();
  if (params.hard !== undefined) {
    query.set("hard", String(params.hard));
  }
  const qs = query.toString();
  const path =
    `/products/${encodeURIComponent(params.productId)}` +
    (qs.length > 0 ? `?${qs}` : "");
  return apiRequest<void>(path, { method: "DELETE", signal });
}

// --------------------------------------------------------------------- //
// Create variant (admin)
// --------------------------------------------------------------------- //

export interface CreateProductVariantParams {
  /** Product UUID — goes into the URL path AND must match `body.product_id`. */
  productId: string;
  /**
   * Validated payload. Backend enforces `body.product_id ===
   * {product_id path}`; mismatch returns 400.
   */
  body: VariantCreateRequest;
}

/**
 * POST /products/{product_id}/variants
 *
 * Admin-only. Returns the persisted `ProductVariant` (201 Created)
 * including server-generated id and timestamps.
 */
export function createProductVariant(
  params: CreateProductVariantParams,
  signal?: AbortSignal,
): Promise<ProductVariant> {
  const path = `/products/${encodeURIComponent(params.productId)}/variants`;
  return apiRequest<ProductVariant>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Update variant (admin)
// --------------------------------------------------------------------- //

export interface UpdateProductVariantParams {
  /**
   * Variant UUID. Mounted under `/variants/{variant_id}` (NOT under the
   * parent product) because a variant has its own globally-unique id.
   */
  variantId: string;
  /**
   * Validated payload. `product_id` is immutable and intentionally
   * absent from `VariantUpdateRequest`.
   */
  body: VariantUpdateRequest;
}

/**
 * PATCH /variants/{variant_id}
 *
 * Admin-only. Returns the updated `ProductVariant`. Sending an empty
 * body is a server-side no-op.
 */
export function updateProductVariant(
  params: UpdateProductVariantParams,
  signal?: AbortSignal,
): Promise<ProductVariant> {
  const path = `/variants/${encodeURIComponent(params.variantId)}`;
  return apiRequest<ProductVariant>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Delete variant (admin)
// --------------------------------------------------------------------- //

export interface DeleteVariantParams {
  /** Variant UUID. */
  variantId: string;
  /**
   * If true, hard-deletes the row. Default false → soft-delete: sets
   * `is_active = false`. Mirrors the backend `?hard=` query param.
   */
  hard?: boolean;
}

/**
 * DELETE /variants/{variant_id}?hard=...
 *
 * Admin-only. Returns 204 No Content; the client wrapper resolves to
 * `void`. Default is a soft delete so inventory / order line FK history
 * stays intact.
 */
export function deleteProductVariant(
  params: DeleteVariantParams,
  signal?: AbortSignal,
): Promise<void> {
  const query = new URLSearchParams();
  if (params.hard !== undefined) {
    query.set("hard", String(params.hard));
  }
  const qs = query.toString();
  const path =
    `/variants/${encodeURIComponent(params.variantId)}` +
    (qs.length > 0 ? `?${qs}` : "");
  return apiRequest<void>(path, { method: "DELETE", signal });
}

// --------------------------------------------------------------------- //
// Compliance update (admin) — writes one audit row server-side
// --------------------------------------------------------------------- //

export interface UpdateProductComplianceParams {
  /** Product UUID. */
  productId: string;
  /**
   * Validated payload. Backend enforces banned + allowed_for_sale = true
   * → 422; same DB CHECK constraint backs it.
   */
  body: ProductComplianceUpdateRequest;
}

/**
 * PATCH /products/{product_id}/compliance
 *
 * Admin-only. Returns the updated `Product`. Every successful call
 * writes exactly one row in `product_compliance_audit_logs` (server-
 * side, atomic with the product update). The frontend never writes
 * audit rows.
 */
export function updateProductCompliance(
  params: UpdateProductComplianceParams,
  signal?: AbortSignal,
): Promise<Product> {
  const path = `/products/${encodeURIComponent(params.productId)}/compliance`;
  return apiRequest<Product>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Compliance audit log (admin)
// --------------------------------------------------------------------- //

export interface GetProductComplianceAuditParams {
  /** Product UUID. */
  productId: string;
}

/**
 * GET /products/{product_id}/compliance-audit
 *
 * Admin-only. Returns the audit trail for a product as a bare
 * `ProductComplianceAuditLog[]` (no pagination envelope). Ordered by
 * `created_at DESC` server-side. Throws ApiError 404 if the product
 * does not exist.
 */
export function getProductComplianceAudit(
  params: GetProductComplianceAuditParams,
  signal?: AbortSignal,
): Promise<ProductComplianceAuditLog[]> {
  const path =
    `/products/${encodeURIComponent(params.productId)}/compliance-audit`;
  return apiRequest<ProductComplianceAuditLog[]>(path, { signal });
}
