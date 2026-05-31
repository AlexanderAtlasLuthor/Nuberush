-- =============================================================================
-- F2.22.3.F — RLS deny-all baseline tests
-- =============================================================================
--
-- Validates the F2.22.3.D deny-all baseline, extended in F2.22.4.E to
-- the product_images metadata table, in F2.24.C1 to the two
-- store-application tables, and reconciled in F2.22.8.B with the two
-- F2.22.5.C realtime SELECT policies:
--   A. RLS is ENABLED and FORCED on each of the 13 public.* application tables.
--   B. Policy posture across the 13 tables:
--        B.1 the 11 pure deny-all tables carry ZERO policies (deny-all by
--            absence);
--        B.2 public.orders and public.inventory_items carry ONLY their
--            locked F2.22.5.C SELECT-only TO-authenticated realtime policy
--            (exactly one each, by name);
--        B.3 no write (INSERT/UPDATE/DELETE/ALL) policy and no anon/public
--            policy exists on any of the 11 tables.
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
    'order_audit_logs', 'product_compliance_audit_logs',
    -- F2.22.4.E: product image metadata is a public.* table and must
    -- carry the same deny-all baseline as every other business table.
    'product_images',
    -- F2.24.C1: merchant store-application tables share the deny-all
    -- baseline; application data flows only through FastAPI.
    'store_applications', 'store_application_audit_logs'
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
  RAISE NOTICE 'PASS [A]: RLS ENABLED+FORCED on all 13 required tables';
END
$A$;

-- ---------------------------------------------------------------------------
-- Part B — Policy posture across the 13 baseline tables.
--
-- F2.22.3.D established deny-all by ABSENCE of any policy. F2.22.5.C then
-- intentionally added exactly two narrow realtime policies — one SELECT-only
-- TO authenticated policy on each of public.orders and public.inventory_items
-- (see ../migrations/20260529115507_realtime_orders_inventory.sql). Part B
-- therefore splits the check rather than asserting a blanket zero:
--
--   B.1  Pure deny-all tables (11) must still have ZERO policies.
--   B.2  Realtime-exposed tables (orders, inventory_items) may carry ONLY
--        their locked SELECT-only TO-authenticated policy — exactly one each,
--        by the expected name.
--   B.3  Across ALL 13 tables: no write policy (INSERT/UPDATE/DELETE/ALL)
--        and no anon/public policy may exist.
--
-- The realtime policies' predicate behavior (cross-tenant isolation) is
-- covered separately by realtime_orders_inventory.sql.
-- ---------------------------------------------------------------------------

DO $B$
DECLARE
  -- The 9 tables that must remain deny-all by absence of any policy.
  deny_all_tables CONSTANT text[] := ARRAY[
    'users', 'stores', 'products', 'product_variants',
    'inventory_logs', 'order_items',
    'order_audit_logs', 'product_compliance_audit_logs',
    'product_images',
    -- F2.24.C1: merchant store-application tables (deny-all by absence).
    'store_applications', 'store_application_audit_logs'
  ];
  -- The 2 realtime-exposed tables and their single allowed policy name,
  -- index-aligned (F2.22.5.C).
  realtime_tables   CONSTANT text[] := ARRAY['orders', 'inventory_items'];
  realtime_policies CONSTANT text[] := ARRAY[
    'orders_realtime_select_authenticated',
    'inventory_items_realtime_select_authenticated'
  ];
  t               text;
  expected_policy text;
  policy_count    integer;
  pol             record;
  hit             record;
  i               integer;
BEGIN
  -- ---- B.1: pure deny-all tables must have zero policies ----
  FOREACH t IN ARRAY deny_all_tables LOOP
    SELECT count(*) INTO policy_count
      FROM pg_policies
     WHERE schemaname = 'public' AND tablename = t;
    IF policy_count <> 0 THEN
      FOR hit IN
        SELECT policyname, cmd, roles
          FROM pg_policies
         WHERE schemaname = 'public' AND tablename = t
      LOOP
        RAISE NOTICE 'unexpected policy on public.%: % (cmd=%, roles=%)',
          t, hit.policyname, hit.cmd, hit.roles;
      END LOOP;
      RAISE EXCEPTION
        'TEST FAIL [B.1]: public.% must have 0 policies (deny-all by absence), found %',
        t, policy_count;
    END IF;
  END LOOP;
  RAISE NOTICE 'PASS [B.1]: 0 policies on the 11 pure deny-all tables';

  -- ---- B.2: each realtime table carries exactly its one locked SELECT policy ----
  FOR i IN 1 .. array_length(realtime_tables, 1) LOOP
    t := realtime_tables[i];
    expected_policy := realtime_policies[i];

    SELECT count(*) INTO policy_count
      FROM pg_policies
     WHERE schemaname = 'public' AND tablename = t;
    IF policy_count <> 1 THEN
      FOR hit IN
        SELECT policyname, cmd, roles
          FROM pg_policies
         WHERE schemaname = 'public' AND tablename = t
      LOOP
        RAISE NOTICE 'observed policy on public.%: % (cmd=%, roles=%)',
          t, hit.policyname, hit.cmd, hit.roles;
      END LOOP;
      RAISE EXCEPTION
        'TEST FAIL [B.2]: public.% must carry exactly 1 policy, found %',
        t, policy_count;
    END IF;

    SELECT policyname, cmd, roles INTO pol
      FROM pg_policies
     WHERE schemaname = 'public' AND tablename = t
     LIMIT 1;

    IF pol.policyname <> expected_policy THEN
      RAISE EXCEPTION
        'TEST FAIL [B.2]: public.% policy name = "%" (expected "%")',
        t, pol.policyname, expected_policy;
    END IF;
    IF pol.cmd <> 'SELECT' THEN
      RAISE EXCEPTION
        'TEST FAIL [B.2]: public.% policy "%" cmd = % (expected SELECT)',
        t, pol.policyname, pol.cmd;
    END IF;
    IF NOT (pol.roles = ARRAY['authenticated']::name[]) THEN
      RAISE EXCEPTION
        'TEST FAIL [B.2]: public.% policy "%" roles = % (expected {authenticated})',
        t, pol.policyname, pol.roles;
    END IF;
  END LOOP;
  RAISE NOTICE 'PASS [B.2]: orders + inventory_items each carry only their locked SELECT-only TO-authenticated realtime policy';

  -- ---- B.3: no write policy + no anon/public policy anywhere in the 11 ----
  FOR hit IN
    SELECT tablename, policyname, cmd, roles
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = ANY (deny_all_tables || realtime_tables)
  LOOP
    IF hit.cmd <> 'SELECT' THEN
      RAISE EXCEPTION
        'TEST FAIL [B.3]: public.% policy "%" has cmd % (no INSERT/UPDATE/DELETE/ALL policy permitted)',
        hit.tablename, hit.policyname, hit.cmd;
    END IF;
    IF ('anon' = ANY (hit.roles)) OR ('public' = ANY (hit.roles)) THEN
      RAISE EXCEPTION
        'TEST FAIL [B.3]: public.% policy "%" targets % (no anon/public policy permitted)',
        hit.tablename, hit.policyname, hit.roles;
    END IF;
  END LOOP;
  RAISE NOTICE 'PASS [B.3]: no write policies and no anon/public policies across the 13 baseline tables';
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
    'order_audit_logs', 'product_compliance_audit_logs',
    -- F2.22.4.E: product image metadata is a public.* table and must
    -- carry the same deny-all baseline as every other business table.
    'product_images',
    -- F2.24.C1: merchant store-application tables share the deny-all
    -- baseline; application data flows only through FastAPI.
    'store_applications', 'store_application_audit_logs'
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
  RAISE NOTICE 'PASS [C.1/authenticated/SELECT]: 0 rows visible on all 13 tables despite seeded row';
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
    'order_audit_logs', 'product_compliance_audit_logs',
    -- F2.22.4.E: product image metadata is a public.* table and must
    -- carry the same deny-all baseline as every other business table.
    'product_images',
    -- F2.24.C1: merchant store-application tables share the deny-all
    -- baseline; application data flows only through FastAPI.
    'store_applications', 'store_application_audit_logs'
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
  RAISE NOTICE 'PASS [C.4/anon/SELECT]: 0 rows visible on all 13 tables';
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
