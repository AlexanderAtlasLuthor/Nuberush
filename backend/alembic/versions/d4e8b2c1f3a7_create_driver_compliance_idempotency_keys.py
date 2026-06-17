"""create driver_compliance_idempotency_keys (Dr.1.2.I.b)

Strong compliance idempotency ledger foundation. One row per
``(store_id, action, idempotency_key)`` claim: inserted ``pending`` in the
same transaction as the business mutation and flipped to ``completed`` before
that transaction commits. Stores only a sha256 ``request_hash`` and a
``response_ref_id`` for replay — never a raw request payload or response body.

I.b wires only the orders-side ``delivery_return_confirmed`` pilot; the action
CHECK is future-ready for all seven Dr.1.2 compliance actions (I.c rollout).

Revision ID: d4e8b2c1f3a7
Revises: c3d7f1a9e2b4
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d4e8b2c1f3a7"
down_revision = "c3d7f1a9e2b4"
branch_labels = None
depends_on = None


# Closed action taxonomy for the ledger CHECK (mirrors the operational-audit
# delivery_assignment actions). Future-ready for all seven; I.b wires one.
_ACTIONS = (
    "delivery_verified",
    "delivery_proof_recorded",
    "delivery_completed",
    "delivery_failed",
    "delivery_return_started",
    "delivery_return_arrived",
    "delivery_return_confirmed",
)
_ACTIONS_SQL = ", ".join(f"'{a}'" for a in _ACTIONS)


def upgrade() -> None:
    op.create_table(
        "driver_compliance_idempotency_keys",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("assignment_id", sa.UUID(), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_ref_id", sa.UUID(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_driver_compliance_idempotency_keys_actor_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_driver_compliance_idempotency_keys_store_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_driver_compliance_idempotency_keys_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["order_driver_assignments.id"],
            name="fk_driver_compliance_idempotency_keys_assignment_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "store_id",
            "action",
            "idempotency_key",
            name="uq_driver_compliance_idempotency_keys_scope",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'completed')",
            name="ck_driver_compliance_idempotency_keys_state_valid",
        ),
        sa.CheckConstraint(
            f"action IN ({_ACTIONS_SQL})",
            name="ck_driver_compliance_idempotency_keys_action_valid",
        ),
        sa.CheckConstraint(
            "idempotency_key <> ''",
            name="ck_driver_compliance_idempotency_keys_key_non_empty",
        ),
        sa.CheckConstraint(
            "char_length(request_hash) = 64",
            name="ck_driver_compliance_idempotency_keys_request_hash_len",
        ),
    )
    op.create_index(
        "ix_driver_compliance_idempotency_keys_created_at",
        "driver_compliance_idempotency_keys",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_driver_compliance_idempotency_keys_expires_at",
        "driver_compliance_idempotency_keys",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_driver_compliance_idempotency_keys_store_action",
        "driver_compliance_idempotency_keys",
        ["store_id", "action"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_driver_compliance_idempotency_keys_store_action",
        table_name="driver_compliance_idempotency_keys",
    )
    op.drop_index(
        "ix_driver_compliance_idempotency_keys_expires_at",
        table_name="driver_compliance_idempotency_keys",
    )
    op.drop_index(
        "ix_driver_compliance_idempotency_keys_created_at",
        table_name="driver_compliance_idempotency_keys",
    )
    op.drop_table("driver_compliance_idempotency_keys")
