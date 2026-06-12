# Dr.1.1 — Driver Backend Contract Foundations

> **Subphase producing this document:** Dr.1.1.A — Contract Lock + Scope
> Freeze. This document is **docs-only**. It implements no backend, no
> migrations, no endpoints, no models, no frontend, and no mobile app. It
> defines and freezes the contracts that the later Dr.1.1 subphases
> (Dr.1.1.B through Dr.1.1.L) will build against.

## 1. Phase Identity

- **Official phase name:** Dr.1.1 — Driver Backend Contract Foundations.
- **Phase type:** backend foundation, contract-first. Dr.1.1 is the first
  backend phase for the future Driver App.
- **Predecessor:** Dr.1.0 — Mobile Research + Driver App Product Architecture,
  completed, pushed, CI-green, synchronized with `origin/main` at commit
  `0dda707860719eed490197391a28cb11833e0be1` (`docs: add driver app product
  architecture`). Dr.1.0 was research / docs / product architecture only and
  produced no runtime artifact.
- **Governance:** Dr.1.1 is governed like the prior F2.x and Dr.1.0 phases — a
  contract lock first, then diagnosis, subphase execution, validation, and a
  pass/fail report. This document is the **contract lock** for Dr.1.1 and is
  authoritative for its scope, boundaries, domains, and definition of done.
- **This subphase (Dr.1.1.A) is docs-only.** It writes this contract and
  freezes scope. No code, migration, endpoint, model, schema, frontend, or
  mobile artifact is produced under Dr.1.1.A.

## 2. Central Purpose

Dr.1.1 converts Dr.1.0 from documentary architecture into **real backend
foundations** for the future Driver App — **without** building full delivery
execution and **without** building any mobile app.

Dr.1.0 defined the domain model, screen inventory, user flows, backend gap map,
compliance architecture, and stack recommendation. Dr.1.1 takes the
backend-relevant subset of that work and establishes the authoritative
server-side contracts and foundational data layer on which Dr.1.2+ mobile work
will later depend. Dr.1.1 deliberately stops short of a working delivery flow:
it locks contracts, establishes RBAC/tenancy, stands up a minimal driver
identity and assignment foundation, separates driver operational state from the
canonical order lifecycle, and lays audit and idempotency foundations. The
heavy compliance- and inventory-affecting write paths (verification, proof,
failed delivery, return-to-store) are **contract-locked here but not
implemented in Dr.1.1**.

The purpose is to remove backend ambiguity before mobile construction. When
Dr.1.1 closes, a future mobile phase can be planned against stable, tested
backend contracts rather than discovering them mid-build.

## 3. Primary Principle

**Mobile is the operational surface. Backend is the authority.**

The future Driver App requests and displays; it never owns business rules. The
backend decides eligibility, assignment, order state, compliance, proof,
completion, failure, return, inventory effects, and audit truth. The mobile app
renders backend state, captures operational intent, submits it, queues safe
idempotent retries, and reconciles with the backend on reconnect. The mobile
app never finalizes a compliance, payment, lifecycle, or inventory decision
locally.

This principle is absolute and governs every contract in this document. Where
any later contract is ambiguous, it must be resolved in favor of
backend authority.

## 4. Tenancy MVP Decision — Driver Is Store-Bound

For Dr.1.1, the driver tenancy model is **store-bound**. This is a frozen MVP
decision.

- Each driver belongs to exactly one store.
- A non-admin driver has a non-null `store_id`, consistent with the existing
  non-admin store invariant.
- A driver sees only assignments belonging to their own store.
- A driver sees only orders explicitly assigned to them via a valid
  assignment.
- A driver cannot list the store's general order queue.
- A driver cannot operate across multiple stores in Dr.1.1 (no multi-store
  driver operation).

Platform-bound (cross-store) drivers are explicitly **out of scope** for
Dr.1.1 and reserved as a future decision. The existing tenancy primitives
(store membership, path-based `store_id`, 403-collapse anti-probe) are the
basis on which driver self-scope is layered; driver self-scope is **narrower**
than store membership because it is assignment-based, not store-wide.

## 5. Scope In

The following are in scope for Dr.1.1 (across its subphases B–L):

- Backend contract lock (this document).
- Driver RBAC and tenancy (store-bound, self-scope).
- Driver self-scope read access (assignment-based).
- Minimal driver profile foundation.
- Driver eligibility skeleton (backend-computed `can_go_online`).
- Dedicated order-driver assignment model (`OrderDriverAssignment`).
- Assigned-delivery read model (driver-scoped).
- Delivery operational state **separate from** `OrderStatus`.
- Driver audit foundation (backend-authoritative, redacted).
- Driver idempotency foundation (retry-safe state-changing actions).
- Store/Admin oversight read foundation (read-only).
- Future contracts (contract-locked, not implemented) for: 21+ verification,
  proof of delivery, failed delivery, return-to-store, route/navigation
  events, safety/support events, and earnings/performance visibility.

## 6. Scope Out

The following are explicitly excluded from Dr.1.1. None of these may be built,
scaffolded, or partially implemented under any Dr.1.1 subphase:

- Flutter app.
- Mobile screens.
- Customer app.
- Real delivery execution UI.
- Payment movement.
- Payouts.
- Stripe.
- Cashout.
- Real ID scan.
- OCR.
- Barcode parsing.
- Liveness detection.
- Third-party ID verification vendor.
- Raw ID image storage.
- Full ID number storage.
- Background GPS tracking.
- Geofence enforcement.
- Route deviation enforcement.
- Phone masking implementation.
- Notification delivery vendor.
- Live chat.
- Full support workflow.
- Automatic inventory mutation from driver actions.
- Driver rewards.
- Real earnings ledger.

Items in this list that are compliance- or vendor-gated (ID scan, OCR,
liveness, third-party verification, raw ID storage, full ID number storage,
background GPS, geofence, route deviation, phone masking) remain future-only
and require separate legal/compliance review before any future phase may
introduce them.

## 7. Backend Domain Architecture

Dr.1.1 introduces a new conceptual layer above the existing authoritative
backend. It does not replace or bypass existing authority.

**Driver API Boundary** — the future driver-facing and oversight-facing
surface. In Dr.1.1 this boundary is contract-defined, not implemented.

**Driver Domain Services** (new conceptual layer):

- Driver Profile / Eligibility — driver identity, status, approval, and the
  backend-computed `can_go_online` gate.
- Driver Assignment — the dedicated assignment lifecycle linking a driver to an
  order.
- Delivery Operational State — driver-layer micro-states distinct from
  `OrderStatus`.
- Driver Audit — backend-authoritative, redacted driver event timeline.
- Driver Idempotency — retry-safe handling of state-changing driver actions.
- Driver Read Models — driver self-scope read projections.

**Existing Backend Authority** (unchanged, authoritative):

- Orders.
- Inventory.
- Stores.
- Users / RBAC.
- Audit.
- Compliance.

**Hard rule:** the Driver Domain may **not** freely modify Orders or Inventory.
Any effect on canonical order state or inventory is mediated by, and authorized
through, the existing backend authority under its existing rules. The Driver
Domain proposes and records; it does not unilaterally mutate canonical
order/inventory state. In particular, inventory remains backend-owned and
row-locked exactly as today, and no driver action mutates inventory in Dr.1.1.

## 8. Driver Profile Contract

`DriverProfile` is the minimal driver identity foundation. It is associated
with:

- `User` — the underlying authenticated user (Supabase-bridged), role
  `driver`.
- `Store` — the store the driver belongs to (store-bound, per Section 4).
- `status` — the driver's lifecycle status (e.g., active / inactive).
- `approval state` — whether the driver is approved to operate.
- `eligibility baseline` — the minimal inputs the eligibility computation reads.

**Explicitly excluded from `DriverProfile` in Dr.1.1:** documents, vehicles,
training records, background checks, payout setup, and advanced scoring. These
are eligibility inputs or growth features reserved for later subphases/phases
and must not be modeled in Dr.1.1.

The profile is a foundation only. It does not constitute onboarding UX,
document review tooling, or any mobile-facing flow.

## 9. Eligibility Contract

`can_go_online` is **backend-computed**. The mobile app may never compute or
assert eligibility locally.

The eligibility result must be able to express:

- `can_go_online` — boolean.
- `unmet requirements` — the list of reasons the driver cannot go online.
- `driver status`.
- `approval state`.
- `store status`.
- `blockers`.

Minimum future blockers the contract must support:

- user inactive.
- store inactive.
- driver profile missing.
- driver profile inactive.
- approval not approved.

In Dr.1.1 the eligibility computation is a **skeleton**: its contract and the
minimal blockers above are established, with inputs kept minimal. Richer inputs
(documents, vehicle, training, suspension, device health) are future and not
modeled in Dr.1.1.

## 10. Assignment Contract

The assignment is a **dedicated entity**: `OrderDriverAssignment`.

**Hard rule:** do **not** use a direct `assigned_driver_id` column on `orders`.
The assignment is its own model with its own lifecycle.

The assignment must support the following conceptual lifecycle:

- `offered`
- `accepted`
- `declined`
- `expired`
- `assigned`
- `started`
- `completed`
- `canceled`

Clarifications (frozen):

- An assignment does **not** alter inventory.
- An assignment does **not** complete orders.
- An assignment does **not** replace or overload `OrderStatus`.
- A driver's visibility depends on a **valid assignment** — no assignment, no
  visibility of the order.

In Dr.1.1 the assignment model foundation and its read paths are established;
the action endpoints that drive lifecycle transitions are contract-locked
(Sections 16–18) and implemented in later subphases/phases, not in Dr.1.1.

## 11. Delivery Operational State Contract

Driver operational state is **separate from** the canonical order status and
must never overload it.

**Canonical Order Status** (existing, authoritative — unchanged by Dr.1.1):

- `pending`
- `accepted`
- `preparing`
- `ready`
- `out_for_delivery`
- `delivered`
- `returned`
- `canceled`

**Driver Operational State** (new, driver-layer):

- `assigned_to_driver`
- `driver_en_route_to_store`
- `arrived_at_store`
- `pickup_pending`
- `pickup_confirmed`
- `en_route_to_customer`
- `arrived_at_customer`
- `verification_pending`
- `proof_pending`
- `completion_pending`
- `return_required`
- `returning_to_store`
- `return_confirmed`

**Rule:** Driver Operational State **may map to** `OrderStatus`, but it must
**not** overload it. The canonical order status remains the small, authoritative
state machine it is today; fine-grained driver progress lives in the driver
layer. Any mapping from driver operational state to a canonical order
transition is mediated by existing order authority, never written directly by
the driver layer.

## 12. Driver Read Model Contract

A driver **may read**:

- their minimal profile.
- their eligibility.
- their assignments.
- their assigned delivery (minimal).
- allowed actions.
- current delivery state.
- authorized redacted information.

A driver **may not read**:

- the store-wide order list.
- general inventory.
- general audit logs.
- orders not assigned to them.
- other drivers' data.
- admin / internal information.
- global compliance.
- financial / platform data.

This read scope is assignment-based and narrower than store membership. It is
enforced server-side; the mobile app cannot widen it.

## 13. Address Release Boundary

Customer and store information is released progressively, by backend
authorization, according to delivery progress:

- **Before assignment accepted:** limited info only (e.g., store/zone-level,
  restricted-product and ID-required flags). No exact customer address or
  contact.
- **After assignment accepted:** store pickup info.
- **After pickup confirmed / out for delivery:** customer delivery info.
- **After completion / return:** limited historical info (redacted).

The backend owns each release boundary. The mobile app never reveals
information ahead of the authorized boundary.

## 14. Store / Admin Oversight Contract

Oversight of driver activity is read-only and scoped:

- **Store users:** may read oversight for their **own store only**; read-only.
- **Admin:** global read-only oversight across all stores.
- **Driver:** may **not** read the audit / oversight feed.

Oversight is achieved through backend-recorded events (Section 15), not through
any direct coupling between a driver surface and Store/Admin state. The existing
audit read pattern excludes the driver role as a reader; that exclusion is
preserved.

## 15. Driver Audit Contract

Every important driver-related event must be **backend-authoritative** and
recorded in the driver audit foundation.

**Initial events (Dr.1.1 foundation):**

- `driver_profile_created`
- `driver_profile_activated`
- `driver_profile_deactivated`
- `driver_eligibility_checked`
- `driver_online_requested`
- `driver_online_blocked`
- `driver_assigned`
- `driver_assignment_viewed`
- `driver_assignment_accepted`
- `driver_assignment_declined`
- `delivery_state_changed`
- `driver_action_duplicate_rejected`
- `driver_action_idempotency_replayed`

**Future events (contract-locked, not implemented in Dr.1.1):**

- `pickup_confirmed`
- `store_handoff_confirmed`
- `age_verification_passed`
- `age_verification_failed`
- `proof_of_delivery_recorded`
- `delivery_completed`
- `delivery_failed`
- `return_required`
- `return_started`
- `returned_to_store`
- `store_return_confirmed`
- `safety_issue_reported`
- `support_case_opened`

**Redaction rule.** The driver audit must **never** store:

- raw ID image.
- full ID number.
- raw barcode / OCR payload.
- payment credentials.
- unnecessary customer private data.
- raw GPS trails.

Audit events should carry actor, store, driver, order/assignment references,
timestamps, prior/new state where relevant, reason, and redacted metadata only.

## 16. Idempotency Contract

Every future state-changing driver action must be **retry-safe**. Mobile
duplicated requests must not duplicate backend effects.

Examples of actions that must be idempotent:

- accept assignment.
- confirm pickup.
- submit age verification.
- submit proof.
- complete delivery.
- report failed delivery.
- start return.
- confirm return handoff.

**Rule:** duplicate requests carrying the same idempotency key must not
duplicate backend state; the backend either replays the original result or
rejects the duplicate, and records the corresponding audit event
(`driver_action_idempotency_replayed` or `driver_action_duplicate_rejected`).
This extends the existing order idempotency pattern to the driver domain. In
Dr.1.1 the idempotency **foundation** is established; the action endpoints
themselves are contract-locked and implemented later.

## 17. Future Contracts

The following are documented as **contract-lock only** in Dr.1.1 — defined, not
implemented:

- 21+ verification result (manual checklist; pass/fail + redacted metadata;
  no raw ID image, no full ID number; backend accepts result and gates
  completion).
- Proof of delivery (attestation + timestamp + verification binding; "no proof,
  no delivered"; backend finalizes).
- Failed delivery reason codes (structured failure set; backend decides whether
  return is required).
- Return-to-store (restricted failure routes to accountable return; driver
  cannot self-close; store confirms, backend closes; inventory review is
  backend-authorized, not automatic restock).
- Route / navigation events (external navigation handoff only; geofence, route
  deviation, and background tracking are future-only and out of Dr.1.1).
- Safety / support events (incident and case recording foundation; full support
  workflow, phone masking, and chat are future-only).
- Communication boundary (masked/controlled contact is backend-owned;
  implementation is future-only).
- Earnings / performance visibility (read-model placeholder only; no money
  movement, no payout, no ledger).

These contracts exist to keep later subphases and phases consistent. None of
them is built in Dr.1.1.

## 18. Conceptual API Boundary

The following routes are documented as **future** contracts in Dr.1.1.A. They
are **not** implemented in Dr.1.1. They define the intended driver-facing and
oversight surface so later subphases build against a stable shape.

**Driver-facing future read routes:**

- `GET /driver/me`
- `GET /driver/eligibility`
- `GET /driver/assignments`
- `GET /driver/assignments/{assignment_id}`
- `GET /driver/active-delivery`

**Store / Admin oversight future read routes:**

- `GET /stores/{store_id}/driver-assignments`
- `GET /stores/{store_id}/driver-audit`
- `GET /admin/driver-assignments`
- `GET /admin/driver-audit`

**Future action routes (contract-locked only):**

- `POST /driver/assignments/{assignment_id}/accept`
- `POST /driver/assignments/{assignment_id}/decline`
- `POST /driver/deliveries/{delivery_id}/pickup-confirm`
- `POST /driver/deliveries/{delivery_id}/verify-age`
- `POST /driver/deliveries/{delivery_id}/proof`
- `POST /driver/deliveries/{delivery_id}/complete`
- `POST /driver/deliveries/{delivery_id}/fail`
- `POST /driver/deliveries/{delivery_id}/return/start`
- `POST /stores/{store_id}/driver-returns/{return_id}/confirm`

**Clarification:** Dr.1.1.A only documents these contracts. No route in this
section is created, registered, or implemented in Dr.1.1.A, and the action
routes are not implemented anywhere in Dr.1.1.

## 19. Testing Contract

The following test categories are required for the future subphases that
implement the contracts above. They are documented here so each subphase ships
with the right coverage. Dr.1.1.A creates no tests.

- driver cannot access the store order list.
- driver cannot access inventory.
- driver cannot access another driver's assignment.
- driver cannot access another store's assignment.
- driver can read their own assignment.
- inactive driver is blocked by eligibility.
- inactive store blocks eligibility.
- admin can read driver oversight.
- store manager can read own-store driver oversight.
- store manager cannot read other-store driver oversight.
- duplicate idempotency key does not duplicate state.
- driver audit event is redacted.
- driver audit is visible to store/admin only.
- existing order / inventory tests still pass.

The final item is a non-negotiable regression guard: no Dr.1.1 subphase may
break existing order, inventory, permissions, or audit behavior.

## 20. Subphase Order

The approved Dr.1.1 subphase order:

- **A — Contract Lock + Scope Freeze** (this document).
- **B — Driver RBAC + Tenancy Foundation.**
- **C — Driver Profile Foundation.**
- **D — Driver Eligibility Skeleton.**
- **E — Order Driver Assignment Model Foundation.**
- **F — Driver Assigned Delivery Read Model.**
- **G — Delivery Operational State Foundation.**
- **H — Driver Audit Foundation.**
- **I — Driver Action Idempotency Foundation.**
- **J — Store/Admin Driver Oversight Read Foundation.**
- **K — Future Action Contract Schemas.**
- **L — Final Validation + Checkpoint Commit.**

Read/identity/audit/RBAC foundations precede any compliance- or
inventory-adjacent write path. Action write paths remain contract-locked until
their dedicated future phase.

## 21. Success Definition

Dr.1.1 is successful when the following exist:

- backend contract lock.
- store-bound driver tenancy.
- driver self-scope.
- minimal driver profile foundation.
- backend-computed eligibility.
- dedicated assignment model.
- safe assigned-delivery read model.
- operational state separate from `OrderStatus`.
- audit foundation.
- idempotency foundation.
- Store/Admin read-only oversight.
- future contracts for verification / proof / failure / return.

And the following remain true (nothing built):

- no mobile.
- no payments.
- no ID scan.
- no geofence.
- no automatic inventory mutation.

### Validation Commands

After creating this document, run:

```bash
git status --short
git diff --name-only
wc -l docs/dr.1.1-driver-backend-contract-foundations.md
```

If markdownlint exists in the repo, also run the project's corresponding
command to validate this file. (As of Dr.1.1.A there is no markdownlint
configuration, binary, or CI step in this repository, so no markdownlint run
applies.)

### Definition of Done for Dr.1.1.A

- This document exists at
  `docs/dr.1.1-driver-backend-contract-foundations.md`.
- The change is docs-only: exactly one new file, no code, no migrations, no
  endpoints, no models, no schemas, no frontend, no mobile.
- Existing behavior is untouched; no existing file is modified.
