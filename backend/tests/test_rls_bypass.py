"""F2.22.3.G — FastAPI bypass regression for the F2.22.3 RLS baseline.

The F2.22.3.D migration enables ENABLE+FORCE ROW LEVEL SECURITY on every
``public.*`` application table. With no positive policies and a FastAPI
runtime DB role lacking BYPASSRLS, every business query would hit
``permission denied`` and the 1757-test suite would go red. The
``nuberush_app`` strategy locked in [docs/f2.22.3-rls-bypass-role.md]
is what keeps FastAPI working under deny-all.

This module is the safety net for that contract. It is environment-aware:

* "RLS not active in this database" → SKIP with a clear reason. This is
  the default local pytest state, where ``conftest.py`` only applies
  Alembic — not the Supabase migration tree. The skip means "there is
  nothing for the bypass to bypass."
* "RLS active but the current DB role does not bypass" → FAIL with a
  clear message. This is the broken-deploy condition F2.22.3.G is
  designed to catch.
* "RLS active and the current DB role bypasses" → run representative
  FastAPI / SQLAlchemy paths and assert success.

In addition to the environment-aware check, this module ships an active
regression — :func:`test_fastapi_request_succeeds_under_actively_enforced_rls`
— that ENABLEs+FORCEs RLS on ``public.users`` inside the test's
transaction (rolled back at teardown) so the regression has teeth even
when the Supabase migration tree has not yet been applied to the local
test database.

This file deliberately does not exercise frontend / supabase-js paths,
storage, or realtime; the F2.22 hybrid contract (§7) keeps RLS as
defense-in-depth and FastAPI as the primary authorization layer, so
"FastAPI still works under deny-all RLS" is the only invariant under
test here.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for
from tests.helpers.auth import make_user as central_make_user


# Kept in sync with supabase/migrations/20260526142048_rls_baseline.sql.
# Any new public.* table covered by that migration must also be added
# here so the detection check stays accurate.
_RLS_BASELINE_TABLES = (
    "users",
    "stores",
    "products",
    "product_variants",
    "inventory_items",
    "inventory_logs",
    "orders",
    "order_items",
    "order_audit_logs",
    "product_compliance_audit_logs",
)


def _current_role_bypasses_rls(db: Session) -> bool:
    """True iff ``current_user`` has BYPASSRLS or is a superuser.

    Postgres exempts both kinds of roles from RLS uniformly — superusers
    bypass RLS by definition, ``rolbypassrls`` is the fine-grained flag
    intended for non-superuser application roles like ``nuberush_app``.
    """
    return bool(
        db.execute(
            text(
                "SELECT rolbypassrls OR rolsuper FROM pg_roles "
                "WHERE rolname = current_user"
            )
        ).scalar_one()
    )


def _rls_enabled_count(db: Session) -> int:
    """How many of the baseline tables currently have ``relrowsecurity=true``."""
    return int(
        db.execute(
            text(
                "SELECT count(*) FROM pg_class "
                "WHERE relnamespace = 'public'::regnamespace "
                "AND relkind = 'r' "
                "AND relrowsecurity = true "
                "AND relname = ANY(:names)"
            ),
            {"names": list(_RLS_BASELINE_TABLES)},
        ).scalar_one()
    )


def _current_role(db: Session) -> str:
    return str(db.execute(text("SELECT current_user")).scalar_one())


# ---------------------------------------------------------------------------
# Detection — runs in every environment; SKIPs when RLS is not active.
# ---------------------------------------------------------------------------


def test_db_role_bypasses_rls_when_baseline_is_applied(
    db_session: Session,
) -> None:
    """Whenever the F2.22.3 baseline is applied in this DB, the FastAPI
    runtime role must bypass it. SKIPs in the default local state, FAILs
    on the broken-deploy condition, PASSes when the migration is applied
    and the role is correct.
    """
    enabled = _rls_enabled_count(db_session)

    if enabled == 0:
        pytest.skip(
            "F2.22.3 RLS baseline not active in this database "
            "(0/10 public.* tables have relrowsecurity=true). "
            "Apply supabase/migrations/*.sql to exercise this check."
        )

    if enabled != len(_RLS_BASELINE_TABLES):
        # Partial application is itself a deploy bug — the baseline must
        # be all-or-nothing or per-table policies will surprise reviewers.
        pytest.fail(
            f"F2.22.3 RLS baseline is partially applied: "
            f"{enabled}/{len(_RLS_BASELINE_TABLES)} required tables have "
            "relrowsecurity=true. Re-apply "
            "supabase/migrations/20260526142048_rls_baseline.sql."
        )

    if not _current_role_bypasses_rls(db_session):
        pytest.fail(
            f"RLS is active but the current DB role {_current_role(db_session)!r} "
            "does not have BYPASSRLS (and is not a superuser). FastAPI "
            "would be blocked by the deny-all baseline. Repoint "
            "DATABASE_URL at the nuberush_app role per "
            "docs/f2.22.3-rls-bypass-role.md, or grant BYPASSRLS to the "
            "current role."
        )


# ---------------------------------------------------------------------------
# Active regression — always runs. Force-enables RLS inside the test's
# transaction so the regression has teeth even when the Supabase migration
# tree has not yet been applied to the local DB.
# ---------------------------------------------------------------------------


def test_fastapi_request_succeeds_under_actively_enforced_rls(
    client: TestClient,
    db_session: Session,
) -> None:
    """Exercises GET /auth/me — the most security-sensitive read path,
    which deps.get_current_user resolves from public.users — under
    ENABLE+FORCE ROW LEVEL SECURITY on that table.

    If the current DB role does not bypass RLS, this test fails with a
    clear message. That is the broken-deploy condition the regression is
    designed to catch.

    The ALTER TABLE statements are issued through the test's transactional
    db_session; the conftest fixture rolls back the outer transaction at
    teardown, reverting the RLS settings cleanly. Postgres DDL is
    transactional, so this works whether or not the baseline migration is
    independently applied to this database.
    """
    if not _current_role_bypasses_rls(db_session):
        pytest.fail(
            f"DB role {_current_role(db_session)!r} does not bypass RLS; "
            "FastAPI would be blocked by deny-all. Configure DATABASE_URL "
            "for the nuberush_app role per docs/f2.22.3-rls-bypass-role.md."
        )

    user = central_make_user(db_session, role=UserRole.admin)

    # Apply the same ALTER TABLE pair the F2.22.3.D migration applies.
    # FORCE is the load-bearing flag: ENABLE alone exempts table owners,
    # which would mask a missing BYPASSRLS on an owner-equivalent role.
    db_session.execute(
        text("ALTER TABLE public.users ENABLE ROW LEVEL SECURITY")
    )
    db_session.execute(
        text("ALTER TABLE public.users FORCE  ROW LEVEL SECURITY")
    )

    response = client.get("/auth/me", headers=auth_headers_for(user))

    assert response.status_code == 200, (
        f"GET /auth/me returned {response.status_code} under enforced "
        f"RLS — FastAPI bypass regression has failed. Body: {response.text[:300]}"
    )
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["role"] == UserRole.admin.value
    assert body["is_active"] is True

    # SELECT through SQLAlchemy directly — closes the loop on "FastAPI's
    # SQLAlchemy session can read public.users under deny-all RLS".
    direct_count = db_session.execute(
        text(
            "SELECT count(*) FROM public.users WHERE auth_user_id = :uid"
        ),
        {"uid": user.auth_user_id},
    ).scalar_one()
    assert direct_count == 1, (
        "FastAPI SQLAlchemy session could not see the seeded public.users "
        "row under enforced RLS even though current_user reports BYPASSRLS — "
        "diagnose the role's effective attributes."
    )


# ---------------------------------------------------------------------------
# Helper-function presence — SKIPs unless the F2.22.3.E migration applied.
# ---------------------------------------------------------------------------


def test_rls_helpers_present_when_helpers_migration_is_applied(
    db_session: Session,
) -> None:
    """When supabase/migrations/20260526144321_rls_helpers.sql has been
    applied, all three helpers must exist. SKIPs cleanly on a fresh
    checkout where the Supabase migration tree has not been applied.
    """
    helper_names = (
        "current_app_user_id",
        "current_app_user_store_id",
        "is_admin",
    )
    existing = (
        db_session.execute(
            text(
                "SELECT proname FROM pg_proc "
                "WHERE pronamespace = 'public'::regnamespace "
                "AND proname = ANY(:names)"
            ),
            {"names": list(helper_names)},
        )
        .scalars()
        .all()
    )

    if not existing:
        pytest.skip(
            "F2.22.3.E RLS helpers not installed in this database. "
            "Apply supabase/migrations/20260526144321_rls_helpers.sql."
        )

    missing = sorted(set(helper_names) - set(existing))
    if missing:
        pytest.fail(
            f"F2.22.3.E helper functions partially applied — missing: {missing}. "
            "Re-apply supabase/migrations/20260526144321_rls_helpers.sql."
        )
