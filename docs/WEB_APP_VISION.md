# NubeRush Web App Vision
## Admin Console + Store Operations Panel

**Status:** Strategic product/architecture document — source of truth for what the
NubeRush Web App is, what it is not, and how it should evolve.
**Audience:** Founder, future engineering team, future product/design team.
**Last reviewed:** 2026-06-06.
**Related:** [PRD.md](PRD.md), [phase-0-foundation.md](phase-0-foundation.md),
[s5.5-handoff.md](s5.5-handoff.md), [f2.6-inventory-readiness.md](f2.6-inventory-readiness.md).

---

## 1. Purpose

The NubeRush Web App is the **operational control center** of the NubeRush
platform. It is the first critical product surface and the foundation of the MVP.

It exists because the business problem NubeRush solves — control of inventory,
compliance, orders and audit in vape stores — is, before anything else, an
**operational problem inside the store**. Stores cannot reliably sell to a
customer if their own internal operation is broken: products not registered,
stock unaccounted for, compliance unenforced, orders not auditable.

The Web App is therefore the surface where:

- NubeRush itself supervises the entire platform across stores.
- Each store runs its day-to-day operation under enforced rules.
- The backend's invariants (RBAC, tenancy, compliance, inventory truth, order
  state machine, audit) are surfaced to humans for the first time.

The Web App is the surface that **must be perfected before any customer-facing
or driver-facing surface is built**, because every later surface depends on the
operational truth that flows through it.

---

## 2. What the Web App is NOT

To prevent scope drift, the Web App is explicitly **not** any of the following:

- **Not the Customer App.** It does not host a public catalog, customer
  signup, cart, checkout, customer-facing payment, customer order tracking,
  or customer push notifications.
- **Not the Driver App.** It does not host driver order assignment, route
  navigation, age/ID verification UX, proof-of-delivery capture, or driver
  shift management.
- **Not a public checkout.** No anonymous, unauthenticated user should ever
  reach a buy-flow on this surface. Every user inside the Web App is
  authenticated and bound to a role.
- **Not a delivery mobile workflow.** Delivery state may eventually be
  *visible* to admins/stores from the Web App, but the actual driver workflow
  lives on a different surface (Driver App / Delivery Surface).

These boundaries are non-negotiable. Customer and Driver flows are separate
surfaces, on a separate roadmap, on top of the same backend. Trying to bend
the Web App into a customer storefront or driver console will corrupt its
operational identity.

---

## 3. Two surfaces inside the Web App

The Web App is a **single application with two distinct surfaces**, gated by
the backend role of the authenticated user.

> **Status note (updated 2026-06-06).** The per-feature *Current status* /
> *Not built* / *Placeholder* markers in §3.1 and §3.2 below are **historical**
> — they are the original 2026-05-04 snapshot and are **no longer the source of
> current truth**. Do not read them as the present state. For the authoritative
> current implementation state, see **§4 below** and **[PRD.md](PRD.md) §9**.
> After F2.26 the Admin Console and Store Panel surfaces (dashboards, stores +
> store applications, global users, products + detail + images, inventory,
> orders, audit/unified feed, compliance, Admin Regulatory, earnings, settings)
> are built and shipped, so most "Not built" markers below are stale. A few
> remain genuinely true (e.g. billing/commission models, daily-operations /
> shifts). The *responsibilities* and *backend dependencies* notes are retained
> as design context. Customer App, Driver App, and Stripe checkout/payments
> remain future.

### 3.1 NubeRush Admin Console

**Audience:**
- NubeRush founder / platform admin / operator.
- Future internal operations team (support, finance, compliance, partnerships).

**Identity:** Cross-store, platform-wide. Sees everything. Owns the platform.

**Responsibilities:**

- **Global dashboard.**
  - *Purpose:* High-level platform health (stores active, orders today, GMV,
    compliance flags, inventory anomalies).
  - *Current status:* Not built. Existing `/app` dashboard is a placeholder
    (`F2.7+` text-only).
  - *Backend dependencies:* Aggregated KPI endpoints across stores (do not
    exist). Must be backend-aggregated, never client-aggregated.

- **Store management.**
  - *Purpose:* Onboard new stores, deactivate stores, view store metadata,
    assign owners, manage tenancy.
  - *Current status:* Not built. The `Store` model exists in the database but
    no admin CRUD UI and no public store-management endpoints.
  - *Backend dependencies:* `GET /stores`, `POST /stores`,
    `PATCH /stores/{id}`, `GET /stores/{id}` (admin-scoped, RBAC-enforced).

- **Global products / compliance oversight.**
  - *Purpose:* Review every product across the platform, change compliance
    status, audit who changed what.
  - *Current status:* Backend supports product CRUD and compliance audit
    (`product_compliance_audit_logs`); the Web App exposes this **per store**
    only. There is no "all products across all stores" admin view yet.
  - *Backend dependencies:* Cross-store product listing for admins (currently
    listing is store-scoped via tenancy).

- **Global orders oversight.**
  - *Purpose:* See orders across all stores, investigate disputes, audit
    state transitions.
  - *Current status:* Not built. Orders listing is store-scoped only.
  - *Backend dependencies:* Cross-store order query endpoint for admins.

- **Global inventory oversight.**
  - *Purpose:* See stock levels across stores, detect anomalies, support
    investigations.
  - *Current status:* Not built.
  - *Backend dependencies:* Cross-store inventory query endpoint for admins.

- **Users / roles oversight.**
  - *Purpose:* See every user across the platform, manage roles, deactivate
    abusive accounts.
  - *Current status:* Not built. Backend currently exposes only
    `POST /auth/users` (create) — no list/update/deactivate.
  - *Backend dependencies:* `GET /auth/users`, `PATCH /auth/users/{id}`,
    deactivation endpoint.

- **Global audit / activity.**
  - *Purpose:* Investigate any event in the system across stores —
    inventory movements, order transitions, compliance changes,
    privileged actions.
  - *Current status:* Not built as a feed. The current Audit Hub
    surfaces only store-scoped inventory logs and per-resource audit
    panels.
  - *Backend dependencies:* Global audit feed endpoint with filtering
    (event type, entity type, user, store, date range, pagination).

- **Business / billing / commission oversight.**
  - *Purpose:* See platform revenue, per-store commissions, payouts,
    billing health.
  - *Current status:* Not built. Billing/commission models do not exist
    in the backend.
  - *Backend dependencies:* New domain entirely — commission model,
    payouts, invoices, payment integration (likely Stripe Connect).

- **Platform settings.**
  - *Purpose:* Platform-level configuration — feature flags, jurisdiction
    defaults, compliance defaults, integrations.
  - *Current status:* Not built.
  - *Backend dependencies:* Settings/configuration endpoints; possibly a
    settings table.

### 3.2 Store Operations Panel

**Audience:**
- Store owner.
- Store manager.
- Store staff.

**Identity:** Store-scoped. Sees and acts on **its own store only**, enforced
by backend tenancy.

**Responsibilities:**

- **Store dashboard.**
  - *Purpose:* Operational pulse for a single store — orders today, low
    stock, compliance flags, recent audit events.
  - *Current status:* Placeholder. The current `/app` index renders a
    `FeaturePlaceholder` ("F2.7+ coming").
  - *Backend dependencies:* Store-scoped KPI endpoints (do not exist yet);
    can be assembled from existing list endpoints in the short term but a
    purpose-built endpoint is preferable.

- **Inventory management.**
  - *Purpose:* Receive stock, adjust, mark damage, sell, reserve, release,
    return; view per-item logs.
  - *Current status:* **Implemented and strong.** Full UI for receive /
    adjust / damage / sell / reserve / release / return + per-item log
    panel + store-wide log panel.
  - *Backend dependencies:* All required endpoints exist.

- **Product management.**
  - *Purpose:* Create products and variants, edit, deactivate, see
    compliance state, change compliance (admin-only inside the store
    panel).
  - *Current status:* **Implemented and strong.** Full product/variant
    CRUD UI, compliance badges, compliance audit panel,
    sellability check.
  - *Backend dependencies:* All required endpoints exist. Missing only
    product image/media support.

- **Order management.**
  - *Purpose:* Create internal orders, transition through state machine,
    cancel, return, view audit trail.
  - *Current status:* **Implemented and strong.** Create order page,
    detail page, state-transition dialogs, cancel/return modals, audit
    panel.
  - *Backend dependencies:* All required endpoints exist for the
    internal-orders flow. Customer-originated orders need separate
    customer-facing endpoints (out of scope for the Web App).

- **User / staff management.**
  - *Purpose:* Add staff/manager/driver users, edit, deactivate, reset
    password.
  - *Current status:* **Create-only MVP.** UI lets owners/managers
    create users via `POST /auth/users`; list / edit / deactivate are
    not implemented because the backend does not yet expose those
    endpoints.
  - *Backend dependencies:* `GET /auth/users` (store-scoped), update,
    deactivate, password reset.

- **Compliance visibility.**
  - *Purpose:* Surface compliance state on every product, every order,
    every catalog view; explain why something is blocked.
  - *Current status:* **Implemented at the product surface** (badges,
    audit panel, status panel). Order-creation does not yet
    short-circuit on compliance (`compliance_blocked` audit action
    deliberately deferred — see [s5.5-handoff.md](s5.5-handoff.md)).
  - *Backend dependencies:* `compliance_blocked` enforcement in order
    service; explicit catalog filter when customer-facing flow lands.

- **Store audit / activity.**
  - *Purpose:* See activity inside this store — who did what, when, why.
  - *Current status:* **Hub MVP.** A page that explains where each
    audit-shaped surface lives (per-resource audit panels) plus a
    store-wide inventory log panel. There is no merged feed.
  - *Backend dependencies:* Optional store-scoped global audit feed.
    The current "no merged feed" position is deliberate to avoid
    deriving business truth client-side.

- **Settings / store profile.**
  - *Purpose:* Edit store name, code, timezone, jurisdiction, contact
    info; manage operating hours; manage integrations.
  - *Current status:* Placeholder.
  - *Backend dependencies:* Store update endpoint, store profile fields,
    possibly a `store_settings` table.

- **Daily operations.**
  - *Purpose:* The umbrella label for the day-to-day rhythm — open
    shift, close shift, generate reports, export.
  - *Current status:* Not modeled yet. There is no shift concept, no
    end-of-day report, no export.
  - *Backend dependencies:* Reporting endpoints; possibly a `shifts`
    domain.

---

## 4. Current implementation status

Snapshot of the Web App as of 2026-06-06 (refreshed after F2.26.6). This
section is descriptive — it records what is real today, not what should be real.

### Implemented / strong

- Protected routing (auth gate via `ProtectedRoute`).
- `StoreGate` (tenancy gate — non-admin users without a `store_id` are
  blocked with a clear `ErrorState`).
- `DashboardLayout` (sidebar + topbar chrome, layout-on-pathless-route
  pattern).
- Admin Console surface — dedicated `/app/admin/*` shell separate from the
  store surface (admin dashboard, stores + store applications, global users,
  global products/inventory/orders oversight, compliance, audit, operations,
  settings, earnings).
- Store Operations Panel — `/app/store/*` surface (dashboard, inventory,
  products, orders, users, compliance, audit, settings).
- Inventory UI (full CRUD-equivalent + logs).
- Products UI (full CRUD + detail + product images + compliance + audit panel).
- Orders UI (list, detail, transitions, cancel, return, audit panel).
- Create Order internal flow (idempotent, store-scoped).
- Users management (global admin + store-scoped).
- Audit — unified feed (global for admin, store-scoped for store users).
- Compliance review surface.
- Admin Regulatory surface (`/app/admin/regulatory`) — admin-only regulatory
  alerts with explicit human review, lifecycle actions, and a decision trail;
  no automatic hold/ban/block.
- Earnings (admin + store) — read-only internal accounting estimates.
- Centralized API client with session-token handling and typed errors.
- Consistent loading / error / empty / success patterns across features.

### Partial / limited

- `compliance_blocked` order action deferred (documented in
  [s5.5-handoff.md](s5.5-handoff.md)).
- Regulatory dashboard KPI tile is deferred — no Admin Dashboard regulatory
  aggregate yet; a future tile should read a backend aggregate rather than add
  a second dashboard query.
- Billing / payouts / commission settlement — not built; earnings are internal
  estimates only, pending Stripe (see below).

### Not part of Web App yet

- Customer checkout.
- Customer catalog app.
- Driver workflow.
- Delivery / proof-of-delivery capture.
- Customer-facing payments UX, Stripe checkout, `PaymentIntent`, payment
  webhook, and payment capture/settlement — pending Stripe approval; no real
  payments are processed in the Web App. (Admin/business-management payment UX
  may eventually be added to the Admin Console — the only in-scope payment
  surface for the Web App.)

---

## 5. Route / surface strategy

### Pragmatic current state

Existing `/app/*` routes mostly behave as the **Store Operations Panel**:
they are tenancy-gated, store-scoped, and oriented at owner / manager /
staff workflows. Admin users currently use the same routes; there is no
visible separation between "I am the platform operator" and "I am running
this store."

This is acceptable for the MVP but will not survive the introduction of
admin-only surfaces (store management, global audit, billing).

### Future pragmatic split

Two sibling sub-trees under `/app`, each gated by role at the backend AND
at the route level. The frontend route guard is a UX courtesy — the
backend remains the only authoritative gate.

**Store Operations Panel:**

```
/app/store/dashboard
/app/store/inventory
/app/store/products
/app/store/orders
/app/store/users
/app/store/audit
/app/store/settings
```

**NubeRush Admin Console:**

```
/app/admin/dashboard
/app/admin/stores
/app/admin/orders
/app/admin/inventory
/app/admin/products
/app/admin/users
/app/admin/audit
/app/admin/billing
/app/admin/settings
```

### Migration constraints

- Route migration must be deliberate. **Do not break existing routes**
  until a replacement plan is in place and shipped.
- A reasonable transition is to introduce `/app/admin/*` first (greenfield
  for admin work), then later move existing `/app/*` routes under
  `/app/store/*` with permanent redirects from the old paths.
- Navigation labeling and the sidebar must communicate the active surface
  ("NubeRush Admin" vs "Store Console") so the operator never has to
  guess which scope they are in.

---

## 6. What must be completed before Customer App

The Customer App must not be started until the Web App is operationally
honest and visually finished. Specifically:

- Store Operations Dashboard with real KPIs (replace the placeholder).
- Visual polish pass across Inventory / Products / Orders / Users / Audit
  (consistent empty states, loading states, error surfaces, copy).
- Clear Admin vs Store navigation and scope (sidebar, page titles,
  breadcrumbs).
- A decision on Settings — either build the minimum viable settings page
  or remove it from the navigation until it has content.
- Admin Console shell **or** a written requirements doc that defines what
  the shell will contain.
- Store management backend requirements written and reviewed.
- Users list / update / deactivate backend requirements written and
  reviewed.
- Global audit backend requirements written and reviewed.
- Billing / commission backend requirements written and reviewed.

The non-negotiable principle: **no Customer App work begins until the
operational surface is honest, complete enough to run a store, and free
of placeholder pages in the primary navigation**.

---

## 7. What requires backend before frontend can fully implement

The frontend is a thin client. The following surfaces are blocked on
backend work and **must not be faked** in the UI:

- `GET /stores`, `POST /stores`, `PATCH /stores/{id}`, `GET /stores/{id}`
  (admin-scoped store management).
- `GET /auth/users` (store-scoped and admin-scoped variants),
  `PATCH /auth/users/{id}`, deactivation endpoint, password-reset endpoint.
- Global audit feed endpoint with filtering (event_type, entity_type,
  user_id, store_id, date range, pagination).
- Global / cross-store orders query endpoint for admins.
- Global / cross-store inventory query endpoint for admins.
- Billing / commission models and APIs (commission per order, payouts,
  invoices, Stripe-Connect-compatible flow).
- Settings / store profile APIs (store profile update, operating hours,
  jurisdiction, contact).
- Reporting / KPI endpoints (store-scoped and platform-scoped).
- Product image / media APIs (upload, retrieve, delete; storage layer).

Until each endpoint exists, the corresponding UI must either:
1. not be built, or
2. be built as an explicit "limitation" surface that states what is not
   yet supported. **It must never invent endpoints, fabricate data, or
   lie about capability.**

---

## 8. Product rule summary

| Surface | User | Purpose | Owns checkout? | Owns delivery? | Current priority |
|---|---|---|---|---|---|
| Admin Console | NubeRush operator / internal team | Supervise the platform across stores; manage stores, billing, global audit | No | No | **High** — required to operate the platform as it scales beyond one store |
| Store Operations Panel | Store owner / manager / staff | Run a single store's daily operations safely under enforced rules | No | No | **Highest** — current MVP base; must be perfected first |
| Customer App | End customer | Browse catalog, place orders, pay, track delivery | **Yes** | No | Future — blocked on Web App completion + payments + customer-facing endpoints |
| Driver App | Driver | Receive assignments, navigate, verify age, capture proof of delivery | No | **Yes** | Future — blocked on Customer App and delivery domain |
| Backend | All clients | Source of truth: auth, RBAC, tenancy, compliance, inventory, orders, audit, billing | n/a | n/a | Continuous — every surface depends on it |

---

## 9. Development rules

These rules are mandatory for all Web App work. They restate the thin-client
contract in operational terms.

- **No fake production data.** Demo / mock data is permitted only in
  isolated tests and explicitly-marked dev fixtures, never in
  production-rendering code paths.
- **No invented endpoints.** If the backend does not expose an endpoint,
  the UI does not call one. Period.
- **No role logic in frontend.** The frontend may *display* role-aware
  affordances for UX, but the backend is the only gate. A user who
  forces their way to a forbidden page must see the backend's `401` or
  `403` surfaced honestly.
- **No business truth in frontend.** Stock counts, order totals, valid
  transitions, compliance state, and audit events come from the backend
  and are rendered as-is. The frontend does not recompute, derive, or
  merge them into new business meaning.
- **No direct fetch / axios calls.** All HTTP goes through the centralized
  API client so session tokens, error mapping, and typing are consistent.
- **Backend errors must be surfaced honestly.** A 403 says 403. A 409
  says "already exists" with the backend's reason. A 422 surfaces field
  errors. Errors are never swallowed and never relabeled into something
  more flattering.
- **If a backend endpoint does not exist, the UI must state the
  limitation** instead of pretending the feature works. "User editing is
  not yet supported by the backend" is a valid product state. A button
  that pretends to save and silently no-ops is not.

---

## 10. Recommended next phase

> **F2.12 — Web App Completion & Visual Polish**

The Web App should reach a point where a real store can be run on it end
to end and a NubeRush operator can credibly demo the platform without
hitting placeholder pages. After that, and only after that, work begins
on the Customer App.

### F2.12.0 — Surface Diagnostic

- Audit every route in `/app/*` and label it: implemented / partial /
  placeholder / not started.
- Audit every primary nav item: same labels.
- Produce a one-page punch list of placeholders to remove or build.

### F2.12.1 — Navigation + Surface Naming

- Decide and ship the Admin vs Store split in navigation, sidebar
  labels, page titles, and breadcrumbs.
- Introduce `/app/admin/*` and `/app/store/*` (or a deliberate
  alternative) with redirects from the old paths.
- Ensure admin users see the Admin Console by default and have a way
  to drop into a specific store's panel for support work.

### F2.12.2 — Store Operations Dashboard

- Replace the `FeaturePlaceholder` index page with a real store
  dashboard: orders today, low-stock count, compliance flags,
  recent audit events.
- Backend endpoints either exist (assembled from current list endpoints)
  or are explicitly added as a store KPI endpoint.

### F2.12.3 — Store Panel Visual Polish

- Consistent empty / loading / error / success states across Inventory,
  Products, Orders, Users, Audit.
- Consistent typography, spacing, density, action placement.
- Copy review (no developer-speak in user-facing text).

### F2.12.4 — Admin Console Shell

- Build the empty Admin Console shell: layout, navigation, an admin
  dashboard placeholder that is explicit about what's coming, and a
  Stores page that lists stores read-only (if a `GET /stores` admin
  endpoint exists or is added).
- This is a thin shell that gives later admin features a real home.

### F2.12.5 — Admin Backend Requirements

- Write and review backend requirement docs for: store management,
  user list/update/deactivate, global audit feed, cross-store orders /
  inventory queries, billing / commissions, reporting / KPIs,
  product media. These docs are the prerequisite for any admin
  feature work beyond F2.12.4.

After F2.12 lands, the Web App should look and feel like the
operational control center the PRD describes — not a partially-finished
internal tool. Only at that point does Customer App work begin.
