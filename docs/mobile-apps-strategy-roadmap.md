# NubeRush Mobile Apps Strategy Roadmap

## 1. Executive Summary

The NubeRush Web App is now complete enough to advance into mobile app
planning. After the F2.27 closure, the internal operating core is stable and
CI-green: products, inventory, orders, audit, regulatory and compliance
visibility, store operations, admin oversight, Excel inventory import, the
QuickBooks inventory connection foundation, automatic regulatory ingestion,
and Stripe readiness documentation all exist on a single authoritative
backend. The Web App can already run a store internally and supervise the
platform from the Admin Panel.

That stability is the precondition for going mobile. We do not move to mobile
because the Web App is finished in every sense; we move because the
operational backbone is reliable enough that new surfaces can be built on top
of it without rebuilding what already works.

This document states four things clearly:

- The Web App remains the operational backbone. It is the admin and store
  operations surface and the place where orders, inventory, compliance, and
  audit live today.
- The next step is **not** to rebuild the Web App. Nothing here replaces the
  Admin Panel or the Store Panel.
- The next step is to **add mobile surfaces on top of the existing backend**,
  starting with the Driver App.
- Mobile must **extend** the existing system, not replace it. Mobile apps call
  existing backend contracts; the backend stays the source of truth.

Guiding product principle for this entire roadmap: **if it is already created
and not broken, do not change it.**

This roadmap is a planning and strategy document only. It is subordinate to
`docs/f2.27-contract-lock.md` and consistent with
`docs/f2.27.x-stripe-readiness-roadmap.md`, both of which already place the
Customer App, Driver App, checkout, payments, and delivery execution in future
phases. Where this document and those documents overlap, those documents are
authoritative and this one cross-references them.

## 2. Current Platform State

The current NubeRush state, as the starting point for mobile planning:

- **Web App complete enough for the next phase.** The Web App MVP shipped in
  F2.26 and was hardened in F2.27 (RLS-active CI, staging, deployment
  readiness, smoke/e2e harness, plus the operational backlog features). It is
  stable and CI-green.
- **Admin Panel exists for platform oversight.** Global, cross-store identity:
  platform supervision, store and store-application review, global product /
  inventory / order visibility, unified audit, regulatory administration, and
  operational reporting.
- **Store Panel exists for store operations.** Store-scoped identity (tenancy
  enforced by the backend): inventory, products, orders, team users,
  compliance visibility, store-scoped audit, and daily operations.
- **Backend remains the authority.** Business logic, validation, compliance
  rules, total calculation, inventory control, and audit live in the backend.
  The frontend is an operational client that displays data and executes
  actions; it does not make business decisions.
- **Operating foundations exist.** Inventory (real stock, movements,
  adjustments, logs), orders (creation and full lifecycle synchronized with
  inventory), audit (unified for admin, store-scoped for store users),
  regulatory visibility (admin regulatory surface with explicit human review),
  settings, and the integration foundations (Excel inventory import,
  QuickBooks inventory connection, automatic regulatory source ingestion).
- **Customer App and Driver App do not exist yet.** They are future surfaces,
  to be built on the same backend once the operating core is consolidated.
- **Stripe / payments are intentionally deferred.** Per
  `docs/f2.27.x-stripe-readiness-roadmap.md`, no payment processing, no
  PaymentIntent, no webhook, and no checkout exist today. Payment activation
  is deliberately sequenced **after** the mobile app foundations.

## 3. Strategic Decision: Which App Comes Next

**Recommendation: build the Driver App first.**

The reasoning is operational risk, not feature appeal.

Why the Driver App is the correct first mobile surface:

- **The biggest delivery risk is not browsing products; it is safe
  execution.** A customer scrolling a catalog is low-risk. A regulated product
  arriving at a door — to the right person, of the right age, with proof — is
  where the real legal, compliance, and operational risk lives. Mobile should
  attack the riskiest surface first.
- **The Driver App owns the high-risk steps:** pickup, delivery, failed
  delivery, proof of delivery, and final age / ID verification. These are
  exactly the steps the PRD already assigns to the Driver App and explicitly
  keeps out of the Web App.
- **The Driver App can be built without Stripe.** Delivery execution does not
  require payment capture. The driver flow can be designed, built, and
  validated while Stripe remains deferred.
- **The Driver App can work with orders the current Store Panel already
  creates and manages.** Orders already move through their full lifecycle
  (`pending → accepted → preparing → ready → out_for_delivery → delivered`,
  with `canceled` and `returned`) inside the existing backend. A Driver App
  can plug into the later stages of that existing lifecycle instead of
  inventing a new one.
- **The Driver App strengthens the delivery operation before public customer
  ordering is launched.** It lets NubeRush prove controlled, audited,
  age-verified delivery with internal orders first.
- **It reduces operational risk before exposing the system to customers.** We
  harden execution, proof, and verification before any public ordering surface
  invites volume.

Why the Customer App should **not** be first:

- **The Customer App naturally pushes toward catalog, cart, checkout,
  payments, and tracking.** A customer ordering surface implies a way to pay.
- **Stripe and payment activation are intentionally deferred** (see
  `docs/f2.27.x-stripe-readiness-roadmap.md`, including the unresolved
  commission source-of-truth and other pre-payment reconciliation items).
  Building the Customer App first would either collide with that deferral or
  ship a customer surface that cannot complete its core job.
- **Building the Customer App first could create an incomplete customer
  experience** — a catalog and cart with no checkout, no payment, and no
  proven delivery behind it.
- **The Customer App should come after the delivery execution foundation
  exists,** so that when customers can order, the operation behind the order is
  already controlled and audited.

## 4. Recommended App Order

The recommended build order:

1. **Driver App** — delivery execution, proof, and age / ID verification.
2. **Customer App** — catalog, compliance-filtered availability, cart draft,
   and order tracking (pre-payment), then checkout after Stripe.
3. **Stripe / payment activation** — only after both mobile foundations are
   designed and the delivery flow is controlled.

If a third mobile surface is later desired, identify a **Store Mobile
Companion** as **optional, not required immediately**. The Store Panel already
exists in the Web App and already handles store operations; a mobile companion
for store staff is a convenience surface, not a gap. It should only be
considered after the Driver App and Customer App, and only if a concrete
mobile store-operations need is proven.

Preferred phase roadmap:

- **F2.28 — Mobile Research + Driver App Strategy**
- **F2.29 — Driver App Backend Surface + Flutter Foundation**
- **F2.30 — Driver App MVP**
- **F2.31 — Customer App Research + Strategy**
- **F2.32 — Customer App Foundation**
- **F2.33 — Customer App Catalog, Cart Draft, and Order Tracking**
- **F2.34 — Stripe / Payment Activation Planning**
- **F2.35 — Customer Checkout + PaymentIntent**, only after Stripe approval and
  the legal / compliance gates are cleared.

Each phase above is future work and requires its own contract lock, diagnosis,
gameplan, implementation, validation, and pass/fail report, consistent with
how prior F2.x phases were governed.

## 5. Technology Direction

The mobile apps should be built **multiplatform for both iOS and Android** from
a single codebase.

**Recommended technology: Flutter.**

Why Flutter is likely the right direction:

- **One codebase for iOS and Android,** which keeps a small team from
  maintaining two native apps in parallel.
- **Strong mobile UI performance,** suitable for the responsive, real-time-feel
  screens both apps need.
- **Good support for the native device APIs these apps depend on:** camera,
  location, maps, push notifications, secure storage, and other native
  integrations.
- **Suitable for Driver App workflows** such as scanning, proof-of-delivery
  capture, navigation handoff, and delivery status updates.
- **Suitable for Customer App workflows** such as catalog browsing, cart,
  order tracking, notifications, and account screens.

Also stated explicitly:

- **The final technology choice should be confirmed after a technical spike.**
  Flutter is the recommended default direction, not a locked decision; a spike
  in F2.29 should validate it against the specific Driver App needs (camera /
  ID capture, maps / navigation handoff, secure storage, push) before it is
  committed.
- **The mobile apps must use the existing backend contracts.** They consume the
  same authoritative API the Web App uses; they do not define their own
  parallel business rules.
- **The backend remains the source of truth.** Permissions, tenancy, inventory,
  compliance, order transitions, and audit stay server-side.

## 6. Product Research Requirement Before Building

Before building the Driver App or the Customer App, a **deep research phase is
required.** Implementation does not begin until research produces a clear
screen map, a user-flow map, and a backend-contract gap analysis.

The research must answer:

- What screens are needed?
- What user flows are needed?
- What data does each screen need?
- Which backend endpoints already exist?
- Which backend endpoints are missing?
- What can be reused from the Web App (contracts, models, patterns)?
- What should not be changed?
- What should be copied conceptually from best-in-class delivery apps?
- What must be different because NubeRush serves smoke shops and regulated
  products?

The research must include:

- Uber Eats driver-side flow analysis.
- Uber Eats customer-side flow analysis.
- DoorDash-style delivery flow analysis, if helpful.
- Compliance and age-verification requirements.
- Delivery failure and return scenarios.
- Store dispatch needs.
- Push notification needs.
- Location and map needs.
- Proof-of-delivery needs.
- Audit and security needs.

**Do not implement** until the research phase produces a clear screen map, a
user-flow map, and a backend-contract gap analysis.

## 7. Uber Eats Functionality to Study

NubeRush should learn from the best parts of Uber Eats as **product research
inspiration only** — never by copying branding, protected design, or UI
directly.

Customer-side functionality to research and evaluate:

- home / catalog discovery;
- store selection;
- product listing;
- product detail;
- cart;
- order status tracking;
- notifications;
- support / help;
- account / profile;
- saved addresses;
- delivery ETA patterns.

Driver-side functionality to research and evaluate:

- available deliveries;
- assigned deliveries;
- accept / decline delivery;
- pickup instructions;
- navigation handoff;
- delivery checklist;
- customer contact controls;
- delivery completion;
- failed delivery flow;
- earnings / status visibility, if applicable later;
- push notification behavior.

Store / dispatch-side functionality to research and evaluate:

- ready orders;
- driver assignment;
- pickup confirmation;
- delivery status visibility;
- failed delivery review.

**Important:** do not copy Uber Eats UI directly. Use it as product research
inspiration only. The goal is to understand proven delivery patterns and then
design NubeRush's own screens around its own regulated-product requirements.

## 8. NubeRush-Specific Requirements

NubeRush is different from Uber Eats because it serves **regulated smoke shop
products.** That difference drives requirements a general food-delivery app
does not have.

The Driver App must include or prepare for:

- final ID verification;
- age verification;
- an ID scanning or ID capture workflow, subject to legal / compliance
  approval;
- proof of delivery;
- a failed verification flow;
- a failed delivery flow;
- a return-to-store flow;
- audit logs for delivery and verification events;
- driver identity and authorization;
- **no delivery completion unless the required checks pass;**
- privacy-safe handling of sensitive documents.

The Customer App must include or prepare for:

- age-gated account onboarding;
- a compliance-filtered catalog;
- only products allowed for sale;
- inventory-aware product availability;
- order tracking;
- notifications;
- future checkout;
- future Stripe payments;
- clear legal / compliance messaging;
- **no claim that delivery or payment is live before launch.**

These requirements preserve the existing human-gated compliance posture: the
backend remains the authority on what is allowed for sale, and no mobile
surface introduces automatic compliance enforcement or override.

## 9. Driver App MVP Scope

The first Driver App MVP is defined **without Stripe.**

In scope for the Driver App MVP:

- login / auth;
- assigned orders list;
- order detail;
- pickup confirmation;
- out-for-delivery transition;
- navigation handoff;
- delivery checklist;
- an age / ID verification placeholder or controlled workflow (final form
  subject to legal / compliance approval);
- proof-of-delivery capture;
- failed delivery reason;
- return flow;
- audit trail;
- push notifications, if approved for the MVP.

Explicitly excluded from the Driver App MVP:

- Stripe;
- payments;
- driver payouts;
- customer checkout;
- marketplace-style driver bidding;
- an automatic dispatch algorithm;
- any public delivery launch claim;
- full ID document storage, unless approved by legal / compliance.

The Driver App MVP works against orders that already exist in the backend and
plugs into the existing order lifecycle (the later stages such as
`ready → out_for_delivery → delivered`, plus the failed / return paths). It
does not introduce a parallel order model.

## 10. Customer App Future Scope

The Customer App is the **second** app.

Initial scope, **before Stripe:**

- account creation / login;
- store selection;
- catalog browsing;
- product detail;
- compliance-filtered product visibility;
- inventory-aware availability;
- cart draft;
- order tracking;
- notifications;
- support / help.

Future scope, **after Stripe approval:**

- checkout;
- PaymentIntent;
- payment confirmation;
- refunds / cancellations;
- receipts;
- payment status;
- customer order history.

**Explicitly stated:** Customer App checkout and payments happen **only** after
Stripe / payment activation and legal / compliance approval. Until then, the
Customer App may present a catalog, a cart draft, and order tracking, but it
must not present a live checkout, must not capture payment, and must not imply
that payment or delivery is live.

## 11. Backend and Web App Reuse Principle

The reuse rules that govern all mobile work:

- **Do not rebuild backend logic in mobile.** Business rules stay server-side.
- **Do not duplicate order lifecycle rules in mobile.** The order state machine
  lives in the backend and is the single definition of allowed transitions.
- **Do not bypass Store Panel workflows.** The Store Panel remains the store
  operations surface; mobile complements it, it does not route around it.
- **Do not replace existing Web App features** unless a gap is proven and
  documented.
- **Mobile should call backend endpoints,** the same authoritative contracts
  the Web App uses.
- **The backend remains responsible** for permissions, tenancy, inventory,
  compliance, order transitions, audit, and — when payments are later added —
  payment state.

This section restates the guiding principle: **if it is already created and not
broken, do not change it.** Mobile extends the system; it does not duplicate or
bypass it.

## 12. Required Research Deliverables Before Implementation

Before building the **Driver App**, the following are required:

1. Driver App screen inventory.
2. Driver App user flow map.
3. Driver App backend endpoint gap analysis.
4. Driver App compliance / ID verification research.
5. Driver App Flutter technical spike plan.
6. Store dispatch bridge requirements.
7. Test strategy.

Before building the **Customer App**, the following are required:

1. Customer App screen inventory.
2. Customer App user flow map.
3. Catalog and product detail requirements.
4. Cart / order request model (before Stripe).
5. Checkout / payment deferral plan.
6. Notification and tracking plan.
7. Legal / compliance copy review.

No implementation phase for either app may begin until its corresponding
deliverables above are produced and reviewed.

## 13. Suggested First Research Phase

Open the next phase as:

**F2.28 — Mobile Research + Driver App Product Architecture**

**Purpose:** research and design the Driver App before any implementation.

**Deliverables:**

- Driver App screen map.
- Driver App user journey.
- Uber Eats-inspired feature analysis (inspiration only, no UI copying).
- NubeRush-specific compliance feature list.
- Backend contract gap analysis.
- Flutter architecture recommendation.
- Store dispatch bridge requirements.
- A clear no-code implementation boundary for this research phase.

F2.28 is a research and design phase. Like F2.27.X, it produces documentation
only and does not introduce app code, Flutter projects, backend changes, or
configuration.

## 14. Hard No-Go Boundaries

For the next phase (F2.28 — Mobile Research + Driver App Product
Architecture), the following must not be introduced:

- No Stripe.
- No checkout.
- No payment capture.
- No PaymentIntent.
- No customer payment flow.
- No driver payouts.
- No Customer App implementation yet.
- No production delivery launch claim.
- No ID image storage without legal / compliance approval.
- No rebuilding of existing Web App functionality.
- No bypassing backend authority.
- No automatic compliance override.

These boundaries are consistent with the F2.27 contract lock and the Stripe
readiness roadmap. Any work that would cross one of them requires a separate,
explicitly approved future phase with its own contract.

## 15. Final Recommendation

NubeRush should build the **Driver App first**, using **Flutter for iOS and
Android**, after a dedicated research phase. The Driver App is the safest and
most strategic next surface because it solves delivery execution, proof, and
age / ID verification, and gives NubeRush operational control over delivery
before public customer ordering and payments are introduced.

After the Driver App, NubeRush should build the **Customer App**. **Stripe and
payments should come last** — after both mobile foundations are designed, the
delivery flow is controlled, the legal / compliance gates are cleared, and
Stripe approval and readiness are complete.

Throughout, the Web App remains the operational backbone, the backend remains
the source of truth, and the governing principle holds: **if it is already
created and not broken, do not change it.** Mobile extends the existing
NubeRush system; it does not replace it.
