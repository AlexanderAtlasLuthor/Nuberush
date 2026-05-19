"""add users.auth_user_id identity bridge

F2.22.2 (subphase B) — adds the minimal structural bridge between
Supabase Auth and `public.users` without changing the active
login/JWT flow.

What this migration does:

- Adds column `users.auth_user_id` UUID, nullable. It will hold the
  Supabase `auth.users` id (= the Supabase JWT `sub`) once identity
  is migrated. Nullable because existing rows have no Supabase
  identity yet and the current login flow still keys on `id`.
- Adds a unique index `ix_users_auth_user_id` so a Supabase identity
  maps to at most one `public.users` row, and so the future
  `WHERE auth_user_id = :sub` lookup is indexed. Postgres treats
  NULLs as distinct, so multiple rows may keep `auth_user_id` NULL
  during the migration window.

What this migration deliberately does NOT do:

- It does not touch `password_hash` (still NOT NULL).
- It does not create a cross-schema foreign key to `auth.users`:
  that schema is owned by Supabase. The relationship stays
  conceptual for this subphase.

Revision ID: b7e3a1f04c9d
Revises: a1c4f9d83b22
Create Date: 2026-05-18 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b7e3a1f04c9d"
down_revision = "a1c4f9d83b22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_users_auth_user_id",
        "users",
        ["auth_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_auth_user_id", table_name="users")
    op.drop_column("users", "auth_user_id")
