"""create driver_delivery_operational_states

Dr.1.1.G.1 — Delivery Operational State Foundation. This migration ONLY lays
down storage for the dedicated delivery operational-state entity. There is no
service, schema, read endpoint, route, or transition logic in this subphase;
nothing here mutates orders, inventory, `OrderStatus`, or the assignment
lifecycle.

What this migration creates:

- `driver_delivery_operational_states`: the dedicated operational-state record
  (Dr.1.1.G domain contract — a THIRD axis distinct from `OrderStatus` and
  `OrderDriverAssignment.status`). Anchored 1:1 on an assignment via a UNIQUE
  `assignment_id`. Its `state` is a VARCHAR + CHECK over the frozen Dr.1.1.G
  vocabulary (no PG enum, so new states never need an `ALTER TYPE`). FKs:
  assignment_id -> order_driver_assignments.id CASCADE (the state is owned by
  its assignment), order_id -> orders.id CASCADE, store_id -> stores.id
  CASCADE, driver_profile_id -> driver_profiles.id RESTRICT (preserve
  operational history; a profile with state rows cannot be hard-deleted).
  `order_id` / `driver_profile_id` / `store_id` are denormalized read anchors
  for future self-scoped, store-bound reads — never a license to mutate the
  order. Mutable, so it gets a `set_updated_at` trigger (the shared
  `set_updated_at()` function is created by migration 7a5ba742b190).

No separate index on `assignment_id`: the UNIQUE constraint already creates a
sufficient unique btree index. Indexes are created for `order_id`,
`driver_profile_id`, `store_id`, and `state`.

Deliberately NOT here: any change to orders / order_driver_assignments /
driver_profiles / stores columns, `OrderStatus`, `OrderDriverAssignmentStatus`,
any `assigned_driver_id` / `driver_id` on orders, RLS, schemas, services,
routes, or transition logic.

Revision ID: 9e15cd2f6a7a
Revises: f1a8d3c6b2e9
Create Date: 2026-06-12 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9e15cd2f6a7a"
down_revision = "f1a8d3c6b2e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_delivery_operational_states",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("driver_profile_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column(
            "state",
            sa.String(length=40),
            server_default=sa.text("'not_started'"),
            nullable=False,
        ),
        sa.Column(
            "state_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_transition_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
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
        sa.UniqueConstraint(
            "assignment_id",
            name="uq_driver_delivery_operational_states_assignment_id",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["order_driver_assignments.id"],
            name="fk_driver_delivery_operational_states_assignment_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_driver_delivery_operational_states_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["driver_profile_id"],
            ["driver_profiles.id"],
            name="fk_driver_delivery_operational_states_driver_profile_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_driver_delivery_operational_states_store_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "state IN ('not_started', 'en_route_to_store', "
            "'arrived_at_store', 'pickup_started', 'picked_up', "
            "'en_route_to_customer', 'arrived_at_customer', "
            "'id_verification_pending', 'id_verified', "
            "'delivery_completed', 'delivery_failed', "
            "'returning_to_store', 'returned_to_store', 'canceled')",
            name="ck_driver_delivery_operational_states_state_valid",
        ),
    )
    op.create_index(
        "ix_driver_delivery_operational_states_order_id",
        "driver_delivery_operational_states",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "ix_driver_delivery_operational_states_driver_profile_id",
        "driver_delivery_operational_states",
        ["driver_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_driver_delivery_operational_states_store_id",
        "driver_delivery_operational_states",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_driver_delivery_operational_states_state",
        "driver_delivery_operational_states",
        ["state"],
        unique=False,
    )

    # Keep updated_at fresh on UPDATE, matching every other timestamped table
    # in this schema. The set_updated_at() function is created by migration
    # 7a5ba742b190 (initial schema).
    op.execute(
        """
        CREATE TRIGGER trg_driver_delivery_operational_states_set_updated_at
        BEFORE UPDATE ON driver_delivery_operational_states
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_driver_delivery_operational_states_set_updated_at "
        "ON driver_delivery_operational_states"
    )
    op.drop_index(
        "ix_driver_delivery_operational_states_state",
        table_name="driver_delivery_operational_states",
    )
    op.drop_index(
        "ix_driver_delivery_operational_states_store_id",
        table_name="driver_delivery_operational_states",
    )
    op.drop_index(
        "ix_driver_delivery_operational_states_driver_profile_id",
        table_name="driver_delivery_operational_states",
    )
    op.drop_index(
        "ix_driver_delivery_operational_states_order_id",
        table_name="driver_delivery_operational_states",
    )
    op.drop_table("driver_delivery_operational_states")
