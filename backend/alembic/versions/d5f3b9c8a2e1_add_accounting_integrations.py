"""add accounting integrations

F2.27.9.A — the storage/foundation for the QuickBooks (accounting) inventory
connection. This migration ONLY lays down storage; no OAuth flow, QuickBooks
client, mapping service, sync orchestrator, scheduler, route, or external call
exists in this subphase, and nothing here mutates inventory, products, or
compliance. NubeRush stays authoritative for inventory; QuickBooks mirrors it.

What this migration creates:

- `store_accounting_integrations`: one row per (store, provider) holding the
  connection lifecycle `status`, the `environment`, the Intuit `realm_id`, and
  the OAuth tokens — stored ENCRYPTED AT REST ONLY (`access_token_encrypted` /
  `refresh_token_encrypted`, Fernet ciphertext). UNIQUE(store_id, provider).
  `provider` / `status` / `environment` are `varchar` discriminators guarded by
  CHECK constraints (no PG enum). Mutable, so it gets a `set_updated_at` trigger
  (the shared `set_updated_at()` function is created by migration 7a5ba742b190).
- `product_variant_accounting_mappings`: a 1:1 variant <-> external-item link,
  with UNIQUE(integration_id, variant_id) and UNIQUE(integration_id,
  external_item_id). Mutable -> `set_updated_at` trigger.
- `accounting_sync_logs`: append-only ledger header for a sync run
  (`sync_type` / `direction` / `status` / `trigger` varchar discriminators,
  counters defaulting to 0, redacted-only `error_summary`).
- `accounting_sync_log_items`: append-only per-item outcome
  (`created` / `updated` / `skipped` / `failed`). Holds NO raw payload/body,
  secret, token, or auth header.

Token-bearing tables are additionally protected by a Supabase deny-all
FORCE-RLS migration (supabase/migrations/...); this Alembic revision owns the
schema only. There is deliberately NO plaintext token, client secret,
authorization header, or raw QuickBooks payload column anywhere here.

Revision ID: d5f3b9c8a2e1
Revises: c1e7a9b46d52
Create Date: 2026-06-09 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d5f3b9c8a2e1"
down_revision = "c1e7a9b46d52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------- #
    # store_accounting_integrations (mutable — set_updated_at trigger)
    # ----------------------------------------------------------------- #
    op.create_table(
        "store_accounting_integrations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=20),
            server_default=sa.text("'quickbooks'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'disconnected'"),
            nullable=False,
        ),
        sa.Column(
            "environment",
            sa.String(length=20),
            server_default=sa.text("'sandbox'"),
            nullable=False,
        ),
        sa.Column("realm_id", sa.String(length=64), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "access_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "refresh_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("connected_by_user_id", sa.UUID(), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
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
            ["store_id"],
            ["stores.id"],
            name="fk_store_accounting_integrations_store_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connected_by_user_id"],
            ["users.id"],
            name="fk_store_accounting_integrations_connected_by_user_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "store_id",
            "provider",
            name="uq_store_accounting_integrations_store_provider",
        ),
        sa.CheckConstraint(
            "provider IN ('quickbooks')",
            name="ck_store_accounting_integrations_provider_valid",
        ),
        sa.CheckConstraint(
            "status IN ('connected', 'disconnected', 'expired', 'error')",
            name="ck_store_accounting_integrations_status_valid",
        ),
        sa.CheckConstraint(
            "environment IN ('sandbox', 'production')",
            name="ck_store_accounting_integrations_environment_valid",
        ),
    )
    op.create_index(
        "ix_store_accounting_integrations_store_id",
        "store_accounting_integrations",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_accounting_integrations_status",
        "store_accounting_integrations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_store_accounting_integrations_connected_by_user_id",
        "store_accounting_integrations",
        ["connected_by_user_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_store_accounting_integrations_set_updated_at
        BEFORE UPDATE ON store_accounting_integrations
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )

    # ----------------------------------------------------------------- #
    # product_variant_accounting_mappings (mutable — set_updated_at trigger)
    # ----------------------------------------------------------------- #
    op.create_table(
        "product_variant_accounting_mappings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("integration_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=20),
            server_default=sa.text("'quickbooks'"),
            nullable=False,
        ),
        sa.Column("external_item_id", sa.String(length=255), nullable=False),
        sa.Column("external_item_name", sa.String(length=255), nullable=True),
        sa.Column(
            "sync_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
            ["integration_id"],
            ["store_accounting_integrations.id"],
            name="fk_product_variant_accounting_mappings_integration_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_product_variant_accounting_mappings_store_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name="fk_product_variant_accounting_mappings_variant_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "integration_id",
            "variant_id",
            name="uq_product_variant_accounting_mappings_integration_variant",
        ),
        sa.UniqueConstraint(
            "integration_id",
            "external_item_id",
            name="uq_product_variant_accounting_mappings_integration_external",
        ),
        sa.CheckConstraint(
            "provider IN ('quickbooks')",
            name="ck_product_variant_accounting_mappings_provider_valid",
        ),
    )
    op.create_index(
        "ix_product_variant_accounting_mappings_integration_id",
        "product_variant_accounting_mappings",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_variant_accounting_mappings_variant_id",
        "product_variant_accounting_mappings",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_variant_accounting_mappings_store_id",
        "product_variant_accounting_mappings",
        ["store_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_product_variant_accounting_mappings_set_updated_at
        BEFORE UPDATE ON product_variant_accounting_mappings
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )

    # ----------------------------------------------------------------- #
    # accounting_sync_logs (append-only ledger header)
    # ----------------------------------------------------------------- #
    op.create_table(
        "accounting_sync_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("integration_id", sa.UUID(), nullable=False),
        sa.Column("sync_type", sa.String(length=20), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "items_seen",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_created",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_updated",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_skipped",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_failed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_accounting_sync_logs_store_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"],
            ["store_accounting_integrations.id"],
            name="fk_accounting_sync_logs_integration_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_accounting_sync_logs_actor_user_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "sync_type IN ('item_discovery', 'mapping_pull', 'inventory_push')",
            name="ck_accounting_sync_logs_sync_type_valid",
        ),
        sa.CheckConstraint(
            "direction IN ('pull', 'push')",
            name="ck_accounting_sync_logs_direction_valid",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'partial')",
            name="ck_accounting_sync_logs_status_valid",
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_accounting_sync_logs_trigger_valid",
        ),
        sa.CheckConstraint(
            "items_seen >= 0 AND items_created >= 0 AND items_updated >= 0 "
            "AND items_skipped >= 0 AND items_failed >= 0",
            name="ck_accounting_sync_logs_counts_non_negative",
        ),
    )
    op.create_index(
        "ix_accounting_sync_logs_store_id",
        "accounting_sync_logs",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_sync_logs_integration_id",
        "accounting_sync_logs",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_sync_logs_status",
        "accounting_sync_logs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_sync_logs_started_at",
        "accounting_sync_logs",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_sync_logs_created_at",
        "accounting_sync_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_sync_logs_actor_user_id",
        "accounting_sync_logs",
        ["actor_user_id"],
        unique=False,
    )

    # ----------------------------------------------------------------- #
    # accounting_sync_log_items (append-only per-item outcome)
    # ----------------------------------------------------------------- #
    op.create_table(
        "accounting_sync_log_items",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("sync_log_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("external_item_id", sa.String(length=255), nullable=True),
        sa.Column("external_item_name", sa.String(length=255), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["sync_log_id"],
            ["accounting_sync_logs.id"],
            name="fk_accounting_sync_log_items_sync_log_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name="fk_accounting_sync_log_items_variant_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "outcome IN ('created', 'updated', 'skipped', 'failed')",
            name="ck_accounting_sync_log_items_outcome_valid",
        ),
    )
    op.create_index(
        "ix_accounting_sync_log_items_sync_log_id",
        "accounting_sync_log_items",
        ["sync_log_id"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_sync_log_items_variant_id",
        "accounting_sync_log_items",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_sync_log_items_outcome",
        "accounting_sync_log_items",
        ["outcome"],
        unique=False,
    )


def downgrade() -> None:
    # accounting_sync_log_items (append-only) — drop indexes then table.
    op.drop_index(
        "ix_accounting_sync_log_items_outcome",
        table_name="accounting_sync_log_items",
    )
    op.drop_index(
        "ix_accounting_sync_log_items_variant_id",
        table_name="accounting_sync_log_items",
    )
    op.drop_index(
        "ix_accounting_sync_log_items_sync_log_id",
        table_name="accounting_sync_log_items",
    )
    op.drop_table("accounting_sync_log_items")

    # accounting_sync_logs (append-only) — drop indexes then table.
    op.drop_index(
        "ix_accounting_sync_logs_actor_user_id",
        table_name="accounting_sync_logs",
    )
    op.drop_index(
        "ix_accounting_sync_logs_created_at",
        table_name="accounting_sync_logs",
    )
    op.drop_index(
        "ix_accounting_sync_logs_started_at",
        table_name="accounting_sync_logs",
    )
    op.drop_index(
        "ix_accounting_sync_logs_status",
        table_name="accounting_sync_logs",
    )
    op.drop_index(
        "ix_accounting_sync_logs_integration_id",
        table_name="accounting_sync_logs",
    )
    op.drop_index(
        "ix_accounting_sync_logs_store_id",
        table_name="accounting_sync_logs",
    )
    op.drop_table("accounting_sync_logs")

    # product_variant_accounting_mappings — drop trigger, indexes, then table.
    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_product_variant_accounting_mappings_set_updated_at "
        "ON product_variant_accounting_mappings"
    )
    op.drop_index(
        "ix_product_variant_accounting_mappings_store_id",
        table_name="product_variant_accounting_mappings",
    )
    op.drop_index(
        "ix_product_variant_accounting_mappings_variant_id",
        table_name="product_variant_accounting_mappings",
    )
    op.drop_index(
        "ix_product_variant_accounting_mappings_integration_id",
        table_name="product_variant_accounting_mappings",
    )
    op.drop_table("product_variant_accounting_mappings")

    # store_accounting_integrations — drop trigger, indexes, then table.
    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_store_accounting_integrations_set_updated_at "
        "ON store_accounting_integrations"
    )
    op.drop_index(
        "ix_store_accounting_integrations_connected_by_user_id",
        table_name="store_accounting_integrations",
    )
    op.drop_index(
        "ix_store_accounting_integrations_status",
        table_name="store_accounting_integrations",
    )
    op.drop_index(
        "ix_store_accounting_integrations_store_id",
        table_name="store_accounting_integrations",
    )
    op.drop_table("store_accounting_integrations")
