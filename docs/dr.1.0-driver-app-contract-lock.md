# Dr.1.0 Driver App Contract Lock

## 1. Phase Identity

- **Official phase name:** Dr.1.0 — Mobile Research + Driver App Product
  Architecture.
- **Phase type:** research, product architecture, and documentation only.
- **This phase does not implement the Driver App.** No app code, no backend
  surface, no mobile project, and no runtime artifact is produced under
  Dr.1.0.
- **This phase prepares the future Driver App phases.** It defines the
  architecture, domains, screens, flows, backend gaps, and compliance model
  that the later Dr.1.x implementation phases will build against.

Dr.1.0 is the mobile counterpart to the prior F2.x web phases and is governed
the same way: a contract lock first, then diagnosis, gameplan, validation, and
a pass/fail report. This document is the contract lock for Dr.1.0 and is
authoritative for its scope, boundaries, deliverables, and definition of done.

## 2. Purpose

Dr.1.0 exists to define the complete NubeRush Driver App architecture before
any construction begins. The Driver App is not a small "assigned orders"
viewer; it is a full driver operations platform. It must be modeled with
professional driver-operation depth, adapted from Uber Driver / Uber Eats
Driver concepts, and then transformed for NubeRush's regulated smoke-shop
delivery model — smoke shops, vapes and other restricted products, 21+
verification, proof of delivery, failed delivery handling, return-to-store
accountability, store handoff, driver safety and support, earnings visibility,
performance, notifications, technical reliability, and a backend-authorized
audit trail.

The goal of Dr.1.0 is to remove ambiguity before implementation. When Dr.1.0
closes, the team should be able to start Dr.1.1 (Driver Backend Surface) with a
documented domain model, a screen inventory, user flows, a backend gap map, a
compliance architecture, and a recommended mobile stack — without revisiting
fundamental product questions mid-build.

## 3. Product Principle

> NubeRush Driver App = Uber Driver operational depth + Uber Eats delivery
> workflow + smoke-shop compliance + 21+ verification + proof-of-delivery
> enforcement + return-to-store accountability + backend-authorized audit
> trail.

This principle is read as follows:

- **NubeRush is not copying Uber.** No Uber branding, protected design, or UI
  is reproduced. Uber Driver and Uber Eats Driver are studied as product
  research inspiration only.
- **NubeRush studies the operational structure and adapts it to its own
  market.** The proven structure of a mature driver platform — onboarding,
  availability, offers, active delivery, pickup, dropoff, failure handling,
  support, earnings — is the reference; the requirements are NubeRush's own,
  driven by regulated-product delivery.
- **Mobile is the operational surface.** The Driver App is where field
  execution happens: pickup, transit, verification, proof, completion,
  failure, and return.
- **The backend is the authority.** Eligibility, assignment, order state,
  compliance rules, proof requirements, completion, failure, return flow, and
  audit records are all decided server-side.
- **The Store and Admin panels are the visibility and oversight layer.** They
  observe and supervise delivery; they do not move into the driver's
  field-execution role, and the Driver App does not move into theirs.

## 4. Relationship to Current Web App

- **The current NubeRush web app is sufficiently complete to move into the
  next product surface.** The Web App MVP shipped in F2.26 and was hardened in
  F2.27 (RLS-active CI, staging, deployment readiness, smoke/e2e harness, and
  the operational backlog). It is stable and CI-green, which is the
  precondition for adding a mobile surface on top of it.
- **The web app remains the admin / store operations foundation.** The Admin
  Panel (platform oversight) and the Store Panel (store-scoped operations)
  remain the source surfaces for products, inventory, orders, audit,
  regulatory visibility, and daily operations.
- **The Driver App must integrate with backend authority and future Store /
  Admin visibility.** It consumes the existing authoritative backend contracts
  and plugs into the existing order lifecycle. Store dispatch and admin
  oversight of delivery are expressed through the same backend, surfaced in the
  existing panels.
- **Existing working systems should not be rewritten unless required later.**
  The guiding principle from the mobile strategy roadmap holds: if it is
  already created and not broken, do not change it. Mobile extends the system;
  it does not duplicate or bypass it.
- **Dr.1.0 creates documentation only and does not change the web app.** No
  backend, frontend, schema, or configuration change is part of this phase.

This document is subordinate to `docs/f2.27-contract-lock.md` and consistent
with `docs/f2.27.x-stripe-readiness-roadmap.md` and
`docs/mobile-apps-strategy-roadmap.md`. Where this document and those overlap,
those are authoritative and this one cross-references them.

## 5. Scope

Dr.1.0 must document, as research and architecture artifacts only:

- the full driver product architecture;
- an Uber Driver / Uber Eats feature adaptation matrix (inspiration to
  NubeRush requirement mapping);
- the NubeRush driver domains;
- a complete screen inventory;
- the driver user flows;
- a backend gap map (endpoints that exist vs. endpoints that are missing);
- a future data model map;
- the compliance / 21+ / ID verification architecture;
- the proof-of-delivery architecture;
- the failed delivery architecture;
- the return-to-store architecture;
- the safety / support / communication / notifications architecture;
- the earnings / performance / rewards future architecture;
- mobile stack research (Flutter vs. Capacitor);
- a final consolidated product architecture document.

Everything in this scope is produced as documentation. None of it authorizes
or includes implementation.

## 6. No-Go Boundaries

Dr.1.0 must **not** introduce any of the following. These are hard boundaries;
crossing any one of them requires a separate, explicitly approved future phase
with its own contract.

- No implementation.
- No Flutter app creation.
- No Capacitor app implementation.
- No backend endpoints.
- No migrations.
- No schema changes.
- No frontend web changes.
- No dependency changes.
- No Stripe.
- No checkout.
- No Customer App.
- No driver payouts.
- No real ID scanning.
- No raw ID image storage.
- No automatic compliance override.
- No production delivery launch claim.

These boundaries are consistent with the F2.27 contract lock and the Stripe
readiness roadmap, both of which already place delivery execution, payments,
and the Customer App in future phases.

## 7. Core Driver App Domains to Be Documented

Dr.1.0 will document the following driver domains. This section names them; the
domain architecture deliverable defines each one in depth.

- Driver Account
- Driver Onboarding
- Driver Documents
- Vehicle Profile
- Driver Compliance
- Driver Training
- Availability / Online State
- Delivery Offers
- Driver Assignment
- Active Delivery
- Store Pickup
- Store Handoff
- Navigation
- Customer Dropoff
- Restricted Product Verification
- Age / ID Verification
- Proof of Delivery
- Failed Delivery
- Return to Store
- Safety Toolkit
- Communication
- Support Center
- Earnings
- Promotions / Opportunities
- Performance
- Rewards / Driver Status
- Notifications
- Account Settings
- Geofencing / Legal Zones
- Technical Reliability
- Audit / Compliance Timeline
- Admin / Store Visibility Bridge

## 8. Required Dr.1.0 Documentation Deliverables

Dr.1.0 produces the following documentation files. No implementation phase for
the Driver App may begin until these are produced and reviewed.

- `docs/dr.1.0-driver-app-contract-lock.md` (this document)
- `docs/dr.1.0-driver-feature-adaptation-matrix.md`
- `docs/dr.1.0-driver-domain-architecture.md`
- `docs/dr.1.0-driver-screen-inventory.md`
- `docs/dr.1.0-driver-user-flows.md`
- `docs/dr.1.0-driver-backend-gap-map.md`
- `docs/dr.1.0-driver-compliance-id-verification.md`
- `docs/dr.1.0-driver-proof-failure-return.md`
- `docs/dr.1.0-driver-ops-support-safety.md`
- `docs/dr.1.0-driver-earnings-performance-rewards.md`
- `docs/dr.1.0-mobile-stack-decision.md`
- `docs/dr.1.0-mobile-research-driver-app-product-architecture.md`

## 9. Future Phase Map

The Driver App program is sequenced as follows. Each phase after Dr.1.0 is
future work and requires its own contract lock, diagnosis, gameplan,
implementation, validation, and pass/fail report.

- **Dr.1.0 — Mobile Research + Driver App Product Architecture.** Research and
  architecture only. Defines the driver domains, screen inventory, user flows,
  backend gap map, compliance model, and mobile stack recommendation. Produces
  documentation; introduces no code.
- **Dr.1.1 — Driver Backend Surface.** Designs and implements the
  backend contracts the Driver App needs — driver identity and authorization,
  order-scoped assignment, delivery state transitions, proof and verification
  records, and the audit timeline — built on the existing authoritative
  backend and the existing order lifecycle, not a parallel one.
- **Dr.1.2 — Driver Mobile Foundation.** Stands up the chosen mobile stack
  (per the Dr.1.0 stack decision and a confirming spike), application shell,
  authentication, navigation, secure storage, and the device-API foundations
  (location, camera, push) without yet implementing the full delivery flow.
- **Dr.1.3 — Driver App MVP.** Implements the first end-to-end driver flow
  against existing orders: login, assigned orders, order detail, pickup
  confirmation, out-for-delivery transition, navigation handoff, delivery
  checklist, a controlled age / ID verification step, proof-of-delivery
  capture, failed delivery reason, return flow, and audit trail. No Stripe, no
  payouts, no public launch claim.
- **Dr.1.4 — Driver App Operations.** Hardens day-to-day operations: store
  dispatch bridge, availability / online state, offers and assignment behavior,
  communication and support surfaces, notifications, and the safety toolkit.
- **Dr.1.5 — Driver Compliance Upgrade.** Strengthens the regulated-delivery
  posture — verification workflow maturity, restricted-product handling,
  return-to-store accountability, and the compliance audit timeline — subject
  to legal / compliance approval for any expanded ID handling.
- **Dr.1.6 — Driver Growth Features.** Adds earnings visibility,
  performance, promotions / opportunities, and rewards / driver status as
  growth modules once the operational and compliance foundations are stable.

## 10. Backend Authority Rule

- **The mobile app displays information and submits driver actions.** Its job
  is to render state and to send the driver's intent (accept, picked up, out
  for delivery, verified, delivered, failed, returned) to the backend.
- **The backend decides** eligibility, assignment, order state, compliance,
  proof requirements, completion, failure, return flow, and audit records. The
  order state machine and the rules around it live server-side and are the
  single definition of what is allowed.
- **Mobile must never own business rules.** The Driver App does not define its
  own compliance logic, its own order transitions, or its own completion
  criteria; it requests transitions and the backend grants or rejects them.
- **Driver access must be order-scoped, not store-wide.** A driver sees and
  acts on the specific deliveries assigned to them. The Driver App is not a
  store-operations surface and must not expose store-wide inventory, orders, or
  administration.

## 11. Compliance Boundary

- **Restricted-product delivery is core to NubeRush Driver.** The app exists to
  deliver regulated smoke-shop products safely and accountably, not generic
  parcels.
- **21+ verification is required for restricted deliveries.** A restricted
  delivery cannot be completed unless the required age / ID check passes.
- **MVP assumes a manual verification checklist only.** The driver confirms the
  required checks through a controlled checklist; the backend records the
  result and enforces that completion is blocked without it.
- **No raw ID images.** The MVP does not capture or store raw identity-document
  images.
- **No OCR.** No automated text extraction from identity documents.
- **No vendor scan.** No third-party ID-scanning or verification vendor
  integration in the MVP.
- **No automatic compliance override.** The system never auto-approves,
  auto-holds, auto-bans, or otherwise overrides human/backend compliance
  authority. This preserves the existing human-gated compliance posture from
  F2.27.
- **Failed restricted deliveries require return-to-store.** If verification or
  delivery fails for a restricted product, the order follows the
  return-to-store path with an accountable, audited handoff back to the store.

Any expansion beyond the manual checklist — image capture, OCR, vendor
scanning, or storage of identity documents — is out of scope here and requires
explicit legal / compliance approval in a later phase.

## 12. Mobile Stack Boundary

- **Dr.1.0 will research Flutter vs. Capacitor** and record the analysis in
  `docs/dr.1.0-mobile-stack-decision.md`.
- **Flutter is expected to be the default recommended direction** because the
  Driver App is mobile-first, field-operational, device-API-heavy (camera,
  location, maps, push, secure storage), and compliance-sensitive, where
  consistent native behavior and performance matter.
- **Capacitor remains a fallback / prototype option** because of existing
  web-tech reuse from the Web App, which could lower the cost of an early
  prototype.
- **No mobile project is created in Dr.1.0.** The stack decision is a documented
  recommendation to be confirmed by a technical spike in a later phase; it is
  not committed here, and no Flutter or Capacitor project, dependency, or
  configuration is introduced.

## 13. Definition of Done

Dr.1.0 is done only when all of the following exist:

- The full driver app product architecture exists.
- The Uber-style feature matrix has been adapted to NubeRush.
- All driver domains are documented.
- All major screens are documented.
- All major flows are documented.
- Backend gaps are mapped.
- Compliance and ID verification are documented.
- Proof / failure / return flows are documented.
- Safety / support / communication are documented.
- Earnings / performance / rewards future modules are documented.
- The mobile stack decision is documented.
- The final architecture document consolidates everything.
- Validation proves docs-only scope (no code, backend, frontend, schema,
  migration, dependency, or configuration change).
- A checkpoint commit is created.

## 14. Dr.1.0.A Pass Criteria

Dr.1.0.A (this contract-lock subphase) passes only when:

- Exactly one new docs file is created
  (`docs/dr.1.0-driver-app-contract-lock.md`).
- No code is modified.
- No backend is modified.
- No frontend is modified.
- No migrations are added.
- No dependencies are changed.
- No configuration is changed.
- No tests are changed (documentation tooling requires none).
- The file clearly establishes Dr.1.0 as documentation-only.

Dr.1.0.A is the contract-lock entry point of Dr.1.0. The remaining Dr.1.0
deliverables listed in Section 8 are produced in subsequent documentation
subphases under this same lock, and Dr.1.0 as a whole closes only when the
Section 13 definition of done is met.
