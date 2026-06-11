# Dr.1.0 Driver User Flow Map

## Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.E — Driver User Flow Map
- **Status:** Draft for Dr.1.0 documentation
- **Scope:** documentation only
- **Implementation:** none

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/dr.1.0-driver-screen-inventory.md`,
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them. Screen
references use the inventory in `docs/dr.1.0-driver-screen-inventory.md`
(Dr.1.0.D).

## Purpose

This document maps the major end-to-end user flows for the NubeRush Driver App —
the operational sequences a driver moves through across a full driver operations
platform, not a small assigned-orders viewer.

The flow map rests on six fixed positions:

- **Mobile is the operational surface.** Flows are executed on the device:
  onboarding, availability, offers, pickup, handoff, dropoff, verification,
  proof, completion, failure, and return.
- **Backend is the authority.** Flow transitions are validated and recorded by
  the backend; the app requests transitions and reflects authorized state.
- **Store and Admin panels are the visibility and oversight layer.** Flow
  actions surface to them through backend events, not direct mobile state.
- **Driver access must be order-scoped, not store-wide.** No flow exposes
  store-wide inventory, orders, or administration.
- **Restricted-product compliance flows are core, not optional.** 21+
  verification, restricted handling, proof, failure, and return flows are
  first-class.
- **This document describes flows only.** It does not create app code, backend
  code, migrations, or UI.

## Flow Architecture Principles

- **Backend-authorized flow transitions.** Each state-changing step is validated
  and recorded by the backend.
- **Order-scoped driver visibility.** Flows operate only on offered/assigned
  orders.
- **Compliance-first restricted delivery.** Restricted handling and 21+
  verification are first-class flow steps.
- **No unattended restricted delivery.** Dropoff flows forbid leave-at-door for
  restricted products.
- **No raw ID image storage in MVP.** Verification flows capture redacted
  metadata only.
- **Return-to-store accountability.** Failed restricted deliveries route through
  return flows the driver cannot self-close.
- **Store handoff accountability.** Pickup and return require store-side
  confirmation steps.
- **Audit-first delivery lifecycle.** Flow steps emit compliance-grade audit
  events.
- **Mobile as action surface, not business-rule owner.** A flow step submits
  driver intent; it does not own a business decision.
- **Permission-aware flow recovery.** Flows degrade gracefully and recover when
  device permissions are missing.
- **Offline/retry-aware flow design.** Flows handle offline and retry without
  double-applying actions.
- **Safety/support escalation as first-class paths.** Safety and support are
  reachable from active flows, not buried.
- **Failed delivery is not an edge case.** Failure and return are designed as
  primary flows, not afterthoughts.
- **Future flows reserved without implementation.** Reserved flows are
  documented as future, not built now.

## Flow Summary Table

| # | Flow | Primary actor | Trigger | Primary screens involved | Backend authority | Compliance sensitivity | Final state | Phase target | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Driver onboarding flow | Driver | Invitation/signup | Signup/Invitation, Activation Checklist, Profile Setup, Phone/Email Verification, Policy Acknowledgment, Approval Pending | Owns completion + approval | High | Approved or action-required | Dr.1.2 | Onboarding ≠ online eligibility |
| 2 | Document approval flow | Driver, Admin | Document upload | Document Center, Upload Document, Document Status, Rejected Document Detail | Owns approval/expiry | High | Approved / rejected / expired | Dr.1.2 | No local approval |
| 3 | Vehicle approval flow | Driver, Admin | Add vehicle | Vehicle Profile, Add Vehicle, Vehicle Documents | Owns vehicle approval | Medium | Approved / rejected | Dr.1.2 | No ride-class logic |
| 4 | Training / policy acknowledgment flow | Driver | Open training | Compliance Training Home, Training Lesson, Policy Acknowledgment | Records completion/acks | High | Training + acks complete | Dr.1.2 | Quiz/cert future |
| 5 | Go online flow | Driver | Tap Go Online | Home / Driver Map, Go Online Check, App Permissions, Online Waiting State | Decides can_go_online | High | Online or blocked | Dr.1.3 | Backend gate |
| 6 | Delivery offer accept flow | Driver | Offer received | Delivery Offer, Delivery Offer Detail, Active Delivery Overview | Validates eligibility/assignment | High | Assigned | Dr.1.3 | Address after accept |
| 7 | Delivery offer decline flow | Driver | Offer received | Delivery Offer, Decline Reason, Online Waiting State | Records decline | Medium | Back to waiting | Dr.1.3 | No penalty logic in Dr.1.0 |
| 8 | Store pickup flow | Driver, Store employee | Assigned + at store | Navigate to Store, Arrived at Store, Store Pickup Instructions, Pickup Checklist, Confirm Pickup | Authorizes pickup | High | Pickup confirmed | Dr.1.3 | Needs handoff |
| 9 | Store order not ready flow | Driver, Store employee | Order not ready | Store Pickup Instructions, Pickup Issue, Online Waiting/Active | Records store issue | High | Waiting / escalated | Dr.1.3 | Wait or escalate |
| 10 | Store handoff PIN flow | Driver, Store employee | At pickup | Store Handoff PIN, Pickup Checklist | Validates handoff | Critical | Handoff confirmed/blocked | Dr.1.3 | No pickup if invalid |
| 11 | Navigation to customer flow | Driver | Pickup confirmed | Navigate to Customer, Active Delivery Overview | Releases address | High | En route to customer | Dr.1.3 | Zone warnings future |
| 12 | Customer contact flow | Driver, Customer | Contact needed | Contact Customer, Active Delivery Overview | Owns masking | Medium | Contact attempted | Dr.1.3 | No personal phone |
| 13 | 21+ ID verification success flow | Driver, Customer | Arrived (restricted) | Arrived at Customer, Restricted Product Warning, Age / ID Verification, Proof of Delivery | Accepts verification result | Critical | Verification passed | Dr.1.3 | Manual checklist MVP |
| 14 | 21+ ID verification failure flow | Driver, Customer | Verification fails | Age / ID Verification, ID Verification Failed, Failed Delivery Reason, Return Required | Blocks completion | Critical | Failed → return | Dr.1.3 | No raw ID images |
| 15 | Proof of delivery flow | Driver | Verification passed | Proof of Delivery, Complete Delivery | Validates proof | Critical | Proof recorded | Dr.1.3 | No proof, no delivered |
| 16 | Complete delivery flow | Driver | Proof captured | Complete Delivery, Delivery Completed Summary | Authorizes completion | Critical | Delivered | Dr.1.3 | Earnings visibility only |
| 17 | Customer unavailable flow | Driver, Customer | No response | Arrived at Customer, Wait Timer, Contact Customer, Failed Delivery Reason | Records unavailability | High | Failed → return (restricted) | Dr.1.3 | Wait + escalate |
| 18 | Failed delivery flow | Driver | Failure reason | Failed Delivery Reason, Return Required | Accepts failure; decides return | Critical | Failed | Dr.1.3 | No mobile inventory call |
| 19 | Return-to-store flow | Driver, Store employee | Return required | Return Required, Navigate Back to Store, Store Return Confirmation | Owns return requirement | Critical | Return started | Dr.1.3 | Cannot self-close |
| 20 | Store return confirmation flow | Driver, Store employee | At store (return) | Store Return Confirmation, Return Completed | Validates return | Critical | Returned to store | Dr.1.3 | Inventory review backend |
| 21 | Safety emergency flow | Driver, Support/admin | Safety risk | Safety Toolkit, Emergency Help, Report Incident | Records safety issue | High | Safety event recorded | Dr.1.4 | Always reachable |
| 22 | Support case flow | Driver, Support/admin | Help needed | Support Center, Support Category, Support Case Detail | Owns case record | Medium | Case opened | Dr.1.4 | Chat/call future |
| 23 | Offline / network recovery flow | Driver | Network loss | Any active screen, App Diagnostics | Rejects duplicate effects | High | Reconciled | Dr.1.2 | Idempotent retries |
| 24 | Permission recovery flow | Driver | Permission denied | App Permissions, blocked screen | May block online/completion | High | Permission restored/blocked | Dr.1.2 | Recovery to settings |

## Flow Groups

The Driver App flows are organized into the following groups:

- **Onboarding / Activation** — driver onboarding, document approval, vehicle
  approval, training/policy acknowledgment.
- **Eligibility / Online State** — go online (eligibility + permission health).
- **Offers / Assignment** — delivery offer accept and decline.
- **Store Pickup / Handoff** — store pickup, store order not ready, store handoff
  PIN.
- **Customer Dropoff / Verification / Proof** — navigation to customer, customer
  contact, 21+ verification success/failure, proof of delivery, complete
  delivery.
- **Failed Delivery / Return to Store** — customer unavailable, failed delivery,
  return-to-store, store return confirmation.
- **Safety / Support** — safety emergency, support case.
- **Reliability / Recovery** — offline/network recovery, permission recovery.

## Full Flow Specifications

Each flow below uses a consistent structure: Actor, Preconditions, Trigger, Main
Path, Alternative Paths, Failure Paths, Backend Decisions, Audit Events, Final
State, Screens Involved, Compliance Notes, and Future Notes. Every step that
changes state submits driver intent for backend authorization; the app never
owns a business decision.

## 1. Driver onboarding flow

### Actor
Driver (primary); Admin (approval); backend system.

### Preconditions
- A valid session exists (the driver has authenticated).
- The driver was provisioned/invited.

### Trigger
The driver begins onboarding from an invitation or signup path.

### Main Path
1. Driver starts onboarding from the invitation/signup entry.
2. Driver completes Profile Setup (legal name, phone, email, DOB, photo,
   operating city/zone).
3. Driver completes phone verification.
4. Driver completes email verification.
5. Driver completes the document checklist (see Document approval flow).
6. Driver completes vehicle setup (see Vehicle approval flow).
7. Driver completes the training checklist and policy acknowledgment.
8. Driver reaches Approval Pending and awaits backend/admin approval.
9. Backend approves; the driver becomes eligible to attempt going online.

### Alternative Paths
- Driver completes steps out of order where prerequisites allow.
- Driver resumes onboarding across sessions from the Activation Checklist.

### Failure Paths
- A step is rejected (e.g., document/vehicle) → rejected/action-required path
  with reason and resubmission.
- Approval is denied → action-required routes; the driver cannot proceed.

### Backend Decisions
- Owns per-step completion truth and the final approval decision.
- **Onboarding completion does not equal online eligibility unless the backend
  confirms** eligibility (Go online flow).

### Audit Events
- `driver_onboarding_started`, `driver_profile_submitted`, and the document/
  vehicle/training/policy events from their flows.

### Final State
- Approved (eligible to attempt online) or action-required/rejected.

### Screens Involved
- Driver Signup / Invitation, Activation Checklist, Profile Setup, Phone
  Verification, Email Verification, Document Center, Vehicle Profile, Compliance
  Training Home, Policy Acknowledgment, Approval Pending.

### Compliance Notes
- Restricted-product and 21+ policy acknowledgments are required; DOB feeds 21+
  eligibility. Verification artifacts are handled minimally.

### Future Notes
- Graded certification (future).

## 2. Document approval flow

### Actor
Driver (primary); Admin (review); backend system.

### Preconditions
- The driver account exists and onboarding is in progress or active.

### Trigger
The driver uploads or replaces a required document.

### Main Path
1. Driver opens the Document Center and selects a document type.
2. Driver captures/uploads via the camera/photo path (Upload Document).
3. Document enters pending review.
4. Backend/admin reviews and sets approved, rejected, expired, or expiring-soon.
5. Approved documents satisfy their requirement.

### Alternative Paths
- Driver replaces an expiring-soon document proactively.

### Failure Paths
- Rejected → Rejected Document Detail shows the reason; driver resubmits.
- Expired required document → operation is blocked until replaced.

### Backend Decisions
- Owns approval/rejection and expiry evaluation; **no local approval.**
- **An expired required document blocks going online.**

### Audit Events
- `driver_document_uploaded`, `driver_document_approved`,
  `driver_document_rejected`.

### Final State
- Approved, rejected, or expired per document.

### Screens Involved
- Document Center, Upload Document, Document Status, Rejected Document Detail.

### Compliance Notes
- Sensitive documents follow the secure handling policy; document review remains
  backend/admin-controlled.

### Future Notes
- Selfie verification (future).

## 3. Vehicle approval flow

### Actor
Driver (primary); Admin (review); backend system.

### Preconditions
- The driver account exists.

### Trigger
The driver adds a vehicle.

### Main Path
1. Driver opens Add Vehicle and enters make, model, year, color, plate.
2. Driver uploads registration (Vehicle Documents).
3. Driver uploads insurance.
4. Vehicle enters pending review.
5. Backend/admin sets approved, rejected, or expired.
6. Driver selects the active vehicle (single active vehicle).

### Alternative Paths
- Driver replaces an expiring registration/insurance document.

### Failure Paths
- Rejected/expired vehicle or document → blocked until resolved.

### Backend Decisions
- Owns vehicle approval and document expiry.
- **Vehicle approval is required for online eligibility.**

### Audit Events
- `vehicle_submitted`, `vehicle_approved`, `vehicle_rejected`.

### Final State
- Approved (usable) or rejected.

### Screens Involved
- Vehicle Profile, Add Vehicle, Vehicle Documents.

### Compliance Notes
- **No passenger-capacity or ride-class path** exists; this is delivery-only.

### Future Notes
- Vehicle photo (future).

## 4. Training / policy acknowledgment flow

### Actor
Driver (primary); backend system.

### Preconditions
- The driver account exists and onboarding is in progress or active.

### Trigger
The driver opens the training home.

### Main Path
1. Driver opens Compliance Training Home and sees required modules.
2. Driver completes each Training Lesson: restricted-product delivery policy,
   21+ verification, valid ID checklist, failed ID handling, return-to-store
   policy, safety, and incident reporting.
3. Driver completes Policy Acknowledgment.
4. Backend records training completion and acknowledgments.

### Alternative Paths
- Driver revisits a completed lesson.

### Failure Paths
- Incomplete training → restricted-delivery eligibility remains blocked.

### Backend Decisions
- Records training completion and policy acknowledgments as eligibility signals.

### Audit Events
- `training_completed`, `policy_acknowledged`.

### Final State
- Training and required acknowledgments complete.

### Screens Involved
- Compliance Training Home, Training Lesson, Policy Acknowledgment.

### Compliance Notes
- Restricted-product, 21+, and return-to-store policies are required before
  restricted deliveries.

### Future Notes
- Quiz / certification (future).

## 5. Go online flow

### Actor
Driver (primary); backend system.

### Preconditions
- The driver is approved and onboarding is complete.

### Trigger
The driver taps Go Online.

### Main Path
1. Driver taps Go Online (Home / Driver Map → Go Online Check).
2. Backend checks documents, vehicle, training, policy, suspension, and driver
   status.
3. App checks location, camera, notification, and network health.
4. Backend returns `can_go_online` or a list of blocked reasons.
5. If eligible, the driver enters the Online Waiting State.

### Alternative Paths
- Driver resolves a failed requirement (open documents/permissions) and retries.

### Failure Paths
- Backend denies → blocked reasons are listed; **no online mode if the backend
  denies.**
- Missing required permission → permission recovery (Flow 24).

### Backend Decisions
- **Decides `can_go_online`** based on eligibility and reported device health.

### Audit Events
- `driver_online` on success; `driver_offline` when going offline.

### Final State
- Online (waiting) or blocked.

### Screens Involved
- Home / Driver Map, Go Online Check, App Permissions, Online Waiting State.

### Compliance Notes
- Eligibility gating ensures only compliant, trained, documented drivers operate.

### Future Notes
- Scheduled availability (future).

## 6. Delivery offer accept flow

### Actor
Driver (primary); backend system.

### Preconditions
- The driver is online and waiting.

### Trigger
An offer is received.

### Main Path
1. Offer is received with an offer timer.
2. Driver reviews store info, approximate dropoff zone, estimated distance/time/
   earnings, the restricted flag, and the ID-required flag (Delivery Offer /
   Delivery Offer Detail).
3. Driver taps Accept.
4. Backend validates eligibility and assignment availability.
5. On success, the assignment is created and the **exact customer address/details
   become available**.

### Alternative Paths
- Driver opens Delivery Offer Detail before accepting (privacy boundary
  preserved).

### Failure Paths
- Offer timer expires → offer withdrawn.
- Backend rejects (no longer eligible/available) → returns to waiting.

### Backend Decisions
- Validates eligibility and assignment availability; owns the timer/expiry and
  releases customer details only after acceptance.

### Audit Events
- `delivery_offered`, `delivery_accepted`, `driver_assigned`.

### Final State
- Assigned (proceeding to pickup).

### Screens Involved
- Delivery Offer, Delivery Offer Detail, Active Delivery Overview.

### Compliance Notes
- Pre-accept privacy boundary: exact customer address/contact withheld until
  acceptance; restricted/ID-required flags shown pre-accept.

### Future Notes
- Batch offers (future).

## 7. Delivery offer decline flow

### Actor
Driver (primary); backend system.

### Preconditions
- The driver is online and an offer is presented.

### Trigger
An offer is received and the driver chooses to decline.

### Main Path
1. Offer is received (Delivery Offer).
2. Driver taps Decline.
3. Driver provides a decline reason (Decline Reason) — optional or required per
   policy.
4. Backend records the decline.
5. Driver returns to the Online Waiting State.

### Alternative Paths
- Offer expires before the driver decides (treated as expiry, not decline).

### Failure Paths
- Decline submission fails (offline) → retry queue; reconciled when online.

### Backend Decisions
- Records the decline and reason; may trigger reassignment to another driver.

### Audit Events
- `delivery_declined`.

### Final State
- Back to waiting.

### Screens Involved
- Delivery Offer, Decline Reason, Online Waiting State.

### Compliance Notes
- **No penalty logic is implemented in Dr.1.0**; performance implications are
  future.

### Future Notes
- Acceptance-rate performance handling (future).

## 8. Store pickup flow

### Actor
Driver (primary); Store employee; backend system.

### Preconditions
- The driver has an accepted assignment.

### Trigger
The driver navigates to and arrives at the pickup store.

### Main Path
1. Driver navigates to the store (Navigate to Store).
2. Driver marks Arrived at Store.
3. Driver reviews Store Pickup Instructions (order number, bag count, item
   count, restricted warning, store instructions).
4. Driver completes the store handoff (see Store handoff PIN flow).
5. Driver completes the Pickup Checklist (correct store, correct order, bag count
   matches, sealed/damage check, restricted-product acknowledgment).
6. Driver confirms pickup (Confirm Pickup); backend authorizes the transition.

### Alternative Paths
- Driver reports a pickup issue (see Store order not ready flow).

### Failure Paths
- Order/store mismatch → Pickup Issue.
- Handoff invalid → pickup blocked (Store handoff PIN flow).

### Backend Decisions
- Authorizes pickup confirmation; **pickup cannot complete without an assignment
  and backend authorization** (plus a valid handoff and compliance).

### Audit Events
- `en_route_to_store`, `arrived_at_store`, `pickup_confirmed`,
  `out_for_delivery`.

### Final State
- Pickup confirmed; out for delivery.

### Screens Involved
- Navigate to Store, Arrived at Store, Store Pickup Instructions, Pickup
  Checklist, Confirm Pickup.

### Compliance Notes
- Restricted-product acknowledgment is part of the checklist; pickup is gated by
  handoff accountability.

### Future Notes
- Geofence arrival validation (future); scan-based item verification (future).

## 9. Store order not ready flow

### Actor
Driver (primary); Store employee; Support/admin; backend system.

### Preconditions
- The driver has arrived at the store with an accepted assignment.

### Trigger
The order is not ready at the store.

### Main Path
1. Driver arrives and finds the order is not ready.
2. Driver enters a wait state and/or reports the issue (Pickup Issue).
3. Driver contacts the store/support if needed.
4. Backend records the waiting/store issue.
5. Driver continues waiting, reports the issue, or support escalates.

### Alternative Paths
- Order becomes ready → resume Store pickup flow.

### Failure Paths
- Prolonged delay/store closed → support escalation or reassignment.

### Backend Decisions
- Records the store issue/wait; determines reassignment/escalation.

### Audit Events
- `store_issue_reported`.

### Final State
- Waiting, escalated, or resumed pickup.

### Screens Involved
- Store Pickup Instructions, Pickup Issue, Online Waiting State / Active Delivery
  Overview.

### Compliance Notes
- Store-side delays are recorded for operational audit.

### Future Notes
- Store-ready push notification (future).

## 10. Store handoff PIN flow

### Actor
Driver (primary); Store employee; backend system.

### Preconditions
- The driver is at the store for an accepted assignment.

### Trigger
The store employee provides a release PIN.

### Main Path
1. Store employee provides the PIN.
2. Driver enters the PIN (Store Handoff PIN).
3. Backend validates the handoff.
4. On success, the handoff is recorded and pickup may proceed.

### Alternative Paths
- Store uses a manager override (future) or QR/barcode handoff (future).

### Failure Paths
- Invalid PIN → **pickup blocked**; retry or escalate via Pickup Issue.

### Backend Decisions
- **Validates the handoff**; the store is accountable for release; pickup is
  blocked if the PIN is invalid.

### Audit Events
- `store_handoff_started`, `store_handoff_confirmed`.

### Final State
- Handoff confirmed or blocked.

### Screens Involved
- Store Handoff PIN, Pickup Checklist.

### Compliance Notes
- Accountable store release of restricted product; the driver cannot
  self-authorize pickup.

### Future Notes
- QR / barcode handoff (future); manager override (future).

## 11. Navigation to customer flow

### Actor
Driver (primary); backend system.

### Preconditions
- Pickup is confirmed.

### Trigger
The driver proceeds out for delivery.

### Main Path
1. Pickup is confirmed; the **exact customer address becomes available**.
2. Driver launches external navigation to Apple Maps, Google Maps, or Waze.
3. Driver views ETA/distance.
4. The app remains the active delivery surface during transit.

### Alternative Paths
- Driver changes the navigation app preference.

### Failure Paths
- Missing location permission → permission recovery (Flow 24).

### Backend Decisions
- Releases the customer address post-pickup; provides any zone constraints.

### Audit Events
- `out_for_delivery` (recorded at the pickup→delivery transition).

### Final State
- En route to the customer.

### Screens Involved
- Navigate to Customer, Active Delivery Overview.

### Compliance Notes
- Customer address is only available after acceptance and pickup; legal/restricted
  zone warnings are a future enhancement.

### Future Notes
- Legal/restricted zone warnings (future); internal turn-by-turn (future);
  CarPlay / Android Auto (future).

## 12. Customer contact flow

### Actor
Driver (primary); Customer; Support/admin; backend system.

### Preconditions
- The driver has an active delivery requiring customer contact.

### Trigger
The driver needs to reach the customer.

### Main Path
1. Driver opens Contact Customer.
2. Driver places a masked call or sends a message, or uses a quick message.
3. The customer responds, or the driver retries.

### Alternative Paths
- Driver uses a canned quick message rather than a free-form one.

### Failure Paths
- No response → Wait Timer / support escalation (Customer unavailable flow).

### Backend Decisions
- Owns number masking and the allowed message set.

### Audit Events
- `customer_contacted`.

### Final State
- Contact attempted (responded or escalated).

### Screens Involved
- Contact Customer, Active Delivery Overview.

### Compliance Notes
- **No personal phone exposure** on either side; messaging is compliance-safe.

### Future Notes
- Contact event audit detail (future); message history (future).

## 13. 21+ ID verification success flow

### Actor
Driver (primary); Customer; backend system.

### Preconditions
- The driver has arrived at the customer for a restricted order.

### Trigger
The driver begins verification at the door.

### Main Path
1. Driver marks Arrived at Customer.
2. Driver reviews the Restricted Product Warning (no unattended delivery,
   customer present, valid ID, 21+).
3. Driver confirms the customer is present.
4. Driver confirms a valid government ID.
5. Driver confirms the ID is not expired.
6. Driver confirms the customer is 21+.
7. Driver confirms the ID appears to match the person.
8. Driver submits the manual verification result (Age / ID Verification).
9. Backend accepts the verification result.
10. Flow proceeds to Proof of delivery.

### Alternative Paths
- None for the success path; any check failing routes to Flow 14.

### Failure Paths
- Any check fails → 21+ ID verification failure flow (Flow 14).

### Backend Decisions
- **Accepts the verification result**; completion is gated on it.

### Audit Events
- `verification_started`, `age_verification_passed`.

### Final State
- Verification passed; ready for proof.

### Screens Involved
- Arrived at Customer, Restricted Product Warning, Age / ID Verification, Proof
  of Delivery.

### Compliance Notes
- Manual checklist is the MVP mechanism; **no raw ID image storage** — only
  redacted metadata is submitted.

### Future Notes
- ID scan / OCR / barcode / liveness / vendor verification (future, legal-review
  dependent).

## 14. 21+ ID verification failure flow

### Actor
Driver (primary); Customer; backend system.

### Preconditions
- The driver is performing verification for a restricted order.

### Trigger
A required verification check cannot be satisfied.

### Main Path
1. The driver encounters a failure condition: no ID, expired ID, underage, ID
   mismatch, wrong recipient, customer refused, suspected fake ID, or unsafe
   situation.
2. Driver selects the failure reason (ID Verification Failed).
3. Backend blocks completion.
4. The failed delivery / return-to-store path is triggered.

### Alternative Paths
- Unsafe situation → safety emergency (Flow 21) in parallel.

### Failure Paths
- Submission fails (offline) → retry queue; reconciled when online.

### Backend Decisions
- **Blocks completion**; records the failure; requires return for restricted
  product.

### Audit Events
- `verification_started`, `age_verification_failed`.

### Final State
- Failed verification → failed delivery → return required.

### Screens Involved
- Age / ID Verification, ID Verification Failed, Failed Delivery Reason, Return
  Required.

### Compliance Notes
- **No unattended delivery**; **no raw ID image storage**. Underage/invalid-ID
  outcomes hard-block delivery and require return.

### Future Notes
- None.

## 15. Proof of delivery flow

### Actor
Driver (primary); backend system.

### Preconditions
- For restricted orders, verification has passed.

### Trigger
The driver proceeds to record proof.

### Main Path
1. For a restricted order, a verification pass is required before proof.
2. Driver records the attestation and timestamp (Proof of Delivery).
3. Backend validates the proof requirements and binds the verification pass to
   the proof.
4. Flow proceeds to Complete delivery.

### Alternative Paths
- Additional proof elements captured where available (future: GPS, customer
  PIN, signature/photo).

### Failure Paths
- Proof cannot be captured/validated → completion blocked; may route to failure.

### Backend Decisions
- Validates proof requirements; **no proof, no delivered.**

### Audit Events
- `proof_of_delivery_recorded`.

### Final State
- Proof recorded.

### Screens Involved
- Proof of Delivery, Complete Delivery.

### Compliance Notes
- The verification result is attached to the proof for restricted orders.

### Future Notes
- Approximate GPS (future); customer PIN (future); signature/photo (future).

## 16. Complete delivery flow

### Actor
Driver (primary); backend system.

### Preconditions
- Proof is captured; for restricted orders, verification passed.

### Trigger
The driver submits completion.

### Main Path
1. Proof is captured.
2. For a restricted order, verification has passed.
3. Driver submits completion (Complete Delivery).
4. Backend authorizes completion.
5. The delivery is recorded to history (Delivery Completed Summary).

### Alternative Paths
- None.

### Failure Paths
- Backend rejects (missing proof/verification or proximity) → blocked; may route
  to failure.

### Backend Decisions
- **Authorizes completion**; requires proof and a verification pass for
  restricted orders; emits the completion event.

### Audit Events
- `delivery_completed`.

### Final State
- Delivered.

### Screens Involved
- Complete Delivery, Delivery Completed Summary.

### Compliance Notes
- **Estimated earnings visibility only — no payout, cashout, or payment
  movement.**

### Future Notes
- None.

## 17. Customer unavailable flow

### Actor
Driver (primary); Customer; Support/admin; backend system.

### Preconditions
- The driver has arrived at the customer.

### Trigger
The customer is not responding.

### Main Path
1. Driver marks Arrived at Customer.
2. Customer does not respond.
3. Driver starts the Wait Timer.
4. Driver makes contact attempts (Contact Customer).
5. Support escalation if still unreachable.
6. Backend records customer-unavailable when the policy wait elapses.
7. For restricted product, the failed delivery and return path is triggered.

### Alternative Paths
- Customer responds before the timer elapses → resume dropoff/verification.

### Failure Paths
- Timer elapses with no response → failed delivery (Flow 18).

### Backend Decisions
- Owns the wait policy; records unavailability; gates the failure transition.

### Audit Events
- `customer_contacted`, `customer_unavailable`.

### Final State
- Customer unavailable → failed delivery → return (restricted).

### Screens Involved
- Arrived at Customer, Wait Timer, Contact Customer, Failed Delivery Reason.

### Compliance Notes
- Restricted product cannot be left unattended; unavailability routes to return.

### Future Notes
- None.

## 18. Failed delivery flow

### Actor
Driver (primary); backend system.

### Preconditions
- A delivery cannot be completed.

### Trigger
The driver selects a failure reason.

### Main Path
1. Driver selects a failure reason (Failed Delivery Reason): unavailable, no ID,
   expired ID, underage, mismatch, refused, unsafe, wrong address, or
   app/vehicle/support issue.
2. Backend accepts the failed delivery.
3. For restricted product, return is required (Return Required).

### Alternative Paths
- Non-restricted future handling may differ.

### Failure Paths
- Submission fails (offline) → retry queue; reconciled when online.

### Backend Decisions
- Accepts the failed delivery and **decides whether return is required.**
- **No inventory-consumption decision is made in mobile.**

### Audit Events
- `delivery_failed`.

### Final State
- Failed (return required for restricted product).

### Screens Involved
- Failed Delivery Reason, Return Required.

### Compliance Notes
- Failed restricted deliveries require an accountable return; failure is a
  primary flow, not an edge case.

### Future Notes
- Differentiated non-restricted handling (future).

## 19. Return-to-store flow

### Actor
Driver (primary); Store employee; backend system.

### Preconditions
- A failed restricted delivery requires return.

### Trigger
Return is required.

### Main Path
1. Return Required is shown with the originating store.
2. Driver navigates back to the store (Navigate Back to Store).
3. Driver records the return reason (carried from the failure).
4. Driver views ETA/distance during transit.

### Alternative Paths
- Driver contacts support about the return.

### Failure Paths
- Missing location permission → permission recovery (Flow 24).

### Backend Decisions
- Owns the return requirement; **the driver cannot self-close a restricted
  return.**

### Audit Events
- `return_required`, `return_started`.

### Final State
- Return started (en route to store).

### Screens Involved
- Return Required, Navigate Back to Store, Store Return Confirmation.

### Compliance Notes
- Accountable handling of undeliverable restricted product.

### Future Notes
- None.

## 20. Store return confirmation flow

### Actor
Driver (primary); Store employee; backend system.

### Preconditions
- The driver has returned to the originating store with the product.

### Trigger
The driver arrives back at the store to hand off the return.

### Main Path
1. Driver arrives back at the store.
2. Store employee provides a PIN/confirmation (Store Return Confirmation).
3. Backend validates the return.
4. Inventory review is backend-controlled.
5. The return is confirmed and closed (Return Completed).

### Alternative Paths
- QR/barcode return (future).

### Failure Paths
- Invalid PIN/confirmation → retry or support escalation; return remains open.

### Backend Decisions
- **Validates the return**; inventory implications are backend-controlled; closes
  the return.

### Audit Events
- `returned_to_store`, `store_return_confirmed`.

### Final State
- Returned to store (failed restricted path closed).

### Screens Involved
- Store Return Confirmation, Return Completed.

### Compliance Notes
- Store-side confirmation makes the return accountable; the driver cannot
  self-confirm.

### Future Notes
- QR / barcode return (future).

## 21. Safety emergency flow

### Actor
Driver (primary); Support/admin; backend system; emergency services (external).

### Preconditions
- The driver is operating (any active flow), or at risk.

### Trigger
The driver perceives a safety risk.

### Main Path
1. Driver opens the Safety Toolkit or Emergency Help.
2. Driver chooses Call 911, or shares location/route with admin/support (future).
3. Driver reports an unsafe location, threat, accident, or vehicle issue (Report
   Incident).
4. Driver may Cancel for safety.
5. Backend records the safety issue and routes it to oversight.

### Alternative Paths
- A safety cancel of a restricted order still requires return.

### Failure Paths
- In-app calling fails → falls back to the system dialer.

### Backend Decisions
- Records the safety issue; ties a safety cancel to the delivery/return outcome.

### Audit Events
- `safety_issue_reported`.

### Final State
- Safety event recorded; oversight notified.

### Screens Involved
- Safety Toolkit, Emergency Help, Report Incident.

### Compliance Notes
- Safety is always reachable; a restricted-order safety cancel still routes
  product to return.

### Future Notes
- Active-route sharing with admin/support (future); long-stop / route-deviation
  detection (future).

## 22. Support case flow

### Actor
Driver (primary); Support/admin; backend system.

### Preconditions
- The driver needs help.

### Trigger
The driver opens support.

### Main Path
1. Driver opens the Support Center.
2. Driver selects a category (Support Category): pickup, store, customer, ID,
   safety, vehicle, app, earnings, or policy.
3. Active-delivery context is attached when relevant.
4. Driver creates a support ticket.
5. Driver views case status (Support Case Detail).

### Alternative Paths
- Driver opens an existing case from a notification.

### Failure Paths
- Submission fails (offline) → retry queue; reconciled when online.

### Backend Decisions
- Owns the support case record and routing.

### Audit Events
- `support_case_opened`; `app_issue_reported` for app-issue tickets.

### Final State
- Case opened.

### Screens Involved
- Support Center, Support Category, Support Case Detail.

### Compliance Notes
- ID-verification and unsafe-delivery topics are first-class support paths.

### Future Notes
- Messages and attachments (future); support chat/call (future).

## 23. Offline / network recovery flow

### Actor
Driver (primary); backend system.

### Preconditions
- The driver is performing actions that may occur during connectivity loss.

### Trigger
A network failure or offline state occurs.

### Main Path
1. The app detects network loss and preserves local state.
2. Idempotent actions are placed in a retry queue.
3. The driver sees a recovery/error state (and App Diagnostics if needed).
4. When connectivity returns, queued actions reconcile with the backend.
5. The backend rejects duplicate side effects.

### Alternative Paths
- Driver manually retries from the recovery state.

### Failure Paths
- Persistent failure → the action remains queued; the driver is informed and can
  escalate to support.

### Backend Decisions
- **Rejects duplicate side effects**; reconciles queued actions idempotently.

### Audit Events
- `offline_retry_queued`, `offline_retry_reconciled`.

### Final State
- Reconciled (no duplicate pickup/proof/completion/return events).

### Screens Involved
- Any active screen; App Diagnostics.

### Compliance Notes
- **No duplicate pickup/proof/completion/return events** — the audit timeline
  must not double-record critical events.

### Future Notes
- Advanced background sync (future).

## 24. Permission recovery flow

### Actor
Driver (primary); backend system.

### Preconditions
- A required device permission is denied or unhealthy.

### Trigger
Location, camera, or notification permission is denied or unhealthy.

### Main Path
1. The app detects the missing/unhealthy permission.
2. The app shows a blocked state with recovery instructions (App Permissions).
3. Driver opens device settings to change the permission.
4. Driver returns and retries the permission check.
5. Operation resumes if the permission is restored.

### Alternative Paths
- Driver grants a partial permission and is informed of remaining limits.

### Failure Paths
- Permission remains denied → the dependent operation stays blocked.

### Backend Decisions
- **May block online or completion if a required permission is unavailable**
  (e.g., location for proximity).

### Audit Events
- `permission_recovery_started`.

### Final State
- Permission restored (operation resumes) or blocked.

### Screens Involved
- App Permissions; the blocked screen requiring the permission.

### Compliance Notes
- Location is required for proximity-gated steps; without it, gated actions are
  blocked.

### Future Notes
- Background location (future).

## Flow Dependency Map

Major dependencies across the flows:

- **Onboarding flows depend on auth/session.** A validated session precedes
  onboarding.
- **Document/vehicle/training flows depend on the driver account.** They feed
  eligibility but do not grant it.
- **Go online depends on backend eligibility and permission health.** Both the
  backend gate and device health must pass.
- **Delivery offer flows depend on online state and backend assignment
  eligibility.** Offers reach only eligible, online drivers.
- **Store pickup/handoff depends on an accepted assignment.** No pickup without
  an assignment and a valid handoff.
- **Customer dropoff depends on pickup confirmation.** The customer address is
  released only post-pickup.
- **Verification/proof depends on restricted-product requirements.** Restricted
  orders require 21+ verification before proof.
- **Completion depends on verification/proof backend acceptance.** The backend
  authorizes the final transition.
- **Failed restricted delivery depends on return-to-store.** Return is required
  and driver-uncloseable.
- **Store return confirmation depends on backend/store validation.** The store
  confirms; the backend closes.
- **Safety/support can be accessed contextually from active delivery.** They are
  reachable at any step.
- **Offline/network recovery applies across idempotent driver actions.** It spans
  every state-changing step.
- **Permission recovery gates screens that require location/camera/
  notifications.** Missing permissions block dependent flows.

## Backend Authority Summary

Across all flows, the backend is authoritative for, at minimum:

- session validity,
- driver identity,
- onboarding completion,
- document status,
- vehicle status,
- training status,
- policy acknowledgment,
- eligibility,
- online permission,
- offer eligibility,
- assignment state,
- active delivery state,
- pickup authorization,
- store handoff validation,
- customer address release after acceptance/pickup,
- verification result acceptance,
- proof requirements,
- completion permission,
- failed delivery acceptance,
- return requirement,
- store return validation,
- inventory implications,
- support case persistence,
- safety incident persistence,
- audit events,
- idempotency / duplicate side-effect rejection.

No flow asserts any of these; flows request and display, the backend decides and
records.

## Audit Event Summary

The following audit events are expected across the flows (names are
architectural, to be finalized in the backend phase):

- `driver_onboarding_started`
- `driver_profile_submitted`
- `driver_document_uploaded`
- `driver_document_approved`
- `driver_document_rejected`
- `vehicle_submitted`
- `vehicle_approved`
- `vehicle_rejected`
- `training_completed`
- `policy_acknowledged`
- `driver_online`
- `driver_offline`
- `delivery_offered`
- `delivery_accepted`
- `delivery_declined`
- `driver_assigned`
- `en_route_to_store`
- `arrived_at_store`
- `store_issue_reported`
- `store_handoff_started`
- `store_handoff_confirmed`
- `pickup_confirmed`
- `out_for_delivery`
- `customer_contacted`
- `arrived_at_customer`
- `verification_started`
- `age_verification_passed`
- `age_verification_failed`
- `proof_of_delivery_recorded`
- `delivery_completed`
- `customer_unavailable`
- `delivery_failed`
- `return_required`
- `return_started`
- `returned_to_store`
- `store_return_confirmed`
- `safety_issue_reported`
- `support_case_opened`
- `app_issue_reported`
- `permission_recovery_started`
- `offline_retry_queued`
- `offline_retry_reconciled`

The audit timeline is backend-owned and contains **no raw ID data**.

## Compliance Flow Summary

The following flows are compliance-critical, with the reason each is sensitive:

- **Driver onboarding flow** — gates entry to restricted delivery; records 21+
  and policy acknowledgments.
- **Document approval flow** — required authorization documents; expired
  documents block operation.
- **Vehicle approval flow** — operating authorization; unapproved/uninsured
  vehicles are blocked.
- **Training / policy acknowledgment flow** — restricted-product and 21+ policy
  readiness.
- **Go online flow** — the eligibility gate; only compliant drivers operate.
- **Delivery offer accept flow** — pre-accept privacy boundary; restricted/ID
  flags.
- **Store pickup flow** — restricted-product acknowledgment; pickup gated by
  handoff.
- **Store handoff PIN flow** — accountable store release of restricted product.
- **21+ ID verification success flow** — the age gate; no raw ID images.
- **21+ ID verification failure flow** — blocks delivery; triggers return; no
  unattended delivery.
- **Proof of delivery flow** — no proof, no delivered; verification attached.
- **Complete delivery flow** — completion requires proof + verification for
  restricted orders.
- **Customer unavailable flow** — restricted product cannot be left unattended.
- **Failed delivery flow** — drives the return requirement; no mobile inventory
  decision.
- **Return-to-store flow** — accountable return; driver cannot self-close.
- **Store return confirmation flow** — store-confirmed, backend-closed return.
- **Safety emergency flow** — driver safety; restricted cancels still return
  product.
- **Offline / network recovery flow** — protects audit integrity from duplicate
  events.
- **Permission recovery flow** — required permissions gate compliant operation
  (e.g., proximity).

## Idempotency / Retry Summary

The following driver actions must be idempotent:

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

- **Mobile can retry safely** — the app may resend an action after a network
  failure or app restart.
- **The backend must reject duplicate side effects** — a retried action does not
  create a second pickup, proof, completion, return, case, or incident.
- **The audit timeline must not duplicate critical events incorrectly** — each
  logical event is recorded once.
- **Offline recovery depends on this** — the offline/network recovery flow relies
  on idempotency to reconcile queued actions safely.

## MVP vs Future Flow Boundary

**MVP / early required flows:**

- onboarding,
- document approval,
- vehicle approval,
- training / policy acknowledgment,
- go online,
- offer accept/decline,
- store pickup,
- store handoff PIN,
- navigation to customer,
- customer contact,
- manual 21+ ID verification success/failure,
- proof of delivery,
- complete delivery,
- customer unavailable,
- failed delivery,
- return-to-store,
- store return confirmation,
- safety emergency basics,
- support case basics,
- offline/network recovery basics,
- permission recovery basics.

**Future / reserved flows and capabilities:**

- advanced quiz/certification,
- ID scan/OCR/vendor verification,
- customer PIN proof,
- signature/photo proof,
- internal turn-by-turn,
- CarPlay/Android Auto,
- support chat/call center sophistication,
- advanced safety detection,
- route deviation detection,
- long stop detection,
- batch delivery,
- optimized routing,
- advanced rewards/performance workflows.

Reserved flows are documented so later phases inherit a designed slot; they are
not implemented now.

## Store/Admin Visibility Summary

The following flow events are what Store and Admin need later, surfaced through
the existing panels:

- approval pending / action required,
- driver online/offline,
- assigned driver,
- arrived at store,
- store issue,
- handoff confirmed,
- pickup confirmed,
- out for delivery,
- customer contacted,
- arrived at customer,
- verification failed,
- proof recorded,
- completed,
- failed delivery,
- return required,
- return started,
- returned to store,
- store return confirmed,
- safety issue,
- support case.

**Driver App flows must emit or submit actions through backend events. No flow
should directly mutate Store/Admin UI state.** Oversight consumes the backend's
authoritative event stream.

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
