# Dr.1.4 — Live Auth / Login Bootstrap + Real-device Smoke Readiness Contract

> Official phase contract for NubeRush Dr.1.4.
> This document is authored in subphase **Dr.1.4.A** and is **docs-only**.
> It defines scope, boundaries, and closure criteria for converting the
> Flutter Driver App MVP foundation into a real, driver-usable application.

## 1. Phase Status

- **Dr.1.4 is starting.**
- **Dr.1.0, Dr.1.1, Dr.1.2 and Dr.1.3 are closed.**
- **Dr.1.4.A is docs-only** — it creates this contract and nothing else.
- No runtime code, backend, web, supabase, or `render.yaml` changes are made in Dr.1.4.A.
- **No commit / no push** until phase-level final closure in **Dr.1.4.H**.
- Subphases B–G are implementation steps with **no commit/push between them**.

## 2. Background

- **Dr.1.3 delivered the Flutter Driver App MVP foundation** — app skeleton,
  driver screens, repository/endpoint centralization, and the auth/runtime
  *boundaries* (`AuthSession`, `GoTrueAuthGateway`, `SecureSessionStore`,
  `accessTokenProviderFor()`, `ApiClient` with `AccessTokenProvider`).
- **Dr.1.3 did NOT deliver live login / runtime auth.** The boundaries exist
  but are not wired into a running app: there is no `Supabase.initialize`, no
  login/logout UI, no session restore, no authenticated app shell, and no real
  Bearer-token injection into `ApiClient`.
- **Dr.1.4 turns that foundation into real auth / runtime readiness** so a real
  driver can install, configure, log in, restore a session, and use the
  authenticated driver screens against the live backend — with NubeRush visual
  identity applied.

## 3. Diagnostic Summary

Based on the Dr.1.4.0 diagnostic (Verdict: **PASS**):

- **Repo is clean and synced** with `origin/main`, except the known untracked
  file `docs/dr.1.3-progress-report.md`.
- **Local mobile validation passed:**
  - `flutter pub get` — OK.
  - `flutter analyze` — OK.
  - `flutter test` — **191 tests** passing.
  - iOS debug **no-codesign** build — OK.
- **Android SDK absent / skipped** — Android build/CI is out of scope unless the
  SDK becomes available.
- **Backend is ready for Supabase JWT** — it already accepts Supabase-issued
  access tokens.
- **No backend changes required** for Dr.1.4.
- **Main risk is visual identity mismatch** — mobile currently uses a generic
  Material teal theme and must adopt NubeRush identity before or alongside login.

## 4. Objective

Define and (across subphases B–H) deliver:

- **Public runtime config validation** for required public environment values.
- **`Supabase.initialize`** runtime bootstrap.
- **Login / logout** using Supabase email/password.
- **Session restore** from the current Supabase session.
- **Authenticated / unauthenticated app shell** with an auth gate.
- **Real Bearer-token injection** into `ApiClient` for driver endpoints.
- **401 recovery** (auth expired → safe return to login).
- **Real-device smoke readiness** documentation.
- **NubeRush visual identity foundation** for the mobile app.

## 5. Scope

In scope for Dr.1.4 (across its subphases):

- **Contract Lock** (this document, Dr.1.4.A).
- **NubeRush mobile theme foundation** (colors, typography, components, brand).
- **Supabase runtime bootstrap** (`Supabase.initialize`).
- **`ConfigRequired` state** when public config is missing.
- **Login UI** (Supabase email/password sign-in).
- **Logout** (clear session, return to login).
- **Session restore** from current Supabase session at startup.
- **`AuthGate`** that routes between unauthenticated and authenticated trees.
- **`AuthenticatedDriverShell`** hosting driver home + assignment/action screens.
- **`AppProviders` real dependency composition** (wiring boundaries together).
- **`ApiClient` `accessTokenProvider` wiring** (`accessTokenProviderFor(authSession)`).
- **401 auth-expired handling** (safe message, clear state, return to login).
- **403 no-access handling** (stay authenticated, safe no-access message).
- **README / smoke docs** for real-device testing.
- **Tests** covering config, auth transitions, login, logout, gate, token
  injection, 401/403, and theme/brand rendering.
- **Final validation / commit / push / CI watch** at phase end (Dr.1.4.H only).

## 6. Non-Scope

Explicitly excluded from Dr.1.4:

- maps / navigation / ETA.
- Apple Maps / Google Maps / Waze handoff.
- push notifications.
- OCR.
- ID photo upload.
- proof photo upload.
- signature capture.
- file picker.
- onboarding / documents.
- vehicle profile.
- training.
- earnings / history / performance.
- customer app.
- store-side confirm-driver-return UI.
- backend compliance changes.
- new backend endpoints.
- order / inventory behavior changes.
- Supabase schema changes.
- `render.yaml` changes.
- production app store release.
- iOS signing / deployment.
- Android CI / build unless the SDK becomes available.

## 7. Architecture Boundaries

- **Flutter remains a thin client.**
- **Backend remains the authority** for RBAC, tenancy, eligibility,
  assignments, compliance gates, order status, inventory, and audit.
- **Mobile must not duplicate backend business rules.**
- **Existing `Navigator.push` flow should remain** unless absolutely necessary.
- **No router package migration** in Dr.1.4.
- **No dependency upgrade** unless directly required by Dr.1.4 work.

## 8. Runtime Auth Contract

- **Email/password Supabase sign-in** is the authentication method for Dr.1.4.
- **Magic link / OTP are deferred** (not in Dr.1.4).
- **Session restore** reads the current Supabase session at startup.
- **Logout** clears the session and returns the user to the login screen.
- **No service-role keys** are used anywhere in the mobile app.
- **No token logging** — access/refresh tokens are never written to logs.
- **No raw errors rendered** — Supabase/backend errors are mapped to safe
  user-facing messages.

## 9. Runtime Config Contract

Required **public** runtime variables:

- `NUBERUSH_API_BASE_URL`
- `NUBERUSH_SUPABASE_URL`
- `NUBERUSH_SUPABASE_ANON_KEY`

Rules:

- **Missing config shows a safe `ConfigRequired` state** (no usable app behind it).
- **No crash** when config is missing or invalid.
- **No localhost fallback.**
- **No network call when config is missing.**
- **No secrets committed** to the repository.
- **Values must be passed via `--dart-define` or `--dart-define-from-file`.**

## 10. App Shell / Auth Gate Contract

Target shell states:

- **`ConfigRequiredScreen`** — shown when public config is missing/invalid.
- **`AuthLoadingScreen`** — shown while resolving/restoring the session.
- **`LoginScreen`** — shown when unauthenticated and config is valid.
- **`AuthenticatedDriverShell`** — shown when authenticated.
- **Driver Home and all assignment/action screens live behind auth**, inside
  the authenticated shell.

## 11. ApiClient Token Wiring Contract

- **`ApiClient` must receive `accessTokenProviderFor(authSession)`** as its
  access-token provider.
- **Driver endpoints must include `Authorization: Bearer <access token>`.**
- **Existing driver repository endpoint centralization must remain** — token
  wiring does not fan endpoint definitions back out.
- **No backend changes required** by default for token wiring.

## 12. 401 / 403 Handling Contract

- **401 means auth expired / invalid:**
  - show a safe message,
  - clear local auth/session state,
  - return to `LoginScreen`,
  - **no automatic mutation retry.**
- **403 means authenticated but not allowed:**
  - **stay authenticated,**
  - show a safe no-access message,
  - **no logout.**

## 13. NubeRush Visual Identity Contract

- **Dr.1.4 must replace the teal Material generic theme.**
- Use the **NubeRush dark navy / near-black background.**
- Use the **NubeRush orange primary / accent.**
- Use **premium cards / buttons / radius.**
- Use **brand / logo treatment.**
- **Align with the web app and the future customer app** — one ecosystem.
- The **new `LoginScreen` must be NubeRush-branded.**
- **The Driver App must not look like a separate, generic product.**

## 14. Security / Privacy Contract

- **No service-role key** in the mobile app.
- **No real secrets** committed.
- **No token logging.**
- **No `SharedPreferences` for tokens.**
- **Use the secure storage / Keychain / Keystore boundary** (`SecureSessionStore`).
- **No raw Supabase/backend errors rendered** to users.
- **No customer PII added** to the mobile app.
- **No `/orders/` mobile usage.**
- **No stored password** (only session tokens via secure storage).

## 15. Testing Contract

Requirements:

- **Existing tests remain passing** (the current 191-test baseline).
- **New unit/widget tests for:**
  - config missing,
  - valid config,
  - auth state transitions,
  - login success / failure,
  - logout,
  - `AuthGate`,
  - token injection,
  - 401 handling,
  - 403 handling,
  - theme / brand rendering.
- **Validation commands:**
  - `cd mobile && flutter pub get`
  - `cd mobile && flutter analyze`
  - `cd mobile && flutter test`
  - `cd mobile && flutter build ios --debug --no-codesign`
- **Android may be skipped if the SDK is absent.**

## 16. Real-device Smoke Contract

README / docs must include the following real-device smoke steps:

- **`dart-define` run command** (how to launch with public config).
- **Config-missing smoke** (app shows `ConfigRequired` safely).
- **Invalid-login smoke** (bad credentials show safe failure).
- **Valid-login smoke** (good credentials reach authenticated shell).
- **Session-restore smoke** (relaunch stays logged in).
- **Driver Home smoke.**
- **Profile / eligibility smoke.**
- **Assignment list / detail smoke.**
- **Logout smoke** (returns to login, session cleared).
- **POST actions only if a safe test assignment exists** (no destructive
  real-data mutations during smoke).

## 17. Allowed Files

Allowed across Dr.1.4 (by subphase):

- `docs/dr.1.4-live-auth-login-bootstrap-contract.md`
- later Dr.1.4 docs under `docs/`
- later Dr.1.4 mobile files under `mobile/`
- `mobile/README.md` (later)
- `mobile/.env.example` (later, **placeholders only**)

**For Dr.1.4.A specifically:**

- **only** `docs/dr.1.4-live-auth-login-bootstrap-contract.md`

## 18. Forbidden Changes

**For Dr.1.4.A**, do not change:

- `mobile/`
- `backend/`
- `web/`
- `supabase/`
- `render.yaml`
- `.github/`
- dependency lockfiles
- generated build files
- existing Dr.1.3 docs (unless explicitly approved)

## 19. Subphase Plan

- **Dr.1.4.A** — Contract Lock / Live Auth + Visual Identity Scope.
- **Dr.1.4.B** — NubeRush Mobile Theme Foundation.
- **Dr.1.4.C** — Supabase Runtime Bootstrap + Config State.
- **Dr.1.4.D** — Login / Logout UI.
- **Dr.1.4.E** — Session Restore + Authenticated App Shell.
- **Dr.1.4.F** — Live ApiClient Token Wiring + 401 Policy.
- **Dr.1.4.G** — Real-device Smoke Readiness Docs.
- **Dr.1.4.H** — Final Validation / Phase Commit / Push / CI Watch.

## 20. Pass / Fail Criteria

**PASS (for Dr.1.4.A) if:**

- the contract doc exists,
- all required sections exist,
- the change is docs-only,
- no runtime changes were made,
- no forbidden files were changed,
- no commit/push happened,
- Dr.1.4 scope / non-scope are clear.

**FAIL if:**

- any runtime code changed,
- backend / web / supabase / `render.yaml` changed,
- auth or theme was implemented in Dr.1.4.A,
- a commit / push happened,
- scope allows maps / push / OCR / photo / signature / backend changes,
- the visual identity contract is missing.

## 21. Commit / Push Policy

- **No commit / push after Dr.1.4.A.**
- **No commit / push after subphases B–G.**
- **One phase-level commit / push only during Dr.1.4.H**, after all validation passes.
- **Fast-forward only.**
- **No force push.**
- **No amend / rebase / squash / reset** unless explicitly approved.

## 22. Carry-forwards After Dr.1.4

Likely future work, explicitly deferred beyond Dr.1.4:

- Android SDK / build / CI.
- iOS CI / signing / deployment.
- maps / navigation / ETA.
- push notifications.
- OCR / photo / signature.
- onboarding / documents / activation.
- earnings / history / performance.
- customer app.
- store-side confirm-driver-return UI (remains store/backend side).
- app store / play store release.

## 23. Closure Definition

Dr.1.4 closes only when:

- `Supabase.initialize` runtime exists,
- public config validation works,
- the config-missing screen works safely,
- login / logout work,
- session restore works,
- `AuthGate` protects driver screens,
- `ApiClient` sends the Bearer token,
- 401 returns to login safely,
- 403 stays authenticated with a no-access message,
- the NubeRush visual identity foundation is applied,
- smoke docs exist,
- `flutter analyze` / `flutter test` pass,
- iOS debug no-codesign build passes,
- no forbidden scope creep occurred,
- final commit / push / CI is green in Dr.1.4.H.
