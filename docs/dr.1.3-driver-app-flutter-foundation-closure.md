# Dr.1.3 Driver App Flutter Foundation Closure

This is the as-built authority for Dr.1.3 (the Flutter driver-app MVP foundation)
and the starting point for the next driver-app phase. It records what shipped,
the boundaries preserved, the endpoints consumed, the validation evidence, and
the handoff plan for the phase-level commit/push in Dr.1.3.L.

## Phase status

- **Dr.1.3 status:** implementation complete, pending phase-level commit, push,
  and hosted-CI watch.
- **Commit/push status:** not yet performed in Dr.1.3.K. No commit or push was
  created in this subphase.
- **Current local state:** the Dr.1.3.A contract-lock commit `2339007` exists
  locally and is unpushed; subphases B through K are accumulated in the working
  tree and remain uncommitted until Dr.1.3.L.
- **Next phase step:** Dr.1.3.L performs the phase-level commit, push, and
  GitHub Actions watch.

## Roadmap position

- **Dr.1.0** — Mobile research and driver-app product architecture.
- **Dr.1.1** — Driver backend contract and operational foundations.
- **Dr.1.2** — Driver compliance backend surface.
- **Dr.1.3** — Flutter foundation / driver-app MVP (this phase).

## Workflow rules followed

- One diagnosis covered the full phase (Dr.1.3.0), not one diagnosis per
  subphase.
- Each subphase followed the same flow: implementation prompt, implementation
  report, validation prompt, then a pass/fail review.
- No subphase committed or pushed.
- Commit and push are deferred to phase-level closure (Dr.1.3.L).

## Scope summary

Dr.1.3 delivered the following, all under `mobile/`:

- A Flutter application project under `mobile/`.
- The NubeRush Driver app identity (`com.nuberush.driver`).
- App configuration and a public-only environment boundary.
- A core API client with typed error handling.
- A Supabase auth/session and secure token-storage boundary.
- Read-only driver profile and eligibility.
- Read-only assignment list, detail, and delivery state.
- Operational action buttons.
- Compliance action screens.
- Mobile state/error/loading/retry hardening.
- Flutter CI readiness (analyze + test).

## Subphase summary

### Dr.1.3.0 Full phase diagnostic

- **Status:** complete.
- **Areas:** repository diagnosis and phase planning.
- **Deliverables:** a single phase-wide diagnosis defining the subphase plan and
  the thin-client boundary.
- **Validation:** plan accepted; no code produced.
- **Boundaries:** established mobile-only scope and backend authority up front.

### Dr.1.3.A Contract lock / Flutter foundation scope

- **Status:** complete (committed locally as `2339007`).
- **Areas:** `docs/dr.1.3-driver-app-flutter-foundation-contract.md`.
- **Deliverables:** the locked foundation contract for the phase.
- **Validation:** documentation review.
- **Boundaries:** contractually fixed scope, identity, and forbidden items.

### Dr.1.3.B Flutter project skeleton + app identity

- **Status:** complete (accumulated, uncommitted).
- **Areas:** `mobile/` project, `lib/app/`, `lib/main.dart`, app metadata, and a
  path-filter `changes` gate in `.github/workflows/ci.yml`.
- **Deliverables:** the app shell, NubeRush Driver identity, and the
  `com.nuberush.driver` bundle/application ID.
- **Validation:** analyze and tests pass; iOS debug build succeeds.
- **Boundaries:** iOS/Android only; no web Capacitor identity reuse.

### Dr.1.3.C Core API client + config + ApiError

- **Status:** complete (accumulated).
- **Areas:** `lib/core/api/`, `lib/core/config/`.
- **Deliverables:** the `ApiClient`, API config, and a normalized `ApiError`
  type (including a network/status-0 variant).
- **Validation:** API client unit tests pass.
- **Boundaries:** public config only; no server-only secrets.

### Dr.1.3.D Supabase auth session + secure token storage

- **Status:** complete (accumulated).
- **Areas:** `lib/core/auth/`.
- **Deliverables:** the app-owned `AuthSession` interface, `SecureSessionStore`
  (Keychain/Keystore), and the `AccessTokenProvider` bridge for the Bearer
  header.
- **Validation:** auth/session/storage unit tests pass.
- **Boundaries:** Supabase used for authentication only, never business data;
  tokens never logged or stored in plain preferences; no login UI.

### Dr.1.3.E Driver home / profile / eligibility read-only

- **Status:** complete (accumulated).
- **Areas:** `lib/features/driver/domain/`, `lib/features/driver/data/`,
  `lib/features/driver/presentation/driver_home_*`.
- **Deliverables:** read-only driver profile and eligibility, the home
  controller/state/screen, and the read repository.
- **Validation:** model, repository, and controller/screen tests pass.
- **Boundaries:** read-only; no actions; no polling.

### Dr.1.3.F Assignment list + detail + delivery state

- **Status:** formally closed.
- **Areas:** `assignment_list_*`, `assignment_detail_*`, delivery-state domain.
- **Deliverables:** assignment list, detail, and delivery-state read flows with
  loading/empty/error/offline/unauthenticated states.
- **Validation:** list/detail/state controller and screen tests pass.
- **Boundaries:** GET-only; backend remains the authority.

### Dr.1.3.G Operational action buttons

- **Status:** formally closed.
- **Areas:** `driver_operational_action.dart`, assignment detail
  controller/state/screen, repository action methods.
- **Deliverables:** the seven operational POST actions (accept, decline, start,
  arrive-store, pickup, depart-to-customer, arrive-customer) with a
  display-only action mapping and re-read after each action.
- **Validation:** operational action repository, controller, and UI tests pass.
- **Boundaries:** bodyless POSTs; no local lifecycle authority; no optimistic
  transitions; backend re-read after each action.

### Dr.1.3.H Compliance action screens

- **Status:** formally closed.
- **Areas:** `compliance_requests.dart`, `driver_compliance_action.dart`,
  `compliance_dialogs.dart`, `lib/core/util/idempotency.dart`, repository
  compliance methods.
- **Deliverables:** the five compliance POST actions (verify-age, proof,
  complete, fail, return-to-store) with exact backend payloads and an
  `Idempotency-Key` per attempt.
- **Validation:** compliance request, repository, controller, and UI tests pass;
  payloads verified against backend schemas.
- **Boundaries:** manual-checklist only; no OCR/photo/signature/file/ID-image
  data; `complete` is bodyless; no `confirm-driver-return`; no `/orders/`.

### Dr.1.3.I Mobile state/error/loading/retry hardening

- **Status:** formally closed.
- **Areas:** `assignment_detail_state.dart`,
  `assignment_detail_controller.dart`, `assignment_detail_screen.dart`, related
  tests, and the shared test fake.
- **Deliverables:** non-destructive inline action errors that preserve loaded
  detail, a GET-only reload, a dismiss action, safe message normalization, and a
  shared single-in-flight guard.
- **Validation:** controller and UI tests pass (191 total after this subphase).
- **Boundaries:** full-screen states reserved for initial-load failures; 401
  still routes to unauthenticated; no mutation auto-retry; no offline queue.

### Dr.1.3.J Flutter test/analyze/CI readiness

- **Status:** formally closed.
- **Areas:** `.github/workflows/ci.yml`, `mobile/README.md`.
- **Deliverables:** a `mobile` CI job (pub get / analyze / test) gated on
  `mobile/**` and the workflow-change fail-safe, pinned to Flutter 3.38.5
  stable, with documented CI policy.
- **Validation:** YAML parse passes; existing backend/frontend/RLS jobs
  preserved; analyze and tests pass locally.
- **Boundaries:** no platform builds, signing, deployment, or secrets in CI.

### Dr.1.3.K Phase closure document + final validation

- **Status:** complete (this document).
- **Areas:** `docs/dr.1.3-driver-app-flutter-foundation-closure.md`.
- **Deliverables:** this as-built closure document plus final local validation.
- **Validation:** documented in the CI / validation summary below.
- **Boundaries:** documentation only; no runtime app changes; no commit/push.

## Final mobile architecture

The app uses a feature-first layout with a thin core:

- `mobile/lib/app/` — application composition root, providers, and read-only
  navigation/router.
- `mobile/lib/core/api/` — `ApiClient`, API config, and the normalized
  `ApiError`.
- `mobile/lib/core/auth/` — `AuthSession`, `SecureSessionStore`, and the access
  token provider bridge.
- `mobile/lib/core/config/` — environment and Supabase config from public
  `--dart-define` values only.
- `mobile/lib/core/util/` — the client-side idempotency-key generator.
- `mobile/lib/features/driver/domain/` — profile, eligibility, assignment,
  delivery-state, and compliance-request models plus JSON parsing.
- `mobile/lib/features/driver/data/` — the driver repository (the single
  endpoint boundary).
- `mobile/lib/features/driver/presentation/` — home, assignment list, assignment
  detail, operational/compliance action definitions, and compliance dialogs with
  their controllers and view states.
- `mobile/test/` — unit and widget tests across core and driver features.

### Thin-client boundary

- The mobile app renders backend-reported state and submits user-initiated
  actions.
- The backend remains the authority for lifecycle, compliance, order, and
  inventory decisions.
- The mobile app never decides final operational or compliance outcomes; action
  buttons are offered from a conservative, display-only mapping.
- After any mutation the app re-reads authoritative backend detail and
  delivery-state rather than applying an optimistic local transition.

## Consumed backend endpoints

### Read-only

- `GET /driver/me`
- `GET /driver/eligibility`
- `GET /driver/assignments`
- `GET /driver/assignments/{assignment_id}`
- `GET /driver/assignments/{assignment_id}/delivery-state`

### Operational

- `POST /driver/assignments/{assignment_id}/accept`
- `POST /driver/assignments/{assignment_id}/decline`
- `POST /driver/assignments/{assignment_id}/start`
- `POST /driver/assignments/{assignment_id}/arrive-store`
- `POST /driver/assignments/{assignment_id}/pickup`
- `POST /driver/assignments/{assignment_id}/depart-to-customer`
- `POST /driver/assignments/{assignment_id}/arrive-customer`

### Compliance

- `POST /driver/assignments/{assignment_id}/verify-age`
- `POST /driver/assignments/{assignment_id}/proof`
- `POST /driver/assignments/{assignment_id}/complete`
- `POST /driver/assignments/{assignment_id}/fail`
- `POST /driver/assignments/{assignment_id}/return-to-store`

### Endpoint notes

- Compliance actions send a client-generated `Idempotency-Key` header per
  attempt.
- `complete` is a bodyless POST.
- `return-to-store` carries an `action` of `start` or `arrive`.
- No `/orders/` endpoint is consumed by the mobile app.

## Explicit non-scope

Dr.1.3 deliberately did not implement:

- Login UI.
- Live Supabase bootstrap into the production shell beyond the boundary/config
  readiness.
- Maps, navigation, or ETA.
- Push notifications.
- Earnings.
- Customer chat or support.
- OCR.
- ID image upload.
- Photo upload.
- Signature capture.
- An offline mutation queue.
- Polling.
- Store return confirmation.
- `POST /orders/{order_id}/confirm-driver-return`.
- Payments or refunds.
- Android build or Android CI.
- iOS CI, signing, or deployment.
- App Store or Play Store release.

## Security, compliance, and privacy boundaries

- No service-role key is referenced or used.
- No real secrets are present in the app or CI.
- Public configuration is supplied only via `--dart-define`
  (`NUBERUSH_API_BASE_URL`, `NUBERUSH_SUPABASE_URL`,
  `NUBERUSH_SUPABASE_ANON_KEY`).
- Access and refresh tokens use the secure-storage boundary
  (Keychain/Keystore); token values are never logged.
- The `Idempotency-Key` is never logged.
- No sensitive ID fields are persisted or sent.
- No image, photo, or signature data is captured or transmitted.
- The app applies no local order or inventory mutation.
- The app holds no local compliance authority.
- The app consumes no `/orders/` endpoint.

## CI and validation summary

Latest local validation for Dr.1.3.K:

- `flutter pub get` — PASS.
- `flutter analyze` — PASS (no issues).
- `flutter test` — PASS, 191 tests.
- iOS local debug no-codesign build (`flutter build ios --debug --no-codesign`)
  — PASS.
- Android build — skipped because the Android SDK is not installed locally.
- Workflow YAML parse — PASS.
- A `mobile` CI job (pub get / analyze / test) was added in Dr.1.3.J.
- Hosted GitHub CI has not yet been observed for Dr.1.3 because no push has been
  performed.

## Repo state before Dr.1.3.L

Expected working-tree state entering Dr.1.3.L:

- `main` is ahead of `origin/main` by one commit due to the Dr.1.3.A contract
  commit `2339007`.
- `.github/workflows/ci.yml` is modified (accumulated Dr.1.3.B path-filter gate
  plus the Dr.1.3.J mobile job).
- `mobile/` is untracked and accumulated until commit.
- `docs/dr.1.3-driver-app-flutter-foundation-closure.md` is newly added.
- No backend, web, frontend, supabase, or render.yaml changes.
- No push has been performed.

## Recommended Dr.1.3.L commit strategy

Two options:

1. Keep the Dr.1.3.A contract commit `2339007` and create one additional commit
   covering subphases B through K.
2. Squash or soft-reset the contract commit and the B through K work into a
   single Dr.1.3 commit.

Recommended default:

- Keep the `2339007` contract commit and create one final B through K commit,
  unless instructed otherwise.

Suggested final commit message for B through K:

- `feat(driver-mobile): add Dr.1.3 Flutter driver app MVP`

Push and watch:

- Do not push until final validation passes in Dr.1.3.L.
- After committing, push and watch the GitHub Actions run for the `mobile` job
  and the unaffected backend/frontend/RLS gates.

## Carry-forwards

- Android SDK, build, and CI are deferred.
- iOS CI, build, signing, and deployment are deferred.
- Hosted mobile CI will not be observed until the first push.
- Branch-protection caveat: if the conditional `mobile` job (or any gated job)
  becomes a required status check, confirm that path-skipped runs do not create
  a required-check dead zone.
- Login UI is deferred.
- Live Supabase bootstrap and runtime auth-flow refinement are deferred.
- Maps, navigation, and ETA are deferred.
- OCR, photo, and signature capture are deferred.
- Store return confirmation remains backend/store-side, not driver mobile.
- Optional: a smoother refresh-in-place for the inline action-error reload
  (currently routes through the full reload path).
- Optional: surfacing recorded verify-age and proof results.
- Optional: telemetry and analytics.

## Next phase recommendation

This is a recommendation only; it does not create a new phase plan.

- The next driver-mobile phase (Dr.1.4 or equivalent) should likely focus on
  live auth/login bootstrap, app environment wiring, and real-device smoke
  readiness.
- Maps and navigation can follow once auth and assignment actions are stable.
- Android CI can be added later as CI/platform hardening.
