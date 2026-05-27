-- =============================================================================
-- F2.22.3.F — RLS deny-all baseline tests
-- =============================================================================
--
-- Validates the F2.22.3.D deny-all baseline:
--   A. RLS is ENABLED and FORCED on each of the 10 public.* application tables.
--   B. No policies exist on those tables yet (deny-all by absence).
--   C. authenticated and anon roles cannot SELECT/INSERT/UPDATE/DELETE.
--
-- Execution context (see ../README.md and supabase/tests/README.md):
--   * Run AFTER `alembic upgrade head` and AFTER applying every file in
--     supabase/migrations/.
--   * Invoke with:  psql ... -v ON_ERROR_STOP=1 -f supabase/tests/rls_baseline.sql
--   * The probe in Part C creates transient roles, issues GRANTs, and inserts
--     one row inside a BEGIN/ROLLBACK block. ROLLBACK reverts every change.
--   * NOT for production: do not point this file at a real DB.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Part A — RLS enabled + forced on every required table.
-- ---------------------------------------------------------------------------

DO $A$
DECLARE
  expected_tables CONSTANT text[] := ARRAY[
    'users', 'stores', 'products', 'product_variants',
    'inventory_items', 'inventory_logs',
    'orders', 'order_items',
    'order_audit_logs', 'product_compliance_audit_logs'
  ];
  t text;
  r record;
BEGIN
  FOREACH t IN ARRAY expected_tables LOOP
    SELECT relrowsecurity AS enabled, relforcerowsecurity AS forced
      INTO r
      FROM pg_class
     WHERE relnamespace = 'public'::regnamespace
       AND relkind = 'r'
       AND relname = t;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TEST FAIL [A]: public.% not found (apply Alembic first?)', t;
    END IF;
    IF NOT r.enabled THEN
      RAISE EXCEPTION 'TEST FAIL [A]: public.% missing relrowsecurity=true (baseline migration not applied?)', t;
    END IF;
    IF NOT r.forced THEN
      RAISE EXCEPTION 'TEST FAIL [A]: public.% missing relforcerowsecurity=true (FORCE not applied?)', t;
    END IF;
  END LOOP;
  RAISE NOTICE 'PASS [A]: RLS ENABLED+FORCED on all 10 required tables';
END
$A$;

-- ---------------------------------------------------------------------------
-- Part B — Zero policies on the 10 tables (deny-all by absence of policy).
-- ---------------------------------------------------------------------------

DO $B$
DECLARE
  policy_count integer;
  hit record;
BEGIN
  SELECT count(*) INTO policy_count
    FROM pg_policies
   WHERE schemaname = 'public'
     AND tablename IN (
       'users', 'stores', 'products', 'product_variants',
       'inventory_items', 'inventory_logs',
       'orders', 'order_items',
       'order_audit_logs', 'product_compliance_audit_logs'
     );
  IF policy_count <> 0 THEN
    FOR hit IN
      SELECT schemaname, tablename, policyname, cmd
        FROM pg_policies
       WHERE schemaname = 'public'
         AND tablename IN (
           'users', 'stores', 'products', 'product_variants',
           'inventory_items', 'inventory_logs',
           'orders', 'order_items',
           'order_audit_logs', 'product_compliance_audit_logs'
         )
    LOOP
      RAISE NOTICE 'unexpected policy: %.%.% (%)',
        hit.schemaname, hit.tablename, hit.policyname, hit.cmd;
    END LOOP;
    RAISE EXCEPTION 'TEST FAIL [B]: expected 0 policies on the 10 tables, found %', policy_count;
  END IF;
  RAISE NOTICE 'PASS [B]: 0 policies on the 10 required tables (deny-all by absence)';
END
$B$;

-- ---------------------------------------------------------------------------
-- Part C — Deny-all direct access for anon and authenticated.
--
-- Wrapped in BEGIN/ROLLBACK so transient roles, GRANTs, and the probe
-- row in public.stores are reverted. SET LOCAL ROLE also auto-resets at
-- ROLLBACK.
-- ---------------------------------------------------------------------------

BEGIN;

-- Bring the Supabase-flavored roles into existence locally if they aren't
-- already (idempotent). On Supabase prod they already exist; CREATE ROLE
-- below short-circuits via the IF NOT EXISTS guard.
DO $setup$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT NOBYPASSRLS;
    RAISE NOTICE 'C: created transient authenticated role for test (rolled back at end)';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT NOBYPASSRLS;
    RAISE NOTICE 'C: created transient anon role for test (rolled back at end)';
  END IF;
END
$setup$;

-- Grant the broadest table privileges so the probe tests RLS specifically,
-- not the absence of GRANTs. Even with these grants, the deny-all baseline
-- must filter everything for non-bypass roles.
GRANT USAGE ON SCHEMA public TO authenticated, anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated, anon;

-- Seed one obviously-fake probe row so SELECT under the test role would
-- see it if the deny-all baseline were broken.
INSERT INTO public.stores (id, name, code, is_active)
VALUES ('11111111-1111-1111-1111-111111111111', 'F2.22.3.F probe store', 'F223F', true);

-- ---- C.1 — authenticated SELECT must yield 0 rows on every table ----------
SET LOCAL ROLE authenticated;

DO $C_auth_sel$
DECLARE
  expected_tables CONSTANT text[] := ARRAY[
    'users', 'stores', 'products', 'product_variants',
    'inventory_items', 'inventory_logs',
    'orders', 'order_items',
    'order_audit_logs', 'product_compliance_audit_logs'
  ];
  t text;
  visible_count integer;
BEGIN
  FOREACH t IN ARRAY expected_tables LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', t) INTO visible_count;
    IF visible_count <> 0 THEN
      RAISE EXCEPTION 'TEST FAIL [C.1/authenticated/SELECT]: saw % rows in public.% (deny-all broken)',
        visible_count, t;
    END IF;
  END LOOP;
  RAISE NOTICE 'PASS [C.1/authenticated/SELECT]: 0 rows visible on all 10 tables despite seeded row';
END
$C_auth_sel$;

-- ---- C.2 — authenticated INSERT must raise --------------------------------
DO $C_auth_ins$
DECLARE
  raised boolean := false;
  emsg text;
  estate text;
BEGIN
  BEGIN
    INSERT INTO public.stores (id, name, code, is_active)
    VALUES ('22222222-2222-2222-2222-222222222222', 'bad', 'BAD', true);
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS emsg = MESSAGE_TEXT, estate = RETURNED_SQLSTATE;
    raised := true;
  END;
  IF NOT raised THEN
    RAISE EXCEPTION 'TEST FAIL [C.2/authenticated/INSERT]: did NOT raise (deny-all INSERT broken)';
  END IF;
  RAISE NOTICE 'PASS [C.2/authenticated/INSERT]: blocked (SQLSTATE=%, msg=%)', estate, emsg;
END
$C_auth_ins$;

-- ---- C.3 — authenticated UPDATE / DELETE must affect 0 rows ---------------
DO $C_auth_upd_del$
DECLARE
  affected integer;
BEGIN
  EXECUTE 'UPDATE public.stores SET name = ''nope''';
  GET DIAGNOSTICS affected = ROW_COUNT;
  IF affected <> 0 THEN
    RAISE EXCEPTION 'TEST FAIL [C.3/authenticated/UPDATE]: affected % rows (expected 0)', affected;
  END IF;

  EXECUTE 'DELETE FROM public.stores';
  GET DIAGNOSTICS affected = ROW_COUNT;
  IF affected <> 0 THEN
    RAISE EXCEPTION 'TEST FAIL [C.3/authenticated/DELETE]: affected % rows (expected 0)', affected;
  END IF;

  RAISE NOTICE 'PASS [C.3/authenticated/UPDATE+DELETE]: 0 rows affected for both';
END
$C_auth_upd_del$;

-- ---- C.4 — anon SELECT must yield 0 rows on every table -------------------
RESET ROLE;
SET LOCAL ROLE anon;

DO $C_anon_sel$
DECLARE
  expected_tables CONSTANT text[] := ARRAY[
    'users', 'stores', 'products', 'product_variants',
    'inventory_items', 'inventory_logs',
    'orders', 'order_items',
    'order_audit_logs', 'product_compliance_audit_logs'
  ];
  t text;
  visible_count integer;
BEGIN
  FOREACH t IN ARRAY expected_tables LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', t) INTO visible_count;
    IF visible_count <> 0 THEN
      RAISE EXCEPTION 'TEST FAIL [C.4/anon/SELECT]: saw % rows in public.% (deny-all broken)',
        visible_count, t;
    END IF;
  END LOOP;
  RAISE NOTICE 'PASS [C.4/anon/SELECT]: 0 rows visible on all 10 tables';
END
$C_anon_sel$;

-- ---- C.5 — anon INSERT must raise -----------------------------------------
DO $C_anon_ins$
DECLARE
  raised boolean := false;
  emsg text;
  estate text;
BEGIN
  BEGIN
    INSERT INTO public.stores (id, name, code, is_active)
    VALUES ('33333333-3333-3333-3333-333333333333', 'bad', 'BAD3', true);
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS emsg = MESSAGE_TEXT, estate = RETURNED_SQLSTATE;
    raised := true;
  END;
  IF NOT raised THEN
    RAISE EXCEPTION 'TEST FAIL [C.5/anon/INSERT]: did NOT raise';
  END IF;
  RAISE NOTICE 'PASS [C.5/anon/INSERT]: blocked (SQLSTATE=%, msg=%)', estate, emsg;
END
$C_anon_ins$;

RESET ROLE;
ROLLBACK;

DO $D$
BEGIN
  RAISE NOTICE 'F2.22.3.F rls_baseline.sql — ALL CHECKS PASS';
END
$D$;
