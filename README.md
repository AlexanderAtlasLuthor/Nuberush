# NubeRush Backend — Session 2 (Auth, RBAC & Tenancy)

## Overview

Session 2 establishes the **security, authentication, authorization, and multi-tenant foundation** of the backend.

This phase transforms the system from a basic API into a **production-ready backend core** with:

- Secure authentication (JWT)
- Role-based access control (RBAC)
- Multi-store (multi-tenant) isolation
- Hardened configuration
- CORS support for frontend integration
- Full automated test coverage

---

## Architecture Summary

### 🔐 Authentication

- `/auth/register` → **disabled (public stub)**
- `/auth/login` → secure login with:
  - constant-time password verification
  - no user enumeration
- `/auth/me` → returns current authenticated user

### 🎟️ JWT

Tokens include:

- `sub` (user id)
- `exp` (expiration)
- `iat` (issued at)
- `iss` (issuer)
- `aud` (audience)

Validation guarantees:

- expired tokens rejected
- malformed tokens rejected
- missing claims rejected
- user existence verified
- inactive users blocked

---

### 🛂 Role-Based Access Control (RBAC)

Role hierarchy:

```
admin > owner > manager > staff / driver
```

Key rules:

- Only backend decides roles
- Frontend cannot assign privileges
- Creation matrix enforced:

| Role | Can Create |
|------|-----------|
| admin | owner, manager, staff, driver |
| owner | manager, staff, driver |
| manager | staff, driver |
| staff | — |
| driver | — |

RBAC is enforced via:

- role aliases (`require_*`)
- fine-grained permission matrix

---

### 🏬 Multi-Tenant (Store Isolation)

Strict store-level isolation:

- users belong to a single store (except admin)
- cross-store access is **blocked**
- store existence is **not leaked** (anti-enumeration)

Key helpers:

- `require_store_member`
- `resolve_store_scope`

Behavior:

- cross-store → `403`
- unknown store → indistinguishable from forbidden
- inactive store → rejected

---

### 🌐 CORS

CORS is fully configured:

- controlled via `BACKEND_CORS_ORIGINS`
- no hardcoded origins
- wildcard (`*`) **blocked in production**
- supports local frontend (`localhost:3000`)
- preflight (`OPTIONS`) fully handled

---

### ⚙️ Configuration Security

Application will **fail at startup** if:

- `JWT_SECRET_KEY` is weak or default
- CORS is misconfigured (e.g. wildcard in production)

---

## Testing

Comprehensive automated testing:

- **165 tests passing**
- Covers:
  - authentication
  - JWT validation
  - RBAC enforcement
  - tenancy isolation
  - CORS behavior
- Includes:
  - unit tests
  - integration tests
  - real DB validation

```bash
python -m pytest -v
python -m alembic check
```

---

## Security Guarantees

The system is protected against:

- privilege escalation
- cross-tenant access
- JWT forgery (basic vectors)
- user enumeration
- CORS misconfiguration

---

## Known Non-Blocking Items

- Decision pending: `driver` role in creation matrix
- Password hashing backend (passlib → future migration)
- JWT issuer/audience stricter validation (future hardening)
- Optional CORS header exposure

---

## Development Rules (IMPORTANT)

These rules are **mandatory** for all future work:

- ❌ Frontend must NOT assign roles
- ❌ Frontend must NOT control `store_id`
- ❌ `/auth/register` must NOT be used
- ✅ All user creation goes through `/auth/users`
- ✅ RBAC is enforced ONLY in backend
- ✅ Store isolation is ALWAYS enforced

---

## Backend Flow Standard

Every endpoint must follow:

```
1. Authenticate (JWT)
2. Authorize (RBAC)
3. Validate store access (Tenancy)
4. Execute business logic
```

---

## Session Status

> **Session 2 — COMPLETED**

- Authentication ✔
- JWT ✔
- RBAC ✔
- Tenancy ✔
- CORS ✔
- Tests ✔

The backend is now **ready for product features**.

---

## Next Phase

Session 3 will introduce:

- Products
- Inventory
- Orders
- Dashboard

All built on top of this secured foundation.
