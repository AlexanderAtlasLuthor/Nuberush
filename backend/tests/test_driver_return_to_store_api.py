"""Dr.1.2.G — return-to-store API tests.

Confirms POST /driver/assignments/{id}/return-to-store: the 200 start/arrive
happy paths (response shape DriverDeliveryReturnRead, confirmed_* null),
per-action idempotency, request validation (action + note max length), the
422/409 guards, the role/store/auth gates, and a redaction-safe response.
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


_RETURN_KEYS = {
    "id",
    "assignment_id",
    "order_id",
    "driver_profile_id",
    "store_id",
    "driver_user_id",
    "confirmed_by_user_id",
    "return_state",
    "confirmed_at",
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
    "location",
    "gps",
}


def _url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/return-to-store"


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "RTA-Store") -> Store:
        store = Store(name=name, code=f"rta-{uuid.uuid4().hex[:8]}")
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
    state: str | None = State.delivery_failed.value,
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


def test_start_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(
        _url(assignment.id),
        headers=_auth(user),
        json={"action": "start", "note": "heading back"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _RETURN_KEYS
    assert body["return_state"] == "returning"
    assert body["note"] == "heading back"
    assert body["assignment_id"] == str(assignment.id)
    assert body["driver_user_id"] == str(user.id)


def test_arrive_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    client.post(_url(assignment.id), headers=_auth(user), json={"action": "start"})
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "arrive"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["return_state"] == "returned_pending_confirmation"


def test_response_shape_is_driver_delivery_return_read(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    body = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "start"}
    ).json()
    assert set(body.keys()) == _RETURN_KEYS


def test_confirmed_fields_null_in_g(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    client.post(_url(assignment.id), headers=_auth(user), json={"action": "start"})
    body = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "arrive"}
    ).json()
    assert body["confirmed_at"] is None
    assert body["confirmed_by_user_id"] is None
    assert body["return_state"] != "confirmed"


# --------------------------------------------------------------------- #
# Request validation
# --------------------------------------------------------------------- #


def test_missing_action_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(_url(assignment.id), headers=_auth(user), json={})
    assert resp.status_code == 422, resp.text


def test_invalid_action_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "confirm"}
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
        json={"action": "start", "note": "x" * 501},
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------- #


def test_start_requires_failure_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(
        db_session, store, user, state=State.id_verified.value
    )
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "start"}
    )
    assert resp.status_code == 422, resp.text


def test_arrive_before_start_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "arrive"}
    )
    assert resp.status_code == 422, resp.text


def test_repeated_start_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    first = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "start"}
    )
    second = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "start"}
    )
    assert first.status_code == 200
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]


def test_repeated_arrive_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    client.post(_url(assignment.id), headers=_auth(user), json={"action": "start"})
    first = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "arrive"}
    )
    second = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "arrive"}
    )
    assert first.status_code == 200
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]


def test_start_after_arrive_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    client.post(_url(assignment.id), headers=_auth(user), json={"action": "start"})
    client.post(_url(assignment.id), headers=_auth(user), json={"action": "arrive"})
    resp = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "start"}
    )
    assert resp.status_code == 409, resp.text


# --------------------------------------------------------------------- #
# Anti-enumeration / RBAC / auth gates
# --------------------------------------------------------------------- #


def test_foreign_store_driver_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, owner)
    other_store = make_store(name="RTA-Other")
    other = _driver(db_session, other_store)
    make_driver_profile(db_session, user=other, store=other_store)
    resp = client.post(
        _url(assignment.id), headers=_auth(other), json={"action": "start"}
    )
    assert resp.status_code == 404, resp.text


def test_missing_assignment_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)
    resp = client.post(
        _url(uuid.uuid4()), headers=_auth(user), json={"action": "start"}
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
        _url(assignment.id), headers=_auth(staff), json={"action": "start"}
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
        _url(assignment.id), headers=_auth(storeless), json={"action": "start"}
    )
    assert resp.status_code == 403, resp.text


def test_response_no_sensitive_fields(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    body = client.post(
        _url(assignment.id), headers=_auth(user), json={"action": "start"}
    ).json()
    for forbidden in _FORBIDDEN_KEYS:
        assert forbidden not in body, forbidden
