"""operational audit logs storage foundation

F2.26.1.A — the persistent, append-only foundation for operational audit
events (user management + store lifecycle today; settings / regulatory
decisions in later phases). See docs/f2.26-web-app-mvp-closure-contract.md
§6.

This migration ONLY creates storage. No service writes rows yet, the unified
audit feed does not read this table, and no AuditSource / AuditEntityType
enum value references it (those land in F2.26.1.B and F2.26.2).

What this migration does:

- Creates `operational_audit_logs`, mirroring the existing per-domain
  append-only audit tables (`order_audit_logs`,
  `product_compliance_audit_logs`, `store_application_audit_logs`): a
  nullable actor FK (ON DELETE SET NULL), an append-only `created_at`, and
  no `updated_at`.
- `target_type` and `action` are `varchar`, NOT PostgreSQL enums — the same
  choice as `OrderAuditLog.action` and `StoreApplicationAuditLog.event_type`
  — so new event kinds never require an `ALTER TYPE ... ADD VALUE`.
- `store_id` is nullable: store-scoped events carry their store, global
  events leave it NULL.
- `before` / `after` / `metadata` are JSONB, matching the repo's existing
  JSONB usage (`store_application_audit_logs.payload`). The model attribute
  is `event_metadata`; the column is named `metadata`.
- Adds indexes on `created_at`, `store_id`, `actor_user_id`, and a composite
  `(target_type, target_id)`, plus non-empty CHECKs on the two varchar
  discriminators.

No PostgreSQL enum is created. No existing table is touched. No data
backfill (the table is append-only from go-live).

Revision ID: f4a7c2e9d1b8
Revises: e3b1d4c7a9f2
Create Date: 2026-06-04 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f4a7c2e9d1b8"
down_revision = "e3b1d4c7a9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_operational_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_operational_audit_logs_store_id_stores",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "target_type <> ''",
            name="ck_operational_audit_logs_target_type_non_empty",
        ),
        sa.CheckConstraint(
            "action <> ''",
            name="ck_operational_audit_logs_action_non_empty",
        ),
    )
    op.create_index(
        "ix_operational_audit_logs_created_at",
        "operational_audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operational_audit_logs_store_id",
        "operational_audit_logs",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_operational_audit_logs_actor_user_id",
        "operational_audit_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_operational_audit_logs_target",
        "operational_audit_logs",
        ["target_type", "target_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_audit_logs_target",
        table_name="operational_audit_logs",
    )
    op.drop_index(
        "ix_operational_audit_logs_actor_user_id",
        table_name="operational_audit_logs",
    )
    op.drop_index(
        "ix_operational_audit_logs_store_id",
        table_name="operational_audit_logs",
    )
    op.drop_index(
        "ix_operational_audit_logs_created_at",
        table_name="operational_audit_logs",
    )
    op.drop_table("operational_audit_logs")
