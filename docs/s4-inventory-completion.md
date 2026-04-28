# NubeRush — S4 Inventory Module Completion

Final completion record for the inventory module. Spans the eight
subphases shipped between domain rules and concurrency tests.

## 1. S4 objective

Build a store-scoped inventory module on top of the auth/RBAC/tenancy
(S2) and products (S3) foundation, covering:

- per-store stock state (`quantity_on_hand`, `quantity_reserved`,
  `reorder_threshold`, operational `status`)
- seven canonical stock movements (receive, adjust, damage, sale,
  reserve, release/cancellation, return) with append-only audit logs
- atomic transactions with `SELECT ... FOR UPDATE` row locks so
  concurrent operations cannot oversell or over-reserve
- automatic compliance cascade: banning a product immediately
  quarantines every related inventory row in the same transaction
- a REST API surface with RBAC tier separation (read / manager /
  staff) and store-scoped tenancy enforcement
- exhaustive automated test coverage (schemas, services, API,
  concurrency)

The exit criterion is a system in which:

- stock cannot go negative, get oversold, or have
  `quantity_reserved > quantity_on_hand` under any path including
  concurrent requests
- every successful mutation is paired with exactly one append-only
  log row; failure rolls them back together
- a banned product cannot be sold via any code path, and its
  inventory state is automatically reflected as quarantined
- driver, anonymous and cross-store callers are blocked at the API

---

## 2. Subphase summary

### S4.1 — Inventory domain rules (commit `9dade19`)

`backend/app/domain/inventory_rules.py` — a documentation-only
module (AST-verified: zero non-docstring nodes) that freezes:

1. inventory scope (store-scoped; products and variants global)
2. driver access policy (no access to inventory in MVP)
3. reservation semantics (`quantity_reserved` only;
   `cancellation` = release; legacy `reserved`/`sold` enum values
   not used)
4. inventory status (operational override:
   `available` / `flagged` / `quarantined`; legacy values rejected)
5. sellability enforcement (sale and reserve only; receive,
   adjust, damage, return and release proceed regardless of
   status)
6. compliance propagation (banned → quarantined cascade in the
   same transaction; reverse path does NOT auto-lift)
7. logging rules (`inventory_logs` is stock-only; compliance
   events live in `product_compliance_audit_logs`)
8. concurrency rules (`SELECT ... FOR UPDATE` mandatory on every
   mutation)
9. transaction guarantees (lock → validate → mutate → log →
   commit, atomic)
10. sellable quantity (`quantity_available =
    quantity_on_hand - quantity_reserved`; never use
    `quantity_on_hand` alone)

No data layer changes were needed in S4 — `inventory_items` and
`inventory_logs` already existed from S1 with the required CHECK
constraints (`quantity_on_hand >= 0`, `quantity_reserved >= 0`,
`quantity_reserved <= quantity_on_hand`, `quantity_delta != 0`,
`quantity_after >= 0`, reference pair consistency,
`UNIQUE(store_id, variant_id)`).

### S4.2 — Pydantic schemas (commit `ab0d979`)

`backend/app/schemas/inventory.py` — Pydantic v2 contracts:

- `InventoryItemCreate`, `InventoryItemUpdate`, `InventoryItemRead`
- `InventoryLogRead` (no Create/Update — append-only by
  convention)
- Movement requests: `ReceiveStockRequest`, `AdjustStockRequest`,
  `DamageStockRequest`, `SaleStockRequest`, `ReserveStockRequest`,
  `ReleaseReservationRequest`, `ReturnStockRequest`

Validation profile per movement:

- quantity > 0 on every movement except `adjust` (signed
  `delta != 0`)
- reason mandatory and non-empty for `adjust`, `damage`, `return`
- reason optional but trimmed when provided for `receive`, `sale`,
  `reserve`, `release`
- `reference_type` + `reference_id` come paired or both null

### S4.3 — Service layer (commit `29e9fa2`)

`backend/app/services/inventory.py` — 14 functions (4 read, 3
setup, 7 movement) plus internal helpers.

Key invariants enforced in every mutation:

- `_lock_inventory_item` issues `SELECT ... FOR UPDATE` before
  reading-and-mutating
- `_assert_item_operable` (sale/reserve only) calls
  `assert_product_sellable(product)` and verifies
  `variant.is_active` and `item.status == available`
- `_assert_stock_available` compares against
  `quantity_available`, never `quantity_on_hand`
- `_write_inventory_log` appends one log row in the same
  transaction; the helper does NOT commit
- `_commit_or_translate` translates IntegrityError to a clean 422
  with no SQL leak

Error mapping: 404 / 409 / 422 — never 500, never raw psycopg
messages bubbled to the caller.

### S4.4 — Compliance cascade (commit `35993fb`)

`backend/app/services/products.py:set_product_compliance` was
extended (29 lines) to issue a single bulk
`UPDATE inventory_items SET status='quarantined' WHERE variant_id
IN (variants of this product) AND status != 'quarantined'`
whenever the new compliance status is `banned`.

The cascade runs in the SAME transaction as the product mutation
and the audit log row. No `InventoryLog` rows are written
(compliance events live in `product_compliance_audit_logs`). The
reverse transition (banned → allowed/restricted) does NOT
auto-lift the quarantine; lifting is a deliberate operational
decision via the inventory status endpoint.

### S4.5 — API router (commit `d434fee`)

`backend/app/api/routes/inventory.py` — 14 REST endpoints across
three access tiers, plus `main.py` wires the router:

| Tier | Endpoints | Allowed | Denied |
|---|---|---|---|
| Read | 4 (list inventory, get item, list store/item logs) | admin, owner, manager, staff | driver, anon |
| Setup + manager | 6 (create item, threshold, status, receive, adjust, damage) | admin, owner, manager | staff, driver, anon |
| Staff | 4 (sell, reserve, release, return) | admin, owner, manager, staff | driver, anon |

Tenancy is enforced two ways:

- store-scoped paths (`/stores/{store_id}/...`) use
  `Depends(require_store_member)` from S2.3
- item-scoped paths (`/inventory/{item_id}/...`) load the item
  first and call `_assert_can_access_store(user, item.store_id)` —
  `store_id` is never trusted from the request body

Routers contain zero business logic.

### S4.6 — Schemas and services tests (commit `7cc0dc6`)

Two new test files, no production changes:

- `tests/test_inventory_schemas.py` — 68 tests (no DB) covering
  every validator on every schema, every edge of the reference
  pair rule, ORM hydration via `model_validate`
- `tests/test_inventory_services.py` — 30 tests using a
  per-test transactional `db_session` covering the 7 movements,
  log writing with correct fields, validation gates (insufficient
  stock, release > reserved, quarantined, banned product, inactive
  variant, adjust-below-reserved, damage-below-reserved), and
  service-level atomicity

### S4.7 — API / RBAC / tenancy tests (commit `407f215`)

`tests/test_inventory_api.py` — 71 tests through the FastAPI
TestClient, no production changes. Covers:

- auth gate parametrized over all 14 endpoints (anon → 401)
- read tier role matrix: 4 endpoints × 5 roles
- manager tier role matrix on receive + spot checks on the other
  five manager-tier endpoints (staff blocked)
- staff tier role matrix on sell + driver-blocked checks on
  reserve / release / return
- tenancy: cross-store reads and mutations rejected on owner /
  manager / staff; admin bypasses; user with `store_id=None`
  (rogue manager) rejected
- error propagation: 404 / 409 / 422 with `_no_sql_leak` helper
  that rejects `psycopg`, `DETAIL:`, `duplicate key`, `ERROR:`,
  `INSERT/UPDATE/SELECT` substrings in any returned `detail`
- integration flows end-to-end: manager-receive → staff-sell with
  logs visible via API; reserve/release round-trip; banned product
  blocks sale via API (cascade); quarantined item blocks
  sell/reserve through API while still accepting receive

### S4.8 — Concurrency tests (commit `f9f1a6f`)

`tests/test_inventory_concurrency.py` — 3 tests using a separate
module-scoped engine with `NullPool`, per-thread sessions, a
`threading.Barrier(2)` for synchronized start, and
`Thread.join(timeout=15s)` with `is_alive()` check to fail loudly
on hangs.

- two concurrent sales for the same single unit → exactly one
  succeeds (qoh→0), one returns 422; final state never negative;
  exactly one sale log
- two concurrent reservations for the same single unit → exactly
  one succeeds (qreserved→1, qoh untouched), one returns 422;
  available drops to 0; exactly one reservation log
- sale vs reserve race → exactly one succeeds (either side may
  win); the loser's mutation AND its log row both rolled back
  atomically

---

## 3. Final guarantees

The inventory module ships with the following guarantees, all
enforced by the production code and verified by the automated
suite:

- **Stock is store-scoped.** Every `inventory_items` row carries
  `store_id`; every `inventory_logs` row carries `store_id`. Two
  stores carrying the same variant have independent stock and
  history. No cross-store inventory operations are possible
  except for admin.
- **All mutations create logs.** Each successful call to
  `receive_stock`, `adjust_stock`, `record_damage`,
  `sell_inventory`, `reserve_inventory`, `release_reservation`,
  `return_to_inventory` appends exactly one `InventoryLog` row
  in the same transaction as the quantity change. Failure rolls
  back both together.
- **Sale and reserve enforce sellability.** Both call
  `assert_product_sellable(product)` (compliance_status ==
  allowed AND allowed_for_sale AND product.is_active) AND verify
  `variant.is_active is True` AND `item.status == available`.
  Any failure → 422 with diagnostic detail.
- **Banned product cascades inventory to quarantined.** A
  successful `set_product_compliance(..., banned, ...)` issues a
  single bulk UPDATE that flips every related
  `inventory_items.status` to `quarantined` in the same
  transaction as the product mutation and the compliance audit
  log row.
- **Driver has no access.** Every inventory endpoint denies the
  driver role with 403, verified by parametrized matrices on
  every tier.
- **Cross-store access is blocked.** Owner / manager / staff
  tokens cannot read or mutate inventory belonging to a store
  other than their own; this holds for store-scoped paths
  (`require_store_member`) and item-scoped paths
  (`_assert_can_access_store(user, item.store_id)` — store_id
  loaded from the item, never trusted from the request).
- **No overselling under concurrency.** Two simultaneous sales /
  reservations / one-of-each on a single unit serialize at the
  DB level via `SELECT ... FOR UPDATE`; exactly one succeeds and
  the other returns 422. Verified empirically.
- **Suite passes.** 400 tests, alembic check clean, no SQL or
  psycopg internals leaked in any error detail.

---

## 4. Test count

Suite as of `f9f1a6f` (the last S4.8 commit):

```
$ python -m pytest
================== 400 passed, 3 warnings in 77.83s (0:01:17) ==================

$ python -m alembic check
No new upgrade operations detected.
```

Distribution:

| Phase | Tests | Description |
|---|---:|---|
| S2 (auth, RBAC, tenancy, CORS) | 165 | from S2.0 through S2.6 |
| S3 (products + compliance) | 63 | from S3.5 product API/integration suite |
| **S4 (inventory)** | **172** | **see breakdown below** |
| **Total** | **400** | |

S4 breakdown:

| Subphase | Tests | File |
|---|---:|---|
| S4.6 schemas | 68 | `tests/test_inventory_schemas.py` |
| S4.6 services | 30 | `tests/test_inventory_services.py` |
| S4.7 API / RBAC / tenancy | 71 | `tests/test_inventory_api.py` |
| S4.8 concurrency | 3 | `tests/test_inventory_concurrency.py` |
| **S4 total** | **172** | |

---

## 5. Known deferrals

Documented but explicitly out of scope for S4. These are recorded
so they do not get relitigated mid-session:

### Inherited from earlier phases (not introduced by S4)

- `driver` role definition in the user creation matrix (product-
  level decision, S2.1 F1)
- passlib / bcrypt 4.x compatibility warning (S2 R5)
- JWT issuer/audience strict validation (S2.2 deferral)
- hard delete on products removes audit history (S3 documented
  trade-off)

### S4-specific (recorded in `app/domain/inventory_rules.py`)

- Orders module — entire `orders` and `order_items` business
  logic is **S5**. The reservation and sale paths are wired
  exactly as S5 will need them; orders will simply call
  `reserve_inventory` and `sell_inventory` with their own
  `reference_type`/`reference_id` polymorphic pointers.
- Driver delivery flow — drivers have no inventory access in
  MVP. Their interaction with inventory (delivery handoffs, lost
  packages) belongs to a future delivery module that will
  presumably introduce its own movement type or specialized
  endpoint.
- Reservation TTL — a reservation lives until cancelled or
  consumed by a sale; no automatic timeout. If product needs
  reservations to expire, that becomes a scheduled job in a
  future subphase.
- Multi-warehouse / multi-location inventory per store.
- Stock transfers between stores.
- Lot / batch tracking.
- Expiration date tracking and automatic damage on expiry.
- Bulk import / CSV upload of inventory levels.
- Inventory soft-delete via dedicated endpoint (use `status` for
  operational holds; deletion of the row is admin-only and out of
  scope).
- Optimistic concurrency tokens (we use pessimistic row locks; no
  ETag-style concurrency).

---

## 6. Final status

**S4 COMPLETE — ready for S5 Orders.**

The inventory module ships with end-to-end coverage from domain
rules to concurrency safety. The reservation and sale paths are
the seams S5 will plug into: orders will create reservations on
checkout intent, convert them to sales on payment confirmation,
and release them on cancellation — using the exact service
functions tested here.
