# Local environment setup

This guide explains how to make a local checkout (Windows, macOS,
Linux) behave identically to the Anthropic sandbox where the test
suite has been validated, so that **any agent — Claude Code in this
sandbox or Claude Code on your laptop — can run the full pytest +
alembic check pipeline without bumping into "alembic not found" or
"connection refused" errors.**

---

## Why the Windows checkout has been failing

When the Windows-side Claude tried to validate S5.5 it hit two
blockers, both of which are **environment** problems, not code
problems:

1. `localhost:5432/nuberush_test` did not respond → no Postgres
   instance running on port 5432.
2. `python -m alembic` and `python -m pytest` could not resolve
   the modules → the active Python interpreter is the system one,
   not the project's vendored venv at `Nuberush/.vendor_py/`.

Fix both and the local checkout runs the same suite the sandbox
runs. The actual model (Claude Opus 4.7) is identical in both
places.

---

## What the Anthropic sandbox has

Snapshot from this validated environment:

| Component | Version | Where |
|---|---|---|
| OS | Linux 6.18.5 (Ubuntu 24.04 base) | sandbox container |
| Python | 3.11.15 | `/usr/local/bin/python` |
| PostgreSQL server | 16.13 | cluster `16/main` listening on `localhost:5432` |
| psql client | 16.13 | system PATH |
| alembic | 1.16.5 | `python -m alembic` |
| pytest | 9.0.3 | `python -m pytest` |
| SQLAlchemy | 2.0.43 | from `backend/requirements.txt` |
| psycopg | 3.2.9 (binary) | from `backend/requirements.txt` |

Test database connection string used by `tests/conftest.py`:

```
postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test
```

(Override via the `DATABASE_URL_TEST` env var.)

The sandbox also has the role `nuberush` with password `nuberush`
inside the Postgres cluster, and a database called `nuberush_test`
that Alembic upgrades to `head` on session start.

---

## Replicating the sandbox locally

### 1. Postgres 16 on `localhost:5432`

The fastest way is Docker — same container behavior on Windows,
macOS and Linux, and no host-level install:

```bash
docker run -d \
  --name nuberush-pg \
  -p 5432:5432 \
  -e POSTGRES_USER=nuberush \
  -e POSTGRES_PASSWORD=nuberush \
  -e POSTGRES_DB=nuberush_test \
  postgres:16
```

Verify:

```bash
docker exec -it nuberush-pg psql -U nuberush -d nuberush_test -c "select version();"
```

You should see `PostgreSQL 16.x ...`. If you see "connection
refused" the container did not start — check `docker logs nuberush-pg`.

To start/stop the container later:

```bash
docker start nuberush-pg
docker stop nuberush-pg
```

### Native install (alternative to Docker)

**Windows:** Download the installer from
<https://www.postgresql.org/download/windows/>, install Postgres 16,
then in `psql` as the superuser:

```sql
CREATE USER nuberush WITH PASSWORD 'nuberush';
CREATE DATABASE nuberush_test OWNER nuberush;
CREATE DATABASE nuberush       OWNER nuberush;  -- for app dev
GRANT ALL PRIVILEGES ON DATABASE nuberush_test TO nuberush;
GRANT ALL PRIVILEGES ON DATABASE nuberush       TO nuberush;
```

**macOS:**

```bash
brew install postgresql@16
brew services start postgresql@16
createuser -s nuberush                # superuser for simplicity in dev
createdb nuberush_test -O nuberush
createdb nuberush       -O nuberush
psql -d postgres -c "ALTER USER nuberush WITH PASSWORD 'nuberush';"
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt install postgresql-16
sudo -u postgres psql -c "CREATE USER nuberush WITH PASSWORD 'nuberush';"
sudo -u postgres psql -c "CREATE DATABASE nuberush_test OWNER nuberush;"
sudo -u postgres psql -c "CREATE DATABASE nuberush OWNER nuberush;"
# In this sandbox specifically:
pg_ctlcluster 16 main start
```

### 2. Activate the project venv before EVERY command

The Windows checkout has a vendored venv at
`C:\Users\ceo\OneDrive\Desktop\Nuberush\.vendor_py\`. The
system-wide `python` does NOT have alembic, pytest, fastapi or
sqlalchemy installed — only the venv does. You MUST either activate
the venv or point `PYTHONPATH` to it before running tests.

**Option A — activate the venv (cleanest):**

Windows PowerShell:
```powershell
cd C:\Users\ceo\OneDrive\Desktop\Nuberush
.\.vendor_py\Scripts\Activate.ps1
```

Windows cmd.exe:
```cmd
cd C:\Users\ceo\OneDrive\Desktop\Nuberush
.\.vendor_py\Scripts\activate.bat
```

macOS/Linux:
```bash
cd /path/to/Nuberush
source .venv/bin/activate
```

After activation your prompt shows `(.vendor_py)` (or `(.venv)`).
Now `python -m alembic`, `python -m pytest` resolve correctly.

**Option B — set `PYTHONPATH` per command:**

Windows PowerShell:
```powershell
$env:PYTHONPATH = "C:\Users\ceo\OneDrive\Desktop\Nuberush\.vendor_py"
cd backend
python -m alembic check
python -m pytest -v
```

(Only persists for the current shell session.)

> **Important:** the venv must contain the dependencies pinned in
> `backend/requirements.txt`. If it does not, install them once:
>
> ```bash
> pip install -r backend/requirements.txt
> ```

### 3. Set the test DB URL

The default in `tests/conftest.py` is
`postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test`.
If you used different credentials in step 1, override:

Windows PowerShell:
```powershell
$env:DATABASE_URL_TEST = "postgresql+psycopg://yourself:yourpw@localhost:5432/yourdb"
```

macOS/Linux:
```bash
export DATABASE_URL_TEST=postgresql+psycopg://yourself:yourpw@localhost:5432/yourdb
```

### 4. Set `DATABASE_URL` for alembic

Alembic reads the runtime DB URL from the environment via
`backend/alembic/env.py` (which calls `get_db_settings`). Either:

- Copy `backend/.env.example` to `backend/.env` and edit the URL, or
- Export `DATABASE_URL` for the current shell:

  ```bash
  export DATABASE_URL=postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush
  ```

### 5. Sanity check

From `Nuberush/backend/`, with venv active and Postgres up:

```bash
python -m alembic check
# Expected: "No new upgrade operations detected."

python -m pytest -v
# Expected: 488 passed (as of main commit 17462b3)
```

If both pass, your local matches the sandbox.

---

## F2.22.1 Supabase Postgres cutover

F2.22.1 moves Postgres hosting to Supabase. It changes only the
database connection — auth, RLS, storage, realtime, and business
logic are out of scope.

- The FastAPI runtime and Alembic both read `DATABASE_URL`.
- The test suite reads `DATABASE_URL_TEST`.
- Supabase URLs must use the Supavisor **session** pooler and end
  with `?sslmode=require`.
- The Supavisor **transaction** pooler is forbidden: it breaks
  SQLAlchemy session semantics, psycopg prepared statements,
  `SELECT ... FOR UPDATE` locks, and the concurrency tests.
- `DATABASE_URL_TEST` must point at an isolated test database or a
  separate Supabase project — never production. The suite can run
  `alembic downgrade base` and drop schema objects.

See `backend/.env.example` for the exact URL shapes.

---

## F2.22.3 migration application order

Starting in F2.22.3, the project has **two** migration trees that must
apply in a fixed order on every environment (local, CI, staging,
production). The order is:

0. **One-off privileged bootstrap** — provision the `nuberush_app`
   bypass role on each target environment **before** any RLS-enabling
   migration lands. `CREATE ROLE ... BYPASSRLS` is a cluster-level
   operation and is intentionally not in the migration tree. Run the
   template in [`f2.22.3-rls-bypass-role.md`](f2.22.3-rls-bypass-role.md)
   §3 as `postgres` (Supabase Dashboard SQL Editor, `psql` against
   the project, or a local `psql -U postgres`). One-off per
   environment.
1. **Alembic** (`python -m alembic upgrade head` from `backend/`) —
   the schema authority for every `public.*` application table,
   column, index, constraint and enum.
2. **Supabase SQL migrations** — files under `supabase/migrations/`
   applied in filename order. As of F2.22.3.H, these are
   `20260526142048_rls_baseline.sql` (enable + force RLS, no policies)
   and `20260526144321_rls_helpers.sql` (three `SECURITY DEFINER`
   helper functions). F2.22.4 will add Storage objects and F2.22.5
   will add the Realtime publication and its narrow `SELECT`
   policies.
3. **Supabase SQL tests** — `supabase/tests/rls_baseline.sql` then
   `supabase/tests/rls_helpers.sql`, each invoked as
   `psql … -v ON_ERROR_STOP=1 -f <file>`. They assert deny-all
   baseline, helper-function correctness, and the absence of any
   `authenticated`-role write policy.
4. **FastAPI bypass regression** — `pytest tests/test_rls_bypass.py -q`
   from `backend/`. Environment-aware: see "Bypass regression"
   below for skip / pass / fail semantics. This step is the
   earliest signal that `DATABASE_URL` is misconfigured (pointing at
   a non-bypass role); catching it here keeps the broader pytest
   suite from going red for the same root cause.
5. **Backend pytest** — the existing 1760-test suite, run with both
   migration trees applied and the bypass regression already green.
   Must stay green.
6. **Frontend smoke** — only when frontend files were touched in the
   subphase. Out of scope for F2.22.3.

### Bypass regression (F2.22.3.G)

`backend/tests/test_rls_bypass.py` is environment-aware:

- On a fresh local checkout (Alembic only, Supabase migrations not
  applied), the detection and helper-existence checks SKIP cleanly,
  while the **active regression**
  (`test_fastapi_request_succeeds_under_actively_enforced_rls`)
  always runs: it force-enables RLS on `public.users` inside the
  test's own transaction, then exercises GET `/auth/me`. The test's
  transaction is rolled back at teardown, so no state leaks.
- After the Supabase migrations are applied, the detection check
  actively verifies that the FastAPI runtime role bypasses RLS, and
  the helper-existence check confirms all three helpers are
  installed.
- If RLS is active in this database but `DATABASE_URL` points at a
  role that lacks `BYPASSRLS` (and is not a superuser), both
  bypass-related tests FAIL with explicit messages — that is the
  broken-deploy condition this layer catches before the rest of the
  pytest suite goes red.

Run it with:

```bash
cd backend
python -m pytest tests/test_rls_bypass.py -q
```

Alembic remains the schema authority. Supabase migrations must not
create or alter `public.*` application tables. See
[`../supabase/README.md`](../supabase/README.md) for the ownership
split and the implementation status table.

### DATABASE_URL discipline in RLS-active environments

Once the F2.22.3.D baseline is applied to an environment, FastAPI's
`DATABASE_URL` **must** use the `nuberush_app` role (or any role with
`BYPASSRLS`). Recap of the rules from
[`f2.22.3-rls-bypass-role.md`](f2.22.3-rls-bypass-role.md) §4:

- Driver: `postgresql+psycopg://` (psycopg 3) — required for the
  prepared-statement and `SELECT ... FOR UPDATE` semantics the
  inventory/orders concurrency tests rely on.
- Pooler: Supavisor **session** pooler. The Supavisor **transaction**
  pooler is forbidden — see the F2.22.1 cutover section above.
- TLS: `?sslmode=require` outside local development.
- **`SUPABASE_SERVICE_ROLE_KEY` is NOT the DB bypass role.** That env
  var is an HTTP API key for the Supabase Admin API, consumed only by
  `backend/app/services/supabase_admin.py` to create `auth.users`
  rows. It never appears in `DATABASE_URL` and has no Postgres role
  attached. Confusing the two has come up enough that it deserves a
  callout here as well as in
  [`f2.22.3-rls-bypass-role.md`](f2.22.3-rls-bypass-role.md) §1.1.

---

## F2.22.4 Supabase Storage

F2.22.4 adds product image upload through Supabase Storage while
keeping FastAPI the authority for permissions and metadata. No new
frontend env var is required for Storage — the frontend reuses the
F2.22.2 auth env vars.

### Required env vars (already in `backend/.env.example`)

Backend (server-only):

- `SUPABASE_URL` — project base URL. Already required by F2.22.2 for
  JWT verification; F2.22.4 reuses it to address the Storage REST API
  and to derive the public CDN URL for `product-images`.
- `SUPABASE_SERVICE_ROLE_KEY` — service-role key server-only. Already
  required by F2.22.2.E for the Auth Admin API; F2.22.4 reuses it to
  mint signed upload URLs against Supabase Storage. **Never expose to
  the frontend, never log, never return in a response body.**
  Confusing this with the `nuberush_app` DB bypass role has come up
  before — the two are unrelated; see the callout in
  [`f2.22.3-rls-bypass-role.md`](f2.22.3-rls-bypass-role.md) §1.1.

Frontend (browser-safe, build-time, already in `web/.env.example`):

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

The anon key is the **only** Supabase credential the frontend ever
holds. `SUPABASE_SERVICE_ROLE_KEY` must not appear in `web/.env` or
in any `VITE_*` var — Vite would inline it into the public bundle.

### Buckets (provisioned by `supabase/migrations/`)

| Bucket | Posture | F2.22.4 use |
| --- | --- | --- |
| `product-images` | public-read | wired end-to-end; storefront renders `primary_image.public_url` via the public CDN; writes only through FastAPI-issued signed upload URLs |
| `store-assets` | private | provisioned only; no UI/end-to-end integration |
| `compliance-attachments` | private | provisioned only; no UI/end-to-end integration |
| `exports` | private | provisioned only; no UI/end-to-end integration |

No `storage.objects` `INSERT` / `UPDATE` / `DELETE` policy is granted
to the `authenticated` or `anon` roles for any of these buckets —
no direct authenticated storage writes are allowed, by contract
(`docs/f2.22-contract-lock.md` §§7, 8.1). Signed upload URLs minted
server-side with `SUPABASE_SERVICE_ROLE_KEY` are the only write path.

### Metadata table (`public.product_images`)

Created by Alembic revision `d2f9e8a7c1b6_add_product_images.py`.
Holds the FastAPI-owned image metadata (id, product_id, object_key,
uploaded_by_user_id, timestamps). Unique constraint on `product_id`
enforces one primary image per product. RLS is `ENABLE` + `FORCE`
with **zero positive policies** for `authenticated` or `anon`
(`supabase/migrations/20260527142744_product_images_rls.sql`); FastAPI
reaches the table through the existing `nuberush_app` BYPASSRLS role
established in F2.22.3.

### Operational upload flow

1. Admin selects an image in the admin product detail page.
2. The frontend hook (`useProductImageUpload`) validates the file type
   (JPEG / PNG / WebP) and size (≤ 5 MB) client-side. Backend remains
   authoritative.
3. The frontend calls `POST /products/{id}/image-upload-url`. FastAPI
   asserts `require_admin`, that the product exists, and that the
   declared content type / size / filename are safe.
4. FastAPI generates a server-side object key
   (`products/{product_id}/<uuid>.<ext>`) and asks Supabase Storage to
   sign an upload URL using `SUPABASE_SERVICE_ROLE_KEY`. The
   service-role key never leaves the backend.
5. The frontend uploads the binary with
   `supabase.storage.from("product-images").uploadToSignedUrl(...)`.
   This is the **only** `supabase-js` storage method touched by the
   admin upload flow.
6. The frontend calls `POST /products/{id}/images` with the bucket and
   object key. FastAPI re-validates the bucket and the
   `products/{product_id}/` prefix.
7. FastAPI upserts a row in `public.product_images` (unique on
   `product_id` — repeated confirms replace the existing row).
8. The frontend invalidates the product detail / list query keys; the
   detail page refetches and renders `primary_image.public_url` from
   the FastAPI response. The frontend never derives the public URL
   from `object_key` itself.

### Boundary checklist (running totals)

- No `supabase.from(...)` against `public.products` or
  `public.product_images` anywhere in `web/src/features/`.
- No frontend reference to `SUPABASE_SERVICE_ROLE_KEY` or the
  `service_role` token; only the F2.22.2 anon key is bundled.
- No `storage.objects` `INSERT` / `UPDATE` / `DELETE` policy exists
  for any of the four buckets — `supabase/tests/storage_buckets.sql`
  Part B asserts this on Supabase-enabled environments and SKIPs
  with a `NOTICE` on bare local Postgres.

### Rollback / emergency disable

If product image upload misbehaves, prefer the **smallest reversible
control first**:

1. **Disable the admin entry point** — hide `ProductImagePanel` from
   `AdminProductDetailPage`, or pull the user out of the `admin`
   role. Existing rows remain readable; new uploads stop.
2. **Disable the backend endpoints** — comment out
   `POST /products/{id}/image-upload-url` and
   `POST /products/{id}/images` in `backend/app/api/routes/products.py`.
   No new signed URLs are minted and no metadata can be written.
3. **Do NOT** rotate by adding `authenticated` storage write policies
   or by giving the frontend the service-role key. The contract
   bans both outright; any "quick fix" of that shape must update
   `docs/f2.22-contract-lock.md` first.

Full rollback, in reverse order of the subphase plan:

| Step | Action | Reverses |
| --- | --- | --- |
| 1 | Remove `ProductImagePanel` + `useProductImageUpload` + `features/products/storage.ts` from the frontend | F2.22.4.G |
| 2 | Remove `POST /products/{id}/image-upload-url`, `POST /products/{id}/images`, `app/services/storage.py`, image schemas | F2.22.4.F |
| 3 | `alembic downgrade -1` past `d2f9e8a7c1b6_add_product_images.py` (drops `public.product_images`) | F2.22.4.D |
| 4 | Drop the storage migrations or `DELETE FROM storage.buckets WHERE id IN ('product-images', 'store-assets', 'compliance-attachments', 'exports')` after emptying objects | F2.22.4.C and F2.22.4.E |

`product-images` being public-read is only safe because writes are
controlled by FastAPI-issued signed URLs and metadata writes are
FastAPI-only. Loosening either of those properties — public writes,
or letting the frontend write `public.product_images` directly —
breaks the contract and must not be done as a hotfix.

---

## Common errors and fixes

| Error | Root cause | Fix |
|---|---|---|
| `connection failed: connection to server at "127.0.0.1", port 5432` | Postgres not running | Start the container (`docker start nuberush-pg`) or service (`brew services start postgresql@16`, `pg_ctlcluster 16 main start`). |
| `ModuleNotFoundError: No module named 'alembic'` | Venv not active | Activate `.vendor_py` / `.venv` or set `PYTHONPATH`. |
| `ModuleNotFoundError: No module named 'app'` | Running pytest from wrong directory | `cd backend` first; pytest config lives in `backend/pytest.ini`. |
| `Target database is not up to date` | Migrations not applied | `python -m alembic upgrade head`. |
| `password authentication failed for user "nuberush"` | Postgres user/db credentials don't match | Recreate the role with the right password: `ALTER USER nuberush WITH PASSWORD 'nuberush';`. |
| `port 5432 already allocated` (Docker) | Native Postgres already running on that port | Either stop the native one or map Docker to a different host port (`-p 5433:5432` and adjust `DATABASE_URL_TEST`). |

---

## What this sandbox does that local needs to match

These are the exact preconditions a Claude session needs to run the
suite without manual intervention:

1. **Postgres 16 cluster running on `localhost:5432`** with role
   `nuberush` (password `nuberush`) owning DB `nuberush_test`. The
   conftest fixture downgrades to base + upgrades to head on every
   session start, so a fresh DB is fine.
2. **A Python 3.11 environment with the deps pinned in
   `backend/requirements.txt`.** This sandbox installs them
   globally; your laptop uses a venv. Either works.
3. **`backend/` as the working directory** when running pytest or
   alembic, because both pick up config files relative to that path
   (`backend/pytest.ini`, `backend/alembic.ini`).
4. **`DATABASE_URL` defined in the environment** — `.env` file or
   shell export.

If your local has all four, you can run the same `pytest -v` your
sandbox-side Claude runs. The codebase is identical; only the
runtime environment differs.

---

## Quick reference — Windows daily workflow

```powershell
# 1. Start Postgres
docker start nuberush-pg

# 2. Activate venv
cd C:\Users\ceo\OneDrive\Desktop\Nuberush
.\.vendor_py\Scripts\Activate.ps1

# 3. Move into backend
cd backend

# 4. Run validation
python -m alembic check
python -m pytest -v

# 5. (When done) stop Postgres
docker stop nuberush-pg
```

That's the full loop. If steps 1–4 succeed you can validate any
phase locally and your Claude won't need to fall back to "the
sandbox is the only place that works."

## F2.25.4 Owner activation / set password

F2.25.4 lets an approved store owner set their own password through
Supabase Auth. On approval the owner's Supabase `auth.users` record is
already created (with a random password that is never exposed); the
backend then asks Supabase Auth to email the owner a set-password link
that lands at the frontend `/auth/callback` route.

### Backend env var

- Set `APP_PUBLIC_BASE_URL=http://localhost:5173` for local development
  (it is the public frontend origin, **not** a secret). In production set
  it to the real frontend origin, e.g.
  `https://your-production-domain.com`. The backend builds the redirect as
  `{APP_PUBLIC_BASE_URL}/auth/callback`.
- If `APP_PUBLIC_BASE_URL` is left blank (the default), the backend skips
  the owner-activation email trigger entirely, so local/dev/test stay
  offline.

### Supabase dashboard step

- Add `http://localhost:5173/auth/callback` to **Authentication → URL
  Configuration → Redirect URLs** for local development.
- Add the production equivalent
  (`https://your-production-domain.com/auth/callback`) in production.
- Without the redirect URL on the allowlist, Supabase rejects the link.

### Notes

- The frontend `/auth/callback` and `/auth/set-password` routes are
  implemented in the later frontend part of F2.25.4.
- No service-role key belongs in the frontend env — the anon key remains
  the only Supabase credential the frontend holds.
