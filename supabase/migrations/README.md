# `supabase/migrations/` — SQL migrations for Supabase platform objects

SQL files in this directory are applied **after** Alembic on every
environment. See [`../README.md`](../README.md) for the full apply
order and the Alembic / Supabase ownership split.

## Current files

| File | Subphase | What it does |
| --- | --- | --- |
| `20260526142048_rls_baseline.sql` | F2.22.3.D | Enables and FORCEs ROW LEVEL SECURITY on the 10 existing `public.*` application tables. No positive policies — the deny-all is achieved by enabling RLS with no matching policies. Depends on the `nuberush_app` bypass role being provisioned first ([`../../docs/f2.22.3-rls-bypass-role.md`](../../docs/f2.22.3-rls-bypass-role.md)). |
| `20260526144321_rls_helpers.sql` | F2.22.3.E | Creates the three `SECURITY DEFINER` RLS helper functions — `public.current_app_user_id()`, `public.current_app_user_store_id()`, `public.is_admin()` — that the future F2.22.5 SELECT policies will call. Preparatory only: no policies, no privilege changes, deny-all baseline stays in force. |
| `20260527134127_storage_buckets.sql` | F2.22.4.C | Idempotently provisions the four Supabase Storage buckets from the F2.22.4 scope lock: `product-images` (public), `store-assets` (private), `compliance-attachments` (private), `exports` (private). No `storage.objects` policies are created — public read on `product-images` relies on the bucket `public = true` flag, and `authenticated` writes stay denied by the default `storage.objects` deny-all. Only `product-images` is wired end-to-end in F2.22.4 (see [`../../docs/f2.22-contract-lock.md`](../../docs/f2.22-contract-lock.md) §8.1); the other three buckets are provisioned skeletons. |
| `20260527142744_product_images_rls.sql` | F2.22.4.E | Extends the F2.22.3.D deny-all baseline to the new `public.product_images` metadata table (created by Alembic revision `d2f9e8a7c1b6`). `ENABLE` + `FORCE` ROW LEVEL SECURITY only; no positive policies for `authenticated` or `anon`. FastAPI continues to bypass RLS via the `nuberush_app` role and remains the only writer of image metadata. Storage object policies (bucket level) live in `20260527134127_storage_buckets.sql`; this file is purely about the `public.*` metadata table. |
| `20260529115507_realtime_orders_inventory.sql` | F2.22.5.C | Adds the Supabase Realtime publication membership for `public.orders` and `public.inventory_items` (idempotent; creates `supabase_realtime` if absent and conditionally `ALTER PUBLICATION ... ADD TABLE`). Adds exactly two positive RLS policies — `orders_realtime_select_authenticated` and `inventory_items_realtime_select_authenticated` — each `FOR SELECT TO authenticated USING (public.is_admin() OR store_id = public.current_app_user_store_id())`. No `INSERT` / `UPDATE` / `DELETE` policies, no `anon` policies, no other tables. On bare local Postgres without the `authenticated` platform role the policy DO blocks `SKIP` with a `NOTICE` rather than fail. See [`../../docs/f2.22-contract-lock.md`](../../docs/f2.22-contract-lock.md) §§7, 9, 9.1 for the locked scope. |

---

## Naming convention

Files use a UTC timestamp prefix so filename order matches apply
order:

```
YYYYMMDDHHMMSS_<short_kebab_description>.sql
```

Examples (illustrative, not yet created):

```
20260601120000_rls_enable_deny_all_baseline.sql
20260601120100_rls_helper_functions.sql
```

The timestamp is the UTC moment the file was authored. Once a file
is committed its name does not change — append a new migration
instead of editing an existing one, the same discipline Alembic
enforces for `versions/`.

## What goes here

- `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` (F2.22.3.D, landed —
  see [`../tests/rls_baseline.sql`](../tests/rls_baseline.sql) for the
  baseline regression).
- `ALTER TABLE ... FORCE ROW LEVEL SECURITY` (F2.22.3.D, landed).
- `CREATE FUNCTION` — RLS helpers only: `current_app_user_id`,
  `current_app_user_store_id`, `is_admin` (F2.22.3.E, landed).
- `CREATE POLICY ...` — **deny-all is achieved by absence of any
  policy** under the F2.22.3.D baseline (no policies were created in
  F2.22.3). The first positive policies to ever land here are the
  narrow realtime `SELECT` policies on `public.orders` and
  `public.inventory_items` in F2.22.5; no `authenticated` write
  policies are ever permitted (F2.22 contract §7).
- `CREATE PUBLICATION` — the Realtime publication for `orders` and
  `inventory_items` (F2.22.5).
- Storage bucket creation and storage policies (F2.22.4).

## What does NOT go here

- `CREATE TABLE` / `ALTER TABLE ... ADD COLUMN` / index changes on
  any `public.*` application table. Those are Alembic's job — add
  a new revision under `backend/alembic/versions/` instead.
- Business-logic functions (order mutations, inventory mutations,
  compliance checks, audit-row writes). Business logic lives in
  FastAPI services, not in the database.
- Triggers that implement business behavior. The contract
  ([`../../docs/f2.22-contract-lock.md`](../../docs/f2.22-contract-lock.md)
  §15) explicitly bans pushing business logic into triggers.
- RPCs intended for direct frontend invocation. The frontend goes
  through FastAPI; `supabase-js` is used for auth, storage and
  realtime invalidation only.
- `CREATE ROLE` / `ALTER ROLE ... BYPASSRLS` and any other
  cluster-level operation. The `nuberush_app` bypass role is
  provisioned as a one-off privileged bootstrap that runs **before**
  this migration tree (step 0 in the apply order). Migration
  runners frequently lack the superuser privileges needed for role
  DDL, so embedding it here would block fresh-environment applies.
  See [`../../docs/f2.22.3-rls-bypass-role.md`](../../docs/f2.22.3-rls-bypass-role.md).

## Idempotency

Migrations should be **forward-only** (the same model Alembic
follows: append a new file rather than edit). Where possible use
`IF NOT EXISTS` / `CREATE OR REPLACE` so a re-application of the
whole tree on a fresh database is safe.

## Reviewing diffs

Any change in this directory must be reviewed against:

1. The F2.22 contract — does the new SQL belong to a locked
   subphase? Is it an in-scope object type?
2. The Alembic boundary — does it modify a `public.*` table that
   Alembic owns?
3. The hybrid boundary — does it expose any `authenticated`-role
   write path? The contract bans those outright.
