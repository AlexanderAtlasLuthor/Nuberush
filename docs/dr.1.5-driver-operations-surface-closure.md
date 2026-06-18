# Dr.1.5 — Driver Operations Surface / Active Delivery Productization — Closure

> **Document type:** Phase closure document (Dr.1.5.M).
> **Change class:** DOCS-ONLY. This document ships no runtime, no dependency, no
> backend, no schema, and no mobile code. It is the **as-built authority** for
> Dr.1.5 immediately before the final Dr.1.5.N validation / commit / push.

---

## 1. Executive Status

- **Dr.1.5 — Driver Operations Surface / Active Delivery Productization** is
  **implementation-complete through subphase L**.
- **Final commit / push / CI is still pending** — it happens only in
  **Dr.1.5.N**. **No commit and no push have occurred yet.**
- All Dr.1.5 work remains **uncommitted** in the working tree, as intended (the
  phase ships as a single commit at Dr.1.5.N).
- Dr.1.5 is **mobile-only plus docs**.
- **No backend / web / supabase / render / CI / dependency changes** are part of
  the delivered scope. No `pubspec.yaml` / `pubspec.lock` / iOS lockfile change.
- HEAD remains at the Dr.1.4 base commit (`2317853 feat(driver-mobile): add
  Dr.1.4 live auth bootstrap`).

---

## 2. Phase Purpose

Dr.1.5 converts the authenticated Driver App (post Dr.1.4) from a
foundation / MVP into a more complete **operational driver experience**, built
strictly on the existing `/driver/*` surface and existing data. It productizes:

- **Operations Home** (presentation-only online/offline + operational entries).
- **Delivery Offers** (from `assignment.status = offered`).
- **Active Delivery** overview.
- **Pickup support** (state-only).
- **Dropoff / compliance** dedicated screens.
- **Failed delivery / return** UX.
- **Navigation gap documentation** (backend-blocked; docs-only).
- **Static safety / support** surface.
- **Delivery history**.
- **State / error / visual UX hardening**.

It adds **no** backend, schema, realtime, maps, OCR, photo, signature, secret,
or `/orders/*` usage.

---

## 3. Contract Boundary

> **Flutter presents. Backend decides.**

Confirmed across all Dr.1.5 surfaces:

- Flutter does **not** own lifecycle authority.
- Flutter does **not** own compliance authority.
- Flutter does **not** mutate orders directly.
- Flutter does **not** release inventory.
- Flutter does **not** confirm store-side returns (`confirm-driver-return` is
  never called from mobile).
- Flutter does **not** invent availability, dispatch, destination/coordinates,
  customer identity, proof, earnings, or support submissions.

The backend remains the single authority for lifecycle, compliance, inventory,
tenancy, and RBAC. Any rejected action surfaces as a normal error and the client
re-reads authoritative state via a safe GET.

---

## 4. Subphase Summary A–L

> Status legend: **CLOSED** = docs-only subphase finished; **PASS** = runtime
> subphase implemented + validated (analyze/test/iOS build green) and confirmed
> in its own formal validation pass.

### A — Contract Lock / Operations Surface Scope

- **Status:** CLOSED.
- **Scope type:** docs-only.
- **Delivered:** `docs/dr.1.5-driver-operations-surface-contract.md`.
- **Boundary:** Froze mobile-only, thin-client, backend-existing-data-only
  scope; allowed/forbidden endpoints; product decisions.

### B — Phase Diagnostic

- **Status:** CLOSED.
- **Scope type:** docs-only (executed → WARN / PASS-leaning).
- **Delivered:** diagnostic findings.
- **Boundary:** Confirmed mobile uses only `/driver/*`; no `/orders/*`;
  read models are PII-free.

### C — Operations Home / Online Presentation Foundation

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `driver_home_screen.dart`, `driver_home_controller.dart`,
  `driver_home_state.dart`; home tests.
- **Boundary:** Online/offline is **presentation-only** (no persistence, no
  dispatch claim); eligibility from `GET /driver/eligibility`.

### D — Delivery Offer Surface

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `delivery_offer_screen.dart`, `delivery_offer_controller.dart`,
  `delivery_offer_state.dart`, `delivery_offer_card.dart`; offer tests.
- **Boundary:** Offers from `assignment.status = offered`; accept/decline via
  existing POSTs; no realtime / expiry / push.

### E — Active Delivery Overview + Timeline

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `active_delivery_summary_card.dart`, `delivery_timeline.dart`,
  `next_action_panel.dart`, `compliance_status_card.dart`;
  `assignment_detail_screen.dart`; overview tests.
- **Boundary:** Timeline / next-action derived strictly from backend-reported
  status/state; no fake ETA / route / earnings.

### F — Pickup Support Screens

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `pickup_support_screen.dart`, `pickup_checklist.dart`,
  `pickup_issue_info_screen.dart`; pickup tests.
- **Boundary:** State-only (`arrive-store` / `pickup`); no pickup PIN, inventory
  handoff, or fake instructions.

### G — Dropoff / Compliance Dedicated Screens

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `dropoff_support_screen.dart`, `age_verification_screen.dart`,
  `age_verification_failed_screen.dart`, `proof_of_delivery_screen.dart`,
  `complete_delivery_screen.dart`; dropoff tests.
- **Boundary:** Payloads byte-for-byte match backend; `Idempotency-Key`
  retained; no OCR / photo / signature / DOB / local age compute.

### H — Failed Delivery / Return UX

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `failed_return_flow.dart`, `failed_return_flow_screen.dart`,
  `failed_delivery_reason_screen.dart`, `return_required_screen.dart`,
  `return_to_store_screen.dart`, `return_pending_confirmation_screen.dart`;
  failed-return tests.
- **Boundary:** Uses existing `fail` / `return-to-store` only; no store-side
  confirm, order cancel, or inventory release.

### I — Navigation Handoff Gap Doc

- **Status:** CLOSED.
- **Scope type:** docs-only / backend-blocked.
- **Delivered:** `docs/dr.1.5-navigation-handoff-gap.md`.
- **Boundary:** No `url_launcher`, maps SDK, ETA, geocoding, or fake coords;
  future contract documented as not-implemented.

### J — Static Safety / Support Minimal Surface

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `safety_toolkit_screen.dart`, `emergency_help_screen.dart`,
  `support_center_screen.dart`, `report_bug_info_screen.dart`,
  `report_incident_info_screen.dart`; safety/support tests.
- **Boundary:** Static / local-only; no backend submission, live chat,
  phone/SMS, or token/config display.

### K — History Foundation

- **Status:** PASS.
- **Scope type:** mobile runtime + tests.
- **Delivered:** `delivery_history_screen.dart`,
  `delivery_history_controller.dart`, `delivery_history_state.dart`,
  `history_assignment_card.dart`; repo `fetchAssignments({String? status})`;
  history + repository tests.
- **Boundary:** History via `GET /driver/assignments?status=<terminal>` only;
  no `/orders/*`, no fake history, no earnings / payouts.

### L — State / Error / Visual UX Hardening

- **Status:** PASS.
- **Scope type:** mobile runtime (targeted).
- **Delivered:** `assignment_detail_screen.dart` (brand primitives / tokens).
- **Boundary:** UI-only hardening; retry stays GET-only; action errors
  non-destructive; 401/403 unchanged; no scope creep.

---

## 5. Runtime Surface Delivered

The Driver App now provides these driver-facing surfaces (all built on existing
data; backend remains the authority):

- **Operations Home** — driver status/readiness, presentation-only
  online/offline affordance, operational entries (Assignments / Offers / Active
  Delivery / Safety & Support / History).
- **Delivery Offers** — offer card with store + safe delivery summary; accept /
  decline.
- **Active Delivery Overview** — mission summary card + **Delivery Timeline** +
  **Next Action panel** + **Compliance Status** card, plus the operational and
  compliance action groups.
- **Store Pickup support** — guided arrive-at-store / confirm-pickup flow +
  static pickup-issue guidance.
- **Customer Dropoff / Compliance flow** — verify-age (21+), proof-of-delivery,
  complete, and report-failed surfaces.
- **Failed Delivery / Return flow** — failed-delivery reason, return-required,
  return-to-store (start/arrive), and return-pending-confirmation surfaces.
- **Static Safety / Support toolkit** — safety hub, emergency guidance, support
  center, report-app-issue, and report-incident guidance (all static/local).
- **Delivery History** — terminal assignment list with status filters
  (completed / canceled / declined / expired) and read-only detail navigation.

---

## 6. Endpoint / Data Source Summary

Dr.1.5 uses **only** the existing permitted driver endpoints.

**GET (reads):**

- `GET /driver/me`
- `GET /driver/eligibility`
- `GET /driver/assignments`
- `GET /driver/assignments?status=<terminal>` (new history filter — same
  endpoint, existing `status` query param; no new endpoint)
- `GET /driver/assignments/{assignment_id}`
- `GET /driver/assignments/{assignment_id}/delivery-state`

**POST (actions already supported by the app):**

- `accept`, `decline`, `start`, `arrive-store`, `pickup`,
  `depart-to-customer`, `arrive-customer`
- `verify-age`, `proof`, `complete`, `fail`, `return-to-store`
  (compliance POSTs carry a client-generated `Idempotency-Key`; bodies mirror
  the backend schema exactly)

**No new backend endpoints were added by Dr.1.5.** The only repository change
was an optional `status` query param on the existing assignments-list call
(Dr.1.5.K), which appends `?status=` only when non-empty — the default
no-status call is byte-for-byte unchanged.

---

## 7. Forbidden Endpoint / Scope Confirmation

Dr.1.5 adds **no** mobile runtime usage of:

- `/orders/*`
- `/admin/*`
- `/stores/*`
- `/inventory/*`
- `/users/*`
- `/history/*`
- `/earnings/*`
- `/payouts/*`
- `confirm-driver-return`
- direct order cancel
- direct inventory release
- store-side return confirmation

It also adds **no**:

- maps / navigation runtime
- `url_launcher` runtime
- Apple / Google / Waze handoff
- embedded maps
- ETA
- OCR
- photo upload
- camera
- signature
- customer PIN
- pickup PIN
- support ticket backend
- incident backend
- live chat
- earnings / payouts / taxes
- fake address / lat / lng / customer PII

> Comments documenting non-scope exist in some files, but no corresponding
> runtime functionality exists. Boundary greps over `mobile/lib` return no
> runtime hits for the items above.

---

## 8. Security / Privacy Notes

- The Driver App remains **PII-minimized**: read models expose store
  name/code/timezone and order lifecycle status/timestamps only.
- **No** customer address / phone / name / coordinates were introduced anywhere.
- **No** raw auth/session token display; tokens are never printed or surfaced.
- **No** raw config display (only the public anon key via `--dart-define`).
- Static support screens **warn** against sharing PII / passwords / tokens /
  payment info / ID photos / full addresses.
- **Navigation remains blocked** until the backend provides a safe destination
  contract (documented in Dr.1.5.I).
- Compliance screens are **manual checklists only** — they do not scan IDs or
  upload photos / signatures, and do not compute legal age locally.

---

## 9. Validation Summary

Validation completed per runtime subphase (C–L) and re-confirmed at each formal
validation pass:

- `flutter pub get` — passed.
- `flutter analyze` — passed (No issues found).
- `flutter test` — passed.
- `flutter build ios --debug --no-codesign` — passed (built `Runner.app`).
- Android build — **skipped** (Android SDK absent); reported as skipped, **not**
  a failure.
- Test count grew as surfaces were added; **final reported suite at L: 338 tests
  passing.**

Status of commit / CI:

- **No commit and no push have occurred yet.**
- **Dr.1.5 has not been pushed and CI has not run for it.** The final full
  validation, the single phase commit, the push, and the GitHub Actions CI watch
  are all still required and happen only in **Dr.1.5.N**.

---

## 10. Files / Areas Delivered

Grouped by feature (representative, not line-by-line):

- **Operations Home / shell:** `driver_home_screen.dart`,
  `driver_home_controller.dart`, `driver_home_state.dart`; `app/router.dart`
  (wires Assignments / Offers / History / read-only detail navigation).
- **Offer surface:** `delivery_offer_screen.dart`,
  `delivery_offer_controller.dart`, `delivery_offer_state.dart`,
  `delivery_offer_card.dart`.
- **Active delivery overview:** `assignment_detail_screen.dart`,
  `active_delivery_summary_card.dart`, `delivery_timeline.dart`,
  `next_action_panel.dart`, `compliance_status_card.dart`.
- **Pickup support:** `pickup_support_screen.dart`, `pickup_checklist.dart`,
  `pickup_issue_info_screen.dart`.
- **Dropoff / compliance:** `dropoff_support_screen.dart`,
  `age_verification_screen.dart`, `age_verification_failed_screen.dart`,
  `proof_of_delivery_screen.dart`, `complete_delivery_screen.dart`
  (reusing existing `compliance_requests.dart` / `compliance_dialogs.dart`).
- **Failed-return:** `failed_return_flow.dart`, `failed_return_flow_screen.dart`,
  `failed_delivery_reason_screen.dart`, `return_required_screen.dart`,
  `return_to_store_screen.dart`, `return_pending_confirmation_screen.dart`.
- **Safety / support:** `safety_toolkit_screen.dart`,
  `emergency_help_screen.dart`, `support_center_screen.dart`,
  `report_bug_info_screen.dart`, `report_incident_info_screen.dart`.
- **History:** `delivery_history_screen.dart`,
  `delivery_history_controller.dart`, `delivery_history_state.dart`,
  `history_assignment_card.dart`; `data/driver_repository.dart`
  (`fetchAssignments({String? status})`).
- **Navigation gap doc:** `docs/dr.1.5-navigation-handoff-gap.md`.
- **Repository / test support:** `data/driver_repository.dart`,
  `test/features/driver/fake_driver_repository.dart`, and focused widget /
  controller / repository tests added per subphase.
- **Docs:** `docs/dr.1.5-driver-operations-surface-contract.md` (A),
  `docs/dr.1.5-navigation-handoff-gap.md` (I), and this closure (M).

---

## 11. Known Non-Blocking Notes

- Android SDK / build remains **skipped** locally (absent SDK).
- iOS build is **debug / no-codesign** only.
- **Navigation runtime** remains deferred (backend-blocked; see Dr.1.5.I).
- **Support / incident submission** remains deferred (no backend).
- **Earnings / payouts** remain deferred.
- **Real dispatch / persisted online availability / push / realtime** remain
  deferred.
- The Dr.1.3.F **assignment list** screen may still use older Material
  primitives (raw `Scaffold` / `CircularProgressIndicator`); it is outside the
  Dr.1.5 C–L surface scope and is a candidate for a future cleanup.
- **Dr.1.5.N** still must perform the final full validation, the single phase
  commit, the push, and the CI watch.

---

## 12. Carry-Forwards / Recommended Next Phases

Recommended future work after Dr.1.5:

- Real **persisted driver online / availability** backend (enables genuine
  online/offline).
- **Realtime dispatch / push notifications** (+ offer expiry / countdown).
- **Navigation backend contract** + runtime handoff (unblocks Dr.1.5.I; first
  introduction of `url_launcher` or an equivalent vetted mechanism).
- **OCR / photo / signature / PIN** compliance upgrade after legal / product
  review.
- **Support / incident backend** (ticketing, incident submission, possibly
  chat).
- **Earnings / performance / rewards.**
- **Android build / CI** and **iOS signing / deployment.**
- **Customer app** integration (shared NubeRush ecosystem identity).
- **App Store / Play Store** release readiness.

---

## 13. Dr.1.5.N Preparation

Dr.1.5.N should:

1. Run the **final full validation**: `flutter pub get` → `flutter analyze` →
   `flutter test` → `flutter build ios --debug --no-codesign`.
2. **Review changed files** (`git status --short`, `git diff --name-only`).
3. **Confirm forbidden boundaries** (no `/orders/*`, no forbidden endpoints, no
   maps/OCR/photo/signature/PIN/support/earnings runtime).
4. **Confirm no backend / web / supabase / render / CI / dependency changes**
   (no `pubspec` / lockfile change).
5. Create **one** phase commit (suggested message:
   `feat(driver-mobile): add Dr.1.5 operations surface`).
6. **Push** fast-forward to `origin/main`.
7. **Watch GitHub Actions CI** (mobile job: pub get / analyze / test).
8. **Confirm `HEAD == origin/main`** and the working tree is clean.

---

## 14. Final Statement

Dr.1.5 — Driver Operations Surface / Active Delivery Productization — is
**implementation-complete through subphase L** and is the **as-built authority**
recorded here. It is **mobile-only plus docs**, uses only the existing
`/driver/*` endpoints, adds **no** backend / dependency / config changes, and
preserves **Flutter presents; backend decides** throughout. The phase has **not
yet been committed, pushed, or run through CI** — that is the sole remaining work
for **Dr.1.5.N**.
