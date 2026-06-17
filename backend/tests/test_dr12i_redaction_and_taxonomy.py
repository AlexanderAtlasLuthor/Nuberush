"""Dr.1.2.I.a — redaction caps + operational-audit taxonomy unit tests.

Covers the schema-level note caps (verify-age / proof) and the extended
`delivery_assignment` operational-audit taxonomy: accepted actions, rejected
unknown action, the strict before/after allow-list, and metadata scrubbing.
No migration, no ledger.
"""

from __future__ import annotations

import uuid

import pydantic
import pytest
from sqlalchemy.orm import Session

from app.schemas.driver import DriverProofSubmitRequest
from app.schemas.driver import DriverVerifyAgeRequest
from app.services.operational_audit import TARGET_DELIVERY_ASSIGNMENT
from app.services.operational_audit import write_operational_audit_log


_DELIVERY_ACTIONS = [
    "delivery_verified",
    "delivery_proof_recorded",
    "delivery_completed",
    "delivery_failed",
    "delivery_return_started",
    "delivery_return_arrived",
    "delivery_return_confirmed",
]


# --------------------------------------------------------------------- #
# Redaction caps
# --------------------------------------------------------------------- #


def test_verify_age_note_over_500_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        DriverVerifyAgeRequest(outcome="pass", note="x" * 501)


def test_verify_age_note_at_500_accepted() -> None:
    req = DriverVerifyAgeRequest(outcome="pass", note="x" * 500)
    assert req.note == "x" * 500


def test_proof_note_over_500_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        DriverProofSubmitRequest(
            recipient_present_confirmed=True,
            handoff_confirmed=True,
            restricted_not_left_unattended=True,
            note="x" * 501,
        )


def test_proof_note_at_500_accepted() -> None:
    req = DriverProofSubmitRequest(
        recipient_present_confirmed=True,
        handoff_confirmed=True,
        restricted_not_left_unattended=True,
        note="x" * 500,
    )
    assert req.note == "x" * 500


# --------------------------------------------------------------------- #
# Taxonomy: accepted actions
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("action", _DELIVERY_ACTIONS)
def test_delivery_assignment_accepts_action(
    db_session: Session, action: str
) -> None:
    log = write_operational_audit_log(
        db_session,
        actor_user_id=None,
        target_type=TARGET_DELIVERY_ASSIGNMENT,
        target_id=uuid.uuid4(),
        action=action,
        store_id=None,
        before={"state": "x"},
        after={"state": "y"},
        metadata={"source": "unit"},
    )
    assert log.target_type == "delivery_assignment"
    assert log.action == action


def test_unknown_delivery_action_rejected(db_session: Session) -> None:
    with pytest.raises(ValueError):
        write_operational_audit_log(
            db_session,
            actor_user_id=None,
            target_type=TARGET_DELIVERY_ASSIGNMENT,
            target_id=uuid.uuid4(),
            action="delivery_not_a_real_action",
            store_id=None,
        )


def test_cross_target_action_rejected(db_session: Session) -> None:
    # A user-target action is not valid for delivery_assignment.
    with pytest.raises(ValueError):
        write_operational_audit_log(
            db_session,
            actor_user_id=None,
            target_type=TARGET_DELIVERY_ASSIGNMENT,
            target_id=uuid.uuid4(),
            action="user_created",
            store_id=None,
        )


# --------------------------------------------------------------------- #
# Allow-list + scrub
# --------------------------------------------------------------------- #


def test_before_after_allow_list_drops_disallowed_fields(
    db_session: Session,
) -> None:
    log = write_operational_audit_log(
        db_session,
        actor_user_id=None,
        target_type=TARGET_DELIVERY_ASSIGNMENT,
        target_id=uuid.uuid4(),
        action="delivery_verified",
        store_id=None,
        before={
            "state": "arrived_at_customer",
            "customer_email": "a@b.c",
            "id_number": "X123",
            "address": "123 Main St",
        },
        after={
            "state": "id_verified",
            "outcome": "pass",
            "reason_code": "ok",
            "latitude": "40.7",
        },
    )
    # Only allow-listed keys survive (state/outcome/reason_code/status/return_state).
    assert log.before == {"state": "arrived_at_customer"}
    assert log.after == {
        "state": "id_verified",
        "outcome": "pass",
        "reason_code": "ok",
    }
    assert "customer_email" not in (log.before or {})
    assert "id_number" not in (log.before or {})
    assert "address" not in (log.before or {})
    assert "latitude" not in (log.after or {})


def test_metadata_scrubs_sensitive_keys(db_session: Session) -> None:
    log = write_operational_audit_log(
        db_session,
        actor_user_id=None,
        target_type=TARGET_DELIVERY_ASSIGNMENT,
        target_id=uuid.uuid4(),
        action="delivery_failed",
        store_id=None,
        metadata={
            "source": "driver_fail",
            "reason_code": "customer_unavailable",
            "access_token": "secret-value",
            "authorization": "Bearer abc",
        },
    )
    assert log.event_metadata is not None
    assert log.event_metadata.get("source") == "driver_fail"
    assert log.event_metadata.get("reason_code") == "customer_unavailable"
    assert "access_token" not in log.event_metadata
    assert "authorization" not in log.event_metadata
