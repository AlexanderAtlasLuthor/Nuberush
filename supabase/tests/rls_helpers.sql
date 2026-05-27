-- =============================================================================
-- F2.22.3.F — RLS helper-function tests
-- =============================================================================
--
-- Validates the F2.22.3.E helper functions:
--   * public.current_app_user_id()        -> uuid
--   * public.current_app_user_store_id()  -> uuid
--   * public.is_admin()                   -> boolean
--
-- across five behavior cases:
--   1. unauthenticated (auth.uid() IS NULL)
--   2. unmapped auth.uid() (no public.users row)
--   3. active mapped admin (store_id is NULL by design)
--   4. active mapped non-admin store user
--   5. inactive mapped user (must behave as unmapped)
--
-- Execution context (see ../README.md and supabase/tests/README.md):
--   * Run AFTER `alembic upgrade head` and AFTER applying every file in
--     supabase/migrations/ (the baseline + helpers).
--   * Invoke with:  psql ... -v ON_ERROR_STOP=1 -f supabase/tests/rls_helpers.sql
--   * The whole test runs inside a single BEGIN/ROLLBACK: the auth.uid()
--     stub, the seeded users, and the seeded store are all reverted.
--   * NOT for production: do not point this file at a real DB.
-- =============================================================================

BEGIN;

-- ---- Test stub for auth.uid() ---------------------------------------------
--
-- The F2.22.3.E helpers reference auth.uid(). On Supabase that function
-- is provided by the platform; on bare Postgres (local / CI test DB) it
-- does not exist. We CREATE OR REPLACE it inside this transaction so the
-- test can drive the helpers via a session GUC. ROLLBACK at the end
-- restores the prior state (auth.uid() vanishes on local; on Supabase
-- the original definition is restored — Postgres DDL is transactional).
--
-- This stub lives ONLY in the test file. It is NOT part of any migration.

CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE plpgsql STABLE AS $stub$
DECLARE
  v text := current_setting('app.fake_uid', true);
BEGIN
  RETURN NULLIF(v, '')::uuid;
END;
$stub$;

-- ---- Seed fixture ----------------------------------------------------------
--
-- One store and three users so all four mapped/unmapped/active/inactive
-- and admin/non-admin combinations can be exercised. IDs are obviously
-- fake and deterministic.

INSERT INTO public.stores (id, name, code, is_active) VALUES
  ('11111111-1111-1111-1111-111111111111', 'F2.22.3.F probe store', 'F223F', true);

-- Active admin (admins are global; store_id stays NULL by design).
INSERT INTO public.users (id, full_name, email, role, is_active, auth_user_id) VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
   'F223F Admin', 'f223f-admin@test.invalid', 'admin', true,
   'a1111111-1111-1111-1111-111111111111');

-- Active manager bound to the test store.
INSERT INTO public.users (id, store_id, full_name, email, role, is_active, auth_user_id) VALUES
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
   '11111111-1111-1111-1111-111111111111',
   'F223F Manager', 'f223f-mgr@test.invalid', 'manager', true,
   'b2222222-2222-2222-2222-222222222222');

-- Inactive staff bound to the test store.
INSERT INTO public.users (id, store_id, full_name, email, role, is_active, auth_user_id) VALUES
  ('cccccccc-cccc-cccc-cccc-cccccccccccc',
   '11111111-1111-1111-1111-111111111111',
   'F223F Inactive', 'f223f-inactive@test.invalid', 'staff', false,
   'c3333333-3333-3333-3333-333333333333');

-- ---- Case 1 — unauthenticated (auth.uid() IS NULL) ------------------------
DO $case1$
DECLARE
  uid uuid;
  sid uuid;
  adm boolean;
BEGIN
  PERFORM set_config('app.fake_uid', '', false);
  SELECT public.current_app_user_id(),
         public.current_app_user_store_id(),
         public.is_admin()
    INTO uid, sid, adm;
  IF uid IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAIL [case1]: current_app_user_id = % (expected NULL)', uid;
  END IF;
  IF sid IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAIL [case1]: current_app_user_store_id = % (expected NULL)', sid;
  END IF;
  IF adm IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'TEST FAIL [case1]: is_admin = % (expected false)', adm;
  END IF;
  RAISE NOTICE 'PASS [case1/unauthenticated]: NULL / NULL / false';
END
$case1$;

-- ---- Case 2 — unmapped auth.uid() (no public.users row) -------------------
DO $case2$
DECLARE
  uid uuid;
  sid uuid;
  adm boolean;
BEGIN
  PERFORM set_config('app.fake_uid', '99999999-9999-9999-9999-999999999999', false);
  SELECT public.current_app_user_id(),
         public.current_app_user_store_id(),
         public.is_admin()
    INTO uid, sid, adm;
  IF uid IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAIL [case2]: current_app_user_id = % (expected NULL)', uid;
  END IF;
  IF sid IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAIL [case2]: current_app_user_store_id = % (expected NULL)', sid;
  END IF;
  IF adm IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'TEST FAIL [case2]: is_admin = % (expected false)', adm;
  END IF;
  RAISE NOTICE 'PASS [case2/unmapped]: NULL / NULL / false';
END
$case2$;

-- ---- Case 3 — active mapped admin (store_id is NULL by design) ------------
DO $case3$
DECLARE
  uid uuid;
  sid uuid;
  adm boolean;
  expected_uid CONSTANT uuid := 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
BEGIN
  PERFORM set_config('app.fake_uid', 'a1111111-1111-1111-1111-111111111111', false);
  SELECT public.current_app_user_id(),
         public.current_app_user_store_id(),
         public.is_admin()
    INTO uid, sid, adm;
  IF uid IS DISTINCT FROM expected_uid THEN
    RAISE EXCEPTION 'TEST FAIL [case3]: current_app_user_id = % (expected %)', uid, expected_uid;
  END IF;
  IF sid IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAIL [case3]: current_app_user_store_id = % (expected NULL — admins are global)', sid;
  END IF;
  IF adm IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'TEST FAIL [case3]: is_admin = % (expected true)', adm;
  END IF;
  RAISE NOTICE 'PASS [case3/active_admin]: % / NULL / true', uid;
END
$case3$;

-- ---- Case 4 — active mapped non-admin store user --------------------------
DO $case4$
DECLARE
  uid uuid;
  sid uuid;
  adm boolean;
  expected_uid   CONSTANT uuid := 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
  expected_store CONSTANT uuid := '11111111-1111-1111-1111-111111111111';
BEGIN
  PERFORM set_config('app.fake_uid', 'b2222222-2222-2222-2222-222222222222', false);
  SELECT public.current_app_user_id(),
         public.current_app_user_store_id(),
         public.is_admin()
    INTO uid, sid, adm;
  IF uid IS DISTINCT FROM expected_uid THEN
    RAISE EXCEPTION 'TEST FAIL [case4]: current_app_user_id = % (expected %)', uid, expected_uid;
  END IF;
  IF sid IS DISTINCT FROM expected_store THEN
    RAISE EXCEPTION 'TEST FAIL [case4]: current_app_user_store_id = % (expected %)', sid, expected_store;
  END IF;
  IF adm IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'TEST FAIL [case4]: is_admin = % (expected false)', adm;
  END IF;
  RAISE NOTICE 'PASS [case4/active_non_admin]: % / % / false', uid, sid;
END
$case4$;

-- ---- Case 5 — inactive mapped user (must behave as unmapped) --------------
DO $case5$
DECLARE
  uid uuid;
  sid uuid;
  adm boolean;
BEGIN
  PERFORM set_config('app.fake_uid', 'c3333333-3333-3333-3333-333333333333', false);
  SELECT public.current_app_user_id(),
         public.current_app_user_store_id(),
         public.is_admin()
    INTO uid, sid, adm;
  IF uid IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAIL [case5]: current_app_user_id = % (expected NULL — user is inactive)', uid;
  END IF;
  IF sid IS NOT NULL THEN
    RAISE EXCEPTION 'TEST FAIL [case5]: current_app_user_store_id = % (expected NULL — user is inactive)', sid;
  END IF;
  IF adm IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'TEST FAIL [case5]: is_admin = % (expected false — user is inactive)', adm;
  END IF;
  RAISE NOTICE 'PASS [case5/inactive_mapped]: NULL / NULL / false';
END
$case5$;

-- ---- Bonus: confirm helper metadata is still the F2.22.3.E shape ----------
DO $meta$
DECLARE
  bad_count integer;
BEGIN
  SELECT count(*) INTO bad_count
    FROM pg_proc
   WHERE pronamespace = 'public'::regnamespace
     AND proname IN ('current_app_user_id', 'current_app_user_store_id', 'is_admin')
     AND (
          prosecdef IS NOT TRUE
       OR provolatile <> 's'
       OR NOT ('search_path=public, pg_temp' = ANY(COALESCE(proconfig, ARRAY[]::text[])))
     );
  IF bad_count <> 0 THEN
    RAISE EXCEPTION 'TEST FAIL [meta]: % helper(s) missing SECURITY DEFINER / STABLE / fixed search_path', bad_count;
  END IF;
  RAISE NOTICE 'PASS [meta]: SECURITY DEFINER + STABLE + search_path=public, pg_temp on all 3 helpers';
END
$meta$;

ROLLBACK;

DO $done$
BEGIN
  RAISE NOTICE 'F2.22.3.F rls_helpers.sql — ALL CHECKS PASS';
END
$done$;
