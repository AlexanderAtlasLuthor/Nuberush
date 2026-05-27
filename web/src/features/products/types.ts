// F2.8.0: products wire types.
//
// 1:1 mirror of the FastAPI products contract. Field names and casing
// match the JSON over the wire exactly (snake_case). Do NOT camelCase
// here; that mapping, if ever needed, belongs in the UI layer.
//
// Sources of truth (do not diverge without updating both sides):
//   - backend/app/schemas/products.py
//       ProductCreate, ProductUpdate, ProductRead,
//       ProductComplianceUpdate,
//       VariantCreate, VariantUpdate, VariantRead,
//       ProductComplianceAuditLogRead
//   - backend/app/db/models.py
//       ComplianceStatus, Product, ProductVariant,
//       ProductComplianceAuditLog
//   - backend/app/api/routes/products.py
//
// Type-design decisions (mirror the orders/inventory feature modules):
//   - Money fields are strings because the backend serializes Decimal
//     values as JSON strings to preserve precision.
//   - Datetime fields are strings from the backend wire (ISO-8601).
//   - UUIDs are strings.
//   - Read shapes mirror backend `*Read` Pydantic models exactly.
//   - Request bodies omit every server-managed or trust-boundary field
//     (id, timestamps, last_compliance_check, audit-only fields).
//   - No business logic, no derived flags, no sellable/permission
//     calculations live here. The UI consumes these shapes verbatim;
//     the backend is the source of truth for every rule.

// --------------------------------------------------------------------- //
// Enum
// --------------------------------------------------------------------- //

/**
 * Source: app.db.models.ComplianceStatus.
 *
 * Same wire values as the inventory module's `ComplianceStatus`. A
 * dedicated alias lives here so the products module is import-self-
 * contained; the inventory copy is preserved as a public-API alias
 * so existing imports keep working.
 */
export type ProductComplianceStatus = "allowed" | "restricted" | "banned";

/**
 * Source: app.db.models.ProductApprovalStatus.
 *
 * Catalog-curation gate for store-proposed products. Independent from
 * `ProductComplianceStatus`: a row needs BOTH gates plus is_active and
 * allowed_for_sale to be sellable. The frontend never derives the
 * status — the backend is authoritative.
 */
export type ProductApprovalStatus = "pending" | "approved" | "rejected";

// --------------------------------------------------------------------- //
// Read shapes
// --------------------------------------------------------------------- //

/**
 * Curated product subset surfaced inside enrichment responses
 * (inventory items, order line items, variant lookups).
 *
 * Mirrors the shape currently nested at `InventoryItem.variant.product`
 * and `OrderItemRead.variant.product`. Pricing, description,
 * hold_reason, jurisdiction and timestamps are intentionally absent —
 * those belong to the full `Product` shape returned by the dedicated
 * product-detail endpoint.
 *
 * Canonical declaration as of F2.8.7. The inventory module re-exports
 * this type so `VariantSummary.product` and the orders module's nested
 * variant payload share one TypeScript interface.
 */
export interface ProductSummary {
  id: string;
  name: string;
  brand: string | null;
  category: string;
  compliance_status: ProductComplianceStatus;
  allowed_for_sale: boolean;
  is_active: boolean;
}

/**
 * Response shape for any endpoint returning a single product.
 *
 * Mirrors backend `ProductRead`. Includes every field the wire carries,
 * including audit-relevant ones (`hold_reason`, `last_compliance_check`)
 * the UI may surface read-only.
 *
 * Field naming follows the wire exactly:
 *   - last_compliance_check  (NOT "last_checked_at")
 *   - allowed_for_sale       (NOT "sellable")
 */
export interface Product {
  id: string;
  name: string;
  brand: string | null;
  category: string;
  description: string | null;
  compliance_status: ProductComplianceStatus;
  allowed_for_sale: boolean;
  is_active: boolean;
  hold_reason: string | null;
  jurisdiction: string;
  /** ISO-8601 datetime string, or null if compliance has never been checked. */
  last_compliance_check: string | null;
  /** Catalog curation status — separate from `compliance_status`. */
  approval_status: ProductApprovalStatus;
  /** Store that proposed this product (null for admin-created rows). */
  proposed_by_store_id: string | null;
  /** User who proposed this product (null for admin-created rows). */
  proposed_by_user_id: string | null;
  /** Admin who last approved or rejected; null until reviewed. */
  reviewed_by_user_id: string | null;
  /** ISO-8601 timestamp of the last admin review; null until reviewed. */
  reviewed_at: string | null;
  /** Free-form reason set when `approval_status === "rejected"`. */
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
  /**
   * Primary product image metadata. `null` when none has been uploaded;
   * `undefined` only when the field is omitted by older callers/test
   * fixtures. The backend (F2.22.4) always emits the field as either
   * `null` or a populated object. F2.22.4 supports exactly one image
   * per product (`unique(product_id)` on `public.product_images`).
   * Mirrors backend `ProductRead.primary_image`.
   */
  primary_image?: ProductImage | null;
}

// --------------------------------------------------------------------- //
// Product image (F2.22.4)
// --------------------------------------------------------------------- //

/**
 * Response shape for the primary image on a product.
 *
 * Mirrors backend `ProductImageRead`. `public_url` is computed
 * server-side from the locked `product-images` bucket and the stored
 * `object_key`; it is `null` when the backend has no `SUPABASE_URL`
 * configured. The frontend renders `public_url` verbatim and never
 * derives its own URL from `object_key`.
 */
export interface ProductImage {
  id: string;
  product_id: string;
  object_key: string;
  public_url: string | null;
  uploaded_by_user_id: string;
  created_at: string;
  updated_at: string;
}

/**
 * Body for `POST /products/{id}/image-upload-url`.
 *
 * The object key itself is generated server-side; this payload only
 * declares what the admin is about to upload so the backend can
 * validate type/size before minting a signed URL. Mirrors backend
 * `ProductImageUploadUrlRequest`.
 */
export interface ProductImageUploadUrlRequest {
  filename: string;
  content_type: string;
  size_bytes: number;
}

/**
 * Response shape for `POST /products/{id}/image-upload-url`.
 *
 * Carries no secrets — the service-role key never leaves the backend.
 * Mirrors backend `ProductImageUploadUrlResponse`.
 */
export interface ProductImageUploadUrlResponse {
  bucket: string;
  object_key: string;
  signed_upload_url: string;
  expires_in_seconds: number;
}

/**
 * Body for `POST /products/{id}/images`. Echoes the bucket and key
 * the backend issued so it can revalidate before upserting the
 * `public.product_images` metadata row. Mirrors backend
 * `ProductImageConfirmRequest`.
 */
export interface ProductImageConfirmRequest {
  bucket: string;
  object_key: string;
}

/**
 * Response shape for any endpoint returning a single variant.
 *
 * Mirrors backend `VariantRead`. `price` is always present; `cost` is
 * nullable because the backend column is nullable. Both money fields
 * are Decimal-as-string on the wire.
 *
 * There is intentionally no `name` field: a variant is identified by
 * its SKU plus optional `flavor` / `size_label` / `thc_strength`
 * modifiers — the UI composes its own display label.
 */
export interface ProductVariant {
  id: string;
  product_id: string;
  sku: string;
  barcode: string | null;
  flavor: string | null;
  size_label: string | null;
  /** Backend constraint: > 0 when present. */
  unit_count: number | null;
  /** Backend constraint: > 0 when present. */
  puff_count: number | null;
  thc_strength: string | null;
  /** Decimal-as-string to preserve precision. NUMERIC(10, 2) on the DB. */
  price: string;
  /** Decimal-as-string. NUMERIC(10, 2) on the DB. */
  cost: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// --------------------------------------------------------------------- //
// Request bodies — products
// --------------------------------------------------------------------- //

/**
 * Body for `POST /products` (admin-only).
 *
 * Mirrors backend `ProductCreate`. Server-managed fields (id,
 * timestamps, hold_reason, last_compliance_check) are intentionally
 * absent.
 *
 * Backend defaults (applied when omitted):
 *   - jurisdiction        → "FL"
 *   - compliance_status   → "allowed"
 *   - allowed_for_sale    → true
 *
 * Backend invariant: a `compliance_status === "banned"` payload with
 * `allowed_for_sale === true` is rejected with 422. The frontend
 * mirrors this as a UX guard only — the server is the authoritative
 * validator.
 */
export interface ProductCreateRequest {
  /** Required. Trimmed, 1..200 chars. */
  name: string;
  /** Optional. Trimmed, 1..120 chars when provided. */
  brand?: string | null;
  /** Required. Trimmed, 1..100 chars. */
  category: string;
  /** Optional. Trimmed and rejected if whitespace-only when provided. */
  description?: string | null;
  /** Optional; backend defaults to "FL". Trimmed, 1..50 chars when provided. */
  jurisdiction?: string;
  /** Optional; backend defaults to "allowed". */
  compliance_status?: ProductComplianceStatus;
  /** Optional; backend defaults to true. Banned + true is rejected (422). */
  allowed_for_sale?: boolean;
}

/**
 * Body for `PATCH /products/{id}` (admin-only).
 *
 * Mirrors backend `ProductUpdate`. Compliance fields
 * (`compliance_status`, `allowed_for_sale`, `hold_reason`) are
 * intentionally absent — callers must use `ProductComplianceUpdateRequest`
 * so the audit log fires server-side.
 *
 * Every field is optional; sending an empty body is a no-op on the
 * server.
 */
export interface ProductUpdateRequest {
  /** Trimmed, 1..200 chars when provided. */
  name?: string | null;
  /** Trimmed, 1..120 chars when provided. */
  brand?: string | null;
  /** Trimmed, 1..100 chars when provided. */
  category?: string | null;
  /** Trimmed and rejected if whitespace-only when provided. */
  description?: string | null;
  /** Trimmed, 1..50 chars when provided. */
  jurisdiction?: string | null;
  is_active?: boolean | null;
}

/**
 * Body for `PATCH /products/{id}/compliance` (admin-only).
 *
 * Mirrors backend `ProductComplianceUpdate`. Every successful call
 * produces one row in `product_compliance_audit_logs` server-side; the
 * frontend never writes audit rows.
 *
 * Backend invariant: `compliance_status === "banned"` with
 * `allowed_for_sale === true` is rejected with 422. Same DB CHECK
 * constraint backs it (migration 5c3f52060b2f).
 */
export interface ProductComplianceUpdateRequest {
  compliance_status: ProductComplianceStatus;
  allowed_for_sale: boolean;
  /** Required. Trimmed, length >= 1. Captured verbatim into the audit log. */
  reason: string;
}

// --------------------------------------------------------------------- //
// Request bodies — variants
// --------------------------------------------------------------------- //

/**
 * Body for `POST /products/{product_id}/variants` (admin-only).
 *
 * Mirrors backend `VariantCreate`. The route additionally enforces that
 * `product_id` in the body matches the `{product_id}` path segment;
 * mismatches return 400.
 *
 * Money fields (`price`, `cost`) travel as strings so Decimal precision
 * is preserved. `unit_count` and `puff_count` must be > 0 when present.
 */
export interface VariantCreateRequest {
  product_id: string;
  /** Required. Trimmed, 1..100 chars. */
  sku: string;
  /** Optional. Trimmed, 1..100 chars when provided. */
  barcode?: string | null;
  /** Optional. Trimmed, 1..100 chars when provided. */
  flavor?: string | null;
  /** Optional. Trimmed, 1..50 chars when provided. */
  size_label?: string | null;
  /** Optional. Backend constraint: > 0 when provided. */
  unit_count?: number | null;
  /** Optional. Backend constraint: > 0 when provided. */
  puff_count?: number | null;
  /** Optional. Trimmed, 1..50 chars when provided. */
  thc_strength?: string | null;
  /** Required. Decimal-as-string. NUMERIC(10, 2), >= 0. */
  price: string;
  /** Optional. Decimal-as-string. NUMERIC(10, 2), >= 0 when provided. */
  cost?: string | null;
  /** Optional; backend defaults to true. */
  is_active?: boolean;
}

/**
 * Body for `PATCH /variants/{variant_id}` (admin-only).
 *
 * Mirrors backend `VariantUpdate`. `product_id` is immutable and is
 * intentionally absent. Every other field is optional; sending an
 * empty body is a no-op on the server.
 */
export interface VariantUpdateRequest {
  /** Trimmed, 1..100 chars when provided. */
  sku?: string | null;
  /** Trimmed, 1..100 chars when provided. */
  barcode?: string | null;
  /** Trimmed, 1..100 chars when provided. */
  flavor?: string | null;
  /** Trimmed, 1..50 chars when provided. */
  size_label?: string | null;
  /** Backend constraint: > 0 when provided. */
  unit_count?: number | null;
  /** Backend constraint: > 0 when provided. */
  puff_count?: number | null;
  /** Trimmed, 1..50 chars when provided. */
  thc_strength?: string | null;
  /** Decimal-as-string. NUMERIC(10, 2), >= 0 when provided. */
  price?: string | null;
  /** Decimal-as-string. NUMERIC(10, 2), >= 0 when provided. */
  cost?: string | null;
  is_active?: boolean | null;
}

// --------------------------------------------------------------------- //
// Audit log
// --------------------------------------------------------------------- //

/**
 * Response shape for an entry in the product compliance audit log.
 *
 * Mirrors backend `ProductComplianceAuditLogRead`. Append-only by
 * convention: rows are produced server-side by the compliance-update
 * service; clients only ever read them. No Create/Update counterpart.
 *
 * `changed_by_user_id` is nullable to cover system-initiated changes
 * (e.g. compliance sweeps) where no human actor is recorded.
 */
export interface ProductComplianceAuditLog {
  id: string;
  product_id: string;
  previous_compliance_status: ProductComplianceStatus;
  new_compliance_status: ProductComplianceStatus;
  previous_allowed_for_sale: boolean;
  new_allowed_for_sale: boolean;
  reason: string;
  changed_by_user_id: string | null;
  created_at: string;
}
