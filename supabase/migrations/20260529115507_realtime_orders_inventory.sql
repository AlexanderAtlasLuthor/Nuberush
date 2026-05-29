-- =============================================================================
-- F2.22.5.C — Realtime publication + narrow SELECT policies
-- =============================================================================
--
-- Adds the Supabase Realtime publication membership and the two positive
-- RLS SELECT policies that scope realtime visibility by store, locked in
-- docs/f2.22-contract-lock.md §§7, 9, 9.1. After this migration, the
-- frontend may subscribe to postgres_changes on public.orders and
-- public.inventory_items via supabase.channel(...); events are treated
-- purely as invalidation signals, and every UI render still comes from
-- the FastAPI refetch that follows. Business data continues to flow
-- through `apiRequest()` → FastAPI exclusively.
--
-- ----- Architecture (locked, see docs/f2.22-contract-lock.md §§7, 9, 9.1) ---
--
-- Realtime = invalidation signal only. FastAPI remains the business
-- authority. The two SELECT policies are defense-in-depth, never the
-- primary authorization gate — that stays in FastAPI's RBAC + tenancy
-- layer. RLS only bounds which rows the realtime channel surfaces:
--
--   USING (
--     public.is_admin()
--     OR store_id = public.current_app_user_store_id()
--   )
--
-- `public.is_admin()` and `public.current_app_user_store_id()` are the
-- SECURITY DEFINER, STABLE helpers provisioned in F2.22.3.E
-- (supabase/migrations/20260526144321_rls_helpers.sql). They map the
-- Supabase JWT sub (`auth.uid()`) to the active public.users row and
-- return NULL / false for unauthenticated, unmapped, or inactive
-- callers — those callers see zero realtime-visible rows.
--
-- Visibility matrix (the four cases the regression test asserts):
--
--   authenticated admin           -> sees rows across every store
--   authenticated own-store user  -> sees own store's rows only
--   authenticated other-store user-> sees zero of another store's rows
--   anon / unmapped / inactive    -> sees nothing
--
-- ----- Scope of this migration ---------------------------------------------
--
-- IN scope:
--   * Ensure the `supabase_realtime` publication exists.
--   * Add EXACTLY two tables to it: public.orders, public.inventory_items.
--   * Create ONE positive SELECT policy per table, TO authenticated, with
--     the visibility predicate above.
--
-- OUT of scope (deferred or banned outright):
--   * No other tables in the publication. Specifically excluded: users,
--     stores, products, product_variants, product_images, inventory_logs,
--     order_items, order_audit_logs, product_compliance_audit_logs.
--   * No INSERT / UPDATE / DELETE policies on these tables (or any other
--     public.* table) for the `authenticated` role. The §7 contract ban
--     is absolute; the two SELECT policies here are the only positive
--     policies F2.22 adds anywhere.
--   * No `anon` policies on any table — neither SELECT nor write.
--   * No changes to existing deny-all RLS on the other 9 public.*
--     tables (users, stores, products, product_variants, product_images,
--     inventory_logs, order_items, order_audit_logs,
--     product_compliance_audit_logs).
--   * No CREATE / ALTER ROLE, no BYPASSRLS adjustments, no GRANT / REVOKE.
--     The FastAPI runtime role (`nuberush_app`, LOGIN + BYPASSRLS) is
--     unaffected; it continues to bypass RLS as documented in
--     docs/f2.22.3-rls-bypass-role.md.
--   * No RPC functions, no Edge Functions, no triggers, no business
--     logic SQL.
--   * No custom WebSocket / broadcast / presence infrastructure — only
--     the managed Supabase Realtime publication is used.
--
-- ----- Idempotency ----------------------------------------------------------
--
-- Each DO block guards on the catalog before issuing the DDL, so a
-- re-application on an environment that already has the publication or
-- the policies is a no-op. Forward-only migration tree (the same model
-- Alembic uses).
--
-- ----- Rollback notes (informational; not auto-applied) ---------------------
--
-- On a non-production environment, as a privileged Postgres session:
--
--   DROP POLICY IF EXISTS orders_realtime_select_authenticated
--     ON public.orders;
--   DROP POLICY IF EXISTS inventory_items_realtime_select_authenticated
--     ON public.inventory_items;
--   ALTER PUBLICATION supabase_realtime DROP TABLE public.orders;
--   ALTER PUBLICATION supabase_realtime DROP TABLE public.inventory_items;
--
-- (Dropping the publication itself is typically left in place — Supabase
-- platform recreates it on demand; only the table membership matters
-- for the F2.22.5 boundary.)
--
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Part A — supabase_realtime publication membership.
--
-- On a fresh Supabase project, the platform may pre-create an empty
-- `supabase_realtime` publication. On bare local Postgres it does not.
-- The DO block handles both: create if missing, then conditionally ADD
-- each of the two locked tables. Re-applies cleanly on any environment.
-- ---------------------------------------------------------------------------

DO $publication$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime'
  ) THEN
    CREATE PUBLICATION supabase_realtime;
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM pg_publication_tables
     WHERE pubname = 'supabase_realtime'
       AND schemaname = 'public'
       AND tablename = 'orders'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.orders;
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM pg_publication_tables
     WHERE pubname = 'supabase_realtime'
       AND schemaname = 'public'
       AND tablename = 'inventory_items'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.inventory_items;
  END IF;
END
$publication$;

-- ---------------------------------------------------------------------------
-- Part B — Realtime SELECT policy on public.orders.
--
-- Authenticated callers see a row iff they are an active admin OR the
-- row's store_id matches their own store. Unauthenticated / unmapped /
-- inactive callers see nothing (helpers return NULL / false). The
-- `authenticated` role is the only target; `anon` gets no policy.
-- ---------------------------------------------------------------------------

DO $policy_orders$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    RAISE NOTICE 'SKIP [orders]: role "authenticated" not found '
      '(bare local Postgres without Supabase platform roles); '
      'this migration creates no policy here. Re-run against a '
      'Supabase-enabled environment to land the SELECT policy.';
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename  = 'orders'
       AND policyname = 'orders_realtime_select_authenticated'
  ) THEN
    CREATE POLICY orders_realtime_select_authenticated
      ON public.orders
      FOR SELECT
      TO authenticated
      USING (
        public.is_admin()
        OR store_id = public.current_app_user_store_id()
      );
  END IF;
END
$policy_orders$;

-- ---------------------------------------------------------------------------
-- Part C — Realtime SELECT policy on public.inventory_items.
--
-- Same predicate as orders. inventory_items also carries a store_id
-- column (NOT NULL FK to public.stores), so the predicate is identical.
-- ---------------------------------------------------------------------------

DO $policy_inventory$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    RAISE NOTICE 'SKIP [inventory_items]: role "authenticated" not found '
      '(bare local Postgres without Supabase platform roles); '
      'this migration creates no policy here. Re-run against a '
      'Supabase-enabled environment to land the SELECT policy.';
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename  = 'inventory_items'
       AND policyname = 'inventory_items_realtime_select_authenticated'
  ) THEN
    CREATE POLICY inventory_items_realtime_select_authenticated
      ON public.inventory_items
      FOR SELECT
      TO authenticated
      USING (
        public.is_admin()
        OR store_id = public.current_app_user_store_id()
      );
  END IF;
END
$policy_inventory$;
