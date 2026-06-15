# Dr.1.2 — Driver Compliance Backend Surface Contract

> **Status:** Contract-lock (Dr.1.2.A). **Doc-only.** This document freezes the
> architecture, boundaries, scope, non-scope, risks, and technical plan for
> Dr.1.2 **before any runtime is implemented**. No endpoint, schema, model,
> migration, or test is created or modified by this phase.
>
> **As-built authority:** `docs/dr.1.1-driver-backend-foundations-closure.md`
> (closure commit `8f4d358f623c88a9b4b8fb0ce73cb88bbc5e52f1`). Dr.1.2 begins
> from the Dr.1.1 **closure**, never from the older Dr.1.1.A planning contract.

---

## 1. Purpose

Dr.1.2 designs and (in later subphases) implements the **backend compliance
surface** of the Driver App, continuing the operational flow from the Dr.1.1
boundary `arrived_at_customer` through age verification, proof of delivery,
delivery completion, failed delivery, and return-to-store — including the
hand-off into the commercial order lifecycle.

This document is the **contract lock** for that work. Its job is to:

- Freeze the architecture and the authority boundaries between the driver
  layer, the orders authority, the inventory authority, and the audit
  authority.
- Declare exactly what is in scope and out of scope for Dr.1.2.
- Lock the protected invariants that every later subphase must preserve.
- Define the state machine, candidate surfaces, audit/redaction/idempotency
  policies, candidate models/schemas, the subphase map, the test strategy, and
  the open decisions.

Nothing in this document is runtime. Names of functions, endpoints, models,
tables, schemas, and events are **candidates / contract concepts**; the final
shapes are confirmed in their own implementation subphases (Dr.1.2.B–J).

---

## 2. Starting Point from Dr.1.1 Closure

Per `docs/dr.1.1-driver-backend-foundations-closure.md`:

- **Dr.1.1 ended at `arrived_at_customer`.** That is the frozen operational
  boundary; Dr.1.2 starts from there.
- **Dr.1.1 implemented 5 GET / 7 POST under `/driver`** (0 PATCH/PUT/DELETE),
  enforced by route-surface guard tests:

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

- **Dr.1.1 did NOT implement:** verify-age / 21+, proof of delivery, complete
  delivery, failed delivery, return-to-store, store return confirmation,
  `Order.status` mutation, inventory mutation, `OrderAuditLog` integration from
  the driver layer, frontend, or mobile.

- **Three state machines already exist and are kept strictly separate**
  (Dr.1.1 closure §8):
  - `OrderDriverAssignment.status` — assignment decision/lifecycle.
  - `DriverDeliveryOperationalState.state` — physical/compliance driver flow.
  - `Order.status` — commercial/authoritative order lifecycle.

- The trailing operational states (`id_verification_pending`, `id_verified`,
  `delivery_completed`, `delivery_failed`, `returning_to_store`,
  `returned_to_store`, `canceled`) are **forward-declared in the enum and the
  DB CHECK constraint** but produced by **no Dr.1.1 endpoint**. Dr.1.2 is what
  activates them.

- The pending `Order.status` hand-off decision was explicitly recorded in
  Dr.1.1 closure §9 and carried forward to Dr.1.2.

---

## 3. Dr.1.2 Scope

Dr.1.2 covers, as a **backend-only compliance surface**:

- verify-age / 21+
- proof of delivery
- complete delivery gate
- failed delivery
- return-to-store
- store return confirmation
- `Order.status` bridge
- `OrderAuditLog` cross-domain audit
- inventory return / review policy
- redaction policy
- strong idempotency
- backend-only compliance surface (no client/UI work of any kind)

---

## 4. Explicit Non-Scope

The following are **explicitly out of all of Dr.1.2** (anti scope-creep):

- Flutter
- mobile app UI
- frontend web UI
- GPS / geofence enforcement
- route deviation
- maps / navigation handoff
- push notifications
- payments
- payouts
- earnings
- dispatch fan-out
- go-online / go-offline
- OCR
- barcode scanning
- liveness detection
- third-party ID verification vendors
- photo storage
- signature storage
- legal retention automation
- GitHub Actions Node.js 20 deprecation fix (its own dedicated CI maintenance
  PR, per Dr.1.1 closure §11)

---

## 5. Protected Invariants

These invariants are **contractually locked**. Every Dr.1.2 subphase must
preserve them; a change that violates one is out of contract.

Carried forward from Dr.1.1 (closure §7):

- **driver-role gated** — only the store-bound driver role reaches `/driver/*`.
- **store-bound** — the driver is bound to their own store.
- **self-scoped** — a driver sees and acts only on their own assignments.
- **anti-enumeration** — a foreign / non-own / missing assignment returns 404,
  never leaking existence across the scope boundary.
- **locking** — `with_for_update` over the assignment + operational-state rows
  (and, for the bridge, the order row) for any operational/commercial
  mutation.
- **idempotency by current state** — re-issuing an action whose destination
  state is already current returns success without re-mutating.
- **no implicit creation** — later operational actions never silently create a
  missing operational-state row.

New for Dr.1.2 (the contractual rules requested for this phase):

1. **Driver service never writes `Order.status` directly.**
2. **Driver service never assigns `OrderStatus.delivered`, `OrderStatus.returned`,
   `OrderStatus.canceled`, or any equivalent directly.**
3. **Driver service proposes outcomes; `orders.py` / the orders authority
   decides and applies all commercial changes.**
4. **The driver → orders bridge is synchronous for now, with locks and audit.**
5. **`OrderAuditLog` records commercial order-status changes.**
6. **Compliance-sensitive events have explicit, redacted audit.**
7. **The driver never auto-restockes inventory.**
8. **Store confirmation is mandatory before `returned` / replenish.**
9. **Proof MVP is redacted metadata, not raw files.**
10. **Verify-age MVP is a backend/manual checklist result, not OCR/vendor.**
11. **Sensitive actions require strong idempotency.**
12. **Complete delivery requires verify-age passed when the order is restricted.**
13. **Failed delivery does not automatically equal `canceled` without an
    explicit commercial decision.**
14. **Dr.1.2 includes no Flutter, mobile UI, frontend web UI, GPS/geofence,
    OCR, third-party ID vendor, payments, payouts, dispatch, or notifications.**

---

## 6. State Machine Architecture

Dr.1.2 advances the **`DriverDeliveryOperationalState.state`** axis from the
Dr.1.1 boundary `arrived_at_customer`, and *proposes* commercial outcomes that
the **orders authority** translates into `Order.status`. The driver axis never
writes the commercial axis.

**Success path** (restricted order shown; the verify-age leg is conditional —
see §11/§13):

```text
arrived_at_customer
→ id_verification_pending
→ id_verified
→ proof submitted
→ delivery_completed
→ orders bridge
→ Order.status delivered
```

**Failure path:**

```text
arrived_at_customer
→ delivery_failed
→ returning_to_store
→ returned_to_store
→ store confirmation
→ orders/inventory authority
→ returned / review / replenish decision
```

Axis ownership during these paths:

- **`DriverDeliveryOperationalState.state`** — the only axis the driver layer
  advances directly (within its own lock + idempotency rules).
- **`OrderDriverAssignment.status`** — whether it advances to `completed` on
  delivery completion is an open decision (§25); Dr.1.1 left it at `started`
  through the operational legs.
- **`Order.status`** — advanced exclusively by the orders authority, triggered
  by a proposed driver outcome through the bridge (§9).

Notes:

- The trailing operational states already exist in the enum and DB CHECK
  constraint; Dr.1.2 makes them reachable through new actions, never by
  loosening or duplicating the constraint.
- `delivery_failed` is an operational state, **not** a commercial verdict. The
  commercial consequence (canceled / returned / review) is the orders
  authority's decision (§13, §25).

---

## 7. Driver Endpoint Candidate Surface

**Candidates only — not implemented in this phase.** They follow the existing
`/driver/assignments/{assignment_id}/...` convention, stay self-scoped and
store-bound, and add no PATCH/PUT/DELETE. Each is gated by
`require_store_bound_driver`.

```text
POST /driver/assignments/{assignment_id}/verify-age
POST /driver/assignments/{assignment_id}/proof
POST /driver/assignments/{assignment_id}/complete
POST /driver/assignments/{assignment_id}/fail
POST /driver/assignments/{assignment_id}/return-to-store
GET  /driver/assignments/{assignment_id}/compliance-state
```

Adding any of these will **intentionally break the route-surface guard tests**
until the guard is updated in the same subphase (§23).

---

## 8. Store-Side Return Confirmation Surface

Return confirmation is a **store-side action, not a driver action**, performed
by a store actor (manager-or-above, matching the existing order role matrix —
to be confirmed in §25/§16). Candidate only:

```text
POST /store/orders/{order_id}/confirm-driver-return
```

The final path **may follow the repo's existing store route conventions**
(e.g. the existing order/store routers and tenancy gates) rather than this
literal path. The contract here is the *capability and authority*, not the URL
string.

---

## 9. Order.status Bridge Architecture

The commercial hand-off is a one-directional bridge from the driver layer into
the orders authority. The driver layer **proposes**; the orders authority
**disposes**.

```text
driver service proposes outcome
orders service validates transition
orders service applies Order.status
orders service writes OrderAuditLog
orders/inventory authority handles stock effects
```

Conceptual bridge entry point (contract concept, **not implemented in this
doc-only phase**):

```text
apply_driver_delivery_outcome(...)
```

Contractual properties of the bridge:

- Lives in / is owned by the **orders authority** (`app/services/orders.py`),
  not the driver service. The driver service calls it; it never reimplements
  the `OrderStatus` transition matrix.
- **Synchronous for now**, executed within the same transaction that advances
  the operational state, under locks on the order + assignment +
  operational-state rows.
- Validates the requested commercial transition through the existing
  `_assert_valid_transition` / `_STATUS_TRANSITIONS` machinery.
- Reuses the existing inventory consume / release / replenish helpers — the
  driver layer never touches inventory directly.
- Writes an `OrderAuditLog` row recording the driver-originated commercial
  change (carrying the driver's `actor_user_id`).
- Commits once, so the operational-state advance, the commercial change, the
  inventory effect, and the audit row all land or roll back atomically.

The final signature of `apply_driver_delivery_outcome(...)` is an open
decision (§25).

---

## 10. Inventory Return / Review Architecture

Inventory is mutated **only** through the inventory/orders authority, and
**only after store confirmation**. The driver layer never restockes.

Explicitly:

```text
delivery_failed does not mutate stock
returning_to_store does not mutate stock
returned_to_store by driver does not mutate stock
only store confirmation can trigger returned/replenish/review flow
driver never auto-restockes
```

Rationale: a driver-reported return is an *intent*, not custody. Until the
store physically confirms receipt, stock stays untouched (the order sits in a
"return in transit / review" posture). On store confirmation, the orders
authority runs the existing replenish path (the same machinery as the
manager-driven `return_order`), writes the commercial audit, and commits once.

---

## 11. Age Verification / 21+ Architecture

MVP approach — **manual / checklist, backend-authorized**. No automation, no
vendor, no document capture.

```text
manual/checklist backend outcome
server timestamp
driver/order/store/assignment context
pass/fail/manual_review outcome
failure reasons
no OCR
no ID image persistence
no raw ID number
no barcode payload
```

Contractual notes:

- The backend **records and authorizes** the result; the app submits a
  structured checklist outcome and cannot self-finalize.
- Verify-age is a **precondition gate** for completing a **restricted** order
  (§13); it is not required for a non-restricted order.
- A failed verify-age routes toward the failed-delivery / return path (§14,
  §15), never toward completion.
- Outcomes: `pass`, `fail`, `manual_review`. Failure reasons come from the
  taxonomy in §14 (and the Dr.1.0.G compliance reason model).
- The persisted record is **redacted metadata only** (§18) — it evidences that
  a check occurred and its outcome, never the identity document.

---

## 12. Proof of Delivery Architecture

MVP proof is **redacted metadata describing a compliant handoff**, never raw
artifacts.

```text
recipient present confirmation
handoff confirmation
restricted items not left unattended
proof method = manual_checklist
safe optional note
server timestamp
no photo storage
no signature storage
```

Contractual notes:

- Proof is **backend-authorized**; the app submits, the backend accepts or
  rejects (out-of-sequence or unverified-restricted proof is rejected).
- Proof **cannot override** a failed/absent compliance check — for restricted
  orders, a passed verify-age is a precondition; proof never substitutes for
  the age gate.
- Restricted product may **not** be left unattended (no leave-at-door, porch,
  lobby, mailbox).
- The optional note must be safe/structured and is subject to the redaction
  policy (§18).

---

## 13. Complete Delivery Architecture

Completion is a **backend transition**, not a local UI state.

- Completion advances the operational state to `delivery_completed` and
  proposes the `delivered` commercial outcome through the bridge (§9).
- **Restricted orders require a passed verify-age** before completion is
  allowed. Attempting to complete a restricted order without `id_verified`
  is rejected.
- **Proof must be submitted before completion** (§12).
- A **failed delivery cannot be completed** — the two paths are mutually
  exclusive.
- On acceptance, the orders authority moves `Order.status` to `delivered`,
  consumes the inventory reservation (existing path), and writes
  `OrderAuditLog` — all atomically with the operational-state advance.
- Whether `OrderDriverAssignment.status` advances to `completed` here is an
  open decision (§25).
- "Restricted order" detection source is an open decision (§25).

---

## 14. Failed Delivery Architecture

A failed delivery records an operational failure with a structured reason; it
does **not** automatically become `canceled` (invariant 13). The commercial
consequence is the orders authority's explicit decision (§9, §25).

Reason taxonomy (candidate, aligned with Dr.1.0 proof/failure design):

```text
customer_unavailable
customer_underage
id_invalid
id_expired
customer_refused
unsafe_location
restricted_product_issue
store_issue
driver_emergency
other_manual_review
```

Contractual notes:

- `fail` advances the operational state to `delivery_failed`.
- For restricted product, a failed delivery normally routes to the
  return-to-store path (§15) rather than leaving product unaccounted.
- No inventory mutation occurs on failure (§10).

---

## 15. Return-to-Store Architecture

When undeliverable product must come back, the driver **initiates** a return
but cannot close it.

- `return-to-store` advances the operational state `delivery_failed →
  returning_to_store`, and a subsequent driver arrival advances
  `returning_to_store → returned_to_store`.
- **The driver cannot self-close the return.** `returned_to_store` is the
  driver asserting physical hand-back; it is **pending store confirmation**.
- **No inventory mutation** occurs at any driver-side step (§10).
- The commercial/stock consequence happens only after store confirmation
  (§16).

---

## 16. Store Return Confirmation Architecture

The store closes the return; the backend finalizes it.

- A store actor confirms physical receipt via the store-side surface (§8).
- On confirmation, the orders/inventory authority decides and applies the
  commercial/stock outcome: `returned` / review / replenish, using the
  existing replenish machinery, writing `OrderAuditLog`, committing once.
- **Store confirmation is mandatory** before any `returned` / replenish
  (invariant 8). Without it, stock and commercial status stay untouched.
- The exact commercial verdict (returned vs a review state) is an open
  decision (§25).

---

## 17. Audit Architecture

Audit is split by domain authority:

```text
OrderAuditLog                          = commercial order status changes
DriverComplianceAuditLog or equivalent = compliance-sensitive driver events
operational_audit pattern              = reused for redaction conventions
```

- **`OrderAuditLog`** (existing `order_audit_logs`) records every commercial
  `Order.status` change, including those originated by the driver bridge.
- **`DriverComplianceAuditLog` (or equivalent)** records compliance-sensitive
  driver events (verify-age, proof, fail, return steps). The final sink/table
  choice is an open decision (§25) — it may be a new table, an extension of the
  operational-audit pattern, or a reuse of an existing log.
- The **`operational_audit.py` pattern** (closed taxonomy, before/after
  allow-lists, deep sensitive-key redaction, JSON-safe payloads) is the
  reference for redaction conventions and should be reused, not reinvented.

Required audit events (candidate names):

```text
driver.verify_age.submitted
driver.verify_age.passed
driver.verify_age.failed
driver.proof.submitted
driver.delivery.completed
driver.delivery.failed
driver.return.started
driver.return.arrived_store
store.return.confirmed
order.status.changed_by_driver_bridge
inventory.return_review_created
inventory.replenished_after_store_confirmation
```

---

## 18. Redaction / Sensitive Data Policy

The compliance records evidence that a check/handoff occurred and its outcome —
never the identity document or a sensitive artifact.

**Prohibited from storage (anywhere — records, audit, notes):**

```text
raw ID image
full ID number
OCR payload
barcode raw payload
biometric data
raw customer signature
sensitive customer photo
```

**Allowed metadata:**

```text
verification_performed
verification_outcome
age_over_21_confirmed
id_expiration_checked
id_not_expired
reason_code
method
server timestamp
driver_profile_id
assignment_id
order_id
store_id
```

A retention policy and legal review are required **before** any future ID
artifact storage; none is introduced in Dr.1.2.

---

## 19. Idempotency Architecture

Sensitive actions use a strong idempotency key in addition to the existing
idempotency-by-current-state behavior.

```text
Header: Idempotency-Key
Scope:  actor_user_id + assignment_id + action + key
same key + same payload      → returns the same result
same key + different payload → returns 409
missing key on sensitive action → returns 400/422
```

Sensitive actions requiring idempotency:

```text
verify-age
proof
complete
fail
return-to-store
store return confirmation
```

Notes:

- This is distinct from order-creation idempotency (`orders.idempotency_key`,
  unique per store) and from operational idempotency-by-state; sensitive
  actions with irreversible side effects (inventory, commercial status) need a
  per-action key to survive offline/retry submission without double effects.
- The idempotency ledger table design is an open decision (§25).

---

## 20. Candidate Models / Tables

**Candidates for later subphases — not implemented by Dr.1.2.A.**

```text
DriverDeliveryVerification
DriverDeliveryProof
DriverDeliveryFailure
DriverDeliveryReturn
DriverComplianceIdempotencyKey
DriverComplianceAuditLog
```

Conventions to follow (matching existing driver models): VARCHAR + CHECK
discriminators for enum-like columns (no PG `ALTER TYPE`); denormalized
`order_id` / `driver_profile_id` / `store_id` read anchors; FK semantics
mirroring `OrderDriverAssignment`; append-only for audit/ledger rows.

---

## 21. Candidate Schemas

**Candidates — not implemented by Dr.1.2.A.** The driver module today has only
read schemas; these introduce the first request bodies.

```text
DriverVerifyAgeRequest
DriverProofSubmitRequest
DriverCompleteDeliveryRequest
DriverFailDeliveryRequest
DriverReturnToStoreRequest
DriverComplianceStateRead
StoreConfirmDriverReturnRequest
```

Request schemas must accept **only redaction-safe fields** (§18); no schema may
carry a raw ID/photo/signature/OCR/barcode field.

---

## 22. Candidate Files Likely to Change Later

(Not changed in this doc-only phase.)

```text
backend/app/api/routes/driver.py
backend/app/services/driver.py
backend/app/schemas/driver.py
backend/app/db/models.py
backend/app/services/orders.py
backend/app/domain/orders_rules.py
backend/app/services/operational_audit.py
backend/app/services/audit.py
backend/alembic/versions/
backend/tests/
```

---

## 23. Test Strategy

Future validation categories (to be implemented alongside each subphase, never
in Dr.1.2.A):

```text
driver RBAC/self-scope
anti-enumeration 404
state transition validity
Order.status bridge authority
OrderAuditLog creation
inventory no-auto-restock
store confirmation required
redaction/no sensitive data persistence
idempotency-key behavior
restricted order complete blocked without verify-age
proof required before complete
failed delivery cannot complete
return flow custody
full backend regression
alembic validation with local DB only
route surface guard updates
```

Note: alembic/pytest are pinned to a **local** database only — never run bare
alembic against `backend/.env` (its `DATABASE_URL` points at live Supabase).

---

## 24. Dr.1.2 Subphase Map

```text
Dr.1.2.A — Contract Lock / Compliance Backend Scope        (this document)
Dr.1.2.B — Compliance Models + Migration Foundation
Dr.1.2.C — Verify Age / 21+ Foundation
Dr.1.2.D — Proof of Delivery Foundation
Dr.1.2.E — Complete Delivery Gate
Dr.1.2.F — Failed Delivery Foundation
Dr.1.2.G — Return-to-Store Foundation
Dr.1.2.H — Store Return Confirmation
Dr.1.2.I — Idempotency / Redaction / Audit Hardening
Dr.1.2.J — Final Validation + Closure
```

---

## 25. Risks / Unresolved Decisions

Open items to resolve before (or within) the relevant implementation subphase:

```text
exact commercial status for delivery_failed
whether OrderStatus needs a review/failed value
final bridge function signature
final audit sink/table choice
final store confirmation route path
restricted order detection source
whether assignment.status becomes completed on delivery completion
idempotency ledger table design
```

Additional context per item:

- **delivery_failed → commercial status:** `OrderStatus` has no `failed` or
  `review` value today (only `canceled` / `returned`); choosing to add one
  requires a PG enum migration (`order_status` is a real PG enum, unlike the
  VARCHAR+CHECK driver enums).
- **bridge signature:** inputs (assignment, proposed outcome, actor, reason,
  idempotency key) and return shape to be locked in Dr.1.2.E.
- **audit sink:** new `DriverComplianceAuditLog` vs extending the
  operational-audit taxonomy vs reusing an existing log; affects the unified
  audit feed (`app/services/audit.py`).
- **restricted detection:** confirm where the backend reads that an order is
  restricted/21+ (product/variant compliance flags reachable from the order).

---

## 26. Validation Checklist

This contract-lock phase (Dr.1.2.A) is valid iff:

```text
[x] doc-only scope
[x] single file created
[x] no backend runtime changed
[x] no frontend/mobile changed
[x] no migrations changed
[x] no tests changed
[x] Dr.1.1 closure used as authority
[x] driver does not write Order.status directly
[x] driver does not auto-restock
[x] store confirmation required
[x] redaction policy included
[x] idempotency policy included
[x] Dr.1.3+ reserved for Flutter/mobile
```
