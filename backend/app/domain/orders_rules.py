"""NubeRush — Orders domain rules (FROZEN for S5).

This module contains **no executable logic**. It is the single source of
truth for the design decisions that govern the orders module — order
lifecycle, inventory effects, money handling, idempotency, RBAC,
compliance and transaction coordination.

Every service, schema, router or test working on orders MUST be
consistent with the rules below. When the rules change, this file
changes first and the implementation follows; never the other way
around.

These decisions are derived from:
  - Phase 0 (foundation): every sale must reduce inventory; banned
    products cannot be sold.
  - S1 (database): `orders` and `order_items` already exist with
    `store_id`, FKs, CHECK constraints and an `OrderStatus` enum.
  - S2 (auth/RBAC/tenancy): backend owns roles and store_id; the
    frontend is never trusted with privileged inputs.
  - S3 (products + compliance): `assert_product_sellable(product)` is
    the canonical sellability gate.
  - S4 (inventory): reserve / sell / release / return are the seams
    orders will plug into.
  - S5 Subfase 1: explicit freezing of orders-module decisions.


1. Tenancy
----------
- Orders are STORE-SCOPED. Every `orders` row carries a `store_id`,
  every `order_items` row links a global variant to that order, and
  every state transition is recorded against that store.
- Two stores running orders on the same global variant operate
  independently. Cross-store order operations are forbidden. Admin
  is the only role that may operate across stores.
- The orders service must always resolve the inventory_item to act
  on through `(order.store_id, order_item.variant_id)` →
  UNIQUE(store_id, variant_id), never by `variant_id` alone. Picking
  the wrong inventory_item would sell stock from another store.


2. Trust boundary — what the frontend MUST NOT send
---------------------------------------------------
The orders API does not accept the following fields in any request
body. They are computed or resolved server-side from authoritative
sources:

- `subtotal_amount`, `tax_amount`, `total_amount` — totals are
  derived from line items and the tax rule (see §5). Accepting
  them from the client opens a fraud path (a buyer could submit
  `total_amount=0.01` for a $9.99 product).
- `unit_price` — copied from `ProductVariant.price` at order-
  creation time. The order item snapshots that value so a later
  catalog price change does not retroactively alter committed
  orders.
- `line_total` — derived as `unit_price * quantity`. Schemas
  reject any client-provided value.
- `inventory_item_id` — resolved by the service from
  `(store_id, variant_id)`. The frontend supplies `variant_id`
  and the service decides which inventory row backs it. Trusting
  the frontend here would let a caller in store A bind an order
  item to store B's inventory.
- Any field the schema marks as server-managed (e.g. `id`,
  timestamps, `status`, `created_at`, `updated_at`).


3. Order lifecycle and inventory effects
----------------------------------------
The 8 values of `OrderStatus` are: `pending, accepted, preparing,
ready, out_for_delivery, delivered, canceled, returned`.

Inventory effects per transition (the canonical S5 rule):

- CREATE order (`status = pending`): for each line item, the
  service calls inventory `reserve_inventory(...)`. Reservations
  RAISE `quantity_reserved`. They DO NOT touch `quantity_on_hand`
  — physical stock stays put on the shelf.
- DELIVERED transition: the service consumes the reservations.
  This means: for each line item, RELEASE the reservation
  (decrement `quantity_reserved`) AND record the SALE (decrement
  `quantity_on_hand`). At inventory log level this produces one
  `cancellation` row and one `sale` row per item, in the same
  transaction.
- CANCELED transition: the service releases the reservations
  (decrement `quantity_reserved`). It does NOT touch
  `quantity_on_hand`. Logs record `cancellation` movements.
- RETURNED transition: the service replenishes inventory by
  calling `return_to_inventory(...)` for each line item, raising
  `quantity_on_hand` back. Returns produce `return_` movement
  logs and require a reason.

Intermediate transitions (`pending → accepted → preparing →
ready → out_for_delivery`) DO NOT mutate inventory. The
reservation persists across them. Inventory only moves at
`delivered` (consume), `canceled` (release) and `returned`
(replenish).

The matrix of allowed transitions and the role that may trigger
each one is fixed in §6 and re-validated against compliance at
every transition that touches inventory (§7).


4. Idempotency
--------------
- Every `POST /orders` request MUST carry an `idempotency_key`.
  Clients that omit it receive 400. The key is provided by the
  client (UUID4 or opaque string) and scoped to the (store_id,
  customer_user_id, idempotency_key) tuple.
- The service treats a duplicate request (same key, same caller,
  same store) as a SAFE replay: it returns the EXISTING order
  unchanged with the original status code (201 if the original
  request created the order, 200 if the replay arrives later).
- A duplicate key with a DIFFERENT body is a violation: the
  service returns 409 with a clear detail. This protects against
  malformed retries that mutate the request between attempts.
- The idempotency key has a documented retention window (TTL).
  After that window, the key may be reused. The TTL is server-
  side metadata, not a client contract.
- Idempotency lives at the request level, not at the line-item
  level. Partial retries of multi-item orders are not supported
  in MVP (the whole order is the unit of replay).


5. Money handling (MVP)
-----------------------
- All money fields are Python `Decimal` and PostgreSQL
  `NUMERIC(10, 2)`. No floats. Inherited from S3 / S4.
- TOTALS ARE COMPUTED SERVER-SIDE. The service resolves each line
  item's `unit_price` from `ProductVariant.price`, computes
  `line_total = unit_price * quantity`, and sets
  `subtotal_amount = sum(line_totals)`.
- `tax_amount = 0` in MVP. The orders module does not compute
  taxes. The column exists and is set to `0.00` on every order.
  When a real tax engine arrives, the calculation lives in the
  orders service (server-side, never client).
- `total_amount = subtotal_amount + tax_amount`. With
  `tax_amount = 0` in MVP, `total_amount == subtotal_amount`.
- The `line_total = unit_price * quantity` invariant is enforced
  by the service. The S1 CHECK `line_total >= unit_price` is a
  weak backstop and remains; service-layer enforcement is the
  primary defence.
- Real PAYMENT is OUT OF SCOPE for MVP. There is no
  `payment_status`, no payment-provider integration, no charge.
  Orders proceed through the lifecycle without tracking money
  movement beyond the totals captured at creation. Payment
  integration is a future module.


6. Roles
--------
Driver does not interact with the orders module in MVP. The
delivery flow that bridges drivers and orders (`out_for_delivery
→ delivered`) is out of scope for S5; until that lands, driver
endpoints on orders return 403.

The matrix below is the SOURCE OF TRUTH the API router will wire
through the existing S2.3 aliases. It is not yet enforced in
code; it is fixed here so subphases that ship code stay
consistent.

  - Create order ............. staff or above (admin / owner /
                                manager / staff). Driver denied.
  - Read order (one)  ........ staff or above, store-scoped;
                                admin global.
  - List orders ............... staff or above, store-scoped;
                                admin global.
  - Transition pending → accepted .......... staff or above
  - Transition accepted → preparing ........ staff or above
  - Transition preparing → ready ........... staff or above
  - Transition ready → out_for_delivery .... staff or above
  - Transition out_for_delivery → delivered  staff or above (in
                                MVP). Future delivery module may
                                hand this transition to the driver
                                role under tighter constraints.
  - Cancel (any pre-delivered status) ...... manager or above.
                                staff cannot cancel because cancel
                                undoes reservations and may
                                contradict floor decisions.
  - Mark returned (after delivered) ........ manager or above.
                                Same logic as cancel — returns
                                replenish inventory and require
                                operational sign-off.
  - Age-verify a pending order ............. staff or above.

Cross-store enforcement applies to every endpoint via
`require_store_member` (path) or item-derived
`_assert_can_access_store(user, order.store_id)` (item path).


7. Compliance
-------------
- `assert_product_sellable(product)` is the canonical gate. It
  remains the rule of record from S3.
- `compliance_status = restricted` is NOT sellable in MVP, same
  as `banned`. Inherited verbatim from `products_rules §3`.
- Compliance is RE-CHECKED at every state transition that
  touches inventory:
    - on CREATE (reserve path): assert sellable per line item.
    - on DELIVERED (sale path): re-assert sellable per line item.
    - on RETURNED (replenish): no sellability check; returns are
      allowed for non-sellable products (the units come back
      regardless).
    - on CANCEL (release): no sellability check; cancel can free
      reservations on banned products.
- Compliance race window: a product banned BETWEEN reserve and
  delivered must NOT be delivered. The DELIVERED transition's
  re-check is the line of defence. If it fires, the order
  cannot transition to delivered until the product is unbanned
  AND the inventory item is manually un-quarantined (per
  `inventory_rules §6`). Otherwise the operator must transition
  to `canceled` instead.


8. Audit log
------------
- A separate `order_audit_logs` table records every state
  transition. The model and migration are out of scope for this
  rules file (S5.2 schema subphase will introduce them); the
  contract is frozen here.
- Each row captures: order_id, previous_status, new_status,
  changed_by_user_id (FK SET NULL), reason (optional in MVP),
  created_at.
- The transition row is written in the SAME transaction as the
  status mutation and any inventory effect. Failure rolls back
  all three together.
- The audit log is append-only by convention.


9. Transaction coordination
---------------------------
- The orders service is the COORDINATOR. It owns the transaction
  boundary and is the only layer that calls `db.commit()` for
  order operations.
- INVENTORY HELPERS USED BY ORDERS DO NOT COMMIT. The S4
  inventory service exposes mutation functions that currently
  commit internally; orders cannot reuse those public functions
  directly inside its own transaction. Two acceptable shapes for
  S5 implementation:
    (a) Refactor inventory to expose underscore-prefixed
        helpers that mutate + log without committing, and let
        the public functions stay as commit-wrappers around
        them. Orders calls the helpers and commits once.
    (b) Use SAVEPOINTs around each inventory call inside an
        outer orders transaction. The outer commit is the only
        commit; inner SAVEPOINTs roll back individual failures.
  The choice is made in S5.2; this file pins the contract that
  inventory helpers reachable from orders MUST NOT commit.
- An order with multiple line items MUST commit exactly once.
  The N reservations / N sales / N returns produced by an
  N-item order are part of one atomic transaction with the
  order row and the audit log row.
- If ANY line item fails (insufficient stock, product not
  sellable, race lost on the row lock), the WHOLE order rolls
  back. There is no partial state: no order row, no inventory
  mutations, no audit row, no log entries persist.
- Concurrency: the inventory row lock from S4 (`SELECT ... FOR
  UPDATE`) keeps two simultaneous orders for the same scarce
  unit serialized at the DB. Orders code reuses that lock; it
  does not introduce a new one.


Out of scope for S5 (recorded so it does not get relitigated)
-------------------------------------------------------------
- Real payment integration (Stripe, etc.). `total_amount` is
  captured but no charge is made.
- `payment_status` column / state machine.
- Discount / coupon codes.
- Refund tracking beyond the `returned` lifecycle event.
- Tax computation by jurisdiction. `tax_amount = 0` is the MVP
  contract.
- Customer self-service flow. The `UserRole` enum has no
  `customer` value. Orders are created by store staff acting on
  behalf of a customer (`customer_user_id` is nullable to
  support walk-in customers without an account).
- Delivery flow (`out_for_delivery → delivered`) handed over to
  driver role. Driver remains denied across orders endpoints in
  MVP; the future delivery module will broker that transition.
- Bulk import or CSV creation of orders.
- Order numbering beyond UUID (no human-readable order_number
  column in MVP).
- Multi-channel orders (web, POS, marketplace) — a single
  channel is assumed in MVP.
- Reservation TTL / automatic timeout (inherited from
  inventory_rules §10 deferral).
- Partial fulfillment (an order is delivered fully or not at
  all in MVP).
"""
