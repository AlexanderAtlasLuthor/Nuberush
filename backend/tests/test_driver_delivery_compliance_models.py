"""Dr.1.2.B — driver compliance model / DB constraint tests.

Exercises the four storage-only compliance tables directly:
`driver_delivery_verifications`, `driver_delivery_proofs`,
`driver_delivery_failures`, and `driver_delivery_returns`. Covers creation and
server-side defaults, the CHECK vocabularies and conditional CHECKs, the
append-only vs 1:1 cardinality split, FK integrity / read anchors, ON DELETE
behaviour (assignment CASCADE, driver_profile RESTRICT), the updated_at
trigger, and domain-separation / redaction guards proving Dr.1.2.B added no
sensitive columns and did not bleed into OrderStatus / inventory.

This is a MODEL/DB suite only — no service, schema, route, transition,
`Order.status` bridge, inventory, idempotency, or audit runtime is touched.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone
from typing import Callable

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryFailure
from app.db.models import DriverDeliveryFailureReason
from app.db.models import DriverDeliveryProof
from app.db.models import DriverDeliveryProofMethod
from app.db.models import DriverDeliveryReturn
from app.db.models import DriverDeliveryReturnState
from app.db.models import DriverDeliveryVerification
from app.db.models import DriverDeliveryVerificationFailureReason
from app.db.models import DriverDeliveryVerificationMethod
from app.db.models import DriverDeliveryVerificationOutcome
from app.db.models import OrderDriverAssignment
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DDC-Store") -> Store:
        store = Store(name=name, code=f"ddc-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_assignment(
    db_session: Session, make_store
) -> Callable[..., OrderDriverAssignment]:
    """A fresh store + order + driver profile + assignment, all same-store."""

    def _create() -> OrderDriverAssignment:
        store = make_store()
        order = make_order(db_session, store=store)
        user = central_make_user(
            db_session, role=UserRole.driver, store_id=store.id
        )
        profile = make_driver_profile(db_session, user=user, store=store)
        return make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
        )

    return _create


def _anchor_kwargs(assignment: OrderDriverAssignment) -> dict:
    """The shared assignment/order/driver_profile/store anchors, all derived
    from the assignment so tenancy stays consistent by construction."""
    return {
        "assignment_id": assignment.id,
        "order_id": assignment.order_id,
        "driver_profile_id": assignment.driver_profile_id,
        "store_id": assignment.store_id,
    }


def _verification(assignment: OrderDriverAssignment, **overrides):
    kwargs = {
        **_anchor_kwargs(assignment),
        "outcome": DriverDeliveryVerificationOutcome.pass_.value,
    }
    kwargs.update(overrides)
    return DriverDeliveryVerification(**kwargs)


def _proof(assignment: OrderDriverAssignment, **overrides):
    kwargs = {
        **_anchor_kwargs(assignment),
        "recipient_present_confirmed": True,
        "handoff_confirmed": True,
        "restricted_not_left_unattended": True,
    }
    kwargs.update(overrides)
    return DriverDeliveryProof(**kwargs)


def _failure(assignment: OrderDriverAssignment, **overrides):
    kwargs = {
        **_anchor_kwargs(assignment),
        "reason_code": DriverDeliveryFailureReason.customer_unavailable.value,
    }
    kwargs.update(overrides)
    return DriverDeliveryFailure(**kwargs)


def _return(assignment: OrderDriverAssignment, **overrides):
    kwargs = {
        **_anchor_kwargs(assignment),
        "return_state": DriverDeliveryReturnState.returning.value,
    }
    kwargs.update(overrides)
    return DriverDeliveryReturn(**kwargs)


def _add_commit_refresh(db_session: Session, row):
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _expect_integrity_error(db_session: Session, row) -> None:
    with pytest.raises(IntegrityError):
        db_session.add(row)
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# A. Happy paths + server-side defaults
# --------------------------------------------------------------------- #


def test_verification_happy_path(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    row = _add_commit_refresh(
        db_session,
        _verification(
            assignment,
            age_over_21_confirmed=True,
            id_expiration_checked=True,
            id_not_expired=True,
            note="visual checklist ok",
        ),
    )
    assert row.id is not None
    assert row.assignment_id == assignment.id
    assert row.order_id == assignment.order_id
    assert row.driver_profile_id == assignment.driver_profile_id
    assert row.store_id == assignment.store_id
    assert row.outcome == "pass"
    assert row.failure_reason_code is None
    assert row.method == "manual_checklist"  # server default
    assert row.created_at is not None
    assert row.updated_at is not None


def test_proof_happy_path(db_session: Session, make_assignment) -> None:
    assignment = make_assignment()
    row = _add_commit_refresh(db_session, _proof(assignment))
    assert row.id is not None
    assert row.method == "manual_checklist"  # server default
    assert row.recipient_present_confirmed is True
    assert row.handoff_confirmed is True
    assert row.restricted_not_left_unattended is True


def test_failure_happy_path(db_session: Session, make_assignment) -> None:
    assignment = make_assignment()
    row = _add_commit_refresh(db_session, _failure(assignment))
    assert row.id is not None
    assert row.reason_code == "customer_unavailable"


def test_return_happy_path(db_session: Session, make_assignment) -> None:
    assignment = make_assignment()
    row = _add_commit_refresh(db_session, _return(assignment))
    assert row.id is not None
    assert row.return_state == "returning"
    assert row.confirmed_at is None
    assert row.confirmed_by_user_id is None


# --------------------------------------------------------------------- #
# B. CHECK vocabularies
# --------------------------------------------------------------------- #


def test_invalid_verification_outcome_blocked(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _expect_integrity_error(
        db_session, _verification(assignment, outcome="approved")
    )


def test_verification_fail_requires_reason(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _expect_integrity_error(
        db_session,
        _verification(
            assignment,
            outcome=DriverDeliveryVerificationOutcome.fail.value,
            failure_reason_code=None,
        ),
    )


def test_invalid_verification_failure_reason_blocked(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _expect_integrity_error(
        db_session,
        _verification(
            assignment,
            outcome=DriverDeliveryVerificationOutcome.fail.value,
            failure_reason_code="bad_vibes",
        ),
    )


def test_verification_fail_with_valid_reason_persists(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    row = _add_commit_refresh(
        db_session,
        _verification(
            assignment,
            outcome=DriverDeliveryVerificationOutcome.fail.value,
            failure_reason_code=(
                DriverDeliveryVerificationFailureReason.customer_underage.value
            ),
        ),
    )
    assert row.outcome == "fail"
    assert row.failure_reason_code == "customer_underage"


def test_invalid_proof_method_blocked(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _expect_integrity_error(db_session, _proof(assignment, method="photo"))


def test_invalid_failure_reason_blocked(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _expect_integrity_error(
        db_session, _failure(assignment, reason_code="bored")
    )


def test_invalid_return_state_blocked(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _expect_integrity_error(
        db_session, _return(assignment, return_state="teleported")
    )


@pytest.mark.parametrize(
    "outcome", [v.value for v in DriverDeliveryVerificationOutcome]
)
def test_all_verification_outcomes_persist(
    db_session: Session, make_assignment, outcome: str
) -> None:
    assignment = make_assignment()
    # A fail needs a reason; pass / manual_review do not.
    reason = (
        DriverDeliveryVerificationFailureReason.manual_review_required.value
        if outcome == "fail"
        else None
    )
    row = _add_commit_refresh(
        db_session,
        _verification(
            assignment, outcome=outcome, failure_reason_code=reason
        ),
    )
    assert row.outcome == outcome


@pytest.mark.parametrize(
    "reason_code", [v.value for v in DriverDeliveryFailureReason]
)
def test_all_failure_reasons_persist(
    db_session: Session, make_assignment, reason_code: str
) -> None:
    assignment = make_assignment()
    row = _add_commit_refresh(
        db_session, _failure(assignment, reason_code=reason_code)
    )
    assert row.reason_code == reason_code


# --------------------------------------------------------------------- #
# C. Cardinality: append-only for verify/proof/fail, 1:1 for return
# --------------------------------------------------------------------- #


def test_verification_allows_multiple_rows_per_assignment(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _add_commit_refresh(db_session, _verification(assignment))
    # A second verification on the same assignment must be allowed.
    _add_commit_refresh(
        db_session,
        _verification(
            assignment,
            outcome=DriverDeliveryVerificationOutcome.manual_review.value,
        ),
    )


def test_proof_allows_multiple_rows_per_assignment(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _add_commit_refresh(db_session, _proof(assignment))
    _add_commit_refresh(db_session, _proof(assignment))


def test_failure_allows_multiple_rows_per_assignment(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _add_commit_refresh(db_session, _failure(assignment))
    _add_commit_refresh(
        db_session,
        _failure(
            assignment,
            reason_code=DriverDeliveryFailureReason.store_issue.value,
        ),
    )


def test_return_is_unique_per_assignment(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _add_commit_refresh(db_session, _return(assignment))
    _expect_integrity_error(db_session, _return(assignment))


# --------------------------------------------------------------------- #
# D. Return confirmation constraints
# --------------------------------------------------------------------- #


def test_return_confirmation_pair_must_be_consistent(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    # confirmed_at set but confirmed_by_user_id null → pair inconsistent.
    _expect_integrity_error(
        db_session,
        _return(
            assignment,
            return_state=(
                DriverDeliveryReturnState.returned_pending_confirmation.value
            ),
            confirmed_at=datetime.now(timezone.utc),
            confirmed_by_user_id=None,
        ),
    )


def test_return_confirmed_requires_confirmation_fields(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    # return_state = confirmed but both confirmation fields null → blocked.
    _expect_integrity_error(
        db_session,
        _return(
            assignment,
            return_state=DriverDeliveryReturnState.confirmed.value,
            confirmed_at=None,
            confirmed_by_user_id=None,
        ),
    )


def test_return_confirmed_with_both_fields_persists(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    store_manager = central_make_user(
        db_session, role=UserRole.manager, store_id=assignment.store_id
    )
    row = _add_commit_refresh(
        db_session,
        _return(
            assignment,
            return_state=DriverDeliveryReturnState.confirmed.value,
            confirmed_at=datetime.now(timezone.utc),
            confirmed_by_user_id=store_manager.id,
        ),
    )
    assert row.return_state == "confirmed"
    assert row.confirmed_at is not None
    assert row.confirmed_by_user_id == store_manager.id


# --------------------------------------------------------------------- #
# E. FK integrity / read anchors
# --------------------------------------------------------------------- #


def test_invalid_assignment_fk_rejected(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    bad = _verification(assignment)
    bad.assignment_id = uuid.uuid4()
    _expect_integrity_error(db_session, bad)


def test_invalid_store_fk_rejected(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    bad = _failure(assignment)
    bad.store_id = uuid.uuid4()
    _expect_integrity_error(db_session, bad)


# --------------------------------------------------------------------- #
# F. ON DELETE behaviour
# --------------------------------------------------------------------- #


def test_assignment_delete_cascades_compliance_rows(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    verification = _add_commit_refresh(db_session, _verification(assignment))
    proof = _add_commit_refresh(db_session, _proof(assignment))
    failure = _add_commit_refresh(db_session, _failure(assignment))
    ret = _add_commit_refresh(db_session, _return(assignment))
    ids = (verification.id, proof.id, failure.id, ret.id)

    db_session.execute(
        delete(OrderDriverAssignment).where(
            OrderDriverAssignment.id == assignment.id
        )
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(DriverDeliveryVerification, ids[0]) is None
    assert db_session.get(DriverDeliveryProof, ids[1]) is None
    assert db_session.get(DriverDeliveryFailure, ids[2]) is None
    assert db_session.get(DriverDeliveryReturn, ids[3]) is None


def test_driver_profile_delete_restricted_by_compliance_row(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    _add_commit_refresh(db_session, _verification(assignment))
    profile = assignment.driver_profile

    # driver_profile FK is ON DELETE RESTRICT: a profile with compliance
    # history cannot be hard-deleted.
    with pytest.raises(IntegrityError):
        db_session.delete(profile)
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# G. updated_at trigger
# --------------------------------------------------------------------- #


def test_updated_at_trigger_fires_on_update(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    row = _add_commit_refresh(db_session, _return(assignment))
    original_updated_at = row.updated_at

    row.return_state = (
        DriverDeliveryReturnState.returned_pending_confirmation.value
    )
    db_session.commit()
    db_session.refresh(row)

    assert row.return_state == "returned_pending_confirmation"
    assert row.updated_at >= original_updated_at


# --------------------------------------------------------------------- #
# H. Domain separation + redaction guards
# --------------------------------------------------------------------- #


def test_order_status_vocabulary_unchanged() -> None:
    assert [s.value for s in OrderStatus] == [
        "pending",
        "accepted",
        "preparing",
        "ready",
        "out_for_delivery",
        "delivered",
        "canceled",
        "returned",
    ]


def test_enum_vocabularies_frozen() -> None:
    assert [v.value for v in DriverDeliveryVerificationOutcome] == [
        "pass",
        "fail",
        "manual_review",
    ]
    assert [
        v.value for v in DriverDeliveryVerificationFailureReason
    ] == [
        "customer_underage",
        "id_invalid",
        "id_expired",
        "id_not_available",
        "customer_refused",
        "manual_review_required",
        "other_manual_review",
    ]
    assert [v.value for v in DriverDeliveryVerificationMethod] == [
        "manual_checklist"
    ]
    assert [v.value for v in DriverDeliveryProofMethod] == ["manual_checklist"]
    assert [v.value for v in DriverDeliveryFailureReason] == [
        "customer_unavailable",
        "customer_underage",
        "id_invalid",
        "id_expired",
        "customer_refused",
        "unsafe_location",
        "restricted_product_issue",
        "store_issue",
        "driver_emergency",
        "other_manual_review",
    ]
    assert [v.value for v in DriverDeliveryReturnState] == [
        "returning",
        "returned_pending_confirmation",
        "confirmed",
    ]


@pytest.mark.parametrize(
    "model",
    [
        DriverDeliveryVerification,
        DriverDeliveryProof,
        DriverDeliveryFailure,
        DriverDeliveryReturn,
    ],
)
def test_no_sensitive_columns(model) -> None:
    """No table may carry raw ID / OCR / barcode / biometric / signature /
    photo / artifact-path columns — only redaction-safe metadata."""
    columns = set(model.__table__.columns.keys())
    forbidden = {
        "raw_id_image",
        "id_image_url",
        "id_number",
        "id_number_last4",
        "date_of_birth",
        "dob",
        "ocr_payload",
        "barcode_payload",
        "barcode_raw",
        "biometric_payload",
        "signature",
        "signature_url",
        "customer_photo",
        "customer_photo_url",
        "proof_file_url",
        "artifact_url",
        "file_path",
        "external_url",
    }
    assert columns.isdisjoint(forbidden)
