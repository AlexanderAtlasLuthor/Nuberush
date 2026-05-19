"""Backfill Supabase Auth identities for pre-F2.22.2 users (F2.22.2.E2).

Background — F2.22.2 moved authentication to Supabase:

  - F2.22.2.D: `get_current_user` verifies a Supabase JWT and loads
    `public.users` by `auth_user_id`.
  - F2.22.2.E: `POST /auth/users` creates new users in Supabase Auth +
    `public.users` atomically.

Users that existed BEFORE F2.22.2 still have `public.users.auth_user_id`
NULL and no `auth.users` record — they cannot authenticate. This tool
creates a Supabase `auth.users` record for each such user and writes the
returned id into `public.users.auth_user_id`.

Password strategy
-----------------
Existing rows only carry a bcrypt `password_hash`; the plaintext is
unrecoverable (and bcrypt cannot be reversed). So this tool sets an
operator-provided **temporary password** on every created Supabase user
(`--password` or env `NUBERUSH_BACKFILL_PASSWORD`). The temporary
password is the same for the run and is **never printed**. Backfilled
users must then reset their password through Supabase's reset flow to
obtain a real personal credential.

For the initial admin bootstrap, run the tool filtered to the admin
email with a known `--password` so the operator can sign in immediately,
then rotate that password.

The temporary password is NOT derived from `password_hash` — that is
impossible and must never be attempted.

Safety
------
  - DRY-RUN by default — reports what it would do, touches nothing and
    calls no Supabase API. Pass ``--apply`` to perform changes.
  - Idempotent — users that already have ``auth_user_id`` are skipped,
    so a rerun is safe and a no-op for already-backfilled users.
  - Per-user commit — one failure does not abort the rest of the run.
  - On a DB write failure after the Supabase user was created, the
    Supabase user is deleted (best-effort) so no orphan is left.
  - Never prints the temporary password or the service-role key.

Limitation — link-to-existing
-----------------------------
This tool does NOT look up pre-existing `auth.users` records by email
(the Supabase Admin list/filter API is version-fragile and would need
paginated scanning). It only CREATES new identities. If a Supabase
`auth.users` already exists for an email while `public.users` is still
unmapped (e.g. a torn earlier run), that user is reported as ``failed``
and needs manual operator intervention — the tool never invents a
mapping without a real `auth_user_id`.

Usage
-----

    cd backend

    # dry run — see what would happen, no changes, no Supabase calls
    DATABASE_URL=... python -m scripts.backfill_supabase_auth_users

    # apply — backfill every unmapped user with a temporary password
    DATABASE_URL=... NUBERUSH_BACKFILL_PASSWORD='<temp-pw>' \\
        python -m scripts.backfill_supabase_auth_users --apply

    # admin bootstrap — backfill just one user
    DATABASE_URL=... python -m scripts.backfill_supabase_auth_users \\
        --apply --email admin@nuberush.dev --password '<temp-pw>'

A real run also needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the
environment (consumed by app.services.supabase_admin).
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

# Allow `python -m scripts.backfill_supabase_auth_users` from backend/
# and a direct invocation from anywhere by ensuring backend/ is on
# sys.path (same convention as scripts/seed_sample_data.py).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_session_factory
from app.services import supabase_admin
from app.services.supabase_admin import SupabaseAdminError


_BACKFILL_PASSWORD_ENV = "NUBERUSH_BACKFILL_PASSWORD"


class BackfillError(Exception):
    """Raised for operator-facing backfill misuse (e.g. --apply with no password)."""


@dataclass
class BackfillSummary:
    """Counts reported at the end of a backfill run."""

    scanned: int = 0
    skipped_already_mapped: int = 0
    created: int = 0
    # `linked` (re-using a pre-existing auth.users record) is always 0:
    # see the "link-to-existing" limitation in the module docstring.
    linked: int = 0
    failed: int = 0


def _rollback_supabase_user(
    delete_auth_user, auth_user_id: uuid.UUID, email: str
) -> None:
    """Best-effort delete of a Supabase user after a failed DB update."""
    try:
        delete_auth_user(auth_user_id)
        print(f"  [rollback] deleted orphaned Supabase identity for {email}")
    except SupabaseAdminError:
        print(
            f"  [warning]  could not roll back the Supabase identity for "
            f"{email}; manual cleanup of the orphaned auth.users row "
            f"may be required."
        )


def run_backfill(
    db: Session,
    *,
    create_auth_user,
    delete_auth_user,
    apply: bool = False,
    email: str | None = None,
    temp_password: str | None = None,
) -> BackfillSummary:
    """Backfill Supabase identities for users missing ``auth_user_id``.

    Testable core of the CLI. ``create_auth_user`` / ``delete_auth_user``
    are injected (the real ones in production, fakes in tests) so this
    function never depends on a live Supabase project.

    DRY-RUN (``apply=False``, the default) reports what it would do and
    calls neither ``create_auth_user`` nor ``db.commit()``.
    """
    summary = BackfillSummary()
    print(f"Supabase auth backfill — {'APPLY' if apply else 'DRY-RUN'}")

    if apply and not temp_password:
        # Refuse to apply without an explicit operator-provided password.
        # We never derive one from password_hash.
        raise BackfillError(
            "A temporary password is required to apply the backfill. "
            f"Pass --password or set {_BACKFILL_PASSWORD_ENV}."
        )

    stmt = select(User)
    if email is not None:
        stmt = stmt.where(User.email == email.strip().lower())
    stmt = stmt.order_by(User.created_at)
    candidates = list(db.scalars(stmt).all())
    summary.scanned = len(candidates)

    for user in candidates:
        if user.auth_user_id is not None:
            summary.skipped_already_mapped += 1
            continue

        if not apply:
            print(
                f"  [would create] {user.email} (role={user.role.value})"
            )
            continue

        # Create the Supabase identity first, then link it onto
        # public.users — same order as POST /auth/users (F2.22.2.E).
        metadata = {
            "full_name": user.full_name,
            "nuberush_role": user.role.value,
            "nuberush_store_id": (
                str(user.store_id) if user.store_id is not None else None
            ),
        }
        try:
            auth_user_id = create_auth_user(user.email, temp_password, metadata)
        except SupabaseAdminError as exc:
            summary.failed += 1
            print(
                f"  [failed]  {user.email}: identity provider create "
                f"failed ({exc})"
            )
            continue

        user.auth_user_id = auth_user_id
        try:
            db.commit()
        except Exception as exc:
            # DB update failed after the Supabase user was created
            # (e.g. an auth_user_id unique-index collision). Roll back
            # the DB and delete the now-orphaned Supabase identity.
            db.rollback()
            _rollback_supabase_user(delete_auth_user, auth_user_id, user.email)
            summary.failed += 1
            print(
                f"  [failed]  {user.email}: database update failed ({exc})"
            )
            continue

        summary.created += 1
        print(f"  [created] {user.email} -> {auth_user_id}")

    _print_summary(summary, apply)
    return summary


def _print_summary(summary: BackfillSummary, apply: bool) -> None:
    print()
    print("Summary:")
    print(f"  scanned:                {summary.scanned}")
    print(f"  skipped_already_mapped: {summary.skipped_already_mapped}")
    print(f"  created:                {summary.created}")
    print(f"  linked:                 {summary.linked}")
    print(f"  failed:                 {summary.failed}")
    if not apply:
        print()
        print(
            "DRY-RUN — no changes were made and no Supabase API was "
            "called. Re-run with --apply to perform the backfill."
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill Supabase Auth identities for users missing "
            "auth_user_id. Dry-run by default; pass --apply to commit."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the backfill. Without this flag the tool dry-runs.",
    )
    parser.add_argument(
        "--email",
        default=None,
        help=(
            "Restrict the backfill to a single user by email "
            "(also the way to bootstrap one admin)."
        ),
    )
    parser.add_argument(
        "--password",
        default=None,
        help=(
            "Temporary password set on created Supabase users. Required "
            f"with --apply. May also be supplied via {_BACKFILL_PASSWORD_ENV}. "
            "Never printed; users should reset it afterwards."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if "DATABASE_URL" not in os.environ:
        print(
            "❌ DATABASE_URL is not set. Point it at the target database "
            "before running.",
            file=sys.stderr,
        )
        return 1

    temp_password = args.password or os.environ.get(_BACKFILL_PASSWORD_ENV)

    session_factory = get_session_factory()
    with session_factory() as db:
        try:
            run_backfill(
                db,
                create_auth_user=supabase_admin.create_auth_user,
                delete_auth_user=supabase_admin.delete_auth_user,
                apply=args.apply,
                email=args.email,
                temp_password=temp_password,
            )
        except BackfillError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        except Exception:
            db.rollback()
            raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
