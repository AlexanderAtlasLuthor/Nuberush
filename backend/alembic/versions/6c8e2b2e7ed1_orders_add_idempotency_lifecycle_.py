"""orders add idempotency lifecycle inventory_item_id and audit log

Revision ID: 6c8e2b2e7ed1
Revises: 5c3f52060b2f
Create Date: 2026-04-28 01:06:37.284319
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "6c8e2b2e7ed1"
down_revision = "5c3f52060b2f"
branch_labels = None
depends_on = None


# Reuse the existing order_status enum (created by the initial S1
# migration). create_type=False prevents Alembic from emitting a
# CREATE TYPE that would conflict with the type already present.
ORDER_STATUS = postgresql.ENUM(
    "pending",
    "accepted",
    "preparing",
    "ready",
    "out_for_delivery",
    "delivered",
    "canceled",
    "returned",
    name="order_status",
    create_type=False,
)


def upgrade() -> None:
    # --------------------------------------------------------------- #
    # New table: order_audit_logs
    # --------------------------------------------------------------- #
    op.create_table(
        "order_audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("performed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("previous_status", ORDER_STATUS, nullable=True),
        sa.Column("new_status", ORDER_STATUS, nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action <> ''",
            name="ck_order_audit_logs_action_non_empty",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_audit_logs_created_at",
        "order_audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_order_audit_logs_order_id",
        "order_audit_logs",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_audit_logs_performed_by_user_id",
        "order_audit_logs",
        ["performed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_audit_logs_store_id",
        "order_audit_logs",
        ["store_id"],
        unique=False,
    )

    # --------------------------------------------------------------- #
    # orders.idempotency_key — safe NOT NULL via server_default fired
    # on existing rows, then default dropped so future inserts must
    # supply the value explicitly.
    # --------------------------------------------------------------- #
    op.add_column(
        "orders",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            server_default=sa.text("gen_random_uuid()::text"),
            nullable=False,
        ),
    )
    op.alter_column("orders", "idempotency_key", server_default=None)

    # Lifecycle timestamps and cancel_reason — nullable by design.
    op.add_column(
        "orders",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("cancel_reason", sa.Text(), nullable=True),
    )

    op.create_unique_constraint(
        "uq_orders_store_idempotency_key",
        "orders",
        ["store_id", "idempotency_key"],
    )
    # Autogenerate does not detect new CHECK constraints reliably.
    op.create_check_constraint(
        "ck_orders_idempotency_key_non_empty",
        "orders",
        "idempotency_key <> ''",
    )

    # --------------------------------------------------------------- #
    # order_items.inventory_item_id — NOT NULL FK. Add nullable,
    # backfill from (store_id, variant_id) → inventory_items, then
    # set NOT NULL. Any row that fails to resolve will fail the
    # NOT NULL constraint (no inventory_item exists for that pair),
    # which is the correct behaviour for production rollouts: the
    # operator sees the failure and investigates.
    # --------------------------------------------------------------- #
    op.add_column(
        "order_items",
        sa.Column("inventory_item_id", sa.UUID(), nullable=True),
    )
    op.execute(
        """
        UPDATE order_items oi
        SET inventory_item_id = (
            SELECT ii.id
            FROM inventory_items ii
            JOIN orders o ON o.id = oi.order_id
            WHERE ii.store_id = o.store_id
              AND ii.variant_id = oi.variant_id
        )
        """
    )
    op.alter_column(
        "order_items",
        "inventory_item_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.create_index(
        "ix_order_items_inventory_item_id",
        "order_items",
        ["inventory_item_id"],
        unique=False,
    )
    op.create_foreign_key(
        "order_items_inventory_item_id_fkey",
        "order_items",
        "inventory_items",
        ["inventory_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "order_items_inventory_item_id_fkey",
        "order_items",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_order_items_inventory_item_id", table_name="order_items"
    )
    op.drop_column("order_items", "inventory_item_id")

    op.drop_constraint(
        "ck_orders_idempotency_key_non_empty",
        "orders",
        type_="check",
    )
    op.drop_constraint(
        "uq_orders_store_idempotency_key", "orders", type_="unique"
    )
    op.drop_column("orders", "cancel_reason")
    op.drop_column("orders", "returned_at")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "canceled_at")
    op.drop_column("orders", "accepted_at")
    op.drop_column("orders", "idempotency_key")

    op.drop_index(
        "ix_order_audit_logs_store_id", table_name="order_audit_logs"
    )
    op.drop_index(
        "ix_order_audit_logs_performed_by_user_id",
        table_name="order_audit_logs",
    )
    op.drop_index(
        "ix_order_audit_logs_order_id", table_name="order_audit_logs"
    )
    op.drop_index(
        "ix_order_audit_logs_created_at", table_name="order_audit_logs"
    )
    op.drop_table("order_audit_logs")
