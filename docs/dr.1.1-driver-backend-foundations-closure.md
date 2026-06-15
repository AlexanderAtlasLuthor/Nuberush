# Dr.1.1 Driver Backend Foundations Closure

## 1. Phase status

- Dr.1.1.A–N are **completed**.
- Dr.1.1.O is this **closure / validation** phase (docs + validation only; no
  runtime changes).
- All implemented subphases are **pushed**.
- CI is **green**.
- `main` is **synced** with `origin/main`.
- Working tree is **clean** at the closure baseline.

**Evidence**

Last implemented commit:

```text
8c63216385b31ac56d9a3ff49f8032b144175768
feat(driver): add assignment arrive-customer action
```

CI:

```text
Run ID 27559390246
Workflow: CI
frontend     success
backend-unit success
rls-active   success
```

## 2. Final route surface as-built

```text
GET  /driver/me
GET  /driver/eligibility
GET  /driver/assignments
GET  /driver/assignments/{assignment_id}
GET  /driver/assignments/{assignment_id}/delivery-state

POST /driver/assignments/{assignment_id}/accept
POST /driver/assignments/{assignment_id}/decline
POST /driver/assignments/{assignment_id}/start
POST /driver/assignments/{assignment_id}/arrive-store
POST /driver/assignments/{assignment_id}/pickup
POST /driver/assignments/{assignment_id}/depart-to-customer
POST /driver/assignments/{assignment_id}/arrive-customer
```

Count:

```text
5 GET
7 POST
0 PATCH
0 PUT
0 DELETE
```

This is the **authorized final Dr.1.1 driver route surface**. No other
`/driver/*` route is registered, and there is no PATCH/PUT/DELETE anywhere on
the surface. This surface is enforced by route-surface guard tests across the
driver test suite.

## 3. Final operational flow as-built

```text
offer assignment
→ accept
→ start
→ en_route_to_store
→ arrive-store
→ arrived_at_store
→ pickup
→ picked_up
→ depart-to-customer
→ en_route_to_customer
→ arrive-customer
→ arrived_at_customer
```

**Dr.1.1 boundary = `arrived_at_customer`.**

Everything after `arrived_at_customer` (ID verification, proof, completion,
failure, return-to-store, and the `Order.status` handoff) is **out of Dr.1.1**
and belongs to Dr.1.2+.

## 4. Contract A vs as-built reconciliation

The document `docs/dr.1.1-driver-backend-contract-foundations.md` was the
**historical foundational contract** (Dr.1.1.A). The real as-built
implementation advanced further than that planning contract anticipated, and it
uses more concrete state names and route shapes. This section reconciles the
two without editing the original contract.

| Dimension                       | Original Dr.1.1.A contract           | Dr.1.1 as-built closure                 |
| ------------------------------- | ------------------------------------ | --------------------------------------- |
| Planned final subphase          | L = final validation                 | N reached arrive-customer; O closes A–N |
| Route model                     | /driver/deliveries/{delivery_id}/... | /driver/assignments/{assignment_id}/... |
| Pickup states                   | pickup_pending / pickup_confirmed    | pickup_started / picked_up              |
| Verification states             | verification_pending / proof_pending | id_verification_pending / id_verified   |
| Completion states               | completion_pending                   | delivery_completed / delivery_failed    |
| Final reached operational state | foundation-level contract            | arrived_at_customer                     |

Declarations:

- The original Dr.1.1.A contract **remains the historical foundation** and is
  preserved unchanged.
- **This closure document is the as-built authority for Dr.1.2 planning.**
- The original contract is **not edited** in this phase.

## 5. Operational state enum

States **reached/produced by Dr.1.1 endpoints**:

- `not_started`
- `en_route_to_store`
- `arrived_at_store`
- `pickup_started`
- `picked_up`
- `en_route_to_customer`
- `arrived_at_customer`

States **defined in the enum but not produced by any Dr.1.1 endpoint**:

- `id_verification_pending`
- `id_verified`
- `delivery_completed`
- `delivery_failed`
- `returning_to_store`
- `returned_to_store`
- `canceled`

Dr.1.1 **does not** start ID verification and **does not** complete or fail
deliveries. The trailing states above exist in the enum so that later subphases
build against a stable shape; they are referenced by Dr.1.1 only as guard
states (for example, an attempt to arrive-customer from a state past
`arrived_at_customer` is rejected, never advanced).

## 6. Boundaries protected

Dr.1.1 driver actions do **not** mutate or implement:

- `Order.status`
- `out_for_delivery`
- `delivered`
- `OrderAuditLog`
- `Inventory`
- `InventoryItem`
- `InventoryLog`
- `Product`
- `ProductVariant`
- payments
- payouts
- ID verification
- verify-age
- proof of delivery
- delivery complete
- failed delivery
- return-to-store
- GPS / geofence / location enforcement
- frontend / mobile / Flutter

## 7. Positive invariants

The Dr.1.1 driver operational actions hold the following invariants:

- **driver-role gated** — only the driver role reaches these endpoints.
- **store-bound** — the driver is bound to their own store.
- **self-scoped** — a driver sees and acts only on their own assignments.
- **anti-enumeration** — a foreign / non-own / missing assignment returns 404,
  never leaking existence across the scope boundary.
- **locking** — `with_for_update` locks over both the assignment and the
  operational_state row for operational mutations.
- **idempotency by current state** — calling an action whose destination state
  is already current returns success without re-mutating.
- **timestamp preservation** — repeated destination-state calls preserve
  `state_started_at` and `last_transition_at`.
- **single materialization point** — only `start` materializes the
  operational_state row.
- **no implicit creation** — later operational actions never create a missing
  operational_state row; a missing row is a 422 precondition failure.

## 8. Assignment status vs operational state vs Order.status

Three distinct state machines are kept separate:

- **`OrderDriverAssignment.status`** — the assignment decision / lifecycle
  (offered, accepted, declined, started, etc.).
- **`DriverDeliveryOperationalState.state`** — the physical driver progress
  through the delivery (the flow in section 3).
- **`Order.status`** — the public / commercial order lifecycle (the canonical,
  authoritative order state machine).

As-built rule:

- `accept` / `decline` mutate the assignment decision state.
- `start` moves the assignment into `started`.
- `arrive-store`, `pickup`, `depart-to-customer`, and `arrive-customer` keep
  `assignment.status = started` and advance only the operational state.
- Dr.1.1 does **not** turn `assignment.status` into the whole delivery
  workflow; fine-grained progress lives in the operational state, not in the
  assignment status.

## 9. Pending Order.status handoff decision

This is recorded as a **pending decision** for Dr.1.2, not implemented here.

**Question:** When and how should driver operational state promote
`Order.status`?

Future cases:

- `picked_up` / `en_route_to_customer` → `out_for_delivery`
- `delivery_completed` → `delivered`
- `delivery_failed` → failed / canceled / review state
- `returned_to_store` → returned / review state

**Recommended rule:** The driver layer should **not** write `Order.status`
directly. The handoff should go through the existing order authority with
locks, `OrderAuditLog`, cross-domain idempotency, and role-matrix validation.

## 10. Dr.1.2 carry-forward scope

Dr.1.2 should cover:

- verify-age / 21+
- ID verification result foundation
- proof of delivery
- delivery completion gate
- failed delivery
- return-to-store
- store return confirmation
- `Order.status` handoff
- `OrderAuditLog` cross-domain
- inventory return / review behavior
- stronger idempotency keys
- redaction / audit validation

## 11. Node.js 20 GitHub Actions deprecation carry-forward

- CI is green.
- There is a **non-blocking** Node.js 20 deprecation warning for GitHub Actions
  (`actions/checkout`, `actions/setup-node`, `actions/setup-python` running on
  Node.js 20).
- **Do not fix it in Dr.1.1.O.**
- It should be handled in a **dedicated CI maintenance change** (its own
  reviewable PR), separate from this contract closure.

## 12. Final validation evidence

Commands run from `backend/` against the local `nuberush_test` database, with
their real results at closure:

```text
.venv/bin/python -m pytest tests/ -q -k driver
  → 648 passed, 2643 deselected

.venv/bin/python -m pytest tests/ -q -k "order or inventory"
  → 740 passed, 2551 deselected

.venv/bin/python -m pytest tests/ -q
  → 3288 passed, 3 skipped
```

The 3 skips are the pre-existing RLS skips in `tests/test_rls_bypass.py`
(RLS baseline / helpers not active in the local database, and the runtime-role
identity gate that only runs under `RLS_ACTIVE_CI=1`). They are environmental
and not Dr.1.1 regressions.

## 13. Final closure statement

Dr.1.1 is closed as the backend operational foundation for the Driver App up to
`arrived_at_customer`. Dr.1.2 should begin from this as-built closure, not from
the older Dr.1.1.A planning contract.
