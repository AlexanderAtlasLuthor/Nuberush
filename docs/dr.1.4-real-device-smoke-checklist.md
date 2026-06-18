# Dr.1.4 — Real-device Smoke Readiness Checklist

> Manual smoke-test guide for the NubeRush Driver App on the iOS simulator /
> device with **live public runtime config** and **Supabase Auth**. This is a
> Dr.1.4.G **docs-only** deliverable — it changes no runtime code.
>
> Phase contract: [dr.1.4-live-auth-login-bootstrap-contract.md](dr.1.4-live-auth-login-bootstrap-contract.md).
> App run/config reference: [../mobile/README.md](../mobile/README.md).

## 1. Dr.1.4 purpose

Dr.1.4 moves the Driver App from a technical MVP foundation to **live-auth /
bootstrap readiness**. After Dr.1.4 a real driver can install, configure, sign
in, and use the authenticated driver surfaces against the live backend. It
delivers:

- **Public runtime config validation** (3 required public vars, fail-safe).
- **`Supabase.initialize` runtime** (only with valid config).
- **Login / logout** (email + password via Supabase Auth).
- **Session restore** from the current Supabase session at launch.
- **Authenticated app shell** (AuthGate → LoginScreen vs. Driver Home).
- **Bearer token API wiring** (`Authorization: Bearer <access token>`).
- **401 recovery** (auth expired → safe return to login, no auto-retry).
- **403 authenticated no-access behavior** (stay signed in, safe message).
- **iOS simulator / device smoke readiness** (this document).

Visual identity: every Dr.1.4 screen (LoginScreen, ConfigRequired, loading,
Driver Home shell) uses the NubeRush dark/orange theme so the Driver App reads
as one ecosystem with the web app and future customer app.

## 2. Required public runtime config

The app reads three **public, client-safe** values via `--dart-define`
(or `--dart-define-from-file`), resolved in
[../mobile/lib/core/config/environment.dart](../mobile/lib/core/config/environment.dart):

| Variable | Meaning |
| --- | --- |
| `NUBERUSH_API_BASE_URL` | FastAPI backend base URL (https). |
| `NUBERUSH_SUPABASE_URL` | Supabase project URL (https). |
| `NUBERUSH_SUPABASE_ANON_KEY` | Supabase **public anon** key (client-safe by design). |

Rules:

- These are **public runtime config** values only.
- **Do not** use the Supabase **service-role** key (forbidden in mobile).
- **Do not** commit real values into the repo, docs, or examples.
- **Missing or invalid** config must show **`ConfigRequiredScreen`** — no crash.
- **No localhost fallback** is assumed for live smoke; an unset/blank base URL is
  a hard, safe config error (not a silent default).
- Values must be passed by `--dart-define` / `--dart-define-from-file`.

## 3. Example run commands

> Placeholders only — replace with your **test** project values at run time.
> Never paste real anon keys into shared docs or tickets.

iOS simulator:

```sh
cd mobile
flutter run \
  --dart-define=NUBERUSH_API_BASE_URL=https://example-api.example.com \
  --dart-define=NUBERUSH_SUPABASE_URL=https://example-project.supabase.co \
  --dart-define=NUBERUSH_SUPABASE_ANON_KEY=example-anon-key
```

Optional: keep your local values out of shell history with a git-ignored
dart-define file (see [../mobile/.env.example](../mobile/.env.example)):

```sh
flutter run --dart-define-from-file=dart_defines.local.json
```

iOS device notes:

- Select a device with `-d` (e.g. `flutter run -d <device-id> --dart-define=...`).
- **Signing / deployment is NOT part of Dr.1.4.** A device run may require a
  development team in Xcode; that setup is out of scope here.
- **Real App Store release is NOT part of Dr.1.4.**

Android:

- Android is **deferred / skipped** when the Android SDK is absent.
- A missing Android SDK is **not** a Dr.1.4 blocker. Do not require an Android
  build to pass Dr.1.4.

Config-missing run (for smoke A) — run with **no** `--dart-define`s:

```sh
cd mobile
flutter run
```

## 4. Smoke checklist

Mark each as **PASS / FAIL**. "Safe" means: no raw Supabase/backend exception,
no stack trace, no token, and no secret is shown or logged.

### A. Missing config smoke
- **Do:** run the app with **no** `--dart-define`s.
- **Expected (PASS):**
  - [ ] `ConfigRequiredScreen` appears, listing the 3 required variable names.
  - [ ] No secrets / values are printed or shown.
  - [ ] App does **not** silently fall back to localhost (no API/auth call).

### B. Invalid login smoke
- **Do:** with valid config, enter an invalid email/password and submit.
- **Expected (PASS):**
  - [ ] A safe inline error appears (e.g. "Could not sign in…").
  - [ ] Password is not logged or rendered anywhere.
  - [ ] No raw Supabase exception / status code is shown.

### C. Valid login smoke
- **Do:** enter valid Supabase Auth **driver test** credentials and submit.
- **Expected (PASS):**
  - [ ] Login succeeds.
  - [ ] App transitions to **Driver Home** (authenticated shell).
  - [ ] A **LogoutButton** appears in the Driver Home app bar.
  - [ ] No access token is displayed anywhere.

### D. Session restore smoke
- **Do:** fully close and reopen the app after a valid login.
- **Expected (PASS):**
  - [ ] A brief "Restoring your session…" loading state may appear.
  - [ ] App lands on **Driver Home** without re-entering credentials.
  - [ ] No token is displayed.

### E. Driver Home smoke
- **Expected (PASS):**
  - [ ] Driver Home loads **behind auth**.
  - [ ] Live API requests carry the `Authorization: Bearer <token>` header.
  - [ ] Loading and error states are safe (no raw bodies/tokens).

### F. Profile / eligibility smoke
- **Expected (PASS):**
  - [ ] Driver profile and eligibility surfaces load behind auth.
  - [ ] If the driver lacks access (**403**), the app **stays authenticated** and
        shows a safe no-access / normalized error state.

### G. Assignment list smoke
- **Expected (PASS):**
  - [ ] Assignment list loads behind auth.
  - [ ] Empty state is safe when no assignments exist.
  - [ ] No `/orders/` endpoint is used from mobile.

### H. Assignment detail smoke
- **Expected (PASS):**
  - [ ] Assignment detail opens via the existing `Navigator.push` flow.
  - [ ] Delivery state loads.
  - [ ] No token or raw backend body is displayed.

### I. 401 smoke (auth expired / invalid)
- **How to simulate (any one):**
  - sign in, then invalidate/expire the session (e.g. revoke the session in the
    Supabase dashboard for the test user, or wait for token expiry), then trigger
    a driver request (pull/refresh a screen); or
  - point at a backend/test stub that returns `401` for a driver endpoint.
- **Expected (PASS):**
  - [ ] App returns to **LoginScreen**.
  - [ ] The mutating request is **not** auto-retried.
  - [ ] A safe session-expired / login state is shown (no raw error/token).

### J. 403 smoke (authenticated but not allowed)
- **How to simulate (any one):**
  - sign in as an authenticated user **without** driver/store access; or
  - point at a backend/test stub that returns `403` for a driver endpoint.
- **Expected (PASS):**
  - [ ] App **remains authenticated** (stays in the shell).
  - [ ] A safe forbidden / no-access normalized error is shown.
  - [ ] User is **not** logged out.

### K. Logout smoke
- **Do:** tap the **LogoutButton**.
- **Expected (PASS):**
  - [ ] App returns to **LoginScreen**.
  - [ ] Reopening the app stays **unauthenticated** until the user logs in again.

### L. Optional POST action smoke (only with safe seeded/test data)
Run **only** against safe seeded/test assignments — never real customer/order
data. Operational + compliance actions:

- accept · decline · start · arrive-store · pickup · depart-to-customer ·
  arrive-customer · verify-age · proof · complete · fail · return-to-store

Notes:

- **Do not** run mutating POST smoke against real customer/order data.
- Use **safe seeded / test data only**.
- **Store-side confirm-driver-return is backend/store-side** and is **not** part
  of mobile Dr.1.4.

## 5. Boundary / non-scope

Dr.1.4 does **not** include:

- maps / navigation / ETA
- Apple Maps / Google Maps / Waze handoff
- push notifications
- OCR
- ID photo upload
- proof photo upload
- signature capture
- file picker
- onboarding / documents
- vehicle profile
- training
- earnings / history / performance
- customer app
- store-side confirm-driver-return UI
- backend compliance changes
- new backend endpoints
- Supabase schema changes
- `render.yaml` changes
- production App Store release
- iOS signing / deployment
- Android CI / build requirement when the SDK is absent

## 6. Troubleshooting

| Symptom | Likely cause / safe action |
| --- | --- |
| **ConfigRequiredScreen appears** | One or more `--dart-define` values missing/invalid. Re-run with all 3 public vars. |
| **Supabase initialize fails** | `NUBERUSH_SUPABASE_URL` / anon key wrong or unreachable. Verify the test project URL + public anon key (never the service-role key). |
| **Invalid credentials** | Expected safe error. Confirm the test driver account exists in Supabase Auth. |
| **401 returns to login** | Expected when the session is expired/invalid. Sign in again; no auto-retry occurs. |
| **403 stays logged in** | Expected when the authenticated user lacks driver/store access. The backend is the authority; fix access server-side. |
| **API base URL incorrect** | Driver requests fail / show safe error. Verify `NUBERUSH_API_BASE_URL` (https, reachable from the device/simulator). |
| **iOS simulator networking** | Ensure the host can reach the API/Supabase URLs; localhost is **not** assumed — use a reachable base URL. |
| **Android SDK absent** | Expected; Android build is deferred. Use iOS for Dr.1.4 smoke. |
| **No assignments shown** | Safe empty state. Seed safe test assignments for the test driver if needed. |
| **Authenticated but not driver-eligible** | Eligibility surface shows "cannot go online" reasons; resolve eligibility server-side (backend authority). |

## 7. Security / privacy

- **Never commit real anon key values** into docs or examples — placeholders only.
- **Never use the service-role key** in the mobile app.
- **Never log access tokens** (no `print`/`debugPrint` of tokens).
- **Never show tokens in the UI.**
- **Never paste real customer / order data** into bug reports or tickets.
- Use **test accounts** and **seeded / test assignments** for all smoke runs.
