"""Dr.1.1.F — driver assigned-delivery read API tests.

Confirms GET /driver/assignments and GET /driver/assignments/{id}: success
shapes, the envelope, every self-scope / tenancy 404 boundary, the role gate,
the status/limit/offset query params and their validation, the strict PII
boundary (no customer identity, money, items, address, notes, etc.), and that
the /driver/* surface stays exactly four read-only routes.
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


_LIST_URL = "/driver/assignments"


def _item_url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}"


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DAS-Api") -> Store:
        store = Store(name=name, code=f"dasa-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


# --------------------------------------------------------------------- #
# 1-2. List success + envelope shape
# --------------------------------------------------------------------- #


def test_list_200_for_valid_driver(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    resp = client.get(_LIST_URL, headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == {"items", "total", "limit", "offset"}
    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert [i["id"] for i in body["items"]] == [str(assignment.id)]


# --------------------------------------------------------------------- #
# 3-6. Item endpoint + self-scope / tenancy boundaries
# --------------------------------------------------------------------- #


def test_get_own_assignment_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    resp = client.get(_item_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(assignment.id)
    assert body["order_id"] == str(order.id)
    assert body["store_id"] == str(store.id)
    assert body["driver_profile_id"] == str(profile.id)
    assert body["order"]["id"] == str(order.id)
    assert body["store"]["id"] == str(store.id)


def test_cannot_get_other_drivers_assignment(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    make_driver_profile(db_session, user=me, store=store)

    other = _driver(db_session, store)
    other_profile = make_driver_profile(db_session, user=other, store=store)
    other_order = make_order(db_session, store=store)
    other_assignment = make_order_driver_assignment(
        db_session,
        order=other_order,
        driver_profile=other_profile,
        store=store,
    )

    resp = client.get(_item_url(other_assignment.id), headers=_auth(me))
    assert resp.status_code == 404, resp.text

    # And it never appears in the list view.
    listed = client.get(_LIST_URL, headers=_auth(me)).json()
    assert listed["items"] == []
    assert listed["total"] == 0


def test_cannot_get_other_store_assignment(
    client: TestClient, db_session: Session, make_store
) -> None:
    store_a = make_store("store-a")
    me = _driver(db_session, store_a)
    my_profile = make_driver_profile(db_session, user=me, store=store_a)

    store_b = make_store("store-b")
    order_b = make_order(db_session, store=store_b)
    foreign = make_order_driver_assignment(
        db_session,
        order=order_b,
        driver_profile=my_profile,
        store=store_b,
    )

    resp = client.get(_item_url(foreign.id), headers=_auth(me))
    assert resp.status_code == 404, resp.text


def test_get_nonexistent_assignment_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)

    resp = client.get(_item_url(uuid.uuid4()), headers=_auth(user))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------- #
# 7-8. Role gate + missing profile
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role",
    [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
)
def test_non_driver_blocked(
    client: TestClient, db_session: Session, make_store, role: UserRole
) -> None:
    store_id = None if role == UserRole.admin else make_store().id
    user = central_make_user(db_session, role=role, store_id=store_id)
    assert client.get(_LIST_URL, headers=_auth(user)).status_code == 403
    assert (
        client.get(_item_url(uuid.uuid4()), headers=_auth(user)).status_code
        == 403
    )


def test_driver_without_profile_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)

    assert client.get(_LIST_URL, headers=_auth(user)).status_code == 404
    assert (
        client.get(_item_url(uuid.uuid4()), headers=_auth(user)).status_code
        == 404
    )


def test_anonymous_401(client: TestClient) -> None:
    assert client.get(_LIST_URL).status_code == 401


# --------------------------------------------------------------------- #
# 9-11. Query params: status, limit/offset, validation
# --------------------------------------------------------------------- #


def test_status_query_param(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)

    active = make_order_driver_assignment(
        db_session,
        order=make_order(db_session, store=store),
        driver_profile=profile,
        store=store,
        status="assigned",
    )
    completed = make_order_driver_assignment(
        db_session,
        order=make_order(db_session, store=store),
        driver_profile=profile,
        store=store,
        status="completed",
    )

    # Default excludes the terminal one.
    default_ids = {
        i["id"] for i in client.get(_LIST_URL, headers=_auth(user)).json()["items"]
    }
    assert str(active.id) in default_ids
    assert str(completed.id) not in default_ids

    # Explicit completed filter returns only the terminal one.
    resp = client.get(
        _LIST_URL, headers=_auth(user), params={"status": "completed"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [i["id"] for i in body["items"]] == [str(completed.id)]
    assert body["total"] == 1


def test_limit_and_offset(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)
    for _ in range(3):
        make_order_driver_assignment(
            db_session,
            order=make_order(db_session, store=store),
            driver_profile=profile,
            store=store,
            status="assigned",
        )

    page1 = client.get(
        _LIST_URL, headers=_auth(user), params={"limit": 2, "offset": 0}
    ).json()
    page2 = client.get(
        _LIST_URL, headers=_auth(user), params={"limit": 2, "offset": 2}
    ).json()

    assert page1["total"] == 3
    assert page1["limit"] == 2
    assert page1["offset"] == 0
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"status": "not-a-status"},
        {"status": "delivered"},  # a delivery state, not an assignment state
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
    ],
)
def test_invalid_query_params_422(
    client: TestClient, db_session: Session, make_store, params
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)

    resp = client.get(_LIST_URL, headers=_auth(user), params=params)
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# 12-20. PII boundary — list + item expose only the allowed keys
# --------------------------------------------------------------------- #


_ALLOWED_ASSIGNMENT_KEYS = {
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

_ALLOWED_ORDER_KEYS = {
    "id",
    "status",
    "created_at",
    "updated_at",
    "accepted_at",
    "canceled_at",
    "delivered_at",
    "returned_at",
}

_ALLOWED_STORE_KEYS = {"id", "name", "code", "timezone"}

_FORBIDDEN_KEYS = {
    "customer_user_id",
    "customer",
    "email",
    "phone",
    "full_name",
    "notes",
    "cancel_reason",
    "idempotency_key",
    "subtotal_amount",
    "subtotal",
    "tax_amount",
    "tax",
    "total_amount",
    "items",
    "address",
    "age_verified_by_user_id",
    "age_verified_at",
}


def test_response_exposes_only_allowed_keys(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    item = client.get(_item_url(assignment.id), headers=_auth(user)).json()
    assert set(item.keys()) == _ALLOWED_ASSIGNMENT_KEYS
    assert set(item["order"].keys()) == _ALLOWED_ORDER_KEYS
    assert set(item["store"].keys()) == _ALLOWED_STORE_KEYS

    list_item = client.get(_LIST_URL, headers=_auth(user)).json()["items"][0]
    assert set(list_item.keys()) == _ALLOWED_ASSIGNMENT_KEYS


def test_response_contains_no_pii_or_money(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    # Inspect the raw serialized payload at every level.
    raw = client.get(_item_url(assignment.id), headers=_auth(user)).text
    item = client.get(_item_url(assignment.id), headers=_auth(user)).json()

    blobs = [item, item["order"], item["store"]]
    for blob in blobs:
        for forbidden in _FORBIDDEN_KEYS:
            assert forbidden not in blob, forbidden

    # Belt-and-suspenders: the literal keys never appear anywhere in the body.
    for forbidden in (
        "customer_user_id",
        "idempotency_key",
        "cancel_reason",
        "subtotal_amount",
        "tax_amount",
        "total_amount",
    ):
        assert forbidden not in raw, forbidden


# --------------------------------------------------------------------- #
# 21-22. Route surface — exactly four read-only /driver/* routes
# --------------------------------------------------------------------- #


def test_driver_route_surface_is_reads_plus_accept_decline_start() -> None:
    """After Dr.1.1.M the /driver surface is five read-only GETs plus exactly
    six mutations: POST .../accept, .../decline, .../start, .../arrive-store,
    .../pickup and .../depart-to-customer."""
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
    }

    # No PATCH/PUT/DELETE anywhere on the /driver surface.
    for route in driver_routes:
        methods = set(route.methods)
        assert "PATCH" not in methods
        assert "PUT" not in methods
        assert "DELETE" not in methods


def test_no_mutative_or_operational_driver_routes() -> None:
    from app.main import app

    driver_paths = {
        route.path
        for route in app.router.routes
        if getattr(route, "path", "").startswith("/driver")
    }
    # accept/decline/start/arrive-store/pickup/depart-to-customer may appear
    # ONLY in their six approved exact paths.
    approved_actions = {
        "/driver/assignments/{assignment_id}/accept",
        "/driver/assignments/{assignment_id}/decline",
        "/driver/assignments/{assignment_id}/start",
        "/driver/assignments/{assignment_id}/arrive-store",
        "/driver/assignments/{assignment_id}/pickup",
        "/driver/assignments/{assignment_id}/depart-to-customer",
    }
    for p in driver_paths:
        if (
            "accept" in p
            or "decline" in p
            or "start" in p
            or "arrive" in p
            or "pickup" in p
            or "depart" in p
        ):
            assert p in approved_actions, p
    # None of the deferred operational / mutative surfaces exist yet. Depart
    # (picked_up -> en_route_to_customer) is approved in M, but the
    # en_route_to_customer successor states and everything downstream of it
    # remain banned.
    for banned_substr in (
        "online",
        "offline",
        "active-delivery",
        "active_delivery",
        "dispatch",
        "proof",
        "picked-up",
        "picked_up",
        "en-route-to-customer",
        "en_route_to_customer",
        "arrive-customer",
        "arrived-at-customer",
        "verify-age",
        "verify-id",
        "id-verification",
        "dropoff",
        "complete",
        "fail",
        "return-to-store",
        "returned-to-store",
        "location",
        "gps",
        "geofence",
        "earnings",
        "payout",
    ):
        assert not any(banned_substr in p for p in driver_paths), banned_substr
