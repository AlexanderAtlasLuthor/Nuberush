"""Dr.1.2.I.b — confirm-driver-return idempotency ledger pilot (API + service).

Exercises the only wired ledger action, ``delivery_return_confirmed``, on
POST /orders/{order_id}/confirm-driver-return:

- no-header baseline is exactly H/I.a;
- a valid Idempotency-Key creates a completed ledger row (ref + 200 + 64-char
  hash, no raw body/response stored);
- replay (same key + payload + scope) returns 200 by reloading from reference
  without a second reservation release, quantity_on_hand change, duplicate
  OrderAuditLog, or duplicate operational_audit row;
- reused key with a changed body / different scope / still-pending → 409;
- malformed key → 400.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverComplianceIdempotencyKey
from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryReturn
from app.db.models import DriverDeliveryReturnState
from app.db.models import InventoryItem
from app.db.models import OperationalAuditLog
from app.db.models import Order
from app.db.models import OrderAuditLog
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


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "IBR-Store") -> Store:
        store = Store(name=name, code=f"ibr-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _build_returned_order(db_session: Session, store: Store):
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
        idempotency_key=f"ibr-{uuid.uuid4().hex}",
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
    return order, assignment, item


def _url(order_id) -> str:
    return f"/orders/{order_id}/confirm-driver-return"


def _manager(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.manager, store_id=store.id
    )


def _ledger_rows(db_session, order_id):
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(DriverComplianceIdempotencyKey).where(
                DriverComplianceIdempotencyKey.order_id == order_id
            )
        )
    )


# --------------------------------------------------------------------- #
# No-header baseline (H / I.a unchanged)
# --------------------------------------------------------------------- #


def test_no_header_baseline_works_and_writes_no_ledger(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, item = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id),
        headers=_auth(actor),
        json={"received_confirmed": True, "note": "received"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order"]["status"] == "canceled"
    assert body["driver_return"]["return_state"] == "confirmed"
    assert _ledger_rows(db_session, order.id) == []
    db_session.refresh(item)
    assert item.quantity_reserved == 0
    assert item.quantity_on_hand == 10


# --------------------------------------------------------------------- #
# New key
# --------------------------------------------------------------------- #


def test_valid_key_creates_completed_ledger_row(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, assignment, _item = _build_returned_order(db_session, store)
    key = f"ik-{uuid.uuid4().hex}"
    resp = client.post(
        _url(order.id),
        headers={**_auth(actor), "Idempotency-Key": key},
        json={"received_confirmed": True},
    )
    assert resp.status_code == 200, resp.text
    rows = _ledger_rows(db_session, order.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "completed"
    assert row.action == "delivery_return_confirmed"
    assert row.idempotency_key == key
    assert row.store_id == store.id
    assert row.actor_user_id == actor.id
    assert row.assignment_id == assignment.id
    assert row.response_ref_id == order.id
    assert row.response_status_code == 200
    assert row.completed_at is not None
    assert len(row.request_hash) == 64


# --------------------------------------------------------------------- #
# Replay
# --------------------------------------------------------------------- #


def test_replay_same_key_same_payload_returns_200_no_side_effects(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, assignment, item = _build_returned_order(db_session, store)
    key = f"ik-{uuid.uuid4().hex}"
    headers = {**_auth(actor), "Idempotency-Key": key}
    body = {"received_confirmed": True}

    first = client.post(_url(order.id), headers=headers, json=body)
    assert first.status_code == 200, first.text

    # Snapshot post-first-call inventory + audit counts.
    db_session.expire_all()

    def _count(model, **w):
        stmt = select(func.count()).select_from(model)
        for col, val in w.items():
            stmt = stmt.where(getattr(model, col) == val)
        return db_session.scalar(stmt)

    order_audits_before = _count(
        OrderAuditLog, order_id=order.id, new_status=OrderStatus.canceled
    )
    op_audits_before = _count(
        OperationalAuditLog,
        target_id=assignment.id,
        action="delivery_return_confirmed",
    )

    second = client.post(_url(order.id), headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["order"]["status"] == "canceled"
    assert second.json()["driver_return"]["return_state"] == "confirmed"

    # Exactly one ledger row; no second release; no duplicate audits.
    assert len(_ledger_rows(db_session, order.id)) == 1
    db_session.refresh(item)
    assert item.quantity_reserved == 0
    assert item.quantity_on_hand == 10
    assert (
        _count(
            OrderAuditLog,
            order_id=order.id,
            new_status=OrderStatus.canceled,
        )
        == order_audits_before
        == 1
    )
    assert (
        _count(
            OperationalAuditLog,
            target_id=assignment.id,
            action="delivery_return_confirmed",
        )
        == op_audits_before
        == 1
    )


# --------------------------------------------------------------------- #
# Conflicts (409) and invalid key (400)
# --------------------------------------------------------------------- #


def test_same_key_changed_body_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _i = _build_returned_order(db_session, store)
    key = f"ik-{uuid.uuid4().hex}"
    headers = {**_auth(actor), "Idempotency-Key": key}
    first = client.post(
        _url(order.id), headers=headers, json={"received_confirmed": True}
    )
    assert first.status_code == 200, first.text
    second = client.post(
        _url(order.id),
        headers=headers,
        json={"received_confirmed": True, "note": "different body"},
    )
    assert second.status_code == 409, second.text


def test_same_key_different_actor_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _i = _build_returned_order(db_session, store)
    key = f"ik-{uuid.uuid4().hex}"
    first = client.post(
        _url(order.id),
        headers={**_auth(actor), "Idempotency-Key": key},
        json={"received_confirmed": True},
    )
    assert first.status_code == 200, first.text
    other = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )
    second = client.post(
        _url(order.id),
        headers={**_auth(other), "Idempotency-Key": key},
        json={"received_confirmed": True},
    )
    assert second.status_code == 409, second.text


def test_same_key_different_order_scope_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order_a, _a, _i = _build_returned_order(db_session, store)
    order_b, _b, _j = _build_returned_order(db_session, store)
    key = f"ik-{uuid.uuid4().hex}"
    first = client.post(
        _url(order_a.id),
        headers={**_auth(actor), "Idempotency-Key": key},
        json={"received_confirmed": True},
    )
    assert first.status_code == 200, first.text
    # Same key reused for a different order in the same store -> scope 409.
    second = client.post(
        _url(order_b.id),
        headers={**_auth(actor), "Idempotency-Key": key},
        json={"received_confirmed": True},
    )
    assert second.status_code == 409, second.text


def test_pending_key_in_progress_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, assignment, _i = _build_returned_order(db_session, store)
    key = f"ik-{uuid.uuid4().hex}"
    # Seed a pending claim for this exact scope (a request already in flight).
    db_session.add(
        DriverComplianceIdempotencyKey(
            idempotency_key=key,
            action="delivery_return_confirmed",
            actor_user_id=actor.id,
            store_id=store.id,
            order_id=order.id,
            assignment_id=assignment.id,
            request_hash="a" * 64,
            state="pending",
        )
    )
    db_session.commit()
    resp = client.post(
        _url(order.id),
        headers={**_auth(actor), "Idempotency-Key": key},
        json={"received_confirmed": True},
    )
    assert resp.status_code == 409, resp.text


# Control-char rejection is covered at the unit level (a control char cannot
# be transmitted through the HTTP header layer); here we use HTTP-valid keys
# that the service must still reject.
def test_business_gate_failure_leaves_no_ledger_row(
    client: TestClient, db_session: Session, make_store
) -> None:
    """If the business mutation is rejected by a gate, the pending claim is
    rolled back in the same transaction — no orphan ledger row persists."""
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _i = _build_returned_order(db_session, store)
    # Push the custody record out of returned_pending_confirmation so the
    # confirm gate raises a 409 after the claim is provisionally inserted.
    dr = db_session.scalar(
        select(DriverDeliveryReturn).where(
            DriverDeliveryReturn.order_id == order.id
        )
    )
    dr.return_state = DriverDeliveryReturnState.returning.value
    db_session.commit()
    resp = client.post(
        _url(order.id),
        headers={**_auth(actor), "Idempotency-Key": f"ik-{uuid.uuid4().hex}"},
        json={"received_confirmed": True},
    )
    assert resp.status_code == 409, resp.text
    assert _ledger_rows(db_session, order.id) == []


def test_fresh_key_on_already_confirmed_returns_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    """A brand-new key on an already-confirmed (no-key) return still replays
    the 200 via the preserved state-inferred path; the provisional claim is
    rolled back (no second release / duplicate)."""
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, item = _build_returned_order(db_session, store)
    first = client.post(
        _url(order.id),
        headers=_auth(actor),
        json={"received_confirmed": True},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        _url(order.id),
        headers={**_auth(actor), "Idempotency-Key": f"ik-{uuid.uuid4().hex}"},
        json={"received_confirmed": True},
    )
    assert second.status_code == 200, second.text
    assert second.json()["order"]["status"] == "canceled"
    db_session.refresh(item)
    assert item.quantity_reserved == 0
    assert item.quantity_on_hand == 10


@pytest.mark.parametrize("bad_key", ["", "   ", "has space", "x" * 256])
def test_invalid_key_400(
    client: TestClient, db_session: Session, make_store, bad_key: str
) -> None:
    store = make_store()
    actor = _manager(db_session, store)
    order, _a, _i = _build_returned_order(db_session, store)
    resp = client.post(
        _url(order.id),
        headers={**_auth(actor), "Idempotency-Key": bad_key},
        json={"received_confirmed": True},
    )
    assert resp.status_code == 400, resp.text
    # A rejected key writes no ledger row and does not confirm the order.
    assert _ledger_rows(db_session, order.id) == []
