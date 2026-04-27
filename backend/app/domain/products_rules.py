"""NubeRush — Products domain rules (FROZEN for S3).

This module contains **no executable logic**. It is the single source of
truth for the design decisions that govern the products / variants /
compliance / catalog surface and how it interacts with tenancy.

Any service, router or test working on products MUST be consistent with
the rules below. When the rules change, this file changes first and the
implementation follows; never the other way around.

These decisions are derived from:
  - Phase 0 (foundation) — business rules and tenancy model.
  - Session 2 (auth/RBAC/tenancy) — backend-only authority over roles
    and store_id.
  - S3 Subfase 1 — explicit freezing of products-module decisions.


1. Catalog scope
----------------
- Products are GLOBAL across all stores. There is no `store_id` on the
  `products` table.
- Product variants are GLOBAL. There is no `store_id` on the
  `product_variants` table.
- Inventory is STORE-SCOPED. `inventory_items` carries `store_id` and
  every quantity, reservation and reorder threshold is per (store,
  variant). Two stores can carry the same variant with independent
  stock.
- Orders are STORE-SCOPED. `orders` carries `store_id` and order items
  reference global variants.
- Inventory logs are STORE-SCOPED. Every movement is attributed to a
  store.


2. RBAC for the catalog
-----------------------
The catalog is global, so writes must be administered globally. The
matrix below is enforced in routers via the existing `require_*`
aliases from `app.api.deps`.

  - Create product .................. admin only
  - Update product (any field) ...... admin only
  - Delete product .................. admin only
  - Create variant .................. admin only
  - Update variant (any field) ...... admin only
  - Delete variant .................. admin only
  - Change compliance_status ........ admin only (audit log mandatory)
  - Toggle allowed_for_sale ......... admin only (audit log mandatory)
  - Read product / variant .......... any authenticated active user
    (admin, owner, manager, staff, driver) — drivers must be able to
    look up SKUs for delivery handoffs.

Roles owner / manager / staff / driver have READ access only on the
catalog. Operational decisions about which global products a store
carries are expressed through `inventory_items`, not through editing
the catalog.

When inventory and orders modules ship, the read-side may be filtered
further by store-scope helpers (`resolve_store_scope`), but the
catalog endpoints themselves stay global.


3. Sellability rule
-------------------
A product is SELLABLE if and only if all three flags hold:

  compliance_status == ComplianceStatus.allowed
  AND allowed_for_sale is True
  AND is_active is True

Notes:
  - `compliance_status == ComplianceStatus.banned` is NEVER sellable.
    No flag combination overrides this.
  - `compliance_status == ComplianceStatus.restricted` is NOT
    sellable in MVP. The state is reserved for future logic
    (e.g. age-verified flows, jurisdiction-restricted flows). Until
    that logic exists, treat `restricted` as non-sellable.
  - `is_active` is the catalog-management flag (product discontinued,
    catalog cleanup, supplier change). It is NOT a compliance flag.
  - `allowed_for_sale` is the operational kill-switch for fast pulls
    that do not yet have a formal compliance decision attached. It
    can be flipped without changing `compliance_status`.

Variants do not carry their own sellability flags. A banned product
bans all of its variants; an inactive product hides all of its
variants from sale.

The sellability check is the contract that inventory/orders modules
will rely on to decide whether a sale path can proceed. The helper
that materializes this rule will live in services/permissions in a
later subfase; this module only freezes the rule itself.


4. Compliance rules
-------------------
- Compliance state lives at the PRODUCT level. Variants do not have
  their own compliance state. Banning a product cascades to all of
  its variants by definition.
- Allowed values for `compliance_status`:
    - allowed
    - restricted   (reserved; not sellable in MVP)
    - banned       (never sellable)
- Every change to `compliance_status` MUST be auditable:
    - the change is recorded in a compliance audit log row,
    - the row captures the previous and new values, the actor
      (user_id), the reason text and the timestamp.
- Every change to `allowed_for_sale` MUST be auditable in the same
  way as `compliance_status`.
- A `reason` is mandatory for both transitions.
- The `last_compliance_check` timestamp on `products` is updated to
  the time of the most recent compliance review, regardless of
  whether the status changed.


5. Tenancy rules (recap, products view)
---------------------------------------
- `products` table: NO store_id.
- `product_variants` table: NO store_id.
- `inventory_items` table: store_id REQUIRED.
- `orders` table: store_id REQUIRED.
- `inventory_logs` table: store_id REQUIRED.
- `users` table: store_id NULLABLE only for admin (per S2.1
  invariant). All other roles must have a store binding.

Catalog endpoints do not consume `resolve_store_scope` because they
are global. Inventory/orders endpoints will.


6. Jurisdiction rules
---------------------
- MVP is Florida-only.
- The `jurisdiction` field on `products` defaults to "FL" and is
  treated as INFORMATIONAL in MVP — no code branches on it.
- Multi-jurisdiction support (a product allowed in FL but banned in
  TX, etc.) is OUT OF SCOPE for S3. Adding a second supported
  jurisdiction triggers a schema refactor (likely a many-to-many
  `product_jurisdictions` table); do not extend the current single
  string field.
- Until multi-jurisdiction lands, the assumption is that every
  product row is interpreted under `DEFAULT_JURISDICTION`.


7. Identifier and pricing rules
-------------------------------
- SKU is a GLOBAL unique identifier on `product_variants`. Two
  different products cannot share an SKU. The application layer
  must translate IntegrityError on duplicate SKU into HTTP 409.
- Barcode is a GLOBAL unique identifier on `product_variants`. Same
  409 translation applies.
- All money fields (`price`, `cost`, and any future totals) MUST be
  Python `Decimal` and PostgreSQL `NUMERIC(10, 2)`. No floats.
- `price >= 0` and `cost >= 0` are enforced at the database level by
  CHECK constraints. The application layer should still validate at
  the schema layer (Pydantic) and translate violations into HTTP 422.
- `cost` is nullable. Margin calculations must handle the None case.


Out of scope for S3 (record so it is not relitigated mid-session)
-----------------------------------------------------------------
- Per-store catalog overrides (store-specific name, price, hide
  flag).
- Per-store SKU schemes.
- Multi-jurisdiction product status.
- Approval workflow for owner-proposed catalog entries.
- Bulk import / CSV upload.
- Product images and media storage.
- Compliance auto-detection (regulator feeds, rule engines).
- Variant-level compliance overrides.
"""


# --------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------- #
# Constants only. No logic in this module.

DEFAULT_JURISDICTION: str = "FL"

# Tuple, not a set, because the iteration order is part of the contract
# (e.g. for fixtures and reports). Add elements only when the schema is
# extended to support multi-jurisdiction; do not extend in MVP.
SUPPORTED_JURISDICTIONS: tuple[str, ...] = ("FL",)
