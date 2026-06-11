# Dr.1.0 Driver Safety, Support, Communication, and Notifications Architecture

## 1. Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.I — Safety, Support, Communication, Notifications
  Architecture
- **Deliverable path:** `docs/dr.1.0-driver-ops-support-safety.md`
- **Status:** Draft / Architecture
- **Scope:** Research/docs only
- **Implementation:** none — this document introduces no backend, frontend, or
  mobile implementation of any kind. It defines no endpoints, no database
  tables, no migrations, no schemas, no services, no emergency calling, no SMS,
  no chat, no push notifications, no phone masking, no support ticketing, no
  location/route sharing, and no notification delivery.

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/dr.1.0-driver-screen-inventory.md`,
`docs/dr.1.0-driver-user-flows.md`,
`docs/dr.1.0-driver-backend-gap-map.md`,
`docs/dr.1.0-driver-compliance-id-verification.md` (Dr.1.0.G),
`docs/dr.1.0-driver-proof-failure-return.md` (Dr.1.0.H),
`docs/dr.1.0-driver-live-map-navigation-surface.md` (Dr.1.0.H2),
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them. State
names, category names, and event names are **architectural candidates**,
finalized in later Dr.1.x phases. Nothing here is implemented.

## 2. Purpose

This document defines how the NubeRush Driver App should handle driver safety,
support, communication with customers and stores, and notifications. These
surfaces are critical because NubeRush delivers regulated smoke-shop and vape
products, and a driver in the field must be able to act on safety, reach
support, coordinate handoffs, and receive backend-authorized notifications
without ever overriding the compliance lifecycle locally.

Safety/support/communication/notification architecture matters for NubeRush
because of:

- **Restricted-product delivery** — regulated items raise the stakes for safe,
  accountable handling and lawful communication.
- **Driver safety** — drivers operate alone in the field and must have fast,
  clear safety and emergency access during active delivery.
- **Customer/store coordination** — pickups and dropoffs require lawful,
  privacy-safe communication to succeed.
- **Failed delivery handling** — support and communication underpin the
  Dr.1.0.H failed delivery flow without replacing it.
- **Return-to-store accountability** — safety and support events can trigger or
  affect the Dr.1.0.H return-to-store flow.
- **Compliance-sensitive communication** — messages must never expose sensitive
  ID data or imply unlawful completion.
- **Operational reliability** — notifications and support keep the active
  delivery moving and recoverable.
- **Support/admin visibility** — oversight observes safety and support outcomes
  through backend-authorized events, not raw surveillance.
- **Uber Driver / Uber Eats inspired operational depth** — the safety, support,
  and notification depth of a mature driver platform is studied (not copied) per
  the contract lock and adapted to NubeRush's regulated model.

## 3. Core Principles

- **Safety actions must be accessible during active delivery.** Emergency and
  safety access is never buried while a delivery is in progress.
- **Support access must be available from the active map/navigation surface.**
  Per Dr.1.0.H2, support and safety remain reachable from the live map.
- **The backend owns lifecycle outcomes.** Delivery, proof, compliance, return,
  inventory, Store, and Admin state are backend-owned.
- **Mobile initiates safety/support/communication actions but does not override
  state.** The app proposes; the backend authorizes.
- **Emergency actions must be clear and fast.** Emergency entry points are
  unambiguous and low-friction.
- **Communication must be privacy-safe.** Contact channels minimize exposure of
  personal data.
- **Phone masking is required for production communication.** Production calls
  and messages use masking or platform-mediated channels.
- **Sensitive ID/compliance details must not be exposed in customer messages.**
  No ID numbers, ID images, or compliance internals in customer-facing text.
- **Store/Admin visibility comes through backend events.** Oversight reads the
  backend event stream, not direct mobile state.
- **Support actions must be audited.** Safety and support steps emit
  compliance-grade audit events.
- **Safety cancellations require a backend-authorized state transition.** A
  driver request is proposed; the backend finalizes the state.
- **Notifications must never imply illegal delivery completion.** No
  notification authorizes or implies an unlawful handoff.
- **Compliance-critical notifications must be backend-driven.** Verification,
  proof, and return notifications originate from backend-authorized state.
- **Offline mode cannot locally complete restricted delivery or close
  safety/support cases.** Compliance-sensitive and case-closing transitions
  always wait for backend acceptance.

## 4. Relationship to Prior Dr.1.0 Documents

This document builds on the prior Dr.1.0 subphases and does not restate or
replace them.

- **Dr.1.0.A — Contract lock** (`docs/dr.1.0-driver-app-contract-lock.md`):
  defines scope and the docs-only nature of Dr.1.0. This subphase stays inside
  that boundary.
- **Dr.1.0.B — Uber feature adaptation**
  (`docs/dr.1.0-driver-feature-adaptation-matrix.md`): the safety/support depth
  adapts the studied operational structure to NubeRush.
- **Dr.1.0.C — Domain architecture**
  (`docs/dr.1.0-driver-domain-architecture.md`): communication, support, and
  safety states are views onto the backend-owned domain.
- **Dr.1.0.D — Screen inventory**
  (`docs/dr.1.0-driver-screen-inventory.md`): support center, safety, and
  communication surfaces map to the screen inventory.
- **Dr.1.0.E — User flows** (`docs/dr.1.0-driver-user-flows.md`): support and
  safety support the existing flows without changing them.
- **Dr.1.0.F — Backend gap map**
  (`docs/dr.1.0-driver-backend-gap-map.md`): the future backend capability map
  in Section 27 extends the gap map for support, safety, and notifications.
- **Dr.1.0.G — Compliance / ID verification**
  (`docs/dr.1.0-driver-compliance-id-verification.md`): no safety/support action
  bypasses the age/ID verification gate.
- **Dr.1.0.H — Proof / failed delivery / return-to-store**
  (`docs/dr.1.0-driver-proof-failure-return.md`): support and safety can affect
  the failure and return flows but do not replace them.
- **Dr.1.0.H2 — Live map / navigation surface**
  (`docs/dr.1.0-driver-live-map-navigation-surface.md`): safety/support must be
  reachable from the active map, consistent with that document.

How this subphase relates:

- **Support/safety must be reachable from the active map.** The live map keeps
  safety and support accessible during navigation (Dr.1.0.H2).
- **Support/safety may affect failed delivery and return-to-store flows.** A
  safety escalation can route an order to failure or return per Dr.1.0.H.
- **Communication supports customer/store coordination but does not replace
  proof or compliance.** Messaging never satisfies verification or proof.
- **Notifications reflect backend-authorized state.** They mirror backend state;
  they do not create it.
- **No safety/support action bypasses age/ID verification or proof
  requirements.** Restricted completion always depends on Dr.1.0.G/H.

## 5. Safety MVP Surface

The MVP safety surface is the set of safety elements available to a driver.
Each item below states Purpose, MVP/Future classification, Backend dependency,
Mobile responsibility, Privacy/safety notes, and Store/Admin visibility. Items
are architectural candidates.

### 5.1 Emergency button entry point

- **Purpose:** give the driver a fast, clear path to emergency/safety options.
- **MVP/Future:** MVP entry point; native emergency call is future.
- **Backend dependency:** safety event recording; routing.
- **Mobile responsibility:** present a prominent, always-reachable entry point.
- **Privacy/safety:** no hidden tracking; any sharing is explicit.
- **Store/Admin visibility:** safety events surface to Admin via backend events.

### 5.2 Unsafe location report

- **Purpose:** let the driver report an unsafe delivery location.
- **MVP/Future:** MVP.
- **Backend dependency:** safety incident recording.
- **Mobile responsibility:** capture report intent; submit to backend.
- **Privacy/safety:** minimal metadata; no continuous location.
- **Store/Admin visibility:** Admin; Store only if store-impacting.

### 5.3 Threatening customer report

- **Purpose:** report a threatening or hostile customer.
- **MVP/Future:** MVP.
- **Backend dependency:** safety incident recording.
- **Mobile responsibility:** capture report; route to support/escalation.
- **Privacy/safety:** privacy-safe references; no sensitive ID data.
- **Store/Admin visibility:** Admin; limited Store visibility.

### 5.4 Accident report

- **Purpose:** report a vehicle accident during delivery.
- **MVP/Future:** MVP.
- **Backend dependency:** safety incident recording.
- **Mobile responsibility:** capture report; surface support options.
- **Privacy/safety:** minimal metadata.
- **Store/Admin visibility:** Admin.

### 5.5 Vehicle issue report

- **Purpose:** report a vehicle breakdown or issue affecting delivery.
- **MVP/Future:** MVP.
- **Backend dependency:** safety/support recording.
- **Mobile responsibility:** capture report; surface support.
- **Privacy/safety:** minimal metadata.
- **Store/Admin visibility:** Admin; Store if delivery-impacting.

### 5.6 Cancel / escalate for safety

- **Purpose:** request a backend-authorized safety cancellation/escalation.
- **MVP/Future:** MVP (request); backend authorizes the final state.
- **Backend dependency:** lifecycle transition; route lock.
- **Mobile responsibility:** submit request; never self-finalize.
- **Privacy/safety:** driver not forced to complete an unsafe delivery.
- **Store/Admin visibility:** Admin; Store if return is required.

### 5.7 Contact support

- **Purpose:** reach support during an active delivery.
- **MVP/Future:** MVP.
- **Backend dependency:** support routing; case creation (future).
- **Mobile responsibility:** open support center / contact path.
- **Privacy/safety:** privacy-safe references only.
- **Store/Admin visibility:** Admin support queue.

### 5.8 Active map safety access

- **Purpose:** keep safety/support reachable from the live map (Dr.1.0.H2).
- **MVP/Future:** MVP.
- **Backend dependency:** safety/support routing.
- **Mobile responsibility:** persistent access during navigation.
- **Privacy/safety:** safety takes precedence over navigation UI.
- **Store/Admin visibility:** Admin via events.

### 5.9 Blocked delivery safety state

- **Purpose:** represent a delivery blocked for safety reasons.
- **MVP/Future:** MVP (backend-owned state).
- **Backend dependency:** lifecycle state; route lock.
- **Mobile responsibility:** present blocked state; restrict completion.
- **Privacy/safety:** no local override.
- **Store/Admin visibility:** Admin; Store if order-impacting.

### 5.10 Return safety exception

- **Purpose:** support a return triggered or affected by a safety event.
- **MVP/Future:** MVP (linked to Dr.1.0.H return).
- **Backend dependency:** return-required state; exception handling.
- **Mobile responsibility:** present return safety exception context.
- **Privacy/safety:** protects restricted inventory and driver safety.
- **Store/Admin visibility:** Store and Admin (return exception).

### 5.11 Excluded from the MVP safety surface

- **No automated emergency dispatch in the MVP.** No backend-placed emergency
  calls or automatic dispatch.
- **No hidden location sharing.** Any location sharing is explicit and future.
- **No local safety override of backend state.** Safety actions propose
  transitions; the backend authorizes them.

## 6. Emergency Button Architecture

- **Emergency button placement.** A prominent, consistent placement reachable
  during active delivery.
- **Access from active delivery.** Available throughout the active delivery
  lifecycle.
- **Access from the live map.** Reachable from the live map/navigation surface
  (Dr.1.0.H2).
- **Access from the support center.** Also reachable from the support center.
- **Confirmation vs immediate action considerations.** A short confirmation may
  guard against accidental taps while keeping genuine emergencies fast; the
  exact pattern is a future design/legal review item.
- **False tap prevention.** Guard against accidental activation without slowing
  a real emergency.
- **Future native emergency call option.** Native call handoff is future
  (Section 7).
- **Future support/admin alert.** Alerting support/admin on emergency is a
  future candidate.
- **Future location/route sharing.** Explicit sharing is future (Section 8).
- **Audit events.** Opening the emergency surface emits an audit event
  (`emergency_button_opened`).
- **Privacy boundaries.** No hidden tracking; any sharing is explicit.
- **No automatic delivery completion/cancellation without a backend state
  transition.** The emergency action never finalizes lifecycle state locally.
- **No emergency services integration in Dr.1.0.** No 911/dispatch integration
  is created here.

## 7. Call 911 Architecture

Call 911 is a future/native action or platform handoff. NubeRush does not place
emergency calls.

- **Driver-controlled action.** The driver initiates the call; the app never
  auto-dials emergency services.
- **Platform-native call behavior.** The action hands off to the device's native
  calling capability (future).
- **No backend placing emergency calls.** The backend never dials emergency
  services on the driver's behalf.
- **Optional future audit marker.** A marker that the emergency action was
  opened/tapped is a future candidate (no call content).
- **Privacy constraints.** No location or call content is captured by the action
  itself.
- **Support follow-up candidate.** A future support follow-up after an emergency
  is a candidate.
- **Delivery state remains backend-owned.** The emergency action does not change
  delivery lifecycle state locally.
- **No automatic customer/store notification unless future policy approves.** No
  party is auto-notified absent a reviewed policy.
- **App Store / Play Store policy sensitivity.** Native emergency calling must
  respect store policy.
- **Legal review dependency.** Emergency calling behavior requires legal review
  before implementation.

## 8. Location and Route Sharing Architecture

- **Share current location with support/admin as a future candidate.** Explicit,
  driver-initiated, future.
- **Share active delivery route with support/admin as a future candidate.**
  Scoped to the active delivery, future.
- **Share return-to-store route as a future candidate.** Scoped to the return
  leg, future.
- **Support-only or admin-only visibility boundaries.** Sharing is scoped to the
  appropriate oversight role.
- **No raw continuous location replay in the MVP.** No continuous trace storage
  or replay.
- **No unrestricted store surveillance.** Store does not receive a live trace.
- **Explicit driver transparency.** The driver is told what is shared and when.
- **Safety exception rules.** Any expanded sharing for safety is explicit and
  scoped.
- **Retention policy requirement.** A retention policy is required before any
  location/route history storage.
- **Backend authorization.** Sharing is backend-authorized and scoped.
- **Audit events.** Sharing actions are auditable.
- **Privacy/legal review dependency.** Location/route sharing requires
  privacy/legal review before implementation.

## 9. Safety Incident Report Types

The following are **candidate incident types**, finalized in a later Dr.1.x
phase. "Backend result" and "Delivery state impact" describe backend-authorized
outcomes the app proposes, never local finalization.

### unsafe_location

- **Meaning:** the delivery location is unsafe.
- **Driver action:** report unsafe location.
- **Immediate mobile UI outcome:** confirm report; surface support/escalation.
- **Backend result:** records incident; may trigger review/escalation.
- **Delivery state impact:** may route to blocked/failed/return per backend.
- **Support escalation requirement:** escalation candidate.
- **Return-to-store impact:** restricted order may require return.
- **Store/Admin visibility:** Admin; Store if store-impacting.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** minimal metadata; no continuous location.

### threatening_customer

- **Meaning:** the customer is threatening or hostile.
- **Driver action:** report threatening customer.
- **Immediate mobile UI outcome:** confirm report; surface escalation.
- **Backend result:** records incident; escalation candidate.
- **Delivery state impact:** may route to failed/return per backend.
- **Support escalation requirement:** escalation candidate.
- **Return-to-store impact:** restricted order may require return.
- **Store/Admin visibility:** Admin; limited Store.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** privacy-safe references; no sensitive ID data.

### accident

- **Meaning:** a vehicle accident occurred during delivery.
- **Driver action:** report accident.
- **Immediate mobile UI outcome:** confirm report; surface support.
- **Backend result:** records incident; support follow-up candidate.
- **Delivery state impact:** likely blocked/failed pending support.
- **Support escalation requirement:** escalation candidate.
- **Return-to-store impact:** may require return depending on outcome.
- **Store/Admin visibility:** Admin.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** minimal metadata.

### vehicle_issue

- **Meaning:** a vehicle breakdown/issue affects delivery.
- **Driver action:** report vehicle issue.
- **Immediate mobile UI outcome:** confirm report; surface support.
- **Backend result:** records incident; support follow-up candidate.
- **Delivery state impact:** may route to delayed/failed/return.
- **Support escalation requirement:** support candidate.
- **Return-to-store impact:** may require return.
- **Store/Admin visibility:** Admin; Store if delivery-impacting.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** minimal metadata.

### robbery_or_attempted_theft

- **Meaning:** robbery or attempted theft of the driver or order.
- **Driver action:** report robbery/attempted theft.
- **Immediate mobile UI outcome:** confirm report; surface emergency/support.
- **Backend result:** records incident; priority escalation candidate.
- **Delivery state impact:** likely blocked/failed; return per backend.
- **Support escalation requirement:** priority escalation.
- **Return-to-store impact:** restricted inventory accountability applies.
- **Store/Admin visibility:** Admin (priority).
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** minimal metadata; emergency exception may apply.

### harassment

- **Meaning:** the driver is being harassed.
- **Driver action:** report harassment.
- **Immediate mobile UI outcome:** confirm report; surface escalation.
- **Backend result:** records incident; escalation candidate.
- **Delivery state impact:** may route to failed/return per backend.
- **Support escalation requirement:** escalation candidate.
- **Return-to-store impact:** restricted order may require return.
- **Store/Admin visibility:** Admin; limited Store.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** privacy-safe references.

### medical_issue

- **Meaning:** a medical issue affects the driver.
- **Driver action:** report medical issue.
- **Immediate mobile UI outcome:** confirm report; surface emergency/support.
- **Backend result:** records incident; support follow-up candidate.
- **Delivery state impact:** likely blocked/failed pending support.
- **Support escalation requirement:** escalation candidate.
- **Return-to-store impact:** may require return.
- **Store/Admin visibility:** Admin.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** health data is sensitive; minimize and avoid retention.

### police_or_authority_interaction

- **Meaning:** an interaction with police or another authority occurs.
- **Driver action:** report authority interaction.
- **Immediate mobile UI outcome:** confirm report; surface support.
- **Backend result:** records incident; legal/support review candidate.
- **Delivery state impact:** may route to blocked/failed/return.
- **Support escalation requirement:** escalation candidate.
- **Return-to-store impact:** restricted order may require return.
- **Store/Admin visibility:** Admin.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** sensitive; minimal metadata; legal review.

### road_hazard

- **Meaning:** a road hazard affects the route/delivery.
- **Driver action:** report road hazard.
- **Immediate mobile UI outcome:** confirm report; continue or reroute.
- **Backend result:** records incident; operational signal.
- **Delivery state impact:** usually none directly; possible delay.
- **Support escalation requirement:** usually none.
- **Return-to-store impact:** usually none.
- **Store/Admin visibility:** Admin (operational).
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** minimal metadata.

### app_blocking_safety_flow

- **Meaning:** an app/technical issue blocks a safety flow.
- **Driver action:** report app-blocking safety issue.
- **Immediate mobile UI outcome:** surface alternative support/safety path.
- **Backend result:** records incident; technical escalation candidate.
- **Delivery state impact:** safety must remain reachable by alternative path.
- **Support escalation requirement:** escalation candidate.
- **Return-to-store impact:** depends on outcome.
- **Store/Admin visibility:** Admin (technical/safety).
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** minimal metadata.

### other_safety_issue

- **Meaning:** a safety issue not otherwise categorized.
- **Driver action:** report other safety issue.
- **Immediate mobile UI outcome:** confirm report; surface support.
- **Backend result:** records incident; triage candidate.
- **Delivery state impact:** per backend triage.
- **Support escalation requirement:** triage candidate.
- **Return-to-store impact:** per backend.
- **Store/Admin visibility:** Admin.
- **Audit event:** `safety_report_submitted`.
- **Privacy notes:** minimal metadata.

## 10. Cancel / Escalate for Safety

- **The driver can request safety cancellation/escalation.** The app submits a
  request; it does not self-cancel.
- **The backend authorizes the final state.** Cancellation/escalation outcomes
  are backend-owned.
- **Support may lock the route/state.** A safety escalation can lock the route
  (consistent with `support_review_route_locked` in Dr.1.0.H2).
- **Restricted product may require return-to-store.** A safety cancellation of a
  restricted order routes to the Dr.1.0.H return flow.
- **The driver should not be forced to complete an unsafe delivery.** Safety
  takes precedence over completion.
- **Proof cannot be forced in an unsafe state.** The Dr.1.0.H proof flow is not
  demanded when the driver is unsafe.
- **Customer/store communication boundaries.** Communication during a safety
  event stays privacy-safe and policy-bounded.
- **Store/Admin visibility.** Visible to Admin; Store when return is required.
- **Audit events.** `safety_escalation_opened`, `safety_escalation_resolved`.
- **Offline behavior.** A safety request may queue offline, but final
  cancellation requires backend acceptance.
- **No local final cancellation without backend acceptance.** The app never
  finalizes a safety cancellation locally.

## 11. Support Center Architecture

- **Support center entry points.** Reachable from active delivery, the live map,
  and standard navigation.
- **Active delivery support.** Help during an in-progress delivery.
- **Order issue support.** Help with an order problem.
- **Pickup issue support.** Help with a store pickup problem.
- **Customer issue support.** Help with a customer problem.
- **Safety issue support.** Routes into the safety surface (Sections 5–10).
- **Return issue support.** Help with the Dr.1.0.H return flow.
- **App/technical issue support.** Help with app or connectivity problems.
- **Account/profile issue support.** Help with account/profile problems.
- **Earnings visibility issue support.** Help with earnings visibility problems
  (visibility only; no payout logic here).
- **Compliance verification issue support.** Help with Dr.1.0.G verification
  problems (no compliance decision made in the app).
- **Support case creation as a future backend capability.** Case creation is a
  future backend capability, not implemented here.
- **Support case status as a future capability.** Case status tracking is
  future.
- **No implementation in Dr.1.0.** This is architecture only.

## 12. Support Categories

The following are **candidate support categories**, finalized in a later Dr.1.x
phase.

### safety_emergency

- **Purpose:** emergency or imminent safety threat.
- **Priority:** highest.
- **Driver-facing examples:** robbery, threat, accident, medical.
- **Backend/support dependency:** priority routing; escalation.
- **Delivery state impact:** likely blocked/failed/return per backend.
- **Store/Admin visibility:** Admin (priority).
- **Audit implication:** safety events.
- **MVP/Future:** MVP (access) / future (full workflow).

### unsafe_delivery

- **Purpose:** unsafe delivery condition short of emergency.
- **Priority:** high.
- **Driver-facing examples:** unsafe location, harassment.
- **Backend/support dependency:** escalation routing.
- **Delivery state impact:** may route to failed/return.
- **Store/Admin visibility:** Admin; limited Store.
- **Audit implication:** safety events.
- **MVP/Future:** MVP (access) / future (workflow).

### customer_problem

- **Purpose:** customer-related issue.
- **Priority:** medium-high.
- **Driver-facing examples:** unreachable, wrong address, refusal.
- **Backend/support dependency:** support routing.
- **Delivery state impact:** may route to failed/return.
- **Store/Admin visibility:** Admin; limited Store.
- **Audit implication:** support events.
- **MVP/Future:** MVP (access) / future (workflow).

### store_problem

- **Purpose:** store-related issue.
- **Priority:** medium-high.
- **Driver-facing examples:** store closed, unresponsive.
- **Backend/support dependency:** support routing.
- **Delivery state impact:** may delay pickup.
- **Store/Admin visibility:** Store and Admin.
- **Audit implication:** support events.
- **MVP/Future:** MVP (access) / future (workflow).

### pickup_problem

- **Purpose:** pickup handoff issue.
- **Priority:** medium-high.
- **Driver-facing examples:** missing item, damaged item.
- **Backend/support dependency:** support routing; Dr.1.0.H linkage.
- **Delivery state impact:** may block pickup.
- **Store/Admin visibility:** Store and Admin.
- **Audit implication:** support events.
- **MVP/Future:** MVP (access) / future (workflow).

### return_problem

- **Purpose:** return-to-store issue.
- **Priority:** high.
- **Driver-facing examples:** store will not accept return.
- **Backend/support dependency:** Dr.1.0.H return linkage; exception handling.
- **Delivery state impact:** return exception.
- **Store/Admin visibility:** Store and Admin.
- **Audit implication:** return support events.
- **MVP/Future:** MVP (access) / future (workflow).

### compliance_verification_problem

- **Purpose:** age/ID verification issue (Dr.1.0.G).
- **Priority:** high.
- **Driver-facing examples:** verification tool failure, dispute.
- **Backend/support dependency:** compliance/support routing.
- **Delivery state impact:** completion blocked until resolved.
- **Store/Admin visibility:** Admin; no sensitive ID data.
- **Audit implication:** compliance/support events.
- **MVP/Future:** MVP (access) / future (workflow).

### proof_of_delivery_problem

- **Purpose:** proof issue (Dr.1.0.H).
- **Priority:** high.
- **Driver-facing examples:** proof capture failure.
- **Backend/support dependency:** proof/support routing.
- **Delivery state impact:** completion blocked until resolved.
- **Store/Admin visibility:** Admin.
- **Audit implication:** proof/support events.
- **MVP/Future:** MVP (access) / future (workflow).

### app_or_network_problem

- **Purpose:** app or connectivity issue.
- **Priority:** medium.
- **Driver-facing examples:** crash, offline, stuck state.
- **Backend/support dependency:** technical support routing.
- **Delivery state impact:** may require reconciliation.
- **Store/Admin visibility:** Admin (technical).
- **Audit implication:** support events.
- **MVP/Future:** MVP (access) / future (workflow).

### vehicle_problem

- **Purpose:** vehicle issue affecting delivery.
- **Priority:** medium-high.
- **Driver-facing examples:** breakdown, flat tire.
- **Backend/support dependency:** support routing.
- **Delivery state impact:** may route to delayed/failed/return.
- **Store/Admin visibility:** Admin; Store if delivery-impacting.
- **Audit implication:** support events.
- **MVP/Future:** MVP (access) / future (workflow).

### account_profile_problem

- **Purpose:** account/profile issue.
- **Priority:** low-medium.
- **Driver-facing examples:** profile data, access.
- **Backend/support dependency:** account support routing.
- **Delivery state impact:** none directly.
- **Store/Admin visibility:** Admin.
- **Audit implication:** support events.
- **MVP/Future:** future (workflow) / MVP (access).

### earnings_visibility_problem

- **Purpose:** earnings visibility issue (visibility only).
- **Priority:** low-medium.
- **Driver-facing examples:** earnings display discrepancy.
- **Backend/support dependency:** support routing; no payout logic here.
- **Delivery state impact:** none.
- **Store/Admin visibility:** Admin.
- **Audit implication:** support events.
- **MVP/Future:** future.

### general_support

- **Purpose:** uncategorized support request.
- **Priority:** low.
- **Driver-facing examples:** general question.
- **Backend/support dependency:** triage routing.
- **Delivery state impact:** none directly.
- **Store/Admin visibility:** Admin.
- **Audit implication:** support events.
- **MVP/Future:** MVP (access) / future (workflow).

## 13. Customer Communication Architecture

- **Call customer.** Available where backend policy permits, via masked/mediated
  channel.
- **Message customer.** Available where permitted, via masked/mediated channel.
- **Masked phone requirement.** Production calls/messages use masking or
  platform-mediated channels (Section 15).
- **Quick messages as an MVP/future candidate.** Templates may be MVP for
  low-risk messages; richer sets are future (Section 16).
- **Pre-arrival message.** "On my way" style message.
- **Arrival message.** "I have arrived" style message.
- **No-show message.** Message when the customer is not present.
- **Verification boundary message.** A message indicating ID verification is
  required, without exposing compliance internals.
- **Failed delivery message.** A message consistent with the Dr.1.0.H failure
  flow.
- **Return-required message boundaries.** Messaging about a return stays within
  policy and does not promise outcomes.
- **Unsafe situation communication boundary.** Communication during a safety
  event is constrained and may be suspended.
- **No sensitive ID/compliance details in customer messages.** No ID numbers, ID
  images, or compliance internals.
- **No personal driver/customer phone exposure.** Personal numbers are not
  exposed.
- **Backend event visibility.** Contact attempts surface via backend events.
- **Audit metadata only.** Audit records contact attempt metadata, not content.

## 14. Store Communication Architecture

- **Call store.** Available where permitted.
- **Message store.** Available where permitted.
- **Masked or platform-mediated communication as a future candidate.** Masking
  for store communication is a future candidate where avoidable exposure exists.
- **Pickup issue communication.** Coordinate a pickup problem.
- **Missing item communication.** Coordinate a missing item.
- **Damaged item communication.** Coordinate a damaged item.
- **Store closed issue.** Coordinate when the store is closed.
- **Return coordination.** Coordinate a Dr.1.0.H return.
- **Return confirmation support.** Support the store's return confirmation step.
- **Compliance issue coordination boundaries.** Compliance coordination stays
  within policy and does not expose sensitive data.
- **Backend event visibility.** Store contact attempts surface via backend
  events.
- **Audit metadata.** Audit records metadata, not content.
- **No direct mobile mutation of store state.** The app never writes store
  state.

## 15. Masked Phone Number Architecture

- **Production communication should use masked numbers or platform-mediated
  calling/messaging.** Direct personal-number contact is avoided in production.
- **Driver and customer personal numbers should not be exposed.** Both sides are
  masked.
- **Driver and store personal numbers should not be exposed where avoidable.**
  Masking applies to store communication where avoidable exposure exists.
- **Call bridge/SMS relay as a future capability.** A masking provider/relay is
  a future backend capability, not implemented here.
- **Audit call attempt metadata, not call content.** No call content is
  recorded.
- **Privacy and retention boundaries.** Minimal metadata; retention policy
  required.
- **Abuse prevention.** Masking and policy prevent contact abuse.
- **Blocked communication after delivery closure.** Contact is blocked once the
  delivery is closed.
- **Emergency exception considerations.** Emergency scenarios may warrant
  exceptions, subject to review.
- **Legal/vendor review required.** A masking vendor and approach require
  legal/vendor review.
- **No masking implementation in Dr.1.0.** Architecture only.

## 16. Quick Messages Architecture

The following are **candidate quick message templates**, finalized in a later
Dr.1.x phase. Templates carry no sensitive ID or compliance internals.

| Template | Audience | Use case | Compliance risk | Backend dependency | MVP/Future | Notes |
|---|---|---|---|---|---|---|
| On my way to store | Store | En route to pickup | Low | Contact policy | MVP candidate | Operational only |
| Picked up and heading to you | Customer | After confirmed pickup | Low | Pickup confirmed | MVP candidate | No compliance detail |
| I have arrived | Customer | At customer location | Low | Contact policy | MVP candidate | Operational only |
| Please meet me outside | Customer | Handoff coordination | Low | Contact policy | MVP candidate | Operational only |
| ID verification required | Customer | Restricted handoff | Medium | Dr.1.0.G state | Future (reviewed) | No ID internals |
| I cannot leave restricted products unattended | Customer | Compliance boundary | Medium | Dr.1.0.G/H state | Future (reviewed) | Policy statement only |
| I will wait for a few minutes | Customer | Brief wait | Low | Contact policy | MVP candidate | Operational only |
| I need to return this order to the store | Customer | Return-required | Medium | Dr.1.0.H state | Future (reviewed) | No outcome promise |
| Please contact support | Customer/Store | Redirect to support | Low | Support routing | MVP candidate | Operational only |
| Store pickup issue | Store | Pickup problem | Low | Support routing | MVP candidate | Operational only |
| Store return coordination | Store | Return handoff | Medium | Dr.1.0.H state | Future (reviewed) | Coordination only |
| Safety/support escalation | Support | Escalate safety/support | High | Safety/support routing | MVP (access) / Future (workflow) | No sensitive detail |

## 17. Notifications Architecture

The following are **candidate notification types**, finalized in a later Dr.1.x
phase. Notifications reflect backend-authorized state and never authorize
completion.

### new delivery assignment

- **Trigger:** backend assigns a delivery.
- **Recipient:** driver.
- **Priority:** active delivery.
- **Backend dependency:** assignment state.
- **Mobile behavior:** open assignment context.
- **Store/Admin visibility:** Store sees assignment; Admin via events.
- **Compliance notes:** no completion implied.
- **MVP/Future:** MVP.

### assignment updated

- **Trigger:** assignment changes.
- **Recipient:** driver.
- **Priority:** active delivery.
- **Backend dependency:** assignment state.
- **Mobile behavior:** refresh assignment.
- **Store/Admin visibility:** via events.
- **Compliance notes:** none.
- **MVP/Future:** MVP.

### pickup reminder

- **Trigger:** approaching/overdue pickup.
- **Recipient:** driver.
- **Priority:** operational reminder.
- **Backend dependency:** route/pickup state.
- **Mobile behavior:** surface pickup step.
- **Store/Admin visibility:** Store sees pickup status.
- **Compliance notes:** none.
- **MVP/Future:** MVP.

### pickup issue

- **Trigger:** pickup problem detected/reported.
- **Recipient:** driver.
- **Priority:** active delivery.
- **Backend dependency:** pickup/support state.
- **Mobile behavior:** surface pickup issue path.
- **Store/Admin visibility:** Store and Admin.
- **Compliance notes:** none.
- **MVP/Future:** MVP.

### customer route started

- **Trigger:** customer leg starts after confirmed pickup.
- **Recipient:** driver.
- **Priority:** active delivery.
- **Backend dependency:** route state (Dr.1.0.H2).
- **Mobile behavior:** surface customer route.
- **Store/Admin visibility:** limited Store status.
- **Compliance notes:** none.
- **MVP/Future:** MVP.

### arrival reminder

- **Trigger:** approaching customer.
- **Recipient:** driver.
- **Priority:** operational reminder.
- **Backend dependency:** route state.
- **Mobile behavior:** surface arrival step.
- **Store/Admin visibility:** via events.
- **Compliance notes:** none.
- **MVP/Future:** MVP.

### ID verification required

- **Trigger:** restricted completion requires verification (Dr.1.0.G).
- **Recipient:** driver.
- **Priority:** compliance-critical.
- **Backend dependency:** verification state.
- **Mobile behavior:** open verification flow; completion blocked.
- **Store/Admin visibility:** Admin; no sensitive ID data.
- **Compliance notes:** does not authorize completion alone.
- **MVP/Future:** MVP.

### proof required

- **Trigger:** completion requires proof (Dr.1.0.H).
- **Recipient:** driver.
- **Priority:** compliance-critical.
- **Backend dependency:** proof state.
- **Mobile behavior:** open proof flow; completion blocked.
- **Store/Admin visibility:** Admin.
- **Compliance notes:** does not authorize completion alone.
- **MVP/Future:** MVP.

### failed delivery action required

- **Trigger:** failure handling required (Dr.1.0.H).
- **Recipient:** driver.
- **Priority:** compliance-critical / active delivery.
- **Backend dependency:** failure state.
- **Mobile behavior:** open failure flow.
- **Store/Admin visibility:** Store and Admin.
- **Compliance notes:** restricted failure may require return.
- **MVP/Future:** MVP.

### return-to-store required

- **Trigger:** return required (Dr.1.0.H).
- **Recipient:** driver.
- **Priority:** compliance-critical.
- **Backend dependency:** return state.
- **Mobile behavior:** open return route (Dr.1.0.H2).
- **Store/Admin visibility:** Store and Admin.
- **Compliance notes:** protects restricted inventory.
- **MVP/Future:** MVP.

### return confirmation pending

- **Trigger:** awaiting store return confirmation.
- **Recipient:** driver.
- **Priority:** active delivery.
- **Backend dependency:** return handoff state.
- **Mobile behavior:** surface return handoff step.
- **Store/Admin visibility:** Store and Admin.
- **Compliance notes:** store confirmation required.
- **MVP/Future:** MVP.

### support case updated

- **Trigger:** support case status changes.
- **Recipient:** driver.
- **Priority:** support update.
- **Backend dependency:** support case state.
- **Mobile behavior:** open support case.
- **Store/Admin visibility:** Admin queue.
- **Compliance notes:** none.
- **MVP/Future:** future (case workflow) / MVP (access).

### safety alert

- **Trigger:** backend-issued safety alert.
- **Recipient:** driver.
- **Priority:** emergency/safety.
- **Backend dependency:** safety state.
- **Mobile behavior:** surface safety information/action.
- **Store/Admin visibility:** Admin (priority).
- **Compliance notes:** safety precedence.
- **MVP/Future:** MVP (access) / future (full alerts).

### network/offline warning

- **Trigger:** connectivity degraded/lost.
- **Recipient:** driver.
- **Priority:** active delivery.
- **Backend dependency:** none for local warning; reconciliation on reconnect.
- **Mobile behavior:** surface offline banner (Dr.1.0.H2).
- **Store/Admin visibility:** stuck/offline signal.
- **Compliance notes:** restricted completion blocked offline.
- **MVP/Future:** MVP.

### app permission warning

- **Trigger:** required permission missing (e.g. location).
- **Recipient:** driver.
- **Priority:** active delivery.
- **Backend dependency:** permission state (future candidate).
- **Mobile behavior:** surface permission recovery (Dr.1.0.H2).
- **Store/Admin visibility:** Admin signal.
- **Compliance notes:** none.
- **MVP/Future:** MVP.

### schedule/availability future

- **Trigger:** schedule/availability change.
- **Recipient:** driver.
- **Priority:** informational/future.
- **Backend dependency:** scheduling (future).
- **Mobile behavior:** surface schedule context.
- **Store/Admin visibility:** Admin (future).
- **Compliance notes:** none.
- **MVP/Future:** future.

### earnings visibility summary future

- **Trigger:** earnings visibility summary available.
- **Recipient:** driver.
- **Priority:** informational/future.
- **Backend dependency:** earnings visibility (future; no payout logic here).
- **Mobile behavior:** surface earnings visibility.
- **Store/Admin visibility:** Admin (future).
- **Compliance notes:** none.
- **MVP/Future:** future.

## 18. Compliance-Critical Notification Behavior

- **Compliance notifications must be backend-driven.** They originate from
  backend-authorized state, never from local logic.
- **ID verification required notification.** Routes to the Dr.1.0.G flow;
  completion stays blocked until verification passes.
- **Failed verification notification.** Reflects a backend-recorded failure and
  routes to failure/return per Dr.1.0.H.
- **Proof blocked notification.** Reflects a backend proof requirement;
  completion stays blocked.
- **Return-to-store required notification.** Routes to the Dr.1.0.H return flow.
- **Restricted product cannot be left unattended.** Notifications reinforce, and
  never contradict, the no-unattended-delivery rule.
- **Customer messages must not reveal sensitive ID details.** No ID numbers,
  images, or compliance internals in any customer-facing notification.
- **Notifications cannot authorize completion alone.** Tapping a notification
  never completes a delivery.
- **A push notification tap opens the appropriate flow, but the backend
  validates state.** Navigation is local; authorization is backend-owned.
- **Stale notification handling.** Stale notifications are reconciled against
  current backend state and may be discarded (`notification_stale_discarded`).
- **Offline notification behavior.** Notifications opened offline do not finalize
  compliance-sensitive state; they await backend validation.
- **Audit events.** `compliance_notification_created`, plus notification
  lifecycle events.

## 19. Notification Priority and Delivery Rules

The following are **candidate priorities**, finalized in a later Dr.1.x phase.

### emergency/safety

- **Meaning:** safety-critical notifications.
- **Examples:** safety alert, emergency follow-up.
- **Delivery behavior:** delivered promptly; not suppressed.
- **Suppression rules:** not suppressed by quiet hours.
- **Retry behavior:** aggressive retry candidate.
- **Store/Admin visibility:** Admin (priority).
- **Audit requirement:** required.

### compliance-critical

- **Meaning:** verification/proof/return notifications.
- **Examples:** ID verification required, proof required, return required.
- **Delivery behavior:** delivered reliably; not casually suppressed.
- **Suppression rules:** limited suppression; never dropped silently.
- **Retry behavior:** retry candidate.
- **Store/Admin visibility:** Admin; no sensitive ID data.
- **Audit requirement:** required.

### active delivery

- **Meaning:** in-progress delivery notifications.
- **Examples:** assignment, pickup issue, customer route started.
- **Delivery behavior:** delivered during active delivery.
- **Suppression rules:** minimal suppression.
- **Retry behavior:** standard retry.
- **Store/Admin visibility:** via events.
- **Audit requirement:** required for state-relevant events.

### support update

- **Meaning:** support case updates.
- **Examples:** support case updated/resolved.
- **Delivery behavior:** standard delivery.
- **Suppression rules:** may batch.
- **Retry behavior:** standard retry.
- **Store/Admin visibility:** Admin queue.
- **Audit requirement:** required for case changes.

### operational reminder

- **Meaning:** non-critical reminders.
- **Examples:** pickup reminder, arrival reminder.
- **Delivery behavior:** standard; may be deferred.
- **Suppression rules:** may be suppressed during driving.
- **Retry behavior:** low retry.
- **Store/Admin visibility:** minimal.
- **Audit requirement:** optional/minimal.

### informational/future

- **Meaning:** informational or future categories.
- **Examples:** schedule, earnings visibility summary.
- **Delivery behavior:** standard/deferred.
- **Suppression rules:** may be suppressed/quiet-hours.
- **Retry behavior:** low/no retry.
- **Store/Admin visibility:** minimal/future.
- **Audit requirement:** minimal.

Cross-cutting delivery rules:

- **No notification spam during driving.** Non-critical notifications are
  minimized while driving.
- **Avoid distracting UI during active navigation.** Notification UI must not
  interfere with safe navigation (Dr.1.0.H2).
- **Safety/compliance exceptions.** Emergency/safety and compliance-critical
  notifications override suppression.
- **Quiet hours as a future candidate where appropriate.** Quiet hours apply
  only to non-critical categories.
- **Backend-configurable notification policy as a future capability.** A policy
  engine is a future backend capability (Section 27).

## 20. Communication State Model

The following are **candidate communication states**, finalized in a later
Dr.1.x phase. State is backend-owned; the app reflects it.

### communication_not_started

- **Meaning:** no communication initiated.
- **Who/what can set it:** backend (default).
- **Allowed next states:** `customer_contact_allowed`, `store_contact_allowed`,
  `support_contact_allowed`.
- **Mobile behavior:** no contact actions yet.
- **Backend authority:** contact allowance is backend-owned.
- **Store/Admin visibility:** none.
- **Audit implication:** none.

### customer_contact_allowed

- **Meaning:** customer contact is permitted.
- **Who/what can set it:** backend (policy/state).
- **Allowed next states:** `masked_call_requested`, `masked_message_requested`,
  `communication_blocked`, `communication_closed`.
- **Mobile behavior:** show permitted customer contact actions.
- **Backend authority:** allowance is policy-bound.
- **Store/Admin visibility:** via events.
- **Audit implication:** contact availability.

### store_contact_allowed

- **Meaning:** store contact is permitted.
- **Who/what can set it:** backend.
- **Allowed next states:** `masked_call_requested`, `masked_message_requested`,
  `communication_blocked`, `communication_closed`.
- **Mobile behavior:** show permitted store contact actions.
- **Backend authority:** allowance is policy-bound.
- **Store/Admin visibility:** Store and Admin.
- **Audit implication:** contact availability.

### support_contact_allowed

- **Meaning:** support contact is permitted.
- **Who/what can set it:** backend.
- **Allowed next states:** `support_case_opened`, `safety_escalation_opened`,
  `communication_closed`.
- **Mobile behavior:** show support contact actions.
- **Backend authority:** routing is backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** support availability.

### masked_call_requested

- **Meaning:** a masked call was requested.
- **Who/what can set it:** mobile proposes; backend brokers.
- **Allowed next states:** `contact_attempt_recorded`, `contact_failed`.
- **Mobile behavior:** initiate masked call request.
- **Backend authority:** masking/brokering is backend-owned.
- **Store/Admin visibility:** attempt metadata via events.
- **Audit implication:** `masked_call_requested`.

### masked_message_requested

- **Meaning:** a masked message was requested.
- **Who/what can set it:** mobile proposes; backend brokers.
- **Allowed next states:** `contact_attempt_recorded`, `contact_failed`.
- **Mobile behavior:** initiate masked message request.
- **Backend authority:** masking/brokering is backend-owned.
- **Store/Admin visibility:** attempt metadata via events.
- **Audit implication:** `masked_message_requested`.

### contact_attempt_recorded

- **Meaning:** a contact attempt was recorded.
- **Who/what can set it:** backend.
- **Allowed next states:** `customer_contact_allowed`, `store_contact_allowed`,
  `communication_blocked`, `communication_closed`.
- **Mobile behavior:** reflect recorded attempt.
- **Backend authority:** attempt recording is backend-owned.
- **Store/Admin visibility:** metadata via events.
- **Audit implication:** `contact_attempt_recorded`.

### contact_failed

- **Meaning:** a contact attempt failed.
- **Who/what can set it:** backend.
- **Allowed next states:** `customer_contact_allowed`, `store_contact_allowed`,
  `communication_blocked`.
- **Mobile behavior:** show failure; offer retry/support.
- **Backend authority:** failure recording is backend-owned.
- **Store/Admin visibility:** metadata via events.
- **Audit implication:** contact failure metadata.

### communication_blocked

- **Meaning:** communication is blocked by policy/state.
- **Who/what can set it:** backend.
- **Allowed next states:** `customer_contact_allowed`, `store_contact_allowed`,
  `communication_closed`.
- **Mobile behavior:** disable blocked contact actions.
- **Backend authority:** block is backend-owned.
- **Store/Admin visibility:** via events.
- **Audit implication:** block record.

### communication_closed

- **Meaning:** communication is closed (e.g. after delivery closure).
- **Who/what can set it:** backend.
- **Allowed next states:** `communication_not_started` (next delivery).
- **Mobile behavior:** no contact actions.
- **Backend authority:** closure is backend-owned.
- **Store/Admin visibility:** via events.
- **Audit implication:** closure record.

### support_case_opened

- **Meaning:** a support case has been opened.
- **Who/what can set it:** backend (future case capability).
- **Allowed next states:** `support_case_pending`, `support_case_resolved`,
  `safety_escalation_opened`.
- **Mobile behavior:** reflect open case.
- **Backend authority:** case lifecycle is backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_created`.

### support_case_pending

- **Meaning:** a support case is pending action.
- **Who/what can set it:** backend.
- **Allowed next states:** `support_case_resolved`, `safety_escalation_opened`.
- **Mobile behavior:** reflect pending case.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_updated`.

### support_case_resolved

- **Meaning:** a support case is resolved.
- **Who/what can set it:** backend.
- **Allowed next states:** `communication_closed`.
- **Mobile behavior:** reflect resolution.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_resolved`.

### safety_escalation_opened

- **Meaning:** a safety escalation is open.
- **Who/what can set it:** backend (on safety escalation).
- **Allowed next states:** `safety_escalation_resolved`.
- **Mobile behavior:** reflect safety escalation context.
- **Backend authority:** escalation is backend-owned; may lock route.
- **Store/Admin visibility:** Admin (priority).
- **Audit implication:** `safety_escalation_opened`.

### safety_escalation_resolved

- **Meaning:** a safety escalation is resolved.
- **Who/what can set it:** backend.
- **Allowed next states:** `communication_closed`.
- **Mobile behavior:** reflect resolution.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin.
- **Audit implication:** `safety_escalation_resolved`.

## 21. Support Case State Model

The following are **candidate support case states**, finalized in a later
Dr.1.x phase. Case state is backend-owned.

### no_case

- **Meaning:** no support case exists.
- **Who/what can set it:** backend (default).
- **Allowed next states:** `draft_case`, `case_submitted`.
- **Mobile behavior:** no active case.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** none.
- **Audit implication:** none.

### draft_case

- **Meaning:** a case is being drafted (possibly offline).
- **Who/what can set it:** mobile (local draft).
- **Allowed next states:** `case_submitted`.
- **Mobile behavior:** allow drafting; queue if offline.
- **Backend authority:** not yet a backend case.
- **Store/Admin visibility:** none until submitted.
- **Audit implication:** draft is local; submission audited.

### case_submitted

- **Meaning:** a case was submitted to the backend.
- **Who/what can set it:** mobile submits; backend accepts.
- **Allowed next states:** `triage_pending`.
- **Mobile behavior:** reflect submitted case.
- **Backend authority:** acceptance is backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_created`.

### triage_pending

- **Meaning:** the case awaits triage.
- **Who/what can set it:** backend.
- **Allowed next states:** `support_in_review`, `escalated_safety`,
  `escalated_compliance`, `escalated_return_exception`.
- **Mobile behavior:** reflect triage status.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_updated`.

### support_in_review

- **Meaning:** support is reviewing the case.
- **Who/what can set it:** backend/support.
- **Allowed next states:** `driver_action_required`, `store_action_required`,
  `admin_action_required`, `customer_action_required_future`, `resolved`,
  `escalated_safety`, `escalated_compliance`, `escalated_return_exception`.
- **Mobile behavior:** reflect review status.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_updated`.

### driver_action_required

- **Meaning:** the case needs driver action.
- **Who/what can set it:** backend/support.
- **Allowed next states:** `support_in_review`, `resolved`.
- **Mobile behavior:** surface required driver action.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_updated`.

### store_action_required

- **Meaning:** the case needs store action.
- **Who/what can set it:** backend/support.
- **Allowed next states:** `support_in_review`, `resolved`.
- **Mobile behavior:** reflect waiting-on-store status.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Store and Admin.
- **Audit implication:** `support_case_updated`.

### admin_action_required

- **Meaning:** the case needs admin action.
- **Who/what can set it:** backend/support.
- **Allowed next states:** `support_in_review`, `resolved`.
- **Mobile behavior:** reflect waiting-on-admin status.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_updated`.

### customer_action_required_future

- **Meaning:** the case needs customer action (future).
- **Who/what can set it:** backend/support (future).
- **Allowed next states:** `support_in_review`, `resolved`.
- **Mobile behavior:** reflect waiting-on-customer status (future).
- **Backend authority:** backend-owned (future).
- **Store/Admin visibility:** Admin (future).
- **Audit implication:** `support_case_updated` (future).

### resolved

- **Meaning:** the case is resolved.
- **Who/what can set it:** backend/support.
- **Allowed next states:** `closed`.
- **Mobile behavior:** reflect resolution.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** `support_case_resolved`.

### closed

- **Meaning:** the case is closed.
- **Who/what can set it:** backend.
- **Allowed next states:** `no_case` (next interaction).
- **Mobile behavior:** reflect closed case.
- **Backend authority:** closure is backend-owned.
- **Store/Admin visibility:** Admin queue.
- **Audit implication:** closure record.

### escalated_safety

- **Meaning:** the case is escalated for safety.
- **Who/what can set it:** backend/support.
- **Allowed next states:** `support_in_review`, `resolved`.
- **Mobile behavior:** reflect safety escalation.
- **Backend authority:** backend-owned; may lock route.
- **Store/Admin visibility:** Admin (priority).
- **Audit implication:** `safety_escalation_opened`.

### escalated_compliance

- **Meaning:** the case is escalated for compliance (Dr.1.0.G/H).
- **Who/what can set it:** backend/support.
- **Allowed next states:** `support_in_review`, `resolved`.
- **Mobile behavior:** reflect compliance escalation.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Admin; no sensitive ID data.
- **Audit implication:** `support_case_updated`.

### escalated_return_exception

- **Meaning:** the case is escalated as a return exception (Dr.1.0.H).
- **Who/what can set it:** backend/support.
- **Allowed next states:** `support_in_review`, `resolved`.
- **Mobile behavior:** reflect return exception.
- **Backend authority:** backend-owned.
- **Store/Admin visibility:** Store and Admin.
- **Audit implication:** `return_support_requested`.

## 22. Store/Admin Visibility

Visibility comes from backend-authorized events. Neither the app nor the panels
read call content or private messages.

### Store visibility

- driver contact attempts with the store
- pickup issues
- return issues
- return confirmation support
- failed delivery support category
- safety issue limited visibility when store-impacting
- no private driver/customer safety details unless necessary
- no sensitive ID details

### Admin visibility

- support case queue
- safety event timeline
- communication metadata
- failed delivery / support linkage
- compliance issue linkage
- route/map context if approved (Dr.1.0.H2)
- return exception context
- driver/order/store/customer references, privacy-safe
- no call content
- no unrestricted private messages
- no sensitive ID data
- audit detail

## 23. Audit Events

Audit events are backend-owned and privacy-safe. Names are candidates,
finalized in a later Dr.1.x phase. "Forbidden metadata" never appears in an
event, consistent with Section 25.

### emergency_button_opened

- **Trigger:** driver opens the emergency surface.
- **Actor:** driver.
- **Required metadata:** delivery/route reference (if active), timestamp.
- **Forbidden metadata:** call content, raw continuous location, sensitive ID.
- **Store/Admin visibility:** Admin (priority).
- **Privacy/compliance:** safety access record.

### emergency_call_action_selected

- **Trigger:** driver selects the native 911/emergency action.
- **Actor:** driver.
- **Required metadata:** delivery/route reference (if active), timestamp.
- **Forbidden metadata:** call content, location trace.
- **Store/Admin visibility:** Admin (priority).
- **Privacy/compliance:** marker only; no call content.

### safety_report_started

- **Trigger:** driver starts a safety report.
- **Actor:** driver.
- **Required metadata:** incident type (candidate), route reference.
- **Forbidden metadata:** sensitive ID, call content.
- **Store/Admin visibility:** Admin.
- **Privacy/compliance:** safety record.

### safety_report_submitted

- **Trigger:** driver submits a safety report.
- **Actor:** driver; recorded by backend.
- **Required metadata:** incident type, route reference.
- **Forbidden metadata:** sensitive ID, call content, raw location trace.
- **Store/Admin visibility:** Admin; Store if store-impacting.
- **Privacy/compliance:** safety record.

### safety_escalation_opened

- **Trigger:** a safety escalation is opened.
- **Actor:** backend/support.
- **Required metadata:** escalation reference, route reference.
- **Forbidden metadata:** sensitive ID, call content.
- **Store/Admin visibility:** Admin (priority).
- **Privacy/compliance:** safety record.

### safety_escalation_resolved

- **Trigger:** a safety escalation is resolved.
- **Actor:** backend/support.
- **Required metadata:** escalation reference, outcome.
- **Forbidden metadata:** sensitive ID, call content.
- **Store/Admin visibility:** Admin.
- **Privacy/compliance:** safety record.

### support_center_opened

- **Trigger:** driver opens the support center.
- **Actor:** driver.
- **Required metadata:** entry point, route reference (if active).
- **Forbidden metadata:** sensitive ID.
- **Store/Admin visibility:** Admin.
- **Privacy/compliance:** support access record.

### support_case_created

- **Trigger:** a support case is created/submitted.
- **Actor:** driver submits; backend records.
- **Required metadata:** category, route/order reference, idempotency key.
- **Forbidden metadata:** sensitive ID, call content.
- **Store/Admin visibility:** Admin queue.
- **Privacy/compliance:** case record.

### support_case_updated

- **Trigger:** a support case status changes.
- **Actor:** backend/support.
- **Required metadata:** case reference, new status.
- **Forbidden metadata:** sensitive ID, call content.
- **Store/Admin visibility:** Admin queue.
- **Privacy/compliance:** case record.

### support_case_resolved

- **Trigger:** a support case is resolved.
- **Actor:** backend/support.
- **Required metadata:** case reference, outcome.
- **Forbidden metadata:** sensitive ID, call content.
- **Store/Admin visibility:** Admin queue.
- **Privacy/compliance:** case record.

### customer_call_requested

- **Trigger:** driver requests a customer call.
- **Actor:** driver.
- **Required metadata:** order reference, masked channel reference.
- **Forbidden metadata:** raw phone number, call content.
- **Store/Admin visibility:** metadata via events.
- **Privacy/compliance:** contact attempt metadata.

### customer_message_requested

- **Trigger:** driver requests a customer message.
- **Actor:** driver.
- **Required metadata:** order reference, template reference (if quick message).
- **Forbidden metadata:** raw phone number, message content (beyond template
  reference), sensitive ID.
- **Store/Admin visibility:** metadata via events.
- **Privacy/compliance:** contact attempt metadata.

### store_call_requested

- **Trigger:** driver requests a store call.
- **Actor:** driver.
- **Required metadata:** store reference, masked channel reference.
- **Forbidden metadata:** raw phone number, call content.
- **Store/Admin visibility:** Store and Admin metadata.
- **Privacy/compliance:** contact attempt metadata.

### store_message_requested

- **Trigger:** driver requests a store message.
- **Actor:** driver.
- **Required metadata:** store reference, template reference (if quick message).
- **Forbidden metadata:** raw phone number, message content.
- **Store/Admin visibility:** Store and Admin metadata.
- **Privacy/compliance:** contact attempt metadata.

### masked_call_requested

- **Trigger:** a masked call is requested.
- **Actor:** driver; backend brokers.
- **Required metadata:** masked channel reference, party reference.
- **Forbidden metadata:** raw phone number, call content.
- **Store/Admin visibility:** metadata via events.
- **Privacy/compliance:** masking record.

### masked_message_requested

- **Trigger:** a masked message is requested.
- **Actor:** driver; backend brokers.
- **Required metadata:** masked channel reference, party reference.
- **Forbidden metadata:** raw phone number, message content, sensitive ID.
- **Store/Admin visibility:** metadata via events.
- **Privacy/compliance:** masking record.

### contact_attempt_recorded

- **Trigger:** a contact attempt is recorded.
- **Actor:** backend.
- **Required metadata:** party reference, attempt outcome.
- **Forbidden metadata:** raw phone number, content.
- **Store/Admin visibility:** metadata via events.
- **Privacy/compliance:** attempt metadata.

### quick_message_selected

- **Trigger:** driver selects a quick message template.
- **Actor:** driver.
- **Required metadata:** template reference, party reference.
- **Forbidden metadata:** sensitive ID, free-text content beyond template.
- **Store/Admin visibility:** metadata via events.
- **Privacy/compliance:** template selection record.

### notification_created

- **Trigger:** a notification is created (backend).
- **Actor:** backend.
- **Required metadata:** notification type, priority, reference.
- **Forbidden metadata:** sensitive ID, content beyond type.
- **Store/Admin visibility:** Admin (relevant types).
- **Privacy/compliance:** notification record.

### notification_delivered

- **Trigger:** a notification is delivered to the device.
- **Actor:** backend/delivery channel.
- **Required metadata:** notification reference, timestamp.
- **Forbidden metadata:** sensitive ID, content.
- **Store/Admin visibility:** minimal.
- **Privacy/compliance:** delivery record.

### notification_opened

- **Trigger:** driver opens a notification.
- **Actor:** driver.
- **Required metadata:** notification reference, timestamp.
- **Forbidden metadata:** sensitive ID, content.
- **Store/Admin visibility:** minimal.
- **Privacy/compliance:** open record.

### notification_stale_discarded

- **Trigger:** a stale notification is discarded after reconciliation.
- **Actor:** mobile/backend.
- **Required metadata:** notification reference, reason.
- **Forbidden metadata:** sensitive ID, content.
- **Store/Admin visibility:** minimal.
- **Privacy/compliance:** stale handling record.

### compliance_notification_created

- **Trigger:** a compliance-critical notification is created (backend).
- **Actor:** backend.
- **Required metadata:** notification type (verification/proof/return), reference.
- **Forbidden metadata:** sensitive ID details, ID images, content beyond type.
- **Store/Admin visibility:** Admin; no sensitive ID data.
- **Privacy/compliance:** compliance notification record.

### return_support_requested

- **Trigger:** return support is requested (Dr.1.0.H linkage).
- **Actor:** driver.
- **Required metadata:** order/return reference, category.
- **Forbidden metadata:** sensitive ID, content.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance:** return support record.

### offline_support_action_queued

- **Trigger:** a support/communication action is queued offline.
- **Actor:** mobile.
- **Required metadata:** action type, reference, idempotency key.
- **Forbidden metadata:** restricted completion payloads, content.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** queue record.

### offline_support_action_replayed

- **Trigger:** a queued action is replayed on reconnect.
- **Actor:** mobile/backend.
- **Required metadata:** action type, reference, idempotency key.
- **Forbidden metadata:** restricted completion payloads, content.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** replay record.

### duplicate_support_action_rejected

- **Trigger:** a duplicate support/communication action is rejected.
- **Actor:** backend.
- **Required metadata:** action type, idempotency key.
- **Forbidden metadata:** content, sensitive ID.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** dedup record.

## 24. Idempotency and Offline Behavior

- **Idempotency keys for support/safety/communication actions.** Each action
  carries an idempotency key so retries are safe.
- **Duplicate support case submissions.** Repeated submissions resolve to one
  case.
- **Duplicate safety reports.** Repeated reports resolve to one incident.
- **Duplicate message/call attempts.** Repeated attempts do not create duplicate
  records.
- **Queued support actions.** Non-sensitive support actions may queue offline.
- **Queued communication metadata.** Contact attempt metadata may queue and
  replay.
- **Offline notification opens.** Opening a notification offline navigates
  locally but does not finalize compliance-sensitive state.
- **Stale support state reconciliation.** Stale local support/communication
  state is reconciled against the backend.
- **Backend state validation on reconnect.** The backend validates and reconciles
  on reconnect.
- **No local safety cancellation finalization.** Safety cancellations are not
  finalized locally.
- **No local restricted delivery completion.** Restricted completion always
  awaits backend acceptance.
- **No local support case closure unless the backend accepts.** Cases are closed
  by the backend.

## 25. Privacy and Data-Minimization Boundaries

- **No call recording in the MVP.** Calls are not recorded.
- **No message content retention in the MVP unless legally/product-approved.**
  Content is not retained without review.
- **Audit metadata only where possible.** Audit records metadata, not content.
- **No sensitive ID data in support/customer messages.** No ID numbers or
  compliance internals.
- **No raw ID image.** ID images are never included in messages or events.
- **No full ID number.** Full ID numbers are never included.
- **No unrestricted location sharing.** Location sharing is explicit, scoped, and
  future.
- **No hidden safety tracking.** Safety features never track silently.
- **Retention policy required.** A retention policy is required before storing
  communication/support history.
- **Vendor/legal review for phone masking/SMS relay/chat/push providers.** All
  providers require vendor/legal review.
- **Driver transparency.** Drivers are told what is collected and when.
- **Abuse-prevention boundaries.** Contact and support flows guard against abuse.

## 26. MVP vs Future Boundary

| Feature | MVP / Future / No-Go | Reason | Backend dependency | Mobile dependency | Store/Admin dependency |
|---|---|---|---|---|---|
| Emergency button entry point | MVP | Safety must be reachable | Safety recording | Persistent entry point | Admin events |
| Call 911 native action | Future | Native/legal review needed | None (no backend dialing) | Native call handoff | Admin marker (future) |
| Contact support | MVP | Drivers must reach support | Support routing | Support center | Admin queue |
| Safety issue report | MVP | Field safety accountability | Incident recording | Report UI | Admin events |
| Accident report | MVP | Safety accountability | Incident recording | Report UI | Admin events |
| Vehicle issue report | MVP | Operational/safety support | Incident recording | Report UI | Admin events |
| Cancel/escalate for safety | MVP (request) | Safety precedence | Lifecycle transition | Request UI | Admin; Store if return |
| Customer call | MVP (masked) | Coordination | Masking/contact policy | Contact action | Metadata events |
| Customer message | MVP (masked) | Coordination | Masking/contact policy | Contact action | Metadata events |
| Store call | MVP (masked/mediated) | Pickup/return coordination | Masking/contact policy | Contact action | Store/Admin metadata |
| Store message | MVP (masked/mediated) | Pickup/return coordination | Masking/contact policy | Contact action | Store/Admin metadata |
| Masked phone numbers | Future | Vendor/legal review needed | Masking provider | Mediated contact | Metadata events |
| Quick messages | MVP (low-risk) / Future (compliance) | Speed and consistency | Template service (future) | Template UI | Metadata events |
| Support center | MVP | Central support access | Support routing | Support center | Admin queue |
| Support case tracking | Future | Case model needed | Support case model | Case UI | Admin queue |
| Push notifications | Future | Provider/legal review needed | Push service | Push handling | Admin (relevant) |
| Compliance-critical notifications | MVP (behavior) / Future (delivery) | Must be backend-driven | Compliance state | Notification handling | Admin; no ID data |
| Route/location sharing with support | Future | Privacy/legal review needed | Context sharing | Explicit share UI | Admin (approved) |
| Active route sharing with admin | Future | Privacy/legal review needed | Context sharing | Explicit share UI | Admin (approved) |
| Live chat | Future | Provider/legal review needed | Chat service | Chat UI | Admin |
| Call recording | No-Go (MVP) | Privacy/legal boundary | — | — | — |
| Unrestricted message retention | No-Go (MVP) | Privacy boundary | — | — | — |

## 27. Future Backend Capability Map

Future backend capabilities needed to implement this architecture. Each is a
candidate, finalized in a later Dr.1.x phase, and extends the Dr.1.0.F gap map.

### Support case model

- **Purpose:** own support case lifecycle (Section 21).
- **Data sensitivity:** medium.
- **MVP/Future:** future (foundation in Dr.1.1).
- **Depends on:** domain model (Dr.1.0.C).
- **Store/Admin impact:** Admin queue, Store linkage.
- **Compliance/privacy risk:** must avoid sensitive ID/content.

### Support category model

- **Purpose:** classify support requests (Section 12).
- **Data sensitivity:** low-medium.
- **MVP/Future:** future.
- **Depends on:** support case model.
- **Store/Admin impact:** routing/visibility.
- **Compliance/privacy risk:** low.

### Safety incident model

- **Purpose:** record safety incidents (Section 9).
- **Data sensitivity:** high.
- **MVP/Future:** future (foundation in Dr.1.1).
- **Depends on:** domain model, privacy controls.
- **Store/Admin impact:** Admin safety timeline.
- **Compliance/privacy risk:** sensitive; minimize and review.

### Communication attempt model

- **Purpose:** record contact attempts as metadata (Sections 13–15).
- **Data sensitivity:** medium.
- **MVP/Future:** future.
- **Depends on:** masking provider, audit.
- **Store/Admin impact:** metadata visibility.
- **Compliance/privacy risk:** no content; no raw numbers.

### Masked phone provider integration

- **Purpose:** broker masked calls/messages (Section 15).
- **Data sensitivity:** high.
- **MVP/Future:** future (vendor/legal review).
- **Depends on:** vendor, privacy controls.
- **Store/Admin impact:** metadata only.
- **Compliance/privacy risk:** vendor and retention risk.

### Notification policy engine

- **Purpose:** configure priorities, suppression, quiet hours (Section 19).
- **Data sensitivity:** low-medium.
- **MVP/Future:** future.
- **Depends on:** notification model.
- **Store/Admin impact:** policy visibility (future).
- **Compliance/privacy risk:** must not suppress compliance/safety.

### Push notification service integration

- **Purpose:** deliver notifications (Section 17).
- **Data sensitivity:** medium.
- **MVP/Future:** future (provider/legal review).
- **Depends on:** provider, notification model.
- **Store/Admin impact:** indirect.
- **Compliance/privacy risk:** no sensitive content in payloads.

### Quick message template service

- **Purpose:** manage templates (Section 16).
- **Data sensitivity:** low.
- **MVP/Future:** future (MVP low-risk subset possible).
- **Depends on:** communication model.
- **Store/Admin impact:** metadata only.
- **Compliance/privacy risk:** templates must avoid sensitive detail.

### Communication idempotency

- **Purpose:** dedup contact/support actions (Section 24).
- **Data sensitivity:** low.
- **MVP/Future:** future (foundation).
- **Depends on:** action endpoints.
- **Store/Admin impact:** dedup signals.
- **Compliance/privacy risk:** prevents duplicate effects.

### Offline communication reconciliation

- **Purpose:** reconcile queued actions on reconnect (Section 24).
- **Data sensitivity:** medium.
- **MVP/Future:** future (foundation).
- **Depends on:** idempotency, state models.
- **Store/Admin impact:** stuck/offline signals.
- **Compliance/privacy risk:** no local restricted completion.

### Support/admin queue visibility

- **Purpose:** expose privacy-safe support/safety events (Section 22).
- **Data sensitivity:** medium.
- **MVP/Future:** future.
- **Depends on:** support/safety models.
- **Store/Admin impact:** core visibility.
- **Compliance/privacy risk:** no content, no sensitive ID.

### Safety route/location context sharing

- **Purpose:** share route/location for safety, explicitly (Section 8).
- **Data sensitivity:** high.
- **MVP/Future:** future (privacy/legal review).
- **Depends on:** Dr.1.0.H2 route context, privacy controls.
- **Store/Admin impact:** Admin safety visibility.
- **Compliance/privacy risk:** explicit and scoped only.

### Privacy/retention controls

- **Purpose:** govern minimization and retention (Section 25).
- **Data sensitivity:** high.
- **MVP/Future:** future (foundation for any storage).
- **Depends on:** legal review.
- **Store/Admin impact:** bounds visibility.
- **Compliance/privacy risk:** required before history storage.

### Audit event expansion

- **Purpose:** record support/safety/communication audit events (Section 23).
- **Data sensitivity:** medium.
- **MVP/Future:** future (foundation).
- **Depends on:** audit infrastructure.
- **Store/Admin impact:** audit detail.
- **Compliance/privacy risk:** privacy-safe metadata only.

## 28. Phase Target Map

Future implementation maps to later Dr.1.x phases. These are planning targets,
not commitments, and define no implementation here.

| Phase | Target |
|---|---|
| Dr.1.1 | Backend support/safety/notification foundations (support case, safety incident, communication attempt, notification, idempotency, audit) |
| Dr.1.2 | Mobile support center / communication shell / offline queue |
| Dr.1.3 | Driver MVP active delivery communication and safety access |
| Dr.1.4 | Support / safety escalation workflows |
| Dr.1.5 | Phone masking / push / legal-reviewed provider integrations |
| Dr.1.6 | Admin intelligence, support analytics, driver trust signals |

## 29. No-Go Reminder

This subphase (Dr.1.0.I) is documentation only. It does not create and does not
authorize creating:

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
- emergency calling implementation
- SMS/chat implementation
- push notification implementation
- phone masking implementation
- support ticketing implementation
- location sharing implementation
- route sharing implementation
- notification delivery implementation
- Store/Admin support UI
- customer app behavior
- Stripe/payment/payout logic
- production launch

All state names, category names, event names, and capabilities in this document
are architectural candidates for later Dr.1.x phases. Nothing here is
implemented.
