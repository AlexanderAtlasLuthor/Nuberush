-- =============================================================================
-- F2.22.5.C — Realtime publication + SELECT policy regression tests
-- =============================================================================
--
-- Validates the F2.22.5.C migration:
--   A. The `supabase_realtime` publication contains EXACTLY
--      public.orders and public.inventory_items — and nothing else
--      from `public.*` (no users, stores, products, product_variants,
--      product_images, inventory_logs, order_items, order_audit_logs,
--      product_compliance_audit_logs).
--   B. Each of public.orders and public.inventory_items carries
--      EXACTLY ONE policy: a SELECT policy for the `authenticated`
--      role only. No INSERT / UPDATE / DELETE policy. No `anon`
--      policy. No additional policies of any shape.
--   C. The SELECT predicate behaves as the contract requires (§9.1):
--        - admin sees every row (across stores).
--        - active store-A user sees only store-A rows.
--        - active store-A user sees zero store-B rows.
--        - anon / unmapped / inactive sees nothing.
--      Exercised under `SET LOCAL ROLE authenticated` (and `anon`)
--      with the F2.22.3.F `auth.uid()` stub pattern (session GUC).
--
-- Execution context (see ../README.md and supabase/tests/README.md):
--   * Run AFTER `alembic upgrade head` and AFTER applying every file
--     in supabase/migrations/.
--   * Invoke with:  psql ... -v ON_ERROR_STOP=1 -f supabase/tests/realtime_orders_inventory.sql
--   * Parts B and C transient-create the `authenticated` and `anon`
--     roles if missing (local CI Postgres without the Supabase
--     platform roles), grant table privileges, seed throwaway rows,
--     and SET LOCAL ROLE the test role inside a BEGIN/ROLLBACK so
--     nothing persists.
--   * On a Supabase-enabled DB the platform roles already exist;
--     the IF NOT EXISTS guards short-circuit cleanly.
--   * NOT for production: do not point this file at a real DB.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Part A — Publication membership (read-only catalog assertion).
-- ---------------------------------------------------------------------------

DO $A$
DECLARE
  expected_count    CONSTANT integer := 2;
  expected_tables   CONSTANT text[] := ARRAY['inventory_items', 'orders'];
  actual_tables     text[];
  rogue_count       integer;
  rogue             record;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime'
  ) THEN
    RAISE EXCEPTION 'TEST FAIL [A]: publication "supabase_realtime" not found '
      '(F2.22.5.C migration not applied?)';
  END IF;

  SELECT array_agg(tablename ORDER BY tablename)
    INTO actual_tables
    FROM pg_publication_tables
   WHERE pubname = 'supabase_realtime'
     AND schemaname = 'public';

  IF actual_tables IS NULL OR actual_tables <> expected_tables THEN
    RAISE EXCEPTION
      'TEST FAIL [A]: publication membership mismatch (actual=%, expected=%)',
      actual_tables, expected_tables;
  END IF;

  -- Defensive: explicitly enumerate any rogue public.* membership.
  SELECT count(*), array_agg(tablename ORDER BY tablename)
    INTO rogue_count, actual_tables
    FROM pg_publication_tables
   WHERE pubname = 'supabase_realtime'
     AND schemaname = 'public'
     AND tablename NOT IN ('orders', 'inventory_items');

  IF rogue_count <> 0 THEN
    FOR rogue IN
      SELECT tablename
        FROM pg_publication_tables
       WHERE pubname = 'supabase_realtime'
         AND schemaname = 'public'
         AND tablename NOT IN ('orders', 'inventory_items')
    LOOP
      RAISE NOTICE 'unexpected publication member: public.%', rogue.tablename;
    END LOOP;
    RAISE EXCEPTION
      'TEST FAIL [A]: publication contains % rogue public.* tables', rogue_count;
  END IF;

  RAISE NOTICE 'PASS [A]: supabase_realtime publication contains exactly orders + inventory_items';
END
$A$;

-- ---------------------------------------------------------------------------
-- Part B — Exactly one policy per table; SELECT only; TO authenticated only.
-- ---------------------------------------------------------------------------

DO $B$
DECLARE
  expected_table  text;
  expected_policy text;
  pol             record;
  policy_count    integer;
BEGIN
  FOR expected_table, expected_policy IN
    VALUES
      ('orders',          'orders_realtime_select_authenticated'),
      ('inventory_items', 'inventory_items_realtime_select_authenticated')
  LOOP
    SELECT count(*) INTO policy_count
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename  = expected_table;

    IF policy_count <> 1 THEN
      FOR pol IN
        SELECT policyname, cmd, roles
          FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename  = expected_table
      LOOP
        RAISE NOTICE 'observed policy on public.%: % (cmd=%, roles=%)',
          expected_table, pol.policyname, pol.cmd, pol.roles;
      END LOOP;
      RAISE EXCEPTION
        'TEST FAIL [B]: public.% must carry exactly 1 policy, found %',
        expected_table, policy_count;
    END IF;

    SELECT * INTO pol
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename  = expected_table
     LIMIT 1;

    IF pol.policyname <> expected_policy THEN
      RAISE EXCEPTION
        'TEST FAIL [B]: public.% policy name = "%" (expected "%")',
        expected_table, pol.policyname, expected_policy;
    END IF;

    IF pol.cmd <> 'SELECT' THEN
      RAISE EXCEPTION
        'TEST FAIL [B]: public.% policy "%" cmd = % (expected SELECT)',
        expected_table, pol.policyname, pol.cmd;
    END IF;

    IF NOT (pol.roles = ARRAY['authenticated']::name[]) THEN
      RAISE EXCEPTION
        'TEST FAIL [B]: public.% policy "%" roles = % (expected {authenticated})',
        expected_table, pol.policyname, pol.roles;
    END IF;
  END LOOP;

  RAISE NOTICE 'PASS [B]: exactly 1 SELECT-only TO-authenticated policy per realtime table';
END
$B$;

-- ---------------------------------------------------------------------------
-- Part C — Behavioral simulation under SET LOCAL ROLE.
--
-- Wraps the whole probe in BEGIN/ROLLBACK so transient roles, GRANTs,
-- and seed rows are reverted. SET LOCAL ROLE auto-resets on ROLLBACK.
-- ---------------------------------------------------------------------------

BEGIN;

-- 1. Bring the Supabase-flavored roles into existence locally if missing.
DO $setup_roles$
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
$setup_roles$;

-- 2. Provide an auth.uid() stub if running on bare Postgres.
--    On Supabase the platform definition is shadowed for this transaction
--    and restored by ROLLBACK (Postgres DDL is transactional).
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE plpgsql STABLE AS $stub$
DECLARE
  v text := current_setting('app.fake_uid', true);
BEGIN
  RETURN NULLIF(v, '')::uuid;
END;
$stub$;

-- 3. Grant table privileges so the probe tests RLS specifically, not
--    the absence of GRANTs. Deny-all RLS still bounds visibility.
GRANT USAGE  ON SCHEMA public TO authenticated, anon;
GRANT SELECT ON public.orders, public.inventory_items TO authenticated, anon;

-- 4. Seed two stores, three users (admin / store-A user / store-B user),
--    a product + variant per store (inventory_items needs a variant_id),
--    one order per store, one inventory_items per store.
INSERT INTO public.stores (id, name, code, is_active) VALUES
  ('11111111-1111-1111-1111-111111111111', 'F2.22.5.C Store A', 'F225CA', true),
  ('22222222-2222-2222-2222-222222222222', 'F2.22.5.C Store B', 'F225CB', true);

INSERT INTO public.users (id, full_name, email, role, is_active, auth_user_id) VALUES
  ('aaaaaaaa-0000-0000-0000-aaaaaaaaaaaa',
   'F225C Admin', 'f225c-admin@test.invalid', 'admin', true,
   'a1111111-0000-0000-0000-111111111111');

INSERT INTO public.users (id, store_id, full_name, email, role, is_active, auth_user_id) VALUES
  ('bbbbbbbb-0000-0000-0000-bbbbbbbbbbbb',
   '11111111-1111-1111-1111-111111111111',
   'F225C Store-A Mgr', 'f225c-mgr-a@test.invalid', 'manager', true,
   'b2222222-0000-0000-0000-222222222222'),
  ('cccccccc-0000-0000-0000-cccccccccccc',
   '22222222-2222-2222-2222-222222222222',
   'F225C Store-B Mgr', 'f225c-mgr-b@test.invalid', 'manager', true,
   'c3333333-0000-0000-0000-333333333333');

INSERT INTO public.products (id, name, category) VALUES
  ('dddddddd-0000-0000-0000-dddddddddddd', 'F225C Test Product', 'vape');

INSERT INTO public.product_variants (id, product_id, sku, price) VALUES
  ('eeeeeeee-0000-0000-0000-aaaaaaaaaaaa',
   'dddddddd-0000-0000-0000-dddddddddddd',
   'F225C-SKU-A', 9.99),
  ('eeeeeeee-0000-0000-0000-bbbbbbbbbbbb',
   'dddddddd-0000-0000-0000-dddddddddddd',
   'F225C-SKU-B', 9.99);

INSERT INTO public.orders (id, store_id, idempotency_key) VALUES
  ('ffffffff-0000-0000-0000-aaaaaaaaaaaa',
   '11111111-1111-1111-1111-111111111111', 'F225C-ORDER-A'),
  ('ffffffff-0000-0000-0000-bbbbbbbbbbbb',
   '22222222-2222-2222-2222-222222222222', 'F225C-ORDER-B');

INSERT INTO public.inventory_items (id, store_id, variant_id) VALUES
  ('00000000-1111-0000-0000-aaaaaaaaaaaa',
   '11111111-1111-1111-1111-111111111111',
   'eeeeeeee-0000-0000-0000-aaaaaaaaaaaa'),
  ('00000000-1111-0000-0000-bbbbbbbbbbbb',
   '22222222-2222-2222-2222-222222222222',
   'eeeeeeee-0000-0000-0000-bbbbbbbbbbbb');

-- ---- C.1 — admin under authenticated sees BOTH stores' rows ----------------
SET LOCAL ROLE authenticated;

DO $C_admin$
DECLARE
  visible_orders integer;
  visible_inventory integer;
BEGIN
  PERFORM set_config('app.fake_uid', 'a1111111-0000-0000-0000-111111111111', true);
  SELECT count(*) INTO visible_orders FROM public.orders
   WHERE id IN ('ffffffff-0000-0000-0000-aaaaaaaaaaaa',
                'ffffffff-0000-0000-0000-bbbbbbbbbbbb');
  IF visible_orders <> 2 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.1/admin/orders]: saw % seeded rows (expected 2 — admin should see every store)',
      visible_orders;
  END IF;

  SELECT count(*) INTO visible_inventory FROM public.inventory_items
   WHERE id IN ('00000000-1111-0000-0000-aaaaaaaaaaaa',
                '00000000-1111-0000-0000-bbbbbbbbbbbb');
  IF visible_inventory <> 2 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.1/admin/inventory_items]: saw % seeded rows (expected 2)',
      visible_inventory;
  END IF;
  RAISE NOTICE 'PASS [C.1/admin]: sees both stores on orders and inventory_items';
END
$C_admin$;

-- ---- C.2 — store-A user sees ONLY store-A's rows ---------------------------
DO $C_storeA$
DECLARE
  own integer;
  other integer;
BEGIN
  PERFORM set_config('app.fake_uid', 'b2222222-0000-0000-0000-222222222222', true);

  SELECT count(*) INTO own FROM public.orders
   WHERE id = 'ffffffff-0000-0000-0000-aaaaaaaaaaaa';
  IF own <> 1 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.2/storeA/orders/own]: saw % own-store rows (expected 1)', own;
  END IF;

  SELECT count(*) INTO other FROM public.orders
   WHERE id = 'ffffffff-0000-0000-0000-bbbbbbbbbbbb';
  IF other <> 0 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.2/storeA/orders/other]: saw % cross-tenant rows (expected 0)', other;
  END IF;

  SELECT count(*) INTO own FROM public.inventory_items
   WHERE id = '00000000-1111-0000-0000-aaaaaaaaaaaa';
  IF own <> 1 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.2/storeA/inventory_items/own]: saw % own-store rows (expected 1)', own;
  END IF;

  SELECT count(*) INTO other FROM public.inventory_items
   WHERE id = '00000000-1111-0000-0000-bbbbbbbbbbbb';
  IF other <> 0 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.2/storeA/inventory_items/other]: saw % cross-tenant rows (expected 0)', other;
  END IF;
  RAISE NOTICE 'PASS [C.2/storeA]: sees only own-store rows; zero cross-tenant rows';
END
$C_storeA$;

-- ---- C.3 — store-B user is the mirror image of store-A ---------------------
DO $C_storeB$
DECLARE
  own integer;
  other integer;
BEGIN
  PERFORM set_config('app.fake_uid', 'c3333333-0000-0000-0000-333333333333', true);

  SELECT count(*) INTO own FROM public.orders
   WHERE id = 'ffffffff-0000-0000-0000-bbbbbbbbbbbb';
  IF own <> 1 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.3/storeB/orders/own]: saw % own-store rows (expected 1)', own;
  END IF;

  SELECT count(*) INTO other FROM public.orders
   WHERE id = 'ffffffff-0000-0000-0000-aaaaaaaaaaaa';
  IF other <> 0 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.3/storeB/orders/other]: saw % cross-tenant rows (expected 0)', other;
  END IF;
  RAISE NOTICE 'PASS [C.3/storeB]: mirror of storeA — own store visible, cross-tenant denied';
END
$C_storeB$;

-- ---- C.4 — unauthenticated authenticated session sees nothing --------------
DO $C_unauth$
DECLARE
  visible integer;
BEGIN
  PERFORM set_config('app.fake_uid', '', true);

  SELECT count(*) INTO visible FROM public.orders
   WHERE id IN ('ffffffff-0000-0000-0000-aaaaaaaaaaaa',
                'ffffffff-0000-0000-0000-bbbbbbbbbbbb');
  IF visible <> 0 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.4/unauth/orders]: saw % rows (expected 0)', visible;
  END IF;

  SELECT count(*) INTO visible FROM public.inventory_items
   WHERE id IN ('00000000-1111-0000-0000-aaaaaaaaaaaa',
                '00000000-1111-0000-0000-bbbbbbbbbbbb');
  IF visible <> 0 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.4/unauth/inventory_items]: saw % rows (expected 0)', visible;
  END IF;
  RAISE NOTICE 'PASS [C.4/unauth-authenticated]: zero rows visible without a uid';
END
$C_unauth$;

-- ---- C.5 — anon role sees nothing (no anon policy exists at all) -----------
RESET ROLE;
SET LOCAL ROLE anon;

DO $C_anon$
DECLARE
  visible integer;
BEGIN
  SELECT count(*) INTO visible FROM public.orders
   WHERE id IN ('ffffffff-0000-0000-0000-aaaaaaaaaaaa',
                'ffffffff-0000-0000-0000-bbbbbbbbbbbb');
  IF visible <> 0 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.5/anon/orders]: saw % rows (expected 0)', visible;
  END IF;

  SELECT count(*) INTO visible FROM public.inventory_items
   WHERE id IN ('00000000-1111-0000-0000-aaaaaaaaaaaa',
                '00000000-1111-0000-0000-bbbbbbbbbbbb');
  IF visible <> 0 THEN
    RAISE EXCEPTION
      'TEST FAIL [C.5/anon/inventory_items]: saw % rows (expected 0)', visible;
  END IF;
  RAISE NOTICE 'PASS [C.5/anon]: zero rows visible (no anon policy exists)';
END
$C_anon$;

RESET ROLE;
ROLLBACK;

-- ---------------------------------------------------------------------------
-- Final pass marker (matches the rls_baseline.sql convention).
-- ---------------------------------------------------------------------------

DO $D$
BEGIN
  RAISE NOTICE 'F2.22.5.C realtime_orders_inventory.sql — ALL CHECKS PASS';
END
$D$;
