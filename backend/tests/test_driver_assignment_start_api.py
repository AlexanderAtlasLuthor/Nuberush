"""Dr.1.1.J — driver start-delivery API tests.

Confirms POST /driver/assignments/{id}/start: the 200 happy path and response
shape (DriverDeliveryOperationalStateRead, no PII), idempotency with preserved
timestamps, the anti-enumeration 404s, the role/store/auth gates, the 409/422
guards, and that the /driver surface is now exactly five GETs plus three POSTs
(accept/decline/start).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


def _start_url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/start"


_STATE_KEYS = {
    "id",
    "assignment_id",
    "order_id",
    "driver_profile_id",
    "store_id",
    "state",
    "state_started_at",
    "last_transition_at",
    "created_at",
    "updated_at",
}


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DST-Api") -> Store:
        store = Store(name=name, code=f"dsta-{uuid.uuid4().hex[:8]}")
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
    db_session: Session, store: Store, user: User, status: str = "accepted"
):
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status=status,
    )
    return profile, order, assignment


# --------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------- #


def test_start_200_shape(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile, order, assignment = _owned_assignment(db_session, store, user)

    resp = client.post(_start_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _STATE_KEYS
    assert body["state"] == "en_route_to_store"
    assert body["assignment_id"] == str(assignment.id)
    assert body["order_id"] == str(order.id)
    assert body["driver_profile_id"] == str(profile.id)
    assert body["store_id"] == str(store.id)


def test_start_response_no_pii(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    body = client.post(_start_url(assignment.id), headers=_auth(user)).json()
    for forbidden in (
        "user",
        "email",
        "customer",
        "customer_user_id",
        "customer_email",
        "customer_phone",
        "phone",
        "order",
        "inventory",
        "product",
        "variant",
        "auth",
        "token",
        "total_amount",
        "idempotency_key",
        "address",
    ):
        assert forbidden not in body, forbidden


# --------------------------------------------------------------------- #
# Idempotency through the API
# --------------------------------------------------------------------- #


def test_start_idempotent_preserves_timestamps(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(
        db_session, store, user, status="started"
    )
    started_at = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    transition_at = datetime(2026, 6, 1, 9, 1, tzinfo=timezone.utc)
    make_driver_delivery_operational_state(
        db_session,
        assignment=assignment,
        state="en_route_to_store",
        state_started_at=started_at,
        last_transition_at=transition_at,
    )

    first = client.post(_start_url(assignment.id), headers=_auth(user))
    second = client.post(_start_url(assignment.id), headers=_auth(user))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["state"] == "en_route_to_store"
    assert (
        first.json()["state_started_at"] == second.json()["state_started_at"]
    )
    assert (
        first.json()["last_transition_at"]
        == second.json()["last_transition_at"]
    )


# --------------------------------------------------------------------- #
# 422 / 409 guards
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_status",
    ["offered", "declined", "expired", "canceled", "completed", "assigned"],
)
def test_start_invalid_status_422(
    client: TestClient, db_session: Session, make_store, bad_status: str
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(
        db_session, store, user, status=bad_status
    )
    resp = client.post(_start_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


def test_start_past_en_route_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(
        db_session, store, user, status="started"
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="arrived_at_store"
    )
    resp = client.post(_start_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "Delivery already past en_route_to_store"


def test_start_terminal_state_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(
        db_session, store, user, status="started"
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="delivery_completed"
    )
    resp = client.post(_start_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# Anti-enumeration 404
# --------------------------------------------------------------------- #


def test_start_404_nonexistent(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)
    resp = client.post(_start_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Driver assignment not found"


def test_start_404_other_driver(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, owner)

    other = _driver(db_session, store)
    make_driver_profile(db_session, user=other, store=store)

    resp = client.post(_start_url(assignment.id), headers=_auth(other))
    assert resp.status_code == 404, resp.text


def test_start_404_other_store(
    client: TestClient, db_session: Session, make_store
) -> None:
    store_a = make_store("store-a")
    owner = _driver(db_session, store_a)
    _profile, _order, assignment = _owned_assignment(
        db_session, store_a, owner
    )

    store_b = make_store("store-b")
    other = _driver(db_session, store_b)
    make_driver_profile(db_session, user=other, store=store_b)

    resp = client.post(_start_url(assignment.id), headers=_auth(other))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------- #
# Auth / role / store gates
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role",
    [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
)
def test_start_non_driver_403(
    client: TestClient, db_session: Session, make_store, role: UserRole
) -> None:
    store_id = None if role == UserRole.admin else make_store().id
    user = central_make_user(db_session, role=role, store_id=store_id)
    resp = client.post(_start_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_start_storeless_driver_403(
    client: TestClient, db_session: Session
) -> None:
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    resp = client.post(_start_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_start_anonymous_401(client: TestClient) -> None:
    assert client.post(_start_url(uuid.uuid4())).status_code == 401


# --------------------------------------------------------------------- #
# Route surface — 5 GET + 3 POST
# --------------------------------------------------------------------- #


def test_route_surface_reads_plus_three_actions() -> None:
    from app.main import app

    driver_routes = [
        route
        for route in app.router.routes
        if getattr(route, "path", "").startswith("/driver")
    ]
    surface = {
        (
            next(m for m in route.methods if m not in ("HEAD", "OPTIONS")),
            route.path,
        )
        for route in driver_routes
    }
    assert surface == {
        ("GET", "/driver/me"),
        ("GET", "/driver/eligibility"),
        ("GET", "/driver/assignments"),
        ("GET", "/driver/assignments/{assignment_id}"),
        ("GET", "/driver/assignments/{assignment_id}/delivery-state"),
        ("POST", "/driver/assignments/{assignment_id}/accept"),
        ("POST", "/driver/assignments/{assignment_id}/decline"),
        ("POST", "/driver/assignments/{assignment_id}/start"),
        ("POST", "/driver/assignments/{assignment_id}/arrive-store"),
        ("POST", "/driver/assignments/{assignment_id}/pickup"),
        ("POST", "/driver/assignments/{assignment_id}/depart-to-customer"),
        ("POST", "/driver/assignments/{assignment_id}/arrive-customer"),
        ("POST", "/driver/assignments/{assignment_id}/verify-age"),
        ("POST", "/driver/assignments/{assignment_id}/proof"),
    }
    gets = sum(1 for m, _ in surface if m == "GET")
    posts = sum(1 for m, _ in surface if m == "POST")
    assert gets == 5
    assert posts == 9
    for route in driver_routes:
        methods = set(route.methods)
        assert "PATCH" not in methods
        assert "PUT" not in methods
        assert "DELETE" not in methods
