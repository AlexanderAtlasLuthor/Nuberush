-- =============================================================================
-- F2.22.3.E — RLS helper functions (preparatory only)
-- =============================================================================
--
-- This migration adds three SECURITY DEFINER helper functions that the
-- future F2.22.5 SELECT policies will call to resolve the current request
-- to a NubeRush identity:
--
--   public.current_app_user_id()        -> uuid
--   public.current_app_user_store_id()  -> uuid
--   public.is_admin()                   -> boolean
--
-- ----- Architecture (locked, see docs/f2.22-contract-lock.md §7) -----------
--
-- These helpers are PREPARATORY. They do not, on their own, expose any
-- row of any table. The deny-all RLS baseline created in
-- supabase/migrations/20260526142048_rls_baseline.sql remains in force,
-- and no positive policies are introduced here. The helpers only become
-- meaningful in F2.22.5, when the realtime-exposed SELECT policies on
-- public.orders and public.inventory_items call them.
--
-- FastAPI authorization (deps.py role gates, permissions.py tenancy
-- helpers, service-layer guards) remains the source of truth for every
-- business read and write. RLS is defense-in-depth.
--
-- ----- Identity bridge ------------------------------------------------------
--
-- Each helper maps the Supabase JWT sub (auth.uid()) to a public.users
-- row via public.users.auth_user_id (the unique index added in Alembic
-- revision b7e3a1f04c9d). The mapping requires the row to be
-- is_active = true. role / store_id / is_active are read from
-- public.users, never from JWT claims, mirroring the FastAPI rule in
-- backend/app/api/deps.py.
--
-- Return semantics in every helper:
--   auth.uid() IS NULL             -> NULL / NULL / false
--   no matching public.users row   -> NULL / NULL / false
--   matched user, is_active=false  -> NULL / NULL / false
--   matched active admin           -> users.id / NULL / true
--   matched active non-admin       -> users.id / users.store_id / false
--
-- ----- Security attributes (per F2.22.3.E spec) -----------------------------
--
--   SECURITY DEFINER  — required so the helpers can read public.users
--                       under the deny-all baseline. Definer-owned
--                       privileges bound the data the function can see;
--                       the WHERE clause bounds it to the caller's
--                       identity.
--   STABLE            — within a single statement the result for a given
--                       auth.uid() is stable; this lets the planner cache
--                       the call and inline policy invocations.
--   search_path = public, pg_temp
--                     — pinned to defeat shadow-table attacks (a
--                       definer function should never resolve names
--                       through a caller-controlled search_path).
--
-- ----- Ownership intent (informational; not enforced by this file) ----------
--
-- The helpers must NOT be owned by nuberush_app (the FastAPI runtime
-- role documented in docs/f2.22.3-rls-bypass-role.md). They should be
-- owned by a privileged DB role with the right to read public.users
-- under the deny-all baseline — in practice, the Supabase project's
-- `postgres` role, which is the same identity the migration runner
-- uses. Because that ownership is the default outcome of running this
-- migration as `postgres`, no explicit ALTER FUNCTION ... OWNER TO is
-- issued: doing so would either be redundant on Supabase or fragile
-- against environment-specific role names.
--
-- ----- Privileges -----------------------------------------------------------
--
-- This migration does not REVOKE or GRANT any EXECUTE privilege on
-- these functions. The CREATE FUNCTION default (PUBLIC EXECUTE) is
-- intentionally left in place for this subphase: no policy yet invokes
-- the helpers, and the helpers return NULL / false to any caller whose
-- auth.uid() does not map to an active public.users row. F2.22.5 will
-- revisit privileges if needed when the realtime SELECT policies that
-- consume these helpers land.
--
-- ----- Rollback notes (informational; forward-only migration tree) ----------
--
--   DROP FUNCTION IF EXISTS public.current_app_user_id();
--   DROP FUNCTION IF EXISTS public.current_app_user_store_id();
--   DROP FUNCTION IF EXISTS public.is_admin();
--
-- ----- Out of scope ---------------------------------------------------------
--
-- No CREATE POLICY (deny-all baseline stays in force; positive policies
-- arrive in F2.22.5).
-- No CREATE PUBLICATION (Realtime — F2.22.5).
-- No Storage buckets, storage policies, or storage.* objects (F2.22.4).
-- No RPC functions intended for frontend invocation; no triggers; no
-- business-logic SQL.
-- No cluster-level operations: no CREATE ROLE, no ALTER ROLE, no
-- passwords, no credentials, no host URLs. Role provisioning lives in
-- docs/f2.22.3-rls-bypass-role.md §3.
--
-- =============================================================================

CREATE OR REPLACE FUNCTION public.current_app_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT u.id
    FROM public.users AS u
   WHERE u.auth_user_id = auth.uid()
     AND u.is_active
   LIMIT 1;
$$;

COMMENT ON FUNCTION public.current_app_user_id() IS
  'Resolves the current Supabase JWT sub (auth.uid()) to the matching '
  'active public.users.id, or NULL when there is no match. '
  'SECURITY DEFINER, STABLE, fixed search_path. Used by future F2.22.5 '
  'RLS policies; FastAPI does not call this helper.';

CREATE OR REPLACE FUNCTION public.current_app_user_store_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT u.store_id
    FROM public.users AS u
   WHERE u.auth_user_id = auth.uid()
     AND u.is_active
   LIMIT 1;
$$;

COMMENT ON FUNCTION public.current_app_user_store_id() IS
  'Resolves the current Supabase JWT sub (auth.uid()) to the matching '
  'active public.users.store_id, or NULL when there is no match or the '
  'user is an admin (admins are global and store_id is NULL). '
  'SECURITY DEFINER, STABLE, fixed search_path.';

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT COALESCE(
    (
      SELECT u.role = 'admin'::public.user_role
        FROM public.users AS u
       WHERE u.auth_user_id = auth.uid()
         AND u.is_active
       LIMIT 1
    ),
    false
  );
$$;

COMMENT ON FUNCTION public.is_admin() IS
  'True iff the current Supabase JWT sub (auth.uid()) maps to an active '
  'public.users row with role = admin. Returns false for unauthenticated '
  'callers, unmapped identities, inactive users, and non-admin active '
  'users. SECURITY DEFINER, STABLE, fixed search_path.';
