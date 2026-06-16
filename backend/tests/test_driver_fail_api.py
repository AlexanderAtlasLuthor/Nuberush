"""Dr.1.2.F — failed-delivery API tests.

Confirms POST /driver/assignments/{id}/fail: the 200 operational-only happy
path (response shape DriverDeliveryFailureRead), per-reason idempotency, the
422/409 guards, request validation (reason_code + note max length), the
role/store/auth gates, and a redaction-safe response.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


_FAILURE_KEYS = {
    "id",
    "assignment_id",
    "order_id",
    "driver_profile_id",
    "store_id",
    "reported_by_user_id",
    "reason_code",
    "note",
    "created_at",
    "updated_at",
}

_FORBIDDEN_KEYS = {
    "raw_id",
    "dob",
    "date_of_birth",
    "license",
    "license_number",
    "photo",
    "signature",
    "ocr",
    "barcode",
    "customer_photo",
    "customer_pii",
    "customer",
    "artifact_url",
    "image_path",
    "id_number",
    "order_status",
    "inventory",
}


def _url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/fail"


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "FDA-Store") -> Store:
        store = Store(name=name, code=f"fda-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def _setup(
    db_session: Session,
    store: Store,
    user: User,
    *,
    assignment_status: str = "started",
    order_status: str = "out_for_delivery",
    state: str | None = State.arrived_at_customer.value,
):
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store, status=order_status)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status=assignment_status,
    )
    if state is not None:
        make_driver_delivery_operational_state(
            db_session, assignment=assignment, state=state
        )
    db_session.commit()
    return profile, order, assignment


# --------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------- #


def test_fail_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "customer_unavailable", "note": "not home"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _FAILURE_KEYS
    assert body["reason_code"] == "customer_unavailable"
    assert body["note"] == "not home"
    assert body["assignment_id"] == str(assignment.id)
    assert body["reported_by_user_id"] == str(user.id)


def test_fail_note_optional(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "driver_emergency"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["note"] is None


def test_response_no_sensitive_fields(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    body = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "id_invalid"},
    ).json()
    for forbidden in _FORBIDDEN_KEYS:
        assert forbidden not in body, forbidden


# --------------------------------------------------------------------- #
# Request validation
# --------------------------------------------------------------------- #


def test_missing_reason_code_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(_url(assignment.id), headers=_auth(user), json={})
    assert resp.status_code == 422, resp.text


def test_invalid_reason_code_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "not_a_real_reason"},
    )
    assert resp.status_code == 422, resp.text


def test_note_too_long_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "other_manual_review", "note": "x" * 501},
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------- #


def test_terminal_state_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(
        db_session, store, user, state=State.delivery_completed.value
    )
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "customer_unavailable"},
    )
    assert resp.status_code == 422, resp.text


def test_too_early_state_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(
        db_session, store, user, state=State.arrived_at_store.value
    )
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "store_issue"},
    )
    assert resp.status_code == 422, resp.text


def test_repeated_same_reason_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    payload = {"reason_code": "customer_refused"}
    first = client.post(_url(assignment.id), headers=_auth(user), json=payload)
    second = client.post(_url(assignment.id), headers=_auth(user), json=payload)
    assert first.status_code == 200
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]


def test_repeated_different_reason_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    first = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "customer_refused"},
    )
    second = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"reason_code": "unsafe_location"},
    )
    assert first.status_code == 200
    assert second.status_code == 409, second.text


# --------------------------------------------------------------------- #
# Anti-enumeration / RBAC / auth gates
# --------------------------------------------------------------------- #


def test_foreign_store_driver_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, owner)
    other_store = make_store(name="FDA-Other")
    other = _driver(db_session, other_store)
    make_driver_profile(db_session, user=other, store=other_store)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(other),
        json={"reason_code": "customer_unavailable"},
    )
    assert resp.status_code == 404, resp.text


def test_missing_assignment_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)
    resp = client.post(
        _url(uuid.uuid4()),
        headers=_auth(user),
        json={"reason_code": "customer_unavailable"},
    )
    assert resp.status_code == 404, resp.text


def test_non_driver_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    driver = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, driver)
    staff = central_make_user(
        db_session, role=UserRole.staff, store_id=store.id
    )
    resp = client.post(
        _url(assignment.id),
        headers=_auth(staff),
        json={"reason_code": "customer_unavailable"},
    )
    assert resp.status_code == 403, resp.text


def test_storeless_driver_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    driver = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, driver)
    storeless = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    resp = client.post(
        _url(assignment.id),
        headers=_auth(storeless),
        json={"reason_code": "customer_unavailable"},
    )
    assert resp.status_code == 403, resp.text
