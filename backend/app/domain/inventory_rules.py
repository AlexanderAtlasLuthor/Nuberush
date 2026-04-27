"""NubeRush — Inventory domain rules (FROZEN for S4).

This module contains **no executable logic**. It is the single source of
truth for the design decisions that govern the inventory module —
stock state, movements, logs, concurrency and the way inventory
interacts with products / compliance / RBAC / tenancy.

Every service, schema, router or test working on inventory MUST be
consistent with the rules below. When the rules change, this file
changes first and the implementation follows; never the other way
around.

These decisions are derived from:
  - Phase 0 (foundation) — every sale must reduce inventory; banned
    products cannot be sold.
  - S1 (database) — `inventory_items` and `inventory_logs` already
    exist with `store_id`, FKs, CHECK constraints and a UNIQUE on
    (store_id, variant_id).
  - S2 (auth/RBAC/tenancy) — backend owns roles and store_id;
    `require_store_member` enforces tenancy.
  - S3 (products) — `assert_product_sellable(product)` is the
    canonical sellability check; compliance changes are audited in
    `product_compliance_audit_logs`.
  - S4 Subfase 1 — explicit freezing of inventory-module decisions.


1. Inventory scope
------------------
- Inventory is STORE-SCOPED. Every `inventory_items` row carries a
  `store_id` and every `inventory_logs` row carries a `store_id`.
  Two stores carrying the same variant have independent stock,
  reservations, thresholds and history.
- Products are GLOBAL.
- Product variants are GLOBAL.
- An `InventoryItem` is the tuple
      (store_id, variant_id, stock state)
  with `UNIQUE(store_id, variant_id)` enforced at the DB level so a
  given (store, variant) pair has exactly one inventory row.
- Cross-store inventory operations are forbidden. Admin is the only
  role that may operate across stores.


2. Driver access
----------------
- Drivers DO NOT have access to inventory in MVP.
- Drivers cannot read, mutate, list, query, search or in any way
  inspect inventory_items or inventory_logs through the API.
- The `staff` and `driver` roles remain siblings (per S2.3): the
  inventory surface is staff-and-above, never driver. Drivers
  acting on deliveries do not touch stock; that is exclusively the
  staff path until orders/delivery modules say otherwise.


3. Reservation semantics
------------------------
- Reservations are tracked using `quantity_reserved` only. They do
  NOT mutate `quantity_on_hand`. A reservation removes the units
  from the available pool but they remain physically on shelf.
- Sales mutate `quantity_on_hand` (units leave the store). They do
  NOT touch `quantity_reserved` directly; the reservation that
  preceded a sale is consumed implicitly when the sale lands.
- `cancellation` movement type means RELEASE OF A RESERVATION: it
  decreases `quantity_reserved` without touching `quantity_on_hand`.
  The units return to the available pool.
- The enum values `InventoryStatus.reserved` and `InventoryStatus.sold`
  are NOT used in MVP. Reservation state lives in
  `quantity_reserved` (a number); sale state is implicit (the units
  are gone). Using `status='reserved'` or `status='sold'` as a way
  to mark an item is forbidden because it would create two parallel
  representations of the same fact.


4. Inventory status
-------------------
- `InventoryItem.status` is an OPERATIONAL OVERRIDE, never a
  representation of stock quantity.
- Allowed values for MVP behaviour:
    available    — normal flow; sales and reservations may proceed
                   subject to other checks.
    flagged      — operational hold; sales and reservations are
                   blocked. Use for "we noticed a problem with this
                   SKU in this store, freeze it until we resolve".
    quarantined  — regulatory hold; sales and reservations are
                   blocked. Set automatically when the underlying
                   product is banned (see §6).
  The enum technically also lists `reserved` and `sold` (legacy
  artefacts of the schema). They are NOT used in MVP and must not
  be set by any service.
- If `status != available`, both sale and reservation are blocked,
  regardless of available quantity. Receipts, adjustments, damage
  records, returns and reservation releases (cancellation) MAY
  still proceed on a non-available item — they are how you correct
  or rebuild state. The contract is that nothing leaves the store
  while status is non-available.


5. Sellability enforcement
--------------------------
- Sale and reserve MUST invoke
      assert_product_sellable(item.variant.product)
  before mutating stock. The helper raises HTTP 422 when the
  product is not sellable per S3 rules
  (compliance_status == allowed AND allowed_for_sale AND is_active).
- Sale and reserve must also verify that
    item.variant.is_active is True
  and
    item.status == InventoryStatus.available
  before proceeding. These three gates are independent and any one
  failing blocks the operation.
- Receipts, adjustments, damage records, returns and cancellations
  (release of reservation) DO NOT require the sellability check.
  Those operations exist precisely to manage stock that may not
  currently be sellable (e.g. recording incoming stock of a
  flagged SKU, returning units of a banned product, etc.).


6. Compliance propagation
-------------------------
- If a product transitions to `compliance_status = banned`, all of
  that product's inventory items in every store MUST be set to
  `status = quarantined` in the same transaction as the compliance
  change.
- The propagation is a service-level cascade, not a DB trigger. It
  belongs in `services.products.set_product_compliance` (or a
  helper invoked from there). It must be an atomic part of the
  same transaction that writes the `product_compliance_audit_logs`
  row, so a failure rolls back the compliance change, the audit
  row AND the inventory status changes together.
- The reverse path (banned → allowed) does NOT automatically lift
  the quarantine on inventory items. Lifting quarantine is a
  separate, deliberate operational decision and should be performed
  by a manager or admin via the inventory status endpoint.
- `inventory_logs` MUST NOT be used to record compliance events.
  Compliance audit history lives in `product_compliance_audit_logs`
  (S3.2). The inventory log is for stock movements only.


7. Logging rules
----------------
- `inventory_logs` records ONLY stock movements. The full set in
  MVP is:
      receipt        stock arriving from a supplier or transfer in
      adjustment     manual correction (positive or negative);
                     reason mandatory at the schema layer
      damage         units lost to damage / breakage / expiry;
                     reason mandatory
      sale           units sold to a customer; quantity_on_hand
                     decreases
      reservation    units reserved (held for an order);
                     quantity_reserved increases
      cancellation   release of a previously made reservation;
                     quantity_reserved decreases
      return_        units returned by a customer; quantity_on_hand
                     increases; reason mandatory
- The legacy enum value `compliance_hold` is reserved and NOT used
  by the inventory log path. Compliance events are audited in
  `product_compliance_audit_logs`.
- Each log row captures: which item, which store, which variant,
  who acted (`performed_by_user_id`, nullable for system actions),
  the movement_type, the signed `quantity_delta` (DB enforces
  != 0), the resulting `quantity_after` (DB enforces >= 0), the
  optional reason and an optional polymorphic reference
  (`reference_type` + `reference_id`, both null or both set).
- Logs are append-only by convention. The service layer never
  updates or deletes log rows.


8. Concurrency rules
--------------------
- ALL inventory mutations MUST take a row-level lock on the
  `inventory_items` row before reading-and-mutating its quantities.
  In SQLAlchemy terms:
      stmt = select(InventoryItem).where(
          InventoryItem.id == item_id
      ).with_for_update()
  The lock is held for the duration of the transaction.
- Locking applies to: receive, adjust, damage, sale, reserve,
  release (cancellation), return, and any status update that may
  block subsequent operations.
- Reads (GET /inventory, GET /logs) DO NOT take locks.
- Two concurrent sales / reservations on the same item must
  serialize at the DB level: the second waits for the first to
  commit and then re-evaluates the available quantity. The
  underlying CHECK constraints (`quantity_on_hand >= 0`,
  `quantity_reserved <= quantity_on_hand`) are a backstop, not the
  primary defence. The primary defence is the row lock.
- The service layer must translate any concurrency-induced
  IntegrityError into a clean HTTP 422 ("insufficient stock" or
  equivalent) — never a 500 with a raw psycopg message.


9. Transaction guarantees
-------------------------
Every inventory mutation must execute the following sequence in a
single transaction:

  1. Lock the inventory_items row (with_for_update).
  2. Validate rules (sellability, status, variant active, available
     quantity, etc.) using the locked-and-current values.
  3. Apply the mutation to quantity_on_hand and / or
     quantity_reserved (and `last_counted_at` if relevant).
  4. Append exactly one InventoryLog row describing the movement.
  5. Commit.

If any step fails — validation, CHECK constraint, FK constraint,
unhandled exception — the transaction rolls back. The mutation and
the log row land together or not at all. There is no path that
mutates quantity without producing a log, and no path that
produces a log without an effective stock change (except for the
documented case of compliance propagation, which lives in product
audit logs and not here).


10. Sellable quantity
---------------------
- The amount available to sell or reserve is:
      quantity_available = quantity_on_hand - quantity_reserved
- Sale and reserve operations MUST compare requested delta against
  `quantity_available`, never against `quantity_on_hand` alone.
  Selling using `quantity_on_hand` would let the seller hand over
  units that another customer has already reserved.
- Receipts, returns and reservation releases increase
  `quantity_available` (by adding to `quantity_on_hand` or
  removing from `quantity_reserved` respectively).
- Adjustments and damage events decrease (or, in the rare positive
  case, increase) `quantity_on_hand` and therefore
  `quantity_available`. They do NOT touch `quantity_reserved`.


Out of scope for S4 (recorded so it is not relitigated mid-session)
-------------------------------------------------------------------
- Multi-warehouse / multi-location-per-store inventory.
- Stock transfers between stores.
- Lot / batch tracking.
- Expiration date tracking and automatic damage on expiry.
- Driver access to inventory (deliberately excluded; see §2).
- Bulk import / CSV upload of inventory levels.
- Reservation expiry / TTL (a reservation lives until cancelled or
  consumed by a sale; no automatic timeout).
- Soft-delete of inventory items (use `status` for operational
  holds; deletion of the row is admin-only and out of scope here).
- Optimistic concurrency tokens (we use pessimistic row locks; no
  ETag-style concurrency).
"""
