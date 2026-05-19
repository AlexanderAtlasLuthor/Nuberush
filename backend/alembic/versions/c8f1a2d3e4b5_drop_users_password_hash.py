"""drop users.password_hash

F2.22.2.F — legacy auth cleanup. Supabase Auth is now the sole identity
authority; FastAPI no longer mints JWTs or verifies local passwords. The
`users.password_hash` column is dead data and is removed here.

upgrade(): drops `users.password_hash`.

downgrade(): re-adds `users.password_hash` as a NULLABLE String(255).
It is intentionally NOT restored as NOT NULL — the original bcrypt
hashes are gone for good and cannot be reconstructed, so a NOT NULL
re-add would be impossible to satisfy for existing rows. Downgrade
restores the column shape for schema reversal only; it does not (and
cannot) restore credentials.

This migration does not touch `auth_user_id`, `email`, `role`,
`store_id` or `is_active`.

Revision ID: c8f1a2d3e4b5
Revises: b7e3a1f04c9d
Create Date: 2026-05-18 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8f1a2d3e4b5"
down_revision = "b7e3a1f04c9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "password_hash")


def downgrade() -> None:
    # Re-add nullable: the dropped hashes are unrecoverable, so a
    # NOT NULL re-add could never be backfilled. See module docstring.
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=True,
        ),
    )
