# NubeRush Driver App — Dr.1.3 Flutter Foundation Contract

Status: contract lock (Dr.1.3.A)
Scope: docs only — no mobile runtime created
Contract base SHA: `9fcfc2a4391ebf7a7e7b5b4dfd32f4a93d28682f`

## 1. Purpose

Dr.1.3 is the **Flutter Foundation / Driver App MVP** phase for the NubeRush
Driver App. It begins the first native mobile runtime for NubeRush, building
directly on the closed backend and architecture work that precedes it:

- **Dr.1.0** — Mobile Research + Driver App Product Architecture (closed). Chose
  Flutter as the default stack and defined the backend-authorized thin-client
  model, driver screens, user flows, and compliance/proof/map architecture.
- **Dr.1.1** — Driver Backend Contract / Operational Foundations (closed).
  Delivered the driver profile, eligibility, assignment lifecycle, and the
  operational delivery flow.
- **Dr.1.2** — Driver Compliance Backend Surface (closed). Delivered
  delivery-time age verification, proof, complete/fail gates, return-to-store
  custody, store return confirmation, redaction/audit hardening, and the
  optional `Idempotency-Key` ledger.

**Dr.1.3.A is a docs-only contract-lock phase.** It creates this document and
nothing else. It does **not** create a Flutter project, a `mobile/` directory,
a `pubspec.yaml`, any `.dart` files, or any mobile runtime. It does not modify
backend, web, Supabase, or CI. Its sole output is the locked foundation
contract that subsequent Dr.1.3 subphases (Dr.1.3.B onward) implement against.

## 2. Current Baseline

- **Repo state:** expected clean working tree, `HEAD == origin/main`.
- **Dr.1.2 closure / contract base commit:**
  `9fcfc2a4391ebf7a7e7b5b4dfd32f4a93d28682f`
  (`docs(driver): close Dr.1.2 compliance backend surface`).
- **Dr.1.2 final driver surface:** **5 GET / 12 POST** driver endpoints
  (enumerated in Section 7), plus one related store/admin-side orders endpoint.
- **Alembic migration head:** `d4e8b2c1f3a7`.
- **`mobile/` directory:** does not exist yet.
- **Flutter SDK:** installed locally (Flutter stable, Dart bundled).
- **Toolchains ready:** iOS, macOS, and Chrome targets are ready locally.
- **Android toolchain:** missing locally (no Android SDK). This is **not
  blocking** for the contract (Dr.1.3.A) or for an iOS-first skeleton
  (Dr.1.3.B); it must be resolved before Android build validation or any
  Android CI job (see Sections 12 and 15).
- **Existing Capacitor wrapper:** the web app carries a Capacitor wrapper using
  `appId: com.nuberush.app`. This is a web-in-webview artifact, not the Driver
  App, and constrains the Driver App's identity (see Section 4).

## 3. Roadmap Reconciliation

The actual, authoritative roadmap is:

- **Dr.1.0** = Mobile Research + Driver App Product Architecture
- **Dr.1.1** = Driver Backend Contract / Operational Foundations
- **Dr.1.2** = Driver Compliance Backend Surface
- **Dr.1.3+** = Flutter Foundation / Driver App MVP

Some older Dr.1.0 planning material (e.g. a phase-target map in the mobile stack
decision) suggested that Dr.1.2 would be the "mobile project foundation" and
Dr.1.3 the driver MVP. That earlier mapping is **historical only and no longer
authoritative.** Dr.1.2 was executed as the driver **compliance backend
surface**, and the Flutter foundation begins at Dr.1.3. This document supersedes
the older phase map for the purpose of mobile phase numbering.

## 4. Mobile App Identity

The Driver App identity is locked as follows:

- **Location:** `mobile/`
- **Display name:** `NubeRush Driver`
- **Bundle / application ID:** `com.nuberush.driver`

**Forbidden bundle/application ID:** `com.nuberush.app`

Rationale:

- `com.nuberush.app` is **already present** in the existing web Capacitor
  wrapper (`web/capacitor.config.ts`).
- The Flutter Driver App is a distinct application from the web shell and must
  have its **own separate app identity** to avoid store-identity collision,
  signing/profile conflicts, and ambiguous app provenance.

## 5. Stack Decision

The Dr.1.3 stack is locked as:

- **Flutter** — cross-platform UI framework (default per Dr.1.0 decision).
- **Dart** — application language.
- **Supabase Auth** — source of the mobile session and access/refresh tokens.
- **FastAPI backend** — the single business authority and integration boundary.
- **Secure token storage** — Keychain (iOS) / Keystore (Android) backed.
- **Thin-client mobile boundary** — the app renders backend state and proposes
  authorized actions; it never owns business or compliance authority
  (see Section 6).

## 6. Thin-Client Boundary

**The backend remains the business authority.** The Flutter app is a thin
client.

The Flutter app **may**:

- render backend-provided state
- execute backend actions the driver is authorized to perform
- attach `Authorization: Bearer <token>` to requests
- send an `Idempotency-Key` header where the backend contract supports it
- handle loading / error / success UI states
- normalize transport-level errors into a typed model for the UI

The Flutter app **must not own or duplicate**:

- RBAC (role-based access control)
- tenancy / store scoping
- driver eligibility authority
- 21+ / age verification authority
- proof authority
- the complete-delivery gate
- failed-delivery rules
- return-to-store rules
- store return confirmation
- `Order.status`
- inventory
- audit
- the idempotency ledger

All of the above are **owned and enforced by the backend.** The app surfaces
their results and proposes actions; it never computes, overrides, or finalizes
them locally.

## 7. Backend API Surface for Driver App

The Driver App MVP integrates against the following backend surface (as-built at
the Dr.1.2 closure baseline).

**Read endpoints (5 GET):**

- `GET /driver/me`
- `GET /driver/eligibility`
- `GET /driver/assignments`
- `GET /driver/assignments/{assignment_id}`
- `GET /driver/assignments/{assignment_id}/delivery-state`

**Operational actions (POST):**

- `POST /driver/assignments/{assignment_id}/accept`
- `POST /driver/assignments/{assignment_id}/decline`
- `POST /driver/assignments/{assignment_id}/start`
- `POST /driver/assignments/{assignment_id}/arrive-store`
- `POST /driver/assignments/{assignment_id}/pickup`
- `POST /driver/assignments/{assignment_id}/depart-to-customer`
- `POST /driver/assignments/{assignment_id}/arrive-customer`

**Compliance actions (POST):**

- `POST /driver/assignments/{assignment_id}/verify-age`
- `POST /driver/assignments/{assignment_id}/proof`
- `POST /driver/assignments/{assignment_id}/complete`
- `POST /driver/assignments/{assignment_id}/fail`
- `POST /driver/assignments/{assignment_id}/return-to-store`

(The operational + compliance actions together total the **12 POST** driver
endpoints of the Dr.1.2 surface.)

**Related orders endpoint (not a direct Driver App MVP endpoint):**

- `POST /orders/{order_id}/confirm-driver-return`

Clarification: `POST /orders/{order_id}/confirm-driver-return` is a
**store/admin-side** endpoint. It is the store-side counterpart to the driver's
return-to-store flow and is **not** invoked by the Driver App MVP. It is listed
here only for completeness of the return custody picture.

## 8. Initial Mobile Folder Contract

The following structure is the **target** for Dr.1.3.B. It is documented here as
a contract only and **must not be created in Dr.1.3.A.**

```
mobile/
  lib/
    app/
      app.dart
      router.dart
      providers.dart
    core/
      api/
        api_client.dart
        api_error.dart
        api_config.dart
      auth/
        auth_session.dart
        token_provider.dart
        secure_session_store.dart
      config/
        environment.dart
    features/
      driver/
        data/
        domain/
        presentation/
  test/
```

This structure is a **target for Dr.1.3.B** and **must not be created in
Dr.1.3.A.** No directories or files above are created by this contract.

## 9. API Client Contract

The future Flutter API client (Dr.1.3.B/C) must provide:

- a **single request layer** that all feature code goes through
- a **centralized base URL** resolved from environment config
- **automatic Bearer token attachment** from the session layer
- **automatic JSON `Content-Type`** when a non-multipart body is present
- **`204` / empty response → `null`**
- **`2xx` JSON → typed response**
- **FastAPI `HTTPException` error normalization** (`{ "detail": "<string>" }`)
- **FastAPI Pydantic validation error normalization**
  (`{ "detail": [{ "loc", "msg", "type" }] }`)
- **network failure → typed `ApiError` with status `0`**
- **no UI logic** inside the API client
- **no business-rule duplication** inside the API client

It must **mirror the web client's transport semantics conceptually**
(centralized request, Bearer attach, dual FastAPI error shapes, 204→null,
network→status 0, typed error) — **not copy web UI code.** The durable reuse is
the contract and transport behavior, not the presentation layer.

## 10. Auth and Session Contract

The auth/session model is locked as:

- **Supabase Auth is the source of the mobile session.**
- The **API client receives the token from the session layer** (it does not
  read auth state directly from screens).
- **Screens never manually attach tokens** — token attachment is a transport
  concern handled centrally.
- **iOS token storage must use the Keychain.**
- **Android token storage must use the Keystore.**
- **No sensitive tokens in plain `SharedPreferences`** (or any unencrypted
  store).
- **No access-token or refresh-token logging** anywhere in the app.
- **Logout must clear local secure session state**, after which the client
  sends no Bearer header.

## 11. Environment / Config Contract

**Allowed mobile public config** (client-safe only):

- `NUBERUSH_API_BASE_URL`
- `NUBERUSH_SUPABASE_URL`
- `NUBERUSH_SUPABASE_ANON_KEY`

**Forbidden in mobile config / app bundle:**

- `DATABASE_URL`
- Supabase service-role key
- Postgres credentials
- private keys
- JWT signing secrets
- backend-only JWKS / private material
- any server-only secret

**Only public / client-safe values may exist in the app bundle config.** Any
secret that grants server-side authority is forbidden from the mobile app, the
same rule the web frontend enforces.

## 12. CI Strategy

- **Dr.1.3.A does not modify CI.** No `.github/` changes occur in this phase.
- **Dr.1.3.B may add path filters** so that mobile-only commits do not
  unnecessarily trigger the existing `frontend`, `backend-unit`, and
  `rls-active` jobs.
- **A dedicated Flutter `analyze` / `test` CI job should be deferred** until a
  meaningful Flutter skeleton and API-client base exist, so the job is
  meaningful rather than red-on-empty.
- **The missing Android toolchain is not blocking** for docs (Dr.1.3.A) or for
  an iOS-first skeleton (Dr.1.3.B), but it **must be resolved before Android
  build validation or any Android CI job.**

## 13. Scope

Allowed in Dr.1.3.A:

- create `docs/dr.1.3-driver-app-flutter-foundation-contract.md`

That is the only change permitted in this phase.

## 14. Non-Scope

Explicitly **not** part of Dr.1.3.A:

- no Flutter project creation
- no `mobile/` directory
- no Dart files
- no backend runtime changes
- no backend migration changes
- no backend schema / service / route changes
- no web runtime changes
- no Supabase migration changes
- no CI changes
- no store / customer UI
- no proof uploads
- no ID OCR
- no live navigation
- no payments / earnings / payouts

## 15. Risks and Carry-Forwards

- **Android SDK / toolchain missing** — must be installed before Android build
  validation or an Android CI job.
- **Flutter SDK local path / version** — the local SDK path and exact version
  should be pinned and documented (in Dr.1.3.B) so builds are reproducible.
- **CI currently lacks path filters** — every commit runs all three jobs; path
  filters are a Dr.1.3.B concern.
- **Flutter CI job deferred** — a dedicated analyze/test job lands once a
  meaningful skeleton/API-client base exists.
- **Bundle-ID collision avoided** — `com.nuberush.app` (web Capacitor wrapper)
  is forbidden for the Driver App; `com.nuberush.driver` is locked instead.
- **Older phase-map drift reconciled** — the historical Dr.1.0 phase map is
  superseded by Section 3 of this document.
- **Secure token storage must be implemented before real auth flows** —
  Keychain/Keystore-backed storage is a prerequisite for any live session.
- **No secrets in mobile config** — only public/client-safe values may ship in
  the app bundle (Section 11).

## 16. Definition of Done

Dr.1.3.A is **PASS** when all of the following hold:

- `docs/dr.1.3-driver-app-flutter-foundation-contract.md` exists
- only this docs file changed
- the document reconciles the Dr.1.0 / Dr.1.1 / Dr.1.2 / Dr.1.3 roadmap
- the document locks `mobile/` as the future app location
- the document locks `NubeRush Driver` as the display name
- the document locks `com.nuberush.driver` as the bundle / application ID
- the document forbids `com.nuberush.app` for the Driver App
- the document locks the thin-client mobile boundary
- the document lists the backend API surface
- the document defines the API client contract
- the document defines auth / session / secure storage rules
- the document defines environment config rules
- the document defines the CI strategy
- the document defines scope / non-scope
- no `mobile/` directory was created
- no runtime files were changed
