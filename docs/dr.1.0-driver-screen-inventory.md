# Dr.1.0 Driver App Screen Inventory

## Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.D — Driver App Screen Inventory + Screen Specs
- **Status:** Draft for Dr.1.0 documentation
- **Scope:** documentation only
- **Implementation:** none

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them.

## Purpose

This document defines the complete screen inventory for the NubeRush Driver App
— every major screen required for a full driver operations platform, not a small
assigned-orders viewer.

The inventory rests on six fixed positions:

- **Mobile is the operational surface.** Screens are where field execution
  happens.
- **Backend is the authority.** Eligibility, order state, compliance, proof, and
  completion are decided server-side; screens request and display.
- **Store and Admin panels are the visibility and oversight layer.** Screen
  actions surface to them through backend events, never by direct mobile state.
- **Driver access must be order-scoped, not store-wide.** No screen exposes
  store-wide inventory, orders, or administration.
- **Restricted-product compliance screens are core, not optional.** Verification,
  proof, restricted warnings, handoff, and return screens are first-class.
- **This document describes screens only; it does not create UI code.** It is
  architecture documentation.

## Screen Architecture Principles

- **Screen inventory before implementation.** The full screen map is defined
  before any UI is built.
- **Backend-authorized screens.** Screen-driven state changes are validated and
  recorded by the backend.
- **Order-scoped driver visibility.** Screens show only offered/assigned orders.
- **Compliance-first restricted delivery.** Restricted handling and 21+
  verification are first-class screen flows.
- **No unattended restricted delivery.** Dropoff screens forbid leave-at-door for
  restricted products.
- **No raw ID image storage in MVP.** Verification screens capture redacted
  metadata only.
- **Return-to-store accountability.** Failed restricted deliveries route through
  return screens the driver cannot self-close.
- **Store handoff accountability.** Pickup and return require store-side
  confirmation screens.
- **Audit-first delivery lifecycle.** Screen actions emit compliance-grade audit
  events.
- **Mobile as action surface, not business-rule owner.** A screen's "primary
  action" submits intent; it does not own a business decision.
- **Permission-aware mobile UX.** Screens degrade gracefully and recover when
  device permissions are missing.
- **Offline/retry-aware UX.** Screens handle offline and retry without
  double-applying actions.
- **Safety and support as first-class screens.** Safety and support are
  always-reachable, not buried.
- **Future screens reserved without implementation.** Reserved screens are
  documented as future, not built now.

## Screen Summary Table

| # | Screen | Screen group | Primary purpose | Core phase target | Backend dependency | Permission dependency | Compliance sensitivity | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Splash / App Loading | App Entry / Auth | Bootstrap session and route | Dr.1.2 | High | None | Medium | No delivery data before session validation |
| 2 | Login | App Entry / Auth | Authenticate driver | Dr.1.2 | High | None | Medium | Backend/auth provider validates |
| 3 | Password Recovery | App Entry / Auth | Initiate recovery | Dr.1.2 | High | None | Medium | No account-existence leak |
| 4 | Driver Signup / Invitation | Onboarding / Activation | Begin onboarding | Dr.1.2 | High | None | High | Provisioned/invited, not open |
| 5 | Activation Checklist | Onboarding / Activation | Drive activation steps | Dr.1.2 | High | None | High | Backend owns completion truth |
| 6 | Profile Setup | Onboarding / Activation | Capture identity profile | Dr.1.2 | High | None | High | DOB drives 21+ eligibility |
| 7 | Phone Verification | Onboarding / Activation | Verify phone | Dr.1.2 | High | None | High | Cannot fake locally |
| 8 | Email Verification | Onboarding / Activation | Verify email | Dr.1.2 | High | None | Medium | Cannot fake locally |
| 9 | Document Center | Documents / Vehicle / Training | View document set | Dr.1.2 | High | None | High | License, ID, insurance, registration |
| 10 | Upload Document | Documents / Vehicle / Training | Submit a document | Dr.1.2 | High | Camera | High | Secure handling; backend review |
| 11 | Document Status | Documents / Vehicle / Training | Show document states | Dr.1.2 | High | None | High | Expired required doc blocks online |
| 12 | Rejected Document Detail | Documents / Vehicle / Training | Explain rejection | Dr.1.2 | High | None | High | Reason + resubmission, no bypass |
| 13 | Vehicle Profile | Documents / Vehicle / Training | Show active vehicle | Dr.1.2 | Medium | None | Medium | No ride-class/passenger logic |
| 14 | Add Vehicle | Documents / Vehicle / Training | Register a vehicle | Dr.1.2 | Medium | None | Medium | Approval required |
| 15 | Vehicle Documents | Documents / Vehicle / Training | Vehicle reg/insurance | Dr.1.2 | High | Camera | High | Expired doc blocks online |
| 16 | Compliance Training Home | Documents / Vehicle / Training | Show training modules | Dr.1.2 | High | None | High | Required before restricted delivery |
| 17 | Training Lesson | Documents / Vehicle / Training | Deliver a lesson | Dr.1.2 | Medium | None | High | 21+, failed ID, return policy |
| 18 | Training Quiz Future | Documents / Vehicle / Training | Certify knowledge | Dr.1.5 (future) | Medium | None | High | Reserved; not MVP |
| 19 | Policy Acknowledgment | Onboarding / Activation | Record acks | Dr.1.2 | High | None | Critical | Restricted/no-unattended/return |
| 20 | Approval Pending | Onboarding / Activation | Show pending approval | Dr.1.2 | High | None | High | Rejected/action-required routes |
| 21 | Home / Driver Map | Home / Online State | Driver state + map | Dr.1.3 | High | Location | Medium | Order-scoped only |
| 22 | Go Online Check | Home / Online State | Gate going online | Dr.1.3 | High | Location | High | Backend decides can_go_online |
| 23 | Online Waiting State | Home / Online State | Await offers | Dr.1.3 | High | Location | Medium | Online time; pause/offline |
| 24 | Delivery Offer | Offers / Assignment | Present an offer | Dr.1.3 | High | Notifications | High | Pre-accept privacy boundary |
| 25 | Delivery Offer Detail | Offers / Assignment | Expand offer details | Dr.1.3 | High | None | High | Preserves privacy boundary |
| 26 | Decline Reason | Offers / Assignment | Capture decline reason | Dr.1.3 | High | None | Medium | Backend records decline |
| 27 | Assigned Deliveries | Offers / Assignment | List assigned deliveries | Dr.1.3 | High | None | High | Driver-scoped only |
| 28 | Active Delivery Overview | Active Delivery | Show current state | Dr.1.3 | High | Location | Critical | Backend controls next action |
| 29 | Navigate to Store | Active Delivery | Route to store | Dr.1.3 | Low | Location | Low | External nav handoff |
| 30 | Arrived at Store | Store Pickup / Handoff | Mark store arrival | Dr.1.3 | High | Location | Medium | Geofence validation future |
| 31 | Store Pickup Instructions | Store Pickup / Handoff | Show pickup details | Dr.1.3 | High | None | High | Order #, bags, items, restricted |
| 32 | Store Handoff PIN | Store Pickup / Handoff | Validate store release | Dr.1.3 | High | None | Critical | No pickup if handoff fails |
| 33 | Pickup Checklist | Store Pickup / Handoff | Confirm correct order | Dr.1.3 | High | None | High | Restricted-product ack |
| 34 | Confirm Pickup | Store Pickup / Handoff | Confirm pickup | Dr.1.3 | High | None | Critical | Emits pickup audit event |
| 35 | Pickup Issue | Store Pickup / Handoff | Report pickup problem | Dr.1.3 | High | None | High | Not ready / closed / damaged |
| 36 | Navigate to Customer | Customer Dropoff / Verification / Proof | Route to customer | Dr.1.3 | Medium | Location | High | Address only after picked-up |
| 37 | Customer Delivery Instructions | Customer Dropoff / Verification / Proof | Show dropoff notes | Dr.1.3 | High | None | High | No leave-at-door for restricted |
| 38 | Contact Customer | Customer Dropoff / Verification / Proof | Masked contact | Dr.1.3 | Medium | None | Medium | No personal phone exposure |
| 39 | Arrived at Customer | Customer Dropoff / Verification / Proof | Mark customer arrival | Dr.1.3 | High | Location | High | Starts verification flow |
| 40 | Restricted Product Warning | Customer Dropoff / Verification / Proof | Enforce restricted rules | Dr.1.3 | High | None | Critical | Customer present, 21+, valid ID |
| 41 | Age / ID Verification | Customer Dropoff / Verification / Proof | 21+ manual checklist | Dr.1.3 | High | None | Critical | No raw ID image storage |
| 42 | ID Verification Failed | Customer Dropoff / Verification / Proof | Capture verification fail | Dr.1.3 | High | None | Critical | Blocks completion → return |
| 43 | Proof of Delivery | Customer Dropoff / Verification / Proof | Capture proof | Dr.1.3 | High | None | Critical | No proof, no delivered |
| 44 | Customer PIN Future | Customer Dropoff / Verification / Proof | Optional PIN proof | Dr.1.5 (future) | High | None | High | Reserved; not MVP |
| 45 | Complete Delivery | Customer Dropoff / Verification / Proof | Authorize completion | Dr.1.3 | High | Location | Critical | Requires proof + verification |
| 46 | Delivery Completed Summary | Customer Dropoff / Verification / Proof | Confirm completion | Dr.1.3 | High | None | Medium | Estimated earnings visibility |
| 47 | Failed Delivery Reason | Failed Delivery / Return to Store | Capture failure reason | Dr.1.3 | High | None | Critical | Backend decides return |
| 48 | Wait Timer | Failed Delivery / Return to Store | Customer-unavailable wait | Dr.1.3 | High | None | High | Contact attempts; escalation |
| 49 | Return Required | Failed Delivery / Return to Store | Trigger return | Dr.1.3 | High | None | Critical | Cannot self-close |
| 50 | Navigate Back to Store | Failed Delivery / Return to Store | Route to store | Dr.1.3 | Low | Location | High | Return audit state |
| 51 | Store Return Confirmation | Failed Delivery / Return to Store | Validate return | Dr.1.3 | High | None | Critical | Store PIN/confirmation |
| 52 | Return Completed | Failed Delivery / Return to Store | Close return | Dr.1.3 | High | None | Critical | Store/admin visibility |
| 53 | Delivery History | History / Earnings / Performance | List past deliveries | Dr.1.4 | High | None | Medium | Driver-scoped only |
| 54 | Delivery Detail History | History / Earnings / Performance | Show delivery timeline | Dr.1.4 | High | None | High | Redacted metadata; no raw ID |
| 55 | Earnings Summary | History / Earnings / Performance | Earnings visibility | Dr.1.6 | Medium | None | Low | No payouts/cashout/Stripe |
| 56 | Performance Dashboard | History / Earnings / Performance | Show metrics | Dr.1.6 | High | None | Medium | Compliance signals |
| 57 | Rewards / Status Future | History / Earnings / Performance | Driver status tiers | Dr.1.6 (future) | High | None | Medium | Reserved; not MVP |
| 58 | Safety Toolkit | Safety / Support | Field safety actions | Dr.1.4 | Medium | Location | High | Always reachable |
| 59 | Emergency Help | Safety / Support | Emergency actions | Dr.1.4 | Medium | Location | High | Call 911; location share |
| 60 | Report Incident | Safety / Support | File incident report | Dr.1.4 | High | None | High | Auditable incident |
| 61 | Support Center | Safety / Support | Help and tickets | Dr.1.4 | High | None | Medium | Contextual support |
| 62 | Support Category | Safety / Support | Pick support topic | Dr.1.4 | Medium | None | Medium | ID/safety topics first-class |
| 63 | Support Case Detail | Safety / Support | View a case | Dr.1.4 | High | None | Medium | Messages/attachments future |
| 64 | Notifications Center | Notifications / Account / Settings | List notifications | Dr.1.4 | High | Notifications | Medium | Compliance pushes non-optional |
| 65 | Account | Notifications / Account / Settings | Account overview | Dr.1.2 | High | None | Medium | Profile/docs/vehicle/status |
| 66 | Settings | Notifications / Account / Settings | App configuration | Dr.1.2 | Medium | None | Medium | Entry to sub-settings |
| 67 | Navigation Preferences | Notifications / Account / Settings | Choose nav app | Dr.1.3 | Low | None | Low | Apple/Google/Waze |
| 68 | Notification Preferences | Notifications / Account / Settings | Configure pushes | Dr.1.4 | Medium | Notifications | Medium | Critical pushes locked |
| 69 | Sound Settings | Notifications / Account / Settings | Sound/vibration | Dr.1.4 | Low | None | Low | Offer sound |
| 70 | App Permissions | Notifications / Account / Settings | Manage permissions | Dr.1.2 | Low | Location/Camera/Notifications | High | Recovery to device settings |
| 71 | Privacy | Diagnostics / Legal | Privacy disclosures | Dr.1.2 | Medium | None | High | No raw ID image storage |
| 72 | Legal / Policies | Diagnostics / Legal | Legal documents | Dr.1.2 | Medium | None | High | Restricted-product policy |
| 73 | App Diagnostics | Diagnostics / Legal | Device/app health | Dr.1.2 | Medium | None | Medium | Version, GPS, network |
| 74 | Report Bug | Diagnostics / Legal | Report app issue | Dr.1.4 | High | None | Low | Diagnostics attach future |

## Screen Groups

The Driver App screens are organized into the following groups:

- **App Entry / Auth** — splash, login, recovery; bootstraps session before any
  delivery data is shown.
- **Onboarding / Activation** — invitation, activation checklist, profile,
  verifications, policy acknowledgment, approval pending.
- **Documents / Vehicle / Training** — document center and uploads, vehicle
  profile and documents, training modules.
- **Home / Online State** — driver home/map, go-online gating, waiting for
  offers.
- **Offers / Assignment** — offers, offer detail, decline reason, assigned
  deliveries (order-scoped).
- **Active Delivery** — active delivery overview and navigation to store.
- **Store Pickup / Handoff** — arrival, pickup instructions, store handoff PIN,
  pickup checklist, confirm pickup, pickup issues.
- **Customer Dropoff / Verification / Proof** — navigation to customer, dropoff
  instructions, masked contact, arrival, restricted warning, 21+ verification,
  verification failure, proof, completion.
- **Failed Delivery / Return to Store** — failure reason, wait timer, return
  required, return navigation, store return confirmation, return completed.
- **History / Earnings / Performance** — delivery history and detail, earnings
  visibility, performance, reserved rewards.
- **Safety / Support** — safety toolkit, emergency help, incident reporting,
  support center, categories, case detail.
- **Notifications / Account / Settings** — notifications center, account,
  settings and sub-settings, permissions.
- **Diagnostics / Legal** — privacy, legal/policies, diagnostics, bug reporting.

## Full Screen Specifications

Each screen below uses a consistent structure: Purpose, Entry Point, Primary
Action, Secondary Actions, Required Backend Data, Required Permissions, Backend
Authority, Audit Events, Empty State, Error State, Blocked State, and Future
Notes. A screen's "primary action" submits driver intent; it never owns a
business decision.

## 1. Splash / App Loading

### Purpose
Bootstrap the app: load auth state, check app version, and route the driver to
the correct entry surface before any delivery data is shown.

### Entry Point
App launch (cold or warm start).

### Primary Action
- Resolve session and route to Login, Onboarding, Approval Pending, or Home.

### Secondary Actions
- Trigger forced-update prompt if the app version is unsupported.

### Required Backend Data
- Session/token validity, minimum-supported app version, driver high-level state
  (onboarding/approval/active).

### Required Permissions
- None for screen entry.

### Backend Authority
- Validates the session and decides the routing state; the app never trusts a
  local-only session.

### Audit Events
- None directly; downstream actions may emit audit events.

### Empty State
- Brief loading indicator; no content.

### Error State
- Connectivity/version failure shows a retry or update prompt; no delivery data
  is revealed.

### Blocked State
- Unsupported app version blocks entry until updated.

### Future Notes
- None.

## 2. Login

### Purpose
Authenticate the driver against the backend/auth provider.

### Entry Point
From Splash when no valid session exists; from logout.

### Primary Action
- Submit email/phone credentials for backend validation.

### Secondary Actions
- Go to Password Recovery; go to Signup / Invitation.

### Required Backend Data
- Auth challenge/result from the backend/auth provider.

### Required Permissions
- None for screen entry.

### Backend Authority
- Validates credentials and issues the session; there is no local-only driver
  identity.

### Audit Events
- Authentication events recorded by the backend/auth provider.

### Empty State
- Empty credential form.

### Error State
- Invalid credentials or connectivity error shown without leaking which field
  failed.

### Blocked State
- Locked/blocked accounts cannot authenticate; a generic message is shown.

### Future Notes
- Biometric unlock (future).

## 3. Password Recovery

### Purpose
Let a driver initiate account recovery through the backend/auth provider.

### Entry Point
From Login.

### Primary Action
- Submit recovery request (email/phone).

### Secondary Actions
- Return to Login.

### Required Backend Data
- Recovery initiation result from the backend/auth provider.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the recovery flow; the response does not leak whether an account exists.

### Audit Events
- Recovery request events recorded by the backend/auth provider.

### Empty State
- Empty recovery form.

### Error State
- Generic failure message; no account-existence disclosure.

### Blocked State
- Rate-limited requests are throttled.

### Future Notes
- None.

## 4. Driver Signup / Invitation

### Purpose
Begin onboarding through an invitation or signup path; entry to the activation
flow.

### Entry Point
From Login (signup link) or an invitation deep link.

### Primary Action
- Start onboarding from an invitation or signup request.

### Secondary Actions
- Return to Login.

### Required Backend Data
- Invitation validity / provisioning state.

### Required Permissions
- None for screen entry.

### Backend Authority
- Provisions the driver account and controls access; **a driver cannot operate
  until approval and eligibility pass.**

### Audit Events
- Account creation/invitation acceptance recorded by the backend.

### Empty State
- Invitation prompt or signup form.

### Error State
- Invalid/expired invitation message.

### Blocked State
- Open self-signup is not permitted where provisioning is invitation-only.

### Future Notes
- None.

## 5. Activation Checklist

### Purpose
Show the steps required to activate: profile, phone, email, documents, vehicle,
training, policy acknowledgment, and approval status.

### Entry Point
After signup/invitation; from Home while not yet active.

### Primary Action
- Open the next incomplete activation step.

### Secondary Actions
- Review completed steps; refresh status.

### Required Backend Data
- Per-step completion state and overall activation state.

### Required Permissions
- None for screen entry.

### Backend Authority
- **Owns checklist completion truth**; the app reflects backend-validated step
  state.

### Audit Events
- None directly; step completions emit their own events.

### Empty State
- All steps shown as not started.

### Error State
- Status fetch failure shows a retry.

### Blocked State
- Steps requiring a prior step are locked until the prerequisite passes.

### Future Notes
- None.

## 6. Profile Setup

### Purpose
Capture the driver's identity profile.

### Entry Point
From the Activation Checklist.

### Primary Action
- Submit legal name, phone, email, date of birth, photo, and operating
  city/zone.

### Secondary Actions
- Edit a previously entered field.

### Required Backend Data
- Existing profile values and validation rules.

### Required Permissions
- None for screen entry (photo capture may request Camera at point of use).

### Backend Authority
- Validates and stores the profile; **date of birth drives 21+ eligibility** and
  is not client-trusted for the gate.

### Audit Events
- Profile creation/update recorded by the backend.

### Empty State
- Empty profile form.

### Error State
- Validation errors per field.

### Blocked State
- Locked after approval where edits require admin review.

### Future Notes
- None.

## 7. Phone Verification

### Purpose
Verify the driver's phone number.

### Entry Point
From the Activation Checklist / Profile Setup.

### Primary Action
- Submit the OTP / provider verification.

### Secondary Actions
- Resend the code.

### Required Backend Data
- Verification challenge/result.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns verification; **the result cannot be faked locally.**

### Audit Events
- Phone-verification result recorded by the backend.

### Empty State
- Awaiting code entry.

### Error State
- Invalid/expired code message.

### Blocked State
- Throttled after repeated failures.

### Future Notes
- None.

## 8. Email Verification

### Purpose
Verify the driver's email address.

### Entry Point
From the Activation Checklist / Profile Setup.

### Primary Action
- Complete provider/backend email verification.

### Secondary Actions
- Resend the verification email.

### Required Backend Data
- Verification state.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns verification; **the result cannot be faked locally.**

### Audit Events
- Email-verification result recorded by the backend.

### Empty State
- Awaiting verification.

### Error State
- Verification failure/expiry message.

### Blocked State
- Throttled after repeated requests.

### Future Notes
- None.

## 9. Document Center

### Purpose
Show the driver's required documents and their states: license, government ID,
selfie, insurance, registration, and background check status.

### Entry Point
From the Activation Checklist; from Account.

### Primary Action
- Open a document to view its status or upload.

### Secondary Actions
- Filter by required/optional; view expiring documents.

### Required Backend Data
- Document list with state, expiry, and required/optional flags; background-check
  status.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns approval/rejection and expiry evaluation; document review is
  backend/admin-controlled.

### Audit Events
- None directly; uploads/decisions emit their own events.

### Empty State
- No documents uploaded yet.

### Error State
- Document list fetch failure shows a retry.

### Blocked State
- N/A (read surface).

### Future Notes
- Selfie verification (future).

## 10. Upload Document

### Purpose
Submit a required document via camera or photo upload.

### Entry Point
From the Document Center / Vehicle Documents.

### Primary Action
- Capture/upload the document image for backend review.

### Secondary Actions
- Retake; cancel.

### Required Backend Data
- Upload target/spec and accepted formats.

### Required Permissions
- Camera (for capture); optional photo/gallery (future).

### Backend Authority
- Receives and reviews the document; **document review remains backend/admin-
  controlled.** Storage follows the approved secure document-handling policy.

### Audit Events
- Document submitted/resubmitted recorded by the backend.

### Empty State
- Capture prompt.

### Error State
- Upload failure with retry; oversized/invalid format rejected.

### Blocked State
- Upload blocked without the Camera permission until granted.

### Future Notes
- Gallery import (future). No raw ID image storage beyond the approved secure
  document-handling policy.

## 11. Document Status

### Purpose
Show the state of a document: pending, approved, rejected, expired, or expiring
soon.

### Entry Point
From the Document Center.

### Primary Action
- Review status and proceed to resubmission if rejected/expired.

### Secondary Actions
- View expiry date; set a reminder (future).

### Required Backend Data
- Document state, decision reason, and expiry.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the status; **an expired required document blocks going online.**

### Audit Events
- None directly; resubmission emits its own event.

### Empty State
- N/A (always tied to a document).

### Error State
- Status fetch failure shows a retry.

### Blocked State
- Indicates when an expired/rejected required document blocks online mode.

### Future Notes
- Expiry reminders (future).

## 12. Rejected Document Detail

### Purpose
Explain why a document was rejected and provide a resubmission path.

### Entry Point
From Document Status when rejected.

### Primary Action
- Start resubmission.

### Secondary Actions
- Contact support about the rejection.

### Required Backend Data
- Rejection reason and resubmission requirements.

### Required Permissions
- None for screen entry (resubmission uses Upload Document).

### Backend Authority
- Owns the rejection reason; **there is no bypass** — only resubmission and
  re-review.

### Audit Events
- None directly; resubmission emits its own event.

### Empty State
- N/A.

### Error State
- Reason fetch failure shows a retry.

### Blocked State
- Operation remains blocked until an approved document replaces the rejected one.

### Future Notes
- None.

## 13. Vehicle Profile

### Purpose
Show the driver's active delivery vehicle and its approval status.

### Entry Point
From the Activation Checklist; from Account.

### Primary Action
- View the active vehicle and its status.

### Secondary Actions
- Add a vehicle; open vehicle documents.

### Required Backend Data
- Vehicle record(s), active selection, and approval state.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns vehicle approval and the active-vehicle relationship; **no passenger
  capacity or rideshare class** exists.

### Audit Events
- None directly; vehicle changes emit their own events.

### Empty State
- No vehicle added yet.

### Error State
- Vehicle fetch failure shows a retry.

### Blocked State
- N/A (read surface).

### Future Notes
- Multiple-vehicle management (future).

## 14. Add Vehicle

### Purpose
Register a delivery vehicle for approval.

### Entry Point
From Vehicle Profile.

### Primary Action
- Submit make, model, year, color, and plate.

### Secondary Actions
- Cancel.

### Required Backend Data
- Vehicle field validation rules.

### Required Permissions
- None for screen entry.

### Backend Authority
- Validates and stores the vehicle; **vehicle approval is required** before it
  can be used to operate.

### Audit Events
- Vehicle added recorded by the backend.

### Empty State
- Empty vehicle form.

### Error State
- Validation errors per field.

### Blocked State
- N/A.

### Future Notes
- Vehicle photo (future).

## 15. Vehicle Documents

### Purpose
Manage vehicle registration and insurance documents and their states.

### Entry Point
From Vehicle Profile.

### Primary Action
- Upload/replace registration and insurance documents.

### Secondary Actions
- View expiry dates.

### Required Backend Data
- Vehicle document states and expiry.

### Required Permissions
- Camera (for capture).

### Backend Authority
- Owns approval and expiry; **an expired vehicle document blocks going online.**

### Audit Events
- None directly; uploads emit their own events.

### Empty State
- No vehicle documents uploaded.

### Error State
- Upload/status failure shows a retry.

### Blocked State
- Indicates when an expired vehicle document blocks online mode.

### Future Notes
- None.

## 16. Compliance Training Home

### Purpose
Show required training modules and restricted-product training status.

### Entry Point
From the Activation Checklist; from Account.

### Primary Action
- Open the next required training module.

### Secondary Actions
- Review completed modules.

### Required Backend Data
- Training module list and completion state.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns module definitions and completion truth; **training is required before
  restricted deliveries.**

### Audit Events
- None directly; lesson/policy completions emit their own events.

### Empty State
- No modules started.

### Error State
- Module list fetch failure shows a retry.

### Blocked State
- Restricted-delivery eligibility blocked until required training is complete.

### Future Notes
- Certification (future, see Training Quiz Future).

## 17. Training Lesson

### Purpose
Deliver a single training lesson, including restricted delivery policy, 21+
verification, failed ID handling, return-to-store, and safety.

### Entry Point
From Compliance Training Home.

### Primary Action
- Complete the lesson and mark it done.

### Secondary Actions
- Revisit content.

### Required Backend Data
- Lesson content reference and completion state.

### Required Permissions
- None for screen entry.

### Backend Authority
- Records lesson completion as a training signal.

### Audit Events
- Lesson completion recorded by the backend.

### Empty State
- Lesson not started.

### Error State
- Content load failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Inline knowledge checks (future).

## 18. Training Quiz Future

### Purpose
Provide a future graded certification of policy mastery.

### Entry Point
From Compliance Training Home (future).

### Primary Action
- Take the certification quiz (future).

### Secondary Actions
- None.

### Required Backend Data
- Quiz definition and scoring (future).

### Required Permissions
- None for screen entry.

### Backend Authority
- Would own scoring and certification (future).

### Audit Events
- Certification result recorded by the backend (future).

### Empty State
- Reserved; not implemented in the MVP.

### Error State
- Reserved.

### Blocked State
- Reserved.

### Future Notes
- **Reserved for Dr.1.5; not required to implement in Dr.1.0.**

## 19. Policy Acknowledgment

### Purpose
Record the driver's acknowledgment of restricted-product, no-unattended-delivery,
and return-to-store policies.

### Entry Point
From the Activation Checklist.

### Primary Action
- Acknowledge each required policy.

### Secondary Actions
- Open the full policy text (Legal / Policies).

### Required Backend Data
- Required policy set and current acknowledgment state.

### Required Permissions
- None for screen entry.

### Backend Authority
- Records acknowledgments with audit; acks are an eligibility signal.

### Audit Events
- Policy acknowledged recorded by the backend.

### Empty State
- All policies pending acknowledgment.

### Error State
- Submission failure shows a retry.

### Blocked State
- Restricted-delivery eligibility blocked until required acks exist.

### Future Notes
- Versioned re-acknowledgment on policy updates.

## 20. Approval Pending

### Purpose
Show that the driver is awaiting backend/admin approval, and route rejected or
action-required states.

### Entry Point
From Splash/Home when the account is pending; after completing onboarding.

### Primary Action
- Refresh approval status.

### Secondary Actions
- Open any action-required step; contact support.

### Required Backend Data
- Approval state and any action-required reasons.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the approval decision; the app cannot self-advance to active.

### Audit Events
- None directly; approval decisions are backend-recorded.

### Empty State
- Pending indicator with no actions.

### Error State
- Status fetch failure shows a retry.

### Blocked State
- Operation is blocked until approval; rejected routes to remediation.

### Future Notes
- None.

## 21. Home / Driver Map

### Purpose
Present the driver's state and a map/state summary; the operational hub once
active.

### Entry Point
From Splash when active; after going online/offline.

### Primary Action
- View current state and proceed to Go Online / active delivery.

### Secondary Actions
- Open account, support, notifications.

### Required Backend Data
- Driver state, current assignment (if any), and online status.

### Required Permissions
- Location (for map and operation).

### Backend Authority
- Owns driver state; **the surface is order-scoped only — no global store-order
  browsing.**

### Audit Events
- None directly; online/offline and delivery actions emit their own events.

### Empty State
- Offline with no active delivery.

### Error State
- State fetch failure shows a retry; cached state may be shown read-only.

### Blocked State
- If ineligible, surfaces the Go Online Check blockers.

### Future Notes
- Demand/zone overlays (future).

## 22. Go Online Check

### Purpose
Gate the transition to online by verifying documents, vehicle, training, policy,
suspension status, permissions, and GPS/network.

### Entry Point
From Home when the driver attempts to go online.

### Primary Action
- Request to go online (subject to backend authorization).

### Secondary Actions
- Resolve a failed requirement (open documents/permissions).

### Required Backend Data
- Eligibility decision and the specific unmet requirement(s).

### Required Permissions
- Location (required); Notifications and Camera health surfaced.

### Backend Authority
- **Backend decides `can_go_online`** based on eligibility and reported device
  health.

### Audit Events
- Driver online event recorded by the backend on success.

### Empty State
- N/A (always evaluates current state).

### Error State
- Eligibility fetch failure shows a retry.

### Blocked State
- Lists each failed requirement and blocks online until resolved.

### Future Notes
- None.

## 23. Online Waiting State

### Purpose
Indicate the driver is online and waiting for an offer, with availability
controls.

### Entry Point
After a successful Go Online Check.

### Primary Action
- Remain available to receive offers.

### Secondary Actions
- Pause requests; go offline; view online time.

### Required Backend Data
- Online session state and online/active time.

### Required Permissions
- Location; Notifications (for offer delivery).

### Backend Authority
- Owns availability state and offer dispatch; the app reflects authorized state.

### Audit Events
- Pause/offline transitions recorded by the backend.

### Empty State
- Waiting indicator with no current offer.

### Error State
- Connectivity loss shows a degraded/offline indicator.

### Blocked State
- Forced offline if eligibility changes (e.g., new suspension).

### Future Notes
- Scheduled availability (future).

## 24. Delivery Offer

### Purpose
Present a time-boxed delivery offer for an existing order within the pre-accept
privacy boundary.

### Entry Point
Push notification / in-app while online and waiting.

### Primary Action
- Accept the offer.

### Secondary Actions
- Decline (to Decline Reason); open Delivery Offer Detail.

### Required Backend Data
- Store name/address, pickup distance, approximate dropoff zone, estimated
  duration, estimated earnings, restricted flag, ID-required flag, offer timer.

### Required Permissions
- Notifications (for delivery); Location (operational).

### Backend Authority
- Issues offers only to eligible drivers; owns the timer/expiry and validates
  accept/decline.

### Audit Events
- Delivery offered/accepted/declined recorded by the backend.

### Empty State
- N/A (only shown when an offer exists).

### Error State
- Expired/withdrawn offer message if the timer lapses.

### Blocked State
- **Pre-accept customer privacy boundary:** exact customer address/contact are
  withheld until acceptance.

### Future Notes
- Batch offers (future).

## 25. Delivery Offer Detail

### Purpose
Provide expanded offer details while preserving the pre-accept privacy boundary.

### Entry Point
From Delivery Offer.

### Primary Action
- Accept the offer.

### Secondary Actions
- Decline; return to the offer.

### Required Backend Data
- Expanded offer metadata (still zone-level for dropoff).

### Required Permissions
- None for screen entry.

### Backend Authority
- Same offer authority as Delivery Offer; still enforces the privacy boundary.

### Audit Events
- Accept/decline recorded by the backend.

### Empty State
- N/A.

### Error State
- Offer-expired message.

### Blocked State
- **Still preserves the pre-accept privacy boundary** — no exact customer
  address/contact pre-accept.

### Future Notes
- None.

## 26. Decline Reason

### Purpose
Capture a structured reason when a driver declines an offer.

### Entry Point
From Delivery Offer / Delivery Offer Detail on decline.

### Primary Action
- Submit the decline reason.

### Secondary Actions
- Cancel and return to the offer.

### Required Backend Data
- Allowed decline reasons.

### Required Permissions
- None for screen entry.

### Backend Authority
- Records the decline and reason; may trigger reassignment.

### Audit Events
- Delivery declined (with reason) recorded by the backend.

### Empty State
- Reason list.

### Error State
- Submission failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- None.

## 27. Assigned Deliveries

### Purpose
List the driver's offered and assigned deliveries — driver-scoped only.

### Entry Point
From Home; from a notification.

### Primary Action
- Open an assigned delivery (to Active Delivery Overview).

### Secondary Actions
- Respond to a pending offer.

### Required Backend Data
- The driver's offered/assigned deliveries and their states.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns assignment state; **only offered/assigned, driver-scoped deliveries are
  returned — no all-store order list.**

### Audit Events
- None directly; per-delivery actions emit their own events.

### Empty State
- No assigned deliveries.

### Error State
- List fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- None.

## 28. Active Delivery Overview

### Purpose
Show the current delivery's lifecycle state and the next valid action.

### Entry Point
From Assigned Deliveries; from a notification; after accepting an offer.

### Primary Action
- Proceed to the next lifecycle step (navigate, pickup, dropoff, verify, etc.).

### Secondary Actions
- Open support/safety; contact store/customer (masked).

### Required Backend Data
- Current delivery state, order summary, and the next allowed action.

### Required Permissions
- Location (operational).

### Backend Authority
- **Backend state controls the next action**; the app requests transitions and
  reflects authorized state, mapping to the existing order lifecycle.

### Audit Events
- None directly; each transition emits its own audit event.

### Empty State
- N/A (only shown for an active delivery).

### Error State
- State fetch failure shows cached state read-only with a retry.

### Blocked State
- Disallowed transitions are not offered; the screen shows why a step is locked.

### Future Notes
- None.

## 29. Navigate to Store

### Purpose
Route the driver to the pickup store via an external navigation app.

### Entry Point
From Active Delivery Overview (en route to store).

### Primary Action
- Launch external navigation to the store.

### Secondary Actions
- View ETA/distance; call store (masked).

### Required Backend Data
- Store location and any pickup notes.

### Required Permissions
- Location.

### Backend Authority
- Provides authoritative store location; does not own the external nav
  experience.

### Audit Events
- None directly; arrival emits its own event.

### Empty State
- N/A.

### Error State
- Missing location/permission prompts recovery.

### Blocked State
- Blocked without Location permission until granted.

### Future Notes
- Internal turn-by-turn (future); CarPlay / Android Auto (future).

## 30. Arrived at Store

### Purpose
Mark arrival at the pickup store and begin the pickup flow.

### Entry Point
From Navigate to Store.

### Primary Action
- Mark arrived at store.

### Secondary Actions
- Open pickup instructions; report a pickup issue.

### Required Backend Data
- Store location for arrival validation; order summary.

### Required Permissions
- Location.

### Backend Authority
- Accepts the arrival event; geofence/arrival validation is backend-evaluated.

### Audit Events
- Arrived at store recorded by the backend.

### Empty State
- N/A.

### Error State
- Arrival submission failure shows a retry.

### Blocked State
- Arrival may be gated by proximity (geofence validation future).

### Future Notes
- Geofence/arrival validation (future).

## 31. Store Pickup Instructions

### Purpose
Show the details needed to collect the correct order at the store.

### Entry Point
From Arrived at Store.

### Primary Action
- Proceed to the store handoff / pickup checklist.

### Secondary Actions
- View store instructions; report a pickup issue.

### Required Backend Data
- Order number, bag count, item count, restricted-product warning, and store
  instructions.

### Required Permissions
- None for screen entry.

### Backend Authority
- Provides the authoritative order/pickup details.

### Audit Events
- None directly.

### Empty State
- N/A.

### Error State
- Details fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- None.

## 32. Store Handoff PIN

### Purpose
Validate store-side release of the order to the driver via a store employee PIN.

### Entry Point
From Store Pickup Instructions / Pickup Checklist.

### Primary Action
- Submit the store employee PIN/confirmation.

### Secondary Actions
- Report a handoff problem (to Pickup Issue).

### Required Backend Data
- Handoff validation result.

### Required Permissions
- None for screen entry.

### Backend Authority
- **Validates the handoff; there is no pickup if handoff fails.** The store is
  accountable for release.

### Audit Events
- Store handoff started/confirmed recorded by the backend.

### Empty State
- PIN entry prompt.

### Error State
- Invalid PIN message; retry/escalation.

### Blocked State
- Pickup confirmation is blocked until the handoff validates.

### Future Notes
- QR / barcode handoff (future); manager override (future).

## 33. Pickup Checklist

### Purpose
Confirm the driver is collecting the correct order with the right contents.

### Entry Point
From Store Handoff PIN.

### Primary Action
- Complete the checklist (correct store, correct order, bag count matches,
  sealed/damage check, restricted-product acknowledgment).

### Secondary Actions
- Report a pickup issue.

### Required Backend Data
- Expected order/store identifiers and item/bag counts.

### Required Permissions
- None for screen entry.

### Backend Authority
- Uses the confirmed checklist as input to authorize pickup confirmation.

### Audit Events
- None directly; Confirm Pickup emits the pickup event.

### Empty State
- Unchecked checklist.

### Error State
- Mismatch (e.g., wrong order) routes to Pickup Issue.

### Blocked State
- Pickup cannot be confirmed until required checks (including restricted ack)
  pass.

### Future Notes
- Scan-based item verification (future).

## 34. Confirm Pickup

### Purpose
Confirm the order has been picked up and transition the delivery forward.

### Entry Point
From Pickup Checklist.

### Primary Action
- Submit pickup confirmation.

### Secondary Actions
- None.

### Required Backend Data
- Assignment, handoff, and checklist state.

### Required Permissions
- None for screen entry.

### Backend Authority
- **Backend confirms pickup**; **no pickup without assignment, handoff, and
  compliance** satisfied. Emits the pickup audit event.

### Audit Events
- Pickup confirmed recorded by the backend.

### Empty State
- N/A.

### Error State
- Confirmation failure shows a retry (idempotent).

### Blocked State
- Blocked if handoff/checklist/compliance are not satisfied.

### Future Notes
- None.

## 35. Pickup Issue

### Purpose
Report a problem at pickup (order not ready, wrong order, store closed, damaged
package) and escalate.

### Entry Point
From Store Pickup Instructions / Pickup Checklist / Store Handoff PIN.

### Primary Action
- Submit the pickup issue and reason.

### Secondary Actions
- Escalate to support.

### Required Backend Data
- Allowed pickup-issue reasons.

### Required Permissions
- None for screen entry.

### Backend Authority
- Records the issue and determines the next step (wait, reassign, support).

### Audit Events
- Pickup issue recorded by the backend.

### Empty State
- Reason list.

### Error State
- Submission failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- None.

## 36. Navigate to Customer

### Purpose
Route the driver to the customer after pickup.

### Entry Point
From Confirm Pickup / Active Delivery Overview (out for delivery).

### Primary Action
- Launch external navigation to the customer.

### Secondary Actions
- View ETA/distance; contact customer (masked).

### Required Backend Data
- Customer address (revealed only after accepted and picked up) and delivery
  notes.

### Required Permissions
- Location.

### Backend Authority
- Releases the exact customer address only post-pickup; provides any
  legal/restricted-zone constraints.

### Audit Events
- Out for delivery recorded by the backend.

### Empty State
- N/A.

### Error State
- Missing location/permission prompts recovery.

### Blocked State
- Customer address is not shown until accepted/picked-up.

### Future Notes
- Legal/restricted zone warnings (future); internal turn-by-turn (future).

## 37. Customer Delivery Instructions

### Purpose
Show delivery notes and restricted handoff requirements.

### Entry Point
From Navigate to Customer / Arrived at Customer.

### Primary Action
- Review instructions and proceed to arrival/verification.

### Secondary Actions
- Contact customer (masked).

### Required Backend Data
- Delivery notes and restricted-handoff flags.

### Required Permissions
- None for screen entry.

### Backend Authority
- Enforces restricted-handoff rules downstream; **no leave-at-door for restricted
  products.**

### Audit Events
- None directly.

### Empty State
- No special instructions.

### Error State
- Instructions fetch failure shows a retry.

### Blocked State
- Restricted orders display the no-unattended-delivery requirement.

### Future Notes
- None.

## 38. Contact Customer

### Purpose
Enable masked call/message with the customer.

### Entry Point
From Active Delivery / dropoff screens.

### Primary Action
- Place a masked call or send a message.

### Secondary Actions
- Use a quick message.

### Required Backend Data
- Masked contact channel and quick-message set.

### Required Permissions
- None for screen entry (uses system dialer via masked number).

### Backend Authority
- Owns number masking and the allowed message set; **personal phone numbers are
  not exposed** on either side.

### Audit Events
- Customer contacted recorded by the backend where audit-relevant.

### Empty State
- Contact options.

### Error State
- Call/message failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Message history (future).

## 39. Arrived at Customer

### Purpose
Confirm arrival at the customer and start the dropoff/verification flow.

### Entry Point
From Navigate to Customer.

### Primary Action
- Mark arrived at customer.

### Secondary Actions
- Contact customer; open delivery instructions.

### Required Backend Data
- Customer location for arrival validation.

### Required Permissions
- Location.

### Backend Authority
- Accepts the arrival event; geofence validation is backend-evaluated; **starts
  the dropoff/verification flow.**

### Audit Events
- Arrived at customer recorded by the backend.

### Empty State
- N/A.

### Error State
- Arrival submission failure shows a retry.

### Blocked State
- Arrival may be gated by proximity (geofence validation future).

### Future Notes
- Geofence/arrival validation (future).

## 40. Restricted Product Warning

### Purpose
Enforce restricted-delivery rules before verification: no unattended delivery,
customer present, valid ID, and 21+.

### Entry Point
From Arrived at Customer for restricted orders.

### Primary Action
- Acknowledge restricted requirements and proceed to verification.

### Secondary Actions
- Abort to failed delivery (unsafe/refusal).

### Required Backend Data
- Restricted-order flags and required checks.

### Required Permissions
- None for screen entry.

### Backend Authority
- Enforces that restricted orders require in-person, verified handoff; **failed
  verification means no delivery.**

### Audit Events
- None directly; verification start/outcome emits events.

### Empty State
- N/A (only for restricted orders).

### Error State
- Flag fetch failure shows a retry.

### Blocked State
- Blocks completion until verification passes.

### Future Notes
- None.

## 41. Age / ID Verification

### Purpose
Perform the 21+ manual verification checklist for restricted delivery.

### Entry Point
From Restricted Product Warning.

### Primary Action
- Complete the manual checklist: ID valid, not expired, age 21+, and the ID
  appears to match the person.

### Secondary Actions
- Mark verification failed (to ID Verification Failed).

### Required Backend Data
- Required verification fields for the order.

### Required Permissions
- None for screen entry.

### Backend Authority
- **Authorizes acceptance of the verification result**; completion is gated on
  it.

### Audit Events
- Verification started; age verification passed/failed recorded by the backend.

### Empty State
- Unchecked checklist.

### Error State
- Submission failure shows a retry.

### Blocked State
- **No raw ID image storage**; only redacted metadata is submitted. Completion is
  blocked until the result is accepted.

### Future Notes
- ID scan / OCR / barcode / liveness / vendor verification (future, legal-review
  dependent).

## 42. ID Verification Failed

### Purpose
Capture a failed verification and route to the failed-delivery / return path.

### Entry Point
From Age / ID Verification on failure.

### Primary Action
- Submit the verification failure reason.

### Secondary Actions
- Contact support; invoke safety if unsafe.

### Required Backend Data
- Allowed failure reasons.

### Required Permissions
- None for screen entry.

### Backend Authority
- Records the failure; **blocks delivery completion and triggers the failed
  delivery / return-to-store path.**

### Audit Events
- Age verification failed recorded by the backend.

### Empty State
- Reason list.

### Error State
- Submission failure shows a retry.

### Blocked State
- Completion remains blocked; return is required for restricted product.

### Future Notes
- None.

## 43. Proof of Delivery

### Purpose
Capture proof that the delivery occurred, with the verification result attached.

### Entry Point
From Age / ID Verification (passed), for the completion step.

### Primary Action
- Capture driver attestation and timestamp.

### Secondary Actions
- Add available proof elements (future: GPS, customer PIN).

### Required Backend Data
- Proof requirements for the order.

### Required Permissions
- None for screen entry.

### Backend Authority
- Validates the proof and binds the verification pass to it; **no proof, no
  delivered.**

### Audit Events
- Proof recorded by the backend.

### Empty State
- Attestation prompt.

### Error State
- Proof submission failure shows a retry (idempotent).

### Blocked State
- Completion blocked without a valid proof record.

### Future Notes
- Approximate GPS (future); customer PIN (future); signature/photo (future).

## 44. Customer PIN Future

### Purpose
Provide an optional/future customer-PIN proof element.

### Entry Point
From Proof of Delivery (future).

### Primary Action
- Enter the customer-provided PIN (future).

### Secondary Actions
- Skip where not required.

### Required Backend Data
- PIN validation (future).

### Required Permissions
- None for screen entry.

### Backend Authority
- Would validate the PIN as a proof element (future).

### Audit Events
- PIN proof recorded by the backend (future).

### Empty State
- Reserved.

### Error State
- Reserved.

### Blocked State
- Reserved.

### Future Notes
- **Optional/future; not required for the MVP unless later decided.**

## 45. Complete Delivery

### Purpose
Authorize and record delivery completion.

### Entry Point
From Proof of Delivery.

### Primary Action
- Submit completion for backend authorization.

### Secondary Actions
- None.

### Required Backend Data
- Proof and verification state for the order.

### Required Permissions
- Location (for completion proximity validation).

### Backend Authority
- **Authorizes completion**; for restricted orders it **requires proof and a
  verification pass**, plus proximity. Emits the delivery-completed audit event.

### Audit Events
- Delivery completed recorded by the backend.

### Empty State
- N/A.

### Error State
- Completion failure shows a retry (idempotent).

### Blocked State
- Blocked without proof/verification (restricted) or required proximity.

### Future Notes
- None.

## 46. Delivery Completed Summary

### Purpose
Confirm a completed delivery and record it to history.

### Entry Point
From Complete Delivery.

### Primary Action
- Acknowledge completion and return to Home.

### Secondary Actions
- View the delivery in history.

### Required Backend Data
- Completed delivery summary and estimated earnings.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the completion record and any earnings estimate.

### Audit Events
- None directly (completion already recorded).

### Empty State
- N/A.

### Error State
- Summary fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- **Estimated earnings visibility only** — no payout.

## 47. Failed Delivery Reason

### Purpose
Capture a structured failure reason when a delivery cannot be completed.

### Entry Point
From Active Delivery / dropoff / verification screens on failure.

### Primary Action
- Submit the failure reason: customer unavailable, no valid ID, expired ID,
  underage, ID mismatch, customer refused, unsafe location, wrong address, or
  app/vehicle/support issue.

### Secondary Actions
- Contact support; invoke safety.

### Required Backend Data
- Allowed failure reasons.

### Required Permissions
- None for screen entry.

### Backend Authority
- Records the failure and **decides whether return-to-store is required.**

### Audit Events
- Delivery failed recorded by the backend.

### Empty State
- Reason list.

### Error State
- Submission failure shows a retry.

### Blocked State
- For restricted product, completion stays blocked and return is required.

### Future Notes
- None.

## 48. Wait Timer

### Purpose
Manage a customer-unavailable wait period with contact attempts before failing.

### Entry Point
From Arrived at Customer when the customer is unavailable.

### Primary Action
- Start/observe the wait timer.

### Secondary Actions
- Contact customer (masked); escalate to support; proceed to failure when the
  timer elapses.

### Required Backend Data
- Wait policy/duration and contact-attempt log.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the wait policy and records contact attempts; gates the failure
  transition.

### Audit Events
- Customer contacted / wait events recorded by the backend.

### Empty State
- Timer running.

### Error State
- Timer/contact failure shows a retry.

### Blocked State
- Failure cannot be finalized before the policy wait elapses.

### Future Notes
- None.

## 49. Return Required

### Purpose
Signal that a failed restricted delivery must be returned to the store.

### Entry Point
From Failed Delivery Reason / ID Verification Failed for restricted product.

### Primary Action
- Begin the return flow (to Navigate Back to Store).

### Secondary Actions
- Contact support.

### Required Backend Data
- Return requirement and originating store.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the return requirement; **the driver cannot self-close** a restricted
  return.

### Audit Events
- Return required recorded by the backend.

### Empty State
- N/A.

### Error State
- State fetch failure shows a retry.

### Blocked State
- The delivery cannot be closed until the return is completed.

### Future Notes
- None.

## 50. Navigate Back to Store

### Purpose
Route the driver back to the originating store for the return.

### Entry Point
From Return Required.

### Primary Action
- Launch external navigation to the store.

### Secondary Actions
- View ETA/distance; call store (masked).

### Required Backend Data
- Originating store location.

### Required Permissions
- Location.

### Backend Authority
- Provides the store location; tracks return-audit state.

### Audit Events
- Return started recorded by the backend.

### Empty State
- N/A.

### Error State
- Missing location/permission prompts recovery.

### Blocked State
- Blocked without Location permission until granted.

### Future Notes
- None.

## 51. Store Return Confirmation

### Purpose
Validate the store's receipt of the returned product.

### Entry Point
From Navigate Back to Store (arrived).

### Primary Action
- Submit the store return PIN / employee confirmation.

### Secondary Actions
- Report a return problem to support.

### Required Backend Data
- Return validation result.

### Required Permissions
- None for screen entry.

### Backend Authority
- **Validates the return**; inventory review is backend-controlled; the driver
  cannot self-confirm.

### Audit Events
- Returned to store / store return confirmed recorded by the backend.

### Empty State
- PIN entry prompt.

### Error State
- Invalid PIN message; retry/escalation.

### Blocked State
- The return cannot close until the store confirms.

### Future Notes
- QR / barcode return (future).

## 52. Return Completed

### Purpose
Confirm the return is closed and the failed restricted-delivery path is resolved.

### Entry Point
From Store Return Confirmation.

### Primary Action
- Acknowledge return completion and return to Home.

### Secondary Actions
- View the delivery in history.

### Required Backend Data
- Closed return record.

### Required Permissions
- None for screen entry.

### Backend Authority
- Closes the return after store/backend confirmation; surfaces to store/admin.

### Audit Events
- None directly (return closure already recorded).

### Empty State
- N/A.

### Error State
- Summary fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- **Store/admin visibility** of the closed return.

## 53. Delivery History

### Purpose
List the driver's completed, failed, and returned deliveries — driver-scoped
only.

### Entry Point
From Home / Account.

### Primary Action
- Open a past delivery (to Delivery Detail History).

### Secondary Actions
- Filter by outcome/date.

### Required Backend Data
- The driver's historical deliveries and outcomes.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the history; **driver-scoped only.**

### Audit Events
- None directly.

### Empty State
- No past deliveries.

### Error State
- History fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- None.

## 54. Delivery Detail History

### Purpose
Show a past delivery's timeline and proof/verification status summary.

### Entry Point
From Delivery History.

### Primary Action
- Review the delivery timeline.

### Secondary Actions
- Open support about this delivery.

### Required Backend Data
- Delivery event timeline and proof/verification status (redacted metadata).

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the timeline; surfaces **redacted metadata only — no raw ID data.**

### Audit Events
- None directly (read surface).

### Empty State
- N/A.

### Error State
- Timeline fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- None.

## 55. Earnings Summary

### Purpose
Show estimated earnings and delivery counts — visibility only.

### Entry Point
From Home / Account.

### Primary Action
- Review estimated earnings and counts.

### Secondary Actions
- Open a support earnings question.

### Required Backend Data
- Estimated earnings and delivery counts.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the source data; **no payouts, cashout, Stripe, or payment movement.**

### Audit Events
- None directly.

### Empty State
- No earnings yet.

### Error State
- Earnings fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Daily/weekly rollups, tips, bonuses (future, post-payments).

## 56. Performance Dashboard

### Purpose
Show operational and compliance performance metrics.

### Entry Point
From Home / Account.

### Primary Action
- Review metrics: completed, failed, return rate, on-time, acceptance/decline/
  cancellation, proof completion, and compliance incidents.

### Secondary Actions
- Drill into a metric (future).

### Required Backend Data
- Backend-computed performance metrics.

### Required Permissions
- None for screen entry.

### Backend Authority
- Computes all metrics from authoritative events; the app does not compute them.

### Audit Events
- None directly.

### Empty State
- Insufficient data yet.

### Error State
- Metrics fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Restricted-success and audit-cleanliness detail (future).

## 57. Rewards / Status Future

### Purpose
Present a future driver status model (tiers and compliance badges).

### Entry Point
From Account (future).

### Primary Action
- View driver status / badges (future).

### Secondary Actions
- None.

### Required Backend Data
- Status computation (future).

### Required Permissions
- None for screen entry.

### Backend Authority
- Would own status and badge eligibility (future).

### Audit Events
- None directly.

### Empty State
- Reserved.

### Error State
- Reserved.

### Blocked State
- Reserved.

### Future Notes
- **Future driver status tiers, Compliance Trusted, and Restricted Delivery
  Certified — not MVP.**

## 58. Safety Toolkit

### Purpose
Provide always-reachable field-safety actions.

### Entry Point
From a persistent safety entry on delivery screens; from Home.

### Primary Action
- Open a safety action (emergency, unsafe location, accident, vehicle issue,
  cancel for safety, contact support).

### Secondary Actions
- Share location/route with oversight.

### Required Backend Data
- Safety action targets and support routing.

### Required Permissions
- Location (for location/route sharing).

### Backend Authority
- Records safety events and routes them to oversight; a safety cancel of a
  restricted order still requires return.

### Audit Events
- Safety issue reported recorded by the backend.

### Empty State
- Safety action menu.

### Error State
- Action failure shows a retry; emergency calling falls back to the dialer.

### Blocked State
- N/A (safety is always reachable).

### Future Notes
- Long-stop / route-deviation detection (future).

## 59. Emergency Help

### Purpose
Provide immediate emergency actions.

### Entry Point
From the Safety Toolkit.

### Primary Action
- Call 911.

### Secondary Actions
- Share location/active route with admin/support (future); escalate to support.

### Required Backend Data
- Support/oversight routing for shares.

### Required Permissions
- Location (for sharing).

### Backend Authority
- Records the emergency action and any share; routes to oversight.

### Audit Events
- Safety/emergency event recorded by the backend.

### Empty State
- Emergency action menu.

### Error State
- Calling falls back to the system dialer if in-app fails.

### Blocked State
- N/A.

### Future Notes
- Active-route sharing with admin/support (future).

## 60. Report Incident

### Purpose
File an auditable incident report.

### Entry Point
From the Safety Toolkit / Support.

### Primary Action
- Submit an incident: unsafe location, threatening customer, accident, vehicle
  issue, or app issue.

### Secondary Actions
- Attach context (future).

### Required Backend Data
- Allowed incident types.

### Required Permissions
- None for screen entry.

### Backend Authority
- Records the incident report and routes it to oversight.

### Audit Events
- Incident report recorded by the backend.

### Empty State
- Incident type list.

### Error State
- Submission failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Attachments (future).

## 61. Support Center

### Purpose
Provide help topics, contextual support, and a path to a support ticket.

### Entry Point
From Home / Account / any delivery screen.

### Primary Action
- Open a support topic or start a ticket.

### Secondary Actions
- View active-delivery contextual help.

### Required Backend Data
- Help topics and ticket entry points.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns ticket lifecycle and routing.

### Audit Events
- Support case opened recorded by the backend.

### Empty State
- Topic list.

### Error State
- Topics fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Support chat/call (future).

## 62. Support Category

### Purpose
Let the driver pick a support category.

### Entry Point
From the Support Center.

### Primary Action
- Select a category: pickup, store, customer, ID verification, safety, vehicle,
  app, earnings, or policy.

### Secondary Actions
- Search topics (future).

### Required Backend Data
- Category list.

### Required Permissions
- None for screen entry.

### Backend Authority
- Routes the category to the correct support flow.

### Audit Events
- None directly; ticket creation emits its own event.

### Empty State
- Category list.

### Error State
- Category fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- None.

## 63. Support Case Detail

### Purpose
Show the status of a support case.

### Entry Point
From the Support Center / a notification.

### Primary Action
- Review the case status.

### Secondary Actions
- Add a message (future); add an attachment (future).

### Required Backend Data
- Case status and history.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns case status and updates.

### Audit Events
- None directly (case already recorded).

### Empty State
- No updates yet.

### Error State
- Case fetch failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Messages and attachments (future).

## 64. Notifications Center

### Purpose
List the driver's notifications across offers, assignments, support, documents,
compliance, returns, device health, and policy updates.

### Entry Point
From Home; from a notification tap.

### Primary Action
- Open a notification and route to its screen.

### Secondary Actions
- Mark read; manage preferences.

### Required Backend Data
- Notification list and read state.

### Required Permissions
- Notifications (for delivery; the list is viewable without it).

### Backend Authority
- Owns notification triggers tied to authoritative state changes.

### Audit Events
- None directly.

### Empty State
- No notifications.

### Error State
- List fetch failure shows a retry.

### Blocked State
- **Compliance-critical notifications cannot be silenced** even if others are
  muted.

### Future Notes
- Grouping/filters (future).

## 65. Account

### Purpose
Provide an account overview: profile, documents, vehicle, performance summary,
and account status.

### Entry Point
From Home.

### Primary Action
- Navigate to a sub-area (profile, documents, vehicle, performance).

### Secondary Actions
- Open settings; open support.

### Required Backend Data
- Account summary and status.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns account-level state; status changes are backend-decided.

### Audit Events
- None directly.

### Empty State
- N/A.

### Error State
- Summary fetch failure shows a retry.

### Blocked State
- Reflects blocked/suspended account status.

### Future Notes
- None.

## 66. Settings

### Purpose
Entry point to app configuration sub-screens.

### Entry Point
From Account / Home.

### Primary Action
- Open a settings sub-screen (navigation, notifications, sounds, permissions,
  privacy, security, language, legal, diagnostics).

### Secondary Actions
- Logout; request account deletion (deferred, backend-gated).

### Required Backend Data
- Server-side preferences where applicable.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns account-level changes (e.g., deletion) and server-side preferences.

### Audit Events
- Logout / account actions recorded by the backend where relevant.

### Empty State
- N/A.

### Error State
- Preference fetch/save failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Account deletion process (deferred to Dr.1.5, backend-gated).

## 67. Navigation Preferences

### Purpose
Let the driver choose a default external navigation app.

### Entry Point
From Settings.

### Primary Action
- Select Apple Maps, Google Maps, or Waze.

### Secondary Actions
- None.

### Required Backend Data
- None (local preference) — may sync server-side (future).

### Required Permissions
- None for screen entry.

### Backend Authority
- None for the preference itself; nav targets remain backend-provided.

### Audit Events
- None directly.

### Empty State
- Default selection.

### Error State
- N/A.

### Blocked State
- N/A.

### Future Notes
- Server-synced preference (future).

## 68. Notification Preferences

### Purpose
Configure push notification categories.

### Entry Point
From Settings.

### Primary Action
- Toggle non-critical push categories.

### Secondary Actions
- Open App Permissions for system-level notification access.

### Required Backend Data
- Category preferences (where server-synced).

### Required Permissions
- Notifications (for delivery).

### Backend Authority
- Enforces that **critical delivery/compliance notifications remain enabled.**

### Audit Events
- None directly.

### Empty State
- Default categories.

### Error State
- Save failure shows a retry.

### Blocked State
- Critical categories are locked on.

### Future Notes
- None.

## 69. Sound Settings

### Purpose
Configure offer and notification sounds/vibration.

### Entry Point
From Settings.

### Primary Action
- Adjust offer sound/vibration and notification sounds.

### Secondary Actions
- Preview a sound.

### Required Backend Data
- None (local preference).

### Required Permissions
- None for screen entry.

### Backend Authority
- None for the preference itself.

### Audit Events
- None directly.

### Empty State
- Default settings.

### Error State
- N/A.

### Blocked State
- N/A.

### Future Notes
- None.

## 70. App Permissions

### Purpose
Show and manage the device permissions the app relies on, with a recovery path
to device settings.

### Entry Point
From Settings; from a blocked screen needing a permission.

### Primary Action
- Review and request location, camera, and notification permissions.

### Secondary Actions
- Open device settings to change a permission.

### Required Backend Data
- None for the permission states (device-owned); the backend consumes reported
  health.

### Required Permissions
- Location, Camera, Notifications; background location (future).

### Backend Authority
- Consumes reported permission health as an input to online eligibility; does not
  grant OS permissions.

### Audit Events
- None directly.

### Empty State
- Permission list with current states.

### Error State
- N/A.

### Blocked State
- Indicates which operations are blocked by a missing permission and offers a
  recovery path to device settings.

### Future Notes
- Background location (future).

## 71. Privacy

### Purpose
Explain data use and the privacy boundaries the app enforces.

### Entry Point
From Settings / Legal.

### Primary Action
- Review privacy disclosures.

### Secondary Actions
- Open the full privacy policy.

### Required Backend Data
- Privacy policy reference/version.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the authoritative privacy policy and data-handling rules.

### Audit Events
- None directly.

### Empty State
- N/A.

### Error State
- Content load failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- States **no personal phone exposure** and **no raw ID image storage in the
  MVP**; redaction by default.

## 72. Legal / Policies

### Purpose
Provide legal documents: terms, restricted-product delivery policy, community
guidelines, and the privacy policy.

### Entry Point
From Settings / Policy Acknowledgment / Privacy.

### Primary Action
- Open a legal document.

### Secondary Actions
- Re-acknowledge an updated policy (future).

### Required Backend Data
- Document references/versions.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns the authoritative policy documents and versions.

### Audit Events
- Policy re-acknowledgment recorded by the backend (future).

### Empty State
- N/A.

### Error State
- Content load failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Versioned re-acknowledgment (future).

## 73. App Diagnostics

### Purpose
Surface app/device health for support and troubleshooting.

### Entry Point
From Settings; from Report Bug.

### Primary Action
- Review app version, network, GPS, permissions, and device state.

### Secondary Actions
- Share diagnostics with a support case.

### Required Backend Data
- Minimum-version and remote-config references.

### Required Permissions
- None for screen entry.

### Backend Authority
- Owns minimum-version enforcement and remote config; consumes diagnostics.

### Audit Events
- None directly.

### Empty State
- N/A.

### Error State
- Diagnostics gathering failure shown inline.

### Blocked State
- N/A.

### Future Notes
- Advanced diagnostics (future).

## 74. Report Bug

### Purpose
Let a driver report an app issue.

### Entry Point
From Settings / App Diagnostics / Support.

### Primary Action
- Submit a bug report.

### Secondary Actions
- Attach diagnostics (future); link to a support case (future).

### Required Backend Data
- Bug-report intake target.

### Required Permissions
- None for screen entry.

### Backend Authority
- Receives and routes the bug report.

### Audit Events
- None directly; a linked support case emits its own event.

### Empty State
- Empty report form.

### Error State
- Submission failure shows a retry.

### Blocked State
- N/A.

### Future Notes
- Diagnostics attachment (future); support-case linkage (future).

## Screen Dependency Map

Major dependencies across the inventory:

- **Auth/session-dependent screens:** every screen except Splash depends on a
  validated session; Splash itself produces the session/routing decision.
- **Onboarding-dependent screens:** Activation Checklist, Profile Setup, Phone/
  Email Verification, Policy Acknowledgment, Approval Pending gate progress
  toward eligibility.
- **Document/vehicle/training-dependent screens:** Document Center/Status/
  Rejected Detail, Upload Document, Vehicle Profile/Add/Documents, Compliance
  Training Home/Lesson, and Policy Acknowledgment feed eligibility; Go Online
  Check depends on them.
- **Online-state-dependent screens:** Online Waiting State, Delivery Offer,
  Delivery Offer Detail depend on a successful Go Online Check.
- **Assignment-dependent screens:** Assigned Deliveries, Active Delivery
  Overview, and all pickup/dropoff screens depend on an accepted assignment.
- **Active-delivery-dependent screens:** Navigate to Store/Customer, Arrived
  screens, pickup and dropoff flows depend on an active delivery.
- **Verification/proof-dependent screens:** Restricted Product Warning, Age / ID
  Verification, ID Verification Failed, Proof of Delivery, and Complete Delivery
  are sequenced; completion depends on verification + proof.
- **Return-to-store-dependent screens:** Return Required, Navigate Back to Store,
  Store Return Confirmation, Return Completed depend on a failed restricted
  delivery.
- **Permission-dependent screens:** map/navigation/arrival/completion screens
  depend on Location; Upload Document and Vehicle Documents depend on Camera;
  offer/notification delivery depends on Notifications.
- **Future-only screens:** Training Quiz Future, Customer PIN Future, and Rewards
  / Status Future are reserved and not implemented in the MVP.

## Backend Authority Summary

Across all screens, the backend is authoritative for, at minimum:

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
- handoff validation,
- verification result acceptance,
- proof requirements,
- completion permission,
- failed delivery acceptance,
- return requirement,
- store return validation,
- inventory implications,
- audit events.

No screen asserts any of these; screens request and display, the backend decides
and records.

## Permission Summary

- **Location** — needed for map, navigation, arrival validation, and completion
  proximity. Screens: Home / Driver Map, Go Online Check, Online Waiting State,
  Active Delivery Overview, Navigate to Store/Customer, Arrived at Store/Customer,
  Complete Delivery, Navigate Back to Store, Safety Toolkit/Emergency Help. If
  missing: the driver cannot go online or progress location-gated steps; the app
  prompts a recovery path to device settings.
- **Camera** — needed to capture documents. Screens: Upload Document, Vehicle
  Documents. If missing: document capture is blocked until granted (gallery
  import is a future option).
- **Notifications** — needed to deliver offers and time-sensitive alerts.
  Screens: Delivery Offer, Online Waiting State, Notifications Center,
  Notification Preferences. If missing: offers/alerts may be missed; the app
  warns and routes to settings. Compliance-critical notifications remain enabled
  at the app level even when others are muted.
- **Background location (future)** — would support continuous location during
  active delivery. If missing: foreground-only operation; no MVP dependency.
- **Network connectivity** — required for all backend-authorized actions. If
  missing: screens enter offline/degraded states with retry; no state-changing
  action is asserted locally.
- **Optional photo/gallery (future)** — would allow importing an existing image
  for a document. If missing: capture-only.

## Compliance Screen Summary

The following screens are compliance-critical:

- **Activation Checklist** — gates progress toward eligibility for restricted
  delivery.
- **Document Center** — required authorization documents.
- **Upload Document** — sensitive document handling under the secure policy.
- **Document Status** — expired/required documents block online.
- **Vehicle Documents** — expired vehicle documents block online.
- **Compliance Training Home** — restricted-product training gate.
- **Policy Acknowledgment** — records restricted/no-unattended/return acks.
- **Go Online Check** — the eligibility gate to operate.
- **Delivery Offer** — restricted/ID-required flags and the pre-accept privacy
  boundary.
- **Store Handoff PIN** — accountable store release; no pickup if it fails.
- **Pickup Checklist** — restricted-product acknowledgment at pickup.
- **Restricted Product Warning** — enforces no-unattended, customer-present, 21+.
- **Age / ID Verification** — the 21+ gate; no raw ID images.
- **ID Verification Failed** — blocks completion; triggers return.
- **Proof of Delivery** — no proof, no delivered.
- **Complete Delivery** — completion requires proof + verification for restricted
  orders.
- **Failed Delivery Reason** — drives the return requirement.
- **Return Required** — failed restricted deliveries must return.
- **Store Return Confirmation** — accountable, store-confirmed return.
- **Delivery Detail History** — redacted metadata only; no raw ID data.
- **App Diagnostics** — supports audit/troubleshooting integrity.
- **Legal / Policies** — authoritative restricted-product and privacy policy.

Each is compliance-sensitive because it gates eligibility, enforces 21+/restricted
rules, protects sensitive data, or produces the audit record on which oversight
depends.

## MVP vs Future Screen Boundary

**MVP / early required screens:**

- auth (Splash, Login, Password Recovery),
- onboarding (Signup/Invitation, Activation Checklist, Profile Setup, Phone/Email
  Verification, Policy Acknowledgment, Approval Pending),
- documents (Document Center, Upload Document, Document Status, Rejected Document
  Detail),
- vehicle (Vehicle Profile, Add Vehicle, Vehicle Documents),
- training/policy (Compliance Training Home, Training Lesson, Policy
  Acknowledgment),
- home/online (Home / Driver Map, Go Online Check, Online Waiting State),
- offers (Delivery Offer, Delivery Offer Detail, Decline Reason, Assigned
  Deliveries),
- active delivery (Active Delivery Overview),
- pickup/handoff (Arrived at Store, Store Pickup Instructions, Store Handoff PIN,
  Pickup Checklist, Confirm Pickup, Pickup Issue),
- navigation handoff (Navigate to Store, Navigate to Customer),
- customer dropoff (Customer Delivery Instructions, Contact Customer, Arrived at
  Customer, Restricted Product Warning),
- manual ID verification (Age / ID Verification, ID Verification Failed),
- proof (Proof of Delivery, Complete Delivery, Delivery Completed Summary),
- failed delivery (Failed Delivery Reason, Wait Timer),
- return-to-store (Return Required, Navigate Back to Store, Store Return
  Confirmation, Return Completed),
- support/safety basics (Safety Toolkit, Emergency Help, Report Incident, Support
  Center, Support Category, Support Case Detail),
- notifications basics (Notifications Center),
- account/settings/permissions (Account, Settings, Navigation Preferences,
  Notification Preferences, Sound Settings, App Permissions, Privacy, Legal /
  Policies, App Diagnostics, Report Bug).

**Future / reserved screens and capabilities:**

- Training Quiz Future,
- Customer PIN Future,
- Rewards / Status Future,
- advanced earnings (Earnings Summary rollups, tips/bonuses),
- promotions/opportunities,
- ID scan / OCR / vendor verification,
- internal turn-by-turn,
- CarPlay / Android Auto,
- support chat/call center sophistication,
- advanced diagnostics,
- background location,
- advanced performance tiers.

Reserved screens are documented so later phases inherit a designed slot; they are
not implemented now.

## Store/Admin Visibility Summary

The following screen-driven events are what Store and Admin need later, surfaced
through the existing panels:

- store handoff,
- pickup confirmed,
- out for delivery,
- arrived at customer,
- verification failed,
- proof recorded,
- completed,
- failed delivery,
- return required,
- returned to store,
- support case,
- incident report.

**Driver App screens must emit or submit actions through backend events. No
screen should directly mutate Store/Admin UI state.** Oversight consumes the
backend's authoritative event stream.

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
