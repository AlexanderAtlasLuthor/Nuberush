-- =============================================================================
-- F2.22.4.H — Supabase Storage bucket + policy posture tests
-- =============================================================================
--
-- Validates the F2.22.4.C bucket provisioning:
--   A. The four F2.22.4 buckets exist with the locked public/private
--      posture: product-images public, the other three private.
--   B. No permissive write policy on `storage.objects` grants the
--      `authenticated`, `anon`, or `public` roles INSERT / UPDATE /
--      DELETE / ALL across any bucket — direct authenticated writes
--      must remain denied at all four buckets (the contract bans
--      them; signed upload URLs from FastAPI are the only write
--      path).
--
-- Execution context (see ../README.md and supabase/tests/README.md):
--   * Run AFTER applying every file in supabase/migrations/, against
--     a Supabase-enabled database (the platform installs the
--     `storage` schema and `storage.buckets` / `storage.objects`
--     tables). On a bare local Postgres without the Supabase storage
--     extension, the script SKIPs each part with a NOTICE rather
--     than failing, mirroring how rls_helpers.sql handles missing
--     `auth.uid()`.
--   * Invoke with:  psql ... -v ON_ERROR_STOP=1 -f supabase/tests/storage_buckets.sql
--   * No transient roles, no transient rows; reads only. Safe to run
--     anywhere with the storage extension; SKIPs gracefully without.
--   * NOT for production: keep this pointed at a local / CI DB.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Part A — Four buckets exist with the locked public/private posture.
-- ---------------------------------------------------------------------------

DO $A$
DECLARE
  expected_public  CONSTANT text[] := ARRAY['product-images'];
  expected_private CONSTANT text[] := ARRAY[
    'store-assets', 'compliance-attachments', 'exports'
  ];
  b text;
  is_public boolean;
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM information_schema.tables
     WHERE table_schema = 'storage'
       AND table_name = 'buckets'
  ) THEN
    RAISE NOTICE 'SKIP [A]: storage.buckets not found '
      '(run against a Supabase-enabled environment to exercise this check)';
    RETURN;
  END IF;

  -- All four buckets must exist.
  FOREACH b IN ARRAY (expected_public || expected_private) LOOP
    PERFORM 1 FROM storage.buckets WHERE id = b;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TEST FAIL [A]: storage bucket "%" not found '
        '(F2.22.4.C migration not applied?)', b;
    END IF;
  END LOOP;

  -- Public bucket(s) must be public = true.
  FOREACH b IN ARRAY expected_public LOOP
    SELECT public INTO is_public FROM storage.buckets WHERE id = b;
    IF NOT is_public THEN
      RAISE EXCEPTION 'TEST FAIL [A]: storage bucket "%" must be public '
        '(public-read storefront contract; see docs/f2.22-contract-lock.md §8.1)', b;
    END IF;
  END LOOP;

  -- Private buckets must be public = false (provisioned skeletons in F2.22.4).
  FOREACH b IN ARRAY expected_private LOOP
    SELECT public INTO is_public FROM storage.buckets WHERE id = b;
    IF is_public THEN
      RAISE EXCEPTION 'TEST FAIL [A]: storage bucket "%" must be private '
        '(provision-only; F2.22.4 does NOT wire it end-to-end)', b;
    END IF;
  END LOOP;

  RAISE NOTICE 'PASS [A]: 4 storage buckets exist with correct public/private posture';
END
$A$;

-- ---------------------------------------------------------------------------
-- Part B — No permissive storage.objects write policy grants
-- authenticated / anon / public roles INSERT / UPDATE / DELETE / ALL.
-- The contract (docs/f2.22-contract-lock.md §§7, 8.1) bans direct
-- authenticated storage writes outright; signed upload URLs minted
-- by FastAPI with the server-side service-role key are the only
-- write path for any of the four buckets.
-- ---------------------------------------------------------------------------

DO $B$
DECLARE
  hit record;
  bad_count integer := 0;
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM information_schema.tables
     WHERE table_schema = 'pg_catalog'
       AND table_name = 'pg_policies'
  ) THEN
    -- pg_policies is a system view shipped with Postgres; absence
    -- means we are on an unsupported Postgres flavour.
    RAISE NOTICE 'SKIP [B]: pg_policies not available';
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM information_schema.tables
     WHERE table_schema = 'storage'
       AND table_name = 'objects'
  ) THEN
    RAISE NOTICE 'SKIP [B]: storage.objects not found '
      '(run against a Supabase-enabled environment to exercise this check)';
    RETURN;
  END IF;

  FOR hit IN
    SELECT policyname, cmd, roles
      FROM pg_policies
     WHERE schemaname = 'storage'
       AND tablename = 'objects'
       AND cmd IN ('INSERT', 'UPDATE', 'DELETE', 'ALL')
       AND (
         'authenticated' = ANY(roles)
         OR 'anon' = ANY(roles)
         OR 'public' = ANY(roles)
       )
  LOOP
    RAISE NOTICE 'unexpected storage.objects write policy: % (cmd=%, roles=%)',
      hit.policyname, hit.cmd, hit.roles;
    bad_count := bad_count + 1;
  END LOOP;

  IF bad_count <> 0 THEN
    RAISE EXCEPTION 'TEST FAIL [B]: % permissive storage.objects write policy/policies '
      'grant authenticated/anon/public access (direct authenticated writes are '
      'banned by docs/f2.22-contract-lock.md §§7, 8.1; signed URLs are the only '
      'write path)', bad_count;
  END IF;

  RAISE NOTICE 'PASS [B]: no authenticated/anon/public storage.objects write policy exists';
END
$B$;

-- ---------------------------------------------------------------------------
-- Final pass marker (matches the rls_baseline.sql convention).
-- ---------------------------------------------------------------------------

DO $D$
BEGIN
  RAISE NOTICE 'F2.22.4.H storage_buckets.sql — ALL CHECKS PASS (or SKIPPED when storage schema absent)';
END
$D$;
