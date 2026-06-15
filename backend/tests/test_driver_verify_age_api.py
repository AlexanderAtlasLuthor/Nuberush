"""Dr.1.2.C — verify-age API tests.

Confirms POST /driver/assignments/{id}/verify-age: the 200 pass happy path and
redaction-safe response shape (DriverDeliveryVerificationRead, no PII / no
Order.status / no inventory), the state advance to id_verified visible via the
delivery-state read, the fail / manual_review record-only behaviour, the
schema validation (fail requires reason; pass forbids reason), the id_verified
idempotency / 409 rules, the 422/409/404 guard matrix, and the role/store/auth
gates.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryVerification
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


_READ_KEYS = {
    "id",
    "assignment_id",
    "order_id",
    "driver_profile_id",
    "store_id",
    "performed_by_user_id",
    "outcome",
    "failure_reason_code",
    "method",
    "age_over_21_confirmed",
    "id_expiration_checked",
    "id_not_expired",
    "note",
    "created_at",
    "updated_at",
}

# Fields that must NEVER appear in the verify-age response (redaction + domain).
_FORBIDDEN_KEYS = {
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
    "order_status",
    "inventory",
    "customer",
    "customer_user_id",
    "email",
    "phone",
    "address",
    "total_amount",
    "age_verified_at",
}


def _url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/verify-age"


def _state_url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/delivery-state"


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "VAA-Store") -> Store:
        store = Store(name=name, code=f"vaa-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def _owned_assignment(
    db_session: Session,
    store: Store,
    user: User,
    *,
    status: str = "started",
    state: str | None = State.arrived_at_customer.value,
):
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store, status="ready")
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status=status,
    )
    if state is not None:
        make_driver_delivery_operational_state(
            db_session, assignment=assignment, state=state
        )
    return profile, order, assignment


def _count_rows(db_session: Session, assignment_id) -> int:
    db_session.expire_all()
    return db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryVerification)
        .where(DriverDeliveryVerification.assignment_id == assignment_id)
    )


# --------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------- #


def test_pass_200_shape(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile, order, assignment = _owned_assignment(db_session, store, user)

    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _READ_KEYS
    assert body["outcome"] == "pass"
    assert body["failure_reason_code"] is None
    assert body["method"] == "manual_checklist"
    assert body["assignment_id"] == str(assignment.id)
    assert body["order_id"] == str(order.id)
    assert body["driver_profile_id"] == str(profile.id)
    assert body["store_id"] == str(store.id)
    assert body["performed_by_user_id"] == str(user.id)


def test_pass_then_delivery_state_is_id_verified(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)

    client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    state_resp = client.get(_state_url(assignment.id), headers=_auth(user))
    assert state_resp.status_code == 200, state_resp.text
    assert state_resp.json()["state"] == "id_verified"


def test_pass_creates_verification_row(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)

    client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    assert _count_rows(db_session, assignment.id) == 1


def test_response_has_no_sensitive_fields(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)

    body = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={
            "outcome": "pass",
            "age_over_21_confirmed": True,
            "id_expiration_checked": True,
            "id_not_expired": True,
            "note": "visual checklist ok",
        },
    ).json()
    for forbidden in _FORBIDDEN_KEYS:
        assert forbidden not in body, forbidden


# --------------------------------------------------------------------- #
# fail / manual_review record-only
# --------------------------------------------------------------------- #


def test_fail_200_keeps_arrived_at_customer(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)

    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={
            "outcome": "fail",
            "failure_reason_code": "customer_underage",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["outcome"] == "fail"
    state = client.get(_state_url(assignment.id), headers=_auth(user)).json()
    assert state["state"] == "arrived_at_customer"


def test_manual_review_200_keeps_arrived_at_customer(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)

    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"outcome": "manual_review"},
    )
    assert resp.status_code == 200, resp.text
    state = client.get(_state_url(assignment.id), headers=_auth(user)).json()
    assert state["state"] == "arrived_at_customer"


# --------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------- #


def test_fail_without_reason_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "fail"}
    )
    assert resp.status_code == 422, resp.text


def test_pass_with_reason_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={
            "outcome": "pass",
            "failure_reason_code": "customer_underage",
        },
    )
    assert resp.status_code == 422, resp.text


def test_invalid_outcome_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"outcome": "approved"},
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# id_verified idempotency / conflict through the API
# --------------------------------------------------------------------- #


def test_pass_idempotent_no_duplicate_row(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)

    first = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    second = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert _count_rows(db_session, assignment.id) == 1


def test_fail_from_id_verified_is_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={
            "outcome": "fail",
            "failure_reason_code": "customer_underage",
        },
    )
    assert resp.status_code == 409, resp.text


def test_manual_review_from_id_verified_is_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"outcome": "manual_review"},
    )
    assert resp.status_code == 409, resp.text


# --------------------------------------------------------------------- #
# State / status guards
# --------------------------------------------------------------------- #


def test_before_arrived_at_customer_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=State.picked_up.value
    )
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    assert resp.status_code == 422, resp.text


def test_no_operational_state_row_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=None
    )
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    assert resp.status_code == 422, resp.text


def test_terminal_state_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=State.delivery_completed.value
    )
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    assert resp.status_code == 422, resp.text


def test_assignment_not_started_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, status="accepted"
    )
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"outcome": "pass"}
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# Anti-enumeration / RBAC / auth gates
# --------------------------------------------------------------------- #


def test_missing_assignment_is_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)
    resp = client.post(
        _url(uuid.uuid4()), headers=_auth(user), json={"outcome": "pass"}
    )
    assert resp.status_code == 404, resp.text


def test_foreign_store_driver_is_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, owner)

    other_store = make_store(name="VAA-Other")
    other = _driver(db_session, other_store)
    make_driver_profile(db_session, user=other, store=other_store)
    resp = client.post(
        _url(assignment.id), headers=_auth(other), json={"outcome": "pass"}
    )
    assert resp.status_code == 404, resp.text


def test_non_driver_is_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    driver = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, driver)
    staff = central_make_user(
        db_session, role=UserRole.staff, store_id=store.id
    )
    resp = client.post(
        _url(assignment.id), headers=_auth(staff), json={"outcome": "pass"}
    )
    assert resp.status_code == 403, resp.text


def test_storeless_driver_is_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    driver = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, driver)
    storeless = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    resp = client.post(
        _url(assignment.id),
        headers=_auth(storeless),
        json={"outcome": "pass"},
    )
    assert resp.status_code == 403, resp.text
