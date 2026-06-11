# Dr.1.0 Driver Domain Architecture

## Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.C — NubeRush Driver Domain Architecture
- **Status:** Draft for Dr.1.0 documentation
- **Scope:** documentation only
- **Implementation:** none

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them.

## Purpose

This document defines the core domains of the NubeRush Driver App. It is the
product, compliance, operational, backend-authority, and mobile-responsibility
map for a full driver operations platform — not a small "assigned orders"
viewer.

The architecture rests on five fixed positions:

- **Mobile is the operational surface.** The Driver App is where field execution
  happens: availability, offers, pickup, handoff, transit, verification, proof,
  completion, failure, and return.
- **Backend is the authority.** Eligibility, assignment, order state, compliance
  rules, proof requirements, completion, failure, return flow, inventory
  implications, and audit are decided server-side.
- **Store and Admin panels are the visibility and oversight layer.** They
  observe and supervise delivery through backend events; they do not take over
  the driver's field role and the Driver App does not take over theirs.
- **Driver access must be order-scoped, not store-wide.** A driver sees and acts
  only on the deliveries assigned to them; the Driver App is never a
  store-operations surface.
- **Restricted-product compliance is core to the product architecture.**
  Smoke-shop and vape delivery, 21+ verification, proof of delivery,
  failed-delivery handling, and return-to-store accountability shape every
  domain below; they are not add-ons.

## Domain Architecture Principles

- **Backend-authorized operations.** Every state-changing driver action is
  validated and recorded by the backend; the app requests transitions, the
  backend grants or rejects them.
- **Order-scoped driver visibility.** Drivers see only offered and assigned
  orders, never store-wide inventory, orders, or administration.
- **Compliance-first restricted delivery.** Restricted-product handling, 21+
  verification, and audit are first-class requirements in the relevant domains.
- **No unattended restricted delivery.** Leave-at-door is forbidden for
  restricted products; the recipient must be present and verified.
- **No raw ID image storage in MVP.** The MVP does not capture or store raw
  identity-document images, full ID numbers, or OCR output.
- **Return-to-store accountability.** Restricted failures route to an
  accountable, audited return; the driver cannot unilaterally close it.
- **Store handoff accountability.** Pickup release and return receipt are
  confirmed on the store side and recorded as audit events.
- **Audit-first delivery lifecycle.** Every meaningful lifecycle event is
  emitted to a compliance-grade audit timeline.
- **Mobile as action surface, not business-rule owner.** A "mobile
  responsibility" never means the app owns a business decision.
- **Store/Admin visibility bridge.** Oversight surfaces consume backend events,
  not direct mobile-to-panel state.
- **Idempotent driver actions.** Critical transitions are idempotent so retries
  never double-apply.
- **Privacy and redaction by default.** Customer contact is masked, sensitive
  documents are not stored, and audit logs hold no raw ID data.
- **Future features reserved without implementation.** Growth and
  compliance-upgrade capabilities are architected as reserved slots, not built
  now.

## Domain Summary Table

| Domain | Purpose | Core phase target | Backend authority level | Mobile responsibility level | Compliance sensitivity | Notes |
|---|---|---|---|---|---|---|
| Driver Account | Driver identity, status, eligibility surface | Dr.1.2 (backend Dr.1.1) | High | Medium | High | Backend owns identity/eligibility |
| Driver Onboarding | Activate a driver toward eligibility | Dr.1.2 | High | High | High | Onboarding alone does not authorize online |
| Driver Documents | License, ID, vehicle docs, expiry | Dr.1.2 | High | High | High | No approved docs, no online |
| Vehicle Profile | Delivery vehicle record | Dr.1.2 | Medium | Medium | Medium | No ride-class/passenger logic |
| Driver Compliance | Computed eligibility gate | Dr.1.1 | High | Low | Critical | Backend decides eligibility |
| Driver Training | Policy and procedure readiness | Dr.1.2 | High | Medium | High | Restricted/21+ modules required |
| Availability / Online State | Controlled online/offline state | Dr.1.3 | High | High | High | Backend blocks online if gates fail |
| Delivery Offers | Time-boxed offers on existing orders | Dr.1.3 | High | High | High | Pre-accept privacy boundary |
| Driver Assignment | Dedicated assignment lifecycle | Dr.1.3 (backend Dr.1.1) | High | Medium | High | Order-scoped visibility |
| Active Delivery | Delivery state machine view | Dr.1.3 | High | High | Critical | Plugs into existing order lifecycle |
| Store Pickup | Collect the correct order | Dr.1.3 | High | High | High | No pickup if handoff/compliance fails |
| Store Handoff | Accountable store release | Dr.1.3 | High | Medium | High | PIN + store confirmation |
| Navigation | Routing context and handoff | Dr.1.3 | Low | High | Low | External nav apps |
| Customer Dropoff | In-person handoff control | Dr.1.3 | High | High | Critical | No leave-at-door for restricted |
| Restricted Product Verification | Enforce restricted delivery rules | Dr.1.3 | High | High | Critical | Backend decides completion |
| Age / ID Verification | 21+ manual verification (MVP) | Dr.1.3 (upgrade Dr.1.5) | High | High | Critical | No raw ID images |
| Proof of Delivery | Bind proof to completion | Dr.1.3 | High | High | Critical | No proof, no delivered |
| Failed Delivery | Structured failure capture | Dr.1.3 | High | High | Critical | Restricted failure → return |
| Return to Store | Accountable return path | Dr.1.3 | High | Medium | Critical | Driver cannot self-close |
| Safety Toolkit | Field safety actions | Dr.1.4 | Medium | High | High | Emergency + reporting |
| Communication | Masked driver/customer/store contact | Dr.1.4 (basic Dr.1.3) | Medium | High | Medium | No personal phone exposure |
| Support Center | Structured help and tickets | Dr.1.4 | Medium | High | Medium | Compliance/safety topics |
| Earnings | Visibility only, no payouts | Dr.1.6 | Medium | Medium | Low | No money movement |
| Promotions / Opportunities | Demand + legal-zone surfaces | Dr.1.6 (zones Dr.1.4) | Medium | Medium | Medium | Legal/restricted zones core |
| Performance | Operational + compliance metrics | Dr.1.6 (basics Dr.1.4) | High | Low | Medium | Compliance signals |
| Rewards / Driver Status | Status tiers and badges | Dr.1.6 | High | Low | Medium | Future growth module |
| Notifications | Operational and compliance pushes | Dr.1.2 (content Dr.1.3) | High | High | Medium | Compliance pushes non-optional |
| Account Settings | Driver app configuration | Dr.1.2 | Medium | High | Medium | Privacy/legal disclosures |
| Geofencing / Legal Zones | Arrival and legal-zone enforcement | Dr.1.3 (zones Dr.1.4) | High | Medium | High | Distance enforcement |
| Technical Reliability | Resilient client behavior | Dr.1.2 | High | High | High | Idempotency + secure storage |
| Audit / Compliance Timeline | Compliance-grade event record | Dr.1.1 | High | Low | Critical | No raw ID data in logs |
| Admin / Store Visibility Bridge | Oversight via backend events | Dr.1.4 | High | Low | High | Web surfaces, not driver app |

## Full Domain Definitions

Each domain below uses a consistent structure: Purpose, Users Involved, Core
Capabilities, NubeRush-Specific Rules, Backend Authority, Mobile
Responsibilities, Store/Admin Visibility, Future Phase Target, and Risks. A
"mobile responsibility" describes what the app presents, collects, initiates, or
submits — never ownership of a business decision.

## Driver Account

### Purpose
Establish and surface the driver's authoritative identity, status, and
eligibility so every downstream domain can rely on a single backend-owned
account record.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Driver identity (legal name, verified phone, verified email, photo).
- Driver status (pending, active, suspended, blocked).
- Account approval state surfaced read-only.
- Blocked / deactivated status that revokes operating authority.
- Policy acknowledgments (restricted-product, 21+, safety) recorded with audit.

### NubeRush-Specific Rules
- Driver date of birth drives backend-computed 21+ eligibility for restricted
  deliveries.
- A block or deactivation immediately removes restricted-delivery authority; the
  app cannot override it.
- Required policy acknowledgments must exist before the driver can go online.

### Backend Authority
- Owns the identity record and all status transitions.
- Computes eligibility (including driver 21+) — never the app.
- Determines whether the account may operate at all.

### Mobile Responsibilities
- Display identity, status, and approval state read-only.
- Collect and submit policy acknowledgments.
- Surface block/deactivation states and stop operation accordingly.

### Store/Admin Visibility
- Admin Panel sees driver status, approval state, and policy-acknowledgment
  history through backend records.

### Future Phase Target
- Dr.1.2 (account surface), with eligibility computation in Dr.1.1.

### Risks
- **Compliance risk:** stale or client-trusted status could allow an ineligible
  driver to operate — eligibility must be server-decided.
- **Backend authority risk:** any client-side status override would break the
  authority model.
- **Privacy risk:** identity data must be handled and displayed minimally.

## Driver Onboarding

### Purpose
Move a provisioned driver through the steps required to become eligible, without
itself granting the right to operate.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Signup via backend-issued invitation (provisioned, not open self-signup).
- Activation checklist driven by the backend.
- Profile setup.
- Phone and email verification.
- Document checklist.
- Vehicle setup.
- Training checklist.
- Approval-pending state.
- Rejected / action-required flow with reason and resubmission.

### NubeRush-Specific Rules
- The document and training checklists include restricted-product and 21+
  requirements.
- **Completing onboarding is not sufficient to go online**; the driver may
  operate only if backend eligibility (Driver Compliance) passes.

### Backend Authority
- Owns checklist definition, step completion validation, and approval decisions.
- Issues invitations and provisions driver accounts.

### Mobile Responsibilities
- Guide the driver through checklist steps and collect inputs.
- Display pending/rejected states and reasons.
- Submit completed steps for backend validation.

### Store/Admin Visibility
- Admin Panel sees onboarding progress, approval state, and rejection reasons.

### Future Phase Target
- Dr.1.2.

### Risks
- **Compliance risk:** treating onboarding completion as authorization would
  bypass eligibility.
- **Scope creep risk:** onboarding must not absorb compliance-decision logic;
  that belongs to Driver Compliance.
- **Privacy risk:** verification artifacts must be handled minimally.

## Driver Documents

### Purpose
Manage the documents that authorize a driver to operate, including their state,
expiry, and remediation.

### Users Involved
- Driver
- Admin
- Backend system (and any verification vendor, status-only)

### Core Capabilities
- Driver license upload.
- Government ID upload.
- Selfie verification (deferred).
- Vehicle registration.
- Vehicle insurance.
- Background check status (read-only result).
- Document expiration tracking and alerts.
- Rejection reason and resubmission.

### NubeRush-Specific Rules
- **No approved documents, no online mode** — required documents must be
  approved before the driver can operate.
- Documents are the driver's own authorization records and are distinct from any
  customer 21+ ID check.
- Sensitive documents are handled privacy-safely; raw report contents are not
  surfaced (status only).

### Backend Authority
- Owns document approval/rejection and expiry evaluation.
- Decides whether the document set satisfies operating requirements.

### Mobile Responsibilities
- Capture/upload documents and display their state.
- Surface expiry and rejection notices and resubmission paths.

### Store/Admin Visibility
- Admin Panel sees document state, expiry, and rejection history.

### Future Phase Target
- Dr.1.2.

### Risks
- **Privacy risk:** document images are sensitive; storage and access must be
  controlled and minimal.
- **Compliance risk:** expired/unapproved documents must block operation.
- **Backend authority risk:** approval must never be client-decided.

## Vehicle Profile

### Purpose
Record the delivery vehicle a driver uses, for identification and operating
authorization, without any rideshare semantics.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Vehicle attributes: make, model, year, color, plate.
- Active vehicle selection.
- Vehicle approval status.
- Linkage to insurance and registration documents.

### NubeRush-Specific Rules
- **No passenger-capacity or ride-class logic** — there are no ride tiers,
  passengers, or airport-permit concepts.
- A single active delivery vehicle is sufficient for the MVP.

### Backend Authority
- Owns vehicle approval state and the link between vehicle and required
  documents.
- Gates operation on an approved vehicle.

### Mobile Responsibilities
- Display vehicle profile and approval state.
- Submit vehicle details and active-vehicle selection.

### Store/Admin Visibility
- Admin Panel sees vehicle record and approval state.

### Future Phase Target
- Dr.1.2.

### Risks
- **Scope creep risk:** importing rideshare vehicle concepts (tiers, capacity)
  would add irrelevant complexity.
- **Compliance risk:** operating on an unapproved/uninsured vehicle must be
  blocked.

## Driver Compliance

### Purpose
Compute, server-side, whether a driver is currently eligible to operate and to
receive restricted deliveries — the single gate the rest of the system trusts.

### Users Involved
- Admin
- Backend system
- Driver (as the subject; read-only consumer)

### Core Capabilities
- Aggregate eligibility signals into a single decision:
  - driver active,
  - driver approved,
  - driver 21+,
  - required documents approved,
  - required vehicle approved,
  - training completed,
  - restricted-product policy acknowledged,
  - no active suspension,
  - device permissions healthy.

### NubeRush-Specific Rules
- Driver 21+ eligibility and restricted-product policy acknowledgment are
  required for restricted deliveries specifically.
- A suspension or block immediately fails eligibility regardless of other
  signals.

### Backend Authority
- **Decides eligibility.** This is the authoritative gate consumed by
  Availability/Online State, Delivery Offers, and Assignment.
- Owns suspension/block enforcement.

### Mobile Responsibilities
- Display the current eligibility state and the specific unmet requirement(s).
- Surface device-permission health as an input signal.
- Never compute or assert eligibility locally.

### Store/Admin Visibility
- Admin Panel sees driver eligibility and the reasons for ineligibility.

### Future Phase Target
- Dr.1.1.

### Risks
- **Backend authority risk:** any client-side eligibility shortcut is a critical
  failure.
- **Compliance risk:** an incorrect eligibility computation could authorize an
  unqualified driver for restricted delivery.
- **Mobile bypass risk:** the app must not allow operation when eligibility is
  false.

## Driver Training

### Purpose
Ensure drivers have completed the policy and procedure training required to
deliver restricted products safely and lawfully.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Delivery basics.
- Restricted-product delivery policy.
- 21+ verification policy.
- Valid ID checklist.
- Failed ID handling.
- Return-to-store policy.
- Safety training.
- Incident reporting.
- Quiz / certification (future).

### NubeRush-Specific Rules
- Restricted-product, 21+, valid-ID, failed-ID, and return-to-store modules are
  required before a driver may take restricted deliveries.
- Training completion feeds Driver Compliance as an eligibility signal.

### Backend Authority
- Owns training-module definitions and completion records.
- Determines whether training requirements are met.

### Mobile Responsibilities
- Present training content and capture completion.
- Submit completion for backend validation.

### Store/Admin Visibility
- Admin Panel sees training completion state per driver.

### Future Phase Target
- Dr.1.2.

### Risks
- **Compliance risk:** unverified training completion weakens the age-gate
  posture.
- **Scope creep risk:** graded certification is a future module, not MVP.

## Availability / Online State

### Purpose
Control whether a driver is online and able to receive offers, gated by
eligibility and device readiness.

### Users Involved
- Driver
- Backend system

### Core Capabilities
- Go online / go offline.
- Pause and resume requests.
- Stop new requests (finish current, accept no new).
- Online-time and active-time visibility.
- GPS, network, camera, and notification permission/health checks.

### NubeRush-Specific Rules
- **The backend must block going online if requirements fail** (eligibility,
  required permissions, GPS/network health).
- Location permission is required to operate.

### Backend Authority
- Authorizes the online state based on Driver Compliance and reported device
  health.
- Records availability transitions as audit events.

### Mobile Responsibilities
- Run pre-online permission and connectivity checks and report them.
- Initiate online/offline/pause/resume actions and reflect authorized state.

### Store/Admin Visibility
- Admin Panel can see driver availability state through backend events.

### Future Phase Target
- Dr.1.3.

### Risks
- **Compliance risk:** allowing online without eligibility/permissions would
  enable non-compliant delivery.
- **Backend authority risk:** the online decision must be server-authorized, not
  purely client-side.
- **Support/safety risk:** operating without GPS/network undermines safety and
  audit.

## Delivery Offers

### Purpose
Present time-boxed delivery offers for existing backend orders and capture the
driver's accept/decline, without exposing sensitive details before acceptance.

### Users Involved
- Driver
- Backend system

### Core Capabilities
- Offer content: store name, store address, pickup distance, approximate dropoff
  zone, estimated duration, estimated earnings (deferred visibility).
- Restricted-product flag and ID-required flag.
- Offer timer with a bounded accept window.
- Accept / decline with structured decline reasons.

### NubeRush-Specific Rules
- **Pre-accept customer privacy boundary:** only an approximate dropoff zone is
  shown before acceptance; the exact customer address and contact are withheld
  until the offer is accepted.
- Restricted and ID-required flags are shown before acceptance so the driver
  knows the delivery's requirements.

### Backend Authority
- Issues offers only to eligible drivers and only for valid existing orders.
- Owns the offer timer and expiry; validates accept/decline.

### Mobile Responsibilities
- Display offer content within the privacy boundary.
- Submit accept/decline and decline reasons.

### Store/Admin Visibility
- Admin Panel may see offer issuance/decline patterns through backend events.

### Future Phase Target
- Dr.1.3.

### Risks
- **Privacy risk:** leaking exact customer details pre-accept violates the
  privacy boundary.
- **Compliance risk:** offering restricted deliveries to ineligible drivers.
- **Backend authority risk:** offer eligibility and expiry must be server-owned.

## Driver Assignment

### Purpose
Track the dedicated lifecycle of a delivery assignment to a driver, separate
from the order's own state, so assignment changes do not overload order status.

### Users Involved
- Driver
- Store employee / manager (dispatch)
- Admin
- Backend system

### Core Capabilities
- Assignment lifecycle: offered, accepted, declined, canceled, expired,
  completed.
- Reassignment support on decline/failure.
- Manual dispatch support (store/admin-driven).
- Future auto-dispatch (deferred).

### NubeRush-Specific Rules
- **A driver sees only offered and assigned orders** — never store-wide orders.
- Assignment state is distinct from order state and lives in its own lifecycle.

### Backend Authority
- Owns the assignment state machine and all transitions.
- Performs reassignment and dispatch decisions.

### Mobile Responsibilities
- Display offered and assigned deliveries.
- Submit accept/decline; reflect backend-driven reassignment.

### Store/Admin Visibility
- Store Panel sees the assigned driver and assignment state; Admin sees dispatch
  patterns.

### Future Phase Target
- Dr.1.3, with the assignment model defined in Dr.1.1.

### Risks
- **Backend authority risk:** assignment transitions must be server-validated.
- **Scope creep risk:** auto-dispatch is future; manual dispatch first.
- **Mobile bypass risk:** the app must not surface unassigned/store-wide orders.

## Active Delivery

### Purpose
Provide the driver's view of, and controls for, the current delivery as it moves
through its lifecycle, plugged into the existing backend order lifecycle.

### Users Involved
- Driver
- Store employee
- Customer
- Backend system

### Core Capabilities
- Lifecycle states surfaced to the driver: delivery accepted, en route to store,
  arrived at store, waiting for order, pickup confirmed, en route to customer,
  arrived at customer, verification started, proof completed, delivery
  completed, delivery failed, return required, returned to store.

### NubeRush-Specific Rules
- **Do not overload OrderStatus with every micro-state.** Fine-grained driver
  progress (e.g., "waiting for order", "verification started") is modeled in the
  driver/assignment layer, not by inflating the canonical order state machine.
- Completion is permitted only after proof and verification pass.

### Backend Authority
- Owns the canonical order state machine and authorizes each transition.
- Maps driver-layer progress to the existing order lifecycle without inventing a
  parallel order model.

### Mobile Responsibilities
- Display current state and the next valid action.
- Submit transition requests (picked up, out for delivery, verified, delivered,
  failed, returned).

### Store/Admin Visibility
- Store Panel sees out-for-delivery, failed, and return states; Admin sees the
  full lifecycle through audit.

### Future Phase Target
- Dr.1.3.

### Risks
- **Backend authority risk:** the app must request, not assert, transitions.
- **Compliance risk:** premature "delivered" without proof/verification.
- **Scope creep risk:** over-modeling micro-states into core order status.

## Store Pickup

### Purpose
Ensure the driver collects the correct order from the correct store with the
right contents before transit.

### Users Involved
- Driver
- Store employee
- Backend system

### Core Capabilities
- Confirm correct store and correct order.
- Order ready status and order-number match.
- Bag count and item count confirmation.
- Pickup checklist (including restricted-product confirmation).
- Pickup issue report (store closed, order not ready).

### NubeRush-Specific Rules
- **No pickup if handoff or compliance fails** — pickup confirmation depends on a
  valid store handoff and the order being releasable.
- "Restaurant not ready" is adapted to "store order not ready".

### Backend Authority
- Authorizes the pickup-confirmed transition and validates order-match.
- Owns the link between pickup and the store handoff event.

### Mobile Responsibilities
- Guide the pickup checklist and capture confirmations.
- Submit pickup confirmation and any pickup issue.

### Store/Admin Visibility
- Store Panel sees pickup readiness and confirmation; Admin sees pickup issues.

### Future Phase Target
- Dr.1.3.

### Risks
- **Compliance risk:** picking up the wrong order or restricted items without
  confirmation.
- **Backend authority risk:** pickup confirmation must be server-validated.
- **Inventory risk:** mismatched item/bag counts feed downstream inventory
  errors.

## Store Handoff

### Purpose
Make the store accountable for releasing an order to a driver, recorded as an
auditable handoff.

### Users Involved
- Driver
- Store employee
- Store manager
- Backend system

### Core Capabilities
- Store employee PIN at release.
- Store employee confirmation of release.
- QR / barcode handoff (future).
- Manager override (future).

### NubeRush-Specific Rules
- **Store-side release accountability:** the store confirms release; the driver
  cannot self-authorize a pickup of restricted product.
- The handoff is recorded as an audit event.

### Backend Authority
- Validates the store PIN/confirmation and records the handoff.
- Ties handoff success to the pickup-confirmed transition.

### Mobile Responsibilities
- Capture the store employee PIN/confirmation and submit it.
- Reflect handoff success/failure.

### Store/Admin Visibility
- Store Panel performs/confirms the handoff; Admin sees handoff audit events.

### Future Phase Target
- Dr.1.3.

### Risks
- **Compliance risk:** unaccountable release of restricted product.
- **Backend authority risk:** handoff validation must be server-side.
- **Scope creep risk:** QR/manager-override are future, not MVP.

## Navigation

### Purpose
Provide routing context and hand off turn-by-turn navigation to the driver's
preferred external map app.

### Users Involved
- Driver
- Backend system (for ETA/zone data)

### Core Capabilities
- Map view for context.
- Handoff to Apple Maps, Google Maps, or Waze.
- Store route, customer route, and return-to-store route.
- ETA and distance.
- Route recalculation (future), CarPlay / Android Auto (future), internal
  turn-by-turn (future).

### NubeRush-Specific Rules
- Surfaces legal/restricted-zone warnings relevant to restricted delivery.
- Return-to-store routing is a first-class route, not an afterthought.

### Backend Authority
- Provides authoritative store/customer locations and any zone constraints.
- Does not own the external navigation experience.

### Mobile Responsibilities
- Render map context and launch external navigation.
- Display ETA/distance and zone warnings.

### Store/Admin Visibility
- Admin may see ETA/route-share data only through safety/oversight events, not a
  live public feed.

### Future Phase Target
- Dr.1.3.

### Risks
- **Privacy risk:** route/location sharing must be limited to oversight, not
  broadcast.
- **Scope creep risk:** internal turn-by-turn and in-car integrations are
  future.

## Customer Dropoff

### Purpose
Control the customer-side handoff, enforcing in-person delivery for restricted
products.

### Users Involved
- Driver
- Customer
- Backend system

### Core Capabilities
- Delivery instructions.
- Contact customer (masked).
- Arrived at customer.
- Meet customer / meet at door / meet outside.
- Customer-unavailable flow.

### NubeRush-Specific Rules
- **Restricted products require in-person handoff**; the recipient must be
  present.
- **Leave-at-door is blocked for restricted products.**
- Customer unavailability for a restricted order leads to failed delivery and
  return.

### Backend Authority
- Enforces that restricted orders cannot be completed via unattended delivery.
- Authorizes the transition into verification and, ultimately, completion.

### Mobile Responsibilities
- Present dropoff instructions and masked contact.
- Mark arrival and initiate the in-person verification step.

### Store/Admin Visibility
- Admin sees dropoff outcomes through audit; Store sees failed/return states.

### Future Phase Target
- Dr.1.3.

### Risks
- **Compliance risk:** any unattended restricted delivery is a critical breach.
- **Privacy risk:** customer contact must remain masked.
- **Safety risk:** unsafe dropoff situations must route to the safety toolkit.

## Restricted Product Verification

### Purpose
Enforce the rules that make a restricted delivery lawful and safe before
completion is allowed.

### Users Involved
- Driver
- Customer
- Backend system
- Support/admin operator (for escalations)

### Core Capabilities
- Confirm customer present.
- Require valid government ID, 21+, not expired, and that the ID appears to match
  the person.
- Wrong-recipient handling.
- Customer-refusal handling.
- Suspected-fake-ID handling.
- Unsafe-situation handling.

### NubeRush-Specific Rules
- All restricted checks must pass for delivery to proceed; any failure routes to
  Failed Delivery and Return to Store.
- **The backend decides completion** based on the recorded verification result.

### Backend Authority
- Defines required checks per order and accepts/rejects the verification result.
- Blocks completion when verification is not satisfied.

### Mobile Responsibilities
- Present the verification checklist and capture the driver's confirmations.
- Submit the verification result and failure reasons.

### Store/Admin Visibility
- Admin sees verification outcomes and failure patterns; Store sees resulting
  failed/return states.

### Future Phase Target
- Dr.1.3.

### Risks
- **Compliance risk:** delivering to an underage/unverified recipient is a
  critical breach.
- **Safety risk:** fake-ID/unsafe situations must have clear, safe procedures.
- **Backend authority risk:** completion must depend on the backend-accepted
  result.

## Age / ID Verification

### Purpose
Provide the mechanism by which 21+ verification is performed and recorded,
starting with a manual checklist and reserving stronger methods for later.

### Users Involved
- Driver
- Customer
- Backend system

### Core Capabilities
- Manual ID checklist (MVP).
- Scan / OCR / barcode / liveness / vendor verification (future).
- Verification pass/fail outcome.

### NubeRush-Specific Rules
- **No raw ID image storage in the MVP.**
- **No full ID number storage**; only redacted, non-sensitive metadata about the
  check (e.g., that a check occurred and its result).
- Stronger verification methods carry a legal-review dependency before adoption.

### Backend Authority
- Records the verification result and binds it to the order and proof.
- Owns the data-minimization rules for what may be stored.

### Mobile Responsibilities
- Present the manual checklist and capture the pass/fail outcome.
- Submit only redacted metadata, never raw ID images or full ID numbers.

### Store/Admin Visibility
- Admin sees verification results and aggregate failure patterns — never raw ID
  data.

### Future Phase Target
- Dr.1.3 (manual MVP); upgrades in Dr.1.5 subject to legal/compliance approval.

### Risks
- **Privacy risk:** storing raw ID images/numbers would breach the
  data-minimization boundary.
- **Compliance risk:** weak verification undermines the age gate.
- **Scope creep risk:** scan/OCR/vendor must not slip into the MVP.

## Proof of Delivery

### Purpose
Capture evidence that a delivery occurred and bind it, together with the
verification result, to completion.

### Users Involved
- Driver
- Customer
- Backend system

### Core Capabilities
- Driver attestation.
- Timestamp.
- Approximate GPS (future).
- Customer PIN (optional/future).
- Signature (future).
- Photo proof (future, non-ID).

### NubeRush-Specific Rules
- The verification pass is attached to the proof record.
- **No proof, no delivered** — completion requires a valid proof record.

### Backend Authority
- Defines proof requirements and validates the proof before authorizing
  completion.
- Binds proof + verification result to the order.

### Mobile Responsibilities
- Capture attestation and any available proof elements.
- Submit the proof for backend validation.

### Store/Admin Visibility
- Admin sees proof completeness and proof-completion rates.

### Future Phase Target
- Dr.1.3.

### Risks
- **Compliance risk:** completing without adequate proof.
- **Privacy risk:** future photo/signature proof must avoid capturing ID
  documents.
- **Backend authority risk:** completion gating must be server-side.

## Failed Delivery

### Purpose
Capture structured, auditable failure outcomes and route restricted failures to
return.

### Users Involved
- Driver
- Customer
- Support/admin operator
- Backend system

### Core Capabilities
- Structured failure reasons: customer unavailable, no valid ID, expired ID,
  underage, ID mismatch, wrong recipient, customer refused, unsafe location,
  wrong address, vehicle issue, driver emergency, app issue, support required.

### NubeRush-Specific Rules
- **A failed restricted delivery requires return-to-store.**
- Verification-based failures (no valid ID, expired, underage, mismatch,
  refusal) are first-class reasons.

### Backend Authority
- Accepts the failure, records it, and determines whether return is required.
- Owns the consequences for order and inventory.

### Mobile Responsibilities
- Present failure reasons and capture the selected reason/details.
- Submit the failure and reflect the required next step (e.g., return).

### Store/Admin Visibility
- Store sees failed deliveries and required returns; Admin sees failure patterns.

### Future Phase Target
- Dr.1.3.

### Risks
- **Compliance risk:** mishandling a restricted failure (e.g., abandoning the
  product) is a critical breach.
- **Inventory risk:** failures must reconcile through backend/inventory.
- **Backend authority risk:** failure acceptance and return requirement are
  server-decided.

## Return to Store

### Purpose
Provide an accountable path for returning undeliverable restricted product to
the store, closed only with store/backend confirmation.

### Users Involved
- Driver
- Store employee
- Backend system

### Core Capabilities
- Return-required screen.
- Navigate back to the originating store.
- Store return PIN.
- Store employee confirmation of receipt.
- Return completed.

### NubeRush-Specific Rules
- **The driver cannot self-close a restricted return**; the store confirms
  receipt and the backend closes it.
- Inventory implications are handled through backend review, not by the app.

### Backend Authority
- Validates the return PIN/confirmation and closes the return.
- Owns inventory reconciliation for returned product.

### Mobile Responsibilities
- Present the return flow and capture the store confirmation/PIN.
- Submit the return step; reflect closure once the backend confirms.

### Store/Admin Visibility
- Store confirms the returned order; Admin sees return events and rates.

### Future Phase Target
- Dr.1.3.

### Risks
- **Inventory risk:** unaccounted returns corrupt stock and create loss.
- **Compliance risk:** unaccountable handling of restricted product.
- **Backend authority risk:** return closure must be server-confirmed.

## Safety Toolkit

### Purpose
Give drivers immediate safety actions and structured incident reporting for
field delivery.

### Users Involved
- Driver
- Support/admin operator
- Backend system
- Emergency services (external)

### Core Capabilities
- Emergency button.
- Call 911.
- Share current location.
- Share active route with admin/support.
- Report unsafe location, threatening customer, accident, or vehicle issue.
- Cancel for safety.
- Long-stop / route-deviation detection (future).

### NubeRush-Specific Rules
- A safety-driven cancel routes to failed delivery and, for restricted product,
  to return.
- Route/location sharing is directed to oversight (admin/support), not public.

### Backend Authority
- Records safety events and routes them to oversight.
- Owns the relationship between a safety cancel and the delivery/return outcome.

### Mobile Responsibilities
- Present safety actions prominently and initiate them.
- Capture and submit incident reports and location/route shares.

### Store/Admin Visibility
- Admin sees safety incidents and active shares; Support can act on them.

### Future Phase Target
- Dr.1.4.

### Risks
- **Safety risk:** unavailable or buried safety actions endanger drivers.
- **Privacy risk:** location/route sharing must be scoped to oversight.
- **Compliance risk:** safety cancels of restricted orders must still return
  product.

## Communication

### Purpose
Enable necessary driver-to-customer and driver-to-store contact without exposing
personal phone numbers.

### Users Involved
- Driver
- Customer
- Store employee
- Support/admin operator
- Backend system

### Core Capabilities
- Call customer / message customer.
- Call store / message store.
- Contact support.
- Masked phone numbers.
- Quick (canned) compliance-safe messages.

### NubeRush-Specific Rules
- **No personal phone exposure** — numbers are masked on both sides.
- A controlled, compliance-safe quick-message set is used for sensitive
  contexts.

### Backend Authority
- Owns number masking and the allowed message set.
- Records communication events relevant to audit.

### Mobile Responsibilities
- Initiate masked calls/messages and present quick messages.
- Submit communication actions where they are audit-relevant.

### Store/Admin Visibility
- Admin/support may see communication metadata for escalations, not private
  content beyond policy.

### Future Phase Target
- Dr.1.4 (basic masked call available in Dr.1.3).

### Risks
- **Privacy risk:** exposing real phone numbers breaches the masking boundary.
- **Compliance risk:** uncontrolled messaging could create non-compliant
  promises.

## Support Center

### Purpose
Provide drivers structured help, issue reporting, and tickets across delivery,
compliance, and safety problems.

### Users Involved
- Driver
- Support/admin operator
- Backend system

### Core Capabilities
- Help center.
- Topic-based issue reporting: pickup problem, store problem, customer problem,
  ID verification problem, unsafe delivery, accident, vehicle issue, app issue,
  earnings question, policy question.
- Support ticket creation.
- Chat / call support (future).

### NubeRush-Specific Rules
- ID-verification and unsafe-delivery topics are first-class, compliance/safety
  paths.
- Support cases are recorded for audit.

### Backend Authority
- Owns ticket lifecycle and routing.
- Records support cases as audit events.

### Mobile Responsibilities
- Present help topics and capture/submit tickets.
- Surface support responses.

### Store/Admin Visibility
- Admin sees support escalations and case patterns.

### Future Phase Target
- Dr.1.4.

### Risks
- **Support/safety risk:** missing escalation paths leave drivers stranded in
  risky situations.
- **Scope creep risk:** live chat/call is future, not MVP.

## Earnings

### Purpose
Provide visibility into delivery activity and estimated earnings without any
money movement.

### Users Involved
- Driver
- Backend system

### Core Capabilities
- Estimated earnings per delivery (visibility).
- Completed delivery count.
- Delivery history (driver-scoped).
- Earnings summary placeholder.

### NubeRush-Specific Rules
- **No real payouts. No cashout. No Stripe. No payment movement.** Earnings is
  visibility-only in this architecture.
- Tips, bonuses, adjustments, payout method, and tax summaries are deferred to a
  post-payments future.

### Backend Authority
- Owns the source data for counts/history and any earnings estimate.
- Does not move money in this scope.

### Mobile Responsibilities
- Display counts, history, and placeholders read-only.

### Store/Admin Visibility
- Admin may see aggregate delivery counts; payout data is out of scope.

### Future Phase Target
- Dr.1.6 (visibility); payouts remain out of the Dr.1.x scope until payments are
  approved.

### Risks
- **Scope creep risk:** any payout/cashout/Stripe creep violates the no-go
  boundary.
- **Compliance risk:** implying live payment where none exists.

## Promotions / Opportunities

### Purpose
Surface demand and operating-zone information, including the legal zones that
bound restricted delivery.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Busy zones (future), store demand zones (future), bonus windows (future),
  scheduled shifts (future).
- Legal delivery zones and restricted delivery radius.

### NubeRush-Specific Rules
- Legal delivery zones and restricted delivery radius are core compliance
  constructs, not growth features, even though incentive surfaces are deferred.

### Backend Authority
- Owns zone definitions and any future incentive logic.

### Mobile Responsibilities
- Display zones and (future) opportunities; enforce nothing locally beyond
  display.

### Store/Admin Visibility
- Admin manages/observes zones and demand.

### Future Phase Target
- Dr.1.6 for incentives; legal/restricted zones land with Geofencing in Dr.1.4.

### Risks
- **Compliance risk:** restricted/legal zones must be authoritative and enforced
  server-side.
- **Scope creep risk:** incentive features must remain deferred until growth
  phase.

## Performance

### Purpose
Provide operational and compliance performance metrics for drivers and oversight.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Completed deliveries, failed deliveries, return rate.
- Pickup on-time, delivery on-time.
- Acceptance, decline, cancellation rates.
- Proof completion, compliance incidents, restricted delivery success rate,
  audit cleanliness score.

### NubeRush-Specific Rules
- Return rate, proof-completion, compliance-incident, restricted-success, and
  audit-cleanliness metrics are compliance signals specific to NubeRush.

### Backend Authority
- Computes all metrics from authoritative events; the app does not compute them.

### Mobile Responsibilities
- Display metrics read-only.

### Store/Admin Visibility
- Admin sees driver performance and compliance signals.

### Future Phase Target
- Dr.1.6 (basic counts available earlier in Dr.1.4).

### Risks
- **Compliance risk:** misleading or client-computed metrics.
- **Scope creep risk:** ratings/reputation surfaces are deferred.

## Rewards / Driver Status

### Purpose
Define a future status model that rewards compliance and delivery quality,
distinct from rideshare tiers.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Status tiers (e.g., Green / Silver / Gold / Elite) — future.
- Compliance Trusted badge (future).
- Restricted Delivery Certified badge (future).
- Priority delivery / bonus eligibility (future).

### NubeRush-Specific Rules
- Status is tied to compliance and performance, not to a copied rideshare tier
  system.
- This entire domain is deferred as a future growth module.

### Backend Authority
- Owns status computation and badge eligibility.

### Mobile Responsibilities
- Display status/badges read-only (future).

### Store/Admin Visibility
- Admin sees driver status as a compliance/quality signal.

### Future Phase Target
- Dr.1.6.

### Risks
- **Scope creep risk:** building status before the operational/compliance core
  is stable.
- **Compliance risk:** status must not imply authority it does not grant.

## Notifications

### Purpose
Deliver timely operational and compliance notifications to the driver.

### Users Involved
- Driver
- Backend system

### Core Capabilities
- Delivery offer, assignment, offer expiring, order ready, pickup reminder.
- Customer/store/support messages.
- ID verification required, return required.
- Document expiring/rejected, account approved/blocked.
- GPS/network/low-battery, policy update, app update required.

### NubeRush-Specific Rules
- Compliance-critical notifications (ID verification required, return required,
  account blocked, policy update) are non-optional.

### Backend Authority
- Owns notification triggers tied to authoritative state changes.

### Mobile Responsibilities
- Register for and present push notifications; route taps to the right surface.

### Store/Admin Visibility
- Not directly; notification triggers derive from the same backend events
  oversight sees.

### Future Phase Target
- Dr.1.2 (push foundation); delivery-flow content arrives with Dr.1.3.

### Risks
- **Compliance risk:** missed compliance notifications (e.g., return required).
- **Reliability risk:** push delivery failures must degrade gracefully.

## Account Settings

### Purpose
Let drivers configure the app and access account, privacy, legal, and
diagnostic controls.

### Users Involved
- Driver
- Backend system

### Core Capabilities
- Profile, vehicle, documents.
- Notification settings, sound settings, navigation preferences.
- Privacy/security, permissions, language.
- Help/legal, app version, diagnostics.
- Logout, delete account (deferred, backend-gated).

### NubeRush-Specific Rules
- Compliance-critical notifications cannot be disabled.
- Legal/privacy disclosures relevant to restricted delivery are surfaced here.

### Backend Authority
- Owns account-level changes (e.g., deletion) and any server-side preferences.

### Mobile Responsibilities
- Present settings and apply local preferences; submit account-level requests.

### Store/Admin Visibility
- Not applicable beyond account-state changes visible to Admin.

### Future Phase Target
- Dr.1.2 (account deletion process deferred to Dr.1.5).

### Risks
- **Privacy risk:** account deletion must follow a controlled, backend-gated
  process.
- **Compliance risk:** allowing compliance pushes to be silenced.

## Geofencing / Legal Zones

### Purpose
Enforce arrival proximity and legal/operating zone constraints relevant to
restricted delivery.

### Users Involved
- Driver
- Admin
- Backend system

### Core Capabilities
- Store geofence and dropoff geofence.
- Legal delivery zone, blocked zone, restricted zone.
- Delivery radius and high-risk area.
- Pickup and delivery distance enforcement.
- Future city/county/product-specific zones.

### NubeRush-Specific Rules
- Restricted delivery is bounded by legal/restricted zones and delivery radius.
- Pickup-confirm and completion require proximity (distance enforcement), as
  validated by the backend.

### Backend Authority
- Owns zone definitions and validates proximity for pickup/completion.

### Mobile Responsibilities
- Report location and present zone warnings; cannot self-authorize out-of-zone
  actions.

### Store/Admin Visibility
- Admin manages zones; oversight sees zone-related events.

### Future Phase Target
- Dr.1.3 (arrival geofences); legal/restricted zones with Dr.1.4.

### Risks
- **Compliance risk:** delivering outside legal zones.
- **Backend authority risk:** distance/zone enforcement must be server-validated,
  not client-trusted.

## Technical Reliability

### Purpose
Ensure the Driver App behaves reliably and safely under real field conditions.

### Users Involved
- Driver
- Backend system

### Core Capabilities
- Offline handling, retry queue, idempotent actions.
- Secure token storage, refresh tokens, device binding (future).
- Push notifications, background location (future).
- Crash reporting, network/GPS diagnostics, state restoration.
- Remote config, feature flags, app version enforcement.
- Event logging, monitoring.

### NubeRush-Specific Rules
- Critical transitions (pickup, verification, completion, failure, return) are
  idempotent and retry-safe so the audit timeline never double-records.
- Event logging feeds the compliance audit timeline.

### Backend Authority
- Defines idempotency keys/semantics and consumes client events.
- Owns remote config, feature flags, and minimum-version enforcement.

### Mobile Responsibilities
- Implement offline/retry behavior, secure storage, diagnostics, and state
  restoration; emit events reliably.

### Store/Admin Visibility
- Not directly; reliability surfaces through monitoring, not panels.

### Future Phase Target
- Dr.1.2.

### Risks
- **Audit integrity risk:** non-idempotent retries could duplicate or lose
  compliance events.
- **Security risk:** weak token storage exposes driver sessions.
- **Reliability risk:** poor offline handling breaks field operations.

## Audit / Compliance Timeline

### Purpose
Maintain a compliance-grade, backend-owned timeline of every meaningful delivery
and compliance event.

### Users Involved
- Admin
- Backend system
- Driver (as subject)

### Core Capabilities
- Events: driver online/offline; offered/accepted/declined; assigned; arrived at
  store; handoff started/confirmed; pickup confirmed; out for delivery; arrived
  at customer; contacted customer; verification started; age verification
  passed/failed; proof recorded; completed; failed; return
  required/started/returned/confirmed; safety issue; support case.

### NubeRush-Specific Rules
- **No raw ID data in audit logs** — the timeline records that verification
  occurred and its result, never raw ID images or full ID numbers.
- The timeline is the authoritative compliance record consumed by oversight.

### Backend Authority
- Owns and writes the audit timeline; events are server-recorded.

### Mobile Responsibilities
- Emit the originating actions reliably and idempotently; the app does not own
  the audit record.

### Store/Admin Visibility
- Admin sees the full delivery audit timeline; Store sees the subset relevant to
  its orders.

### Future Phase Target
- Dr.1.1.

### Risks
- **Privacy risk:** leaking raw ID data into logs is a critical breach.
- **Audit integrity risk:** missing or duplicated events undermine compliance.
- **Backend authority risk:** the audit record must be server-owned.

## Admin / Store Visibility Bridge

### Purpose
Define how the existing Store and Admin panels gain visibility into driver
operations, through backend events rather than direct mobile state.

### Users Involved
- Store employee / manager
- Admin
- Backend system

### Core Capabilities
- Store Panel: assigned driver, driver en route, pickup confirmed, out for
  delivery, failed delivery, return required, returned to store, store return
  confirmation.
- Admin Panel: driver compliance, delivery audit timeline, verification failure
  patterns, incident reports, support escalations.

### NubeRush-Specific Rules
- **Driver App actions must be visible through backend events, not direct
  mobile-to-panel state.**
- This domain reuses the existing Store/Admin web surfaces; it does not build a
  parallel oversight app.

### Backend Authority
- Emits the events the panels consume and enforces tenancy/scoping for what each
  panel may see.

### Mobile Responsibilities
- None directly — the Driver App produces the underlying actions/events; it does
  not push state to panels.

### Store/Admin Visibility
- This domain is the visibility layer itself; it defines what Store and Admin
  see.

### Future Phase Target
- Dr.1.4.

### Risks
- **Backend authority risk:** any direct mobile-to-panel coupling would bypass
  the event model.
- **Tenancy risk:** store visibility must remain scoped to that store's orders.
- **Scope creep risk:** building a new oversight surface instead of reusing the
  Store/Admin panels.

## Cross-Domain Lifecycle Map

The domains connect across the main delivery lifecycle. Happy path:

Driver Account / Onboarding / Documents / Vehicle / Training → Driver Compliance
→ Availability / Online State → Delivery Offers → Driver Assignment → Active
Delivery → Store Pickup → Store Handoff → Navigation → Customer Dropoff → Age /
ID Verification → Proof of Delivery → Delivery Completed.

Failed restricted path:

Customer Dropoff → Age / ID Verification Failed or Customer Unavailable → Failed
Delivery → Return to Store → Store Return Confirmation → Audit / Compliance
Timeline.

Throughout both paths, the Audit / Compliance Timeline records each event, the
Safety Toolkit and Support Center can be invoked at any step, Notifications
signal state changes, and the Admin / Store Visibility Bridge exposes
backend-emitted events to the Store and Admin panels. Eligibility
(Driver Compliance) and Geofencing / Legal Zones gate entry to and progression
through the operational steps.

## Backend Authority Summary

The backend is authoritative for, at minimum:

- driver identity,
- eligibility,
- online permission,
- delivery offer eligibility,
- assignment state,
- order state,
- pickup authorization,
- store handoff validation,
- verification result acceptance,
- proof requirements,
- completion permission,
- failed delivery acceptance,
- return requirement,
- inventory implications,
- audit events.

No mobile surface may assert any of these; the app requests, the backend
decides and records.

## Mobile Responsibility Summary

The Driver App is responsible for:

- displaying state,
- collecting driver inputs,
- initiating actions,
- capturing confirmations,
- showing instructions,
- handling device permissions,
- submitting the verification result,
- submitting proof,
- submitting the failure reason,
- submitting the return step,
- showing support/safety actions,
- maintaining local reliability/retry behavior.

Each of these is an action or presentation responsibility; none constitutes
ownership of a business decision.

## Store/Admin Visibility Summary

- **Store Panel** gains visibility into the assigned driver, pickup,
  out-for-delivery, failed delivery, return required, and returned-to-store
  states for its own orders.
- **Admin Panel** gains visibility into driver compliance, driver status, the
  delivery audit timeline, verification failures, safety incidents, and support
  escalations.
- **Driver App actions must be visible through backend events, not direct
  mobile-to-panel state.** Oversight consumes the backend's authoritative event
  stream; it never reads mobile state directly.

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

Any work that would cross one of these boundaries requires a separate,
explicitly approved future phase with its own contract, consistent with
`docs/dr.1.0-driver-app-contract-lock.md` and `docs/f2.27-contract-lock.md`.
