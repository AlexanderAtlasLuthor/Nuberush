"""add regulatory ingestion ledger

F2.27.7.B — the persistence foundation for regulatory source ingestion
observability. This migration ONLY lays down storage; no orchestrator,
service, schema wiring, API route, scheduler, or external fetch exists in
this subphase, and nothing here mutates a product, an alert, or a compliance
decision.

What this migration does:

- Adds NON-SECRET ingestion bookkeeping columns to `regulatory_sources`:
  `fetch_config` (JSONB), `cursor` (JSONB), `last_attempted_at`,
  `last_succeeded_at`. Secrets / credentials never live in these columns.
- Creates `regulatory_ingestion_runs`: one row per ingestion attempt against
  a source (who/when/status + rolled-up counters). `trigger` / `status` are
  `varchar` discriminators guarded by CHECK constraints (no PG enum, so new
  values never need an `ALTER TYPE`), with a `set_updated_at` trigger because
  the row is mutable (the shared `set_updated_at()` function is created by
  migration 7a5ba742b190). `actor_user_id` is nullable (ON DELETE SET NULL):
  a `scheduled` run has no human actor.
- Creates append-only `regulatory_ingestion_items`: one row per item outcome
  within a run (`created` / `deduped` / `failed`). It deliberately holds NO
  raw payload/body, secret, API key, or auth header — only `external_ref`,
  `content_hash`, and a short `error_code` / `error_message`.

Deliberately does NOT add `regulatory_notices.source_url` (deferred to a
later slice to avoid touching the existing notice read contract) and does NOT
touch any existing regulatory ingest / matching / alert behavior.

Revision ID: c1e7a9b46d52
Revises: b9d4e6a2c7f1
Create Date: 2026-06-08 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c1e7a9b46d52"
down_revision = "b9d4e6a2c7f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------- #
    # regulatory_sources — non-secret ingestion bookkeeping columns
    # ----------------------------------------------------------------- #
    op.add_column(
        "regulatory_sources",
        sa.Column("fetch_config", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "regulatory_sources",
        sa.Column("cursor", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "regulatory_sources",
        sa.Column(
            "last_attempted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "regulatory_sources",
        sa.Column(
            "last_succeeded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ----------------------------------------------------------------- #
    # regulatory_ingestion_runs (mutable — set_updated_at trigger)
    # ----------------------------------------------------------------- #
    op.create_table(
        "regulatory_ingestion_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
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
            "items_deduped",
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
        sa.Column(
            "matches_created",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "alerts_created",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["regulatory_sources.id"],
            name="fk_regulatory_ingestion_runs_source_id_regulatory_sources",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_regulatory_ingestion_runs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_regulatory_ingestion_runs_trigger_valid",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'partial')",
            name="ck_regulatory_ingestion_runs_status_valid",
        ),
        sa.CheckConstraint(
            "items_seen >= 0 AND items_created >= 0 AND items_deduped >= 0 "
            "AND items_failed >= 0 AND matches_created >= 0 "
            "AND alerts_created >= 0",
            name="ck_regulatory_ingestion_runs_counts_non_negative",
        ),
    )
    op.create_index(
        "ix_regulatory_ingestion_runs_source_id",
        "regulatory_ingestion_runs",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_runs_status",
        "regulatory_ingestion_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_runs_started_at",
        "regulatory_ingestion_runs",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_runs_created_at",
        "regulatory_ingestion_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_runs_actor_user_id",
        "regulatory_ingestion_runs",
        ["actor_user_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_regulatory_ingestion_runs_set_updated_at
        BEFORE UPDATE ON regulatory_ingestion_runs
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )

    # ----------------------------------------------------------------- #
    # regulatory_ingestion_items (append-only)
    # ----------------------------------------------------------------- #
    op.create_table(
        "regulatory_ingestion_items",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("notice_id", sa.UUID(), nullable=True),
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
            ["run_id"],
            ["regulatory_ingestion_runs.id"],
            name=(
                "fk_regulatory_ingestion_items_run_id_"
                "regulatory_ingestion_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["regulatory_notices.id"],
            name=(
                "fk_regulatory_ingestion_items_notice_id_"
                "regulatory_notices"
            ),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "outcome IN ('created', 'deduped', 'failed')",
            name="ck_regulatory_ingestion_items_outcome_valid",
        ),
    )
    op.create_index(
        "ix_regulatory_ingestion_items_run_id",
        "regulatory_ingestion_items",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_items_notice_id",
        "regulatory_ingestion_items",
        ["notice_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_items_outcome",
        "regulatory_ingestion_items",
        ["outcome"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_items_external_ref",
        "regulatory_ingestion_items",
        ["external_ref"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_ingestion_items_content_hash",
        "regulatory_ingestion_items",
        ["content_hash"],
        unique=False,
    )


def downgrade() -> None:
    # regulatory_ingestion_items (append-only) — drop indexes then table.
    op.drop_index(
        "ix_regulatory_ingestion_items_content_hash",
        table_name="regulatory_ingestion_items",
    )
    op.drop_index(
        "ix_regulatory_ingestion_items_external_ref",
        table_name="regulatory_ingestion_items",
    )
    op.drop_index(
        "ix_regulatory_ingestion_items_outcome",
        table_name="regulatory_ingestion_items",
    )
    op.drop_index(
        "ix_regulatory_ingestion_items_notice_id",
        table_name="regulatory_ingestion_items",
    )
    op.drop_index(
        "ix_regulatory_ingestion_items_run_id",
        table_name="regulatory_ingestion_items",
    )
    op.drop_table("regulatory_ingestion_items")

    # regulatory_ingestion_runs — drop trigger, indexes, then table.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_regulatory_ingestion_runs_set_updated_at "
        "ON regulatory_ingestion_runs"
    )
    op.drop_index(
        "ix_regulatory_ingestion_runs_actor_user_id",
        table_name="regulatory_ingestion_runs",
    )
    op.drop_index(
        "ix_regulatory_ingestion_runs_created_at",
        table_name="regulatory_ingestion_runs",
    )
    op.drop_index(
        "ix_regulatory_ingestion_runs_started_at",
        table_name="regulatory_ingestion_runs",
    )
    op.drop_index(
        "ix_regulatory_ingestion_runs_status",
        table_name="regulatory_ingestion_runs",
    )
    op.drop_index(
        "ix_regulatory_ingestion_runs_source_id",
        table_name="regulatory_ingestion_runs",
    )
    op.drop_table("regulatory_ingestion_runs")

    # regulatory_sources — drop the non-secret ingestion bookkeeping columns.
    op.drop_column("regulatory_sources", "last_succeeded_at")
    op.drop_column("regulatory_sources", "last_attempted_at")
    op.drop_column("regulatory_sources", "cursor")
    op.drop_column("regulatory_sources", "fetch_config")
