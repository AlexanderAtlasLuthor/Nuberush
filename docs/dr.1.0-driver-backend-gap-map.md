# Dr.1.0 Driver Backend Gap Map

## Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.F — Backend Gap Analysis + Future Data Model Map
- **Status:** Draft for Dr.1.0 documentation
- **Scope:** documentation only
- **Implementation:** none

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/dr.1.0-driver-screen-inventory.md`,
`docs/dr.1.0-driver-user-flows.md`,
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them.

## Purpose

This document maps the backend capabilities that future Driver App phases will
need. It is a gap analysis and a future data-model map, not an implementation.

Stated clearly:

- **This document does not implement backend functionality.** It introduces no
  endpoints, models, migrations, or schemas.
- **It identifies gaps and future work.** Existing-capability claims are
  deliberately cautious and must be confirmed by a Dr.1.1 backend diagnostic.
- **Backend remains the source of truth.** Eligibility, order state, compliance,
  proof, completion, inventory, and audit are backend-owned.
- **Mobile is the operational surface.** The Driver App requests and displays;
  it does not own business rules.
- **Driver access must be order-scoped, not store-wide.** No driver-facing
  capability exposes store-wide inventory, orders, or administration.
- **Restricted-product compliance and auditability are core backend
  responsibilities.** 21+ verification, proof, return-to-store, and the audit
  timeline are backend-owned, not mobile concerns.

Endpoint paths, model fields, and event names in this document are
**architectural candidates**, not final contracts. Final shapes are decided in
Dr.1.1 (Driver Backend Surface) and its diagnostic.

## Backend Gap Principles

- **Backend authority before mobile action.** Every state-changing driver action
  is validated and recorded server-side.
- **Order-scoped driver access.** Drivers read only offered/assigned orders.
- **Admin/store visibility through backend events.** Oversight consumes the
  backend event stream, not direct mobile state.
- **Compliance-first restricted delivery.** Restricted handling and 21+
  verification are first-class backend concerns.
- **No unattended restricted delivery.** The backend enforces in-person, verified
  handoff for restricted orders.
- **No raw ID image storage in MVP.** Verification persists redacted metadata
  only.
- **Redacted metadata by default.** Sensitive fields are minimized across
  models, reads, and audit.
- **Return-to-store accountability.** Failed restricted deliveries route through
  a backend-owned return the driver cannot self-close.
- **Store handoff accountability.** Pickup release and return receipt are
  store-confirmed and backend-validated.
- **Audit-first lifecycle.** Every meaningful transition emits a compliance-grade
  audit event.
- **Idempotent driver actions.** Critical transitions are idempotent; the backend
  rejects duplicate side effects.
- **Inventory safety remains backend-owned.** Mobile never mutates inventory;
  completion/failure/return effects are server-side.
- **Support and safety events are backend-owned records.** Tickets and incidents
  persist server-side with audit.
- **Future features reserved without implementation.** Growth and
  compliance-upgrade capabilities are documented as reserved, not built now.

## Existing Backend Capability Map

The current NubeRush backend is a layered FastAPI/SQLAlchemy service with Alembic
migrations and an existing route surface for admin and store operations. The
following capabilities are **likely reusable or extendable** for the Driver App
program. Each claim is cautious and **must be verified in the Dr.1.1 diagnostic**;
none is implemented or modified by this document.

- **Auth / session integration** — an existing authentication surface and
  session model. *Likely reusable* for driver authentication and *likely
  extendable* to a driver actor/role; mobile session/token handling must be
  verified in Dr.1.1.
- **Stores** — store entities and store-scoped operations exist. *Likely
  reusable* as the pickup/return store reference for assignments and handoff.
- **Products / variants** — product and variant catalog exists. *Likely reusable*
  read-only for order/pickup context; the Driver App does not manage catalog.
- **Inventory items** — real stock/inventory items exist. *Likely extendable* for
  backend-owned return/failure effects; **mobile must never mutate inventory.**
- **Inventory logs** — inventory movement/adjustment logging exists. *Likely
  extendable* to record return-to-store effects under backend control.
- **Orders** — orders exist with a full lifecycle synchronized with inventory.
  *Likely extendable* for driver-scoped reads and the later delivery-stage
  transitions; the order state machine remains backend-owned and must **not** be
  overloaded with driver micro-states.
- **Admin audit** — a unified admin audit capability exists. *Likely extendable*
  to host the driver delivery/compliance audit timeline; naming and shape are
  architectural until Dr.1.1.
- **Admin dashboard / operations visibility** — admin operations and dashboard
  surfaces exist. *Likely extendable* to surface driver compliance, delivery
  audit, incidents, and support escalations (the Admin/Store visibility bridge).
- **Regulatory / compliance foundations** — admin regulatory/compliance surfaces
  exist with explicit human review. *Likely reusable* as the human-gated
  compliance posture the Driver App must preserve.
- **Store panel operations** — store-scoped operations (orders, inventory,
  earnings, regulatory read surfaces) exist. *Likely extendable* for store-side
  handoff and return confirmation, scoped to the store's own orders.
- **QuickBooks / integration work** — accounting/integration work exists. It is
  **unrelated to the Driver MVP**, but it is evidence of backend integration
  maturity (external connections, scheduled ingestion) that de-risks future
  driver integrations.

The above is a reuse hypothesis, not a commitment. Exact file paths, table
names, and reuse boundaries are **not asserted here** and are to be confirmed by
the Dr.1.1 diagnostic before any implementation.

## Missing Backend Capability Summary

The following capabilities do not exist for the Driver App today and are future
work. "Current likely state" is cautious and to be verified in Dr.1.1.

| Gap area | Current likely state | Required future capability | Driver App dependency | Compliance sensitivity | Phase target | Notes |
|---|---|---|---|---|---|---|
| Driver profile | No driver-specific profile | Driver identity/profile with DOB-driven eligibility input | Account, onboarding | High | Dr.1.1 | Distinct from generic user |
| Driver documents | No driver document store | Document records, states, expiry, review | Documents, eligibility | High | Dr.1.1 | Secure handling policy |
| Driver vehicles | No vehicle model | Delivery-vehicle records + approval | Vehicle, eligibility | Medium | Dr.1.1 | No ride-class logic |
| Driver training | No training records | Training completion tracking | Training, eligibility | High | Dr.1.1 | Restricted/21+ modules |
| Policy acknowledgments | No ack records | Versioned policy acknowledgments | Onboarding, eligibility | Critical | Dr.1.1 | Audited acks |
| Driver eligibility | No driver eligibility compute | Server-side can_go_online aggregate | Go online | Critical | Dr.1.1 | Single trusted gate |
| Driver availability / online sessions | No availability model | Online/offline session tracking | Online state | High | Dr.1.1 | Audited transitions |
| Delivery offers | No offer model | Time-boxed offers with privacy boundary | Offers | High | Dr.1.1 | Pre-accept privacy |
| Driver assignment | No assignment model | Dedicated assignment lifecycle | Assignment | High | Dr.1.1 | Not assigned_driver_id only |
| Driver-scoped order reads | Orders not driver-scoped | Order reads filtered to driver assignments | Assigned deliveries | High | Dr.1.1 | No all-store list |
| Active delivery state | No driver-layer state | Driver delivery state mapped to order lifecycle | Active delivery | Critical | Dr.1.1 | No OrderStatus overload |
| Pickup confirmation | No pickup-confirm action | Backend-authorized pickup transition | Store pickup | High | Dr.1.1 | Needs handoff |
| Store handoff | No handoff validation | Store PIN/confirmation validation | Handoff | Critical | Dr.1.1 | No pickup if invalid |
| Customer contact event | No contact event | Masked-contact event record | Customer contact | Medium | Dr.1.1 | No phone exposure |
| Age / ID verification result | No verification record | 21+ verification result (redacted) | Verification | Critical | Dr.1.1 | No raw ID images |
| Proof of delivery | No proof record | Backend-validated proof bound to completion | Proof | Critical | Dr.1.1 | No proof, no delivered |
| Delivery completion authorization | No completion gate | Backend completion authorization | Complete delivery | Critical | Dr.1.1 | Requires proof+verification |
| Failed delivery | No failure record | Structured failure + return decision | Failed delivery | Critical | Dr.1.1 | Decides return |
| Return-to-store | No return workflow | Backend-owned return record | Return-to-store | Critical | Dr.1.1 | Driver cannot self-close |
| Store return confirmation | No return validation | Store-confirmed return + inventory review | Store return | Critical | Dr.1.1 | Backend inventory review |
| Safety reports | No safety record | Safety/incident report persistence | Safety toolkit | High | Dr.1.4 | Oversight visibility |
| Support cases | No driver support cases | Support ticket persistence + routing | Support | Medium | Dr.1.4 | Active-delivery context |
| Driver earnings read model future | No driver earnings read | Estimated-earnings read model (no payout) | Earnings | Low | Dr.1.6 | Visibility only |
| Driver performance read model future | No driver performance read | Performance metrics read model | Performance | Medium | Dr.1.6 | Compliance signals |
| Notification device tokens | No driver device tokens | Device token registration | Notifications | Medium | Dr.1.2 | Push foundation |
| Push notification events | No driver push events | Backend-triggered push events | Notifications | Medium | Dr.1.4 | Compliance pushes |
| Geofence validation | No geofence validation | Arrival/proximity validation | Geofence | High | Dr.1.4 | Distance enforcement |
| Audit timeline | Admin audit exists | Driver delivery/compliance timeline | Audit | Critical | Dr.1.1 | No raw ID data |
| Idempotency keys / action dedupe | Unknown coverage | Idempotency keys for driver actions | Reliability | High | Dr.1.1 | Reject duplicate effects |
| Offline retry reconciliation | No reconcile path | Idempotent reconciliation of queued actions | Offline recovery | High | Dr.1.1 | Depends on dedupe |

## Required Future Endpoint Map

The following are **candidate endpoint families**, not final REST contracts.
Paths, verbs, and payloads are decided in Dr.1.1. Each family lists purpose,
candidate operations, primary actor, backend decisions, data returned to mobile,
audit events, compliance sensitivity, phase target, and notes.

### Driver profile endpoints

- **Purpose:** read and maintain the driver's identity profile.
- **Candidate operations:** read profile; submit/update profile fields.
- **Primary actor:** Driver (self); Admin (read).
- **Backend decisions:** validates fields; computes DOB-derived 21+ eligibility
  input; owns immutable-after-approval rules.
- **Data returned to mobile:** profile, status, approval state (read-mostly).
- **Audit events:** `driver_profile_submitted`.
- **Compliance sensitivity:** High (DOB feeds the age gate).
- **Phase target:** Dr.1.1.
- **Notes:** driver reads only its own profile.

### Driver document endpoints

- **Purpose:** upload and track authorization documents.
- **Candidate operations:** list documents; submit/resubmit document; read
  status.
- **Primary actor:** Driver (self); Admin (review).
- **Backend decisions:** approval/rejection and expiry; whether the set satisfies
  requirements.
- **Data returned to mobile:** document states, reasons, expiry.
- **Audit events:** `driver_document_uploaded`, `driver_document_approved`,
  `driver_document_rejected`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** secure handling; no local approval.

### Vehicle endpoints

- **Purpose:** register and track the delivery vehicle.
- **Candidate operations:** add vehicle; upload vehicle documents; set active
  vehicle; read status.
- **Primary actor:** Driver (self); Admin (review).
- **Backend decisions:** vehicle approval; document expiry; active-vehicle
  validity.
- **Data returned to mobile:** vehicle records and approval state.
- **Audit events:** `vehicle_submitted`, `vehicle_approved`, `vehicle_rejected`.
- **Compliance sensitivity:** Medium.
- **Phase target:** Dr.1.1.
- **Notes:** no passenger-capacity/ride-class fields.

### Driver training endpoints

- **Purpose:** present and record training completion.
- **Candidate operations:** list modules; mark lesson complete; read completion.
- **Primary actor:** Driver (self).
- **Backend decisions:** records completion as an eligibility signal.
- **Data returned to mobile:** module list and completion state.
- **Audit events:** `training_completed`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** restricted/21+ modules required for restricted delivery.

### Policy acknowledgment endpoints

- **Purpose:** record acknowledgment of restricted/no-unattended/return policies.
- **Candidate operations:** read required policies; submit acknowledgments.
- **Primary actor:** Driver (self).
- **Backend decisions:** records acks with audit; treats as eligibility signal.
- **Data returned to mobile:** required policies and current ack state.
- **Audit events:** `policy_acknowledged`.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** versioned re-acknowledgment on policy change (future).

### Driver eligibility endpoint

- **Purpose:** expose the single server-computed eligibility decision.
- **Candidate operations:** read eligibility / can_go_online with reasons.
- **Primary actor:** Driver (self); Admin (read).
- **Backend decisions:** aggregates documents, vehicle, training, policy,
  suspension, status into one decision.
- **Data returned to mobile:** eligibility boolean and unmet-requirement list.
- **Audit events:** none directly (online transition emits its own).
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** the authoritative gate consumed by availability/offers.

### Driver availability endpoint

- **Purpose:** manage online/offline/pause state.
- **Candidate operations:** go online; go offline; pause/resume; read session.
- **Primary actor:** Driver (self).
- **Backend decisions:** authorizes online based on eligibility + reported device
  health.
- **Data returned to mobile:** authorized availability state and times.
- **Audit events:** `driver_online`, `driver_offline`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** blocked if eligibility/permissions fail.

### Delivery offer endpoint

- **Purpose:** deliver time-boxed offers within the pre-accept privacy boundary.
- **Candidate operations:** receive/read current offer; observe timer.
- **Primary actor:** Driver (self); backend (issuer).
- **Backend decisions:** offer eligibility; timer/expiry; withholds exact
  customer details pre-accept.
- **Data returned to mobile:** store info, approximate dropoff zone, estimates,
  restricted/ID flags, timer.
- **Audit events:** `delivery_offered`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** zone-level dropoff only pre-accept.

### Assignment accept/decline endpoints

- **Purpose:** capture accept/decline and drive the assignment lifecycle.
- **Candidate operations:** accept offer; decline offer (with reason).
- **Primary actor:** Driver (self).
- **Backend decisions:** validates eligibility/availability; creates assignment;
  releases customer details on accept; may reassign on decline.
- **Data returned to mobile:** assignment state; post-accept customer details.
- **Audit events:** `delivery_accepted`, `delivery_declined`, `driver_assigned`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** no penalty logic in the MVP.

### Driver-scoped assigned orders

- **Purpose:** list/read the driver's offered and assigned orders only.
- **Candidate operations:** list assigned; read assigned order detail.
- **Primary actor:** Driver (self).
- **Backend decisions:** enforces order-scoping to the driver's assignments.
- **Data returned to mobile:** driver-scoped order summaries/details.
- **Audit events:** none directly.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** **no all-store order list**; RBAC/tenancy critical.

### Active delivery endpoint

- **Purpose:** expose the current delivery state and next valid action.
- **Candidate operations:** read active delivery; request next transition.
- **Primary actor:** Driver (self).
- **Backend decisions:** maps driver-layer progress to the order lifecycle;
  authorizes transitions.
- **Data returned to mobile:** current state, order summary, next action.
- **Audit events:** transition-specific (see below).
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** does not overload OrderStatus with micro-states.

### Pickup confirmation endpoint

- **Purpose:** confirm pickup after handoff and checklist.
- **Candidate operations:** mark en route to store; mark arrived; confirm pickup.
- **Primary actor:** Driver (self).
- **Backend decisions:** authorizes pickup only with assignment + valid handoff +
  compliance.
- **Data returned to mobile:** updated delivery state.
- **Audit events:** `en_route_to_store`, `arrived_at_store`, `pickup_confirmed`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** pickup ≠ inventory consumption by mobile.

### Store handoff endpoint

- **Purpose:** validate store-side release of the order.
- **Candidate operations:** start handoff; submit store PIN/confirmation.
- **Primary actor:** Driver (self); Store employee (PIN source).
- **Backend decisions:** validates the handoff; blocks pickup if invalid.
- **Data returned to mobile:** handoff success/failure.
- **Audit events:** `store_handoff_started`, `store_handoff_confirmed`.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** store accountable for release.

### Out-for-delivery transition endpoint

- **Purpose:** transition to out-for-delivery and release the customer address.
- **Candidate operations:** mark out for delivery.
- **Primary actor:** Driver (self).
- **Backend decisions:** releases exact customer address post-pickup; validates
  transition.
- **Data returned to mobile:** customer address and delivery notes.
- **Audit events:** `out_for_delivery`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.1.
- **Notes:** address only after pickup.

### Customer contact event endpoint

- **Purpose:** record masked customer-contact attempts.
- **Candidate operations:** initiate masked call/message; record contact event.
- **Primary actor:** Driver (self).
- **Backend decisions:** owns number masking and the allowed message set.
- **Data returned to mobile:** masked channel; quick-message set.
- **Audit events:** `customer_contacted`.
- **Compliance sensitivity:** Medium.
- **Phase target:** Dr.1.1.
- **Notes:** **no personal phone exposure.**

### Age/ID verification endpoint

- **Purpose:** record the 21+ manual verification result.
- **Candidate operations:** start verification; submit result (pass/fail +
  reason).
- **Primary actor:** Driver (self).
- **Backend decisions:** accepts/records the result; gates completion on it.
- **Data returned to mobile:** verification acceptance; next step.
- **Audit events:** `verification_started`, `age_verification_passed`,
  `age_verification_failed`.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** **redacted metadata only; no raw ID images, no full ID numbers.**

### Proof of delivery endpoint

- **Purpose:** record and validate proof bound to the verification result.
- **Candidate operations:** submit attestation + timestamp (+ future proof
  elements).
- **Primary actor:** Driver (self).
- **Backend decisions:** validates proof requirements; binds verification pass.
- **Data returned to mobile:** proof acceptance.
- **Audit events:** `proof_of_delivery_recorded`.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** **no proof, no delivered.**

### Complete delivery endpoint

- **Purpose:** authorize and record delivery completion.
- **Candidate operations:** submit completion.
- **Primary actor:** Driver (self).
- **Backend decisions:** authorizes completion; requires proof + verification for
  restricted orders; validates proximity.
- **Data returned to mobile:** completion confirmation + summary.
- **Audit events:** `delivery_completed`.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** earnings visibility only; no payment movement.

### Failed delivery endpoint

- **Purpose:** record a structured failure and decide whether return is required.
- **Candidate operations:** submit failure reason.
- **Primary actor:** Driver (self).
- **Backend decisions:** accepts the failure; decides return requirement; no
  mobile inventory call.
- **Data returned to mobile:** failure acceptance; required next step.
- **Audit events:** `delivery_failed`, `customer_unavailable` (when applicable).
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** restricted failure requires return.

### Return-to-store endpoint

- **Purpose:** start and track the return of undeliverable restricted product.
- **Candidate operations:** mark return required; start return.
- **Primary actor:** Driver (self).
- **Backend decisions:** owns the return requirement; prevents driver
  self-closing.
- **Data returned to mobile:** return state + originating store.
- **Audit events:** `return_required`, `return_started`.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** route + reason carried from failure.

### Store return confirmation endpoint

- **Purpose:** validate the store's receipt of a return and close it.
- **Candidate operations:** submit store return PIN/confirmation; close return.
- **Primary actor:** Store employee (confirm); Driver (submit).
- **Backend decisions:** validates the return; triggers inventory review; closes
  it.
- **Data returned to mobile:** return closure.
- **Audit events:** `returned_to_store`, `store_return_confirmed`.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** inventory review is backend-controlled.

### Safety report endpoint

- **Purpose:** persist safety/incident reports and route to oversight.
- **Candidate operations:** report incident; share location/route (future);
  cancel for safety.
- **Primary actor:** Driver (self); Support/admin (consume).
- **Backend decisions:** records the safety event; ties safety cancel to
  delivery/return outcome.
- **Data returned to mobile:** acknowledgment; support routing.
- **Audit events:** `safety_issue_reported`.
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.4.
- **Notes:** always reachable.

### Support ticket endpoint

- **Purpose:** create and track driver support cases.
- **Candidate operations:** create case (category + context); read case status.
- **Primary actor:** Driver (self); Support/admin (manage).
- **Backend decisions:** owns case lifecycle and routing.
- **Data returned to mobile:** case status.
- **Audit events:** `support_case_opened`, `app_issue_reported`.
- **Compliance sensitivity:** Medium.
- **Phase target:** Dr.1.4.
- **Notes:** messages/attachments future.

### Driver earnings read endpoint (future)

- **Purpose:** expose estimated earnings and counts — visibility only.
- **Candidate operations:** read earnings summary; read counts/history.
- **Primary actor:** Driver (self).
- **Backend decisions:** owns the read model; **no money movement.**
- **Data returned to mobile:** estimates, counts, history (read-only).
- **Audit events:** none directly.
- **Compliance sensitivity:** Low.
- **Phase target:** Dr.1.6.
- **Notes:** **no payouts, cashout, Stripe, or payment movement.**

### Driver performance read endpoint (future)

- **Purpose:** expose backend-computed performance metrics.
- **Candidate operations:** read performance dashboard.
- **Primary actor:** Driver (self); Admin (read).
- **Backend decisions:** computes all metrics from authoritative events.
- **Data returned to mobile:** metrics (read-only).
- **Audit events:** none directly.
- **Compliance sensitivity:** Medium.
- **Phase target:** Dr.1.6.
- **Notes:** includes compliance signals.

### Notification device token endpoint

- **Purpose:** register/unregister push device tokens.
- **Candidate operations:** register token; update preferences; unregister.
- **Primary actor:** Driver (self).
- **Backend decisions:** owns token lifecycle and push targeting.
- **Data returned to mobile:** registration acknowledgment.
- **Audit events:** none directly.
- **Compliance sensitivity:** Medium.
- **Phase target:** Dr.1.2 (foundation).
- **Notes:** compliance-critical pushes not fully suppressible.

### Geofence validation endpoint

- **Purpose:** validate arrival/proximity for pickup and completion.
- **Candidate operations:** validate store arrival; validate completion
  proximity.
- **Primary actor:** Driver (self); backend (validator).
- **Backend decisions:** validates proximity; may gate pickup/completion.
- **Data returned to mobile:** validation result; zone warnings.
- **Audit events:** none directly (the gated transition emits its own).
- **Compliance sensitivity:** High.
- **Phase target:** Dr.1.4.
- **Notes:** legal/restricted zones; privacy/retention review.

### Audit timeline endpoint

- **Purpose:** expose the driver/delivery audit timeline to oversight.
- **Candidate operations:** read timeline (admin/store-scoped).
- **Primary actor:** Admin (full); Store (its orders).
- **Backend decisions:** owns and scopes the timeline; **no raw ID data.**
- **Data returned to mobile:** none directly (oversight surface, not a driver
  screen).
- **Audit events:** consumes all delivery/compliance events.
- **Compliance sensitivity:** Critical.
- **Phase target:** Dr.1.1.
- **Notes:** read by Store/Admin panels, not the Driver App.

## Future Data Model Map

The following are **candidate future models**, not schemas. Field lists are
illustrative; final shapes (types, constraints, relationships) are decided in
Dr.1.1. Several model rules are architectural requirements and are called out
explicitly.

### DriverProfile

- **Purpose:** authoritative driver identity and status.
- **Likely owner / scope:** driver-owned record; one per driver.
- **Key candidate fields:** legal name, verified phone, verified email, date of
  birth, photo reference, operating city/zone, status, approval state.
- **Tenancy relationship:** driver-scoped; may relate to one or more stores
  depending on the future operating model.
- **Privacy / redaction notes:** DOB and contact are sensitive; expose minimally;
  DOB drives eligibility but is not client-trusted.
- **Audit relationship:** profile submission/approval events.
- **Phase target:** Dr.1.1.
- **Notes:** distinct from a generic user account.

### DriverDocument

- **Purpose:** authorization documents and their lifecycle.
- **Likely owner / scope:** driver-owned; many per driver.
- **Key candidate fields:** type, secure storage reference, state, decision
  reason, expiry, timestamps.
- **Tenancy relationship:** driver-scoped.
- **Privacy / redaction notes:** sensitive; stored under the secure
  document-handling policy; not exposed beyond status to non-admins.
- **Audit relationship:** upload/approve/reject events.
- **Phase target:** Dr.1.1.
- **Notes:** review is backend/admin-owned.

### DriverVehicle

- **Purpose:** delivery vehicle record and approval.
- **Likely owner / scope:** driver-owned; one active per driver.
- **Key candidate fields:** make, model, year, color, plate, active flag,
  approval state, linked registration/insurance documents.
- **Tenancy relationship:** driver-scoped.
- **Privacy / redaction notes:** plate is identifying; expose minimally.
- **Audit relationship:** submit/approve/reject events.
- **Phase target:** Dr.1.1.
- **Notes:** **no passenger-capacity or ride-class fields.**

### DriverTrainingCompletion

- **Purpose:** record completion of required training modules.
- **Likely owner / scope:** driver-owned; one per module per driver.
- **Key candidate fields:** module key, completion timestamp, version.
- **Tenancy relationship:** driver-scoped.
- **Privacy / redaction notes:** low sensitivity.
- **Audit relationship:** `training_completed` events.
- **Phase target:** Dr.1.1.
- **Notes:** feeds eligibility.

### DriverPolicyAcknowledgment

- **Purpose:** record acknowledgment of required policies.
- **Likely owner / scope:** driver-owned; one per policy version per driver.
- **Key candidate fields:** policy key, version, acknowledgment timestamp.
- **Tenancy relationship:** driver-scoped.
- **Privacy / redaction notes:** low sensitivity.
- **Audit relationship:** `policy_acknowledged` events.
- **Phase target:** Dr.1.1.
- **Notes:** supports versioned re-acknowledgment.

### DriverAvailabilitySession

- **Purpose:** track online/offline/pause sessions.
- **Likely owner / scope:** driver-owned; many per driver over time.
- **Key candidate fields:** start/end timestamps, state, online/active duration.
- **Tenancy relationship:** driver-scoped.
- **Privacy / redaction notes:** session timing only; no continuous location in
  the MVP.
- **Audit relationship:** `driver_online` / `driver_offline` events.
- **Phase target:** Dr.1.1.
- **Notes:** availability is server-authorized.

### OrderDriverAssignment

- **Purpose:** the dedicated assignment lifecycle linking a driver to an order.
- **Likely owner / scope:** order- and driver-related; its own lifecycle.
- **Key candidate fields:** order reference, driver reference, assignment state
  (offered/accepted/declined/canceled/expired/completed), timestamps, decline
  reason.
- **Tenancy relationship:** scopes driver order access; ties to the order's
  store.
- **Privacy / redaction notes:** gates customer-detail release until accepted.
- **Audit relationship:** offer/accept/decline/assigned events.
- **Phase target:** Dr.1.1.
- **Notes:** **must be a dedicated model, not just an `assigned_driver_id` on the
  order.**

### DeliveryAttempt

- **Purpose:** model driver-layer delivery progress and outcomes without
  inflating the order state machine.
- **Likely owner / scope:** per assignment; one or more attempts.
- **Key candidate fields:** assignment reference, driver-layer state, outcome,
  failure reason, timestamps.
- **Tenancy relationship:** scoped via the assignment/order.
- **Privacy / redaction notes:** references, not raw customer data.
- **Audit relationship:** transition events (arrived, out for delivery, failed,
  etc.).
- **Phase target:** Dr.1.1.
- **Notes:** **must not overload OrderStatus with every driver micro-state.**

### DeliveryProof

- **Purpose:** record proof bound to completion.
- **Likely owner / scope:** per delivery attempt/assignment.
- **Key candidate fields:** attestation, timestamp, verification-result
  reference, (future) GPS/PIN/signature/photo references.
- **Tenancy relationship:** scoped via the assignment/order.
- **Privacy / redaction notes:** future photo/signature must avoid capturing ID
  documents.
- **Audit relationship:** `proof_of_delivery_recorded`.
- **Phase target:** Dr.1.1.
- **Notes:** **must be backend-validated before completion** — no proof, no
  delivered.

### AgeVerificationResult

- **Purpose:** record the 21+ verification outcome.
- **Likely owner / scope:** per delivery attempt/assignment.
- **Key candidate fields:** result (pass/fail), failure reason, redacted check
  metadata, timestamp.
- **Tenancy relationship:** scoped via the assignment/order.
- **Privacy / redaction notes:** **must not store raw ID images or full ID
  numbers in the MVP**; redacted metadata only.
- **Audit relationship:** `age_verification_passed` / `age_verification_failed`.
- **Phase target:** Dr.1.1.
- **Notes:** completion depends on an accepted pass for restricted orders.

### StoreHandoff

- **Purpose:** record accountable store release at pickup.
- **Likely owner / scope:** per assignment; store-confirmed.
- **Key candidate fields:** assignment reference, store reference, confirmation
  method (PIN), confirming employee reference, timestamp.
- **Tenancy relationship:** ties to the store's order; store-confirmed.
- **Privacy / redaction notes:** employee reference minimized.
- **Audit relationship:** `store_handoff_started` / `store_handoff_confirmed`.
- **Phase target:** Dr.1.1.
- **Notes:** pickup blocked without a valid handoff.

### ReturnToStoreRecord

- **Purpose:** model the accountable return of undeliverable restricted product.
- **Likely owner / scope:** per failed restricted delivery; store-confirmed.
- **Key candidate fields:** assignment/order reference, return reason, state,
  store confirmation, timestamps, inventory-review reference.
- **Tenancy relationship:** ties to the originating store.
- **Privacy / redaction notes:** references only.
- **Audit relationship:** `return_required` / `return_started` /
  `returned_to_store` / `store_return_confirmed`.
- **Phase target:** Dr.1.1.
- **Notes:** **must prevent the driver from self-closing restricted returns.**

### DriverSafetyReport

- **Purpose:** persist safety/incident reports.
- **Likely owner / scope:** driver-created; oversight-visible.
- **Key candidate fields:** type, context references, location share (scoped),
  timestamp, status.
- **Tenancy relationship:** driver-scoped; visible to support/admin.
- **Privacy / redaction notes:** location sharing scoped to oversight, not
  public.
- **Audit relationship:** `safety_issue_reported`.
- **Phase target:** Dr.1.4.
- **Notes:** safety cancels still route restricted product to return.

### DriverSupportCase

- **Purpose:** persist driver support tickets.
- **Likely owner / scope:** driver-created; support/admin-managed.
- **Key candidate fields:** category, active-delivery context reference, status,
  timestamps; (future) messages/attachments.
- **Tenancy relationship:** driver-scoped; support/admin-visible.
- **Privacy / redaction notes:** attachments (future) must avoid sensitive ID
  data.
- **Audit relationship:** `support_case_opened`, `app_issue_reported`.
- **Phase target:** Dr.1.4.
- **Notes:** messages/attachments future.

### DriverPerformanceSnapshot

- **Purpose:** store periodic, backend-computed performance metrics.
- **Likely owner / scope:** driver-scoped; periodic snapshots.
- **Key candidate fields:** completed/failed counts, return rate, on-time rates,
  acceptance/decline/cancellation, proof completion, compliance incidents,
  restricted success, audit-cleanliness score, period.
- **Tenancy relationship:** driver-scoped; admin-visible.
- **Privacy / redaction notes:** aggregates only.
- **Audit relationship:** derived from authoritative events.
- **Phase target:** Dr.1.6.
- **Notes:** read model; no payment data.

### DriverNotificationDevice

- **Purpose:** register push device tokens and preferences.
- **Likely owner / scope:** driver-owned; one or more devices.
- **Key candidate fields:** device token, platform, preferences, active flag.
- **Tenancy relationship:** driver-scoped.
- **Privacy / redaction notes:** token is sensitive; store securely.
- **Audit relationship:** none directly.
- **Phase target:** Dr.1.2.
- **Notes:** compliance-critical pushes not fully suppressible.

### DriverLocationEvent (future)

- **Purpose:** capture location events for arrival/safety where justified.
- **Likely owner / scope:** driver-scoped; high-volume, future.
- **Key candidate fields:** coordinates, accuracy, purpose, timestamp,
  retention/expiry.
- **Tenancy relationship:** driver-scoped.
- **Privacy / redaction notes:** **carefully scoped for privacy**; minimized
  retention; collected only for a justified purpose (arrival validation, active
  safety share), subject to legal review.
- **Audit relationship:** referenced by safety/geofence events, not raw-logged.
- **Phase target:** future (not MVP).
- **Notes:** background location is a future, privacy-reviewed capability.

## Future Migration Map

This section maps **likely migration groups** for future phases. It does not
write migrations or define migration filenames; table names are illustrative.
Each group lists reason, likely tables, high-risk constraints, compliance/privacy
concerns, and phase target.

### Driver profiles / account extension

- **Reason:** introduce driver identity distinct from generic users.
- **Likely tables:** driver profile (and any account-link extension).
- **High-risk constraints:** uniqueness per driver; relationship to the auth
  identity; status enum.
- **Compliance/privacy concerns:** DOB and contact handling; minimal exposure.
- **Phase target:** Dr.1.1.

### Driver documents

- **Reason:** store and track authorization documents.
- **Likely tables:** driver document.
- **High-risk constraints:** state enum; expiry; secure-reference integrity.
- **Compliance/privacy concerns:** sensitive document storage policy; no raw
  surfacing.
- **Phase target:** Dr.1.1.

### Driver vehicles

- **Reason:** store delivery-vehicle records and approval.
- **Likely tables:** driver vehicle (with links to vehicle documents).
- **High-risk constraints:** single active vehicle; approval enum.
- **Compliance/privacy concerns:** plate is identifying.
- **Phase target:** Dr.1.1.

### Driver training / policy acknowledgments

- **Reason:** record training completion and policy acknowledgments.
- **Likely tables:** training completion; policy acknowledgment.
- **High-risk constraints:** uniqueness per module/policy version per driver.
- **Compliance/privacy concerns:** versioned acks for compliance evidence.
- **Phase target:** Dr.1.1.

### Availability sessions

- **Reason:** track online/offline sessions.
- **Likely tables:** availability session.
- **High-risk constraints:** open/close consistency; state enum.
- **Compliance/privacy concerns:** session timing only; no continuous location.
- **Phase target:** Dr.1.1.

### Assignment lifecycle

- **Reason:** dedicated assignment model linking driver and order.
- **Likely tables:** order-driver assignment.
- **High-risk constraints:** state machine; uniqueness of active assignment per
  order; relationship to order/store.
- **Compliance/privacy concerns:** gates customer-detail release.
- **Phase target:** Dr.1.1.

### Delivery attempts

- **Reason:** model driver-layer progress without overloading order status.
- **Likely tables:** delivery attempt.
- **High-risk constraints:** mapping to the order lifecycle; outcome enum.
- **Compliance/privacy concerns:** references only.
- **Phase target:** Dr.1.1.

### Store handoff

- **Reason:** record accountable store release at pickup.
- **Likely tables:** store handoff.
- **High-risk constraints:** confirmation integrity; link to assignment/store.
- **Compliance/privacy concerns:** employee reference minimized.
- **Phase target:** Dr.1.1.

### Age verification result

- **Reason:** persist 21+ verification outcomes.
- **Likely tables:** age verification result.
- **High-risk constraints:** result enum; one-per-attempt linkage.
- **Compliance/privacy concerns:** **no raw ID images or full ID numbers**;
  redacted metadata only.
- **Phase target:** Dr.1.1.

### Delivery proof

- **Reason:** persist proof bound to completion.
- **Likely tables:** delivery proof.
- **High-risk constraints:** link to verification result; completion gating.
- **Compliance/privacy concerns:** future media must avoid ID documents.
- **Phase target:** Dr.1.1.

### Failed delivery / return-to-store

- **Reason:** record failures and the accountable return workflow.
- **Likely tables:** failure outcome (on the attempt) and return-to-store record.
- **High-risk constraints:** return state machine; prevent self-close;
  inventory-review linkage.
- **Compliance/privacy concerns:** restricted product accountability.
- **Phase target:** Dr.1.1.

### Safety reports

- **Reason:** persist safety/incident reports.
- **Likely tables:** driver safety report.
- **High-risk constraints:** type enum; oversight visibility scoping.
- **Compliance/privacy concerns:** scoped location sharing; abuse prevention.
- **Phase target:** Dr.1.4.

### Support cases

- **Reason:** persist driver support tickets.
- **Likely tables:** driver support case (and future messages/attachments).
- **High-risk constraints:** status lifecycle; context linkage.
- **Compliance/privacy concerns:** attachments must avoid sensitive ID data.
- **Phase target:** Dr.1.4.

### Notification devices

- **Reason:** register push device tokens and preferences.
- **Likely tables:** driver notification device.
- **High-risk constraints:** token uniqueness; active-flag management.
- **Compliance/privacy concerns:** tokens stored securely.
- **Phase target:** Dr.1.2.

### Performance snapshots

- **Reason:** store periodic performance metrics.
- **Likely tables:** driver performance snapshot.
- **High-risk constraints:** period uniqueness; derivation from events.
- **Compliance/privacy concerns:** aggregates only; no payment data.
- **Phase target:** Dr.1.6.

### Geofence / location events (future)

- **Reason:** support arrival validation and active safety where justified.
- **Likely tables:** geofence/zone definitions; driver location event (future).
- **High-risk constraints:** high-volume location data; retention limits.
- **Compliance/privacy concerns:** **carefully scoped for privacy**; legal review;
  minimized retention.
- **Phase target:** Dr.1.4 (zones) / future (continuous location).

## RBAC Gap Analysis

Future role-based access control needs for the Driver App:

- A **driver role or driver actor model** is required, distinct from existing
  admin/store/user roles.
- A **driver can only read its own profile**, documents, vehicle, training, and
  eligibility.
- A **driver can only read offered/assigned orders** — not arbitrary orders.
- A **driver cannot browse store orders** or any store-wide order/inventory list.
- A **driver cannot mutate inventory directly**; inventory effects are
  backend-owned.
- A **driver cannot approve documents** (driver or otherwise); review is
  admin-owned.
- A **driver cannot override a verification failure**; a failed 21+ check blocks
  completion.
- A **driver cannot self-confirm a restricted return**; the store confirms and
  the backend closes it.
- A **store can confirm handoff and return for its own orders** only, scoped by
  tenancy.
- An **admin can review compliance, audit, incidents, and support** across the
  platform.
- **Support/admin operator visibility must be scoped and audited** — access to
  driver/delivery data is permissioned and recorded.

## Tenancy Gap Analysis

Future multi-tenant boundaries:

- A **driver may serve one or more stores** depending on the future operating
  model; the model must not assume a single fixed store.
- **Delivery/order access must be order-scoped** to the driver's assignments.
- **Store visibility must remain store-scoped** — a store sees only its own
  orders, handoffs, and returns.
- **Admin visibility may be global** across stores and drivers.
- **Support visibility must be permissioned** and limited to what a case
  requires.
- **Cross-store leakage must be prevented** — no driver or store surface may
  expose another store's data.
- **Pre-accept offers must preserve customer privacy** — only an approximate
  dropoff zone is shown before acceptance.
- **Customer address should only be released after valid assignment acceptance**
  (and the correct lifecycle state, e.g., post-pickup for the exact dropoff).

## Audit Gap Analysis

Future audit needs:

- **Existing audit foundations may be extendable** to host the driver timeline;
  this must be verified in Dr.1.1.
- The **driver delivery audit timeline must include** assignment, pickup,
  handoff, dropoff, verification, proof, failed delivery, return, safety, and
  support events.
- **Audit events must not contain raw ID data** — no ID images, no full ID
  numbers.
- **Audit events should include** actor, order, store, driver, timestamps,
  prior/new state where relevant, reason, and redacted metadata.
- **Audit event naming is architectural** until Dr.1.1 finalizes the schema; the
  names in this document are candidates.
- **Duplicate audit events must be controlled through idempotency** so retries do
  not double-record critical events.

## Inventory Safety Gap Analysis

Future inventory-safety requirements:

- **Mobile must never mutate inventory directly.** The Driver App submits
  delivery outcomes; it does not write stock.
- **Pickup does not equal inventory consumption by mobile.** Any stock effect of
  pickup is a backend decision, not a mobile write.
- **Completion/failure/return inventory effects must be backend-owned** and
  derived from authoritative delivery outcomes.
- **A failed restricted delivery requires a backend-managed return workflow**;
  the product is not abandoned or silently consumed.
- **Store return confirmation should trigger a backend inventory review** of the
  returned product.
- **Support/admin override flows must be audited** where they affect inventory or
  delivery state.

## Notification Gap Analysis

Future notification needs:

- **Mobile needs device token registration** to receive push.
- **Notification preferences** for non-critical categories.
- **Delivery offer pushes** for time-sensitive offers.
- **Order ready / pickup reminders** during pickup.
- **Customer/store/support message notifications.**
- **ID verification required** prompts.
- **Return required** prompts.
- **Document expiring/rejected** alerts.
- **Account approved/blocked** notices.
- **GPS/network/low battery** diagnostics.
- **Policy update** prompts (re-acknowledgment).
- **App update required** notices.
- **Compliance-critical notifications may not be fully suppressible** (e.g., ID
  verification required, return required, account blocked, policy update).
- **Push delivery and audit should be backend-owned** — triggers derive from
  authoritative state changes.

## Geofence / Legal Zone Gap Analysis

Future geofence and legal-zone needs:

- **Store arrival validation** (future).
- **Dropoff arrival validation** (future).
- **Pickup distance enforcement** (future).
- **Delivery completion distance enforcement** (future).
- **Legal delivery zones** for restricted product.
- **Blocked/restricted zones.**
- **Delivery radius** bounds.
- **High-risk areas** flags.
- **City/county/product-specific zones** (future).
- **Legal review dependency** before enforcement is activated.
- **Location data privacy and retention considerations** — minimize collection,
  bound retention, collect only for a justified purpose.

## Support / Safety Gap Analysis

Future support and safety needs:

- **Support ticket persistence** with backend-owned lifecycle.
- **Active delivery context** attached to a case when relevant.
- **Support category taxonomy** (pickup, store, customer, ID, safety, vehicle,
  app, earnings, policy).
- **Support case status** tracking.
- **Support messages** (future).
- **Attachments** (future), avoiding sensitive ID data.
- **Safety report persistence** for incidents.
- **Emergency/safety event visibility** to support/admin.
- **Cancel-for-safety flow** tied to delivery/return outcomes.
- **Admin/support escalation** routing.
- **Privacy and abuse prevention** — scoped sharing, rate limiting, and audit.

## Performance / Earnings Gap Analysis

Future performance and earnings needs (visibility only):

- **Estimated earnings read model only** — no money movement.
- **Delivery count.**
- **Delivery history** (driver-scoped, visibility only).
- **No payouts.**
- **No cashout.**
- **No Stripe.**
- **No payment movement.**
- **Performance metrics:**
  - completed deliveries,
  - failed deliveries,
  - return rate,
  - pickup on-time,
  - delivery on-time,
  - acceptance/decline/cancellation,
  - proof completion,
  - compliance incidents,
  - restricted delivery success,
  - audit cleanliness score.
- **Performance snapshots** (future) for periodic aggregation.

## Idempotency / Offline Retry Gap Analysis

The following driver actions require idempotency:

- accept delivery
- decline delivery
- mark en route to store
- mark arrived at store
- submit store issue
- submit handoff PIN
- confirm pickup
- mark out for delivery
- contact customer event
- mark arrived at customer
- submit ID verification
- submit proof
- complete delivery
- submit failed delivery
- start return
- confirm return
- create support case
- report safety incident
- submit app issue

For these actions:

- **Mobile can retry safely** after network failure or app restart.
- **The backend must reject duplicate side effects** — a retried action does not
  create a second pickup, proof, completion, return, case, or incident.
- **The audit timeline must not duplicate critical events incorrectly** — each
  logical event is recorded once.
- **Offline recovery depends on backend action dedupe** — queued actions
  reconcile idempotently when connectivity returns.

## Phase Target Map

Backend work maps to future phases as follows. Each phase requires its own
contract lock, diagnostic, gameplan, implementation, validation, and pass/fail
report.

**Dr.1.1 — Driver Backend Surface:**

- eligibility,
- assignment,
- driver-scoped orders,
- pickup,
- store handoff,
- delivery transitions,
- age verification result,
- proof,
- failed delivery,
- return to store,
- audit events,
- idempotency basics.

**Dr.1.2 — Driver Mobile Foundation:**

- backend supports mobile auth/session and secure API access,
- notification device token registration may begin,
- app version / config endpoint (future).

**Dr.1.3 — Driver App MVP:**

- mobile consumes Dr.1.1 backend endpoints,
- manual verification,
- proof,
- failed delivery,
- return-to-store.

**Dr.1.4 — Driver App Operations:**

- support center,
- safety toolkit,
- notifications,
- delivery history,
- earnings placeholder,
- performance basics.

**Dr.1.5 — Driver Compliance Upgrade:**

- legal-approved ID scan,
- vendor verification if approved,
- advanced compliance audit,
- restricted zone enforcement,
- admin review queue.

**Dr.1.6 — Driver Growth Features:**

- promotions,
- rewards,
- performance tiers,
- batch delivery,
- multi-store delivery,
- advanced dispatch.

## No-Go Reminder

This document is documentation only. It does **not** implement:

- backend endpoints
- migrations
- schemas
- frontend changes
- mobile app code
- a Flutter project
- a Capacitor project
- dependency changes
- Stripe
- checkout
- driver payouts
- real ID scan
- raw ID storage
- production launch

Any work that would cross one of these boundaries requires a separate, explicitly
approved future phase with its own contract, consistent with
`docs/dr.1.0-driver-app-contract-lock.md` and `docs/f2.27-contract-lock.md`.
