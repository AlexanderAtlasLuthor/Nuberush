# Dr.1.0 Driver Compliance and ID Verification Architecture

## Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.G — Compliance / 21+ / ID Verification Architecture
- **Status:** Draft for Dr.1.0 documentation
- **Scope:** documentation only
- **Implementation:** none

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/dr.1.0-driver-screen-inventory.md`,
`docs/dr.1.0-driver-user-flows.md`,
`docs/dr.1.0-driver-backend-gap-map.md`,
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them. The
companion proof / failure / return architecture is Dr.1.0.H
(`docs/dr.1.0-driver-proof-failure-return.md`).

## Purpose

This document defines the compliance and ID verification architecture for
restricted-product delivery in the NubeRush Driver App. Restricted products
(smoke-shop and vape items) require lawful, age-verified, in-person delivery,
and that requirement shapes the verification design.

Stated clearly:

- **Restricted-product compliance is core, not optional.** 21+ verification,
  proof, and return-to-store are first-class.
- **Mobile is the operational surface.** The Driver App presents the warning,
  collects the manual checklist result, and submits it.
- **Backend is the authority.** The backend decides whether verification is
  required, whether a result is accepted, and whether completion may proceed.
- **Store/Admin panels are visibility and oversight layers.** They observe
  verification outcomes through backend events and redacted records.
- **Driver access must be order-scoped.** Verification operates only on the
  driver's assigned order.
- **This document does not create ID scanning, OCR, backend endpoints, schemas,
  migrations, or app code.** It is architecture documentation only.

Status names, failure reasons, and event names in this document are
**architectural candidates**, finalized in Dr.1.1.

## Compliance Architecture Principles

- **Compliance-first restricted delivery.** Restricted handling and 21+
  verification are first-class, not add-ons.
- **Backend-authorized verification.** The backend accepts or rejects the
  verification result; the app never self-authorizes completion.
- **Manual 21+ verification checklist for MVP.** The MVP verification mechanism
  is a driver-completed checklist.
- **No unattended restricted delivery.** Leave-at-door is forbidden for
  restricted orders.
- **No raw ID image storage in MVP.** The app does not capture or store raw
  identity-document images.
- **No full ID number storage in MVP.** Full identity-document numbers are not
  captured or stored.
- **Redacted metadata by default.** Only redacted, non-sensitive metadata about
  the check is persisted.
- **Failed verification blocks completion.** A failed 21+ check stops the
  delivery from completing.
- **Failed restricted delivery requires return-to-store.** Undeliverable
  restricted product routes to an accountable return.
- **Driver cannot self-close restricted returns.** The store confirms and the
  backend closes the return.
- **Audit-first verification lifecycle.** Each verification step emits a
  compliance-grade audit event.
- **Legal review before scan/OCR/vendor verification.** Stronger methods are
  gated on legal/compliance approval.
- **Mobile as action surface, not compliance authority.** The app submits
  intent; it does not own the compliance decision.
- **Store/Admin visibility through backend events.** Oversight consumes
  backend-emitted events and redacted records, not direct mobile state.
- **Future verification methods reserved without implementation.** Scan, OCR,
  liveness, and vendor verification are documented as future, not built.

## MVP Compliance Decision

**The MVP uses a manual 21+ verification checklist only.** The driver visually
inspects the customer's government-issued ID and confirms a structured checklist;
the backend records and authorizes the result.

For the MVP, explicitly:

- **No ID scan in MVP.**
- **No OCR in MVP.**
- **No barcode scan in MVP.**
- **No liveness check in MVP.**
- **No third-party verification vendor in MVP.**
- **No raw ID image storage in MVP.**
- **No full ID number storage in MVP.**
- **No automatic compliance override** — the system never auto-approves,
  auto-holds, or auto-overrides human/backend compliance authority.
- **Backend-authorized verification result only** — the result is accepted or
  rejected server-side.
- **Redacted metadata only** — the persisted record holds non-sensitive metadata
  (that a check occurred, its outcome, reason, method, timestamp, and
  driver/order/store association), never raw ID data.

This decision preserves the existing human-gated compliance posture from
F2.27: automated and vendor methods are deferred and legally gated.

## Restricted Product Delivery Rules

Restricted-product deliveries follow these rules:

- The **customer must be physically present.**
- **Unattended delivery is not allowed.**
- **Leave-at-door is blocked.**
- A **valid government ID is required.**
- The **recipient must be 21+.**
- The **ID must not be expired.**
- The **ID must appear to match the person.**
- A **wrong recipient blocks delivery.**
- A **customer refusal blocks delivery.**
- A **suspected fake ID blocks delivery.**
- An **unsafe situation blocks delivery and escalates safety/support.**
- A **failed verification triggers failed delivery.**
- A **failed restricted delivery requires return-to-store.**
- The **backend decides whether completion is allowed.**

These rules are enforced server-side; the app presents them and collects the
driver's confirmations, but cannot override them.

## Valid ID Checklist

The manual verification checklist the driver completes for a restricted delivery:

- **Government-issued ID presented.**
- **ID is readable.**
- **ID is not expired.**
- **Date of birth confirms 21+.**
- **Photo appears to match the person.**
- **Name / order-recipient policy is satisfied.**
- **ID appears physically valid.**
- **Customer is physically present.**
- **Customer accepts verification.**
- **Driver attests checklist completion.**

Boundaries for the checklist:

- **The driver does not store a raw ID image.**
- **The driver does not store a full ID number.**
- **Mobile submits the checklist result and failure reason** (when failed).
- **The backend accepts or rejects the verification result.**

## Verification Status Model

The following are **candidate verification statuses** for a restricted order's
verification, finalized in Dr.1.1. Statuses are backend-owned; the app reflects
them.

### not_required

- **Meaning:** the order is not a restricted order; no 21+ verification is
  needed.
- **Who/what can set it:** backend (from order/product compliance attributes).
- **Allowed next states:** terminal for verification (proceeds to normal
  completion).
- **Backend authority notes:** the backend determines whether verification is
  required; the app does not decide this.
- **Audit implication:** none specific to verification.

### required_pending

- **Meaning:** verification is required but has not started.
- **Who/what can set it:** backend (when the restricted order is assigned).
- **Allowed next states:** `in_progress`, `blocked`.
- **Backend authority notes:** completion is blocked while pending.
- **Audit implication:** `restricted_delivery_warning_shown` when the warning is
  presented.

### in_progress

- **Meaning:** the driver has started the manual checklist.
- **Who/what can set it:** backend (on a valid verification start from the
  driver).
- **Allowed next states:** `passed`, `failed`, `manual_review_required`,
  `blocked`.
- **Backend authority notes:** the backend validates lifecycle/assignment before
  accepting a start.
- **Audit implication:** `verification_started`.

### passed

- **Meaning:** the manual checklist was satisfied and the backend accepted the
  result.
- **Who/what can set it:** backend (accepting a driver-submitted pass).
- **Allowed next states:** terminal for verification (proceeds to proof).
- **Backend authority notes:** the backend, not the app, marks a result as
  accepted; required before proof/completion.
- **Audit implication:** `age_verification_passed`.

### failed

- **Meaning:** a required check could not be satisfied.
- **Who/what can set it:** backend (accepting a driver-submitted failure with a
  reason).
- **Allowed next states:** failed delivery / `return_required` path.
- **Backend authority notes:** completion is blocked; the backend decides return.
- **Audit implication:** `age_verification_failed`.

### manual_review_required

- **Meaning:** an outcome needs human/admin review before resolution (future).
- **Who/what can set it:** backend (future review queue).
- **Allowed next states:** `passed`, `failed`, `blocked` (after review).
- **Backend authority notes:** review is admin-owned; reserved for a future
  compliance upgrade.
- **Audit implication:** review events (future); no raw ID data.

### blocked

- **Meaning:** verification (and therefore completion) cannot proceed —
  ineligibility, invalid assignment/lifecycle, unsafe situation, or backend
  rejection.
- **Who/what can set it:** backend.
- **Allowed next states:** failed delivery / return, or resolution of the
  blocking condition.
- **Backend authority notes:** the app cannot clear a blocked state locally.
- **Audit implication:** `verification_blocked`.

## Verification Failure Reasons

The following are **candidate failure reasons**, finalized in Dr.1.1. Each routes
through the backend; the app only submits the selected reason.

### no_id

- **Meaning:** no government ID was presented.
- **Driver action:** select `no_id` failure.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### expired_id

- **Meaning:** the ID is expired.
- **Driver action:** select `expired_id` failure.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### under_21

- **Meaning:** the recipient is under 21.
- **Driver action:** select `under_21` failure.
- **Backend result:** records failure; hard-blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### name_mismatch

- **Meaning:** the ID name does not satisfy the recipient policy.
- **Driver action:** select `name_mismatch` failure.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### photo_mismatch

- **Meaning:** the ID photo does not appear to match the person.
- **Driver action:** select `photo_mismatch` failure.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### wrong_recipient

- **Meaning:** the person is not the authorized recipient.
- **Driver action:** select `wrong_recipient` failure.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### customer_refused

- **Meaning:** the customer refused verification.
- **Driver action:** select `customer_refused` failure.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### suspected_fake_id

- **Meaning:** the ID appears fraudulent.
- **Driver action:** select `suspected_fake_id` failure; may escalate.
- **Backend result:** records failure; blocks completion; flags for review.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed` (and a flag for admin review).

### unsafe_situation

- **Meaning:** the situation is unsafe to continue.
- **Driver action:** select `unsafe_situation`; invoke safety toolkit.
- **Backend result:** records failure; blocks completion; routes safety.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`, `safety_issue_reported`.

### id_unreadable

- **Meaning:** the ID cannot be read/verified.
- **Driver action:** select `id_unreadable` failure.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### verification_abandoned

- **Meaning:** verification could not be completed and was abandoned.
- **Driver action:** select `verification_abandoned`.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`.

### app_issue

- **Meaning:** a technical issue prevented verification.
- **Driver action:** select `app_issue`; may open support.
- **Backend result:** records failure; blocks completion.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed` (and a support case if opened).

### support_required

- **Meaning:** verification needs support intervention.
- **Driver action:** select `support_required`; open support.
- **Backend result:** records failure; blocks completion; routes support.
- **Delivery result:** failed delivery.
- **Return-to-store requirement:** required (restricted).
- **Audit event:** `age_verification_failed`, `support_escalated`.

## Manual Verification Flow

The full manual verification flow for a restricted order:

1. The driver arrives at the customer.
2. The **Restricted Product Warning** screen appears (no unattended delivery,
   customer present, valid ID, 21+).
3. The **customer must be present** to proceed.
4. The driver starts **Age / ID Verification**.
5. The app displays the **manual checklist.**
6. The driver checks ID validity, expiration, age (21+), and photo/person match.
7. The driver submits a **pass** or **fail** result (with a reason when failed).
8. The backend **validates the current lifecycle and assignment.**
9. The backend records an **AgeVerificationResult** candidate record (redacted
   metadata only).
10. The backend emits **`age_verification_passed`** or
    **`age_verification_failed`.**
11. **If pass:** proceed to **Proof of Delivery.**
12. **If fail:** **block completion** and trigger the **Failed Delivery /
    Return Required** path.

## Backend Authority Requirements

The backend owns, at minimum, these decisions:

- whether the **order requires verification**;
- whether the **driver is eligible** to perform restricted delivery;
- whether the **assignment is valid**;
- whether the **delivery lifecycle allows verification**;
- whether the **verification result can be accepted**;
- whether **completion can proceed**;
- whether a **failure requires return**;
- whether a **support/admin override is needed**;
- whether an **audit event should be emitted**;
- whether **duplicate verification submissions should be rejected** (idempotency).

**Mobile never decides compliance completion alone.** The app submits the result;
the backend accepts or rejects it and authorizes (or blocks) completion.

## Mobile Responsibilities

The Driver App is responsible for:

- **displaying the restricted warning**;
- **collecting the manual checklist result**;
- **collecting the failure reason** (when failed);
- **showing the no-unattended-delivery rule**;
- **blocking local UI progress until the backend responds**;
- **requesting camera permission only for document upload or future verification
  features, not raw ID capture in the MVP**;
- **submitting the verification result**;
- **showing the blocked/failure path**;
- **guiding the driver to proof if passed**;
- **guiding the driver to failed delivery/return if failed**;
- **showing privacy boundaries**;
- **supporting offline/retry-safe submission without duplicate side effects**.

Each item is a presentation or submission responsibility; none constitutes
ownership of the compliance decision.

## Privacy / Redaction Boundary

Privacy rules for verification data:

- **No raw ID image storage in MVP.**
- **No full ID number storage in MVP.**
- **No unredacted OCR data in MVP** (OCR is not used in the MVP at all).
- **No ID image in audit logs.**
- **Redacted metadata only.**
- **Failure reason allowed** (structured, non-sensitive).
- **Verification method allowed** (e.g., "manual checklist").
- **Timestamp allowed.**
- **Driver/order/store association allowed.**
- **Approximate GPS (future) allowed only if legally approved and
  privacy-scoped.**
- **A retention policy must be defined before any future ID artifact storage.**
- **Legal review is required before scan/OCR/vendor/liveness.**

The persisted verification record describes that a check occurred and its
outcome; it never holds the identity document itself or a full identifier.

## Audit Requirements

The following are **candidate audit events**, finalized in Dr.1.1. Each is
backend-emitted.

### restricted_delivery_warning_shown

- **Trigger:** the Restricted Product Warning is presented for a restricted
  order.
- **Actor:** driver (presented); backend (records).
- **Required metadata:** order, store, driver, timestamp.
- **Forbidden metadata:** any ID data.
- **Compliance reason:** evidences that the restricted requirements were
  surfaced.

### verification_started

- **Trigger:** the driver starts the manual checklist.
- **Actor:** driver; backend (records).
- **Required metadata:** order, driver, timestamp, method (manual checklist).
- **Forbidden metadata:** raw ID image, full ID number.
- **Compliance reason:** marks the start of the age gate.

### age_verification_passed

- **Trigger:** the backend accepts a passing result.
- **Actor:** driver (submitted); backend (accepts/records).
- **Required metadata:** order, driver, timestamp, method, outcome.
- **Forbidden metadata:** raw ID image, full ID number, DOB value.
- **Compliance reason:** the authoritative pass enabling proof/completion.

### age_verification_failed

- **Trigger:** the backend accepts a failing result.
- **Actor:** driver (submitted); backend (accepts/records).
- **Required metadata:** order, driver, timestamp, method, failure reason.
- **Forbidden metadata:** raw ID image, full ID number, DOB value.
- **Compliance reason:** blocks completion and drives the return decision.

### verification_blocked

- **Trigger:** verification/completion cannot proceed (ineligibility, invalid
  assignment/lifecycle, backend rejection).
- **Actor:** backend.
- **Required metadata:** order, driver, timestamp, blocking reason.
- **Forbidden metadata:** any ID data.
- **Compliance reason:** records that completion was prevented.

### failed_delivery_started

- **Trigger:** the failed delivery path begins after a verification failure.
- **Actor:** driver (initiates); backend (records).
- **Required metadata:** order, driver, timestamp, failure linkage.
- **Forbidden metadata:** any ID data.
- **Compliance reason:** ties the failure to the delivery outcome.

### return_required

- **Trigger:** a failed restricted delivery requires return.
- **Actor:** backend.
- **Required metadata:** order, store, driver, timestamp, reason linkage.
- **Forbidden metadata:** any ID data.
- **Compliance reason:** mandates accountable return of restricted product.

### support_escalated

- **Trigger:** verification escalates to support.
- **Actor:** driver (initiates); backend (records).
- **Required metadata:** order, driver, timestamp, category.
- **Forbidden metadata:** any ID data.
- **Compliance reason:** routes intervention with an audit trail.

### safety_issue_reported

- **Trigger:** an unsafe verification situation is reported.
- **Actor:** driver (initiates); backend (records).
- **Required metadata:** order, driver, timestamp, type, scoped location share.
- **Forbidden metadata:** any ID data; unscoped/public location.
- **Compliance reason:** driver safety with an audit trail.

Additional audit rules:

- **No raw ID data in audit logs.**
- **No full ID number in audit logs.**
- **The audit timeline is backend-owned.**
- **Idempotency must prevent duplicate critical verification events.**

## Store/Admin Visibility

Store and Admin gain visibility through backend events and redacted records, not
direct mobile mutation.

**Store visibility:**

- verification required status;
- delivery failed due to verification failure, **without exposing sensitive ID
  details**;
- return required;
- returned to store;
- store return confirmation requirement.

**Admin visibility:**

- verification pass/fail counts;
- failure reasons;
- delivery audit timeline;
- driver compliance pattern;
- suspected fake ID reports;
- safety/support escalations;
- **redacted verification metadata only.**

**Store/Admin visibility must come through backend events and redacted records,
not direct mobile mutation.** No driver-app screen writes to Store/Admin state.

## Legal Review Dependencies

The following require legal/compliance review **before** they may be introduced:

- ID scan;
- barcode scan;
- OCR;
- liveness detection;
- third-party verification vendor;
- encrypted redacted ID artifact storage;
- GPS proof retention;
- automated compliance decisions;
- admin review of sensitive verification artifacts.

**Until legally approved, the MVP remains a manual checklist only.** No automated,
vendor, or image-based verification is introduced without explicit legal sign-off
and a defined retention policy.

## Future Verification Methods

The following are **reserved future methods**, not implemented. Each is gated on
legal review and a later phase.

### future_barcode_scan

- **Purpose:** read the ID's machine-readable barcode to assist verification.
- **Prerequisite:** legal review; defined data-minimization and retention.
- **Privacy risk:** barcode contains identity data; must be minimized/redacted.
- **Compliance risk:** parsing accuracy; false pass/fail.
- **Backend requirement:** accept/validate parsed, redacted result.
- **Mobile requirement:** scan capability; no raw storage.
- **Phase target:** Dr.1.5.
- **Notes:** reserved; not MVP.

### future_ocr_vendor

- **Purpose:** extract and verify ID fields via OCR/vendor.
- **Prerequisite:** legal review; vendor due diligence; contract.
- **Privacy risk:** processing of identity documents; data sharing.
- **Compliance risk:** vendor accuracy and liability.
- **Backend requirement:** integrate vendor result as redacted metadata.
- **Mobile requirement:** capture per the approved policy only.
- **Phase target:** Dr.1.5.
- **Notes:** reserved; not MVP.

### future_liveness_vendor

- **Purpose:** confirm the presenter is a live person matching the ID.
- **Prerequisite:** legal review; vendor due diligence.
- **Privacy risk:** biometric processing.
- **Compliance risk:** biometric regulation; accuracy.
- **Backend requirement:** accept redacted liveness outcome.
- **Mobile requirement:** capture per the approved policy only.
- **Phase target:** Dr.1.5.
- **Notes:** reserved; not MVP.

### future_encrypted_redacted_image_storage

- **Purpose:** store an encrypted, redacted artifact for evidence if required.
- **Prerequisite:** legal review; retention policy; encryption design.
- **Privacy risk:** storing any ID-derived artifact.
- **Compliance risk:** breach exposure; retention limits.
- **Backend requirement:** encrypted storage with strict access + retention.
- **Mobile requirement:** capture per the approved policy only.
- **Phase target:** Dr.1.5.
- **Notes:** reserved; not MVP — the MVP stores no ID artifact.

### future_admin_compliance_review

- **Purpose:** admin review queue for `manual_review_required` outcomes.
- **Prerequisite:** legal review; access controls.
- **Privacy risk:** admin exposure to verification artifacts.
- **Compliance risk:** consistent, audited decisions.
- **Backend requirement:** review queue + audited decisions on redacted data.
- **Mobile requirement:** none directly.
- **Phase target:** Dr.1.5.
- **Notes:** reserved; redacted metadata only.

### future_customer_pin_pairing

- **Purpose:** a customer-provided PIN as a proof/pairing factor.
- **Prerequisite:** product/legal review.
- **Privacy risk:** low (PIN, not ID).
- **Compliance risk:** does not replace 21+ verification.
- **Backend requirement:** validate PIN as a proof element.
- **Mobile requirement:** capture PIN.
- **Phase target:** Dr.1.5.
- **Notes:** reserved; complements, does not replace, 21+ verification.

### future_signature_or_photo_proof_if_legally_allowed

- **Purpose:** signature or non-ID delivery photo as proof, if permitted.
- **Prerequisite:** legal review; must avoid capturing ID documents.
- **Privacy risk:** photo could inadvertently capture sensitive data.
- **Compliance risk:** proof integrity; privacy.
- **Backend requirement:** validate and store per the approved policy.
- **Mobile requirement:** capture per the approved policy only.
- **Phase target:** Dr.1.5.
- **Notes:** reserved; never an ID-document capture.

## Blocked Delivery Rules

Each scenario below blocks completion. The app shows a blocked/failure outcome;
the backend records it; restricted product routes to return.

### No ID

- **Driver UI outcome:** verification fails; completion blocked.
- **Backend outcome:** records `age_verification_failed` (`no_id`); blocks
  completion.
- **Audit event:** `age_verification_failed`.
- **Return-to-store outcome:** required.
- **Support/safety escalation:** none unless requested.

### Expired ID

- **Driver UI outcome:** verification fails; completion blocked.
- **Backend outcome:** records failure (`expired_id`); blocks completion.
- **Audit event:** `age_verification_failed`.
- **Return-to-store outcome:** required.
- **Support/safety escalation:** none unless requested.

### Under 21

- **Driver UI outcome:** verification fails; hard block.
- **Backend outcome:** records failure (`under_21`); hard-blocks completion.
- **Audit event:** `age_verification_failed`.
- **Return-to-store outcome:** required.
- **Support/safety escalation:** none unless requested.

### ID does not match person

- **Driver UI outcome:** verification fails; completion blocked.
- **Backend outcome:** records failure (`photo_mismatch`); blocks completion.
- **Audit event:** `age_verification_failed`.
- **Return-to-store outcome:** required.
- **Support/safety escalation:** none unless requested.

### Wrong recipient

- **Driver UI outcome:** verification fails; completion blocked.
- **Backend outcome:** records failure (`wrong_recipient`); blocks completion.
- **Audit event:** `age_verification_failed`.
- **Return-to-store outcome:** required.
- **Support/safety escalation:** none unless requested.

### Customer refused

- **Driver UI outcome:** verification fails; completion blocked.
- **Backend outcome:** records failure (`customer_refused`); blocks completion.
- **Audit event:** `age_verification_failed`.
- **Return-to-store outcome:** required.
- **Support/safety escalation:** none unless requested.

### Suspected fake ID

- **Driver UI outcome:** verification fails; completion blocked; report option.
- **Backend outcome:** records failure (`suspected_fake_id`); flags for review.
- **Audit event:** `age_verification_failed` (+ review flag).
- **Return-to-store outcome:** required.
- **Support/safety escalation:** optional support escalation.

### Unsafe situation

- **Driver UI outcome:** verification blocked; safety actions surfaced.
- **Backend outcome:** records failure (`unsafe_situation`); routes safety.
- **Audit event:** `age_verification_failed`, `safety_issue_reported`.
- **Return-to-store outcome:** required.
- **Support/safety escalation:** safety/support escalation.

### App cannot complete verification

- **Driver UI outcome:** verification blocked; support option.
- **Backend outcome:** records failure (`app_issue`); blocks completion.
- **Audit event:** `age_verification_failed` (+ support case if opened).
- **Return-to-store outcome:** required.
- **Support/safety escalation:** optional support escalation.

### Backend rejects verification result

- **Driver UI outcome:** result not accepted; completion blocked.
- **Backend outcome:** rejects the submission; emits `verification_blocked`.
- **Audit event:** `verification_blocked`.
- **Return-to-store outcome:** required if the order cannot be completed.
- **Support/safety escalation:** none unless requested.

### Driver not eligible

- **Driver UI outcome:** cannot perform restricted delivery; blocked.
- **Backend outcome:** blocks via eligibility; emits `verification_blocked`.
- **Audit event:** `verification_blocked`.
- **Return-to-store outcome:** required if already in possession of product.
- **Support/safety escalation:** none unless requested.

### Assignment invalid

- **Driver UI outcome:** action rejected; blocked.
- **Backend outcome:** rejects on invalid assignment; emits
  `verification_blocked`.
- **Audit event:** `verification_blocked`.
- **Return-to-store outcome:** as directed by the backend.
- **Support/safety escalation:** none unless requested.

### Order lifecycle invalid

- **Driver UI outcome:** action rejected; blocked.
- **Backend outcome:** rejects out-of-sequence verification; emits
  `verification_blocked`.
- **Audit event:** `verification_blocked`.
- **Return-to-store outcome:** as directed by the backend.
- **Support/safety escalation:** none unless requested.

### Required permissions unavailable (if needed)

- **Driver UI outcome:** blocked with a recovery path to device settings.
- **Backend outcome:** may block completion if a required permission is
  unavailable.
- **Audit event:** `verification_blocked` (where applicable).
- **Return-to-store outcome:** as directed by the backend.
- **Support/safety escalation:** none unless requested.

## Return-to-Store Requirement

For a failed restricted delivery:

- A **failed restricted delivery requires return.**
- The **driver cannot complete the delivery.**
- The **driver cannot self-close the return.**
- The **store must confirm the returned item.**
- The **backend controls inventory review.**
- **Store/admin visibility is required** through backend events.
- A **support/admin override must be audited.**
- The **return record must link to the verification failure** that triggered it.

This routes undeliverable restricted product back to the store accountably; the
detailed return architecture is in Dr.1.0.H.

## Idempotency / Offline Retry Requirements

The following actions require idempotency:

- start verification
- submit passed verification
- submit failed verification
- submit verification failure reason
- open support escalation
- report unsafe verification situation
- start failed delivery
- start return
- confirm store return

For these actions:

- **Mobile can retry safely** after a network failure or app restart.
- **The backend rejects duplicate side effects** — a retried submission does not
  create a second verification result, failure, escalation, or return.
- **The audit timeline must not duplicate verification events incorrectly** —
  each logical verification event is recorded once.
- **Offline verification should be constrained** because restricted-delivery
  completion requires backend acceptance.
- **If offline, the app should block completion** until verification/proof can be
  accepted by the backend.

## Integration With Proof / Failed Delivery / Return

This document connects to the proof / failure / return architecture (Dr.1.0.H):

- A **verification pass is required before proof/completion** for restricted
  orders.
- A **verification failure feeds failed delivery.**
- A **failed restricted delivery feeds return-to-store.**
- A **return confirmation closes the failed restricted path.**
- **Proof cannot override a failed verification** — proof is only meaningful
  after an accepted pass.
- **Return cannot be skipped by mobile** — the backend owns the return
  requirement and closure.

## Phase Target Map

Compliance/verification work maps to future phases as follows:

- **Dr.1.1 — backend verification result, failure reasons, audit events,
  return-required decisions, idempotency.**
- **Dr.1.2 — mobile foundation permission/privacy handling and API client
  readiness.**
- **Dr.1.3 — manual verification checklist MVP in the driver app.**
- **Dr.1.4 — support/safety escalation integration.**
- **Dr.1.5 — legal-approved scan/OCR/vendor/liveness/compliance review
  upgrade.**
- **Dr.1.6 — advanced trust/performance signals based on compliance history.**

Each phase requires its own contract lock, diagnostic, gameplan, implementation,
validation, and pass/fail report.

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
- OCR
- barcode scan
- liveness check
- vendor verification
- raw ID storage
- full ID number storage
- automatic compliance override
- production launch

Any work that would cross one of these boundaries requires a separate, explicitly
approved future phase with its own contract, consistent with
`docs/dr.1.0-driver-app-contract-lock.md` and `docs/f2.27-contract-lock.md`.
