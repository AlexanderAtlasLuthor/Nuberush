# NubeRush Driver (Flutter)

The NubeRush Driver mobile app. Backend-authorized **thin client** — it renders
backend state and proposes authorized actions; it never owns compliance,
payment, or final lifecycle decisions. See
[../docs/dr.1.3-driver-app-flutter-foundation-contract.md](../docs/dr.1.3-driver-app-flutter-foundation-contract.md)
for the foundation contract.

## App identity

| Property | Value |
| --- | --- |
| Flutter project / Dart package | `nuberush_driver` |
| Display name | `NubeRush Driver` |
| Bundle / application ID | `com.nuberush.driver` |
| Org | `com.nuberush` |
| Platforms | iOS, Android only |

The web Capacitor wrapper's `com.nuberush.app` is a **different** application and
must not be reused here.

## Toolchain (pinned at Dr.1.3 diagnostic)

- **Flutter:** 3.38.5 (stable)
- **Dart:** 3.10.4 (stable)

Pin to these versions for reproducible builds until a deliberate upgrade.

## Platform notes

- **iOS-first skeleton.** iOS / macOS / Chrome toolchains are available locally.
- **Android SDK is not required to generate or analyze this skeleton**, but it
  **is required before any Android build or Android CI validation.** Android
  build validation is deferred (see the Dr.1.3 plan).

## Continuous integration (Dr.1.3.J)

The repo CI workflow (`.github/workflows/ci.yml`) includes a `mobile` job that
runs on `mobile/**` changes (and on any CI-workflow change, via the path-filter
fail-safe). It pins Flutter to the toolchain above (`3.38.5` / `stable`) and runs:

```sh
flutter pub get
flutter analyze
flutter test
```

Scope and policy:

- **Analyze + unit/widget tests only.** Tests use fakes, so no runtime
  `--dart-define` configuration (and therefore no secrets) is required in CI.
- **No platform builds in CI.** The iOS build needs a macOS runner and is
  validated locally with `flutter build ios --debug --no-codesign`; the Android
  build needs the Android SDK and is deferred until that setup is added.
- **No signing and no deployment** in this phase.

## Configuration

Runtime configuration uses **public / client-safe values only**, supplied via
compile-time `--dart-define` (see `lib/core/config/environment.dart`):

- `NUBERUSH_API_BASE_URL`
- `NUBERUSH_SUPABASE_URL`
- `NUBERUSH_SUPABASE_ANON_KEY`

**Never commit real secrets.** Forbidden in mobile config: `DATABASE_URL`,
Supabase service-role keys, Postgres credentials, JWT/private signing secrets,
or any server-only material.

## Auth & session (Dr.1.3.D)

- **Supabase Auth is the mobile session source** — authentication ONLY, never
  business data (those go through the FastAPI API client). Screens depend on the
  app-owned `AuthSession` interface, not on Supabase directly.
- **Secure token storage uses Keychain (iOS) / Keystore (Android)** via
  `flutter_secure_storage` (`SecureSessionStore`). Tokens are never stored in
  plain `SharedPreferences` and token values are never logged.
- Access tokens are read **live** from the session (no stale caching); sign-out
  clears both the Supabase session and the secure store.
- The `AccessTokenProvider` bridge feeds the API client's `Bearer` header.
- Only the public config values below are used; **no service-role key, no
  `DATABASE_URL`, no server-only secrets.** Real login UI is **not** implemented
  in Dr.1.3.D.

## Status

Dr.1.3 foundation in progress: app shell + identity (B), core API transport
(C), and auth/session + secure-storage foundation (D). No driver screens or
endpoint wrappers yet — those arrive in later Dr.1.3 subphases.
