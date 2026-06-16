"""Dr.1.2.D — proof-of-delivery API tests.

Confirms POST /driver/assignments/{id}/proof: the 200 happy path from
id_verified, the redaction-safe response shape (DriverDeliveryProofRead, no PII
/ no Order.status / no inventory), the record-only guarantee (state stays
id_verified), idempotency-by-existence, the all-confirmations-true validation,
the 422/409/404 guard matrix, and the role/store/auth gates.
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
from app.db.models import DriverDeliveryProof
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
    "submitted_by_user_id",
    "method",
    "recipient_present_confirmed",
    "handoff_confirmed",
    "restricted_not_left_unattended",
    "note",
    "created_at",
    "updated_at",
}

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
    "photo",
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

_VALID = {
    "recipient_present_confirmed": True,
    "handoff_confirmed": True,
    "restricted_not_left_unattended": True,
}


def _url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/proof"


def _state_url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/delivery-state"


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "PRA-Store") -> Store:
        store = Store(name=name, code=f"pra-{uuid.uuid4().hex[:8]}")
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
    state: str | None = State.id_verified.value,
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
        .select_from(DriverDeliveryProof)
        .where(DriverDeliveryProof.assignment_id == assignment_id)
    )


# --------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------- #


def test_proof_200_shape(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile, order, assignment = _owned_assignment(db_session, store, user)

    resp = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _READ_KEYS
    assert body["method"] == "manual_checklist"
    assert body["recipient_present_confirmed"] is True
    assert body["handoff_confirmed"] is True
    assert body["restricted_not_left_unattended"] is True
    assert body["assignment_id"] == str(assignment.id)
    assert body["order_id"] == str(order.id)
    assert body["driver_profile_id"] == str(profile.id)
    assert body["store_id"] == str(store.id)
    assert body["submitted_by_user_id"] == str(user.id)


def test_proof_creates_row(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    assert _count_rows(db_session, assignment.id) == 1


def test_proof_keeps_state_id_verified(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    state = client.get(_state_url(assignment.id), headers=_auth(user)).json()
    assert state["state"] == "id_verified"


def test_response_has_no_sensitive_fields(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    body = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={**_VALID, "note": "handed to recipient"},
    ).json()
    for forbidden in _FORBIDDEN_KEYS:
        assert forbidden not in body, forbidden


# --------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------- #


def test_repeated_proof_no_duplicate_row(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    first = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    second = client.post(
        _url(assignment.id), headers=_auth(user), json=_VALID
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert _count_rows(db_session, assignment.id) == 1


# --------------------------------------------------------------------- #
# Confirmation validation
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "field",
    [
        "recipient_present_confirmed",
        "handoff_confirmed",
        "restricted_not_left_unattended",
    ],
)
def test_confirmation_false_is_422(
    client: TestClient, db_session: Session, make_store, field: str
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    payload = {**_VALID, field: False}
    resp = client.post(_url(assignment.id), headers=_auth(user), json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "missing",
    [
        "recipient_present_confirmed",
        "handoff_confirmed",
        "restricted_not_left_unattended",
    ],
)
def test_confirmation_missing_is_422(
    client: TestClient, db_session: Session, make_store, missing: str
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, user)
    payload = {k: v for k, v in _VALID.items() if k != missing}
    resp = client.post(_url(assignment.id), headers=_auth(user), json=payload)
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# State / status guards
# --------------------------------------------------------------------- #


def test_arrived_at_customer_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=State.arrived_at_customer.value
    )
    resp = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    assert resp.status_code == 422, resp.text


def test_pre_id_verified_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=State.picked_up.value
    )
    resp = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    assert resp.status_code == 422, resp.text


def test_no_operational_state_row_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=None
    )
    resp = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    assert resp.status_code == 422, resp.text


def test_terminal_state_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=State.delivery_completed.value
    )
    resp = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    assert resp.status_code == 422, resp.text


def test_returning_to_store_is_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, state=State.returning_to_store.value
    )
    resp = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
    assert resp.status_code == 409, resp.text


def test_assignment_not_started_is_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(
        db_session, store, user, status="accepted"
    )
    resp = client.post(_url(assignment.id), headers=_auth(user), json=_VALID)
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
    resp = client.post(_url(uuid.uuid4()), headers=_auth(user), json=_VALID)
    assert resp.status_code == 404, resp.text


def test_foreign_store_driver_is_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    _p, _o, assignment = _owned_assignment(db_session, store, owner)
    other_store = make_store(name="PRA-Other")
    other = _driver(db_session, other_store)
    make_driver_profile(db_session, user=other, store=other_store)
    resp = client.post(
        _url(assignment.id), headers=_auth(other), json=_VALID
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
        _url(assignment.id), headers=_auth(staff), json=_VALID
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
        _url(assignment.id), headers=_auth(storeless), json=_VALID
    )
    assert resp.status_code == 403, resp.text
