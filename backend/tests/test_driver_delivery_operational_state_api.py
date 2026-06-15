"""Dr.1.1.H — driver delivery operational-state read API tests.

Confirms GET /driver/assignments/{assignment_id}/delivery-state: the success
shape (exactly the 10 read-model fields, no PII), the owned-but-stateless 404,
every self-scope / tenancy anti-enumeration 404, the role/store/auth gates,
that the endpoint never materializes state, and that the /driver/* surface is
now exactly five read-only routes.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalState
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


def _state_url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/delivery-state"


_ALLOWED_KEYS = {
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
    def _create(name: str = "DDOS-Api") -> Store:
        store = Store(name=name, code=f"ddosa-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def _owned_assignment(db_session: Session, store: Store, user: User):
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )
    return profile, order, assignment


# --------------------------------------------------------------------- #
# A. Happy path — 200, exact shape, no PII
# --------------------------------------------------------------------- #


def test_get_state_200_exact_shape(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile, order, assignment = _owned_assignment(db_session, store, user)
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    resp = client.get(_state_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == _ALLOWED_KEYS
    assert body["id"] == str(state.id)
    assert body["assignment_id"] == str(assignment.id)
    assert body["order_id"] == str(order.id)
    assert body["driver_profile_id"] == str(profile.id)
    assert body["store_id"] == str(store.id)
    assert body["state"] == "not_started"


def test_get_state_exposes_no_pii(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)
    make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    resp = client.get(_state_url(assignment.id), headers=_auth(user))
    body = resp.json()
    raw = resp.text
    for forbidden in (
        "user",
        "email",
        "customer",
        "customer_email",
        "customer_phone",
        "phone",
        "order",
        "inventory",
        "product",
        "variant",
        "auth",
        "token",
        "notes",
        "idempotency_key",
        "subtotal_amount",
        "tax_amount",
        "total_amount",
        "address",
    ):
        assert forbidden not in body, forbidden
    # The nested-object keys must not leak via the raw payload either.
    for forbidden in ("customer_email", "customer_phone", "idempotency_key"):
        assert forbidden not in raw, forbidden


# --------------------------------------------------------------------- #
# B. Owned assignment without state -> 404 (does not materialize)
# --------------------------------------------------------------------- #


def test_get_state_404_when_missing(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    resp = client.get(_state_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 404, resp.text
    assert (
        resp.json()["detail"]
        == "Driver delivery operational state not found"
    )

    # Pure read: no state row was created as a side effect.
    count = db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert count == 0


# --------------------------------------------------------------------- #
# C. Nonexistent assignment -> 404 anti-enumeration
# --------------------------------------------------------------------- #


def test_get_state_404_nonexistent_assignment(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)

    resp = client.get(_state_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Driver assignment not found"


# --------------------------------------------------------------------- #
# D. Another driver's assignment -> 404
# --------------------------------------------------------------------- #


def test_get_state_404_other_driver(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(
        db_session, store, owner
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    other = _driver(db_session, store)
    make_driver_profile(db_session, user=other, store=store)

    resp = client.get(_state_url(assignment.id), headers=_auth(other))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Driver assignment not found"


# --------------------------------------------------------------------- #
# E. Another store's assignment -> 404
# --------------------------------------------------------------------- #


def test_get_state_404_other_store(
    client: TestClient, db_session: Session, make_store
) -> None:
    store_a = make_store("store-a")
    owner = _driver(db_session, store_a)
    _profile, _order, assignment = _owned_assignment(
        db_session, store_a, owner
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    store_b = make_store("store-b")
    other = _driver(db_session, store_b)
    make_driver_profile(db_session, user=other, store=store_b)

    resp = client.get(_state_url(assignment.id), headers=_auth(other))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Driver assignment not found"


# --------------------------------------------------------------------- #
# F. Non-driver role -> 403
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role",
    [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
)
def test_get_state_non_driver_403(
    client: TestClient, db_session: Session, make_store, role: UserRole
) -> None:
    store_id = None if role == UserRole.admin else make_store().id
    user = central_make_user(db_session, role=role, store_id=store_id)
    resp = client.get(_state_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# G. Storeless driver -> 403
# --------------------------------------------------------------------- #


def test_get_state_storeless_driver_403(
    client: TestClient, db_session: Session
) -> None:
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    resp = client.get(_state_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# H. Anonymous -> 401
# --------------------------------------------------------------------- #


def test_get_state_anonymous_401(client: TestClient) -> None:
    assert client.get(_state_url(uuid.uuid4())).status_code == 401


# --------------------------------------------------------------------- #
# I. Route surface — exactly five read-only /driver/* routes
# --------------------------------------------------------------------- #


def test_driver_route_surface_reads_plus_accept_decline() -> None:
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
    }

    # The delivery-state read stays GET-only; no mutative method leaks onto it.
    for route in driver_routes:
        methods = set(route.methods)
        assert "PATCH" not in methods
        assert "PUT" not in methods
        assert "DELETE" not in methods
        if route.path.endswith("/delivery-state"):
            assert methods >= {"GET"}
            assert "POST" not in methods
