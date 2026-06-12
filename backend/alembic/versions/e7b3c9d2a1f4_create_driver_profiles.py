"""create driver_profiles

Dr.1.1.C — Driver Profile Foundation. This migration ONLY lays down storage
for the minimal operational driver identity. It introduces no /driver/*
behaviour beyond the read model, mutates no existing table, and touches no
order, inventory, compliance, payment, or auth surface.

What this migration creates:

- `driver_profiles`: one row per driver `User`, bound to a `Store`
  (store-bound driver tenancy, Dr.1.1.A §4). Holds the operational `status`
  and onboarding `approval_status` as VARCHAR + CHECK discriminators (no PG
  enum, matching the F2.27 convention), plus the three lifecycle timestamps
  (`activated_at` / `deactivated_at` / `approved_at`, all nullable).
  UNIQUE(user_id) makes the User<->DriverProfile link one-to-one. Mutable, so
  it gets a `set_updated_at` trigger (the shared `set_updated_at()` function
  is created by migration 7a5ba742b190).

Deliberately NOT here: documents, vehicles, training, background checks,
payout, assignments, availability, eligibility, audit, any /driver route
besides GET /driver/me, and any change to existing tables. `suspended` is NOT
a valid status in this subphase. The user/store match invariant is enforced
in the service layer and tests, not by a (cross-table) CHECK.

Revision ID: e7b3c9d2a1f4
Revises: d5f3b9c8a2e1
Create Date: 2026-06-12 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7b3c9d2a1f4"
down_revision = "d5f3b9c8a2e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_profiles",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "approval_status", sa.String(length=20), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "activated_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "deactivated_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "approved_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_driver_profiles_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_driver_profiles_store_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "user_id", name="uq_driver_profiles_user_id"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_driver_profiles_status_valid",
        ),
        sa.CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_driver_profiles_approval_status_valid",
        ),
    )
    op.create_index(
        "ix_driver_profiles_store_id",
        "driver_profiles",
        ["store_id"],
        unique=False,
    )

    # Keep updated_at fresh on UPDATE, matching every other timestamped
    # table in this schema. The set_updated_at() function is created by
    # migration 7a5ba742b190 (initial schema).
    op.execute(
        """
        CREATE TRIGGER trg_driver_profiles_set_updated_at
        BEFORE UPDATE ON driver_profiles
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_driver_profiles_set_updated_at "
        "ON driver_profiles"
    )
    op.drop_index(
        "ix_driver_profiles_store_id",
        table_name="driver_profiles",
    )
    op.drop_table("driver_profiles")
