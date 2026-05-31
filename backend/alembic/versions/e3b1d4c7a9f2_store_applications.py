"""store applications data-layer foundation

F2.24.C1 — the persistent foundation for professional store sign-up /
merchant onboarding. This migration ONLY lays down inert data structures;
no submit / approve / reject service exists yet (those land in later
subphases), so nothing here ever provisions a store, a user, or a Supabase
Auth record.

What this migration does:

- Creates the enum `store_application_status` with values
  `draft`, `submitted`, `pending_review`, `approved`, `rejected`. Only the
  last three are operational in F2.24; the first two exist for extensibility.
- Creates `store_applications`, the merchant application table, with the
  Uber-Eats-style benchmark fields (business + owner + address + operational
  profile), terms acceptance, review fields, provisioning links and an
  opaque public lookup token. `status` defaults to `draft` at the DB layer;
  the intake service (C2) sets the operational status explicitly.
- Adds CHECK constraints that keep a row honest:
    * rejected ⇔ rejection_reason set;
    * approved ⇔ provisioned_store_id set;
    * approved ⇔ provisioned_owner_user_id set
      (so a non-approved row — including pending_review — never carries a
       provisioning link);
    * terms_accepted ⇒ terms_accepted_at set;
    * non-empty business_name / business_type / owner_full_name /
      owner_email;
    * location_count > 0; estimated_weekly_orders ≥ 0 when present.
- Adds indexes on status, owner_email, submitted_at, a UNIQUE index on
  public_lookup_token, and on the three FK columns.
- Creates `store_application_audit_logs`, an append-only audit trail that
  mirrors the existing per-domain audit tables (`order_audit_logs`,
  `product_compliance_audit_logs`). No service writes rows in C1.
- Adds a `set_updated_at` trigger on `store_applications` (the audit table
  is append-only and has no updated_at).

Schema authority stays in Alembic. The matching Supabase RLS deny-all
coverage for these two tables lands in a sibling `supabase/migrations/`
SQL file, following the F2.22.4.E pattern.

Revision ID: e3b1d4c7a9f2
Revises: d2f9e8a7c1b6
Create Date: 2026-05-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e3b1d4c7a9f2"
down_revision = "d2f9e8a7c1b6"
branch_labels = None
depends_on = None


# create_type=False keeps SQLAlchemy from re-emitting CREATE TYPE when the
# type is attached to the column — the enum is created explicitly first.
STORE_APPLICATION_STATUS = postgresql.ENUM(
    "draft",
    "submitted",
    "pending_review",
    "approved",
    "rejected",
    name="store_application_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    STORE_APPLICATION_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "store_applications",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Business / store details.
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("business_type", sa.String(length=100), nullable=False),
        # Owner / contact details.
        sa.Column("owner_full_name", sa.String(length=150), nullable=False),
        sa.Column("owner_email", sa.String(length=255), nullable=False),
        sa.Column("owner_phone", sa.String(length=30), nullable=False),
        sa.Column("business_phone", sa.String(length=30), nullable=True),
        # Address.
        sa.Column("address_line_1", sa.String(length=200), nullable=False),
        sa.Column("address_line_2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column(
            "country",
            sa.String(length=2),
            server_default=sa.text("'US'"),
            nullable=False,
        ),
        # Operational profile.
        sa.Column(
            "location_count",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("estimated_weekly_orders", sa.Integer(), nullable=True),
        sa.Column("hours_of_operation", sa.Text(), nullable=True),
        sa.Column("website_url", sa.String(length=255), nullable=True),
        sa.Column("social_url", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Terms.
        sa.Column(
            "terms_accepted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "terms_accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Lifecycle / review.
        sa.Column(
            "status",
            STORE_APPLICATION_STATUS,
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # Provisioning links (populated only on approval, later subphase).
        sa.Column("provisioned_store_id", sa.UUID(), nullable=True),
        sa.Column("provisioned_owner_user_id", sa.UUID(), nullable=True),
        # Public status-lookup token. No server-side default: the token is
        # generated Python-side by the model (uuid4 hex) on every ORM
        # insert. Keeping the column free of a server_default keeps the
        # model and DB in lockstep for `alembic check`.
        sa.Column(
            "public_lookup_token",
            sa.String(length=64),
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
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name="fk_store_applications_reviewed_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["provisioned_store_id"],
            ["stores.id"],
            name="fk_store_applications_provisioned_store_id_stores",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["provisioned_owner_user_id"],
            ["users.id"],
            name="fk_store_applications_provisioned_owner_user_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "business_name <> ''",
            name="ck_store_applications_business_name_non_empty",
        ),
        sa.CheckConstraint(
            "business_type <> ''",
            name="ck_store_applications_business_type_non_empty",
        ),
        sa.CheckConstraint(
            "owner_full_name <> ''",
            name="ck_store_applications_owner_full_name_non_empty",
        ),
        sa.CheckConstraint(
            "owner_email <> ''",
            name="ck_store_applications_owner_email_non_empty",
        ),
        sa.CheckConstraint(
            "location_count > 0",
            name="ck_store_applications_location_count_positive",
        ),
        sa.CheckConstraint(
            "estimated_weekly_orders IS NULL OR estimated_weekly_orders >= 0",
            name="ck_store_applications_estimated_weekly_orders_non_negative",
        ),
        sa.CheckConstraint(
            "(status = 'rejected') = (rejection_reason IS NOT NULL)",
            name="ck_store_applications_rejected_iff_reason",
        ),
        sa.CheckConstraint(
            "(status = 'approved') = (provisioned_store_id IS NOT NULL)",
            name="ck_store_applications_approved_iff_store",
        ),
        sa.CheckConstraint(
            "(status = 'approved') = (provisioned_owner_user_id IS NOT NULL)",
            name="ck_store_applications_approved_iff_owner",
        ),
        sa.CheckConstraint(
            "terms_accepted = false OR terms_accepted_at IS NOT NULL",
            name="ck_store_applications_terms_accepted_requires_timestamp",
        ),
    )
    op.create_index(
        "ix_store_applications_status",
        "store_applications",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_store_applications_owner_email",
        "store_applications",
        ["owner_email"],
        unique=False,
    )
    op.create_index(
        "ix_store_applications_submitted_at",
        "store_applications",
        ["submitted_at"],
        unique=False,
    )
    op.create_index(
        "ix_store_applications_public_lookup_token",
        "store_applications",
        ["public_lookup_token"],
        unique=True,
    )
    op.create_index(
        "ix_store_applications_reviewed_by_user_id",
        "store_applications",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_applications_provisioned_store_id",
        "store_applications",
        ["provisioned_store_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_applications_provisioned_owner_user_id",
        "store_applications",
        ["provisioned_owner_user_id"],
        unique=False,
    )
    # Partial unique index backing the public-intake dedup rule (F2.24.C2):
    # at most one ACTIVE (non-rejected) application per owner_email. Closes
    # the query-then-insert race on the unauthenticated endpoint.
    op.create_index(
        "uq_store_applications_active_owner_email",
        "store_applications",
        ["owner_email"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('draft', 'submitted', 'pending_review', 'approved')"
        ),
    )

    # Keep updated_at fresh on UPDATE, matching every other timestamped
    # table. set_updated_at() is created by migration 7a5ba742b190.
    op.execute(
        """
        CREATE TRIGGER trg_store_applications_set_updated_at
        BEFORE UPDATE ON store_applications
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )

    op.create_table(
        "store_application_audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["store_applications.id"],
            name="fk_store_app_audit_logs_application_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_store_application_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "event_type <> ''",
            name="ck_store_application_audit_logs_event_type_non_empty",
        ),
    )
    op.create_index(
        "ix_store_application_audit_logs_application_id",
        "store_application_audit_logs",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_application_audit_logs_actor_user_id",
        "store_application_audit_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_store_application_audit_logs_created_at",
        "store_application_audit_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_store_application_audit_logs_created_at",
        table_name="store_application_audit_logs",
    )
    op.drop_index(
        "ix_store_application_audit_logs_actor_user_id",
        table_name="store_application_audit_logs",
    )
    op.drop_index(
        "ix_store_application_audit_logs_application_id",
        table_name="store_application_audit_logs",
    )
    op.drop_table("store_application_audit_logs")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_store_applications_set_updated_at "
        "ON store_applications"
    )
    op.drop_index(
        "uq_store_applications_active_owner_email",
        table_name="store_applications",
    )
    op.drop_index(
        "ix_store_applications_provisioned_owner_user_id",
        table_name="store_applications",
    )
    op.drop_index(
        "ix_store_applications_provisioned_store_id",
        table_name="store_applications",
    )
    op.drop_index(
        "ix_store_applications_reviewed_by_user_id",
        table_name="store_applications",
    )
    op.drop_index(
        "ix_store_applications_public_lookup_token",
        table_name="store_applications",
    )
    op.drop_index(
        "ix_store_applications_submitted_at",
        table_name="store_applications",
    )
    op.drop_index(
        "ix_store_applications_owner_email",
        table_name="store_applications",
    )
    op.drop_index(
        "ix_store_applications_status",
        table_name="store_applications",
    )
    op.drop_table("store_applications")

    bind = op.get_bind()
    STORE_APPLICATION_STATUS.drop(bind, checkfirst=True)
