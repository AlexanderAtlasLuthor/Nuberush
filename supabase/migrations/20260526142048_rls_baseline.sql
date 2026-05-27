-- =============================================================================
-- F2.22.3.D — RLS deny-all baseline
-- =============================================================================
--
-- This migration is the first Supabase SQL migration in the project. It
-- enables ROW LEVEL SECURITY on every existing public.* application table
-- and forces it so that even table owners are subject to the policies
-- (or, in this baseline, the absence of policies — see "Design intent"
-- below). No positive policies are introduced here.
--
-- ----- Architecture (locked, see docs/f2.22-contract-lock.md §7) -----------
--
-- RLS is the *secondary* authorization layer. The primary layer is FastAPI:
-- RBAC in backend/app/api/deps.py, tenancy / permission helpers in
-- backend/app/core/permissions.py, and the service-layer guards in
-- backend/app/services/. Every business read and write is authorized there.
--
-- Alembic remains the schema authority. This file does not create, alter,
-- or drop any application table, column, index, constraint, sequence or
-- enum. It only flips RLS-related table flags. Schema changes still go
-- through backend/alembic/versions/.
--
-- ----- Design intent --------------------------------------------------------
--
-- "Deny-all" is achieved by enabling RLS with no positive policies. In
-- Postgres, a table with RLS enabled and no matching policy returns zero
-- rows for any role subject to RLS, and rejects every INSERT / UPDATE /
-- DELETE. FORCE ROW LEVEL SECURITY extends that behavior to the table's
-- owner (otherwise table owners would silently bypass policies, hiding
-- bugs from the test layer).
--
-- The intended FastAPI runtime identity is the dedicated nuberush_app
-- role provisioned per docs/f2.22.3-rls-bypass-role.md. That role carries
-- LOGIN + BYPASSRLS, so the 1757-test pytest suite and every FastAPI
-- endpoint continue to behave exactly as they do today. Without
-- BYPASSRLS on the runtime role, the next FastAPI request after this
-- migration applies will hit "permission denied" on every business
-- query.
--
-- Provisioning nuberush_app is a one-off privileged bootstrap (CREATE
-- ROLE ... BYPASSRLS) and intentionally lives outside this migration
-- tree — see supabase/migrations/README.md "What does NOT go here" and
-- docs/f2.22.3-rls-bypass-role.md §3.
--
-- ----- Scope of this migration ---------------------------------------------
--
-- IN scope (this file does this):
--   * ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY for the 10 tables
--     listed below.
--   * ALTER TABLE public.<t> FORCE  ROW LEVEL SECURITY for the same tables.
--
-- OUT of scope (deferred to a later subphase or banned outright):
--   * No CREATE POLICY of any kind. authenticated INSERT/UPDATE/DELETE
--     write policies are explicitly banned by the F2.22 contract §7 and
--     will never be added here. authenticated SELECT policies for the
--     realtime-exposed tables (orders, inventory_items) are deferred to
--     F2.22.5 so they land together with the realtime publication that
--     consumes them.
--   * No RLS helper functions (current_app_user_id, current_app_user_store_id,
--     is_admin). Those land in a later F2.22.3.x migration alongside the
--     first policy that actually consumes them.
--   * No CREATE PUBLICATION (Realtime — F2.22.5).
--   * No Storage buckets, storage policies, or storage.* objects (F2.22.4).
--   * No RPC functions, triggers, or any business-logic SQL.
--   * No cluster-level operations: no CREATE ROLE, no ALTER ROLE, no
--     GRANT/REVOKE, no passwords, no credentials, no host URLs. Role
--     provisioning is a separate privileged bootstrap (F2.22.3.C).
--
-- ----- Rollback notes (informational; not auto-applied) ---------------------
--
-- If this migration needs to be reverted on an environment, run the
-- following as a privileged Postgres session (Supabase Dashboard SQL
-- Editor or psql -U postgres). This is documented as comments rather
-- than provided as an executable rollback file because the project's
-- migration model is forward-only (the same model Alembic uses):
--
--   ALTER TABLE public.users                          DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.stores                         DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.products                       DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.product_variants               DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.inventory_items                DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.inventory_logs                 DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.orders                         DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.order_items                    DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.order_audit_logs               DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.product_compliance_audit_logs  DISABLE ROW LEVEL SECURITY;
--
-- =============================================================================

-- A. Identity / user table.
ALTER TABLE public.users                          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users                          FORCE  ROW LEVEL SECURITY;

-- C. Global / admin table.
ALTER TABLE public.stores                         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stores                         FORCE  ROW LEVEL SECURITY;

-- C. Global catalog.
ALTER TABLE public.products                       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products                       FORCE  ROW LEVEL SECURITY;

ALTER TABLE public.product_variants               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_variants               FORCE  ROW LEVEL SECURITY;

-- B. Store-scoped (realtime candidate — SELECT policy deferred to F2.22.5).
ALTER TABLE public.inventory_items                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_items                FORCE  ROW LEVEL SECURITY;

-- D. Audit, store-scoped.
ALTER TABLE public.inventory_logs                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_logs                 FORCE  ROW LEVEL SECURITY;

-- B. Store-scoped (realtime candidate — SELECT policy deferred to F2.22.5).
ALTER TABLE public.orders                         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders                         FORCE  ROW LEVEL SECURITY;

-- B. Indirect store-scoped (via parent order).
ALTER TABLE public.order_items                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items                    FORCE  ROW LEVEL SECURITY;

-- D. Audit, store-scoped.
ALTER TABLE public.order_audit_logs               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_audit_logs               FORCE  ROW LEVEL SECURITY;

-- D. Audit, global.
ALTER TABLE public.product_compliance_audit_logs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_compliance_audit_logs  FORCE  ROW LEVEL SECURITY;
