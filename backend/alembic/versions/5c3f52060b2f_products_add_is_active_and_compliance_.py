"""products add is_active and compliance audit log

Revision ID: 5c3f52060b2f
Revises: 7a5ba742b190
Create Date: 2026-04-27 20:29:45.272243
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '5c3f52060b2f'
down_revision = '7a5ba742b190'
branch_labels = None
depends_on = None


# Reuse the compliance_status enum that the initial migration already
# created. create_type=False tells SQLAlchemy not to emit CREATE TYPE for
# this column, otherwise the second use here would conflict with the type
# that already exists in the database.
COMPLIANCE_STATUS = postgresql.ENUM(
    "allowed",
    "restricted",
    "banned",
    name="compliance_status",
    create_type=False,
)


def upgrade() -> None:
    # New audit table for compliance state transitions.
    op.create_table(
        "product_compliance_audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column(
            "previous_compliance_status",
            COMPLIANCE_STATUS,
            nullable=False,
        ),
        sa.Column(
            "new_compliance_status",
            COMPLIANCE_STATUS,
            nullable=False,
        ),
        sa.Column("previous_allowed_for_sale", sa.Boolean(), nullable=False),
        sa.Column("new_allowed_for_sale", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason <> ''",
            name="ck_product_compliance_audit_logs_reason_non_empty",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_compliance_audit_logs_changed_by_user_id",
        "product_compliance_audit_logs",
        ["changed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_compliance_audit_logs_created_at",
        "product_compliance_audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_product_compliance_audit_logs_product_id",
        "product_compliance_audit_logs",
        ["product_id"],
        unique=False,
    )

    # New is_active flag on products. server_default=true keeps existing
    # rows valid; the column is NOT NULL.
    op.add_column(
        "products",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_products_is_active", "products", ["is_active"], unique=False
    )

    # Structural guard: a banned product cannot be allowed_for_sale.
    # Autogenerate does not detect new CHECK constraints reliably, so it
    # is added explicitly here.
    op.create_check_constraint(
        "ck_products_banned_implies_not_allowed_for_sale",
        "products",
        "compliance_status != 'banned' OR allowed_for_sale = false",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_products_banned_implies_not_allowed_for_sale",
        "products",
        type_="check",
    )
    op.drop_index("ix_products_is_active", table_name="products")
    op.drop_column("products", "is_active")
    op.drop_index(
        "ix_product_compliance_audit_logs_product_id",
        table_name="product_compliance_audit_logs",
    )
    op.drop_index(
        "ix_product_compliance_audit_logs_created_at",
        table_name="product_compliance_audit_logs",
    )
    op.drop_index(
        "ix_product_compliance_audit_logs_changed_by_user_id",
        table_name="product_compliance_audit_logs",
    )
    op.drop_table("product_compliance_audit_logs")
