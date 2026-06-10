-- =============================================================================
-- F2.27.9.A — accounting integrations RLS deny-all (defense-in-depth)
-- =============================================================================
--
-- Extends the F2.22.3.D RLS deny-all baseline to the four new public.* tables
-- created by Alembic revision d5f3b9c8a2e1 (F2.27.9.A):
--   * public.store_accounting_integrations
--   * public.product_variant_accounting_mappings
--   * public.accounting_sync_logs
--   * public.accounting_sync_log_items
--
-- This file ONLY toggles RLS flags on the already-created tables; the schema
-- itself stays in Alembic (see ./README.md "What does NOT go here").
--
-- ----- Architecture (locked, see docs/f2.22-contract-lock.md §7) ------------
--
-- Mirrors every other public.* application table: RLS is enabled, FORCED so
-- the table owner is also subject to policies, and NO positive policies are
-- created. With RLS on and no permissive policy, the anon and authenticated
-- roles get zero rows on SELECT and every write raises — exactly the F2.22
-- hybrid boundary.
--
-- This matters especially here: store_accounting_integrations holds ENCRYPTED
-- OAuth tokens (the most sensitive data in the system). Denying anon /
-- authenticated direct access guarantees the frontend cannot read or write
-- accounting/token-bearing rows around the API even if a Supabase anon key
-- leaks. Token material is additionally encrypted at rest (Fernet, see
-- app/core/encryption.py) and never exposed by any read schema.
--
-- FastAPI continues to connect with the dedicated nuberush_app role
-- (LOGIN + BYPASSRLS, provisioned per docs/f2.22.3-rls-bypass-role.md) and
-- remains the only reader/writer of these tables. RLS is defense-in-depth,
-- never the primary gate.
--
-- ----- Scope of this migration ---------------------------------------------
--
-- IN scope (this file does this):
--   * ALTER TABLE public.store_accounting_integrations         ENABLE + FORCE.
--   * ALTER TABLE public.product_variant_accounting_mappings   ENABLE + FORCE.
--   * ALTER TABLE public.accounting_sync_logs                  ENABLE + FORCE.
--   * ALTER TABLE public.accounting_sync_log_items             ENABLE + FORCE.
--
-- OUT of scope (deferred or banned outright):
--   * No CREATE POLICY of any kind. authenticated/anon read/write policies are
--     banned by the F2.22 contract §7 and never added here. Accounting data
--     flows only through FastAPI, never a direct table read.
--   * No CREATE TABLE / ALTER TABLE on columns (Alembic d5f3b9c8a2e1 owns the
--     schema).
--   * No CREATE PUBLICATION (accounting data is never realtime).
--   * No storage.* changes, no RPCs, no triggers, no business logic SQL.
--   * No cluster-level operations: no CREATE ROLE, no GRANT/REVOKE, no
--     passwords, no credentials, no host URLs.
--
-- ----- Rollback notes (informational; forward-only migration tree) ----------
--
--   ALTER TABLE public.store_accounting_integrations       DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.product_variant_accounting_mappings DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.accounting_sync_logs                DISABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.accounting_sync_log_items           DISABLE ROW LEVEL SECURITY;
--
-- =============================================================================

ALTER TABLE public.store_accounting_integrations         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.store_accounting_integrations         FORCE  ROW LEVEL SECURITY;

ALTER TABLE public.product_variant_accounting_mappings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_variant_accounting_mappings   FORCE  ROW LEVEL SECURITY;

ALTER TABLE public.accounting_sync_logs                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounting_sync_logs                  FORCE  ROW LEVEL SECURITY;

ALTER TABLE public.accounting_sync_log_items             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounting_sync_log_items             FORCE  ROW LEVEL SECURITY;
