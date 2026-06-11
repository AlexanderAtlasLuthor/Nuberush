# NubeRush Dr.1.0 — Mobile Research + Driver App Product Architecture

## 1. Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.L — Final Dr.1.0 Product Architecture Document
- **Deliverable path:**
  `docs/dr.1.0-mobile-research-driver-app-product-architecture.md`
- **Status:** Final Architecture / Research Complete
- **Scope:** Research/docs only
- **Implementation:** none — this document consolidates the Dr.1.0 architecture
  and introduces no backend, frontend, or mobile implementation of any kind. It
  creates no endpoints, tables, migrations, schemas, services, mobile project,
  dependencies, tests, or CI/config changes, and no compliance, payment, maps,
  GPS, geofence, verification, notification, or support implementation.

This is the single, final consolidated reference for Dr.1.0. It supersedes the
earlier draft of this file and summarizes the authoritative subphase documents
without modifying them. Where this document and a subphase document differ in
detail, the subphase document is authoritative and this one cross-references it.
All state names, model names, metric names, tier names, and event names are
**architectural candidates**, finalized in later Dr.1.x phases. Nothing here is
implemented.

Source documents consolidated by this final document:

- `docs/dr.1.0-driver-app-contract-lock.md` (Dr.1.0.A)
- `docs/dr.1.0-driver-feature-adaptation-matrix.md` (Dr.1.0.B)
- `docs/dr.1.0-driver-domain-architecture.md` (Dr.1.0.C)
- `docs/dr.1.0-driver-screen-inventory.md` (Dr.1.0.D)
- `docs/dr.1.0-driver-user-flows.md` (Dr.1.0.E)
- `docs/dr.1.0-driver-backend-gap-map.md` (Dr.1.0.F)
- `docs/dr.1.0-driver-compliance-id-verification.md` (Dr.1.0.G)
- `docs/dr.1.0-driver-proof-failure-return.md` (Dr.1.0.H)
- `docs/dr.1.0-driver-live-map-navigation-surface.md` (Dr.1.0.H2)
- `docs/dr.1.0-driver-ops-support-safety.md` (Dr.1.0.I)
- `docs/dr.1.0-driver-earnings-performance-rewards.md` (Dr.1.0.J)
- `docs/dr.1.0-mobile-stack-decision.md` (Dr.1.0.K)

## 2. Executive Summary

- **The NubeRush web app is mature enough to move toward the next app.** The
  F2.x web phases established the store and admin foundation; NubeRush is ready
  to design its next application.
- **The next app should be the Driver App.** Delivery execution is the operational
  layer the web foundation cannot serve well, and it is inherently mobile.
- **The Driver App is critical because delivery operations need a dedicated mobile
  workflow.** Pickup, transit, verification, proof, failure, return, safety, and
  navigation are field activities that require a guided, mobile-native surface.
- **Smoke-shop/restricted-product delivery requires more than a generic delivery
  driver app.** Regulated products demand 21+ verification, no-unattended
  handling, accountable return-to-store, and a compliance-grade audit trail.
- **The NubeRush Driver App must combine Uber Driver/Uber Eats operational depth
  with NubeRush compliance needs.** The proven structure of a mature driver
  platform is studied (not copied) and adapted to a regulated-delivery model.
- **The backend remains the authority.** Eligibility, assignment, lifecycle,
  compliance, proof, return, support, earnings, and payment state are
  backend-owned; the mobile app is a thin operational surface.
- **Flutter is the recommended future stack.** Flutter is the recommended default
  mobile stack for the production Driver App (Dr.1.0.K), with Capacitor reserved
  for prototype/demo only.

The product principle, consistent with the contract lock (Dr.1.0.A):

> NubeRush Driver App = Uber Driver operational depth + Uber Eats delivery
> workflow + smoke-shop compliance + 21+ verification + proof-of-delivery
> enforcement + return-to-store accountability + backend-authorized audit trail.

## 3. Why Driver App Comes First

- **The store/admin web foundation already exists.** The web phases delivered the
  store and admin surfaces; the missing layer is field delivery execution.
- **Delivery execution cannot be handled well from the web admin/store panel.**
  Web panels are oversight surfaces, not field tools; drivers need a dedicated
  mobile app.
- **Driver workflows are mobile-native.** Location, the live map, camera-based
  future verification, notifications, and offline behavior are native concerns.
- **Restricted-product delivery requires guided verification, proof, failure,
  return, safety, and navigation workflows.** These are structured, compliance-
  sensitive flows that a generic viewer cannot provide.
- **The Driver App unlocks the next operational layer before customer app
  expansion.** Reliable, compliant delivery execution is a prerequisite for a
  broader marketplace.
- **The customer app should come later, after driver operations are defined.**
  Defining the driver operation first establishes the lifecycle, compliance, and
  audit foundations a future customer app would depend on.

## 4. Product Principles

- **Backend-authorized lifecycle.** The backend owns every lifecycle transition;
  the mobile app proposes, the backend authorizes.
- **Mobile thin client.** The app renders backend state, initiates actions, and
  queues safe retries; it never owns final state.
- **Compliance first.** Regulated handling and 21+ verification take precedence
  over speed and convenience.
- **No unattended restricted delivery.** Restricted product is never left at a
  door, porch, lobby, mailbox, or otherwise unattended.
- **No local driver override.** Drivers cannot locally override compliance,
  proof, return, route, support, earnings, payment, inventory, or lifecycle
  state.
- **Proof/failure/return enforced.** Completion requires proof; failures and
  returns are structured and accountable (Dr.1.0.H).
- **Safety always accessible.** Safety and support remain reachable during active
  delivery, including from the live map (Dr.1.0.H2/I).
- **Privacy and data minimization.** Sensitive data is minimized; no raw ID data
  and no raw continuous location replay in the MVP.
- **Audit-first operations.** Every meaningful step emits a privacy-safe,
  backend-owned audit event.
- **Store/Admin visibility through backend events.** Oversight reads the backend
  event stream, not direct mobile state.
- **No payment/payout movement in Dr.1.0.** No Stripe, cashout, payout, or
  payment movement is introduced (Dr.1.0.J).
- **Future legal-reviewed upgrades only.** ID scan/OCR/liveness/vendor,
  background location, geofence, and route deviation are future, legally
  reviewed, backend-authorized candidates only.

## 5. Uber Driver Feature Adaptation Summary

Consolidates Dr.1.0.B. Uber Driver and Uber Eats Driver are studied as product
research inspiration; no Uber branding, protected design, or UI is reproduced.
The proven operational structure is adapted to NubeRush's regulated smoke-shop
delivery model.

- **Features kept:** assignment/offers, active delivery lifecycle, store pickup,
  customer dropoff, navigation handoff, safety toolkit concept, support center
  concept, earnings visibility, performance concept, notifications.
- **Features adapted:** passenger pickup becomes store pickup; passenger dropoff
  becomes restricted-product customer handoff; alcohol ID checks become 21+
  smoke-shop verification; restaurant-not-ready becomes store-order-not-ready;
  airport geofence becomes store/customer/legal-zone geofence; Uber Pro becomes
  NubeRush Driver Performance/Compliance Status.
- **Features deferred:** background location, geofence arrival, route deviation,
  internal turn-by-turn, masked phone, push delivery, support ticketing,
  rewards/status tiers, camera/OCR/liveness verification.
- **Features not applicable:** rideshare-only concepts (passenger trips, fares,
  rider ratings, multi-rider trips, airport queues, passenger no-show/destination
  changes).
- **NubeRush-specific upgrades:** 21+ verification gate, no-unattended-restricted
  rule, accountable return-to-store, compliance metrics, restricted delivery
  quality model, compliance-grade audit trail.
- **Rideshare-only exclusions:** any passenger-carrying behavior is out of scope.

| Feature area | Uber-style concept | NubeRush decision | MVP/Future/No-Go | Notes |
|---|---|---|---|---|
| Pickup | Passenger/restaurant pickup | Store pickup with handoff | MVP | Store-confirmed handoff (Dr.1.0.H) |
| Dropoff | Passenger dropoff | Restricted customer handoff | MVP | No unattended delivery |
| Age check | Alcohol ID check | 21+ smoke-shop verification | MVP (manual) | Camera/vendor future (Dr.1.0.G) |
| Navigation | In-app/handoff navigation | External map handoff | MVP | Internal turn-by-turn future (Dr.1.0.H2) |
| Geofence | Airport/venue geofence | Store/customer/legal-zone geofence | Future | Backend-authorized candidate |
| Safety | Safety toolkit | Driver delivery safety toolkit | MVP (access) | Emergency/support (Dr.1.0.I) |
| Performance | Uber Pro tiers | Performance/Compliance Status | Future | Compliance-weighted (Dr.1.0.J) |
| Earnings | Earnings/cashout | Visibility-only earnings | MVP (visibility) | No payout/Stripe (Dr.1.0.J) |
| Rides | Passenger trips/fares | Not applicable | No-Go | Not a rideshare app |

## 6. NubeRush Driver App Domain Architecture

Consolidates Dr.1.0.C. The Driver App is modeled as a set of domains, each a view
onto the backend-owned delivery domain. The backend is the authority; the mobile
app is the operational surface; Store/Admin panels are visibility/oversight
surfaces.

- **Domain categories:** account/onboarding/documents/vehicle/compliance/training;
  availability/offers/assignment; active delivery/pickup/handoff/navigation/
  dropoff; restricted verification/age-ID; proof/failure/return; live map/
  navigation; safety/communication/support; earnings/performance/rewards;
  notifications/settings; geofencing/legal zones; technical reliability; audit;
  and the Admin/Store visibility bridge.
- **Backend authority summary:** eligibility, assignment, lifecycle transitions,
  verification results, proof acceptance, failure/return outcomes, support/safety
  outcomes, earnings snapshots, and audit are backend-owned.
- **Mobile responsibility summary:** render state, capture operational intent,
  submit backend-authorized actions, queue safe retries, and recover permissions
  and connectivity.
- **Store/Admin visibility summary:** privacy-safe, role-limited visibility via
  backend events; no raw surveillance, no sensitive ID data, no call content.
- **Compliance domains:** driver compliance, restricted verification, age/ID
  verification (Dr.1.0.G).
- **Proof/failure/return domains:** proof of delivery, failed delivery, return-to-
  store (Dr.1.0.H).
- **Live map/navigation domain:** active delivery map, route state, navigation
  handoff (Dr.1.0.H2).
- **Safety/support/communication domain:** safety toolkit, support center,
  communication, notifications (Dr.1.0.I).
- **Earnings/performance domain:** earnings visibility, performance, compliance
  metrics, future rewards (Dr.1.0.J).

| Domain | Purpose | Backend responsibility | Mobile responsibility | Store/Admin visibility | MVP/Future |
|---|---|---|---|---|---|
| Account / Onboarding / Documents | Approved, eligible driver | Eligibility, approval, document state | Submit/display profile and documents | Admin approval status | MVP |
| Availability / Offers / Assignment | Connect orders to drivers | Assignment lifecycle | Display offers, submit accept/decline | Store assigned status | MVP |
| Active Delivery | Execute the delivery | Lifecycle transitions | Render steps, submit actions | Store/Admin status | MVP |
| Compliance / Age-ID Verification | Lawful restricted handoff | Verification result, gate | Manual checklist, submit result | Admin (redacted) | MVP (manual) |
| Proof / Failure / Return | Accountable outcomes | Acceptance, return closure | Capture proof/failure/return intent | Store/Admin status | MVP |
| Live Map / Navigation | Spatial workspace | Route state, destinations | Render map, handoff to nav apps | Admin route state | MVP |
| Safety / Support / Communication | Driver safety and help | Routing, escalation, masking | Initiate safety/support/contact | Admin events | MVP (access) |
| Earnings / Performance | Visibility and quality | Snapshots, metrics | Display visibility-only | Admin aggregate | MVP (visibility) |
| Geofencing / Legal Zones | Location compliance | Zone evaluation, warnings | Display warnings | Admin signals | Future |
| Technical Reliability | Real-world robustness | Reconciliation, idempotency | Offline queue, retries | Stuck/offline signals | MVP |
| Audit Timeline | Traceability | Event truth | Emit action intents | Admin audit | MVP |

## 7. Complete Screen Inventory

Consolidates Dr.1.0.D. The detailed screen specifications remain authoritative in
Dr.1.0.D; this section summarizes the groups. No screens are implemented in
Dr.1.0.

- **Major screen groups:** onboarding/documents/vehicle; availability/offers;
  active delivery; pickup/handoff; customer dropoff; verification; proof/failure/
  return; live map/navigation; support/safety; communication; earnings/history;
  notifications/settings; permission/offline recovery.
- **Compliance-critical screens:** age/ID verification, restricted handoff,
  verification failure, proof-required.
- **Active delivery screens:** offer, en route to store, arrived at store, pickup,
  en route to customer, arrival at customer.
- **Proof/failure/return screens:** proof capture, failed delivery, return-to-
  store, return handoff.
- **Live map/navigation screens:** active delivery map, route step overlay,
  navigation handoff.
- **Support/safety screens:** emergency/safety, support center, incident report.
- **Earnings/performance screens:** earnings summary placeholder, delivery
  history, performance detail (future).
- **MVP vs future screen boundaries:** manual verification, external navigation
  handoff, and visibility-only earnings are MVP; camera/OCR/liveness, embedded
  maps, masked-phone UI, and rewards screens are future.

| Screen group | Examples | MVP/Future |
|---|---|---|
| Onboarding / Documents | Login, checklist, document upload | MVP |
| Availability / Offers | Online/offline, delivery offer | MVP |
| Active Delivery | En route, arrival, pickup steps | MVP |
| Verification | Age/ID checklist, failure | MVP (manual) |
| Proof / Failure / Return | Proof capture, failure, return | MVP |
| Live Map / Navigation | Active map, step overlay, handoff | MVP |
| Support / Safety | Emergency, support center, incident | MVP (access) |
| Communication | Contact customer/store, quick messages | MVP (masked future) |
| Earnings / History | Summary placeholder, history | MVP (visibility) |
| Settings / Recovery | Settings, permission/offline recovery | MVP |

## 8. Driver User Flows

Consolidates Dr.1.0.E. Flows are backend-authorized; the app reflects backend
transitions and never advances lifecycle locally.

- **Assigned delivery flow:** offer → accept → backend-authorized assignment.
- **Pickup flow:** navigate to store → arrive → store handoff → backend-confirmed
  pickup.
- **Delivery flow:** navigate to customer → arrive → verification → proof →
  backend-authorized completion.
- **ID verification flow:** 21+ manual checklist → backend-authorized result
  (Dr.1.0.G).
- **Proof flow:** proof capture → backend acceptance (Dr.1.0.H).
- **Failed delivery flow:** contact + wait → failure reason → backend-recorded
  failure (Dr.1.0.H).
- **Return-to-store flow:** return-required → navigate to store → store-confirmed
  return (Dr.1.0.H).
- **Live map/navigation flow:** route state → step overlay → external navigation
  handoff (Dr.1.0.H2).
- **Support/safety flow:** emergency/support access → backend routing/escalation
  (Dr.1.0.I).
- **Communication flow:** masked/policy-bound contact with customer/store
  (Dr.1.0.I).
- **Earnings/history viewing flow:** display backend snapshots, visibility-only
  (Dr.1.0.J).
- **Offline/retry flow:** queue safe actions → reconcile on reconnect (Dr.1.0.H2/
  I/J).

Flow dependency summary: pickup precedes the customer leg; verification precedes
proof for restricted orders; failure may route to return; safety may lock the
route. All transitions are backend-authorized and emit audit events. There is no
local override of compliance, proof, return, route, support, earnings, payment,
inventory, or lifecycle state.

## 9. Compliance / ID Verification Architecture

Consolidates Dr.1.0.G.

- **MVP manual 21+ verification checklist.** The MVP is a manual driver checklist
  (customer present, valid government ID, 21+, ID not expired, ID matches person,
  correct recipient).
- **No raw ID image storage.** No raw ID images are stored.
- **No full ID number storage.** No full ID numbers are stored.
- **No OCR/barcode/liveness/vendor in the MVP.** Automated verification methods
  are future, legally reviewed candidates only.
- **Backend-authorized verification result.** The backend records the result and
  decides whether completion is allowed; the app submits intent.
- **Failure reasons.** Structured reasons (no ID, expired, underage, mismatch,
  wrong recipient, refused, suspected fake, unsafe).
- **Blocked delivery rules.** A failed verification blocks completion and the
  proof path.
- **Return-to-store dependency.** A restricted verification failure routes to
  failed delivery and return-to-store (Dr.1.0.H).
- **Store/Admin visibility.** Redacted, privacy-safe; no sensitive ID data.
- **Future legal-reviewed verification methods.** Barcode, OCR, vendor
  verification, liveness, and any redacted encrypted capture are future and
  require legal review and a retention policy.

## 10. Proof / Failed Delivery / Return Architecture

Consolidates Dr.1.0.H.

- **MVP proof policy.** The MVP persists redacted, non-sensitive proof metadata
  (driver attestation, verification-passed, timestamp, approximate GPS, optional
  customer PIN); richer methods (signature, photo, geofence-verified) are future.
- **Proof cannot override failed compliance.** A passed 21+ verification is a
  precondition; proof never substitutes for it.
- **Restricted delivery cannot be left unattended.** No leave-at-door or
  unattended handoff for restricted product.
- **Failed delivery reasons.** Structured failure reasons capture why a delivery
  could not complete.
- **Wait timer.** A contact-and-wait step precedes a no-show failure.
- **Customer/store contact requirements.** Reasonable contact attempts are
  expected before failure where applicable.
- **Support escalation.** Failures and returns can route to support (Dr.1.0.I).
- **Return-to-store requirement.** Undeliverable restricted product routes to an
  accountable return.
- **Store return confirmation.** The store confirms the return; the driver cannot
  self-close it.
- **Inventory safety implications.** Failed delivery does not consume inventory;
  return protects restricted-product accountability.
- **Audit events.** Every proof/failure/return step emits a compliance-grade
  audit event.
- **Idempotency/offline behavior.** Actions carry idempotency keys; restricted
  completion is never finalized locally or offline.

## 11. During Delivery Map / Live Navigation Surface Architecture

Consolidates Dr.1.0.H2. This is the live map/navigation surface and is presented
here as its own major section.

- **Live driver map.** A driver-facing spatial workspace during active delivery.
- **Route state model.** A backend-owned route state model (store leg, customer
  leg, return leg, arrival candidates, completion/failure/return states, support-
  locked, offline-pending).
- **Current step overlay.** A single-step overlay with primary/secondary CTAs and
  disabled actions per state.
- **ETA/distance as estimate only.** ETA/distance is guidance, never a contract;
  no payout/penalty depends on it.
- **Apple Maps / Google Maps / Waze handoff.** External navigation handoff is the
  MVP navigation mechanism; no embedded SDK and no internal turn-by-turn in the
  MVP.
- **Customer route.** Begins only after backend-confirmed pickup.
- **Store route.** Routes to the store for pickup; the customer leg depends on
  confirmed pickup.
- **Return-to-store route.** A first-class route state for accountable returns.
- **GPS permission recovery.** Recovery flows for denied/restricted location.
- **Network recovery.** Offline banner, retry, stale warning, reconciliation.
- **Geofence arrival as future/backend-authorized candidate.** Geofence only
  suggests an arrival candidate; the backend validates the transition; manual
  arrival may be MVP.
- **Route deviation as future only.** No deviation enforcement, penalty, or
  cancellation in the MVP.
- **Legal/restricted-zone warnings as backend-provided future candidate.**
  Display-only; no mobile-only legal decision.
- **Support/safety access from the active map.** Safety/support remain reachable
  during navigation.
- **Privacy/location boundaries.** No raw continuous location replay in the MVP;
  location is minimized and scoped to the active delivery.
- **No internal turn-by-turn in the MVP.** External handoff only.
- **No CarPlay/Android Auto in the MVP.** Future.

## 12. Safety / Support / Communication / Notifications Architecture

Consolidates Dr.1.0.I.

- **Emergency button.** A prominent, always-reachable emergency entry point.
- **Call 911 future/native handoff.** A driver-controlled native call handoff;
  the backend never dials emergency services.
- **Support center.** A central support surface with categorized help.
- **Safety incident reports.** Structured incident types (unsafe location,
  threatening customer, accident, vehicle issue, robbery/attempted theft,
  harassment, medical, authority interaction, road hazard, app-blocking, other).
- **Cancel/escalate for safety.** A driver request; the backend authorizes the
  final state and may lock the route.
- **Customer communication.** Masked/policy-bound contact; no sensitive ID
  details in customer messages.
- **Store communication.** Pickup/return coordination; no direct store-state
  mutation.
- **Masked phone future requirement.** Production communication uses masked or
  platform-mediated channels (future capability).
- **Quick messages.** Candidate templates carrying no sensitive ID/compliance
  internals.
- **Notification architecture.** Assignment, active delivery, compliance-critical,
  return, support, and safety notifications.
- **Compliance-critical notification behavior.** Backend-driven; a notification
  never authorizes completion alone.
- **Store/Admin visibility.** Privacy-safe events; no call content, no sensitive
  ID data.
- **Audit events.** Safety/support/communication steps emit privacy-safe events.
- **Privacy/data minimization.** No call recording or message-content retention
  in the MVP without review.
- **Offline/idempotency.** Safe actions queue with idempotency keys; safety/
  support cases are not closed locally.

## 13. Earnings / Performance / Rewards Future Architecture

Consolidates Dr.1.0.J. This is visibility-only and architecture-only.

- **Estimated earnings per delivery.** Backend-provided estimate; never computed
  locally; not a guaranteed payout.
- **Completed delivery count.** Counts only backend-authorized completions;
  restricted completions count only after verification/proof.
- **Delivery history.** Redacted history with status labels and an estimate line;
  no settlement detail.
- **Earnings summary placeholder.** Daily/weekly placeholders with disclaimer
  copy.
- **No payouts.** No payout movement.
- **No cashout.** No cashout.
- **No Stripe.** No Stripe or Stripe Connect.
- **No payment movement.** No transfers, wallet, or ledger.
- **No payroll/tax implementation.** No payroll, tax, or accounting handling.
- **Performance metrics.** Explainable, never auto-punitive; safety-aware
  exclusions.
- **Compliance metrics.** Redacted; never reward shortcuts; lawful blocks are
  correct behavior.
- **Restricted delivery quality model.** Compliance-weighted, not speed-only.
- **Future rewards/status tiers.** Future-only; no auto-privilege or legal claim.
- **Compliance Trusted.** Future-only recognition for compliance-safe behavior;
  not speed; no legal certification without review.
- **Restricted Delivery Certified.** Future-only; training/legal-approval gated;
  no age/ID bypass.
- **Store/Admin visibility.** Privacy-safe, role-limited; no unrestricted
  payroll/payment data.
- **Audit/privacy boundaries.** Privacy-safe metadata only; no bank/tax/raw ID
  data; retention policy required before history storage.

## 14. Backend Gap Map

Consolidates Dr.1.0.F at a high level, with cautious language and without
exposing unnecessary backend internals.

- **Existing backend capabilities (high level).** Store and admin web foundations
  exist (orders, store/admin surfaces); the driver operational layer is not yet
  built.
- **Missing backend capability groups.** Driver identity/eligibility, assignment
  lifecycle, delivery execution lifecycle, verification, proof, failure, return,
  route state, support/safety, communication, notifications, earnings/performance
  read models, geofence/legal zones, and audit expansion.
- **Candidate endpoint families.** Driver eligibility, assignment actions, delivery
  lifecycle actions, verification result, proof submission, failure/return actions,
  route actions/arrival candidates, support/safety actions, communication
  brokering, notification policy, and earnings/performance reads. All are
  candidates, finalized later.
- **Future data models.** See Section 15.
- **RBAC and tenancy gaps.** Driver role, store-scoped and admin-scoped visibility,
  and tenancy boundaries for driver/order/store/customer references.
- **Audit/privacy/compliance gaps.** Compliance-grade, privacy-safe audit; data
  minimization; retention controls.
- **Inventory/notification/geofence/support/performance gaps.** Return-aware
  inventory handling, notification policy/delivery, geofence evaluation, support
  case model, and performance/compliance projections.
- **Idempotency/offline retry needs.** Idempotency keys and offline reconciliation
  across all driver actions.

## 15. Future Data Model Map

Future candidate models, summarized from the subphase documents. Each is a
candidate, finalized in a later Dr.1.x phase; all are backend-owned, and the
mobile app never writes authoritative state.

| Model | Purpose | Sensitivity | MVP/Future | Backend authority note |
|---|---|---|---|---|
| Driver profile | Driver identity/eligibility | Medium | Future foundation | Eligibility is backend-owned |
| Driver assignment | Order-to-driver assignment lifecycle | Medium | Future foundation | Assignment is backend-owned |
| Delivery lifecycle | Execution lifecycle (attempt) | Medium | Future foundation | Transitions are backend-owned |
| Age verification result | 21+ verification outcome | High | Future | Result is backend-owned; redacted |
| Proof of delivery result | Proof outcome | Medium-High | Future | Acceptance is backend-owned |
| Failed delivery reason | Structured failure reason | Medium | Future | Failure is backend-owned |
| Return-to-store record | Accountable return | Medium | Future | Store confirmation required |
| Route state / route event | Live route state and events | Medium | Future | Route state is backend-owned |
| Support case | Support lifecycle | Medium | Future | Case lifecycle is backend-owned |
| Safety incident | Safety event record | High | Future | Never auto-punitive; backend-owned |
| Communication attempt | Contact metadata (no content) | Medium | Future | Metadata only; masked |
| Notification event | Notification lifecycle | Low-Medium | Future | Backend-driven |
| Earnings snapshot | Read-only earnings snapshot | Medium | Future | Display only; no settlement |
| Performance metric projection | Explainable metrics | Medium | Future | No auto-discipline |
| Compliance metric projection | Redacted compliance metrics | High | Future | No sensitive ID data |
| Reward/status tier candidate | Future trust tiers | Medium | Future | No auto-privilege; reviewed |
| Audit expansion | Privacy-safe audit events | Medium | Future foundation | Event truth is backend-owned |

## 16. Mobile Stack Decision

Consolidates Dr.1.0.K.

- **Flutter recommended default.** Flutter is the recommended default stack for
  the production Driver App.
- **Capacitor fallback/prototype only.** Capacitor is acceptable for a short-lived
  prototype or internal demo with no background location and no production
  restricted delivery, with a clear migration path to Flutter.
- **React Native viable but not preferred unless team changes.** React Native is a
  credible cross-platform option but not the default unless team expertise or TS-
  contract priorities change.
- **Native iOS/Android not default.** Fully native dual implementation is reserved
  for future/specialized needs; it is not recommended as the default.
- **Why Flutter fits the requirements.** Flutter balances native capability and
  single-codebase velocity and is best positioned for camera, GPS, background
  location, push, secure storage, offline queues, maps, performance, and app
  store readiness for this team.
- **Web reuse should be design/API contract reuse, not necessarily UI code
  reuse.** The durable reuse is shared product contracts and design language, not
  shared UI code.
- **Mobile remains a thin client.** The app renders backend state, initiates
  actions, queues safe retries, and never owns compliance/payment/final lifecycle
  decisions.

## 17. Phase Roadmap

The forward roadmap from Dr.1.1 through Dr.1.6. These are planning targets, not
commitments, and define no implementation here.

### Dr.1.1 — Backend contracts/models/audit foundations

- **Goal:** establish the backend driver surface and read-model/audit
  foundations.
- **Major deliverables:** driver eligibility/assignment/lifecycle contracts,
  verification/proof/failure/return state, route state, support/safety/
  communication/notification foundations, earnings/performance read models,
  idempotency, and privacy-safe audit.
- **Explicit exclusions:** no mobile app; no payment movement; no automated
  verification; no background location.
- **Dependencies:** Dr.1.0 architecture (this document).
- **Definition of ready:** Dr.1.0 validated and consolidated.
- **Definition of done candidate:** backend contracts and audit foundations
  documented and (in a later build phase) implemented behind the agreed
  boundaries.

### Dr.1.2 — Mobile project foundation/API client/offline queue/shell

- **Goal:** stand up the Flutter foundation and integration shell.
- **Major deliverables:** Flutter project foundation, API client, offline queue
  foundation, navigation handoff shell, secure storage approach.
- **Explicit exclusions:** no compliance/payment logic; no background location;
  no production release.
- **Dependencies:** Dr.1.1 contracts.
- **Definition of ready:** Dr.1.1 contracts available.
- **Definition of done candidate:** a thin-client shell that renders backend
  state and queues safe retries.

### Dr.1.3 — Driver MVP delivery lifecycle app

- **Goal:** deliver the MVP active-delivery experience.
- **Major deliverables:** assigned delivery, pickup/handoff, manual 21+
  verification, proof, failure, return, and the live map with external
  navigation handoff.
- **Explicit exclusions:** no camera/OCR/liveness; no background location; no
  payouts.
- **Dependencies:** Dr.1.1, Dr.1.2.
- **Definition of ready:** shell and contracts in place.
- **Definition of done candidate:** a compliant MVP delivery lifecycle on iOS and
  Android behind backend authority.

### Dr.1.4 — Safety/support/communication/notifications

- **Goal:** deliver safety, support, communication, and notifications.
- **Major deliverables:** emergency/support access, incident reports, masked
  communication (as available), and backend-driven notifications.
- **Explicit exclusions:** no automated emergency dispatch; no message-content
  retention without review.
- **Dependencies:** Dr.1.3.
- **Definition of ready:** MVP lifecycle app available.
- **Definition of done candidate:** safety/support reachable from active delivery
  with privacy-safe audit.

### Dr.1.5 — Legal-reviewed compliance/camera/geofence/location/provider upgrades

- **Goal:** add legally reviewed compliance and location upgrades.
- **Major deliverables:** camera/document/barcode/OCR/liveness candidates,
  geofence arrival candidates, background location, restricted-zone warnings,
  and masked-phone/push provider integrations.
- **Explicit exclusions:** nothing without legal/privacy review and a retention
  policy.
- **Dependencies:** Dr.1.3, Dr.1.4, legal review.
- **Definition of ready:** legal/privacy review complete for each upgrade.
- **Definition of done candidate:** reviewed upgrades shipped behind backend
  authority and store policy.

### Dr.1.6 — Analytics/performance/rewards/admin intelligence

- **Goal:** add analytics, performance/rewards surfaces, and admin intelligence.
- **Major deliverables:** performance/compliance analytics, reward/status tiers
  (after review), admin visibility, and a possible payout-planning handoff to a
  separate legal/accounting phase.
- **Explicit exclusions:** no payout/payment movement in Dr.1.x without a
  dedicated legal/product/accounting phase.
- **Dependencies:** Dr.1.3–Dr.1.5.
- **Definition of ready:** stable metrics read models.
- **Definition of done candidate:** privacy-safe analytics and reviewed tiers.

## 18. No-Go Boundaries

Dr.1.0 is documentation only. It does not create and does not authorize creating:

- backend endpoints
- database tables
- migrations
- schemas
- services
- frontend UI
- mobile app code
- a Flutter project
- a Capacitor project
- a React Native project
- a native iOS project
- a native Android project
- dependency changes
- tests
- CI/config changes
- real ID scan
- OCR
- barcode scanning
- liveness
- third-party verification vendor integration
- raw ID image storage
- full ID number storage
- geofence implementation
- route deviation implementation
- internal turn-by-turn navigation
- push notification delivery
- phone masking
- support ticketing
- payouts
- cashout
- Stripe
- payment movement
- customer app behavior
- a production launch

## 19. Definition of Done for Dr.1.0

Dr.1.0 is complete when:

- **All architecture docs are complete.** Dr.1.0.A through Dr.1.0.K exist.
- **All validations PASS.** Each subphase has a passing validation.
- **The final consolidated doc is created.** This document (Dr.1.0.L) exists.
- **Docs-only scope is confirmed.** No implementation was introduced in any
  subphase.
- **No implementation introduced.** No backend, frontend, or mobile code.
- **No payment/compliance/mobile code introduced.** No Stripe/payout, no
  verification/OCR/liveness, no mobile project.
- **The roadmap is ready for Dr.1.1.** The phase roadmap (Section 17) is defined.
- **A checkpoint commit is ready only after final validation.** Any commit happens
  only after Dr.1.0.L validation and only when explicitly instructed.

## 20. Final Architecture Decision

- **Build the NubeRush Driver App next.** The Driver App is the next application
  after the web foundation.
- **Flutter is the recommended future stack.** Flutter is the recommended default
  mobile stack, with Capacitor reserved for prototype/demo.
- **Driver App MVP focus.** The MVP focuses on assigned delivery, pickup,
  restricted 21+ verification, proof, failure, return, external map handoff,
  support/safety, communication, notifications, and visibility-only earnings/
  history.
- **The customer app comes later.** Customer-facing work follows once driver
  operations are defined and reliable.
- **Backend work comes before mobile implementation.** Dr.1.1 backend contracts
  precede Dr.1.2+ mobile work.
- **Dr.1.0 is complete only after validation and checkpoint.** Completion requires
  Dr.1.0.L validation and an explicitly instructed checkpoint commit.

## 21. Appendix — Source Document Index

| File path | Subphase | Purpose | Status |
|---|---|---|---|
| `docs/dr.1.0-driver-app-contract-lock.md` | Dr.1.0.A | Phase scope, boundaries, product principle | Complete |
| `docs/dr.1.0-driver-feature-adaptation-matrix.md` | Dr.1.0.B | Uber feature adaptation matrix | Complete |
| `docs/dr.1.0-driver-domain-architecture.md` | Dr.1.0.C | Driver App domain architecture | Complete |
| `docs/dr.1.0-driver-screen-inventory.md` | Dr.1.0.D | Full screen inventory | Complete |
| `docs/dr.1.0-driver-user-flows.md` | Dr.1.0.E | Driver user flows | Complete |
| `docs/dr.1.0-driver-backend-gap-map.md` | Dr.1.0.F | Backend gap map | Complete |
| `docs/dr.1.0-driver-compliance-id-verification.md` | Dr.1.0.G | Compliance / 21+ ID verification | Complete |
| `docs/dr.1.0-driver-proof-failure-return.md` | Dr.1.0.H | Proof / failed delivery / return-to-store | Complete |
| `docs/dr.1.0-driver-live-map-navigation-surface.md` | Dr.1.0.H2 | Live map / navigation surface | Complete |
| `docs/dr.1.0-driver-ops-support-safety.md` | Dr.1.0.I | Safety / support / communication / notifications | Complete |
| `docs/dr.1.0-driver-earnings-performance-rewards.md` | Dr.1.0.J | Earnings / performance / rewards future | Complete |
| `docs/dr.1.0-mobile-stack-decision.md` | Dr.1.0.K | Mobile stack decision (Flutter vs Capacitor) | Complete |
| `docs/dr.1.0-mobile-research-driver-app-product-architecture.md` | Dr.1.0.L | Final consolidated architecture (this document) | Final / Research Complete |

All state names, model names, metric names, tier names, and event names in this
document are architectural candidates for later Dr.1.x phases. Nothing here is
implemented, and no payment movement is introduced.
