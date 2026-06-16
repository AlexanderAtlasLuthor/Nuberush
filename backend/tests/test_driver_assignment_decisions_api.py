"""Dr.1.1.I — driver assignment accept/decline API tests.

Confirms POST /driver/assignments/{id}/accept and .../decline: the 200 happy
paths and response shape, the anti-enumeration 404s, the role/store/auth
gates, the 409 conflict and 422 invalid-transition paths, API-level
idempotency, the PII boundary, and that the /driver surface is now exactly
five GETs plus the two approved POSTs.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


def _accept_url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/accept"


def _decline_url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/decline"


_ASSIGNMENT_KEYS = {
    "id",
    "order_id",
    "store_id",
    "driver_profile_id",
    "status",
    "assigned_at",
    "accepted_at",
    "declined_at",
    "canceled_at",
    "completed_at",
    "created_at",
    "updated_at",
    "order",
    "store",
}


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DAD-Api") -> Store:
        store = Store(name=name, code=f"dada-{uuid.uuid4().hex[:8]}")
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
    db_session: Session, store: Store, user: User, status: str = "offered"
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
# A/B. Happy paths
# --------------------------------------------------------------------- #


def test_accept_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    resp = client.post(_accept_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _ASSIGNMENT_KEYS
    assert body["id"] == str(assignment.id)
    assert body["status"] == "accepted"
    assert body["accepted_at"] is not None
    assert body["declined_at"] is None


def test_decline_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    resp = client.post(_decline_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _ASSIGNMENT_KEYS
    assert body["status"] == "declined"
    assert body["declined_at"] is not None
    assert body["accepted_at"] is None


# --------------------------------------------------------------------- #
# C. Anti-enumeration 404
# --------------------------------------------------------------------- #


def test_accept_404_nonexistent(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)
    resp = client.post(_accept_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Driver assignment not found"


def test_accept_404_other_driver(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, owner)

    other = _driver(db_session, store)
    make_driver_profile(db_session, user=other, store=store)

    resp = client.post(_accept_url(assignment.id), headers=_auth(other))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Driver assignment not found"


def test_decline_404_other_store(
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

    resp = client.post(_decline_url(assignment.id), headers=_auth(other))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Driver assignment not found"


# --------------------------------------------------------------------- #
# D. Role / store / auth gates
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role",
    [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
)
def test_non_driver_403(
    client: TestClient, db_session: Session, make_store, role: UserRole
) -> None:
    store_id = None if role == UserRole.admin else make_store().id
    user = central_make_user(db_session, role=role, store_id=store_id)
    aid = uuid.uuid4()
    assert (
        client.post(_accept_url(aid), headers=_auth(user)).status_code == 403
    )
    assert (
        client.post(_decline_url(aid), headers=_auth(user)).status_code
        == 403
    )


def test_storeless_driver_403(
    client: TestClient, db_session: Session
) -> None:
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    aid = uuid.uuid4()
    assert (
        client.post(_accept_url(aid), headers=_auth(user)).status_code == 403
    )
    assert (
        client.post(_decline_url(aid), headers=_auth(user)).status_code
        == 403
    )


def test_anonymous_401(client: TestClient) -> None:
    aid = uuid.uuid4()
    assert client.post(_accept_url(aid)).status_code == 401
    assert client.post(_decline_url(aid)).status_code == 401


# --------------------------------------------------------------------- #
# E. Conflict (409)
# --------------------------------------------------------------------- #


def test_accept_after_decline_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    assert (
        client.post(
            _decline_url(assignment.id), headers=_auth(user)
        ).status_code
        == 200
    )
    resp = client.post(_accept_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "Assignment already declined"


def test_decline_after_accept_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    assert (
        client.post(
            _accept_url(assignment.id), headers=_auth(user)
        ).status_code
        == 200
    )
    resp = client.post(_decline_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "Assignment already accepted"


# --------------------------------------------------------------------- #
# F. Invalid transition (422)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_status",
    ["expired", "canceled", "completed", "started", "assigned"],
)
def test_accept_invalid_transition_422(
    client: TestClient, db_session: Session, make_store, bad_status: str
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(
        db_session, store, user, status=bad_status
    )
    resp = client.post(_accept_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "bad_status",
    ["expired", "canceled", "completed", "started", "assigned"],
)
def test_decline_invalid_transition_422(
    client: TestClient, db_session: Session, make_store, bad_status: str
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(
        db_session, store, user, status=bad_status
    )
    resp = client.post(_decline_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# G. API-level idempotency
# --------------------------------------------------------------------- #


def test_double_accept_idempotent_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    first = client.post(_accept_url(assignment.id), headers=_auth(user))
    second = client.post(_accept_url(assignment.id), headers=_auth(user))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["accepted_at"] == first.json()["accepted_at"]
    assert second.json()["status"] == "accepted"


def test_double_decline_idempotent_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    first = client.post(_decline_url(assignment.id), headers=_auth(user))
    second = client.post(_decline_url(assignment.id), headers=_auth(user))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["declined_at"] == first.json()["declined_at"]
    assert second.json()["status"] == "declined"


# --------------------------------------------------------------------- #
# H. PII boundary
# --------------------------------------------------------------------- #


def test_response_exposes_no_pii(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _profile, _order, assignment = _owned_assignment(db_session, store, user)

    body = client.post(
        _accept_url(assignment.id), headers=_auth(user)
    ).json()
    for forbidden in (
        "user",
        "email",
        "customer",
        "customer_user_id",
        "customer_email",
        "customer_phone",
        "phone",
        "inventory",
        "product",
        "variant",
        "auth",
        "token",
        "subtotal_amount",
        "tax_amount",
        "total_amount",
        "idempotency_key",
        "notes",
        "address",
    ):
        assert forbidden not in body, forbidden
    # The nested order summary stays PII-free too.
    for forbidden in ("customer_user_id", "idempotency_key", "notes"):
        assert forbidden not in body["order"], forbidden


# --------------------------------------------------------------------- #
# I. Route surface — exactly 5 GET + 2 POST
# --------------------------------------------------------------------- #


def test_route_surface_reads_plus_accept_decline_start() -> None:
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
        ("POST", "/driver/assignments/{assignment_id}/complete"),
        ("POST", "/driver/assignments/{assignment_id}/fail"),
    }

    posts = {p for m, p in surface if m == "POST"}
    assert posts == {
        "/driver/assignments/{assignment_id}/accept",
        "/driver/assignments/{assignment_id}/decline",
        "/driver/assignments/{assignment_id}/start",
        "/driver/assignments/{assignment_id}/arrive-store",
        "/driver/assignments/{assignment_id}/pickup",
        "/driver/assignments/{assignment_id}/depart-to-customer",
        "/driver/assignments/{assignment_id}/arrive-customer",
        "/driver/assignments/{assignment_id}/verify-age",
        "/driver/assignments/{assignment_id}/proof",
        "/driver/assignments/{assignment_id}/complete",
        "/driver/assignments/{assignment_id}/fail",
    }
    for route in driver_routes:
        methods = set(route.methods)
        assert "PATCH" not in methods
        assert "PUT" not in methods
        assert "DELETE" not in methods
