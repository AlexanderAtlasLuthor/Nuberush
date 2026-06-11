# Dr.1.0 Driver Live Map and Navigation Surface Architecture

## 1. Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.H2 — During Delivery Map / Live Navigation Surface
  Architecture
- **Deliverable path:** `docs/dr.1.0-driver-live-map-navigation-surface.md`
- **Status:** Draft / Architecture
- **Scope:** Research/docs only
- **Implementation:** none — this document introduces no backend, frontend, or
  mobile implementation of any kind. It defines no endpoints, no database
  tables, no migrations, no schemas, no services, no maps, no GPS tracking, no
  geofence logic, and no navigation SDK integration.

This document is a new dedicated subphase requested after Dr.1.0.H. It is
subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and consistent with
`docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/dr.1.0-driver-screen-inventory.md`,
`docs/dr.1.0-driver-user-flows.md`,
`docs/dr.1.0-driver-backend-gap-map.md`,
`docs/dr.1.0-driver-compliance-id-verification.md` (Dr.1.0.G),
`docs/dr.1.0-driver-proof-failure-return.md` (Dr.1.0.H),
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them. Route
state names, overlay names, and event names are **architectural candidates**,
finalized in later Dr.1.x phases. Nothing here is implemented.

## 2. Purpose

This document defines how the NubeRush Driver App should present a live
delivery map and a live navigation surface during an active delivery. The map
is the driver's primary spatial workspace while a delivery is in progress: it
shows where the driver is, where they are going, what step they are on, and
what actions are available, while the backend remains the authority over the
delivery lifecycle.

The live map and navigation surface matter for NubeRush because of:

- **Driver situational awareness** — the driver must always know the current
  step, destination, and available actions at a glance during an active
  delivery.
- **Store pickup routing** — the driver must be routed to the correct store for
  pickup before any customer leg begins.
- **Customer delivery routing** — the driver must be routed to the
  backend-provided customer destination only after a backend-authorized pickup.
- **Restricted-product accountability** — regulated smoke-shop and vape orders
  require that arrival and completion stay backend-authorized, never decided by
  the map alone.
- **Proof / failure / return workflow support** — the map surfaces the route
  context for the proof, failed delivery, and return-to-store flows defined in
  Dr.1.0.H, without replacing them.
- **Safety access during active delivery** — emergency and support actions must
  remain reachable while the driver is navigating.
- **Support / admin visibility** — oversight observes route progress through
  backend-authorized events, not raw surveillance.
- **Future route intelligence** — the architecture leaves room for future ETA
  telemetry, geofence candidates, and route-deviation risk signals without
  committing to them now.
- **Uber Driver / Uber Eats inspired operational depth** — the live map adapts
  the proven operational depth of a mature driver platform to NubeRush's
  regulated-delivery model, as studied (not copied) per the contract lock.

## 3. Core Principles

- **Mobile displays route state; the backend authorizes lifecycle state.** The
  map renders the current backend-owned route state and proposes transitions;
  it never self-assigns lifecycle state.
- **The map is an operational surface, not a compliance authority.** Visual
  arrival, route progress, or step display never satisfies a compliance gate.
- **Driver location is privacy-sensitive.** Location is treated as sensitive
  data, minimized, and never continuously surveilled in the MVP.
- **Compliance-sensitive geofence decisions must be backend-authorized.** A
  geofence may suggest an arrival candidate; the backend validates whether the
  lifecycle transition is allowed.
- **No direct Store/Admin UI mutation from the map.** The map cannot write to
  Store or Admin state; oversight reads backend events.
- **Support/safety access must be available from the active map.** Safety
  actions remain reachable during navigation and map mode.
- **Route deviation detection is future.** No deviation enforcement, penalty, or
  cancellation exists in the MVP.
- **Internal turn-by-turn navigation is future.** The MVP hands off to external
  navigation apps; it does not embed a turn-by-turn engine.
- **CarPlay / Android Auto is future.** Not in the MVP scope.
- **Apple Maps / Google Maps / Waze handoff is likely MVP or early MVP.**
  External navigation handoff is the expected MVP navigation mechanism.
- **Restricted delivery cannot be completed from the map alone.** Completion
  requires the verification/proof flow and a backend transition.
- **Return-to-store route is a first-class route state.** It is modeled
  explicitly, not as an afterthought.
- **Audit events must be privacy-safe.** Map and route events carry minimal,
  redacted metadata and never raw sensitive location replay in the MVP.
- **Offline mode must not allow local override of restricted completion.** The
  map may degrade and queue non-sensitive actions, but compliance-sensitive
  completion always waits for backend acceptance.

## 4. Relationship to Prior Dr.1.0 Documents

This document builds on the prior Dr.1.0 subphases and does not restate or
replace them.

- **Dr.1.0.A — Contract lock** (`docs/dr.1.0-driver-app-contract-lock.md`):
  defines scope, boundaries, and the docs-only nature of Dr.1.0. The live map
  surface stays inside that boundary.
- **Dr.1.0.B — Uber feature adaptation**
  (`docs/dr.1.0-driver-feature-adaptation-matrix.md`): the live map adapts the
  active-delivery operational depth studied there to NubeRush's model.
- **Dr.1.0.C — Domain architecture**
  (`docs/dr.1.0-driver-domain-architecture.md`): the route state model here is a
  view onto the backend-owned delivery domain, not a parallel authority.
- **Dr.1.0.D — Screen inventory**
  (`docs/dr.1.0-driver-screen-inventory.md`): the active delivery map screen and
  its overlays map to the screen inventory.
- **Dr.1.0.E — User flows** (`docs/dr.1.0-driver-user-flows.md`): the map
  supports the pickup, delivery, failure, and return flows without changing
  them.
- **Dr.1.0.F — Backend gap map**
  (`docs/dr.1.0-driver-backend-gap-map.md`): the future backend capability map
  in Section 25 extends the gap map for route state and route telemetry.
- **Dr.1.0.G — Compliance / ID verification**
  (`docs/dr.1.0-driver-compliance-id-verification.md`): age/ID verification
  gates completion; the map never bypasses it.
- **Dr.1.0.H — Proof / failed delivery / return-to-store**
  (`docs/dr.1.0-driver-proof-failure-return.md`): the proof, failure, and return
  flows are authoritative; the map routes to them and reflects their state.

How the live map relates to these:

- **The live map supports the active delivery flow.** It is the spatial surface
  on which pickup, transit, arrival, and return are presented.
- **The live map does not replace the proof / failure / return flows.** Those
  flows from Dr.1.0.H remain the authority for completion and failure.
- **The live map does not bypass age/ID verification.** Restricted completion
  still depends on the Dr.1.0.G verification gate.
- **The live map routes to customer or store depending on backend-authorized
  state.** The active destination is chosen by the backend-owned route state,
  not by the map.
- **Map-based arrival may support, but not solely decide, compliance-sensitive
  state transitions.** Arrival candidates inform the backend; they do not
  finalize lifecycle state.

## 5. Live Map MVP Surface

The MVP live map surface is the set of elements shown during an active
delivery. Each element below states its purpose, MVP/Future classification,
backend dependency, mobile responsibility, privacy/compliance notes, and
Store/Admin visibility. Items are architectural candidates.

### 5.1 Current driver location display

- **Purpose:** show the driver their own position on the map.
- **MVP/Future:** MVP.
- **Backend dependency:** none for display; permission state may be a future
  backend candidate.
- **Mobile responsibility:** request location permission, render position, fail
  gracefully if denied.
- **Privacy/compliance:** location stays on-device for display; no continuous
  upload in the MVP.
- **Store/Admin visibility:** none directly; oversight sees route state events,
  not raw position.

### 5.2 Pickup / store destination

- **Purpose:** show the store the driver must reach to pick up.
- **MVP/Future:** MVP.
- **Backend dependency:** store destination provided by the backend.
- **Mobile responsibility:** render the store pin and store route context.
- **Privacy/compliance:** store address is operational data, shown only during
  the active assignment.
- **Store/Admin visibility:** Store sees "driver en route to store" as a backend
  event.

### 5.3 Customer destination

- **Purpose:** show the backend-provided customer/dropoff destination.
- **MVP/Future:** MVP.
- **Backend dependency:** customer destination provided by the backend; visible
  only during active delivery.
- **Mobile responsibility:** render the customer pin only after backend-
  authorized pickup.
- **Privacy/compliance:** customer location is sensitive; shown only during the
  active delivery and not retained on-device beyond it.
- **Store/Admin visibility:** Store sees only limited "en route to customer"
  status; Admin sees privacy-safe references.

### 5.4 Active route state

- **Purpose:** reflect the current backend-owned route state (Section 6).
- **MVP/Future:** MVP.
- **Backend dependency:** route state is backend-owned.
- **Mobile responsibility:** render the current state; never self-assign it.
- **Privacy/compliance:** state names are operational, not sensitive.
- **Store/Admin visibility:** via backend route events.

### 5.5 Current step overlay

- **Purpose:** present the current step and its actions (Section 7).
- **MVP/Future:** MVP.
- **Backend dependency:** step derives from backend-authorized route state.
- **Mobile responsibility:** render the correct overlay for the state.
- **Privacy/compliance:** overlay shows operational instructions only.
- **Store/Admin visibility:** indirect via state events.

### 5.6 Delivery status banner

- **Purpose:** give a persistent at-a-glance status during navigation.
- **MVP/Future:** MVP.
- **Backend dependency:** reflects backend route/delivery state.
- **Mobile responsibility:** keep the banner consistent with route state.
- **Privacy/compliance:** operational text only.
- **Store/Admin visibility:** indirect via state events.

### 5.7 ETA / distance display

- **Purpose:** give the driver an estimate of time and distance to destination.
- **MVP/Future:** MVP as estimate; backend route telemetry is future.
- **Backend dependency:** none required in MVP; future route telemetry candidate.
- **Mobile responsibility:** display as an estimate, never as a contract.
- **Privacy/compliance:** estimate only; no payout/penalty dependency.
- **Store/Admin visibility:** cautious, estimate-only language if shown later.

### 5.8 Open external navigation action

- **Purpose:** hand off to Apple Maps / Google Maps / Waze (Section 9).
- **MVP/Future:** MVP.
- **Backend dependency:** destination from backend.
- **Mobile responsibility:** open the chosen provider with the destination.
- **Privacy/compliance:** destination is shared with the external app the driver
  chooses; this is a handoff, not internal navigation.
- **Store/Admin visibility:** a handoff audit event (privacy-safe).

### 5.9 Call / message customer / store entry points where allowed

- **Purpose:** let the driver contact the store or customer where permitted.
- **MVP/Future:** MVP where contact is allowed by backend policy.
- **Backend dependency:** masked contact / allowed-contact policy from backend.
- **Mobile responsibility:** show contact only when the backend permits it.
- **Privacy/compliance:** contact must be masked/brokered per existing privacy
  rules; no raw customer contact data exposed beyond policy.
- **Store/Admin visibility:** contact attempts may be audited where required.

### 5.10 Support / safety access

- **Purpose:** keep emergency and support reachable during the active map
  (Section 18).
- **MVP/Future:** MVP for core access; richer safety sharing is future.
- **Backend dependency:** support routing; safety context sharing is future.
- **Mobile responsibility:** keep the action visible during navigation/map mode.
- **Privacy/compliance:** safety location sharing must be explicit, not hidden.
- **Store/Admin visibility:** safety events surface to Admin via backend events.

### 5.11 Permission recovery UI

- **Purpose:** guide the driver to restore location permission (Section 13).
- **MVP/Future:** MVP.
- **Backend dependency:** permission state recording is a future candidate.
- **Mobile responsibility:** detect denied/restricted state, present recovery.
- **Privacy/compliance:** privacy-first language; no hidden tracking.
- **Store/Admin visibility:** a permission-denied event is a future candidate.

### 5.12 Network recovery UI

- **Purpose:** handle degraded or lost connectivity gracefully (Section 14).
- **MVP/Future:** MVP.
- **Backend dependency:** reconciliation on reconnect.
- **Mobile responsibility:** show offline banner, retry CTA, stale warning.
- **Privacy/compliance:** queued actions must exclude restricted completion.
- **Store/Admin visibility:** stuck/offline route state is an Admin signal.

### 5.13 Return-to-store route mode

- **Purpose:** present the return route as a first-class mode (Section 12).
- **MVP/Future:** MVP route mode.
- **Backend dependency:** return-required state from backend.
- **Mobile responsibility:** switch destination to store, present return steps.
- **Privacy/compliance:** return protects restricted inventory accountability.
- **Store/Admin visibility:** Store sees "driver returning to store".

### 5.14 Excluded from the MVP surface

- **No internal turn-by-turn engine.** External handoff only.
- **No route deviation enforcement.** Future and review-gated.
- **No local geofence-only completion.** Backend authorizes transitions.
- **No Store/Admin mutation.** The map never writes Store/Admin state.

## 6. Route State Model

The following are **candidate route states**, finalized in a later Dr.1.x
phase. Route state is backend-owned; the map reflects it and proposes
transitions through backend-authorized actions. "Mobile behavior" describes
what the app presents or submits, never a state it can self-assign.

### no_active_route

- **Meaning:** no active delivery; the map is idle or not shown.
- **Who/what can set it:** backend (default / after route close).
- **Allowed next states:** `route_to_store_pending`.
- **Mobile behavior:** no active map context; standard non-delivery UI.
- **Backend authority:** backend assigns the next active route.
- **Store/Admin visibility:** no active route for this driver.
- **Audit implication:** none until a route starts.

### route_to_store_pending

- **Meaning:** a store pickup route is assigned but not yet started.
- **Who/what can set it:** backend (on assignment).
- **Allowed next states:** `navigating_to_store`, `support_review_route_locked`.
- **Mobile behavior:** show store destination and a start/navigate action.
- **Backend authority:** backend owns assignment.
- **Store/Admin visibility:** Store sees an assigned, pending pickup.
- **Audit implication:** route assignment context.

### navigating_to_store

- **Meaning:** the driver is en route to the store for pickup.
- **Who/what can set it:** backend (on start), reflecting driver action.
- **Allowed next states:** `arrived_at_store_candidate`,
  `support_review_route_locked`, `offline_route_state_pending_sync`.
- **Mobile behavior:** show store route, ETA/distance, external nav handoff.
- **Backend authority:** backend records route start.
- **Store/Admin visibility:** "driver en route to store".
- **Audit implication:** `route_to_store_started`.

### arrived_at_store_candidate

- **Meaning:** the driver appears to have arrived at the store (manual or future
  geofence candidate).
- **Who/what can set it:** mobile proposes; backend validates the candidate.
- **Allowed next states:** `pickup_confirmed_route_ready`,
  `support_review_route_locked`.
- **Mobile behavior:** present arrival/pickup step; await backend.
- **Backend authority:** backend validates arrival as a candidate, not a final
  transition.
- **Store/Admin visibility:** "driver arrived at store (candidate)".
- **Audit implication:** `arrived_at_store_candidate`.

### pickup_confirmed_route_ready

- **Meaning:** backend-authorized pickup is confirmed; customer route can begin.
- **Who/what can set it:** backend (on confirmed pickup per Dr.1.0.H).
- **Allowed next states:** `route_to_customer_pending`.
- **Mobile behavior:** close store route; prepare customer route.
- **Backend authority:** pickup confirmation is backend-owned.
- **Store/Admin visibility:** "pickup confirmed".
- **Audit implication:** `pickup_route_closed`.

### route_to_customer_pending

- **Meaning:** customer route assigned but not yet started.
- **Who/what can set it:** backend.
- **Allowed next states:** `navigating_to_customer`,
  `support_review_route_locked`.
- **Mobile behavior:** show customer destination and a start/navigate action.
- **Backend authority:** backend provides the customer destination.
- **Store/Admin visibility:** Store sees limited "out for delivery".
- **Audit implication:** route-to-customer assignment context.

### navigating_to_customer

- **Meaning:** the driver is en route to the customer.
- **Who/what can set it:** backend (on start), reflecting driver action.
- **Allowed next states:** `arrived_at_customer_candidate`,
  `failed_delivery_route_closed`, `return_to_store_required`,
  `support_review_route_locked`, `offline_route_state_pending_sync`.
- **Mobile behavior:** show customer route, ETA/distance, external nav handoff.
- **Backend authority:** backend records route start.
- **Store/Admin visibility:** limited "en route to customer".
- **Audit implication:** `route_to_customer_started`.

### arrived_at_customer_candidate

- **Meaning:** the driver appears to have arrived at the customer (manual or
  future geofence candidate).
- **Who/what can set it:** mobile proposes; backend validates the candidate.
- **Allowed next states:** `verification_blocking_completion`,
  `proof_blocking_completion`, `failed_delivery_route_closed`,
  `return_to_store_required`.
- **Mobile behavior:** present arrival; route into verification/proof per
  Dr.1.0.G/H.
- **Backend authority:** arrival is a candidate, not a completion.
- **Store/Admin visibility:** "arrived at customer (candidate)".
- **Audit implication:** `arrived_at_customer_candidate`.

### verification_blocking_completion

- **Meaning:** age/ID verification (Dr.1.0.G) must pass before completion.
- **Who/what can set it:** backend.
- **Allowed next states:** `proof_blocking_completion`,
  `failed_delivery_route_closed`, `return_to_store_required`.
- **Mobile behavior:** present the verification flow; block completion CTA.
- **Backend authority:** verification result is backend-owned.
- **Store/Admin visibility:** "verification in progress / required".
- **Audit implication:** verification events per Dr.1.0.G.

### proof_blocking_completion

- **Meaning:** proof of delivery (Dr.1.0.H) is required before completion.
- **Who/what can set it:** backend (after verification passes for restricted).
- **Allowed next states:** `delivery_completed_route_closed`,
  `failed_delivery_route_closed`, `return_to_store_required`.
- **Mobile behavior:** present the proof flow; block completion until accepted.
- **Backend authority:** proof acceptance is backend-owned.
- **Store/Admin visibility:** "proof required / in progress".
- **Audit implication:** proof events per Dr.1.0.H.

### delivery_completed_route_closed

- **Meaning:** delivery is completed and the route is closed.
- **Who/what can set it:** backend (on accepted completion).
- **Allowed next states:** `no_active_route`.
- **Mobile behavior:** close the route; show completion summary.
- **Backend authority:** completion is a backend transition, not a local state.
- **Store/Admin visibility:** "delivered".
- **Audit implication:** completion events per Dr.1.0.H.

### failed_delivery_route_closed

- **Meaning:** delivery failed; the customer route is closed.
- **Who/what can set it:** backend (on accepted failure).
- **Allowed next states:** `return_to_store_required`, `no_active_route`.
- **Mobile behavior:** close customer route; route to failure/return flow.
- **Backend authority:** failure acceptance is backend-owned.
- **Store/Admin visibility:** "failed delivery".
- **Audit implication:** failure events per Dr.1.0.H.

### return_to_store_required

- **Meaning:** undeliverable/restricted order must return to the store.
- **Who/what can set it:** backend (compliance failure, failed delivery, or
  return-required trigger per Dr.1.0.H).
- **Allowed next states:** `navigating_return_to_store`.
- **Mobile behavior:** switch active destination to the store; present return
  route mode.
- **Backend authority:** return requirement is backend-owned.
- **Store/Admin visibility:** "return required".
- **Audit implication:** `return_route_started` on transition to navigation.

### navigating_return_to_store

- **Meaning:** the driver is en route back to the store with the order.
- **Who/what can set it:** backend (on return route start).
- **Allowed next states:** `arrived_at_store_for_return_candidate`,
  `support_review_route_locked`, `offline_route_state_pending_sync`.
- **Mobile behavior:** show return route, ETA/distance, external nav handoff.
- **Backend authority:** backend records return route start.
- **Store/Admin visibility:** "driver returning to store".
- **Audit implication:** `return_route_started`.

### arrived_at_store_for_return_candidate

- **Meaning:** the driver appears to have arrived back at the store (manual or
  future geofence candidate).
- **Who/what can set it:** mobile proposes; backend validates the candidate.
- **Allowed next states:** `return_handoff_pending`.
- **Mobile behavior:** present return handoff step; await store confirmation.
- **Backend authority:** arrival is a candidate.
- **Store/Admin visibility:** "driver arrived for return (candidate)".
- **Audit implication:** `arrived_at_store_for_return_candidate`.

### return_handoff_pending

- **Meaning:** the order is being handed back; awaiting store confirmation.
- **Who/what can set it:** backend.
- **Allowed next states:** `return_confirmed_route_closed`,
  `support_review_route_locked`.
- **Mobile behavior:** present handoff step; driver cannot self-close.
- **Backend authority:** store confirmation closes the return (Dr.1.0.H).
- **Store/Admin visibility:** "return pending confirmation".
- **Audit implication:** return handoff events per Dr.1.0.H.

### return_confirmed_route_closed

- **Meaning:** the store confirmed the return; the route is closed.
- **Who/what can set it:** backend (on store-confirmed return).
- **Allowed next states:** `no_active_route`.
- **Mobile behavior:** close the return route; show summary.
- **Backend authority:** return closure is backend-owned.
- **Store/Admin visibility:** "return confirmed".
- **Audit implication:** `return_route_closed`.

### support_review_route_locked

- **Meaning:** the route is locked pending support/safety review.
- **Who/what can set it:** backend (support/safety escalation).
- **Allowed next states:** prior route state on release, or a backend-directed
  state.
- **Mobile behavior:** present support/review context; restrict route actions.
- **Backend authority:** lock/release is backend-owned.
- **Store/Admin visibility:** "route under review" as an Admin signal.
- **Audit implication:** support/safety events.

### offline_route_state_pending_sync

- **Meaning:** the device is offline; route state is awaiting reconciliation.
- **Who/what can set it:** mobile (local degraded state); reconciled by backend.
- **Allowed next states:** the backend-reconciled state on reconnect.
- **Mobile behavior:** show offline banner, stale warning, retry; block
  restricted completion.
- **Backend authority:** backend reconciles the true state on reconnect.
- **Store/Admin visibility:** "stuck / offline route" as an Admin signal.
- **Audit implication:** `network_lost_during_route`, `route_state_reconciled`.

## 7. Current Step Overlay Architecture

The current step overlay sits on top of the active map and presents the single
current step, its actions, and its constraints. Overlay states derive from the
backend-authorized route state and never self-advance. CTAs that would change
lifecycle state submit a backend-authorized action.

### Pickup step

- **Display purpose:** prepare the driver to head to the store.
- **Primary CTA:** start navigation to store.
- **Secondary CTA:** view order/store details.
- **Disabled actions:** customer route, completion.
- **Backend dependency:** store destination, assignment.
- **Compliance/safety notes:** support/safety remains accessible.

### En route to store

- **Display purpose:** guide the driver to the store.
- **Primary CTA:** open external navigation.
- **Secondary CTA:** contact store where allowed.
- **Disabled actions:** customer route, completion.
- **Backend dependency:** store route context.
- **Compliance/safety notes:** ETA shown as estimate only.

### Arrived at store

- **Display purpose:** confirm arrival candidate and prepare pickup handoff.
- **Primary CTA:** confirm arrival / begin pickup handoff (candidate).
- **Secondary CTA:** report pickup issue.
- **Disabled actions:** customer route until pickup is backend-confirmed.
- **Backend dependency:** arrival candidate validation.
- **Compliance/safety notes:** arrival does not confirm pickup.

### Pickup verification / store handoff

- **Display purpose:** complete the store handoff per Dr.1.0.H.
- **Primary CTA:** submit pickup handoff (backend-authorized).
- **Secondary CTA:** report missing/damaged order.
- **Disabled actions:** customer route until pickup is confirmed.
- **Backend dependency:** pickup confirmation.
- **Compliance/safety notes:** restricted order custody begins here.

### En route to customer

- **Display purpose:** guide the driver to the customer.
- **Primary CTA:** open external navigation.
- **Secondary CTA:** contact customer where allowed.
- **Disabled actions:** completion until verification/proof.
- **Backend dependency:** customer destination, route start.
- **Compliance/safety notes:** ETA estimate only; contact masked per policy.

### Arrival at customer

- **Display purpose:** confirm arrival candidate at the customer.
- **Primary CTA:** confirm arrival (candidate) / begin completion flow.
- **Secondary CTA:** report delivery issue.
- **Disabled actions:** completion until verification/proof pass.
- **Backend dependency:** arrival candidate validation.
- **Compliance/safety notes:** arrival never completes a restricted delivery.

### Age/ID verification required

- **Display purpose:** route the driver into the Dr.1.0.G verification flow.
- **Primary CTA:** start verification.
- **Secondary CTA:** report verification problem / fail path.
- **Disabled actions:** completion, proof until verification passes.
- **Backend dependency:** verification gate (Dr.1.0.G).
- **Compliance/safety notes:** failure routes to failure/return.

### Proof required

- **Display purpose:** route the driver into the Dr.1.0.H proof flow.
- **Primary CTA:** start proof capture.
- **Secondary CTA:** report inability to complete.
- **Disabled actions:** local completion without backend acceptance.
- **Backend dependency:** proof gate (Dr.1.0.H).
- **Compliance/safety notes:** proof never substitutes for verification.

### Failed delivery action required

- **Display purpose:** route into the Dr.1.0.H failed delivery flow.
- **Primary CTA:** record failure reason (backend-authorized).
- **Secondary CTA:** contact support.
- **Disabled actions:** completion.
- **Backend dependency:** failure acceptance.
- **Compliance/safety notes:** restricted failure typically requires return.

### Return-to-store required

- **Display purpose:** announce that the order must return to the store.
- **Primary CTA:** start return route.
- **Secondary CTA:** contact support.
- **Disabled actions:** customer completion.
- **Backend dependency:** return-required state.
- **Compliance/safety notes:** protects restricted inventory accountability.

### En route back to store

- **Display purpose:** guide the driver back to the store.
- **Primary CTA:** open external navigation to store.
- **Secondary CTA:** contact store / support.
- **Disabled actions:** customer completion.
- **Backend dependency:** return route context.
- **Compliance/safety notes:** ETA estimate only.

### Return handoff required

- **Display purpose:** complete the return handoff per Dr.1.0.H.
- **Primary CTA:** submit return handoff (backend-authorized).
- **Secondary CTA:** report return issue / escalate.
- **Disabled actions:** driver self-closing the return.
- **Backend dependency:** store confirmation closes the return.
- **Compliance/safety notes:** store confirmation is mandatory.

### Support / safety state

- **Display purpose:** present support/safety context when invoked or locked.
- **Primary CTA:** access support / emergency action.
- **Secondary CTA:** report specific incident type.
- **Disabled actions:** route actions while review-locked, per backend.
- **Backend dependency:** support routing; lock/release.
- **Compliance/safety notes:** safety actions take precedence.

### Offline / retry state

- **Display purpose:** present degraded connectivity and recovery.
- **Primary CTA:** retry / reconnect.
- **Secondary CTA:** continue external navigation outside the app.
- **Disabled actions:** restricted completion until backend acceptance.
- **Backend dependency:** reconciliation on reconnect.
- **Compliance/safety notes:** no local override of compliance state.

## 8. ETA and Distance Architecture

ETA and distance are driver guidance, not commitments.

- **ETA/distance display as driver guidance.** The map may show an ETA and
  distance so the driver can plan, but these are aids, not promises.
- **External navigation provider may own live turn-by-turn ETA.** When the
  driver hands off to Apple Maps / Google Maps / Waze, that app owns the live
  turn-by-turn ETA; the NubeRush app does not compute turn-by-turn timing in the
  MVP.
- **Backend may receive route metadata or status timestamps in the future.**
  Future route telemetry (status timestamps, coarse route metadata) is a
  candidate, not an MVP feature.
- **ETA/distance should be treated as an estimate, not a contract.** No SLA,
  payout, or penalty is derived from displayed ETA.
- **Store/Admin visibility should use cautious language.** Any future ETA shown
  to Store/Admin should be framed as an estimate that may be stale.
- **Stale ETA handling.** When data is old or connectivity is poor, the ETA
  should be marked stale rather than shown as authoritative.
- **Network loss behavior.** On connectivity loss, ETA/distance may freeze or
  hide; the offline banner takes precedence.
- **Customer/store communication boundaries.** ETA is not auto-promised to the
  customer; any customer-facing ETA is governed by separate backend policy, not
  the driver map.
- **No pricing/payout dependency.** ETA/distance never affects pricing or payout
  in this architecture.
- **No automatic penalty based only on ETA.** A missed estimate alone never
  triggers a penalty.

Approach and future direction:

- **MVP approach:** display estimate from the device/route context; hand off
  live timing to the external navigation app.
- **Future backend route telemetry:** coarse status timestamps and route
  metadata, privacy-reviewed, as a candidate.
- **Future admin/store ETA display:** estimate-only, cautious-language display
  as a candidate.
- **Privacy considerations:** ETA telemetry must avoid raw continuous location;
  minimize and review before storage.

## 9. Navigation Provider Handoff

The MVP navigation mechanism is a handoff to an external navigation app. No
embedded SDK and no internal turn-by-turn engine are required in the MVP.

### Apple Maps

- **Use case:** native navigation on iOS.
- **MVP/Future:** likely MVP / early MVP.
- **Required input:** destination coordinates/address from backend.
- **Mobile behavior:** open Apple Maps with the destination.
- **Backend dependency:** destination only.
- **Privacy note:** destination shared with Apple Maps on handoff.
- **Failure handling:** if unavailable, fall back to another provider or web map
  (future fallback).
- **Platform notes:** iOS default; availability assumed on Apple devices.

### Google Maps

- **Use case:** cross-platform navigation.
- **MVP/Future:** likely MVP / early MVP.
- **Required input:** destination coordinates/address from backend.
- **Mobile behavior:** open Google Maps with the destination.
- **Backend dependency:** destination only.
- **Privacy note:** destination shared with Google Maps on handoff.
- **Failure handling:** fall back if the app is not installed.
- **Platform notes:** available on iOS and Android when installed.

### Waze

- **Use case:** driver-preferred routing.
- **MVP/Future:** MVP or early MVP candidate.
- **Required input:** destination coordinates/address from backend.
- **Mobile behavior:** open Waze with the destination.
- **Backend dependency:** destination only.
- **Privacy note:** destination shared with Waze on handoff.
- **Failure handling:** fall back if Waze is not installed.
- **Platform notes:** availability depends on installation.

Cross-cutting handoff notes:

- **Default provider preference as a future setting.** A driver-selectable
  default provider is a future candidate.
- **Fallback behavior if the provider app is unavailable.** Offer the next
  available provider when the chosen one is missing.
- **Browser/web map fallback as a future option.** A web map link is a future
  fallback candidate.
- **No embedded SDK requirement in the MVP.** Handoff only.
- **No internal turn-by-turn in the MVP.** The external app owns turn-by-turn.

## 10. Customer Route Architecture

- **Route starts only after pickup is confirmed.** The customer leg begins from
  `pickup_confirmed_route_ready`, never before.
- **Destination is the backend-provided customer/dropoff destination.** The map
  does not invent or override the destination.
- **The customer route is visible only during active delivery.** It is not shown
  before pickup or after route close.
- **Restricted completion requires the verification/proof flow, not map arrival
  alone.** Arrival candidates do not complete the delivery.
- **Contact the customer from the route where allowed.** Contact is masked and
  policy-gated.
- **Support/safety access remains visible.** Safety actions persist during the
  customer leg.
- **Arrival candidate can be detected by driver action or future geofence.**
  Manual arrival confirmation may be MVP; geofence arrival is future.
- **Backend confirms the lifecycle transition.** Arrival candidates are proposed
  to the backend.
- **The map cannot complete the delivery alone.** Completion is a backend
  transition.
- **The route closes after a backend-authorized completion / failure /
  return-required transition.** Route closure follows the backend.

## 11. Store Route Architecture

- **Route to store for pickup.** The store leg begins from
  `route_to_store_pending`/`navigating_to_store`.
- **Store destination from backend.** The map renders the backend-provided store
  location.
- **Arrival candidate.** Arrival at the store is a candidate, validated by the
  backend.
- **Pickup handoff dependency.** The customer route depends on a
  backend-confirmed pickup handoff (Dr.1.0.H).
- **Store contact access.** The driver may contact the store where allowed.
- **Pickup issue path.** A pickup issue routes to the appropriate Dr.1.0.H
  handling.
- **Missing/damaged order path.** Missing or damaged order handling follows
  Dr.1.0.H.
- **Support escalation.** Support/safety remains accessible from the store leg.
- **Route to customer begins only after backend-authorized pickup
  confirmation.** No customer leg before confirmation.
- **Store/Admin visibility through backend events.** Store sees pickup-related
  status via backend events, not direct map state.

## 12. Return-to-Store Route Architecture

- **Return route starts from a failed / restricted / return-required state.**
  Triggered by `return_to_store_required` per Dr.1.0.H.
- **The original customer route ends.** The customer leg is closed when return
  begins.
- **The store becomes the active destination.** The map switches the active
  destination to the store.
- **The return route is first-class, not an afterthought.** It has its own route
  states and overlay steps.
- **External navigation handoff to the store.** The driver may hand off to an
  external provider for the return leg.
- **The driver cannot complete the original order while returning.** Customer
  completion is disabled during return.
- **Return handoff required.** The order must be handed back at the store.
- **The store must confirm the return.** Driver self-closing is not allowed
  (Dr.1.0.H).
- **Support escalation if the return cannot be completed.** Support handles
  unresolvable returns.
- **Inventory safety implications.** Return protects restricted-product
  inventory accountability.
- **The backend closes the return route after confirmation or exception.**
  Closure is backend-owned.

## 13. GPS Permission Recovery

- **Location permission is required for the active map experience.** The live
  map and own-position display depend on location permission.
- **Approximate vs precise location considerations.** Precise location improves
  routing; approximate may degrade the experience. The choice and its handling
  are a future review item.
- **Permission denied state.** When denied, the map presents a recovery path and
  degrades gracefully.
- **Permission restricted state.** Device-restricted permission is handled with
  clear guidance.
- **Background/foreground location considerations.** The MVP focuses on
  foreground use; background location is a future, policy-sensitive item.
- **Recovery instructions.** Clear steps to re-enable permission in device
  settings.
- **The driver can still use external navigation manually where possible.** Even
  without in-app location, the driver can open an external navigation app.
- **Restricted workflow limitations if location is unavailable.** Some
  location-dependent candidates (e.g. geofence arrival) are unavailable; manual
  flows still apply, and restricted completion remains backend-gated.
- **The backend receives permission state as a future candidate.** Recording
  permission state is future.
- **No hidden tracking.** Location is never collected without driver awareness.
- **Privacy-first language.** Recovery UI uses transparent, privacy-first
  language.

Behavior summary:

- **MVP behavior:** foreground location for display and manual arrival; external
  navigation handoff; graceful denial recovery.
- **Future background location behavior:** policy-sensitive, legally reviewed
  candidate only.
- **App Store / Play Store policy sensitivity as a future review item.**
  Background and precise location must be reviewed against store policy.

## 14. Network Recovery

- **The map may degrade during poor connectivity.** Tiles, position, and ETA may
  be limited offline.
- **Cached active destination as a future candidate.** Caching the current
  destination for offline display is a future candidate.
- **Queued non-sensitive actions.** Non-compliance actions (e.g. a navigation
  handoff intent) may queue.
- **Restricted completion blocked until backend acceptance.** Compliance-
  sensitive completion is never accepted offline.
- **Offline banner.** A clear offline indicator is shown.
- **Retry CTA.** A retry/reconnect action is provided.
- **Stale route state warning.** Route state shown while offline is marked
  potentially stale.
- **External navigation may continue outside the app.** The handed-off provider
  may keep navigating during a NubeRush-app outage.
- **Backend reconciliation on reconnect.** The backend reconciles the true route
  state on reconnect.
- **Duplicate action prevention.** Idempotency prevents duplicate route actions
  (Section 21).
- **Audit replay events.** Queued actions and their replay are auditable
  (`offline_route_action_queued`, `offline_route_action_replayed`).

## 15. Geofence Arrival Checks

Geofence arrival is a future, backend-authorized feature. The MVP may rely on
manual driver arrival confirmation.

- **`arrived_at_store_candidate`** — geofence may suggest store arrival.
- **`arrived_at_customer_candidate`** — geofence may suggest customer arrival.
- **`arrived_at_store_for_return_candidate`** — geofence may suggest return
  arrival.
- **Geofence only suggests candidate arrival.** It never finalizes a transition.
- **The backend validates the allowed lifecycle transition.** Candidates are
  validated server-side.
- **Driver manual arrival confirmation may be MVP.** Manual confirmation is the
  likely MVP path; geofence is future.
- **GPS spoofing / fraud considerations.** Geofence is vulnerable to spoofing;
  fraud handling is a future review item.
- **Privacy considerations.** Geofence evaluation must minimize location data and
  avoid continuous tracking.
- **Restricted delivery cannot complete by geofence alone.** Geofence never
  satisfies the verification/proof gates.
- **Store/Admin visibility as a backend event.** Candidates surface via backend
  events.
- **Future legal/product review required.** Geofence must be legally and product
  reviewed before implementation.

## 16. Route Deviation Future

Route deviation detection is future only. No deviation feature exists in the
MVP.

- **Purpose:** detect potential route anomalies for safety and risk awareness.
- **Deviation from the external navigation route as a candidate signal.**
- **Long stop / unexpected stop candidate.**
- **Wrong direction candidate.**
- **Support/safety trigger candidate.**
- **Fraud/risk signal candidate.**
- **Privacy risk:** deviation detection implies tracking; privacy review
  required.
- **False positive risk:** legitimate stops can look like deviations.
- **No automatic penalties in the MVP.**
- **No automatic delivery cancellation.**
- **Backend review required.** Any deviation signal routes to backend/Admin
  review, never automated action.
- **Admin visibility as a risk signal only.** Surfaced as a signal, not a
  verdict.

## 17. Legal / Restricted Zone Warnings

Restricted-zone warnings are backend-provided and display-only on mobile. The
mobile app makes no legal decision on its own.

- **Restricted delivery zones.** Backend-provided zone warnings may be displayed.
- **School / sensitive area warnings as a future candidate.**
- **State/local restriction warnings as a future candidate.**
- **Unsafe area warning as a future candidate.**
- **Store-configured delivery boundary as a future candidate.**
- **Backend-provided warnings.** Warning content and triggers come from the
  backend.
- **Mobile display only.** The map displays warnings; it does not evaluate legal
  rules.
- **Driver acknowledgement.** The driver may be required to acknowledge a
  warning (`legal_zone_warning_acknowledged`).
- **Support escalation.** Warnings may route to support where needed.
- **Delivery block if the backend requires it.** The backend, not the map, can
  block a delivery for a restricted zone.
- **No mobile-only legal decision.** The map never decides legality locally.

## 18. Support and Safety Access From Map

Support and safety must remain reachable during active navigation and map mode.

- **Emergency button access.** A prominent emergency action stays available.
- **Call 911 option as a future/native action.** A native emergency-call path is
  a future candidate.
- **Contact support.** In-app support contact is available.
- **Report unsafe location.**
- **Report threatening customer.**
- **Report accident.**
- **Report vehicle issue.**
- **Cancel/escalate for safety.** Safety escalation can lock the route
  (`support_review_route_locked`).
- **Share current location with support/admin as a future candidate.** Explicit,
  not hidden.
- **Share active route with support/admin as a future candidate.** Explicit,
  scoped to the active delivery.
- **Keep safety actions accessible during active navigation/map mode.** Safety
  is never buried behind navigation.
- **Audit events.** Safety/support access emits audit events
  (`support_accessed_from_map`, `safety_event_started_from_map`).
- **Backend authority.** Support/safety routing and route locking are
  backend-owned.
- **Privacy boundaries.** Any safety location sharing is explicit and scoped.

## 19. Store/Admin Visibility

Visibility comes from backend-authorized events. Neither the map nor the panels
read raw continuous location in the MVP.

### Store visibility

- driver en route to store
- arrived at store candidate
- pickup issue
- driver en route to customer as a limited status
- failed delivery
- return required
- driver returning to store
- return arrival candidate
- return pending confirmation
- return confirmed / exception

### Admin visibility

- active route state
- route timeline
- driver/order/store/customer references, privacy-safe
- support/safety events
- stuck/offline route state
- return exceptions
- restricted-zone warnings
- audit timeline
- no raw continuous surveillance in the MVP
- no unrestricted location replay in the MVP

## 20. Audit Events

Audit events are backend-owned and privacy-safe. Names are candidates,
finalized in a later Dr.1.x phase. "Forbidden metadata" never appears in an
event, consistent with the privacy boundaries in Section 22.

### map_opened_for_active_delivery

- **Trigger:** driver opens the live map for an active delivery.
- **Actor:** driver (via app), recorded by backend.
- **Required metadata:** delivery/route reference, route state.
- **Forbidden metadata:** raw continuous location, customer PII.
- **Store/Admin visibility:** Admin timeline.
- **Privacy/compliance:** confirms map context, not a location trace.

### navigation_handoff_requested

- **Trigger:** driver requests external navigation.
- **Actor:** driver.
- **Required metadata:** route reference, destination type (store/customer).
- **Forbidden metadata:** raw coordinates beyond what policy allows, PII.
- **Store/Admin visibility:** Admin timeline.
- **Privacy/compliance:** handoff intent only.

### navigation_provider_selected

- **Trigger:** driver selects Apple Maps / Google Maps / Waze.
- **Actor:** driver.
- **Required metadata:** provider name, route reference.
- **Forbidden metadata:** location trace, PII.
- **Store/Admin visibility:** Admin timeline.
- **Privacy/compliance:** provider choice only.

### route_to_store_started

- **Trigger:** store leg starts.
- **Actor:** backend (reflecting driver action).
- **Required metadata:** route reference, store reference.
- **Forbidden metadata:** continuous location, PII.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance:** leg start, not a trace.

### arrived_at_store_candidate

- **Trigger:** store arrival candidate proposed.
- **Actor:** mobile proposes; backend records.
- **Required metadata:** route reference, candidate source (manual/geofence).
- **Forbidden metadata:** raw location history.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance:** candidate, not a confirmed arrival.

### pickup_route_closed

- **Trigger:** pickup confirmed; store leg closes.
- **Actor:** backend.
- **Required metadata:** route reference.
- **Forbidden metadata:** PII.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance:** leg closure.

### route_to_customer_started

- **Trigger:** customer leg starts after confirmed pickup.
- **Actor:** backend.
- **Required metadata:** route reference.
- **Forbidden metadata:** customer PII beyond policy, continuous location.
- **Store/Admin visibility:** Store limited; Admin.
- **Privacy/compliance:** leg start.

### arrived_at_customer_candidate

- **Trigger:** customer arrival candidate proposed.
- **Actor:** mobile proposes; backend records.
- **Required metadata:** route reference, candidate source.
- **Forbidden metadata:** raw location history, customer PII.
- **Store/Admin visibility:** Admin; Store limited.
- **Privacy/compliance:** candidate only.

### return_route_started

- **Trigger:** return-to-store route starts.
- **Actor:** backend.
- **Required metadata:** route reference, return reason category.
- **Forbidden metadata:** PII.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance:** return accountability.

### arrived_at_store_for_return_candidate

- **Trigger:** return arrival candidate proposed.
- **Actor:** mobile proposes; backend records.
- **Required metadata:** route reference, candidate source.
- **Forbidden metadata:** raw location history.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance:** candidate only.

### return_route_closed

- **Trigger:** store-confirmed return closes the route.
- **Actor:** backend.
- **Required metadata:** route reference, outcome.
- **Forbidden metadata:** PII.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance:** return closure.

### gps_permission_denied

- **Trigger:** location permission denied/restricted.
- **Actor:** mobile; backend records (future candidate).
- **Required metadata:** route reference, permission state.
- **Forbidden metadata:** location data.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** state only, no location.

### gps_permission_recovered

- **Trigger:** permission restored.
- **Actor:** mobile; backend records (future candidate).
- **Required metadata:** route reference, permission state.
- **Forbidden metadata:** location data.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** state only.

### network_lost_during_route

- **Trigger:** connectivity lost during a route.
- **Actor:** mobile; reconciled by backend.
- **Required metadata:** route reference, timestamp.
- **Forbidden metadata:** location trace, PII.
- **Store/Admin visibility:** Admin signal (stuck/offline).
- **Privacy/compliance:** connectivity state.

### network_recovered_during_route

- **Trigger:** connectivity restored.
- **Actor:** mobile; reconciled by backend.
- **Required metadata:** route reference, timestamp.
- **Forbidden metadata:** location trace, PII.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** connectivity state.

### route_state_reconciled

- **Trigger:** backend reconciles route state on reconnect.
- **Actor:** backend.
- **Required metadata:** route reference, reconciled state.
- **Forbidden metadata:** PII.
- **Store/Admin visibility:** Admin timeline.
- **Privacy/compliance:** reconciliation record.

### support_accessed_from_map

- **Trigger:** driver opens support from the active map.
- **Actor:** driver.
- **Required metadata:** route reference.
- **Forbidden metadata:** unrelated PII.
- **Store/Admin visibility:** Admin.
- **Privacy/compliance:** support access record.

### safety_event_started_from_map

- **Trigger:** driver starts a safety action from the map.
- **Actor:** driver.
- **Required metadata:** route reference, safety category.
- **Forbidden metadata:** unrelated PII.
- **Store/Admin visibility:** Admin (priority).
- **Privacy/compliance:** safety record; location sharing only if explicit.

### legal_zone_warning_displayed

- **Trigger:** a backend-provided zone warning is shown.
- **Actor:** mobile (display); backend originates.
- **Required metadata:** route reference, warning type.
- **Forbidden metadata:** PII.
- **Store/Admin visibility:** Admin.
- **Privacy/compliance:** display record.

### legal_zone_warning_acknowledged

- **Trigger:** driver acknowledges a zone warning.
- **Actor:** driver.
- **Required metadata:** route reference, warning type.
- **Forbidden metadata:** PII.
- **Store/Admin visibility:** Admin.
- **Privacy/compliance:** acknowledgement record.

### route_deviation_detected_future

- **Trigger:** future deviation signal (future only).
- **Actor:** backend (future).
- **Required metadata:** route reference, signal type.
- **Forbidden metadata:** raw continuous location beyond review policy.
- **Store/Admin visibility:** Admin risk signal only.
- **Privacy/compliance:** future, review-gated.

### offline_route_action_queued

- **Trigger:** a non-sensitive route action is queued offline.
- **Actor:** mobile.
- **Required metadata:** route reference, action type, idempotency key.
- **Forbidden metadata:** restricted completion payloads.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** queue record.

### offline_route_action_replayed

- **Trigger:** a queued action is replayed on reconnect.
- **Actor:** mobile/backend.
- **Required metadata:** route reference, action type, idempotency key.
- **Forbidden metadata:** restricted completion payloads.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** replay record.

### duplicate_route_action_rejected

- **Trigger:** a duplicate route action is rejected by idempotency.
- **Actor:** backend.
- **Required metadata:** route reference, idempotency key.
- **Forbidden metadata:** PII.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** dedup record.

## 21. Idempotency and Offline Behavior

- **Idempotency keys for map route actions.** Each route action carries an
  idempotency key so retries are safe.
- **Duplicate arrival taps.** Repeated arrival confirmations resolve to one
  candidate, not many.
- **Duplicate navigation handoffs.** Repeated handoff requests do not create
  duplicate state.
- **Duplicate route-state submissions.** The backend deduplicates repeated
  submissions.
- **Queued route actions.** Non-sensitive actions may queue offline and replay
  on reconnect.
- **Restricted completion cannot be accepted locally.** Compliance-sensitive
  completion always waits for backend acceptance.
- **Backend state reconciliation.** The backend reconciles the true route state
  on reconnect.
- **Stale route state handling.** Stale local state is marked and superseded by
  backend reconciliation.
- **Offline route action audit.** Queue and replay are audited.
- **No local override of route lifecycle.** The map cannot advance lifecycle
  state on its own.
- **No local override of compliance/proof/return state.** Verification, proof,
  and return state are never finalized locally.

## 22. Privacy and Location Data Boundaries

- **Location is sensitive.** Treated as sensitive data throughout.
- **MVP should avoid raw continuous location replay unless legally/product
  approved.** No continuous trace storage or replay in the MVP without review.
- **Only active delivery route context should be visible.** Visibility is scoped
  to the active delivery.
- **Location events should be minimized.** Capture and emit the minimum needed.
- **No hidden tracking.** Location is never collected without driver awareness.
- **No unlimited admin surveillance.** Admin sees route state and events, not a
  live trace, in the MVP.
- **No unrestricted store surveillance.** Store sees scoped status events only.
- **A retention policy is required before route history storage.** Any route
  history needs a defined retention policy first.
- **Driver transparency.** Drivers are informed about what is collected and when.
- **Support/safety exceptions must be explicit.** Any expanded sharing for
  safety is explicit and scoped.
- **Legal review for background location.** Background location requires legal
  review.
- **App Store / Play Store policy review.** Location handling must pass store
  policy review.

## 23. MVP vs Future Boundary

| Feature | MVP / Future / No-Go | Reason | Backend dependency | Mobile dependency | Store/Admin dependency |
|---|---|---|---|---|---|
| External navigation handoff | MVP | Proven, low-risk navigation path | Destination | Open external app | Handoff event |
| Live map active delivery display | MVP | Core driver situational awareness | Route state | Map render | Route events |
| Current step overlay | MVP | Drives correct action per step | Route state | Overlay render | State events |
| ETA/distance display | MVP (estimate) | Driver guidance only | None (future telemetry) | Estimate render | Cautious display (future) |
| GPS permission recovery | MVP | Required for map to function | Permission state (future) | Recovery UI | Permission signal (future) |
| Network recovery | MVP | Field connectivity is unreliable | Reconciliation | Offline/retry UI | Stuck/offline signal |
| Return-to-store route | MVP | Restricted inventory accountability | Return state | Return route mode | Return events |
| Geofence arrival | Future | Spoofing/legal review needed | Candidate evaluator | Location | Candidate events |
| Route deviation detection | Future | Privacy/false-positive risk | Risk engine | Tracking | Admin risk signal |
| Legal/restricted-zone warnings | Future (display when provided) | Backend must own legal logic | Warning provider | Display only | Admin visibility |
| Support/safety access from map | MVP (core) / Future (sharing) | Safety must always be reachable | Support routing | Persistent action | Safety events |
| Continuous background tracking | No-Go (MVP) | Privacy and store policy risk | — | — | — |
| Internal turn-by-turn navigation | Future | Heavy build; handoff suffices | Route engine | Turn-by-turn UI | — |
| Embedded maps SDK | Future | Not needed for handoff MVP | — | SDK | — |
| CarPlay / Android Auto | Future | Out of MVP scope | — | Platform integration | — |
| Store/Admin live map | Future | Surveillance/privacy boundary | Telemetry | — | Map UI |
| Unrestricted location replay | No-Go (MVP) | Privacy boundary | — | — | — |

## 24. Mobile Screen / Flow Dependencies

This section maps the live map to prior screen/flow docs conceptually
(Dr.1.0.D, Dr.1.0.E, Dr.1.0.G, Dr.1.0.H). No implementation is defined.

- **Active delivery map screen** — the spatial surface for an active delivery.
- **Route step overlay** — the current step presentation (Section 7).
- **Pickup flow** — store pickup steps (Dr.1.0.E/H).
- **Store arrival flow** — store arrival candidate handling.
- **Customer arrival flow** — customer arrival candidate handling.
- **Age/ID verification flow** — Dr.1.0.G gate.
- **Proof flow** — Dr.1.0.H proof gate.
- **Failed delivery flow** — Dr.1.0.H failure handling.
- **Return-to-store flow** — Dr.1.0.H return handling.
- **Support/safety flow** — Section 18.
- **Permission recovery flow** — Section 13.
- **Offline/retry flow** — Section 14.

## 25. Future Backend Capability Map

Future backend capabilities needed to implement this architecture. Each is a
candidate, finalized in a later Dr.1.x phase, and extends the Dr.1.0.F gap map.

### Route state model

- **Purpose:** own the route lifecycle (Section 6).
- **Data sensitivity:** medium (operational references).
- **MVP/Future:** MVP foundation (Dr.1.1).
- **Depends on:** delivery domain (Dr.1.0.C), proof/return (Dr.1.0.H).
- **Store/Admin impact:** powers visibility events.
- **Compliance risk:** must not allow local lifecycle override.

### Route action endpoint family

- **Purpose:** accept driver-proposed route actions (start, arrival candidate).
- **Data sensitivity:** medium.
- **MVP/Future:** MVP foundation.
- **Depends on:** route state model, idempotency.
- **Store/Admin impact:** drives state events.
- **Compliance risk:** restricted completion must stay gated.

### Arrival candidate event family

- **Purpose:** record store/customer/return arrival candidates.
- **Data sensitivity:** medium-high (location-adjacent).
- **MVP/Future:** MVP (manual) / future (geofence).
- **Depends on:** route state model.
- **Store/Admin impact:** candidate visibility.
- **Compliance risk:** candidate must not finalize transitions.

### Navigation handoff audit event

- **Purpose:** record handoff and provider selection.
- **Data sensitivity:** low-medium.
- **MVP/Future:** MVP.
- **Depends on:** audit infrastructure.
- **Store/Admin impact:** Admin timeline.
- **Compliance risk:** minimal; avoid PII.

### Location permission status recording

- **Purpose:** record permission denied/recovered (no location data).
- **Data sensitivity:** low (state only).
- **MVP/Future:** future candidate.
- **Depends on:** audit infrastructure.
- **Store/Admin impact:** Admin signal.
- **Compliance risk:** must not record location.

### Geofence candidate evaluator

- **Purpose:** evaluate geofence arrival candidates server-side.
- **Data sensitivity:** high (location).
- **MVP/Future:** future (legally reviewed).
- **Depends on:** location handling, privacy controls.
- **Store/Admin impact:** candidate events.
- **Compliance risk:** spoofing and privacy; review required.

### Restricted-zone warning provider

- **Purpose:** provide zone warnings for display.
- **Data sensitivity:** medium.
- **MVP/Future:** future.
- **Depends on:** zone data, legal rules.
- **Store/Admin impact:** Admin visibility.
- **Compliance risk:** legal logic must stay backend-side.

### Route deviation / risk signal engine

- **Purpose:** future deviation/risk signals.
- **Data sensitivity:** high (tracking).
- **MVP/Future:** future.
- **Depends on:** location telemetry, privacy review.
- **Store/Admin impact:** Admin risk signal only.
- **Compliance risk:** privacy and false positives; review required.

### Support/safety route context sharing

- **Purpose:** share active route context for safety, explicitly.
- **Data sensitivity:** high (location).
- **MVP/Future:** future candidate.
- **Depends on:** support tooling, privacy controls.
- **Store/Admin impact:** Admin safety visibility.
- **Compliance risk:** must be explicit and scoped.

### Route-state idempotency

- **Purpose:** dedup route actions safely.
- **Data sensitivity:** low.
- **MVP/Future:** MVP foundation.
- **Depends on:** route action endpoints.
- **Store/Admin impact:** dedup signals.
- **Compliance risk:** prevents duplicate lifecycle effects.

### Offline reconciliation

- **Purpose:** reconcile queued actions and stale state on reconnect.
- **Data sensitivity:** medium.
- **MVP/Future:** MVP foundation.
- **Depends on:** route state model, idempotency.
- **Store/Admin impact:** stuck/offline signals.
- **Compliance risk:** restricted completion must not replay-finalize locally.

### Store/Admin route visibility

- **Purpose:** expose privacy-safe route events to panels.
- **Data sensitivity:** medium.
- **MVP/Future:** MVP (events) / future (live map).
- **Depends on:** route state events.
- **Store/Admin impact:** core visibility.
- **Compliance risk:** no raw surveillance in MVP.

### Privacy / retention controls

- **Purpose:** govern minimization and retention of route/location data.
- **Data sensitivity:** high.
- **MVP/Future:** MVP foundation for any storage.
- **Depends on:** legal review.
- **Store/Admin impact:** bounds visibility.
- **Compliance risk:** required before any route history storage.

## 26. Phase Target Map

Future implementation maps to later Dr.1.x phases. These are planning targets,
not commitments, and define no implementation here.

| Phase | Target |
|---|---|
| Dr.1.1 | Backend route-state / audit foundations (route state model, route action family, idempotency, route audit events) |
| Dr.1.2 | Mobile map shell / navigation handoff / offline queue foundation |
| Dr.1.3 | Driver MVP active delivery map (display, overlay, ETA estimate, return route mode, manual arrival) |
| Dr.1.4 | Support / safety from map (safety actions, context sharing candidates) |
| Dr.1.5 | Legal / geofence / restricted-zone upgrades (geofence candidates, zone warnings) |
| Dr.1.6 | Route intelligence / Admin analytics (deviation/risk signals, telemetry, Admin views) |

## 27. No-Go Reminder

This subphase (Dr.1.0.H2) is documentation only. It does not create and does not
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
- maps implementation
- GPS tracking implementation
- geofence implementation
- navigation SDK integration
- Apple Maps integration
- Google Maps integration
- Waze integration
- an ETA engine
- route deviation detection
- a restricted-zone engine
- a notification system
- a support system
- a Store/Admin live map
- Stripe / payment / payout logic
- checkout / customer app behavior
- a production launch

All state names, overlay names, event names, and capabilities in this document
are architectural candidates for later Dr.1.x phases. Nothing here is
implemented.
