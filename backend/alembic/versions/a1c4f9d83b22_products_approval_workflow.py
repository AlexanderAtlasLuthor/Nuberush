"""products approval workflow

Adds the catalog-curation approval gate so stores can propose new
products and admins can approve or reject them.

What this migration does:

- Creates the enum `product_approval_status` with values
  `pending`, `approved`, `rejected`.
- Adds columns to `products`:
    approval_status        NOT NULL, server default `approved` so every
                           existing row is treated as already curated
                           and visible to all stores. New admin-created
                           rows default the same way; new store-proposed
                           rows are inserted as `pending` by the service
                           layer (the default never fires for them).
    proposed_by_store_id   nullable FK → stores.id ON DELETE SET NULL
    proposed_by_user_id    nullable FK → users.id  ON DELETE SET NULL
    reviewed_by_user_id    nullable FK → users.id  ON DELETE SET NULL
    reviewed_at            nullable TIMESTAMPTZ
    rejection_reason       nullable TEXT
- Adds a CHECK constraint `ck_products_rejected_iff_reason` so a
  rejected row must carry a reason and a non-rejected row must not.
- Adds indexes on `approval_status` and `proposed_by_store_id` so the
  admin pending queue and the per-store "my proposals" filter both
  hit indexed paths.

Revision ID: a1c4f9d83b22
Revises: 6c8e2b2e7ed1
Create Date: 2026-05-14 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a1c4f9d83b22"
# Chain after the orders idempotency migration so this is the single
# linear head; 5c3f52060b2f already feeds 6c8e2b2e7ed1.
down_revision = "6c8e2b2e7ed1"
branch_labels = None
depends_on = None


# Reuse the new enum on both upgrade and downgrade. create_type=False
# on the column declaration prevents SQLAlchemy from re-emitting
# CREATE TYPE when we attach the type to the column — we create it
# explicitly first.
PRODUCT_APPROVAL_STATUS = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    name="product_approval_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    PRODUCT_APPROVAL_STATUS.create(bind, checkfirst=True)

    op.add_column(
        "products",
        sa.Column(
            "approval_status",
            PRODUCT_APPROVAL_STATUS,
            server_default=sa.text("'approved'"),
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column("proposed_by_store_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("proposed_by_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "fk_products_proposed_by_store_id_stores",
        "products",
        "stores",
        ["proposed_by_store_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_products_proposed_by_user_id_users",
        "products",
        "users",
        ["proposed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_products_reviewed_by_user_id_users",
        "products",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_check_constraint(
        "ck_products_rejected_iff_reason",
        "products",
        "(approval_status = 'rejected') = (rejection_reason IS NOT NULL)",
    )

    op.create_index(
        "ix_products_approval_status",
        "products",
        ["approval_status"],
        unique=False,
    )
    op.create_index(
        "ix_products_proposed_by_store_id",
        "products",
        ["proposed_by_store_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_products_proposed_by_store_id", table_name="products")
    op.drop_index("ix_products_approval_status", table_name="products")
    op.drop_constraint(
        "ck_products_rejected_iff_reason", "products", type_="check"
    )
    op.drop_constraint(
        "fk_products_reviewed_by_user_id_users",
        "products",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_products_proposed_by_user_id_users",
        "products",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_products_proposed_by_store_id_stores",
        "products",
        type_="foreignkey",
    )
    op.drop_column("products", "rejection_reason")
    op.drop_column("products", "reviewed_at")
    op.drop_column("products", "reviewed_by_user_id")
    op.drop_column("products", "proposed_by_user_id")
    op.drop_column("products", "proposed_by_store_id")
    op.drop_column("products", "approval_status")

    bind = op.get_bind()
    PRODUCT_APPROVAL_STATUS.drop(bind, checkfirst=True)
