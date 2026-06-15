"""create driver delivery compliance tables

Dr.1.2.B — Driver Compliance Models + Migration Foundation. This migration
ONLY lays down storage for the four driver compliance records that the
Dr.1.2.C–H action subphases will later populate:

- `driver_delivery_verifications`: delivery-time 21+ / age verification result
  (append-only per assignment; NO UNIQUE(assignment_id)).
- `driver_delivery_proofs`: redaction-safe proof-of-delivery metadata
  (append-only per assignment; NO UNIQUE(assignment_id)).
- `driver_delivery_failures`: structured failed-delivery record
  (append-only per assignment; NO UNIQUE(assignment_id)).
- `driver_delivery_returns`: return-to-store custody/confirmation record
  (1:1 per assignment; UNIQUE(assignment_id)).

Every enum-like column is a VARCHAR + CHECK over the frozen Dr.1.2 vocabulary
(no PostgreSQL enum, so new outcomes / reason codes never need an `ALTER
TYPE`). FK semantics mirror `driver_delivery_operational_states`: assignment /
order / store CASCADE, driver_profile RESTRICT (preserve driver history), every
actor `*_by_user_id` SET NULL. `order_id` / `driver_profile_id` / `store_id`
are denormalized read anchors for future self-scoped, store-bound reads — never
a license to mutate the order. Mutable tables get the shared `set_updated_at`
trigger (the `set_updated_at()` function is created by migration 7a5ba742b190).

Per the Dr.1.2 contract redaction policy, these tables hold ONLY redaction-safe
metadata, boolean checklist flags, reason codes, safe notes, timestamps, and
association IDs — never a raw ID image, full ID number, OCR/barcode payload,
biometric data, signature, customer photo, or any artifact path/URL.

Deliberately NOT here: any service, schema, route, or transition logic; the
`Order.status` bridge; any change to `order_status` / `orders` / `inventory_*`
/ `order_driver_assignments` / `driver_delivery_operational_states`; the
idempotency ledger; and the compliance audit sink (both deferred to Dr.1.2.I).

Revision ID: c3d7f1a9e2b4
Revises: 9e15cd2f6a7a
Create Date: 2026-06-15 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d7f1a9e2b4"
down_revision = "9e15cd2f6a7a"
branch_labels = None
depends_on = None


_VERIFICATION_OUTCOMES = "'pass', 'fail', 'manual_review'"
_VERIFICATION_FAILURE_REASONS = (
    "'customer_underage', 'id_invalid', 'id_expired', 'id_not_available', "
    "'customer_refused', 'manual_review_required', 'other_manual_review'"
)
_METHODS = "'manual_checklist'"
_FAILURE_REASONS = (
    "'customer_unavailable', 'customer_underage', 'id_invalid', "
    "'id_expired', 'customer_refused', 'unsafe_location', "
    "'restricted_product_issue', 'store_issue', 'driver_emergency', "
    "'other_manual_review'"
)
_RETURN_STATES = "'returning', 'returned_pending_confirmation', 'confirmed'"


def _common_anchor_columns(table_prefix: str) -> list:
    """The id + assignment/order/driver_profile/store anchor columns shared by
    every Dr.1.2.B compliance table, with the per-table FK constraint names."""
    return [
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
    ]


def _common_anchor_constraints(table_prefix: str) -> list:
    return [
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["order_driver_assignments.id"],
            name=f"fk_{table_prefix}_assignment_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=f"fk_{table_prefix}_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["driver_profile_id"],
            ["driver_profiles.id"],
            name=f"fk_{table_prefix}_driver_profile_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=f"fk_{table_prefix}_store_id",
            ondelete="CASCADE",
        ),
    ]


def _timestamp_columns() -> list:
    return [
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
    ]


def _set_updated_at_trigger(table_name: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER trg_{table_name}_set_updated_at
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
        """
    )


def upgrade() -> None:
    # ----------------------------------------------------------------- #
    # driver_delivery_verifications
    # ----------------------------------------------------------------- #
    op.create_table(
        "driver_delivery_verifications",
        *_common_anchor_columns("driver_delivery_verifications"),
        sa.Column("performed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("failure_reason_code", sa.String(length=40), nullable=True),
        sa.Column(
            "method",
            sa.String(length=40),
            server_default=sa.text("'manual_checklist'"),
            nullable=False,
        ),
        sa.Column("age_over_21_confirmed", sa.Boolean(), nullable=True),
        sa.Column("id_expiration_checked", sa.Boolean(), nullable=True),
        sa.Column("id_not_expired", sa.Boolean(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        *_common_anchor_constraints("driver_delivery_verifications"),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"],
            ["users.id"],
            name="fk_driver_delivery_verifications_performed_by_user_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            f"outcome IN ({_VERIFICATION_OUTCOMES})",
            name="ck_driver_delivery_verifications_outcome_valid",
        ),
        sa.CheckConstraint(
            f"method IN ({_METHODS})",
            name="ck_driver_delivery_verifications_method_valid",
        ),
        sa.CheckConstraint(
            "method <> ''",
            name="ck_driver_delivery_verifications_method_non_empty",
        ),
        sa.CheckConstraint(
            "failure_reason_code IS NULL OR failure_reason_code IN ("
            f"{_VERIFICATION_FAILURE_REASONS})",
            name="ck_driver_delivery_verifications_failure_reason_valid",
        ),
        sa.CheckConstraint(
            "outcome <> 'fail' OR failure_reason_code IS NOT NULL",
            name="ck_driver_delivery_verifications_fail_requires_reason",
        ),
    )
    for column in (
        "assignment_id",
        "order_id",
        "driver_profile_id",
        "store_id",
        "created_at",
        "outcome",
        "failure_reason_code",
    ):
        op.create_index(
            f"ix_driver_delivery_verifications_{column}",
            "driver_delivery_verifications",
            [column],
            unique=False,
        )
    _set_updated_at_trigger("driver_delivery_verifications")

    # ----------------------------------------------------------------- #
    # driver_delivery_proofs
    # ----------------------------------------------------------------- #
    op.create_table(
        "driver_delivery_proofs",
        *_common_anchor_columns("driver_delivery_proofs"),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "method",
            sa.String(length=40),
            server_default=sa.text("'manual_checklist'"),
            nullable=False,
        ),
        sa.Column(
            "recipient_present_confirmed", sa.Boolean(), nullable=False
        ),
        sa.Column("handoff_confirmed", sa.Boolean(), nullable=False),
        sa.Column(
            "restricted_not_left_unattended", sa.Boolean(), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        *_common_anchor_constraints("driver_delivery_proofs"),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name="fk_driver_delivery_proofs_submitted_by_user_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            f"method IN ({_METHODS})",
            name="ck_driver_delivery_proofs_method_valid",
        ),
        sa.CheckConstraint(
            "method <> ''",
            name="ck_driver_delivery_proofs_method_non_empty",
        ),
    )
    for column in (
        "assignment_id",
        "order_id",
        "driver_profile_id",
        "store_id",
        "created_at",
    ):
        op.create_index(
            f"ix_driver_delivery_proofs_{column}",
            "driver_delivery_proofs",
            [column],
            unique=False,
        )
    _set_updated_at_trigger("driver_delivery_proofs")

    # ----------------------------------------------------------------- #
    # driver_delivery_failures
    # ----------------------------------------------------------------- #
    op.create_table(
        "driver_delivery_failures",
        *_common_anchor_columns("driver_delivery_failures"),
        sa.Column("reported_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason_code", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        *_common_anchor_constraints("driver_delivery_failures"),
        sa.ForeignKeyConstraint(
            ["reported_by_user_id"],
            ["users.id"],
            name="fk_driver_delivery_failures_reported_by_user_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            f"reason_code IN ({_FAILURE_REASONS})",
            name="ck_driver_delivery_failures_reason_code_valid",
        ),
        sa.CheckConstraint(
            "reason_code <> ''",
            name="ck_driver_delivery_failures_reason_code_non_empty",
        ),
    )
    for column in (
        "assignment_id",
        "order_id",
        "driver_profile_id",
        "store_id",
        "created_at",
        "reason_code",
    ):
        op.create_index(
            f"ix_driver_delivery_failures_{column}",
            "driver_delivery_failures",
            [column],
            unique=False,
        )
    _set_updated_at_trigger("driver_delivery_failures")

    # ----------------------------------------------------------------- #
    # driver_delivery_returns
    # ----------------------------------------------------------------- #
    op.create_table(
        "driver_delivery_returns",
        *_common_anchor_columns("driver_delivery_returns"),
        sa.Column("driver_user_id", sa.UUID(), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("return_state", sa.String(length=40), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            name="uq_driver_delivery_returns_assignment_id",
        ),
        *_common_anchor_constraints("driver_delivery_returns"),
        sa.ForeignKeyConstraint(
            ["driver_user_id"],
            ["users.id"],
            name="fk_driver_delivery_returns_driver_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name="fk_driver_delivery_returns_confirmed_by_user_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            f"return_state IN ({_RETURN_STATES})",
            name="ck_driver_delivery_returns_return_state_valid",
        ),
        sa.CheckConstraint(
            "return_state <> ''",
            name="ck_driver_delivery_returns_return_state_non_empty",
        ),
        sa.CheckConstraint(
            "(confirmed_at IS NULL) = (confirmed_by_user_id IS NULL)",
            name="ck_driver_delivery_returns_confirmation_pair_consistent",
        ),
        sa.CheckConstraint(
            "return_state <> 'confirmed' OR "
            "(confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL)",
            name="ck_driver_delivery_returns_confirmed_requires_confirmation",
        ),
    )
    # No separate index on assignment_id: the UNIQUE constraint already
    # creates a sufficient unique btree index.
    for column in (
        "order_id",
        "driver_profile_id",
        "store_id",
        "created_at",
        "return_state",
        "confirmed_at",
    ):
        op.create_index(
            f"ix_driver_delivery_returns_{column}",
            "driver_delivery_returns",
            [column],
            unique=False,
        )
    _set_updated_at_trigger("driver_delivery_returns")


def downgrade() -> None:
    for table_name in (
        "driver_delivery_returns",
        "driver_delivery_failures",
        "driver_delivery_proofs",
        "driver_delivery_verifications",
    ):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table_name}_set_updated_at "
            f"ON {table_name}"
        )

    op.drop_index(
        "ix_driver_delivery_returns_confirmed_at",
        table_name="driver_delivery_returns",
    )
    op.drop_index(
        "ix_driver_delivery_returns_return_state",
        table_name="driver_delivery_returns",
    )
    op.drop_index(
        "ix_driver_delivery_returns_created_at",
        table_name="driver_delivery_returns",
    )
    op.drop_index(
        "ix_driver_delivery_returns_store_id",
        table_name="driver_delivery_returns",
    )
    op.drop_index(
        "ix_driver_delivery_returns_driver_profile_id",
        table_name="driver_delivery_returns",
    )
    op.drop_index(
        "ix_driver_delivery_returns_order_id",
        table_name="driver_delivery_returns",
    )
    op.drop_table("driver_delivery_returns")

    op.drop_index(
        "ix_driver_delivery_failures_reason_code",
        table_name="driver_delivery_failures",
    )
    op.drop_index(
        "ix_driver_delivery_failures_created_at",
        table_name="driver_delivery_failures",
    )
    op.drop_index(
        "ix_driver_delivery_failures_store_id",
        table_name="driver_delivery_failures",
    )
    op.drop_index(
        "ix_driver_delivery_failures_driver_profile_id",
        table_name="driver_delivery_failures",
    )
    op.drop_index(
        "ix_driver_delivery_failures_order_id",
        table_name="driver_delivery_failures",
    )
    op.drop_index(
        "ix_driver_delivery_failures_assignment_id",
        table_name="driver_delivery_failures",
    )
    op.drop_table("driver_delivery_failures")

    op.drop_index(
        "ix_driver_delivery_proofs_created_at",
        table_name="driver_delivery_proofs",
    )
    op.drop_index(
        "ix_driver_delivery_proofs_store_id",
        table_name="driver_delivery_proofs",
    )
    op.drop_index(
        "ix_driver_delivery_proofs_driver_profile_id",
        table_name="driver_delivery_proofs",
    )
    op.drop_index(
        "ix_driver_delivery_proofs_order_id",
        table_name="driver_delivery_proofs",
    )
    op.drop_index(
        "ix_driver_delivery_proofs_assignment_id",
        table_name="driver_delivery_proofs",
    )
    op.drop_table("driver_delivery_proofs")

    op.drop_index(
        "ix_driver_delivery_verifications_failure_reason_code",
        table_name="driver_delivery_verifications",
    )
    op.drop_index(
        "ix_driver_delivery_verifications_outcome",
        table_name="driver_delivery_verifications",
    )
    op.drop_index(
        "ix_driver_delivery_verifications_created_at",
        table_name="driver_delivery_verifications",
    )
    op.drop_index(
        "ix_driver_delivery_verifications_store_id",
        table_name="driver_delivery_verifications",
    )
    op.drop_index(
        "ix_driver_delivery_verifications_driver_profile_id",
        table_name="driver_delivery_verifications",
    )
    op.drop_index(
        "ix_driver_delivery_verifications_order_id",
        table_name="driver_delivery_verifications",
    )
    op.drop_index(
        "ix_driver_delivery_verifications_assignment_id",
        table_name="driver_delivery_verifications",
    )
    op.drop_table("driver_delivery_verifications")
