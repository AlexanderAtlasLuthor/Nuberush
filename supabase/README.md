# `supabase/` — Supabase platform-object scaffold

This directory owns **Supabase-specific platform objects** for the
NubeRush database: RLS policies, RLS helper functions, the Realtime
publication, and Storage buckets/policies (when those phases land).

This directory does **not** own application schema. Tables, columns,
indexes, constraints, enums and every other `public.*` schema object
remain owned by Alembic in [`backend/alembic/`](../backend/alembic/).

This split is locked by the F2.22 contract — see
[`docs/f2.22-contract-lock.md`](../docs/f2.22-contract-lock.md) §6
("Database Architecture") and §7 ("RLS Architecture").

---

## What lives where

| Object | Owner | Location |
|---|---|---|
| `public.*` tables, columns, indexes, constraints, enums | Alembic | `backend/alembic/versions/` |
| RLS enable / force flags | Supabase SQL | `supabase/migrations/` |
| RLS policies (`CREATE POLICY ...`) | Supabase SQL | `supabase/migrations/` |
| RLS helper functions (`current_app_user_id`, `is_admin`, etc.) | Supabase SQL | `supabase/migrations/` |
| Realtime publication (F2.22.5) | Supabase SQL | `supabase/migrations/` |
| Storage buckets and storage policies (F2.22.4) | Supabase SQL | `supabase/migrations/` |
| RLS / pgTAP SQL tests | Supabase SQL | `supabase/tests/` |

## What this scaffold is NOT

- It is **not** a place to put business logic. No `CREATE FUNCTION` for
  order, inventory or compliance mutation; those stay in FastAPI
  services. The only functions allowed here are the RLS helpers
  enumerated in the contract (`current_app_user_id`,
  `current_app_user_store_id`, `is_admin`).
- It is **not** a second schema authority. Any new `public.*` table,
  column or constraint goes through Alembic. The boundary-enforcement
  check in §16 of the contract greps for `CREATE TABLE` here and
  expects zero hits.
- It is **not** a replacement for Alembic. Apply order is always:
  Alembic first, then Supabase migrations.
- It is **not** a write path for the frontend. The frontend never
  reads or writes `public.*` business tables directly via
  `supabase-js` (no `.from(...)`, no `.rpc(...)` against business
  schema). Every business read/write goes through FastAPI's
  `apiRequest()`. F2.22 contract §10 enumerates the boundary; the
  boundary-enforcement check in §16 greps for `.from(` and `.rpc(`
  inside `web/src/features` and expects zero business-table hits.

---

## Migration application order

The two migration trees apply in this fixed order on every
environment (local, CI, staging, production):

0. **One-off privileged bootstrap** — provision the `nuberush_app`
   bypass role on each environment **before** any RLS-enabling
   migration lands. This is a cluster-level operation (`CREATE ROLE
   ... BYPASSRLS`), not a versioned migration, so it lives outside
   `supabase/migrations/`. See
   [`../docs/f2.22.3-rls-bypass-role.md`](../docs/f2.22.3-rls-bypass-role.md)
   for the SQL template and execution paths. Step 0 only needs to
   run once per environment; subsequent deploys skip it.
1. **Alembic** (`python -m alembic upgrade head` from `backend/`) —
   creates / updates every `public.*` application object.
2. **Supabase SQL migrations** (`supabase/migrations/*.sql`, applied
   in filename order) — enables RLS and creates the helper functions
   today; later adds the Realtime publication and Storage objects.
3. **RLS SQL tests** (`supabase/tests/*.sql`) — assert deny-all
   baseline, helper-function correctness, and the absence of any
   `authenticated` write policy.
4. **FastAPI bypass regression** (`python -m pytest tests/test_rls_bypass.py -q`
   from `backend/`) — environment-aware pytest that confirms the
   FastAPI runtime role bypasses RLS in any environment where the
   baseline is active. See
   [`../docs/f2.22.3-rls-bypass-role.md`](../docs/f2.22.3-rls-bypass-role.md)
   §8 for skip / pass / fail semantics.
5. **Backend pytest** (`python -m pytest` from `backend/`) — the
   existing 1760-test suite (1757 pre-F2.22.3.G + 3 from
   `test_rls_bypass.py`), run against the database with both
   migration trees applied. Must stay green.
6. **Frontend smoke** — only when frontend files were touched in the
   subphase. Out of scope until F2.22.4 / F2.22.5.

If a subphase only touches Alembic, step 2 is a no-op; if it only
touches `supabase/migrations/`, step 1 still runs first.

---

## F2.22.3 implementation status

F2.22.3 is the RLS defense-in-depth phase. Through F2.22.3.H the
following is in place — current files in this directory and the
linked supporting artifacts:

| Subphase | Artifact | Effect |
| --- | --- | --- |
| F2.22.3.B | `supabase/`, `supabase/migrations/`, `supabase/tests/` scaffold + this README | Migration tree exists; ownership and apply order are locked. No SQL ran. |
| F2.22.3.C | [`../docs/f2.22.3-rls-bypass-role.md`](../docs/f2.22.3-rls-bypass-role.md) | DB bypass-role strategy locked (`nuberush_app` with `LOGIN` + `BYPASSRLS`). Role provisioning is a one-off privileged bootstrap outside this migration tree. |
| F2.22.3.D | `migrations/20260526142048_rls_baseline.sql` | `ENABLE` + `FORCE ROW LEVEL SECURITY` on the 10 `public.*` application tables. **No positive policies.** Deny-all by absence. |
| F2.22.3.E | `migrations/20260526144321_rls_helpers.sql` | Three `SECURITY DEFINER STABLE` helpers — `public.current_app_user_id()`, `public.current_app_user_store_id()`, `public.is_admin()`. Preparatory: no policy yet consumes them. |
| F2.22.3.F | `tests/rls_baseline.sql`, `tests/rls_helpers.sql` | SQL-level regression for the baseline and helpers. Transactional, no persisted state. |
| F2.22.3.G | `../backend/tests/test_rls_bypass.py` | Environment-aware pytest that proves the FastAPI runtime role still works under deny-all. |
| F2.22.3.H | Documentation hardening across these READMEs and `../docs/` | No new SQL or code; consistency pass on operator-facing docs. |

Hybrid invariants that hold at the end of F2.22.3:

- FastAPI remains the **primary** authorization layer (RBAC, tenancy,
  service-layer guards). RLS is **defense-in-depth**.
- The deny-all baseline remains **closed** — no `SELECT`, `INSERT`,
  `UPDATE`, or `DELETE` policy exists on any `public.*` table. The
  first positive policies (realtime `SELECT` on `public.orders` and
  `public.inventory_items`) are deferred to F2.22.5.
- `authenticated` write policies are **never** permitted (F2.22
  contract §7).
- The frontend stays on `apiRequest()` → FastAPI for every business
  read/write; `supabase-js` is used for auth, storage, and realtime
  invalidation signals only.

See [`../docs/f2.22-contract-lock.md`](../docs/f2.22-contract-lock.md)
§12 for the locked per-subphase scope.
