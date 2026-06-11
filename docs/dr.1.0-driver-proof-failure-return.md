# Dr.1.0 Driver Proof, Failed Delivery, and Return-to-Store Architecture

## 1. Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.H — Proof, Failed Delivery, Return-to-Store Architecture
- **Deliverable path:** `docs/dr.1.0-driver-proof-failure-return.md`
- **Status:** Draft / Architecture
- **Scope:** Research/docs only
- **Implementation:** none — this document introduces no backend, frontend, or
  mobile implementation of any kind.

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/dr.1.0-driver-screen-inventory.md`,
`docs/dr.1.0-driver-user-flows.md`,
`docs/dr.1.0-driver-backend-gap-map.md`,
`docs/dr.1.0-driver-compliance-id-verification.md` (Dr.1.0.G),
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them. State names,
reasons, and event names are **architectural candidates**, finalized in Dr.1.1.

## 2. Purpose

This document defines how the NubeRush Driver App should handle proof of
delivery, failed delivery, and return-to-store. These flows are critical because
NubeRush delivers regulated smoke-shop and vape products, and an undeliverable or
non-compliant restricted order must be handled with accountability rather than
abandonment.

Proof, failure, and return architecture is critical for NubeRush because of:

- **Restricted products** — regulated items cannot be handed off casually or
  left unattended.
- **21+ verification dependency** — completion depends on a passed age/ID check
  (see Dr.1.0.G).
- **Delivery accountability** — every completion and failure must be attributable
  and auditable.
- **Store inventory protection** — undeliverable restricted product must return
  to the store, not vanish or be silently consumed.
- **Driver accountability** — drivers act within a backend-authorized lifecycle,
  not a self-served one.
- **Customer dispute handling** — proof and structured failure reasons support
  later dispute resolution.
- **Compliance audit trail** — a backend-owned audit timeline evidences lawful
  handling.
- **Support/admin visibility** — oversight observes outcomes through backend
  events.

## 3. Core Principles

- **Proof is backend-authorized.** The backend validates and accepts proof; the
  app submits it and cannot self-finalize.
- **Proof cannot override failed compliance.** A passed age/ID verification is a
  precondition; proof is meaningless without it for restricted orders.
- **Restricted delivery cannot be left unattended.** No leave-at-door,
  porch/lobby/mailbox drop, or unattended handoff for restricted product.
- **Driver cannot complete delivery locally without backend acceptance.**
  Completion is a backend transition, not a local UI state.
- **Failed restricted delivery normally requires return-to-store.** Undeliverable
  restricted product routes to an accountable return.
- **Driver cannot self-close a return.** The store confirms and the backend
  closes it.
- **Store confirmation is required to close a returned restricted order.** The
  return is not closed on the driver's word alone.
- **Mobile captures operational intent; the backend validates lifecycle state.**
  The app proposes transitions; the backend grants or rejects them.
- **Store/Admin visibility comes from backend events.** Oversight reads the
  backend event stream, not direct mobile state.
- **The audit trail is mandatory.** Every meaningful proof/failure/return step
  emits a compliance-grade audit event.
- **Privacy-safe proof metadata only for the MVP.** The MVP persists redacted,
  non-sensitive proof metadata — no raw ID data, no unattended photo.
- **Future richer proof methods require legal/product review.** Signature, photo,
  PIN, and geofence-verified proof are gated future options.

## 4. Relationship to Dr.1.0.G Compliance / 21+ Verification

This document continues the compliance architecture defined in Dr.1.0.G
(`docs/dr.1.0-driver-compliance-id-verification.md`):

- **Age/ID verification must pass before restricted proof of delivery can
  proceed.** `verification_passed` is a precondition for `proof_required` →
  `proof_submitted` on a restricted order.
- **Failed verification blocks proof.** A failed 21+ check prevents the order from
  entering the proof/completion path.
- **Failed verification creates the failed delivery / return-required path.** A
  restricted verification failure routes to failed delivery and then return.
- **Proof cannot be used as a compliance substitute.** Capturing proof never
  satisfies or replaces the age gate.
- **Return-to-store may be triggered by compliance failure.** Compliance failure
  is a primary trigger for `return_required`.
- **The backend controls the transition from verification to proof/failure/
  return.** The app reflects backend-authorized transitions; it does not move
  between these phases on its own.

## 5. Delivery Completion State Model

The following are **candidate completion states**, finalized in Dr.1.1. States
are backend-owned; the app reflects them. "Mobile behavior" describes what the
app presents or submits, never a state it can self-assign.

### pending_pickup

- **Meaning:** assignment accepted; not yet picked up.
- **Who/what can set it:** backend (on assignment acceptance).
- **Allowed next states:** `picked_up`, `failed`, `canceled_by_backend`.
- **Mobile behavior:** shows navigate-to-store and pickup steps.
- **Backend authority notes:** pickup requires handoff + compliance (Dr.1.0.D/E).
- **Store/Admin visibility:** assigned driver; awaiting pickup.
- **Audit implication:** pickup events on transition.

### picked_up

- **Meaning:** the order has been picked up from the store.
- **Who/what can set it:** backend (on confirmed pickup).
- **Allowed next states:** `en_route_to_customer`, `failed`,
  `return_required`.
- **Mobile behavior:** shows out-for-delivery start.
- **Backend authority notes:** releases the exact customer address post-pickup.
- **Store/Admin visibility:** pickup confirmed.
- **Audit implication:** `pickup_confirmed`, `out_for_delivery`.

### en_route_to_customer

- **Meaning:** in transit to the customer.
- **Who/what can set it:** backend (on out-for-delivery).
- **Allowed next states:** `arrived_at_customer`, `failed`, `return_required`.
- **Mobile behavior:** navigation handoff; masked contact.
- **Backend authority notes:** zone constraints may apply (future).
- **Store/Admin visibility:** out for delivery.
- **Audit implication:** `out_for_delivery`.

### arrived_at_customer

- **Meaning:** the driver has arrived at the customer.
- **Who/what can set it:** backend (accepting an arrival event).
- **Allowed next states:** `verification_required` (restricted),
  `proof_required` (non-restricted), `failed`, `return_required`.
- **Mobile behavior:** marks arrival; may start the wait timer.
- **Backend authority notes:** geofence validation is future.
- **Store/Admin visibility:** arrived at customer.
- **Audit implication:** `delivery_arrived_at_customer`.

### verification_required

- **Meaning:** a restricted order requires 21+ verification before proof.
- **Who/what can set it:** backend (for restricted orders).
- **Allowed next states:** `verification_passed`, `failed`, `return_required`.
- **Mobile behavior:** shows Restricted Product Warning and the manual checklist.
- **Backend authority notes:** see Dr.1.0.G; completion is blocked until passed.
- **Store/Admin visibility:** verification required.
- **Audit implication:** `verification_started`.

### verification_passed

- **Meaning:** the backend accepted a passing verification result.
- **Who/what can set it:** backend.
- **Allowed next states:** `proof_required`.
- **Mobile behavior:** proceeds to proof.
- **Backend authority notes:** required reference for restricted proof.
- **Store/Admin visibility:** verification passed (redacted).
- **Audit implication:** `age_verification_passed`.

### proof_required

- **Meaning:** proof of delivery must be captured before completion.
- **Who/what can set it:** backend.
- **Allowed next states:** `proof_submitted`, `failed`, `return_required`.
- **Mobile behavior:** shows the proof capture step (MVP: attestation +
  timestamp).
- **Backend authority notes:** proof requirements are backend-defined.
- **Store/Admin visibility:** awaiting proof.
- **Audit implication:** `proof_required`.

### proof_submitted

- **Meaning:** the driver submitted proof; backend validation pending.
- **Who/what can set it:** backend (recording a submitted proof).
- **Allowed next states:** `completed`, `failed`, `support_review_required`.
- **Mobile behavior:** shows submission state; awaits acceptance.
- **Backend authority notes:** the backend may accept or reject the proof.
- **Store/Admin visibility:** proof submitted.
- **Audit implication:** `proof_submitted`.

### completed

- **Meaning:** the backend authorized and recorded completion.
- **Who/what can set it:** backend.
- **Allowed next states:** terminal.
- **Mobile behavior:** shows completion summary (earnings visibility only).
- **Backend authority notes:** requires proof + verification for restricted.
- **Store/Admin visibility:** completed.
- **Audit implication:** `proof_accepted`, `delivery_completed`.

### failed

- **Meaning:** the delivery could not be completed.
- **Who/what can set it:** backend (accepting a failure with a reason).
- **Allowed next states:** `return_required` (restricted),
  `support_review_required`, terminal (non-restricted future).
- **Mobile behavior:** shows the failure outcome and the next step.
- **Backend authority notes:** the backend decides return.
- **Store/Admin visibility:** failed (reason category).
- **Audit implication:** `delivery_failed`.

### return_required

- **Meaning:** undeliverable restricted product must return to the store.
- **Who/what can set it:** backend.
- **Allowed next states:** `returning_to_store`.
- **Mobile behavior:** shows Return Required; the driver cannot complete the
  original delivery.
- **Backend authority notes:** the driver cannot self-close; see Section 14.
- **Store/Admin visibility:** return required.
- **Audit implication:** `return_required`.

### returning_to_store

- **Meaning:** the driver is en route back to the store with the product.
- **Who/what can set it:** backend (on return acknowledgment/start).
- **Allowed next states:** `returned_to_store_pending_confirmation`,
  `support_review_required`.
- **Mobile behavior:** return navigation; ETA/distance.
- **Backend authority notes:** return state is tracked server-side.
- **Store/Admin visibility:** driver returning (ETA future).
- **Audit implication:** `return_started`.

### returned_to_store_pending_confirmation

- **Meaning:** the driver has handed off the return; store confirmation pending.
- **Who/what can set it:** backend (on return handoff submission).
- **Allowed next states:** `return_confirmed`, `support_review_required`.
- **Mobile behavior:** shows pending confirmation; cannot self-confirm.
- **Backend authority notes:** the store confirms; the backend closes.
- **Store/Admin visibility:** returned pending confirmation.
- **Audit implication:** `return_handoff_submitted`.

### return_confirmed

- **Meaning:** the store confirmed receipt of the returned product.
- **Who/what can set it:** backend (on validated store confirmation).
- **Allowed next states:** terminal.
- **Mobile behavior:** shows the closed return.
- **Backend authority notes:** triggers inventory review (not auto-restock).
- **Store/Admin visibility:** return confirmed.
- **Audit implication:** `return_confirmed_by_store`.

### support_review_required

- **Meaning:** an exception needs support/admin review.
- **Who/what can set it:** backend.
- **Allowed next states:** resolution paths (back to a valid state or terminal).
- **Mobile behavior:** shows escalation; awaits resolution.
- **Backend authority notes:** review is support/admin-owned and audited.
- **Store/Admin visibility:** exception / under review.
- **Audit implication:** `support_escalated`, `return_exception_opened`.

### canceled_by_backend

- **Meaning:** the backend canceled the delivery/assignment.
- **Who/what can set it:** backend.
- **Allowed next states:** terminal.
- **Mobile behavior:** shows cancellation; no further driver action.
- **Backend authority notes:** the app cannot cancel a backend-owned order
  unilaterally.
- **Store/Admin visibility:** canceled.
- **Audit implication:** cancellation event.

## 6. Proof of Delivery Types

The following proof types are classified MVP / Future / No-Go. The MVP remains
conservative; unattended/drop-off proof is **No-Go for restricted** product.

| Proof type | Class | Restricted suitability | Privacy / compliance risk | Backend validation | Mobile responsibility | Store/Admin visibility | Notes |
|---|---|---|---|---|---|---|---|
| Backend completion acknowledgment | MVP | Required | Low | Backend authorizes completion | Reflect state | Completed event | The authoritative completion signal |
| Driver checklist confirmation | MVP | Suitable | Low | Validate checklist + lifecycle | Capture checklist | Redacted outcome | Core MVP proof element |
| Customer handoff confirmation | MVP | Suitable | Low | Validate in-person handoff | Capture handoff confirm | Handoff recorded | In-person handoff for restricted |
| Age/ID verification reference | MVP | Required (restricted) | Low (redacted ref) | Bind verification pass | Reference only | Redacted reference | No raw ID data |
| Timestamp | MVP | Suitable | Low | Record server-trusted time | Submit local time | Timestamp | Server time authoritative |
| Approximate location/geofence context | Future | Conditional | Medium (location) | Validate proximity (future) | Provide if available | Redacted context | Legal/privacy review |
| Customer signature | Future | Conditional | Medium | Validate per policy | Capture if approved | Redacted reference | Legal review required |
| Delivery photo | Future | Conditional | High | Validate per policy | Capture if approved | Redacted reference | Must not capture ID |
| Barcode/QR handoff code | Future | Suitable | Low | Validate code | Scan code | Code event | Handoff integrity (future) |
| Customer PIN | Future | Suitable | Low | Validate PIN | Capture PIN | PIN event | Complements, not replaces, 21+ |
| Store-packed item handoff reference | Future | Suitable | Low | Validate reference | Reference only | Reference event | Ties pickup to dropoff |
| Support-approved completion | Future | Exceptional | Medium | Support-authorized override | Reflect outcome | Support audit | Audited exception only |
| Unattended/drop-off photo | No-Go (restricted MVP) | Not allowed | High | Rejected for restricted | Not offered for restricted | N/A | No unattended restricted delivery |

Classification notes:

- **Unattended/drop-off proof is No-Go for the restricted MVP** — restricted
  product requires in-person, verified handoff.
- **Photo, signature, and PIN are future, legally reviewed options** — not in the
  MVP.
- **The MVP stays conservative:** backend acknowledgment + driver checklist +
  handoff confirmation + verification reference + timestamp.

## 7. MVP Proof Policy

The MVP proof model is conservative and privacy-safe:

- **Manual driver completion checklist** — the driver confirms the structured
  completion checklist.
- **Backend confirms the delivery state** — completion is a backend transition.
- **A `verification_passed` reference is required for restricted orders** — proof
  binds to the accepted age/ID result.
- **Delivery handoff confirmation** — an in-person handoff is recorded.
- **Timestamp** — server-trusted time is authoritative.
- **Driver/order/store association** — recorded for accountability.
- **Optional approximate arrival context if available** — only where present and
  privacy-scoped; not required for the MVP.
- **No raw customer ID storage.**
- **No full ID number.**
- **No unattended delivery proof.**
- **No customer signature unless legally approved.**
- **No delivery photo unless legally approved.**
- **The backend can reject proof if the state is invalid** — out-of-sequence or
  unverified restricted proof is rejected.

This policy preserves the privacy/redaction boundary from Dr.1.0.G: the proof
record evidences that a compliant handoff occurred, not the identity document.

## 8. Restricted Product Completion Rules

Completion of a restricted order requires all of the following; any violation
blocks completion and routes to failure/return:

- **The customer must be present.**
- **The customer must be 21+.**
- **ID verification must pass first** (Dr.1.0.G).
- **No leave-at-door.**
- **No mailbox/porch/lobby unattended delivery.**
- **No handoff to the wrong recipient.**
- **No handoff after refusal.**
- **No handoff after failed verification.**
- **No handoff during an unsafe event.**
- **No completion while offline** unless the backend later accepts queued proof;
  **restricted completion should be blocked until backend acceptance.**
- **The backend finalizes completion** — the app cannot self-complete.
- **Store/Admin can audit completion** through the backend audit timeline.

## 9. Failed Delivery Reason Model

The following are **candidate failure reasons**, finalized in Dr.1.1. For
restricted orders, a failure routes to return-to-store unless otherwise noted.
Each reason routes through the backend; the app only submits the selected reason.

### customer_unavailable

- **Meaning:** the customer is not reachable/present at the dropoff.
- **Driver action:** attempt contact; may start the wait timer; submit failure.
- **Customer contact required:** yes.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted).
- **Backend result:** records failure; decides return.
- **Store/Admin visibility:** failed (customer unavailable).
- **Audit event:** `delivery_failed`, `customer_unavailable`.

### customer_no_show_after_wait

- **Meaning:** the wait timer elapsed with no customer.
- **Driver action:** submit failure after the wait window.
- **Customer contact required:** yes (during wait).
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted).
- **Backend result:** records failure after validating the wait; decides return.
- **Store/Admin visibility:** failed (no-show).
- **Audit event:** `wait_timer_expired`, `delivery_failed`.

### customer_refused_order

- **Meaning:** the customer refused to accept the order.
- **Driver action:** submit failure.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted).
- **Backend result:** records failure; decides return.
- **Store/Admin visibility:** failed (refused).
- **Audit event:** `delivery_failed`.

### customer_refused_verification

- **Meaning:** the customer refused 21+ verification.
- **Driver action:** submit failure (compliance).
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted).
- **Backend result:** records compliance failure; blocks completion; decides
  return.
- **Store/Admin visibility:** failed (verification refused).
- **Audit event:** `age_verification_failed`, `delivery_failed`.

### under_21

- **Meaning:** the recipient is under 21.
- **Driver action:** submit failure (compliance).
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** no.
- **Return-to-store required:** yes (restricted).
- **Backend result:** hard-blocks completion; decides return.
- **Store/Admin visibility:** failed (compliance).
- **Audit event:** `age_verification_failed`, `delivery_failed`.

### missing_id

- **Meaning:** no government ID presented.
- **Driver action:** submit failure (compliance).
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** no.
- **Return-to-store required:** yes (restricted).
- **Backend result:** blocks completion; decides return.
- **Store/Admin visibility:** failed (compliance).
- **Audit event:** `age_verification_failed`, `delivery_failed`.

### expired_id

- **Meaning:** the ID is expired.
- **Driver action:** submit failure (compliance).
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** no.
- **Return-to-store required:** yes (restricted).
- **Backend result:** blocks completion; decides return.
- **Store/Admin visibility:** failed (compliance).
- **Audit event:** `age_verification_failed`, `delivery_failed`.

### id_mismatch

- **Meaning:** the ID does not match the person/recipient policy.
- **Driver action:** submit failure (compliance).
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted).
- **Backend result:** blocks completion; decides return.
- **Store/Admin visibility:** failed (compliance).
- **Audit event:** `age_verification_failed`, `delivery_failed`.

### suspected_fake_id

- **Meaning:** the ID appears fraudulent.
- **Driver action:** submit failure; may escalate to support.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** recommended.
- **Return-to-store required:** yes (restricted).
- **Backend result:** blocks completion; flags for review; decides return.
- **Store/Admin visibility:** failed (compliance) + review flag.
- **Audit event:** `age_verification_failed`, `support_escalated`,
  `delivery_failed`.

### wrong_recipient

- **Meaning:** the person is not the authorized recipient.
- **Driver action:** submit failure (compliance).
- **Customer contact required:** optional.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted).
- **Backend result:** blocks completion; decides return.
- **Store/Admin visibility:** failed (compliance).
- **Audit event:** `age_verification_failed`, `delivery_failed`.

### unsafe_location

- **Meaning:** the dropoff location is unsafe.
- **Driver action:** invoke safety; submit failure.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** yes.
- **Return-to-store required:** yes (restricted).
- **Backend result:** records failure; routes safety; decides return.
- **Store/Admin visibility:** failed (safety).
- **Audit event:** `support_escalated`, `delivery_failed`.

### threatening_customer

- **Meaning:** the customer is threatening/abusive.
- **Driver action:** invoke safety; submit failure.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** yes.
- **Return-to-store required:** yes (restricted).
- **Backend result:** records failure; routes safety; decides return.
- **Store/Admin visibility:** failed (safety).
- **Audit event:** `support_escalated`, `delivery_failed`.

### accident_or_vehicle_issue

- **Meaning:** an accident or vehicle problem prevents delivery.
- **Driver action:** invoke safety/support; submit failure.
- **Customer contact required:** no.
- **Store contact required:** optional.
- **Support escalation required:** yes.
- **Return-to-store required:** as directed (restricted product still accounted
  for).
- **Backend result:** records failure; routes support; decides handling.
- **Store/Admin visibility:** failed (operational).
- **Audit event:** `support_escalated`, `delivery_failed`.

### restricted_location

- **Meaning:** the dropoff is in a restricted/illegal delivery zone.
- **Driver action:** submit failure (compliance/legal).
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted).
- **Backend result:** blocks completion; decides return.
- **Store/Admin visibility:** failed (legal zone).
- **Audit event:** `delivery_failed`.

### store_issue

- **Meaning:** a store-side problem affects the delivery.
- **Driver action:** contact store; submit failure/issue.
- **Customer contact required:** no.
- **Store contact required:** yes.
- **Support escalation required:** optional.
- **Return-to-store required:** as directed.
- **Backend result:** records issue/failure; decides handling.
- **Store/Admin visibility:** failed/issue (store).
- **Audit event:** `store_contact_attempted`, `delivery_failed`.

### damaged_order

- **Meaning:** the order is damaged.
- **Driver action:** contact store/support; submit failure.
- **Customer contact required:** optional.
- **Store contact required:** yes.
- **Support escalation required:** optional.
- **Return-to-store required:** yes (restricted; damaged product accounted for).
- **Backend result:** records failure; decides return/inventory review.
- **Store/Admin visibility:** failed (damaged).
- **Audit event:** `delivery_failed`.

### app_issue

- **Meaning:** an app problem prevents completion.
- **Driver action:** report bug; may open support; submit failure.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** as directed (restricted accounted for).
- **Backend result:** records failure; decides handling.
- **Store/Admin visibility:** failed (technical).
- **Audit event:** `delivery_failed` (+ support case if opened).

### network_issue

- **Meaning:** connectivity prevents backend acceptance.
- **Driver action:** retry when online; submit when possible.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** as directed once reconciled.
- **Backend result:** reconciles when online; rejects duplicates; decides
  handling.
- **Store/Admin visibility:** pending/failed once reconciled.
- **Audit event:** `offline_action_queued`, `offline_action_replayed`,
  `delivery_failed`.

### support_instructed_failure

- **Meaning:** support instructed the driver to fail the delivery.
- **Driver action:** submit failure per support instruction.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** already engaged.
- **Return-to-store required:** as directed (restricted accounted for).
- **Backend result:** records support-instructed failure; decides handling.
- **Store/Admin visibility:** failed (support).
- **Audit event:** `support_escalated`, `delivery_failed`.

### backend_rejected_completion

- **Meaning:** the backend rejected an attempted completion.
- **Driver action:** none can override; follow the directed next step.
- **Customer contact required:** no.
- **Store contact required:** no.
- **Support escalation required:** optional.
- **Return-to-store required:** as directed (restricted accounted for).
- **Backend result:** rejects completion; emits a rejection; decides handling.
- **Store/Admin visibility:** failed (rejected).
- **Audit event:** `proof_rejected`, `delivery_failed`.

## 10. Wait Timer Architecture

The wait timer governs the customer-unavailable case before a failure can be
finalized.

- **When the wait timer starts:** after the driver marks arrival
  (`arrived_at_customer`) and the customer is not present/responding.
- **`arrived_at_customer` dependency:** the timer is only valid after a
  backend-accepted arrival.
- **Customer contact attempts before/while waiting:** the driver should attempt
  masked contact before and during the wait.
- **Minimum wait duration:** a **backend-configurable future setting** (a
  candidate value, not hardcoded here); the backend owns the qualifying duration.
- **Visible countdown/elapsed timer on mobile:** the app shows the countdown or
  elapsed time for transparency.
- **What happens when the timer expires:** the driver may transition to failure
  (`customer_no_show_after_wait`), subject to backend validation.
- **Restricted-product rules after the timer expires:** restricted product is
  **never left unattended**; expiry routes to failed delivery and return, not a
  drop-off.
- **Support escalation option:** the driver may escalate instead of failing.
- **Failed delivery transition:** the backend validates the elapsed wait before
  accepting the no-show failure.
- **Audit events:** `wait_timer_started`, `wait_timer_expired`,
  `customer_contact_attempted`.
- **Offline/retry behavior:** timer state is presentational; the failure
  transition still requires backend acceptance (idempotent).
- **Backend owns whether the wait timer qualifies for failure** — the app cannot
  self-qualify a no-show.

The final production wait duration is **not hardcoded** here; it is a
candidate/configurable value owned by the backend.

## 11. Customer Contact Requirements

- **When the driver should call/message the customer:** to coordinate handoff,
  on arrival, and during a no-show wait.
- **Pre-arrival contact:** optional courtesy contact while en route.
- **Arrival contact:** contact on arrival if the customer is not present.
- **No-show contact:** contact attempts during the wait timer.
- **Verification-issue contact boundaries:** contact may coordinate presence but
  **must not coach or disclose how to pass** verification; verification outcome
  is the driver's in-person judgment plus backend acceptance.
- **Unsafe-situation boundaries:** if unsafe, the driver prioritizes safety over
  contact and escalates.
- **Masked phone requirement:** all contact uses masked numbers; **no personal
  phone exposure** on either side.
- **Quick message (future) option:** a controlled, compliance-safe quick-message
  set is a future enhancement.
- **Audit of contact attempt metadata:** contact attempts are recorded as
  metadata (`customer_contact_attempted`).
- **No sensitive ID details in customer messages** — messages never contain ID
  data.
- **Backend/store/admin visibility:** contact-attempt metadata is visible to
  oversight through backend events, not message content beyond policy.

## 12. Store Contact Requirements

- **When the driver should contact the store:** pickup issues, missing/damaged
  items, and return coordination.
- **Pickup issue:** coordinate an order-not-ready or wrong-order situation.
- **Missing item:** report and coordinate a missing item.
- **Damaged item:** report a damaged item.
- **Return-to-store coordination:** coordinate the return handoff.
- **Store closed during return:** if the store is closed, the driver escalates to
  support; the return remains open and accountable.
- **Store return confirmation:** the store confirms the returned items (Section
  16).
- **Contact metadata:** store-contact attempts are recorded
  (`store_contact_attempted`).
- **Backend event visibility:** store contact and issues surface to oversight via
  backend events.
- **No direct mobile mutation of store state** — the app cannot change store-side
  state; it submits intent and the backend/store act.

## 13. Support Escalation Requirements

Support is required (or recommended) in these situations:

- **unsafe location**;
- **threatening customer**;
- **accident**;
- **suspected fake ID**;
- **legal/restricted-zone issue**;
- **backend state mismatch**;
- **customer dispute**;
- **driver cannot complete the app flow**;
- **return exception** (store cannot/will not confirm);
- **store unavailable for return**;
- **app/network recovery failure**.

Support escalation architecture:

- **Support case candidate fields:** category, order/assignment reference, store
  reference, driver reference, active-delivery context, status, timestamps,
  redacted notes (no raw ID data).
- **Backend authority:** the backend owns the case lifecycle and routing; support
  actions are server-side.
- **Store/Admin visibility:** Admin sees support escalations and linked
  exceptions; Store sees escalations relevant to its orders.
- **Audit events:** `support_escalated`, and `return_exception_opened` for return
  exceptions.
- **Mobile behavior:** the app opens a case and reflects status; it does not
  resolve cases.
- **No direct override from mobile** — support outcomes (including
  support-approved completion) are backend-authorized and audited, never a local
  override.

## 14. Return-to-Store Architecture

The full return-to-store path for an undeliverable restricted order:

- **What triggers `return_required`:** a failed restricted delivery (compliance
  failure, refusal, no-show, unsafe, damaged, etc.) where the product must come
  back to the store.
- **Who/what authorizes the return:** the **backend** sets `return_required`; the
  app reflects it.
- **Driver UI state:** the app shows Return Required and the return route; the
  original delivery cannot be completed.
- **Navigation handoff to the store:** the driver launches external navigation to
  the originating store.
- **Customer route ends, store return route starts:** the active route switches
  from the customer to the return destination.
- **The driver cannot complete the original delivery** once return is required.
- **The driver cannot self-confirm the return** — confirmation is store-side.
- **The store must confirm the returned items** (Section 16).
- **The backend updates the final state** on validated store confirmation.
- **Inventory review implications:** return triggers a backend-owned inventory
  review, not an automatic restock (Section 17).
- **Support escalation if the store cannot confirm:** a return exception routes to
  support.
- **Audit timeline:** the return is fully audited (`return_required` →
  `return_started` → `arrived_at_store_for_return` → `return_handoff_submitted` →
  `return_confirmed_by_store` or `return_rejected_by_store`).

## 15. Return-to-Store State Model

The following are **candidate return states**, finalized in Dr.1.1. States are
backend-owned; the app reflects them.

### return_not_required

- **Meaning:** the delivery does not require a return.
- **Who/what can set it:** backend (default for completed/non-restricted paths).
- **Allowed next states:** `return_required` (if a later failure mandates it).
- **Mobile behavior:** no return UI.
- **Backend authority notes:** the default unless a restricted failure occurs.
- **Store/Admin visibility:** none specific.
- **Audit implication:** none specific.

### return_required

- **Meaning:** a return is mandated.
- **Who/what can set it:** backend.
- **Allowed next states:** `return_acknowledged_by_driver`.
- **Mobile behavior:** shows Return Required.
- **Backend authority notes:** the driver cannot clear this locally.
- **Store/Admin visibility:** return required.
- **Audit implication:** `return_required`.

### return_acknowledged_by_driver

- **Meaning:** the driver acknowledged the return.
- **Who/what can set it:** backend (on driver acknowledgment).
- **Allowed next states:** `returning_to_store`.
- **Mobile behavior:** confirms acknowledgment; starts the return.
- **Backend authority notes:** acknowledgment is recorded, not a self-close.
- **Store/Admin visibility:** return acknowledged.
- **Audit implication:** `return_acknowledged_by_driver`.

### returning_to_store

- **Meaning:** the driver is en route back to the store.
- **Who/what can set it:** backend.
- **Allowed next states:** `arrived_at_store_for_return`,
  `return_exception_support_required`.
- **Mobile behavior:** return navigation; ETA/distance.
- **Backend authority notes:** tracked server-side.
- **Store/Admin visibility:** driver returning (ETA future).
- **Audit implication:** `return_started`.

### arrived_at_store_for_return

- **Meaning:** the driver arrived at the store with the product.
- **Who/what can set it:** backend (accepting arrival).
- **Allowed next states:** `return_handoff_submitted`,
  `return_exception_support_required`.
- **Mobile behavior:** shows the return handoff step.
- **Backend authority notes:** geofence validation is future.
- **Store/Admin visibility:** driver arrived for return.
- **Audit implication:** `arrived_at_store_for_return`.

### return_handoff_submitted

- **Meaning:** the driver submitted the return handoff.
- **Who/what can set it:** backend (on handoff submission).
- **Allowed next states:** `returned_to_store_pending_confirmation`.
- **Mobile behavior:** shows pending store confirmation.
- **Backend authority notes:** submission is not confirmation.
- **Store/Admin visibility:** handoff submitted.
- **Audit implication:** `return_handoff_submitted`.

### returned_to_store_pending_confirmation

- **Meaning:** awaiting store confirmation of the returned items.
- **Who/what can set it:** backend.
- **Allowed next states:** `return_confirmed_by_store`,
  `return_rejected_by_store`, `return_exception_support_required`.
- **Mobile behavior:** the driver cannot self-confirm.
- **Backend authority notes:** the store confirms; the backend closes.
- **Store/Admin visibility:** pending confirmation.
- **Audit implication:** none new (awaiting store action).

### return_confirmed_by_store

- **Meaning:** the store confirmed the return.
- **Who/what can set it:** backend (on validated store confirmation).
- **Allowed next states:** terminal.
- **Mobile behavior:** shows the closed return.
- **Backend authority notes:** triggers inventory review (not auto-restock).
- **Store/Admin visibility:** return confirmed.
- **Audit implication:** `return_confirmed_by_store`.

### return_rejected_by_store

- **Meaning:** the store rejected/disputed the return (e.g., mismatch).
- **Who/what can set it:** backend (on store rejection).
- **Allowed next states:** `return_exception_support_required`.
- **Mobile behavior:** shows the exception; awaits resolution.
- **Backend authority notes:** routes to support/admin review.
- **Store/Admin visibility:** return rejected.
- **Audit implication:** `return_rejected_by_store`.

### return_exception_support_required

- **Meaning:** the return needs support/admin intervention.
- **Who/what can set it:** backend.
- **Allowed next states:** resolution paths (confirmed, or admin-resolved).
- **Mobile behavior:** shows the exception; awaits resolution.
- **Backend authority notes:** support/admin-owned and audited.
- **Store/Admin visibility:** exception / under review.
- **Audit implication:** `return_exception_opened`.

## 16. Store Return Confirmation

- **The store confirms the physical return** of the product.
- **The store may confirm full/partial/missing/damaged return** as a **future
  candidate** distinction (the MVP confirms receipt; granular condition is
  future).
- **Store user identity is required** for the confirmation.
- **A timestamp is required.**
- **Order/delivery/driver/store references** are recorded.
- **The backend validates store tenancy** — only the originating store may
  confirm its return.
- **The driver cannot confirm on behalf of the store.**
- **Admin can review exceptions** (rejected/disputed returns).
- **Inventory should not be automatically restocked** without a
  backend/store-authorized review.
- **Audit is required** (`return_confirmed_by_store` /
  `return_rejected_by_store`).

## 17. Inventory Safety Implications

- **A failed restricted delivery should not be treated as a completed sale
  handoff** — the product did not lawfully reach the customer.
- **Returned items may require inspection before resale** — condition is not
  assumed.
- **Product condition may matter** — damaged/opened items follow a separate path.
- **Inventory mutation must be backend-owned** — the mobile app never writes
  inventory.
- **Store confirmation may trigger an inventory review, not an automatic blind
  restock** — restock is a reviewed, backend-authorized action.
- **Damaged/missing item path:** discrepancies route to a return exception and
  admin oversight rather than silent reconciliation.
- **Audit implications:** inventory-affecting return outcomes are audited.
- **Admin oversight:** admin reviews exceptions and inventory implications.
- **Future integration with inventory logs:** the existing inventory-log
  capability is a likely integration point (to be verified in Dr.1.1), not
  modified here.

## 18. Proof / Failure / Return Audit Events

The following are **candidate audit events**, finalized in Dr.1.1. Each is
backend-emitted; none contains raw ID data.

| Event | Trigger | Actor | Required metadata | Forbidden metadata | Store/Admin visibility | Compliance/inventory relevance |
|---|---|---|---|---|---|---|
| delivery_arrived_at_customer | Driver marks arrival | Driver/backend | order, driver, timestamp | ID data | Arrived | Lifecycle |
| proof_required | Order enters proof step | Backend | order, driver, timestamp | ID data | Awaiting proof | Completion gate |
| proof_submitted | Driver submits proof | Driver/backend | order, driver, timestamp, method | raw ID, full ID number | Proof submitted | Completion |
| proof_accepted | Backend accepts proof | Backend | order, driver, timestamp | ID data | Completed | Completion |
| proof_rejected | Backend rejects proof | Backend | order, driver, timestamp, reason | ID data | Rejected | Completion gate |
| delivery_completed | Backend authorizes completion | Backend | order, driver, store, timestamp | ID data | Completed | Compliance/sale |
| delivery_failure_started | Failure path begins | Driver/backend | order, driver, timestamp | ID data | Failing | Lifecycle |
| delivery_failed | Backend accepts failure | Backend | order, driver, timestamp, reason | raw ID data | Failed (reason) | Compliance/inventory |
| wait_timer_started | Wait begins after arrival | Driver/backend | order, driver, timestamp | ID data | Waiting | Lifecycle |
| wait_timer_expired | Wait window elapses | Backend | order, driver, timestamp | ID data | No-show | Lifecycle |
| customer_contact_attempted | Driver contacts customer | Driver/backend | order, driver, timestamp, channel | message content, phone | Contact attempted | Privacy |
| store_contact_attempted | Driver contacts store | Driver/backend | order, store, driver, timestamp | message content | Contact attempted | Operational |
| support_escalated | Support case opened | Driver/backend | order, driver, timestamp, category | raw ID data | Escalation | Safety/compliance |
| return_required | Return mandated | Backend | order, store, driver, timestamp, reason link | ID data | Return required | Inventory/compliance |
| return_acknowledged_by_driver | Driver acknowledges return | Driver/backend | order, driver, timestamp | ID data | Return acknowledged | Inventory |
| return_started | Return navigation begins | Driver/backend | order, store, driver, timestamp | ID data | Returning | Inventory |
| arrived_at_store_for_return | Driver arrives for return | Driver/backend | order, store, driver, timestamp | ID data | Arrived for return | Inventory |
| return_handoff_submitted | Driver submits return handoff | Driver/backend | order, store, driver, timestamp | ID data | Handoff submitted | Inventory |
| return_confirmed_by_store | Store confirms return | Store/backend | order, store, store-user, timestamp | ID data | Return confirmed | Inventory review |
| return_rejected_by_store | Store rejects return | Store/backend | order, store, store-user, timestamp, reason | ID data | Return rejected | Inventory exception |
| return_exception_opened | Return exception raised | Backend | order, store, driver, timestamp, reason | ID data | Exception | Inventory/support |
| offline_action_queued | Action queued offline | Mobile/backend | action ref, idempotency key, timestamp | ID data | Pending | Reliability |
| offline_action_replayed | Queued action reconciled | Backend | action ref, idempotency key, timestamp | ID data | Reconciled | Reliability |
| duplicate_action_rejected | Duplicate side effect blocked | Backend | action ref, idempotency key, timestamp | ID data | None | Reliability/audit integrity |

Audit rules: **no raw ID data and no full ID number in any event**; the audit
timeline is backend-owned; idempotency prevents duplicate critical events.

## 19. Idempotency and Offline Retry

- **Client-generated idempotency keys (or an equivalent future pattern):** each
  state-changing action carries a key so retries are dedupable.
- **Duplicate proof submissions:** the backend accepts the first and rejects
  duplicates (`duplicate_action_rejected`).
- **Duplicate failed-delivery submissions:** deduped to a single failure.
- **Duplicate return submissions:** deduped to a single return action.
- **Offline queue for non-sensitive actions:** non-sensitive operational actions
  may queue and replay when online.
- **Restricted completion blocked until backend acceptance:** restricted delivery
  cannot complete offline; completion waits for backend acceptance.
- **Backend transition validation:** every replayed action is re-validated
  against the authoritative lifecycle state.
- **Stale submission handling:** submissions against an outdated state are
  rejected, not blindly applied.
- **Conflict handling:** if the server state has advanced, the app reconciles to
  the backend's state rather than forcing the local one.
- **Audit replay semantics:** replay emits `offline_action_replayed`; duplicates
  emit `duplicate_action_rejected`; the timeline is not double-written.
- **No local override while offline** — the app never finalizes proof,
  completion, failure, or return locally.

## 20. Store/Admin Visibility

Store and Admin observe outcomes through backend events and redacted records.

**Store visibility:**

- delivery state;
- failed delivery reason category;
- return-required status;
- driver return ETA/status (**future candidate**);
- returned pending confirmation;
- the return confirmation action (for its own orders);
- exception state;
- an audit timeline summary.

**Admin visibility:**

- the proof/failure/return timeline;
- driver/order/store/customer references, **privacy-safe**;
- failure reason analytics;
- return exceptions;
- compliance-related failure patterns;
- the support escalation link;
- audit detail;
- **no raw ID data**;
- **no full ID number**;
- **no unauthorized customer PII.**

Store/Admin visibility comes through backend events and redacted records, never
direct mobile mutation of panel state.

## 21. Mobile Screen / Flow Dependencies

This document depends conceptually on the prior Dr.1.0 screen inventory
(`docs/dr.1.0-driver-screen-inventory.md`) and user flows
(`docs/dr.1.0-driver-user-flows.md`). The proof/failure/return architecture maps
to these screens (no implementation, dependency mapping only):

- **Active delivery screen** — reflects the completion state model.
- **Arrival screen** — `arrived_at_customer`; may start the wait timer.
- **Age/ID verification screen** — precondition for restricted proof (Dr.1.0.G).
- **Proof of delivery screen** — `proof_required` → `proof_submitted`.
- **Failed delivery reason screen** — submits the failure reason model.
- **Wait timer screen** — the customer-unavailable wait.
- **Support escalation screen** — opens support cases.
- **Return-to-store screen** — `return_required` → return navigation.
- **Store return handoff screen** — `return_handoff_submitted` and pending
  confirmation.
- **Offline/retry screen** — surfaces queued/reconciled actions and blocks
  restricted completion while offline.

## 22. Future Enhancements

The following are **future-only** items, reserved and not implemented. Each is
gated on legal/product review and a later phase.

### Customer PIN

- **Purpose:** a customer-provided PIN as a proof/pairing factor.
- **Prerequisite:** product/legal review.
- **Risk:** low (PIN, not ID); does not replace 21+ verification.
- **Backend requirement:** validate the PIN as a proof element.
- **Mobile requirement:** capture the PIN.
- **Store/Admin requirement:** visibility of PIN-proof outcome.
- **Phase target candidate:** Dr.1.5.

### QR handoff code

- **Purpose:** scan-based handoff integrity.
- **Prerequisite:** product review.
- **Risk:** low.
- **Backend requirement:** validate the code.
- **Mobile requirement:** scan capability.
- **Store/Admin requirement:** code-event visibility.
- **Phase target candidate:** Dr.1.5.

### Customer signature

- **Purpose:** captured signature as proof.
- **Prerequisite:** legal review.
- **Risk:** medium (PII).
- **Backend requirement:** validate/store per policy (redacted reference).
- **Mobile requirement:** signature capture.
- **Store/Admin requirement:** redacted reference visibility.
- **Phase target candidate:** Dr.1.5.

### Photo proof (if legally allowed)

- **Purpose:** a non-ID delivery photo as proof.
- **Prerequisite:** legal review; must not capture ID documents.
- **Risk:** high (privacy).
- **Backend requirement:** validate/store per policy.
- **Mobile requirement:** capture per the approved policy only.
- **Store/Admin requirement:** redacted reference visibility.
- **Phase target candidate:** Dr.1.5.

### Geofence-verified arrival

- **Purpose:** validate arrival/proximity via geofence.
- **Prerequisite:** legal/privacy review; retention limits.
- **Risk:** medium (location).
- **Backend requirement:** proximity validation.
- **Mobile requirement:** location provision.
- **Store/Admin requirement:** redacted context.
- **Phase target candidate:** Dr.1.4.

### Route deviation detection

- **Purpose:** detect anomalous routes for safety.
- **Prerequisite:** privacy review.
- **Risk:** medium (location).
- **Backend requirement:** anomaly detection.
- **Mobile requirement:** background location (future).
- **Store/Admin requirement:** safety oversight.
- **Phase target candidate:** future.

### Richer support case tooling

- **Purpose:** messages, attachments, and richer case workflows.
- **Prerequisite:** product review.
- **Risk:** medium (attachments must avoid ID data).
- **Backend requirement:** case messaging/attachment storage.
- **Mobile requirement:** messaging/attachment UI.
- **Store/Admin requirement:** case management.
- **Phase target candidate:** Dr.1.4/Dr.1.6.

### Store return inspection workflow

- **Purpose:** granular full/partial/missing/damaged return inspection.
- **Prerequisite:** product review.
- **Risk:** low/medium (inventory accuracy).
- **Backend requirement:** inspection states and outcomes.
- **Mobile requirement:** none (store-side).
- **Store/Admin requirement:** inspection UI.
- **Phase target candidate:** Dr.1.5/Dr.1.6.

### Inventory restock workflow

- **Purpose:** a reviewed restock path after confirmed return.
- **Prerequisite:** backend inventory authority; admin review.
- **Risk:** medium (stock integrity).
- **Backend requirement:** reviewed restock action + inventory-log integration.
- **Mobile requirement:** none.
- **Store/Admin requirement:** restock review.
- **Phase target candidate:** Dr.1.5/Dr.1.6.

### Admin dispute resolution

- **Purpose:** admin tooling to resolve return/proof disputes.
- **Prerequisite:** product review.
- **Risk:** low.
- **Backend requirement:** dispute states and audited resolutions.
- **Mobile requirement:** none.
- **Store/Admin requirement:** dispute resolution UI.
- **Phase target candidate:** Dr.1.6.

### Customer dispute portal

- **Purpose:** a customer-facing dispute channel.
- **Prerequisite:** customer app exists; product/legal review.
- **Risk:** medium (PII).
- **Backend requirement:** dispute intake.
- **Mobile requirement:** none (customer app).
- **Store/Admin requirement:** dispute visibility.
- **Phase target candidate:** future (post Customer App).

### Delivery evidence packet

- **Purpose:** a redacted, bundled evidence record per delivery.
- **Prerequisite:** legal review; retention policy.
- **Risk:** medium (aggregated data).
- **Backend requirement:** evidence assembly (redacted).
- **Mobile requirement:** none.
- **Store/Admin requirement:** evidence review.
- **Phase target candidate:** Dr.1.6.

### Fraud / risk scoring

- **Purpose:** risk signals for suspicious deliveries/returns.
- **Prerequisite:** data/legal review.
- **Risk:** medium (fairness, privacy).
- **Backend requirement:** scoring on authoritative events.
- **Mobile requirement:** none.
- **Store/Admin requirement:** risk oversight.
- **Phase target candidate:** Dr.1.6.

## 23. Phase Target Map

Future implementation of this architecture maps to:

- **Dr.1.1 — backend models/endpoints/audit foundations:** completion and return
  state models, proof acceptance, failure reasons, return-required decisions,
  audit events, idempotency basics.
- **Dr.1.2 — mobile API client/offline queue foundation:** secure API client,
  idempotency-key handling, offline queue scaffolding, privacy handling.
- **Dr.1.3 — driver MVP delivery lifecycle:** manual proof, failed delivery, and
  return-to-store in the driver app against Dr.1.1 endpoints.
- **Dr.1.4 — support/safety escalation:** support cases, safety escalation, store
  contact, and exception handling.
- **Dr.1.5 — compliance/legal-approved proof upgrades:** signature/photo/PIN/QR/
  geofence proof and store return inspection, gated on legal review.
- **Dr.1.6 — performance/analytics/admin intelligence:** failure analytics,
  dispute resolution, evidence packets, and risk scoring.

Each phase requires its own contract lock, diagnostic, gameplan, implementation,
validation, and pass/fail report.

## 24. No-Go Reminder

This subphase is documentation only. It does **not** create:

- backend endpoints
- database tables
- migrations
- schemas
- services
- frontend UI
- mobile screens
- a Flutter project
- a Capacitor project
- dependency changes
- tests
- CI/config changes
- real proof upload
- signature capture
- photo proof
- geofence implementation
- navigation implementation
- inventory mutation
- support system implementation
- Stripe/payment/payout logic
- customer app behavior
- production launch

Any work that would cross one of these boundaries requires a separate, explicitly
approved future phase with its own contract, consistent with
`docs/dr.1.0-driver-app-contract-lock.md` and `docs/f2.27-contract-lock.md`.
