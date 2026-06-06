"""regulatory intelligence foundation

F2.26.5.A — the persistent, backend-first foundation for vape/ENDS
regulatory compliance signals. This migration ONLY lays down storage:
regulatory sources, imported notices/snapshots, best-effort product
matches, human-reviewable compliance alerts, and an append-only audit
trail for admin decisions on those alerts.

No ingestion service, matching engine, alert-resolution service, API
route, scheduler, external fetch, or notification exists in this subphase.
A ComplianceAlert is advisory only — nothing here blocks, holds or bans a
product, and no Product compliance/sellability column is touched. Real
compliance mutation later goes through `set_product_compliance()`.

What this migration does:

- Creates six PostgreSQL enums for the constrained domain/state columns:
  `regulatory_source_kind`, `regulatory_notice_type`,
  `regulatory_match_strategy`, `compliance_alert_severity`,
  `compliance_alert_status`, `compliance_recommended_action`. The
  decision-audit `action` is a `varchar` discriminator (NOT an enum),
  matching every other append-only audit table in this repo
  (`order_audit_logs.action`, `operational_audit_logs.action`) so new verbs
  never require an `ALTER TYPE ... ADD VALUE`.
- Creates `regulatory_sources` (with a `set_updated_at` trigger), append-only
  `regulatory_notices` (unique on `(source_id, content_hash)` for dedupe),
  `regulatory_product_matches` (confidence bounded 0.00–1.00, dedupe on
  `(notice_id, product_id, variant_id, match_strategy)`), `compliance_alerts`
  (with a `set_updated_at` trigger and a resolved-pair CHECK), and append-only
  `regulatory_decision_audit_logs` (REQUIRED actor with ON DELETE RESTRICT).

Deliberately does NOT extend `operational_audit_logs`: regulatory decisions
get their own dedicated table. `set_updated_at()` is created by migration
7a5ba742b190.

Revision ID: a8c1f5e2d934
Revises: f4a7c2e9d1b8
Create Date: 2026-06-05 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a8c1f5e2d934"
down_revision = "f4a7c2e9d1b8"
branch_labels = None
depends_on = None


# create_type=False keeps SQLAlchemy from re-emitting CREATE TYPE when the
# type is attached to a column — each enum is created explicitly first.
REGULATORY_SOURCE_KIND = postgresql.ENUM(
    "fda_pmta",
    "fda_enforcement",
    "fda_advisory",
    "retailer_guidance",
    "manual",
    name="regulatory_source_kind",
    create_type=False,
)
REGULATORY_NOTICE_TYPE = postgresql.ENUM(
    "authorized_product_list",
    "enforcement_notice",
    "advisory",
    "retailer_guidance",
    "manual_snapshot",
    name="regulatory_notice_type",
    create_type=False,
)
REGULATORY_MATCH_STRATEGY = postgresql.ENUM(
    "name",
    "brand",
    "category",
    "sku",
    "barcode",
    "flavor",
    "manual",
    name="regulatory_match_strategy",
    create_type=False,
)
COMPLIANCE_ALERT_SEVERITY = postgresql.ENUM(
    "low",
    "medium",
    "high",
    "critical",
    name="compliance_alert_severity",
    create_type=False,
)
COMPLIANCE_ALERT_STATUS = postgresql.ENUM(
    "open",
    "acknowledged",
    "actioned",
    "dismissed",
    name="compliance_alert_status",
    create_type=False,
)
COMPLIANCE_RECOMMENDED_ACTION = postgresql.ENUM(
    "none",
    "hold",
    "ban",
    name="compliance_recommended_action",
    create_type=False,
)

_ALL_ENUMS = (
    REGULATORY_SOURCE_KIND,
    REGULATORY_NOTICE_TYPE,
    REGULATORY_MATCH_STRATEGY,
    COMPLIANCE_ALERT_SEVERITY,
    COMPLIANCE_ALERT_STATUS,
    COMPLIANCE_RECOMMENDED_ACTION,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in _ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    # ----------------------------------------------------------------- #
    # regulatory_sources
    # ----------------------------------------------------------------- #
    op.create_table(
        "regulatory_sources",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("kind", REGULATORY_SOURCE_KIND, nullable=False),
        sa.Column("reference_url", sa.String(length=500), nullable=True),
        sa.Column(
            "is_active",
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
        sa.UniqueConstraint("name", name="uq_regulatory_sources_name"),
        sa.CheckConstraint(
            "name <> ''", name="ck_regulatory_sources_name_non_empty"
        ),
    )
    op.create_index(
        "ix_regulatory_sources_kind",
        "regulatory_sources",
        ["kind"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_sources_is_active",
        "regulatory_sources",
        ["is_active"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_regulatory_sources_set_updated_at
        BEFORE UPDATE ON regulatory_sources
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )

    # ----------------------------------------------------------------- #
    # regulatory_notices (append-only)
    # ----------------------------------------------------------------- #
    op.create_table(
        "regulatory_notices",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("notice_type", REGULATORY_NOTICE_TYPE, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["regulatory_sources.id"],
            name="fk_regulatory_notices_source_id_regulatory_sources",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "source_id",
            "content_hash",
            name="uq_regulatory_notices_source_content_hash",
        ),
        sa.CheckConstraint(
            "title <> ''", name="ck_regulatory_notices_title_non_empty"
        ),
        sa.CheckConstraint(
            "content_hash <> ''",
            name="ck_regulatory_notices_content_hash_non_empty",
        ),
    )
    op.create_index(
        "ix_regulatory_notices_source_id",
        "regulatory_notices",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_notices_notice_type",
        "regulatory_notices",
        ["notice_type"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_notices_published_at",
        "regulatory_notices",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_notices_content_hash",
        "regulatory_notices",
        ["content_hash"],
        unique=False,
    )

    # ----------------------------------------------------------------- #
    # regulatory_product_matches (append-only)
    # ----------------------------------------------------------------- #
    op.create_table(
        "regulatory_product_matches",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("notice_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column(
            "match_strategy", REGULATORY_MATCH_STRATEGY, nullable=False
        ),
        sa.Column(
            "confidence", sa.Numeric(precision=3, scale=2), nullable=False
        ),
        sa.Column("matched_fields", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["regulatory_notices.id"],
            name="fk_regulatory_product_matches_notice_id_regulatory_notices",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_regulatory_product_matches_product_id_products",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name="fk_regulatory_product_matches_variant_id_product_variants",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "notice_id",
            "product_id",
            "variant_id",
            "match_strategy",
            name="uq_regulatory_product_matches_dedupe",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_regulatory_product_matches_confidence_range",
        ),
    )
    op.create_index(
        "ix_regulatory_product_matches_notice_id",
        "regulatory_product_matches",
        ["notice_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_product_matches_product_id",
        "regulatory_product_matches",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_product_matches_variant_id",
        "regulatory_product_matches",
        ["variant_id"],
        unique=False,
    )

    # ----------------------------------------------------------------- #
    # compliance_alerts
    # ----------------------------------------------------------------- #
    op.create_table(
        "compliance_alerts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("notice_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("match_id", sa.UUID(), nullable=True),
        sa.Column("severity", COMPLIANCE_ALERT_SEVERITY, nullable=False),
        sa.Column(
            "status",
            COMPLIANCE_ALERT_STATUS,
            server_default=sa.text("'open'"),
            nullable=False,
        ),
        sa.Column(
            "recommended_action",
            COMPLIANCE_RECOMMENDED_ACTION,
            server_default=sa.text("'none'"),
            nullable=False,
        ),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            ["notice_id"],
            ["regulatory_notices.id"],
            name="fk_compliance_alerts_notice_id_regulatory_notices",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_compliance_alerts_product_id_products",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["regulatory_product_matches.id"],
            name="fk_compliance_alerts_match_id_regulatory_product_matches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name="fk_compliance_alerts_resolved_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "(resolved_at IS NULL) = (resolved_by_user_id IS NULL)",
            name="ck_compliance_alerts_resolution_pair_consistent",
        ),
    )
    op.create_index(
        "ix_compliance_alerts_status",
        "compliance_alerts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_alerts_severity",
        "compliance_alerts",
        ["severity"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_alerts_created_at",
        "compliance_alerts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_alerts_notice_id",
        "compliance_alerts",
        ["notice_id"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_alerts_product_id",
        "compliance_alerts",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_alerts_match_id",
        "compliance_alerts",
        ["match_id"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_alerts_resolved_by_user_id",
        "compliance_alerts",
        ["resolved_by_user_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_compliance_alerts_set_updated_at
        BEFORE UPDATE ON compliance_alerts
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )

    # ----------------------------------------------------------------- #
    # regulatory_decision_audit_logs (append-only)
    # ----------------------------------------------------------------- #
    op.create_table(
        "regulatory_decision_audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("alert_id", sa.UUID(), nullable=False),
        sa.Column("notice_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["compliance_alerts.id"],
            name="fk_regulatory_decision_audit_logs_alert_id_compliance_alerts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["regulatory_notices.id"],
            name=(
                "fk_regulatory_decision_audit_logs_notice_id_"
                "regulatory_notices"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_regulatory_decision_audit_logs_product_id_products",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_regulatory_decision_audit_logs_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action <> ''",
            name="ck_regulatory_decision_audit_logs_action_non_empty",
        ),
        sa.CheckConstraint(
            "reason <> ''",
            name="ck_regulatory_decision_audit_logs_reason_non_empty",
        ),
    )
    op.create_index(
        "ix_regulatory_decision_audit_logs_alert_id",
        "regulatory_decision_audit_logs",
        ["alert_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_decision_audit_logs_notice_id",
        "regulatory_decision_audit_logs",
        ["notice_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_decision_audit_logs_product_id",
        "regulatory_decision_audit_logs",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_decision_audit_logs_actor_user_id",
        "regulatory_decision_audit_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_decision_audit_logs_created_at",
        "regulatory_decision_audit_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regulatory_decision_audit_logs_created_at",
        table_name="regulatory_decision_audit_logs",
    )
    op.drop_index(
        "ix_regulatory_decision_audit_logs_actor_user_id",
        table_name="regulatory_decision_audit_logs",
    )
    op.drop_index(
        "ix_regulatory_decision_audit_logs_product_id",
        table_name="regulatory_decision_audit_logs",
    )
    op.drop_index(
        "ix_regulatory_decision_audit_logs_notice_id",
        table_name="regulatory_decision_audit_logs",
    )
    op.drop_index(
        "ix_regulatory_decision_audit_logs_alert_id",
        table_name="regulatory_decision_audit_logs",
    )
    op.drop_table("regulatory_decision_audit_logs")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_compliance_alerts_set_updated_at "
        "ON compliance_alerts"
    )
    op.drop_index(
        "ix_compliance_alerts_resolved_by_user_id",
        table_name="compliance_alerts",
    )
    op.drop_index(
        "ix_compliance_alerts_match_id", table_name="compliance_alerts"
    )
    op.drop_index(
        "ix_compliance_alerts_product_id", table_name="compliance_alerts"
    )
    op.drop_index(
        "ix_compliance_alerts_notice_id", table_name="compliance_alerts"
    )
    op.drop_index(
        "ix_compliance_alerts_created_at", table_name="compliance_alerts"
    )
    op.drop_index(
        "ix_compliance_alerts_severity", table_name="compliance_alerts"
    )
    op.drop_index(
        "ix_compliance_alerts_status", table_name="compliance_alerts"
    )
    op.drop_table("compliance_alerts")

    op.drop_index(
        "ix_regulatory_product_matches_variant_id",
        table_name="regulatory_product_matches",
    )
    op.drop_index(
        "ix_regulatory_product_matches_product_id",
        table_name="regulatory_product_matches",
    )
    op.drop_index(
        "ix_regulatory_product_matches_notice_id",
        table_name="regulatory_product_matches",
    )
    op.drop_table("regulatory_product_matches")

    op.drop_index(
        "ix_regulatory_notices_content_hash",
        table_name="regulatory_notices",
    )
    op.drop_index(
        "ix_regulatory_notices_published_at",
        table_name="regulatory_notices",
    )
    op.drop_index(
        "ix_regulatory_notices_notice_type",
        table_name="regulatory_notices",
    )
    op.drop_index(
        "ix_regulatory_notices_source_id",
        table_name="regulatory_notices",
    )
    op.drop_table("regulatory_notices")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_regulatory_sources_set_updated_at "
        "ON regulatory_sources"
    )
    op.drop_index(
        "ix_regulatory_sources_is_active", table_name="regulatory_sources"
    )
    op.drop_index(
        "ix_regulatory_sources_kind", table_name="regulatory_sources"
    )
    op.drop_table("regulatory_sources")

    bind = op.get_bind()
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(bind, checkfirst=True)
