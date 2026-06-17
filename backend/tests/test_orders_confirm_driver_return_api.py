"""Dr.1.2.H — store return confirmation API tests.

Confirms POST /orders/{order_id}/confirm-driver-return: the 200 composite
happy path (order canceled + driver_return confirmed), request validation,
RBAC (manager/owner/admin allowed; staff/driver/foreign-store forbidden), the
404 anti-enumeration, idempotency, and a redaction-safe response.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryReturn
from app.db.models import DriverDeliveryReturnState
from app.db.models import InventoryItem
from app.db.models import Order
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order_driver_assignment


_RESPONSE_TOP_KEYS = {"order", "driver_return"}

_FORBIDDEN_KEYS = {
    "raw_id",
    "dob",
    "license",
    "license_number",
    "photo",
    "signature",
    "ocr",
    "barcode",
    "customer_photo",
    "artifact_url",
    "image_path",
    "id_number",
    "gps",
    "location",
}


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "HCA-Store") -> Store:
        store = Store(name=name, code=f"hca-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _build_returned_order(db_session: Session, store: Store):
    """Build a returned-pending-confirmation order in `store`. Returns
    (order, assignment, driver_return)."""
    driver_user = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    profile = make_driver_profile(db_session, user=driver_user, store=store)
    product = Product(name=f"Vape {uuid.uuid4().hex[:6]}", category="vape")
    db_session.add(product)
    db_session.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku=f"sku-{uuid.uuid4().hex[:8]}",
        price=Decimal("10.00"),
    )
    db_session.add(variant)
    db_session.flush()
    item = InventoryItem(
        store_id=store.id,
        variant_id=variant.id,
        quantity_on_hand=10,
        quantity_reserved=2,
    )
    db_session.add(item)
    db_session.flush()
    order = Order(
        store_id=store.id,
        idempotency_key=f"hca-{uuid.uuid4().hex}",
        status=OrderStatus.out_for_delivery,
        subtotal_amount=Decimal("20.00"),
        total_amount=Decimal("20.00"),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            variant_id=variant.id,
            inventory_item_id=item.id,
            quantity=2,
            unit_price=Decimal("10.00"),
            line_total=Decimal("20.00"),
        )
    )
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status="started",
    )
    make_driver_delivery_operational_state(
        db_session,
        assignment=assignment,
        state=State.returned_to_store.value,
    )
    driver_return = DriverDeliveryReturn(
        assignment_id=assignment.id,
        order_id=order.id,
        driver_profile_id=profile.id,
        store_id=store.id,
        driver_user_id=driver_user.id,
        return_state=(
            DriverDeliveryReturnState.returned_pending_confirmation.value
        ),
        note="returned by driver",
    )
    db_session.add(driver_return)
    db_session.commit()
    db_session.refresh(order)
    db_session.refresh(assignment)
    db_session.refresh(driver_return)
    return order, assignment, driver_return


def _url(order_id) -> str:
    return f"/orders/{order_id}/confirm-driver-return"


def _manager(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.manager, store_id=store.id
    )


# --------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------- #


def test_confirm_200_composite_shape(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id),
        headers=_auth(actor),
        json={"received_confirmed": True, "note": "received"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _RESPONSE_TOP_KEYS
    assert body["order"]["status"] == "canceled"
    assert body["driver_return"]["return_state"] == "confirmed"
    assert body["driver_return"]["confirmed_at"] is not None
    assert body["driver_return"]["confirmed_by_user_id"] == str(actor.id)


# --------------------------------------------------------------------- #
# Request validation
# --------------------------------------------------------------------- #


def test_received_confirmed_false_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id),
        headers=_auth(actor),
        json={"received_confirmed": False},
    )
    assert resp.status_code == 422, resp.text


def test_missing_received_confirmed_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(_url(order.id), headers=_auth(actor), json={})
    assert resp.status_code == 422, resp.text


def test_note_too_long_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id),
        headers=_auth(actor),
        json={"received_confirmed": True, "note": "x" * 501},
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# RBAC / tenancy
# --------------------------------------------------------------------- #


def test_manager_confirms_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = central_make_user(
        db_session, role=UserRole.manager, store_id=store.id
    )
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id), headers=_auth(actor), json={"received_confirmed": True}
    )
    assert resp.status_code == 200, resp.text


def test_owner_confirms_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id), headers=_auth(actor), json={"received_confirmed": True}
    )
    assert resp.status_code == 200, resp.text


def test_admin_cross_store_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    admin = central_make_user(db_session, role=UserRole.admin, store_id=None)
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id), headers=_auth(admin), json={"received_confirmed": True}
    )
    assert resp.status_code == 200, resp.text


def test_staff_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    staff = central_make_user(
        db_session, role=UserRole.staff, store_id=store.id
    )
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id), headers=_auth(staff), json={"received_confirmed": True}
    )
    assert resp.status_code == 403, resp.text


def test_driver_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    driver = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id), headers=_auth(driver), json={"received_confirmed": True}
    )
    assert resp.status_code == 403, resp.text


def test_foreign_store_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    other_store = make_store(name="HCA-Other")
    foreign_manager = central_make_user(
        db_session, role=UserRole.manager, store_id=other_store.id
    )
    order, _a, _dr = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id),
        headers=_auth(foreign_manager),
        json={"received_confirmed": True},
    )
    assert resp.status_code == 403, resp.text


def test_missing_order_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    resp = client.post(
        _url(uuid.uuid4()),
        headers=_auth(actor),
        json={"received_confirmed": True},
    )
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------- #
# Idempotency + redaction
# --------------------------------------------------------------------- #


def test_repeat_confirm_200_idempotent(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _dr = _build_returned_order(db_session, store)
    first = client.post(
        _url(order.id), headers=_auth(actor), json={"received_confirmed": True}
    )
    second = client.post(
        _url(order.id), headers=_auth(actor), json={"received_confirmed": True}
    )
    assert first.status_code == 200
    assert second.status_code == 200, second.text
    assert second.json()["order"]["status"] == "canceled"
    assert second.json()["driver_return"]["return_state"] == "confirmed"


def test_response_no_sensitive_fields(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _dr = _build_returned_order(db_session, store)
    dr_body = client.post(
        _url(order.id), headers=_auth(actor), json={"received_confirmed": True}
    ).json()["driver_return"]
    for forbidden in _FORBIDDEN_KEYS:
        assert forbidden not in dr_body, forbidden
