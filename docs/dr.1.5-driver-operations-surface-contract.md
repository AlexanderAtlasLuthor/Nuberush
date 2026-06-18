# Dr.1.5 — Driver Operations Surface / Active Delivery Productization Contract

> **Document type:** Phase contract (Dr.1.5.A — Contract Lock).
> **Change class:** DOCS-ONLY. This document defines scope; it ships no runtime.

---

## 1. Status

- **Phase:** Dr.1.5 — Driver Operations Surface / Active Delivery Productization.
- **Subphase authoring this document:** Dr.1.5.A — Contract Lock / Operations Surface Scope.
- **State:** Contract proposed. Dr.1.5.B (Phase Diagnostic) already executed → **WARN / PASS-leaning**.
- **Prior phase:** Dr.1.4 (Live Auth / Login Bootstrap + Real-device Smoke Readiness) — **CLOSED**.
- **Repo:** `main`, synced with `origin/main` (0 ahead / 0 behind at authoring time).
- **This subphase change class:** docs-only. No runtime, backend, web, supabase, render.yaml, or CI changes. No commit. No push.

---

## 2. Phase Objective

Convert the authenticated Driver App (post Dr.1.4) into a more complete **operational experience** for the driver — online presentation, delivery offers, active-delivery UX, pickup support, dropoff/compliance support, failed-delivery/return UX, a navigation-handoff gap doc, a minimal static safety/support surface, and a basic history foundation — **without adding any backend, schema, realtime, maps, OCR, photo, signature, or secrets.**

Dr.1.5 is a **mobile-only, thin-client, backend-existing-data-only** phase. It productizes what the existing `/driver/*` surface already serves. It must not invent data, authority, or transport the backend does not provide.

---

## 3. Prior Phase Context

Closed phases:

- **Dr.1.0** — Mobile Research + Driver App Product Architecture (docs-only; Uber-Driver-style vision adapted to NubeRush).
- **Dr.1.1** — Driver Backend Contract / Operational Foundations (driver profile, eligibility, assignments, delivery operational state; lifecycle: offer → accept/decline → start → arrive-store → pickup → depart-to-customer → arrive-customer).
- **Dr.1.2** — Driver Compliance Backend Surface (verify-age/21+, proof, complete, fail, return-to-store; store-side confirm-driver-return lives in the **orders** router; driver surface final = **5 GET / 12 POST**).
- **Dr.1.3** — Flutter Foundation / Driver App MVP (`mobile/` app: ApiClient/ApiConfig/ApiError, Driver Home, Assignment List/Detail, operational action buttons, compliance action dialogs, mobile CI).
- **Dr.1.4** — Live Auth / Login Bootstrap + Real-device Smoke Readiness (Supabase bootstrap, runtime config validation, login/logout, session restore, authenticated shell, ApiClient Bearer token, 401 recovery → signOut/LoginScreen, 403 stay-authenticated/no-access, mobile theme foundation, smoke docs).

Current Driver App capabilities at Dr.1.5 entry: real auth, Supabase bootstrap, login/logout, session restore, Bearer token, 401 recovery, 403 handling, mobile CI, smoke readiness.

---

## 4. Diagnostic Summary (Dr.1.5.B → WARN / PASS-leaning)

**Clean / reusable:**

- Mobile foundation is clean and reusable.
- Dr.1.4 auth/runtime is intact (config validation, Supabase init, session restore, login/logout, Bearer token, 401, 403).
- Mobile consumes **only** `/driver/*` (full 5 GET / 12 POST surface).
- No mobile use of `/orders/*`.
- No mobile use of admin/store endpoints.
- No token logging.
- No hardcoded secrets (only the public anon key via `--dart-define`).

**Backend gaps (no data behind these today):**

- No persisted online/offline driver availability.
- No realtime dispatch.
- No offer expiry.
- No push / websocket.
- No address / lat / lng / safe destination data for navigation.
- No pickup instructions; no store handoff PIN; no inventory handoff.
- No dropoff instructions; no customer PIN; no customer location/notes.
- No support / incident / bug-report backend.
- No OCR / ID photo / proof photo / signature.
- No earnings / payouts.

**Consequence:** Dr.1.5 must build only what existing read models serve. Read models are deliberately **PII-free** (store summary has name/code/timezone only — no address/coords; order summary has lifecycle status + timestamps only — no customer identity/notes/money/items).

---

## 5. Core Architecture Rule

> **Flutter presents. Backend decides.**

**Flutter MAY:**

- Render states (loading / loaded / empty / error / offline / unauthenticated / no-access).
- Organize screens, flows, and navigation.
- Show which actions are available (display-only gating from backend-reported status/state).
- Send requests to **existing** `/driver/*` endpoints.
- Show errors (normalized, non-destructive, with safe reload/retry).
- Perform safe GET refresh / re-read after an action.
- Improve UX (timelines, cards, panels, copy).

**Flutter MAY NOT:**

- Decide business rules.
- Compute legal compliance (age, gate outcomes).
- Mutate orders directly.
- Release inventory.
- Cancel orders.
- Confirm store-side returns.
- Invent real availability (no persisted online/offline).
- Invent realtime dispatch (no websocket/push/polling-as-dispatch).
- Invent coordinates / addresses / destinations.

The backend remains the single authority for lifecycle, compliance, inventory, tenancy, and RBAC. Any action the backend rejects surfaces as a normal error and the client re-reads authoritative state.

---

## 6. Scope

Dr.1.5 is:

- mobile-only.
- thin-client.
- backend-existing-data only.
- no new backend.
- no Supabase schema changes.
- no render.yaml changes.
- no `/orders/*` from mobile.
- no realtime / maps / OCR / photo / signature.

Dr.1.5 builds / productizes:

1. **Operations Home / Online Presentation Foundation** (Dr.1.5.C).
2. **Delivery Offer Surface** over `assignment.status = offered` (Dr.1.5.D).
3. **Active Delivery Overview + Timeline** (Dr.1.5.E).
4. **Pickup Support Screens** — state-only (Dr.1.5.F).
5. **Dropoff / Compliance Dedicated Screens** (Dr.1.5.G).
6. **Failed Delivery / Return UX** (Dr.1.5.H).
7. **Navigation Handoff Gap Doc** — docs-only / backend-blocked (Dr.1.5.I).
8. **Static Safety / Support Minimal Surface** (Dr.1.5.J).
9. **History Foundation** via `GET /driver/assignments?status=<terminal>` (Dr.1.5.K).
10. **State / Error / Visual UX Hardening** (Dr.1.5.L).
11. **Closure Document** (Dr.1.5.M).
12. **Final Validation / Phase Commit / Push / CI Watch** (Dr.1.5.N).

---

## 7. Non-Scope

Explicitly **out of scope** for Dr.1.5 (do not build, do not stub as if real):

- Persistent online/offline state.
- Driver availability backend.
- Realtime dispatch.
- Websocket.
- Push notifications.
- Offer expiry.
- Real offer countdown.
- Embedded maps.
- Apple / Google / Waze handoff real navigation (while no safe destination data exists).
- Fake coordinates.
- Fake addresses.
- OCR.
- ID photo upload.
- Proof photo upload.
- Signature capture.
- Customer PIN.
- Pickup PIN.
- Real pickup instructions.
- Real dropoff instructions.
- Support ticket backend.
- Incident submission backend.
- Earnings.
- Payouts.
- Wallet.
- Tax docs.
- Onboarding / documents.
- Android full CI / build.
- App Store / Play Store release.

---

## 8. Allowed Endpoint Surface

Only the existing `/driver/*` endpoints are permitted from mobile.

**GET:**

- `GET /driver/me`
- `GET /driver/eligibility`
- `GET /driver/assignments`
- `GET /driver/assignments?status=<terminal>`
- `GET /driver/assignments/{assignment_id}`
- `GET /driver/assignments/{assignment_id}/delivery-state`

**POST:**

- `POST /driver/assignments/{assignment_id}/accept`
- `POST /driver/assignments/{assignment_id}/decline`
- `POST /driver/assignments/{assignment_id}/start`
- `POST /driver/assignments/{assignment_id}/arrive-store`
- `POST /driver/assignments/{assignment_id}/pickup`
- `POST /driver/assignments/{assignment_id}/depart-to-customer`
- `POST /driver/assignments/{assignment_id}/arrive-customer`
- `POST /driver/assignments/{assignment_id}/verify-age`
- `POST /driver/assignments/{assignment_id}/proof`
- `POST /driver/assignments/{assignment_id}/complete`
- `POST /driver/assignments/{assignment_id}/fail`
- `POST /driver/assignments/{assignment_id}/return-to-store`

Notes:

- Compliance POSTs (`verify-age`, `proof`, `complete`, `fail`, `return-to-store`) carry a client-generated `Idempotency-Key`. Request bodies must continue to mirror the backend schema exactly (manual-checklist only; no ID image/number, DOB, OCR, biometric, photo, signature, or customer PII).
- `?status=<terminal>` uses the backend's existing `status` query param on the assignment list (terminal values: e.g. `completed`, `canceled`, `declined`, `expired`). No new endpoint is introduced.

---

## 9. Forbidden Endpoint Surface

Forbidden from mobile (must remain absent):

- `/orders/*`
- `/admin/*`
- `/stores/*`
- `/inventory/*`
- `/users/*`
- store-side **confirm-driver-return** (lives in the orders router; manager+; never driver-facing).
- any endpoint that cancels an order directly.
- any endpoint that releases inventory directly.

---

## 10. Product Decisions Frozen

1. **Online / offline**
   - Dr.1.5 implements **presentation-only** online/offline UI.
   - It must **not** persist availability.
   - It must **not** claim the backend is dispatching offers because the driver toggled "online."
   - Eligibility display may use `GET /driver/eligibility` (`can_go_online` + blockers), which is read-only.

2. **Offers**
   - Dr.1.5 presents `assignment.status = offered` as a delivery offer.
   - **No** realtime.
   - **No** push.
   - **No** websocket.
   - **No** real expiry / countdown.
   - Accept/decline reuse existing `POST .../accept` and `POST .../decline`.

3. **Navigation**
   - Dr.1.5.I is **docs-only / backend-blocked**.
   - **No** `url_launcher` dependency is added.
   - **No** invented coords / addresses / destinations.
   - A future backend must expose safe destination data **before** any runtime navigation handoff is built.

4. **History**
   - Dr.1.5.K **may** implement history using `GET /driver/assignments?status=<terminal>`.
   - **No** `/orders/*`.
   - **No** fake local history.
   - **No** earnings / payouts.

---

## 11. Visual Identity Rules

Dr.1.5 must preserve the NubeRush identity:

- Dark navy / near-black background.
- Orange primary / accent.
- Premium cards.
- Consistent radii.
- Consistent spacing.
- Consistent button hierarchy.
- Use `core/ui` primitives wherever possible (`NubeRushCard`, `NubeRushPrimaryButton`, `NubeRushSecondaryButton`, `NubeRushTextField`, `NubeRushScaffold`, `NubeRushBrandHeader`, `NubeRushInlineError`, `NubeRushLoadingState`).
- Avoid Material-generic drift (do not hand-build new ops screens with stock `Card`/`FilledButton` when a brand primitive exists; extend `core/ui` when a new primitive is needed — offer card, operations card, delivery timeline/stepper, action panel, support screen).

**Ecosystem rule:** Web App, Driver App, and the future Customer App are **one ecosystem** and must share the same visual identity. Every new screen must look NubeRush-consistent.

---

## 12. Subphase Plan

| Subphase | Title | Type |
|---|---|---|
| Dr.1.5.A | Contract Lock / Operations Surface Scope | docs-only |
| Dr.1.5.B | Phase Diagnostic | docs-only (executed → WARN/PASS-leaning) |
| Dr.1.5.C | Operations Home / Online Presentation Foundation | runtime (mobile) |
| Dr.1.5.D | Delivery Offer Surface | runtime (mobile) |
| Dr.1.5.E | Active Delivery Overview + Timeline | runtime (mobile) |
| Dr.1.5.F | Pickup Support Screens | runtime (mobile) |
| Dr.1.5.G | Dropoff / Compliance Dedicated Screens | runtime (mobile) |
| Dr.1.5.H | Failed Delivery / Return UX | runtime (mobile) |
| Dr.1.5.I | Navigation Handoff Gap Doc | docs-only |
| Dr.1.5.J | Static Safety / Support Minimal Surface | runtime (mobile) |
| Dr.1.5.K | History Foundation | runtime (mobile) |
| Dr.1.5.L | State / Error / Visual UX Hardening | runtime (mobile) |
| Dr.1.5.M | Closure Document | docs-only |
| Dr.1.5.N | Final Validation / Phase Commit / Push / CI Watch | process (single commit/push) |

---

## 13. Per-Subphase Contracts

### Dr.1.5.A — Contract Lock / Operations Surface Scope
- **Type:** docs-only.
- **Objective:** Freeze Dr.1.5 scope, endpoints, product decisions, visual identity, testing, and commit policy in this contract.
- **Allowed changes:** Create `docs/dr.1.5-driver-operations-surface-contract.md` only.
- **Forbidden changes:** Any runtime/backend/web/supabase/render/CI change; any dependency; any commit/push.
- **Expected validation:** Document exists; all required sections present; boundary rules stated; no non-docs changes.

### Dr.1.5.B — Phase Diagnostic
- **Type:** docs-only (already executed).
- **Objective:** Inspect real code; report readiness, data gaps, and boundary status before architecture.
- **Allowed changes:** Diagnostic report doc only (no edits to runtime).
- **Forbidden changes:** Any code change; any commit/push.
- **Expected validation:** Verdict produced (WARN / PASS-leaning); endpoints, gaps, and boundary findings documented.

### Dr.1.5.C — Operations Home / Online Presentation Foundation
- **Type:** runtime (mobile).
- **Objective:** Evolve Driver Home into an Operations Home with a **presentation-only** online/offline affordance driven by `GET /driver/eligibility` + `GET /driver/me`; no persisted availability.
- **Allowed changes:** `mobile/lib` presentation/controllers/widgets for the operations home; `core/ui` brand primitives; widget/controller tests.
- **Forbidden changes:** Persisting availability; any availability endpoint; claiming dispatch; backend/schema; `/orders/*`; realtime/push.
- **Expected validation:** `flutter analyze` + `flutter test`; tests assert the toggle is presentation-only and persists nothing; eligibility/profile render from real reads.

### Dr.1.5.D — Delivery Offer Surface
- **Type:** runtime (mobile).
- **Objective:** Present `assignment.status = offered` as a delivery offer card with store summary + safe delivery summary; accept/decline via existing POSTs.
- **Allowed changes:** Offer card UI, offer presentation in list/detail, controllers, tests.
- **Forbidden changes:** Realtime/push/websocket; real expiry/countdown; inventing offer-pool data; PII exposure; backend.
- **Expected validation:** `flutter analyze` + `flutter test`; accept/decline call only existing endpoints; no realtime; no fabricated expiry.

### Dr.1.5.E — Active Delivery Overview + Timeline
- **Type:** runtime (mobile).
- **Objective:** Compose an active-delivery overview + timeline/stepper from assignment lifecycle status, order timestamps, store context, and delivery `state`.
- **Allowed changes:** Overview screen, timeline primitive in `core/ui`, controllers, tests.
- **Forbidden changes:** Fake map/route/ETA/earnings; local transition computation; PII beyond what reads provide; backend.
- **Expected validation:** `flutter analyze` + `flutter test`; timeline derives strictly from backend-reported fields; raw status/state strings preserved.

### Dr.1.5.F — Pickup Support Screens
- **Type:** runtime (mobile).
- **Objective:** Dedicated "arrived at store" + "confirm pickup" screens driven by delivery state (`arrived_at_store` → `pickup`).
- **Allowed changes:** Pickup screens, action wiring to existing `arrive-store`/`pickup`, tests.
- **Forbidden changes:** Pickup PIN; inventory handoff; real pickup instructions; issue-report backend; `/orders/*`; backend.
- **Expected validation:** `flutter analyze` + `flutter test`; state-only behavior; no fabricated instructions/PIN.

### Dr.1.5.G — Dropoff / Compliance Dedicated Screens
- **Type:** runtime (mobile).
- **Objective:** Promote verify-age / proof / complete dialogs to dedicated screens, payloads identical to backend; no backend change.
- **Allowed changes:** Dropoff/compliance screens, reuse of existing compliance request bodies + `Idempotency-Key`, tests.
- **Forbidden changes:** OCR/photo/signature; DOB; local age computation; customer PIN; real dropoff instructions; backend/schema.
- **Expected validation:** `flutter analyze` + `flutter test`; payloads byte-for-byte match backend schema; backend remains compliance authority; no sensitive data captured.

### Dr.1.5.H — Failed Delivery / Return UX
- **Type:** runtime (mobile).
- **Objective:** Dedicated failure-reason + note flow (`fail`) and return-to-store flow (`return-to-store` start/arrive) driven by delivery state.
- **Allowed changes:** Failure/return screens, action wiring, tests.
- **Forbidden changes:** Store-side confirm-driver-return; releasing inventory; cancelling orders; `/orders/*`; backend.
- **Expected validation:** `flutter analyze` + `flutter test`; mobile never calls store-side confirm/inventory/order-cancel; state-driven gating only.

### Dr.1.5.I — Navigation Handoff Gap Doc
- **Type:** docs-only.
- **Objective:** Document that runtime navigation handoff is blocked until the backend exposes safe destination data; specify the future contract.
- **Allowed changes:** A navigation gap doc under `docs/`.
- **Forbidden changes:** Adding `url_launcher`; any maps/handoff runtime; inventing coords/addresses; backend.
- **Expected validation:** Doc states blocked/future; no dependency added; no runtime change.

### Dr.1.5.J — Static Safety / Support Minimal Surface
- **Type:** runtime (mobile).
- **Objective:** Static/local-only safety/support surface (help text, safe app/version diagnostics) with no backend submission.
- **Allowed changes:** Static support/safety screen(s), safe diagnostics display, tests.
- **Forbidden changes:** Support ticket / incident submission backend; logging tokens/PII; backend.
- **Expected validation:** `flutter analyze` + `flutter test`; screens are static/local; diagnostics expose no secrets/tokens/PII.

### Dr.1.5.K — History Foundation
- **Type:** runtime (mobile).
- **Objective:** Completed/terminal history list via `GET /driver/assignments?status=<terminal>` (+ existing detail read).
- **Allowed changes:** History list screen/controller, addition of the `status` query param to the existing list call, tests.
- **Forbidden changes:** `/orders/*`; fake local history; earnings/payouts; backend.
- **Expected validation:** `flutter analyze` + `flutter test`; history reads only `/driver/assignments` with a status filter; no fabricated rows.

### Dr.1.5.L — State / Error / Visual UX Hardening
- **Type:** runtime (mobile).
- **Objective:** Harden loading/empty/error/offline/unauth/no-access states; align all new screens to `core/ui` brand primitives; remove Material drift.
- **Allowed changes:** UX/state/visual refinements, `core/ui` primitives, tests.
- **Forbidden changes:** New endpoints; business logic; backend; dependencies beyond brand needs (no new transport/maps deps).
- **Expected validation:** `flutter analyze` + `flutter test`; consistent brand styling; safe non-destructive error handling preserved.

### Dr.1.5.M — Closure Document
- **Type:** docs-only.
- **Objective:** Document what Dr.1.5 delivered, what stayed out of scope, and carry-forwards.
- **Allowed changes:** A closure doc under `docs/`.
- **Forbidden changes:** Any runtime/backend change; commit/push (closure precedes the single Dr.1.5.N commit).
- **Expected validation:** Closure doc complete; scope honored; carry-forwards listed.

### Dr.1.5.N — Final Validation / Phase Commit / Push / CI Watch
- **Type:** process.
- **Objective:** Run full validation, then perform the **single** phase commit +
  push for all of Dr.1.5 and watch CI.
- **Allowed changes:** None to source beyond what prior subphases produced;
  commit + push only here.
- **Forbidden changes:** New scope; backend/web/supabase/render/CI source edits;
  per-subphase commits.
- **Expected validation:** `flutter pub get` → `flutter analyze` →
  `flutter test` → `flutter build ios --debug --no-codesign`; boundary checks
  clean; CI mobile job green after push.

---

## 14. Testing Policy

**Expected commands:**

- `flutter pub get`
- `flutter analyze`
- `flutter test`
- `flutter build ios --debug --no-codesign`

**Notes:**

- Android build remains **deferred** (Android SDK absent; no Android full
  CI/build in Dr.1.5).
- iOS build is validated **locally** (`flutter build ios --debug
  --no-codesign`); CI runs `pub get` / `analyze` / `test` only (no platform
  build in CI).
- Each runtime subphase must add **widget / controller / repository tests** as
  applicable. Tests use fakes (no `--dart-define`, no secrets).

**Mandatory boundary checks (every runtime subphase):**

- No `/orders/` usage in mobile.
- No `/admin/` usage in mobile.
- No `/stores/` usage in mobile.
- No `/inventory/` usage in mobile.
- No `/users/` usage in mobile.
- No token logging.
- No secrets.
- No hardcoded live credentials.

---

## 15. Security / Privacy / Thin-client Boundary

- Preserve the thin-client boundary: Flutter presents, backend decides.
- Backend owns RBAC, tenancy, lifecycle, compliance, inventory.
- No duplicated order/compliance/inventory rules in Flutter.
- No direct `/orders/*` usage from mobile.
- No store-side confirm-driver-return, order cancel, or inventory release from
  mobile.
- No secrets; only the public anon key via `--dart-define`;
  service-role/server-only material forbidden.
- No token logging; tokens never printed or surfaced; 401 fires once →
  signOut/Login, 403 stays authenticated (no-access).
- PII discipline: read models are PII-free by design; the app displays only what
  `/driver/*` returns and must not infer, fabricate, or expose customer
  identity/location.
- Idempotency-Key retained on all compliance POSTs.

---

## 16. Commit / Push Policy

- **No commit / push per subphase.**
- **Single commit + push only at the total close of Dr.1.5, in Dr.1.5.N.**
- Suggested commit message:

  ```text
  feat(driver-mobile): add Dr.1.5 operations surface
  ```

- Work on a branch off `main` as needed; the phase-close commit/push is the only
  one for Dr.1.5.

---

## 17. Pass / Fail Criteria

**PASS (this contract subphase, Dr.1.5.A) when:**

- `docs/dr.1.5-driver-operations-surface-contract.md` is created.
- Change is docs-only.
- No `mobile/lib` changes.
- No backend changes.
- No web changes.
- No supabase changes.
- No render.yaml changes.
- No CI changes.
- No commit.
- No push.
- Document includes all required sections (1–19).
- Document freezes mobile-only, thin-client, backend-existing-data-only scope.
- Document marks Navigation Handoff as docs-only / backend-blocked.
- Document marks online/offline as presentation-only.
- Document allows history via assignment status filter.
- Document preserves the no `/orders/*` mobile rule.

**FAIL when:**

- It edits runtime, backend, web, supabase, render.yaml, or CI.
- It adds dependencies.
- It creates commits or pushes.
- It permits mobile `/orders/*`.
- It permits online persistence without backend.
- It permits fake navigation.
- It permits realtime / push / websocket.
- It omits critical no-scope items.

**PASS criteria for the overall Dr.1.5 phase (evaluated at Dr.1.5.N):** all
runtime subphases honor the allowed/forbidden surface and product decisions;
`analyze`/`test` green; iOS debug build succeeds locally; boundary checks clean;
single phase commit/push; CI mobile job green.

---

## 18. Carry-Forwards

These are explicitly deferred to future phases (backend-blocked or out of scope):

- Persisted driver availability + go-online backend (enables real online/offline).
- Realtime dispatch (websocket/push) + offer expiry/countdown.
- Safe destination data (address/lat/lng/label) → runtime navigation handoff +
  `url_launcher` (Dr.1.5.I unblocks here).
- Pickup/dropoff instructions, pickup PIN, customer PIN, inventory handoff.
- OCR / ID photo / proof photo / signature capture.
- Support ticket / incident / bug-report backend.
- Earnings / payouts / wallet / tax docs.
- Onboarding / documents.
- Android full CI/build; App Store / Play Store release.

---

## 19. Final Contract Statement

Dr.1.5 — Driver Operations Surface / Active Delivery Productization — is a
**mobile-only, thin-client, backend-existing-data-only** phase. It productizes
the driver operational experience over the existing `/driver/*` surface
(5 GET / 12 POST) and adds **no** backend, schema, realtime, maps, OCR, photo,
signature, secret, or `/orders/*` usage. **Flutter presents; backend decides.**
Online/offline is presentation-only; offers are presented from
`assignment.status = offered` with no realtime; navigation handoff is docs-only /
backend-blocked; history is allowed via
`GET /driver/assignments?status=<terminal>`. The NubeRush visual identity (dark
navy, orange accent, premium cards, `core/ui` primitives) is preserved across the
shared Web / Driver / future Customer ecosystem. The phase ships as a **single**
commit/push at Dr.1.5.N. This contract is locked at Dr.1.5.A.
