"""create order_driver_assignments

Dr.1.1.E — Order Driver Assignment Model Foundation. This migration ONLY lays
down storage for the dedicated driver<->order assignment entity. There is no
dispatch, accept/decline, read endpoint, service, schema, or route in this
subphase; nothing here mutates orders, inventory, or `OrderStatus`.

What this migration creates:

- `order_driver_assignments`: the dedicated assignment record (Dr.1.1.A §10),
  deliberately NOT an `assigned_driver_id` column on `orders`. It carries its
  own lifecycle `status` (VARCHAR + CHECK over the frozen §10 vocabulary; no PG
  enum) and the lifecycle timestamps `assigned_at` / `accepted_at` /
  `declined_at` / `canceled_at` / `completed_at`. FKs:
  order_id -> orders.id CASCADE, driver_profile_id -> driver_profiles.id
  RESTRICT (preserve assignment history; a driver profile with assignments
  cannot be hard-deleted), store_id -> stores.id CASCADE. Mutable, so it gets a
  `set_updated_at` trigger (the shared `set_updated_at()` function is created by
  migration 7a5ba742b190).

Deliberately NOT here: any unique / partial-unique constraint (offer fan-out
semantics are not frozen — uniqueness is deferred to Dr.1.1.F), PG enum, RLS,
`offered_at` / `expired_at` / `started_at`, and any change to orders /
driver_profiles / stores / OrderStatus. The user/store match invariant is a
service-level rule for a later subphase, not a (cross-table) DB constraint.

Revision ID: f1a8d3c6b2e9
Revises: e7b3c9d2a1f4
Create Date: 2026-06-12 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a8d3c6b2e9"
down_revision = "e7b3c9d2a1f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_driver_assignments",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("driver_profile_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "accepted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "declined_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "canceled_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_order_driver_assignments_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["driver_profile_id"],
            ["driver_profiles.id"],
            name="fk_order_driver_assignments_driver_profile_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_order_driver_assignments_store_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('offered', 'accepted', 'declined', 'expired', "
            "'assigned', 'started', 'completed', 'canceled')",
            name="ck_order_driver_assignments_status_valid",
        ),
    )
    op.create_index(
        "ix_order_driver_assignments_order_id",
        "order_driver_assignments",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_driver_assignments_driver_profile_id",
        "order_driver_assignments",
        ["driver_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_driver_assignments_store_id",
        "order_driver_assignments",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_driver_assignments_status",
        "order_driver_assignments",
        ["status"],
        unique=False,
    )

    # Keep updated_at fresh on UPDATE, matching every other timestamped
    # table in this schema. The set_updated_at() function is created by
    # migration 7a5ba742b190 (initial schema).
    op.execute(
        """
        CREATE TRIGGER trg_order_driver_assignments_set_updated_at
        BEFORE UPDATE ON order_driver_assignments
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_order_driver_assignments_set_updated_at "
        "ON order_driver_assignments"
    )
    op.drop_index(
        "ix_order_driver_assignments_status",
        table_name="order_driver_assignments",
    )
    op.drop_index(
        "ix_order_driver_assignments_store_id",
        table_name="order_driver_assignments",
    )
    op.drop_index(
        "ix_order_driver_assignments_driver_profile_id",
        table_name="order_driver_assignments",
    )
    op.drop_index(
        "ix_order_driver_assignments_order_id",
        table_name="order_driver_assignments",
    )
    op.drop_table("order_driver_assignments")
