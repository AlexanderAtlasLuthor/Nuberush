# `supabase/tests/` — SQL tests for RLS and platform objects

SQL-level tests that exercise Supabase platform objects directly
against the database: RLS deny-all assertions, helper-function unit
checks, "no `authenticated` write policy" guards, and (later)
realtime / storage policy tests.

These tests are designed for a **local or CI test database**. They
seed transient data, create transient roles, and replace
`auth.uid()` inside `BEGIN/ROLLBACK` blocks so nothing persists.
Do not point them at a production database.

---

## Files

| File | Subphase | Validates |
| --- | --- | --- |
| `rls_baseline.sql` | F2.22.3.F (Part B reconciled in F2.22.8.B) | The F2.22.3.D deny-all baseline. Part A asserts `relrowsecurity=true` and `relforcerowsecurity=true` on every required `public.*` table. Part B checks policy posture across the 11 tables in three parts: **B.1** the 9 pure deny-all tables carry zero `pg_policies` rows; **B.2** `public.orders` and `public.inventory_items` carry **only** their locked F2.22.5.C realtime policy — exactly one each, SELECT-only, `TO authenticated`, by the expected name (`orders_realtime_select_authenticated` / `inventory_items_realtime_select_authenticated`); **B.3** no write (`INSERT`/`UPDATE`/`DELETE`/`ALL`) policy and no `anon`/`public` policy exists on any of the 11 tables. (The realtime predicate behavior is validated by `realtime_orders_inventory.sql`.) Part C creates transient `authenticated` and `anon` roles (or reuses the Supabase ones if present), grants table privileges, seeds a probe row, switches to each role via `SET LOCAL ROLE`, and asserts deny-all: `SELECT` yields 0 rows, `INSERT` raises, `UPDATE` / `DELETE` affect 0 rows. Everything in Part C is wrapped in `BEGIN/ROLLBACK`. |
| `rls_helpers.sql` | F2.22.3.F | The F2.22.3.E helper functions. Inside `BEGIN/ROLLBACK`: stubs `auth.uid()` via a session GUC, seeds an admin / active non-admin / inactive user, and asserts the five spec cases — unauthenticated, unmapped uid, active admin, active store member, inactive mapped user. Also re-asserts that the three helpers still carry `SECURITY DEFINER` + `STABLE` + `search_path=public, pg_temp`. |
| `storage_buckets.sql` | F2.22.4.H | The F2.22.4.C bucket provisioning and the boundary that bans direct `authenticated`/`anon` writes to `storage.objects`. Part A asserts the four F2.22.4 buckets exist (`product-images`, `store-assets`, `compliance-attachments`, `exports`) with the locked public/private posture. Part B enumerates `pg_policies` on `storage.objects` and asserts no permissive write policy (`INSERT`/`UPDATE`/`DELETE`/`ALL`) is granted to `authenticated`, `anon`, or `public`. Both parts SKIP with a `NOTICE` (rather than fail) when the `storage` schema is not installed, so the script is safe to run on a bare local Postgres without the Supabase storage extension — meaningful failures only fire on Supabase-enabled environments. |
| `realtime_orders_inventory.sql` | F2.22.5.C | The F2.22.5.C realtime publication and RLS SELECT policy posture. Part A asserts the `supabase_realtime` publication contains exactly `public.orders` and `public.inventory_items` (and no other `public.*` tables). Part B asserts each table carries exactly one policy: SELECT only, `TO authenticated` only — no INSERT/UPDATE/DELETE policy, no `anon` policy, no rogue extra policies. Part C is wrapped in `BEGIN/ROLLBACK`: transiently creates `authenticated` + `anon` roles if missing, stubs `auth.uid()` via session GUC (same pattern as `rls_helpers.sql`), seeds two stores + an admin + per-store managers + a product/variant/order/inventory_items row per store, then under `SET LOCAL ROLE authenticated`/`anon` asserts the four visibility cases: admin sees both stores; store-A user sees only store-A's rows; store-A user sees zero store-B rows; unauthenticated/anon sees nothing. Prerequisite: the F2.22.3.D RLS baseline must be applied to the target environment (otherwise `relrowsecurity` is false on both tables and the policy doesn't filter). On Supabase that runs as part of the normal migration tree. |

The test files are plain SQL run via `psql`. No pgTAP dependency,
no harness scripts — invocation is one `psql -f` per file.

## Required execution order

0. **Privileged role bootstrap** — provision the `nuberush_app`
   bypass role per [`../../docs/f2.22.3-rls-bypass-role.md`](../../docs/f2.22.3-rls-bypass-role.md)
   §3 on each target environment. One-off; subsequent runs skip it.
1. **Alembic** — `python -m alembic upgrade head` from `backend/`.
   Creates every `public.*` application table the tests probe.
2. **Supabase migrations** — apply every file under
   `../migrations/` in filename order (the deny-all baseline first,
   then the helper functions).
3. **`rls_baseline.sql`** — must pass with all `NOTICE PASS [...]`
   lines. Any `TEST FAIL` aborts the script.
4. **`rls_helpers.sql`** — must pass with all `NOTICE PASS [...]`
   lines. Any `TEST FAIL` aborts the script.
5. **FastAPI bypass regression** — `python -m pytest tests/test_rls_bypass.py -q`
   from `backend/`. In an RLS-active environment it confirms the
   FastAPI runtime role bypasses RLS; broken `DATABASE_URL`
   configuration surfaces here before the full pytest suite goes
   red. Skip / fail / pass semantics in
   [`../../docs/f2.22.3-rls-bypass-role.md`](../../docs/f2.22.3-rls-bypass-role.md)
   §8.
6. **Backend pytest** — the existing 1760-test suite, run with both
   migration trees applied and the bypass regression already green.
   Must stay green.

## How to run

From the repo root, against a local or CI test database:

```bash
psql "$DATABASE_URL_TEST" -v ON_ERROR_STOP=1 -f supabase/tests/rls_baseline.sql
psql "$DATABASE_URL_TEST" -v ON_ERROR_STOP=1 -f supabase/tests/rls_helpers.sql
```

`-v ON_ERROR_STOP=1` is mandatory — without it `psql` keeps running
after a `RAISE EXCEPTION`, swallowing test failures. Each script
also ends with a final `NOTICE` confirming all checks passed, so
the exit signal is "script exited cleanly AND the final NOTICE
appeared in stderr".

## Interpreting failures

Each `DO $...$` block raises a labeled exception when an assertion
trips, so a failed run prints the failing label first, then aborts
under `ON_ERROR_STOP=1`. Failure label → likely cause:

| Label | Likely cause |
| --- | --- |
| `TEST FAIL [A]: public.<table> not found` | Alembic was not applied first. Run `python -m alembic upgrade head` from `backend/`. |
| `TEST FAIL [A]: public.<table> missing relrowsecurity=true` | `supabase/migrations/20260526142048_rls_baseline.sql` was not applied. |
| `TEST FAIL [A]: public.<table> missing relforcerowsecurity=true` | Baseline ran without the `FORCE` clause — re-apply the unmodified migration. |
| `TEST FAIL [B.1]: public.<table> must have 0 policies, found <n>` | A policy slipped onto a pure deny-all table (look at the preceding `NOTICE unexpected policy:` lines). Only `orders` and `inventory_items` are allowed a policy (the F2.22.5.C realtime SELECT policy). |
| `TEST FAIL [B.2]: public.<table> ... policy ...` | The realtime SELECT policy on `orders` / `inventory_items` is missing, renamed, not SELECT-only, or not `TO authenticated`. Re-check `supabase/migrations/20260529115507_realtime_orders_inventory.sql`. |
| `TEST FAIL [B.3]: public.<table> policy ... (no ... permitted)` | A forbidden policy exists — a write policy (`INSERT`/`UPDATE`/`DELETE`/`ALL`) or an `anon`/`public` policy on one of the 11 tables. The F2.22 contract bans both outright. |
| `TEST FAIL [C.1/...]: saw <n> rows in public.<table>` | Deny-all `SELECT` is broken for the named role. Inspect any policy added on that table. |
| `TEST FAIL [C.2/.../INSERT]: did NOT raise` | A permissive `INSERT` policy or grant exists for `authenticated`/`anon` (forbidden by the F2.22 contract). |
| `TEST FAIL [case<N>/...]: <helper> = <value> (expected ...)` | The helper migration was modified or shadowed. Re-check `supabase/migrations/20260526144321_rls_helpers.sql`. |
| `TEST FAIL [meta]: <n> helper(s) missing SECURITY DEFINER / STABLE / fixed search_path` | A helper was redefined without the required attributes. Restore the migration's definition. |

If `rls_helpers.sql` fails at the `CREATE OR REPLACE FUNCTION
auth.uid()` step on Supabase, the invoking role lacks permission to
replace the platform `auth.uid()`. That is expected on production
Supabase; run the SQL tests against a CI / local test DB instead.

## Local role prerequisites

`rls_baseline.sql` Part C and `rls_helpers.sql` need the following
roles to exist before they run as `authenticated` / `anon` /
issue helper grants. The scripts handle each case automatically:

| Role | Local bare Postgres | Supabase project |
| --- | --- | --- |
| `authenticated` | Created inside the transaction by `CREATE ROLE … NOBYPASSRLS` if missing. ROLLBACK drops it. | Pre-existing platform role. The `IF NOT EXISTS` guard short-circuits. |
| `anon` | Same as `authenticated`. | Pre-existing platform role. Same short-circuit. |
| Test invoker | Must be a superuser (or member of every target role) so `SET LOCAL ROLE` works. The local `nuberush` dev role is created as superuser in `docs/local-environment-setup.md`. | Supabase `postgres` role. |

The transient role creation is wrapped in `BEGIN/ROLLBACK` so the
local cluster is left untouched after the script finishes.

## How `auth.uid()` is handled

`rls_helpers.sql` opens with:

```sql
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE plpgsql STABLE AS $$ ... $$;
```

so the helpers being tested have an `auth.uid()` to call on
local bare Postgres. The stub reads `current_setting('app.fake_uid', true)`,
which the test sets per case via `SET LOCAL` / `set_config(...)`.

The stub is **test-only**:

- It lives only in `rls_helpers.sql`. No migration file references
  it; `supabase/migrations/README.md` calls out that platform
  function stubs do not belong in the migration tree.
- It is created inside `BEGIN`. ROLLBACK reverts the function (and
  the schema, if the schema was newly created in this transaction).
- On Supabase the original `auth.uid()` is restored by ROLLBACK
  because Postgres DDL is transactional; `CREATE OR REPLACE` only
  shadows it for the test transaction.

## What does NOT live here

- Anything that depends on Python, FastAPI, or the SQLAlchemy ORM —
  those belong in `backend/tests/`.
- Business-rule tests (order state machine, inventory invariants,
  RBAC matrices) — those stay in pytest.
- Integration tests against the production Supabase project. These
  SQL tests run against a disposable local / CI database that has
  the same migration tree applied.
