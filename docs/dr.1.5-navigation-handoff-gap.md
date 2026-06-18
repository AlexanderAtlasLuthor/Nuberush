# Dr.1.5.I — Navigation Handoff Gap Document

> **Document type:** Phase gap document (Dr.1.5.I — Navigation Handoff Gap).
> **Change class:** DOCS-ONLY. This document ships no runtime, no dependency, no
> backend, no schema, and no mobile code. It records *why* runtime navigation is
> intentionally absent in Dr.1.5 and *what* must exist before it can be built.

---

## 1. Status

- **Phase:** Dr.1.5 — Driver Operations Surface / Active Delivery Productization.
- **Subphase:** Dr.1.5.I — Navigation Handoff Gap Doc.
- **Type:** docs-only / backend-blocked.
- **State:** Navigation handoff is **intentionally not implemented**. This
  document is the authoritative record of the gap.
- **Repo:** `main`; this subphase adds exactly one new docs file and changes no
  runtime, mobile, backend, web, supabase, render, CI, or dependency files. No
  commit. No push.

This document does **not** propose building navigation in Dr.1.5. It proposes a
*future* backend-owned contract and *future* mobile behavior so a later phase
can design navigation safely.

---

## 2. Current Dr.1.5 Navigation Status

Navigation handoff is **intentionally not implemented** in Dr.1.5. As of this
subphase, the Driver App has:

- **No** `url_launcher` runtime (no maps/URI launching from the app).
- **No** maps SDK (no Apple MapKit, Google Maps SDK, Mapbox, or equivalent).
- **No** Apple Maps / Google Maps / Waze handoff.
- **No** embedded / in-app map.
- **No** ETA computation or display.
- **No** route preview.
- **No** geocoding (no name → coordinate or address → coordinate lookups).
- **No** fake address and **no** fake / placeholder coordinates anywhere in the
  runtime.

This is a deliberate product/architecture decision, not an oversight. The
backend does not yet expose a **safe navigation contract**, so the only correct
behavior is to ship no navigation at all (see §4 — Flutter must not invent data).

---

## 3. Why Navigation Is Backend-Blocked

The current driver-facing read models — assignment list, assignment detail, and
delivery operational state — are deliberately **PII-free**. They provide:

- Store context: store **name**, **code**, **timezone** only — **no** address,
  **no** coordinates.
- Order summary: lifecycle **status** + **timestamps** only — **no** customer
  identity, **no** customer address, **no** customer location/notes, **no**
  money, **no** items.
- Delivery operational state: the physical-flow `state` string only.

None of this is a safe navigation target. A correct navigation handoff requires
backend-owned data and rules that **do not exist today**. The required missing
backend capabilities are:

1. **Store pickup destination** suitable for navigation (the store location a
   driver should route to for pickup / return).
2. **Customer dropoff destination** suitable for navigation (where the order is
   delivered).
3. **Safe address string or coordinates** — an explicit, backend-vetted address
   and/or lat/lng (or a provider-safe destination URI) intended for navigation.
4. **Destination type** — e.g. `pickup` vs `dropoff` vs `return`, so the UI and
   audit trail know what is being routed to.
5. **Privacy-safe display rules** — what may be shown in the UI vs what may only
   be passed to a maps provider.
6. **Redaction rules** — how addresses/coordinates are minimized or masked when
   shown to the driver.
7. **Role / assignment authorization rules** — only the assigned, authenticated
   driver may receive a destination; tenancy and RBAC enforced server-side.
8. **Lifecycle gating rules** — *when* each destination may be exposed (e.g.
   dropoff destination only after pickup / departure, not at offer time).
9. **Audit / logging expectations** — server-side record that a destination was
   issued (who, which assignment, when), without leaking the address into logs.
10. **Error states when destination is unavailable** — explicit, structured
    reasons (not available yet, withheld, expired, no-access) the UI can render
    safely.
11. **Future API / schema contract** — a stable endpoint + response schema the
    mobile client can consume (proposed in §6, **not** implemented here).

Until the backend owns and serves these, the mobile client has nothing safe to
navigate to.

---

## 4. Privacy and Compliance Constraints

NubeRush handles **restricted-product (age-gated) deliveries**. Destination data
— especially the customer dropoff location — is sensitive and must be protected.
The following constraints must hold for any future navigation feature:

- **Customer destination must not be exposed before it is operationally
  required.** A dropoff address should not be visible at offer/accept time; it
  should appear only at the lifecycle point the backend authorizes (e.g. after
  pickup / depart-to-customer).
- **Destination should only be available to the assigned, authenticated
  driver.** The backend enforces role, tenancy, and assignment ownership; the
  client never derives access locally.
- **Data should be minimized.** Show the least destination detail necessary for
  the driver to complete the leg; prefer backend-redacted display values.
- **Logs must not leak addresses or coordinates.** No raw destination data in
  client logs, crash reports, analytics, or token/debug output.
- **UI must not display raw destination data unless the backend explicitly
  allows it.** Display vs navigate-only fields must be distinguished by the
  backend contract.
- **Failed / returned / canceled deliveries need clear destination access
  behavior.** After cancellation or return, the customer destination should be
  withheld unless the backend explicitly says it is still allowed; return legs
  may expose only the **store** destination.
- **Screenshot / customer-PII risk should be considered in future
  product/legal review.** On-screen destination data can be screenshotted;
  retention, masking, and legal review are required before exposure.

---

## 5. Why Flutter Must Not Invent Navigation Data

Because no safe contract exists yet, the mobile client must **never** synthesize
navigation data. Specifically, Flutter must not:

- **Hardcode addresses** of stores or customers.
- **Infer coordinates** for any store, customer, or order.
- **Geocode** store names, customer names, or any free-text into coordinates.
- **Derive a destination** from order/store names or any other read-model field.
- **Use placeholder coordinates** (e.g. `0,0`, a city centroid, or any dummy
  lat/lng) as a stand-in for a real destination.
- **Open maps from incomplete or fake data** — no `url_launcher` / maps handoff
  built on guessed, partial, or fabricated destinations.

Any of the above would create false precision, leak or invent location data, and
violate the **Flutter presents; backend decides** boundary. The correct behavior
remains: **show no navigation** until the backend provides a real destination.

---

## 6. Future Backend Contract Proposal (Docs-Only, Not Implemented)

The following is a **conceptual** future contract to guide a later phase. It is
**not implemented in Dr.1.5** and is illustrative only — exact shapes, names,
and gating are to be designed and owned by the backend.

**Conceptual endpoint:**

```text
GET /driver/assignments/{assignment_id}/navigation
```

- Authenticated, assigned-driver-only; tenancy + RBAC enforced server-side.
- Lifecycle-gated: returns only the destination(s) the backend currently
  authorizes for this assignment's state.

**Conceptual response schema (illustrative only):**

```jsonc
{
  "pickup_destination": {
    "destination_type": "pickup",          // pickup | dropoff | return
    "label": "Store display label",        // safe, human-readable
    "redacted_address": "masked address",  // backend-decided display value
    "navigation": {                         // navigate-only payload
      "lat": null,                          // or provider-safe value
      "lng": null,
      "destination_uri": null               // provider-safe destination URI
    },
    "allowed_actions": ["open_apple_maps", "open_google_maps", "open_waze"],
    "expires_at": "<timestamp>",            // short-lived; client must re-fetch
    "audit_id": "<server audit reference>"  // server logs issuance, not address
  },
  "dropoff_destination": null,              // present only when lifecycle allows
  "unavailable_reason": null                // e.g. not_available_yet | withheld
                                            //      | expired | no_access
}
```

Notes on the proposal:

- `destination_type`, `label`, `redacted_address` separate *display* from
  *navigate-only* data.
- `lat`/`lng` **or** a `destination_uri` (provider-safe) — the backend decides
  what is safe to hand to a maps provider.
- `allowed_actions` / lifecycle availability are **backend-driven**; the client
  shows only what is allowed.
- `expires_at` keeps destinations short-lived so the client re-fetches rather
  than caching sensitive data.
- `audit_id` supports server-side audit without logging the address itself.
- `unavailable_reason` gives the client structured, safe empty/denied states.

Again: **this is a future proposal, not an endpoint that exists or is consumed
in Dr.1.5.**

---

## 7. Future Mobile Behavior Proposal (Docs-Only, Not Implemented)

Once the backend contract above exists, mobile behavior **should**:

- **Show a navigation card only when the backend says a destination is
  available** (driven by the response + lifecycle gating, never inferred).
- **Let the driver choose Apple Maps / Google Maps / Waze** only from the
  **backend-provided** destination (lat/lng or provider-safe URI), and only
  among `allowed_actions`.
- **Avoid logging raw destination** data anywhere (no addresses/coordinates in
  logs, analytics, or crash reports).
- **Show an unavailable state** when the backend denies or withholds the
  destination, surfacing the structured `unavailable_reason` as safe copy.
- **Refresh destination state with a safe GET** (re-read the navigation
  endpoint), consistent with the existing thin-client re-read pattern.
- **Not cache the destination longer than needed** — respect `expires_at`; drop
  sensitive data when it is no longer operationally required.
- **Not show the customer destination after cancellation / return** unless the
  backend explicitly says it is still allowed (return legs may surface only the
  store destination).

This preserves **Flutter presents; backend decides**: the client renders and
launches only backend-authorized destinations and never invents them.

---

## 8. Non-Scope Confirmation (Dr.1.5.I)

Dr.1.5.I is docs-only. It explicitly does **not** add any of the following:

- `url_launcher`.
- maps SDK (Apple MapKit / Google Maps / Mapbox / etc.).
- Apple Maps / Google Maps / Waze runtime links.
- embedded maps.
- ETA.
- address fields.
- coordinates.
- geocoding.
- polling.
- push / realtime.
- backend endpoints.
- mobile runtime code (`mobile/lib`).
- mobile test changes (`mobile/test`).
- dependency / lockfile changes (`pubspec.yaml`, `pubspec.lock`,
  `ios/Podfile.lock`).

The only artifact produced is this single document:
`docs/dr.1.5-navigation-handoff-gap.md`.

---

## 9. Relationship to Dr.1.5

This document supports the Dr.1.5 phase as follows:

- Dr.1.5.C–H productized the driver **operational** experience (operations home,
  delivery offers, active-delivery overview/timeline, pickup support,
  dropoff/compliance screens, and failed-delivery / return UX) on
  **existing** `/driver/*` data only.
- **Navigation remains a known, deliberate gap** — it was scoped out at contract
  lock (Dr.1.5.A) because no safe destination data exists.
- **Dr.1.5.I documents the exact reason the gap exists** (backend-blocked: no
  safe destination contract, plus privacy/compliance constraints for restricted
  products).
- **Future phases can use this document** to design a safe, backend-owned
  navigation contract and the corresponding mobile behavior, without
  re-discovering the constraints.

This keeps the Dr.1.5 surface honest: the app never fakes navigation, and the
gap is recorded rather than worked around.

---

## 10. Carry-Forward Recommendation

Navigation handoff should be picked up **after Dr.1.5**, in a dedicated
backend + mobile navigation phase (for example **Dr.1.9** or an equivalent
later phase). That phase should:

1. Design and ship the backend navigation contract (§6) with RBAC, tenancy,
   lifecycle gating, redaction, audit, expiry, and structured unavailable
   reasons.
2. Add the supporting schema/storage for safe destinations (without leaking PII
   into the existing PII-free read models).
3. Implement the mobile navigation card + provider handoff (§7), including the
   first introduction of `url_launcher` (or an equivalent vetted mechanism) —
   which is explicitly **deferred** out of Dr.1.5.
4. Complete a product/legal/privacy review for restricted-product destination
   exposure (display rules, screenshot/PII risk, retention).

Until that phase lands, the Driver App correctly ships **no** runtime
navigation.

---

## 11. Final Statement

Dr.1.5.I records that **runtime navigation handoff is intentionally blocked in
Dr.1.5** because the backend does not yet provide a safe destination contract,
and because restricted-product deliveries impose privacy/compliance constraints
that must be satisfied first. The mobile client must not invent addresses,
coordinates, or destinations. A future backend-owned contract and the
corresponding backend-gated mobile behavior are proposed here as documentation
only — **not implemented** in Dr.1.5. This subphase adds exactly one docs file
and changes no runtime, mobile, backend, dependency, or CI artifact.
