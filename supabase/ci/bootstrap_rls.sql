-- =============================================================================
-- F2.27.1 — CI-only bootstrap for the rls-active gate
-- =============================================================================
--
-- This file is NOT a migration. It is applied ONLY by the `rls-active` job in
-- .github/workflows/ci.yml, against a disposable GitHub Actions Postgres
-- service, to prepare a vanilla Postgres instance so that:
--
--   * the Supabase RLS migration tree can be applied (the helper functions
--     reference auth.uid(), which does not exist on bare Postgres), and
--   * test_rls_bypass.py can connect as a genuine non-superuser BYPASSRLS
--     runtime role (nuberush_app) instead of the postgres superuser, so the
--     bypass strategy is actually proven rather than trivially satisfied.
--
-- DELIBERATELY NOT DONE HERE (see docs/f2.27.1-rls-active-ci.md):
--   * No `storage` schema and no storage.buckets — Supabase Storage is not
--     shimmed in F2.27.1. supabase/migrations/20260527134127_storage_buckets.sql
--     is therefore NOT applied by the rls-active job.
--
-- SAFETY: throwaway CI credentials only. Never apply to production / Supabase.
--
-- Apply with:
--   psql "$DATABASE_URL_PSQL" -v ON_ERROR_STOP=1 -f supabase/ci/bootstrap_rls.sql
-- where $DATABASE_URL_PSQL points at the CI admin/superuser (postgres).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Runtime role: nuberush_app — the FastAPI / pytest identity.
--    LOGIN + BYPASSRLS + NOSUPERUSER is the locked contract from
--    docs/f2.22.3-rls-bypass-role.md §1. Idempotent: ALTER if it exists.
-- -----------------------------------------------------------------------------
DO $bootstrap_app_role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nuberush_app') THEN
    CREATE ROLE nuberush_app
      LOGIN
      BYPASSRLS
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOREPLICATION
      PASSWORD 'nuberush_app';
  ELSE
    ALTER ROLE nuberush_app
      LOGIN
      BYPASSRLS
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOREPLICATION
      PASSWORD 'nuberush_app';
  END IF;
END
$bootstrap_app_role$;

-- -----------------------------------------------------------------------------
-- 2. RLS-subject roles: authenticated / anon. These are the deny-all subjects
--    the SQL tests switch into via SET LOCAL ROLE. They MUST NOT bypass RLS.
--    On a real Supabase project these are platform roles; here we provision
--    them so the migrations' `TO authenticated` policies and the SQL tests'
--    role probes work on bare Postgres. NOLOGIN — they are never connected to.
-- -----------------------------------------------------------------------------
DO $bootstrap_rls_subject_roles$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOBYPASSRLS NOSUPERUSER;
  ELSE
    ALTER ROLE authenticated NOLOGIN NOBYPASSRLS NOSUPERUSER;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOBYPASSRLS NOSUPERUSER;
  ELSE
    ALTER ROLE anon NOLOGIN NOBYPASSRLS NOSUPERUSER;
  END IF;
END
$bootstrap_rls_subject_roles$;

-- -----------------------------------------------------------------------------
-- 3. auth schema + CI-only auth.uid() shim.
--    The F2.22.3.E helper migration is LANGUAGE sql and references auth.uid()
--    in its body, so the function must resolve at CREATE time on bare Postgres.
--    This stub reads the same session GUC the SQL tests use (app.fake_uid), so
--    supabase/tests/rls_helpers.sql and realtime_orders_inventory.sql can
--    simulate identity exactly as documented in supabase/tests/README.md.
--    Test files CREATE OR REPLACE their own auth.uid() inside BEGIN/ROLLBACK,
--    which simply shadows this one for the duration of that transaction.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $auth_uid$
DECLARE
  v text := current_setting('app.fake_uid', true);
BEGIN
  RETURN NULLIF(v, '')::uuid;
END;
$auth_uid$;

-- -----------------------------------------------------------------------------
-- 4. Minimal grants for nuberush_app on existing public.* objects.
--    Mirrors docs/f2.22.3-rls-bypass-role.md §2. Run AFTER `alembic upgrade
--    head`, so ALL TABLES / ALL SEQUENCES already exist.
-- -----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO nuberush_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nuberush_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO nuberush_app;

-- -----------------------------------------------------------------------------
-- 5. Default privileges so any object a later migration step creates in public
--    (as the role running this DDL — the CI admin/superuser that also runs
--    Alembic) automatically extends to nuberush_app. Idempotent.
-- -----------------------------------------------------------------------------
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nuberush_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO nuberush_app;
