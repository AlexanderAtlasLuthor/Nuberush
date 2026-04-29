# NubeRush — S5 Orders Module Completion

Final completion record for the orders module. Spans the eleven
subphases shipped between domain rules and concurrency tests.

This document reflects the state of `main` after S5.10 and is
authoritative: every claim below maps to running code, a passing
test, or a database constraint. Aspirational items are explicitly
marked under §12 (Limitations) and §13 (Risks).

---

## 1. Overview

The orders module is a **transaction coordinator** sitting on top of
the inventory subsystem (S4). It owns the order lifecycle (create →
delivered/canceled/returned), the totals computation, the audit log,
and the integration with the inventory `_locked` helpers introduced
in S5.3.

### What it solves

- Multi-item orders that must reserve scarce inventory atomically:
  if any line cannot be reserved, **nothing** persists.
- Idempotent order creation: duplicate POSTs (network retries,
  client glitches) cannot create duplicate orders, duplicate
  reservations, or duplicate audit rows.
- A regulated lifecycle (pending → … → delivered → returned) where
  inventory only moves at three transitions (delivered, canceled,
  returned) and where every transition is recorded immutably.
- A trust boundary where the client supplies only `variant_id`,
  `quantity` and `idempotency_key`; everything monetary or
  inventory-related is server-resolved.
- RBAC- and tenancy-aware HTTP surface for staff/manager workflows
  with cross-store and unauthenticated access denied at the gate.

### What it guarantees

- **No double reservation** under concurrency (Test S5.10 A, E).
- **No double consumption** at delivered (Test S5.10 C).
- **No double release** on cancel (Test S5.10 D).
- **No idempotency leak**: same `(store_id, idempotency_key)`
  always resolves to one order, even under concurrent retries
  (Test S5.10 B).
- **Atomicity**: a multi-item create that fails on item N rolls
  back the order row, every order_item, every inventory mutation,
  every inventory log and every audit log produced so far
  (S5.5 group C, S5.10 E).
- **No client-side tampering** of money or inventory binding:
  schemas reject those keys at the API boundary (S5.4, S5.6
  group G).
- **Append-only audit trail** for every successful state
  transition.
- **Driver and anonymous callers cannot reach orders** (S5.6 auth
  gate + RBAC matrices).

### What is explicitly out of scope (MVP)

- Real payment integration. `total_amount` is captured but no
  charge is made.
- Tax computation by jurisdiction. `tax_amount = 0` is the MVP
  contract.
- Delivery flow. Driver role remains denied across all orders
  endpoints; the future delivery module will broker
  `out_for_delivery → delivered`.
- Reservation TTL / automatic timeout.
- Discount or coupon codes.
- Refund tracking beyond the `returned` lifecycle event.
- Customer self-service flow. Orders are created by store staff
  acting on behalf of a customer (`customer_user_id` is nullable
  to support walk-in customers without an account).
- Bulk import or CSV creation of orders.
- Multi-channel orders. A single channel is assumed.

---

## 2. Architecture

### Layers

```
┌──────────────────────────────────────────────────────────────────┐
│  HTTP layer        backend/app/api/routes/orders.py              │
│  thin router       (auth + RBAC + tenancy → service)             │
└──────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Service layer     backend/app/services/orders.py                │
│  transaction       (idempotency, totals, state machine,          │
│  coordinator       audit log, inventory orchestration)           │
└──────────────────────────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
┌──────────────────────────┐  ┌────────────────────────────────────┐
│  Inventory `_locked`     │  │  Pydantic schemas                  │
│  helpers (S5.3)          │  │  backend/app/schemas/orders.py     │
│  no-commit primitives    │  │  trust boundary (extra="forbid")   │
│  with row-level locks    │  └────────────────────────────────────┘
└──────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Database       Order, OrderItem, OrderAuditLog,                 │
│                 InventoryItem, InventoryLog                      │
│                 + check / unique / FK constraints                │
└──────────────────────────────────────────────────────────────────┘
            ▲
            │
┌──────────────────────────────────────────────────────────────────┐
│  Domain rules   backend/app/domain/orders_rules.py               │
│  (FROZEN)       executable-doc (no logic) — single source of     │
│                 truth for tenancy / trust boundary / lifecycle / │
│                 money / RBAC / compliance / transactions         │
└──────────────────────────────────────────────────────────────────┘
```

### Canonical write flow

```
create_order
  ├─ 1. idempotency pre-check  (return existing if found)
  ├─ 2. validate store exists
  ├─ 3. INSERT order(pending, totals=0)        ← held in session
  ├─ 4. flush                                  ← may catch UNIQUE; retry
  ├─ 5. for each line item:
  │      ├─ resolve inventory_item via (store_id, variant_id)
  │      ├─ _reserve_inventory_locked         ← FOR UPDATE; mutate; log
  │      └─ INSERT order_item(snapshot price, line_total)
  ├─ 6. recompute totals from snapshots
  ├─ 7. INSERT order_audit_log(order_created)
  └─ 8. db.commit()                            ← single commit

transition_order_status(... → delivered)
  ├─ load order
  ├─ assert valid transition (state machine)
  ├─ for each line item: _consume_reserved_inventory_locked
  │      (re-checks sellability; ↓ qreserved AND ↓ qoh; sale log)
  ├─ set delivered_at, status=delivered
  ├─ INSERT order_audit_log(order_delivered)
  └─ db.commit()

cancel_order
  ├─ load order
  ├─ assert previous_status in {pending, accepted, preparing, ready,
  │                             out_for_delivery}
  ├─ for each line item: _release_reservation_locked
  │      (↓ qreserved; cancellation log)
  ├─ set canceled_at, cancel_reason, status=canceled
  ├─ INSERT order_audit_log(order_canceled)
  └─ db.commit()

return_order
  ├─ load order
  ├─ assert previous_status == delivered
  ├─ for each line item: _return_to_inventory_locked
  │      (↑ qoh; return_ log)
  ├─ set returned_at, status=returned
  ├─ INSERT order_audit_log(order_returned)
  └─ db.commit()
```

The service is the **only** layer that calls `db.commit()` for
order operations. Inventory `_locked` helpers do not commit; the
public commit-wrapper functions (`reserve_inventory`,
`consume_reserved_inventory`, etc.) exist for direct administrative
use but the orders coordinator never calls them.

---

## 3. Data model

### `orders`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `store_id` | UUID FK → `stores` (CASCADE) | NOT NULL, indexed |
| `customer_user_id` | UUID FK → `users` (SET NULL) | nullable (walk-in) |
| `idempotency_key` | varchar(128) | NOT NULL, see §7 |
| `status` | enum `order_status` | NOT NULL, default `pending` |
| `subtotal_amount` | numeric(10,2) | NOT NULL, ≥ 0 |
| `tax_amount` | numeric(10,2) | NOT NULL, ≥ 0 (MVP: always 0) |
| `total_amount` | numeric(10,2) | NOT NULL, ≥ subtotal |
| `accepted_at` | timestamptz | nullable |
| `canceled_at` | timestamptz | nullable |
| `delivered_at` | timestamptz | nullable |
| `returned_at` | timestamptz | nullable |
| `cancel_reason` | text | nullable |
| `notes` | text | nullable |
| `age_verified_at` / `age_verified_by_user_id` | (out of scope MVP) | reserved |
| `created_at`, `updated_at` | timestamptz | server-managed |

Constraints:

- `UNIQUE(store_id, idempotency_key)` → `uq_orders_store_idempotency_key`
- `CHECK idempotency_key <> ''`
- `CHECK subtotal_amount >= 0`, `tax_amount >= 0`, `total_amount >= 0`
- `CHECK total_amount >= subtotal_amount`

### `order_items`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `order_id` | UUID FK → `orders` (CASCADE) | NOT NULL |
| `variant_id` | UUID FK → `product_variants` (RESTRICT) | NOT NULL |
| `inventory_item_id` | UUID FK → `inventory_items` (RESTRICT) | NOT NULL — bound at create time, never sent by client |
| `quantity` | int | NOT NULL, > 0 |
| `unit_price` | numeric(10,2) | NOT NULL — snapshot of `ProductVariant.price` at create time |
| `line_total` | numeric(10,2) | NOT NULL, = `unit_price × quantity` |
| `created_at`, `updated_at` | timestamptz | server-managed |

Constraints:

- `UNIQUE(order_id, variant_id)` — duplicate variants in the same
  order are rejected at the schema layer (§9 trust boundary) AND
  at the DB
- `CHECK quantity > 0`
- `CHECK unit_price >= 0`, `line_total >= 0`, `line_total >= unit_price`

The `inventory_item_id` binding is the linchpin of cross-store
safety: an order in store A, on a global variant V, only ever
points at the inventory_item row for `(A, V)`. The service resolves
this from `(order.store_id, line.variant_id)` via
`UNIQUE(store_id, variant_id)`. The client cannot supply or
override it.

### `order_audit_logs`

Append-only audit trail. One row per state transition; rows are
written in the same transaction as the mutation they record.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `order_id` | UUID FK → `orders` (CASCADE) | NOT NULL |
| `store_id` | UUID FK → `stores` (CASCADE) | NOT NULL — denormalized for fast tenant-scoped queries |
| `performed_by_user_id` | UUID FK → `users` (SET NULL) | nullable |
| `previous_status` | enum `order_status` | nullable (NULL on `order_created`) |
| `new_status` | enum `order_status` | NOT NULL |
| `action` | varchar(50) | NOT NULL — see action vocabulary below |
| `reason` | text | nullable |
| `created_at` | timestamptz | server-managed |

Action vocabulary (constants exported by `app.services.orders`):

| Constant | Value | Emitted by |
|---|---|---|
| `ACTION_ORDER_CREATED` | `order_created` | `create_order` |
| `ACTION_STATUS_CHANGED` | `status_changed` | `transition_order_status` (non-delivered branch) |
| `ACTION_ORDER_DELIVERED` | `order_delivered` | `transition_order_status` (delivered branch) |
| `ACTION_ORDER_CANCELED` | `order_canceled` | `cancel_order` |
| `ACTION_ORDER_RETURNED` | `order_returned` | `return_order` |

`compliance_blocked` was deliberately **not** introduced in MVP.
Writing it would require committing an audit row from a path that
otherwise needs to roll back; see §13 risks.

---

## 4. State machine

```
   ┌──────────────────────────────────────────────────────────┐
   │                                                          │
   ▼                                                          │
pending ─→ accepted ─→ preparing ─→ ready ─→ out_for_delivery │
   │           │            │         │              │        │
   │           │            │         │              │        │
   ▼           ▼            ▼         ▼              ▼        │
canceled ───── canceled ─── canceled  canceled       canceled │
                                      │                       │
                                      ▼                       │
                                  delivered ◀─────────────────┘
                                      │
                                      ▼
                                  returned
```

### Allowed transitions

```
pending          → {accepted, canceled}
accepted         → {preparing, canceled}
preparing        → {ready, canceled}
ready            → {out_for_delivery, delivered, canceled}
out_for_delivery → {delivered, canceled}
delivered        → {returned}
canceled         → terminal
returned         → terminal
```

Any transition not in this matrix raises `HTTPException(422)` from
`_assert_valid_transition`. Terminal states have no allowed
outbound transition.

### Endpoint routing

Cancel and return have their own service methods (and HTTP routes)
because they carry mandatory reasons and operate at a different RBAC
tier (manager-or-above). The generic
`transition_order_status` endpoint **rejects** `→ canceled` and
`→ returned` with 422 to force callers to the dedicated routes.

### Inventory effects per transition

| Transition | Inventory effect | Inventory log type |
|---|---|---|
| (create) → pending | `_reserve_inventory_locked` per line — `↑ quantity_reserved` | `reservation` |
| pending → accepted | none (sets `accepted_at`) | — |
| accepted → preparing | none | — |
| preparing → ready | none | — |
| ready → out_for_delivery | none | — |
| ready / out_for_delivery → delivered | `_consume_reserved_inventory_locked` per line — `↓ quantity_reserved` AND `↓ quantity_on_hand`; **re-checks sellability** | `sale` |
| any pre-delivered → canceled | `_release_reservation_locked` per line — `↓ quantity_reserved` | `cancellation` |
| delivered → returned | `_return_to_inventory_locked` per line — `↑ quantity_on_hand` | `return_` |

`quantity_on_hand` only moves at delivered (down) and returned (up).
The intermediate transitions are intentionally inventory-neutral so
the reservation persists across them.

---

## 5. Business rules

Rules in force, each with the file/test that anchors it. Numbering
follows `app/domain/orders_rules.py`.

| # | Rule | Anchor |
|---|---|---|
| 1 | Orders are store-scoped; cross-store operations are admin-only. | `orders_rules.py` §1; `_assert_can_access_store` in router; 8 tenancy tests in `test_orders_api.py` |
| 2 | Frontend MUST NOT send `subtotal_amount`, `tax_amount`, `total_amount`, `unit_price`, `line_total`, `inventory_item_id`, `status`, `id`, timestamps. | `model_config = ConfigDict(extra="forbid")` on every input schema; 16 trust-boundary tests at API + 27 at schema |
| 3 | Lifecycle and inventory effects per transition (see §4 above). | `_ALLOWED_TRANSITIONS` dict; `TestStateMachine` (7 tests) |
| 4 | `idempotency_key` is required on every `POST /orders`. | Schema `Field(min_length=1, max_length=128)`; `_strip_required` validator |
| 5 | Totals are computed server-side. `tax_amount = 0` MVP. `total_amount = subtotal_amount + tax_amount`. `line_total = unit_price × quantity`. | `_calculate_order_totals`; `_reserve_order_items` snapshots `unit_price` from `ProductVariant.price`; 4 money tests (service) + 1 money test (API) |
| 6 | RBAC tiers (see §9). | `require_staff_or_above` / `require_manager_or_above` deps; 5×3 role matrices in `test_orders_api.py` |
| 7 | `assert_product_sellable(product)` is the canonical gate. Re-invoked on CREATE (via `_reserve_inventory_locked` → `_assert_item_operable`) AND on DELIVERED (via `_consume_reserved_inventory_locked` → `_assert_item_operable`). | `_assert_item_operable` in inventory service; `TestComplianceSellability` (5 tests) |
| 8 | One audit row per state transition, written in the same transaction. | `_write_order_audit_log` (no-commit); 4 audit tests (service) + 4 (API) |
| 9 | Service is the coordinator; one `db.commit()` per write op. Inventory helpers reachable from orders MUST NOT commit. | `_locked` helper convention from S5.3; `TestAtomicRollback` (S5.5 group C) |

Additional rules:

- `compliance_status = restricted` is **not sellable** in MVP, same
  as `banned` (inherited from `products_rules` §3).
- Cancel and return paths skip the sellability gate — operators
  must be able to free reservations and accept returns on banned
  products.
- Returns are allowed only from `delivered`. Returns from earlier
  states are 422.

---

## 6. Transactionality

### Helpers and commits

Inventory exposes a private set of `_locked` helpers (S5.3) that
**mutate state and write a log row but do not commit**. The orders
coordinator composes these inside its own transaction:

- `_reserve_inventory_locked`
- `_release_reservation_locked`
- `_consume_reserved_inventory_locked`
- `_return_to_inventory_locked`

Every public commit-wrapper function (`reserve_inventory`,
`release_reservation`, `consume_reserved_inventory`,
`return_to_inventory`) is built on top of the corresponding helper
and adds exactly one `_commit_or_translate(db)`. The orders service
**never** calls these wrappers; it always calls the underscore
helpers directly so the entire order operation lands in a single
transaction.

### Locking discipline

Every helper begins with `_lock_inventory_item(db, item_id)` which
issues `SELECT … FOR UPDATE` on the `inventory_items` row. The lock
is held until the surrounding transaction commits or rolls back.
Concurrent operations on the same item serialize at the DB level.
This is the **same lock** used by S4 inventory; orders does not
introduce a new one.

### Single commit per operation

Every public mutation in `orders.py` ends with exactly one call to
`_commit_or_translate(db)`. The N reservations / N consumes / N
releases produced by an N-item order land or roll back together.

### Rollback semantics

Conceptually, `create_order` for a multi-item payload looks like:

```
BEGIN
  INSERT order(pending, totals=0)
  flush                                        ← idempotency uniqueness here

  for each line in payload.items:
    SELECT ... FROM inventory_items FOR UPDATE
    assert sellable + stock available
    UPDATE inventory_items SET qreserved += line.quantity
    INSERT inventory_logs(reservation, ...)
    INSERT order_items(...)

  recompute totals → UPDATE order
  INSERT order_audit_logs(order_created)
COMMIT
```

If any step from line 1 onward raises `HTTPException(422)` (e.g.
insufficient stock on line N), the service does `db.rollback()`
and re-raises. The DB-level effect is that the order row, every
order_item row inserted, every inventory_items mutation, every
inventory_logs row and any partially written audit row all
disappear together. There is no partial state on disk.

The same shape applies to `transition_order_status(... delivered)`:
N consumes serialize against the N inventory rows; if the N-th one
fails (e.g. the product was banned mid-flight and the
inventory_item is now `quarantined`), the previous N-1 consumes
are rolled back along with any status mutation already staged in
the session.

### Error translation

`_commit_or_translate(db)` catches `IntegrityError` from a final
`db.commit()` and translates it to:

- `409 CONFLICT` if the violation is on `uq_orders_store_idempotency_key`
- `422 UNPROCESSABLE_ENTITY` otherwise

This protects clients from raw psycopg messages. The same pattern
guards the post-flush path that resolves the idempotency race
(see §7).

---

## 7. Idempotency

### Contract

Every `POST /stores/{store_id}/orders` carries a non-empty
`idempotency_key` (1–128 chars, trimmed). The combination
`(store_id, idempotency_key)` is unique at the DB level via
`uq_orders_store_idempotency_key`.

### Sequential replay

A second POST with the same `(store_id, idempotency_key)` after the
first has committed:

1. The pre-flight check `_find_existing_idempotent_order(store_id,
   key)` returns the existing order.
2. The service returns it unchanged. No new inventory mutation, no
   new order_item, no new audit row.

### Concurrent race

Two simultaneous POSTs with the same key:

1. Both pre-flight checks return None (their snapshots predate any
   commit).
2. Both threads insert the order row. The first acquires the
   uniqueness lock on the index entry until it commits.
3. The second's INSERT blocks waiting for the first's transaction
   to resolve.
4. When the first commits, the second's INSERT fails with
   `UniqueViolation` raised as SQLAlchemy `IntegrityError`.
5. The service catches the `IntegrityError`, rolls back, calls
   `_find_existing_idempotent_order` again — this time it finds the
   committed order — and returns it.

Both callers therefore observe a successful create with the same
`order.id`. The second's prepared inventory work (if any) was rolled
back in step 5. This race is exercised by **Test S5.10 B**:

```python
ok, fail, err = _split_results(results)
assert err == [], f"Unexpected errors: {err}"
assert len(ok) == 2          # both succeed (replay-safe)
assert ok[0][1] == ok[1][1]  # same order.id

# Final DB:
assert len(orders) == 1
assert item.quantity_reserved == 2     # not 4 — single reservation
assert len(reservation_logs) == 1
assert len(audit_created) == 1
```

### What is **not** done

- Idempotency keys do **not** time out. A key reused months later
  is treated as a replay if the original order is still in the DB.
  TTL is documented as a future deferral.
- The service does **not** verify the replay payload matches the
  original. A duplicate key with a different body returns the
  original order, not 409. (Schema-level `extra="forbid"` keeps the
  payload shape consistent across retries; the deeper semantic
  check is deferred.)
- Idempotency operates at the request level, not the line-item
  level. Partial retries of multi-item orders are not supported.

---

## 8. Concurrency

### Mechanism

All inventory mutation paths reachable from orders take a row-level
lock with `SELECT … FOR UPDATE` on `inventory_items`. Postgres
serializes concurrent transactions on the same row; the second
transaction blocks until the first commits or rolls back, then
proceeds with a fresh read of the post-commit state.

The orders service inherits this lock; it does not introduce a new
one. Idempotency is additionally protected by a unique index lock
on `uq_orders_store_idempotency_key`.

### Isolation

Tests run against the project's default Postgres isolation level
(`READ COMMITTED`). Two MVCC snapshots of the same `Order` taken
across the commit boundary of another transaction can see different
states, which is why some tests accept either of two failure
details for the loser (see Test C and Test D below).

### Demonstrated guarantees

| Test | Scenario | Asserted invariant |
|---|---|---|
| S5.10 A | `qoh=1`; two simultaneous `create_order(qty=1)` with distinct keys | `len(ok)==1`, `len(fail)==1`, fail is 422 stock; `qreserved==1`; one order, one order_item, one reservation log, one `order_created` audit. |
| S5.10 B | `qoh=10`; two simultaneous `create_order` with **same** `(store_id, idempotency_key)` | Both succeed, both return same `order.id`; one order, one reservation, one log, one audit. |
| S5.10 C | order at `ready`; two simultaneous `transition → delivered` | Exactly one consume succeeds; loser is 422 (either "Cannot consume X units: only 0 are reserved." after losing the row-lock race, or "Invalid transition delivered → delivered." after losing the status race). `qreserved=0`, `qoh` decremented once, one sale log, one `order_delivered` audit. |
| S5.10 D | order pending with `qreserved=2`; two simultaneous `cancel_order` | Exactly one cancel succeeds; loser is 422 (either "Cannot release …" or "Cannot cancel an order in status 'canceled'."). `qreserved=0` (never negative); one cancellation log; one `order_canceled` audit. |
| S5.10 E | two simultaneous orders for `[A=1, B=1]` with `A.qoh=10`, `B.qoh=1` | Exactly one order completes; loser's reservation on A is **rolled back** along with B (atomicity). `A.qreserved=1`, `B.qreserved=1`, no orphan order_items, no orphan logs, one audit. |

### Stability

The five tests are run via a module-scoped engine with `NullPool`,
each worker on its own `Session`, synchronized at start by
`threading.Barrier(2)`. Worker threads have a 20-second `join`
timeout that calls `pytest.fail` on hang to make deadlocks loud
rather than silent. Five consecutive runs at validation time
produced 25/25 passes with no flakes, no deadlocks, no timeouts.

---

## 9. Security

### RBAC

Role hierarchy (S2): `admin > owner > manager > {staff, driver}`.
`staff` and `driver` are sibling operational roles, not stacked.
Driver is **denied across every orders endpoint** in MVP — the
delivery flow that would let them participate is deferred.

| Endpoint | Allowed | Denied |
|---|---|---|
| `POST /stores/{id}/orders` | admin, owner, manager, staff | driver, anon |
| `GET /stores/{id}/orders` | admin, owner, manager, staff | driver, anon |
| `GET /orders/{id}` | admin, owner, manager, staff | driver, anon |
| `GET /orders/{id}/audit-logs` | admin, owner, manager, staff | driver, anon |
| `PATCH /orders/{id}/status` | admin, owner, manager, staff | driver, anon |
| `POST /orders/{id}/cancel` | admin, owner, manager | staff, driver, anon |
| `POST /orders/{id}/return` | admin, owner, manager | staff, driver, anon |

Cancel and return require manager-or-above because they undo
operational decisions (cancel) or commit to a refund flow (return)
and the audit trail must reflect that.

### Tenancy

Two enforcement points, both backed by tests:

- **Store-scoped paths** (`/stores/{store_id}/...`) use
  `Depends(require_store_member)` from `app/api/deps.py`. The
  dependency runs **before** the function body; it 403s non-admin
  callers acting on a store they do not belong to and 404/400s
  admin callers on missing/inactive stores.
- **Order-scoped paths** (`/orders/{order_id}/...`) load the order
  first via `svc.get_order` (which 404s a missing order) and then
  call `_assert_can_access_store(current_user, order.store_id)`.
  `store_id` is **read from the loaded order**, never trusted from
  the request body or path.

Admin bypasses both gates by design and can read or mutate orders
across any store.

### Trust boundary

Five Pydantic input schemas use `model_config =
ConfigDict(extra="forbid")`:

- `OrderItemCreate`
- `OrderCreate`
- `OrderStatusUpdate`
- `OrderCancelRequest`
- `OrderReturnRequest`

Any of the following in a `POST /orders` body returns 422 from
FastAPI's Pydantic layer before the router function executes:

```
OrderCreate root:    subtotal_amount, tax_amount, total_amount,
                     unit_price, line_total, inventory_item_id,
                     status, id, store_id, customer_user_id,
                     created_at, updated_at, accepted_at,
                     delivered_at, canceled_at, returned_at,
                     cancel_reason, age_verified_at,
                     age_verified_by_user_id

OrderItemCreate:     unit_price, line_total, inventory_item_id, id,
                     order_id, created_at, updated_at
```

Service-layer fallback: even if a future caller bypasses the
schema, the `customer_user_id` parameter to `create_order` is
function-only (no schema field exposes it), and the service
re-resolves `inventory_item_id` from `(store_id, variant_id)` and
re-snapshots `unit_price` from `ProductVariant.price` regardless of
what the caller might have tried to pass. The trust boundary is
enforced redundantly at the HTTP layer (schema) and the data layer
(service ignores anything not in the contract).

---

## 10. API

Seven endpoints, registered in `backend/app/main.py` after the
inventory router. None contains business logic; each is a thin
auth/RBAC/tenancy gate wrapped around a service call.

### `POST /stores/{store_id}/orders` → `OrderRead` (201)

Creates an order. Body: `OrderCreate` (`idempotency_key` + `items[]`
+ optional `notes`). Tenancy via `require_store_member`. RBAC:
staff-or-above. Resolves inventory_item per line, reserves stock,
snapshots prices, computes totals, writes audit, commits once.
Idempotent on `(store_id, idempotency_key)`.

### `GET /stores/{store_id}/orders` → `list[OrderRead]` (200)

Lists orders for a store. Query params: `?status=`, `?created_from=`,
`?created_to=`. Tenancy via `require_store_member`. RBAC:
staff-or-above. Pure read; service returns rows ordered by
`created_at desc` with line items eagerly loaded
(`selectinload(Order.items)`).

### `GET /orders/{order_id}` → `OrderRead` (200, 404)

Reads a single order. Tenancy via `_assert_can_access_store` after
load. RBAC: staff-or-above. 404 if the order does not exist.

### `GET /orders/{order_id}/audit-logs` → `list[OrderAuditLogRead]`

Returns every audit row for the order ordered by `created_at asc`.
Tenancy via `_assert_can_access_store`. RBAC: staff-or-above. 404
if the order does not exist.

### `PATCH /orders/{order_id}/status` → `OrderRead`

Body: `OrderStatusUpdate(new_status, optional reason)`. Tenancy via
`_assert_can_access_store`. RBAC: staff-or-above. Service validates
the transition; rejects `→ canceled` and `→ returned` with 422
(forces use of the dedicated routes); sets `accepted_at` /
`delivered_at` as appropriate; consumes reservations on `→ delivered`.

### `POST /orders/{order_id}/cancel` → `OrderRead`

Body: `OrderCancelRequest(reason)` — reason is mandatory. Tenancy
via `_assert_can_access_store`. RBAC: manager-or-above. Releases
the reservation on every line, sets `canceled_at` / `cancel_reason`,
audit, single commit.

### `POST /orders/{order_id}/return` → `OrderRead`

Body: `OrderReturnRequest(reason)` — reason is mandatory. Tenancy
via `_assert_can_access_store`. RBAC: manager-or-above. Allowed
only from `delivered`; replenishes `quantity_on_hand`, sets
`returned_at`, audit, single commit.

### Error mapping

| Condition | HTTP | Origin |
|---|---|---|
| Anonymous | 401 | `get_current_user` |
| Inactive user | 403 | `get_current_user` |
| Wrong role | 403 | `require_*` aliases |
| Cross-store (non-admin) | 403 | `require_store_member` / `_assert_can_access_store` |
| Missing order | 404 | `svc.get_order` |
| Missing store (admin) | 404 | `require_store_member` |
| Inactive store | 400 | `require_store_member` |
| Missing inventory for `(store, variant)` | 422 | `_resolve_inventory_item` |
| Insufficient stock | 422 | `_assert_stock_available` |
| Invalid transition | 422 | `_assert_valid_transition` |
| Cancel from non-cancelable | 422 | `cancel_order` guard |
| Return from non-delivered | 422 | `return_order` guard |
| Duplicate idempotency_key (concurrent) | 409 (rare) / 200 replay | `_commit_or_translate` |
| DB integrity violation (other) | 422 | `_commit_or_translate` |
| Schema rejection (extra field, type, range) | 422 | FastAPI/Pydantic |

No path returns 500. No `detail` contains raw psycopg / SQL
strings; the API tests run an explicit `_no_sql_leak` substring
check on every error response.

---

## 11. Testing

Coverage at the close of S5.10:

| Layer | File | Tests | Style |
|---|---|---:|---|
| Domain (frozen rules, AST-verified) | `app/domain/orders_rules.py` | n/a | docstring-only module |
| Schemas | `tests/test_order_schemas.py` | 77 | Pydantic, no DB |
| Inventory `_locked` helpers (S5.3) | `tests/test_inventory_transactional.py` | 11 | NullPool engine; rollback semantics; `_consume` guardrails |
| Service (transaction coordinator) | `tests/test_orders_service.py` | 52 | per-test transactional `db_session` + NullPool engine for atomicity test |
| API (HTTP) | `tests/test_orders_api.py` | 73 | FastAPI `TestClient` |
| Concurrency | `tests/test_orders_concurrency.py` | 5 | NullPool engine + `threading.Barrier` |
| **S5 total** | — | **218** | |

Layered responsibilities:

- **Schemas (77)** — input validators, `extra="forbid"` for every
  prohibited key, `ConfigDict(from_attributes=True)` hydration on
  read, parametrized matrices over the trust-boundary fields.
- **`_locked` helpers (11)** — proves no inner commits, multi-item
  rollback semantics, `_consume_reserved_inventory_locked`
  guardrails (qty validation, expected_store_id, sellability gate).
- **Service (52)** — A: create, B: idempotency, C: atomic rollback,
  D: cancel, E: delivered, F: return, G: state machine, H:
  compliance / sellability re-check, I: cross-store safety, J:
  money. Plus reads (5 tests).
- **API (73)** — auth gate parametrized over every endpoint, RBAC
  matrices on each tier, store- and order-scoped tenancy, trust
  boundary at HTTP, error propagation with `_no_sql_leak`,
  end-to-end behavior (create→cancel releases, create→deliver
  consumes).
- **Concurrency (5)** — A through E above (§8).

Suite total at S5 close:

```
$ python -m pytest -v
================= 618 passed, 2 warnings in ~90s ==================

$ python -m alembic check
No new upgrade operations detected.
```

The two warnings are an Alembic 1.16.5 `path_separator`
deprecation; cosmetic, recorded under §13.

---

## 12. Limitations (MVP)

Current as of `main` after S5.10. None of these blocks shipping;
each is recorded so the assumption is explicit.

- **`tax_amount = 0`.** The `tax_amount` column exists and is set
  to `0.00` on every order. No tax engine. When tax computation is
  added, it MUST live server-side in `orders.py`; the contract
  (`total_amount = subtotal_amount + tax_amount`) is preserved.
- **No real payment.** No `payment_status` column, no charge call,
  no provider integration. `total_amount` is captured but never
  collected.
- **No delivery tracking.** `out_for_delivery → delivered` is a
  staff transition; there is no driver linkage, no GPS, no
  delivery_attempt records.
- **No reservation TTL.** A reservation lives until cancelled or
  consumed at `delivered`. There is no scheduled job that
  auto-releases stale reservations.
- **No retries / outbox / queue.** All operations are synchronous
  request → service → DB → response. There is no event bus, no
  outbox table, no retry queue.
- **No partial fulfilment.** An order is either fully delivered or
  not at all. There is no concept of partial shipment.
- **No discounts / coupons.**
- **No order numbering beyond UUID.** No human-readable order
  number column.
- **Single channel.** Web only; no POS or marketplace.
- **No semantic idempotency check.** Same key with a different
  payload returns the original order (see §7).

---

## 13. Future risks

Items that work today but warrant attention as load grows or as
adjacent features ship.

### Scaling concerns

- **Horizontal scaling.** Multiple API instances running against
  the same Postgres are supported (the row lock is in the DB), but
  any in-process state (e.g. caches) MUST stay in-process or move
  to a shared store. The current implementation has no
  application-level state for orders.
- **Lock contention under high write throughput.** All concurrent
  orders on the same scarce inventory_item serialize on a single
  row lock. Hot SKUs can become a bottleneck. Mitigations exist
  (sharding inventory by sub-bucket, queueing), but none are needed
  at MVP volume.
- **Concurrent `delivered` is rare in practice but possible.** If
  it becomes common (e.g. async webhook re-delivery), the loser's
  422 is the right answer but operators may want a dedicated
  "already delivered" 409 — left as a future refinement.

### Architectural pressure points

- **Event-driven extension.** When pagos and delivery land, those
  modules will likely want to subscribe to `order_created` /
  `order_delivered` events. The audit log table is the natural
  source of those events; an outbox pattern will keep emission
  atomic with the order mutation.
- **Higher isolation level.** All current guarantees hold under
  `READ COMMITTED`. Two known windows where the loser's 422
  message depends on its MVCC snapshot are documented (Test C,
  Test D); they are correctness-equivalent today. If a stricter
  audit message contract emerges, raising to `REPEATABLE READ`
  would tighten the spec at a small throughput cost.
- **`compliance_blocked` audit action.** Today, a delivered
  transition that fails the sellability re-check raises 422 and
  rolls back without writing an audit row. Operators see "the
  transition was rejected" via the API but no audit trail
  documents *why*. Adding `compliance_blocked` requires a
  two-transaction shape (commit the audit, then re-raise) and is
  deferred.

### Cosmetic deuda

- Alembic 1.16.5 emits a `DeprecationWarning` about
  `path_separator` on `prepend_sys_path`. Two warnings per pytest
  session. Silencing it is a one-line addition to `alembic.ini`
  (`path_separator = os`); not done in this phase to keep the
  S5.10 diff minimal.

---

## 14. Production checklist

Pre-deploy verification gates. Each item maps to a single concrete
command or configuration.

- [ ] Postgres 16 reachable on the configured `DATABASE_URL`.
- [ ] `nuberush` role exists with login privileges; database owns
      the `orders`, `order_items`, `order_audit_logs` tables.
- [ ] `python -m alembic upgrade head` ran cleanly.
- [ ] `python -m alembic check` reports
      `No new upgrade operations detected`.
- [ ] `python -m pytest` reports 618 passing tests (or
      higher if subsequent phases shipped).
- [ ] Environment variables present and non-default for production:
      `DATABASE_URL`, `JWT_SECRET_KEY` (≥ 32 chars, not on the
      blocklist, no `dev-only-` prefix), `JWT_ALGORITHM`,
      `JWT_ISSUER`, `JWT_AUDIENCE`, `BACKEND_CORS_ORIGINS` (no
      `*`).
- [ ] App `JWT_SECRET_KEY` policy passes
      (`AuthSettings._enforce_jwt_secret_policy`); app refuses to
      start otherwise.
- [ ] Application logs are captured at the operational layer
      (uvicorn / process manager). The module itself does not
      configure logging beyond the framework defaults.
- [ ] Reverse proxy / load balancer terminates TLS; the API itself
      assumes Bearer auth over HTTPS.
- [ ] Postgres backup strategy in place — the audit log is
      append-only and load-bearing for compliance.
- [ ] `driver` users created without the orders surface in mind.
      They have **no** orders access and do not need any
      configuration here.

---

## 15. Final state

**S5 Orders Module = COMPLETED.**

| Subphase | Output | Status |
|---|---|---|
| S5.1 | `app/domain/orders_rules.py` (frozen) | ✅ |
| S5.2 | `Order`, `OrderItem`, `OrderAuditLog` + migration `6c8e2b2e7ed1` | ✅ |
| S5.3 | inventory `_locked` helpers + 11 transactional tests | ✅ |
| S5.4 | `app/schemas/orders.py` + 77 schema tests | ✅ |
| S5.5 | `app/services/orders.py` (transaction coordinator) + 52 service tests | ✅ |
| S5.6 | `app/api/routes/orders.py` + 73 API tests | ✅ |
| S5.7 | schema + migration validation | ✅ (covered by S5.4 + alembic check) |
| S5.8 | service tests | ✅ (covered by S5.5) |
| S5.9 | API / RBAC / tenancy tests | ✅ (covered by S5.6) |
| S5.10 | concurrency tests + 5 tests, 25/25 stable | ✅ |
| S5.11 | this completion document | ✅ |

The module is:

- **Transactionally correct.** One commit per write op. Multi-item
  failures roll back the whole order, every order_item, every
  inventory mutation, every inventory log, every audit row.
- **Secure.** Authentication required, RBAC enforced, tenancy
  enforced both ways, trust boundary enforced at the schema layer.
- **Consistent.** Totals derive from DB-resolved unit prices.
  Inventory bindings derive from `(store_id, variant_id)`.
  Audit log written in the same transaction as the mutation.
- **Tested under concurrency.** Five real Postgres race scenarios
  (single-unit contention, concurrent idempotency, concurrent
  delivered, concurrent cancel, multi-item partial failure) all
  pass deterministically with no flakes across five consecutive
  full runs.

S5 closes here. The next phase can take any of the deferred items
in §12 / §13 as input without revisiting any of the above.
