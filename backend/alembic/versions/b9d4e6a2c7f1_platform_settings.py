"""platform settings persistence foundation

F2.27.10.A — the persistent, backend-first foundation for the writable
Admin Settings surface. This migration ONLY lays down storage:

- `platform_settings`: a singleton platform-wide configuration row
  (singleton-ness is enforced by a later service layer, not the DB). This
  migration does NOT insert that row and does NOT seed defaults — the
  get-or-create lands in a later subphase.
- `platform_settings_audit_logs`: an append-only audit trail for settings
  mutations. Dedicated table — deliberately NOT `operational_audit_logs` and
  NOT wired into the unified Admin Audit feed.

No service, schema, API route, writer/helper, or feed integration exists in
this subphase. Secrets / env-backed config (Supabase / email / database /
CORS) never live in these tables.

What this migration does:

- Creates `platform_settings` with column server defaults
  (`platform_name='NubeRush'`, `default_locale='en-US'`,
  `default_timezone='America/New_York'`), non-empty CHECKs on the three
  required text columns, and a `set_updated_at` trigger (the shared
  `set_updated_at()` function is created by migration 7a5ba742b190).
- Creates append-only `platform_settings_audit_logs` with REQUIRED FKs
  (`platform_settings_id` ON DELETE CASCADE, `actor_user_id` ON DELETE
  RESTRICT), a non-empty CHECK on `action`, JSONB `before`/`after`, and the
  three minimal indexes (`platform_settings_id`, `actor_user_id`,
  `created_at`).

Deliberately does NOT touch `operational_audit_logs`, `audit` feed mapping,
RLS, or any existing table.

Revision ID: b9d4e6a2c7f1
Revises: a8c1f5e2d934
Create Date: 2026-06-08 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b9d4e6a2c7f1"
down_revision = "a8c1f5e2d934"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------- #
    # platform_settings (singleton — not seeded here)
    # ----------------------------------------------------------------- #
    op.create_table(
        "platform_settings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "platform_name",
            sa.String(length=150),
            server_default=sa.text("'NubeRush'"),
            nullable=False,
        ),
        sa.Column("support_email", sa.String(length=255), nullable=True),
        sa.Column(
            "default_locale",
            sa.String(length=10),
            server_default=sa.text("'en-US'"),
            nullable=False,
        ),
        sa.Column(
            "default_timezone",
            sa.String(length=50),
            server_default=sa.text("'America/New_York'"),
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
        sa.CheckConstraint(
            "platform_name <> ''",
            name="ck_platform_settings_platform_name_non_empty",
        ),
        sa.CheckConstraint(
            "default_locale <> ''",
            name="ck_platform_settings_default_locale_non_empty",
        ),
        sa.CheckConstraint(
            "default_timezone <> ''",
            name="ck_platform_settings_default_timezone_non_empty",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER trg_platform_settings_set_updated_at
        BEFORE UPDATE ON platform_settings
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )

    # ----------------------------------------------------------------- #
    # platform_settings_audit_logs (append-only)
    # ----------------------------------------------------------------- #
    op.create_table(
        "platform_settings_audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("platform_settings_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=False),
        sa.Column("after", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["platform_settings_id"],
            ["platform_settings.id"],
            name="fk_platform_settings_audit_logs_settings_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_platform_settings_audit_logs_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action <> ''",
            name="ck_platform_settings_audit_logs_action_non_empty",
        ),
    )
    op.create_index(
        "ix_platform_settings_audit_logs_platform_settings_id",
        "platform_settings_audit_logs",
        ["platform_settings_id"],
        unique=False,
    )
    op.create_index(
        "ix_platform_settings_audit_logs_actor_user_id",
        "platform_settings_audit_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_platform_settings_audit_logs_created_at",
        "platform_settings_audit_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_settings_audit_logs_created_at",
        table_name="platform_settings_audit_logs",
    )
    op.drop_index(
        "ix_platform_settings_audit_logs_actor_user_id",
        table_name="platform_settings_audit_logs",
    )
    op.drop_index(
        "ix_platform_settings_audit_logs_platform_settings_id",
        table_name="platform_settings_audit_logs",
    )
    op.drop_table("platform_settings_audit_logs")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_platform_settings_set_updated_at "
        "ON platform_settings"
    )
    op.drop_table("platform_settings")
