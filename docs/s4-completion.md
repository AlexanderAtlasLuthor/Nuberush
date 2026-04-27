# NubeRush — S4 Completion Announcement

## Summary

S4 (Inventory + Movements + Logs) has been **fully completed and validated**.

This is the second business module shipped on top of the auth/RBAC/tenancy/products foundation. It introduces store-scoped stock state, transactional movements with row-level locking, append-only audit logs, and an automatic compliance cascade that quarantines inventory whenever the underlying product is banned.

The module spans 5 subphases:

- S4.1 — Inventory domain rules (frozen)
- S4.2 — Pydantic schemas for items / logs / movements
- S4.3 — Transactional service layer
- S4.4 — Compliance cascade integration with S3
- S4.5 — REST API surface with RBAC and tenancy

---

## Scope Delivered

### 1. Domain Layer (S4.1)

`backend/app/domain/inventory_rules.py` is a pure documentation file (AST-verified: zero non-docstring nodes) that freezes the design decisions for the entire module. Sections covered:

- Inventory scope (per store; products/variants global)
- Driver access policy (no access in MVP)
- Reservation semantics (`quantity_reserved` only; `cancellation` = release)
- Inventory status (`available` / `flagged` / `quarantined`; legacy `reserved`/`sold` rejected)
- Sellability enforcement (sale and reserve only)
- Compliance propagation (banned → quarantined; reverse does not auto-lift)
- Logging rules (`inventory_logs` is stock-only; compliance lives elsewhere)
- Concurrency rules (`SELECT ... FOR UPDATE` mandatory on every mutation)
- Transaction guarantees (lock → validate → mutate → log → commit, atomic)
- Sellable quantity (`quantity_available = quantity_on_hand - quantity_reserved`)

### 2. Data Layer

No schema changes were needed in S4 — `inventory_items` and `inventory_logs` were already in place from S1 with the correct CHECK constraints (`quantity_on_hand >= 0`, `quantity_reserved >= 0`, `quantity_reserved <= quantity_on_hand`, `quantity_delta != 0`, `quantity_after >= 0`, reference pair consistency). `alembic check` remained clean throughout.

### 3. API Contract (S4.2)

`backend/app/schemas/inventory.py` — Pydantic v2 schemas:

- `InventoryItemCreate`, `InventoryItemUpdate`, `InventoryItemRead`
- `InventoryLogRead` (no Create/Update — append-only by convention)
- Movement requests: `ReceiveStockRequest`, `AdjustStockRequest`, `DamageStockRequest`, `SaleStockRequest`, `ReserveStockRequest`, `ReleaseReservationRequest`, `ReturnStockRequest`

Validation profile per movement:

- Quantity > 0 on every movement except `adjust` (signed `delta != 0`)
- Reason mandatory and non-empty for `adjust`, `damage`, `return`
- Reason optional but trimmed when provided for `receive`, `sale`, `reserve`, `release`
- Reference fields (`reference_type` + `reference_id`) come paired or both null

### 4. Business Logic — Service Layer (S4.3)

`backend/app/services/inventory.py` — 14 functions across 4 read, 3 setup and 7 movement operations.

Key invariants:

- Every mutation locks the row with `SELECT ... FOR UPDATE` before reading-and-mutating
- Sale and reserve invoke `assert_product_sellable(product)` plus check `variant.is_active` and `item.status == available`
- Sellable comparison uses `quantity_available = qoh - qreserved`, never `qoh` alone
- Every mutation appends exactly one `InventoryLog` row in the same transaction
- IntegrityError translates to clean 422 / 409 / 404 — never bubbles raw psycopg messages

### 5. Compliance Cascade (S4.4)

`backend/app/services/products.py:set_product_compliance` was extended (29 lines) to issue a single bulk `UPDATE inventory_items SET status='quarantined' WHERE variant_id IN (variants of this product)` whenever the new compliance status is `banned`. The cascade runs in the SAME transaction as the product mutation and the audit log row. No `InventoryLog` rows are written for the cascade (compliance events live in `product_compliance_audit_logs`). The reverse transition (`banned → allowed/restricted`) does NOT auto-lift the quarantine; lifting is a deliberate operational decision.

### 6. API Layer (S4.5)

`backend/app/api/routes/inventory.py` exposes 14 endpoints across three access tiers:

- **Reads** (`require_staff_or_above`, driver/anon denied): list inventory, get item, list store/item logs
- **Setup + manager-tier movements** (`require_manager_or_above`): create item, threshold/status updates, receive/adjust/damage
- **Staff-tier movements** (`require_staff_or_above`): sell/reserve/release/return

Tenancy is enforced two ways:

- Store-scoped paths (`/stores/{store_id}/...`) use `Depends(require_store_member)` from S2.3
- Item-scoped paths (`/inventory/{item_id}/...`) load the item first and call `_assert_can_access_store(user, item.store_id)` — `store_id` is never trusted from the request body

The router contains zero business logic; every endpoint is thin: parse, authorize, call service, return.

### 7. Testing & Validation

Throughout S4, validation was performed at every subphase via:

- Static AST-based checks (function existence, lock usage, no `InventoryLog` in cascade, etc.)
- Behavioral harnesses against the real test database (`nuberush_test`)
- Smoke imports
- Full suite regression (`pytest`, 228/228 passing)
- `alembic check` clean

S4.5 added live API matrices: 18 RBAC checks, 5 tenancy cases, 3 error propagation cases, 4 cascade cases — all 30 OK.

The S4 closure adds an automated test file `backend/tests/test_inventory.py` that locks in the most critical behaviors so regressions surface in CI rather than during validation.

---

## Guarantees Achieved

- **Stock correctness**: it is impossible to leave stock negative, oversold, or with `reserved > on_hand` — enforced at three layers (schema, service, DB CHECK).
- **Concurrency safety**: every stock mutation serializes at the DB level via `SELECT ... FOR UPDATE`, so two simultaneous sales on the same item cannot both succeed.
- **Atomicity**: every mutation produces its `InventoryLog` row in the SAME transaction; failure rolls back both. Compliance changes also roll back inventory cascade with the audit log.
- **Tenancy**: cross-store inventory access is impossible for non-admin roles; admin bypass works.
- **Sellability enforcement**: sale and reserve require `compliance_status == allowed` AND `allowed_for_sale` AND `is_active` AND `variant.is_active` AND `item.status == available`. Any failure → 422 with diagnostic detail.
- **Compliance propagation**: banning a product automatically quarantines all related inventory items in the SAME transaction.
- **No SQL leaks**: every IntegrityError or DB CHECK violation translates to clean 4xx HTTP responses.

---

## Current System State

After S4, the backend includes:

- Authentication (JWT with full claim set)
- RBAC with role aliases and store-membership helpers
- Multi-tenant architecture (store-based)
- Product catalog (global, with compliance + audit)
- **Inventory module (per-store, transactional, audited)**
- **14 inventory REST endpoints with RBAC and tenancy**
- 14 product REST endpoints
- 4 auth endpoints
- Health endpoint
- CORS middleware

---

## Known Non-Blocking Items

Carried forward from earlier phases (none introduced by S4):

- `driver` role definition in the user creation matrix (product-level, not technical)
- `passlib` / bcrypt compatibility warning (inherited from S2)
- JWT issuer/audience strict validation (inherited deferral)
- Hard delete on products removes audit history (inherited, documented)

S4-specific deferrals (recorded in `inventory_rules.py` "Out of scope"):

- Multi-warehouse / multi-location-per-store inventory
- Stock transfers between stores
- Lot / batch tracking
- Expiration date tracking
- Driver access to inventory
- Bulk import / CSV upload
- Reservation TTL / automatic timeout
- Inventory soft-delete via dedicated endpoint
- Optimistic concurrency tokens (we use pessimistic row locks)

---

## Status

**S4 — COMPLETED**

- Domain rules ✔
- Schemas ✔
- Service layer ✔
- Compliance cascade ✔
- API layer ✔
- Tests ✔

The backend now has two fully functional business modules (products + inventory) on top of the security foundation.

---

## Next Phase

S5 will introduce:

- Orders
- Order items linked to inventory reservations and sales
- Order lifecycle states
- Foundation for delivery and payment integrations

Built on top of: products, compliance, inventory (reservations and sales already wired through to the inventory layer; orders module will use those exact paths).
