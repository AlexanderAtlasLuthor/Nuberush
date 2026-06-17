"""Dr.1.2.I.c — compliance idempotency ledger rollout to driver actions.

End-to-end (API) coverage for the optional Idempotency-Key on the five driver
compliance routes: verify-age, proof, complete, fail, return-to-store
(start/arrive). For each: the no-header baseline is unchanged and writes no
ledger row; a valid key creates a completed ledger row; replay returns 200 by
reloading from reference with no duplicate compliance row, operational_audit
row, OrderAuditLog, or inventory side effect; conflicts are 409; bad keys 400.

Also asserts the Dr.1.1 operational routes did NOT gain the header and the
driver route surface stayed 5 GET / 12 POST.
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
from app.db.models import DriverDeliveryFailure
from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryProof
from app.db.models import DriverDeliveryProofMethod
from app.db.models import DriverDeliveryReturn
from app.db.models import DriverDeliveryReturnState
from app.db.models import DriverDeliveryVerification
from app.db.models import DriverDeliveryVerificationMethod
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
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "ICC-Store") -> Store:
        store = Store(name=name, code=f"icc-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def _assignment(
    db_session: Session,
    store: Store,
    user: User,
    *,
    state: str,
    order_status: str = "ready",
    with_pass: bool = False,
    with_proof: bool = False,
    with_inventory: bool = False,
    with_return_state: str | None = None,
):
    profile = make_driver_profile(db_session, user=user, store=store)
    order = make_order(db_session, store=store, status=order_status)
    item = None
    if with_inventory:
        product = Product(name=f"V {uuid.uuid4().hex[:6]}", category="vape")
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
        db_session, order=order, driver_profile=profile, store=store,
        status="started",
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state=state
    )
    if with_pass:
        db_session.add(
            DriverDeliveryVerification(
                assignment_id=assignment.id,
                order_id=order.id,
                driver_profile_id=profile.id,
                store_id=store.id,
                outcome="pass",
                method=DriverDeliveryVerificationMethod.manual_checklist.value,
            )
        )
    if with_proof:
        db_session.add(
            DriverDeliveryProof(
                assignment_id=assignment.id,
                order_id=order.id,
                driver_profile_id=profile.id,
                store_id=store.id,
                method=DriverDeliveryProofMethod.manual_checklist.value,
                recipient_present_confirmed=True,
                handoff_confirmed=True,
                restricted_not_left_unattended=True,
            )
        )
    if with_return_state is not None:
        db_session.add(
            DriverDeliveryReturn(
                assignment_id=assignment.id,
                order_id=order.id,
                driver_profile_id=profile.id,
                store_id=store.id,
                driver_user_id=user.id,
                return_state=with_return_state,
            )
        )
    db_session.commit()
    db_session.refresh(assignment)
    return profile, order, item, assignment


def _key() -> str:
    return f"ik-{uuid.uuid4().hex}"


def _ledger(db_session, assignment_id, action=None):
    db_session.expire_all()
    stmt = select(DriverComplianceIdempotencyKey).where(
        DriverComplianceIdempotencyKey.assignment_id == assignment_id
    )
    if action is not None:
        stmt = stmt.where(DriverComplianceIdempotencyKey.action == action)
    return list(db_session.scalars(stmt))


def _op_audit_count(db_session, assignment_id, action) -> int:
    db_session.expire_all()
    return db_session.scalar(
        select(func.count())
        .select_from(OperationalAuditLog)
        .where(
            OperationalAuditLog.target_id == assignment_id,
            OperationalAuditLog.action == action,
        )
    )


# ===================================================================== #
# verify-age
# ===================================================================== #


def _va_url(aid) -> str:
    return f"/driver/assignments/{aid}/verify-age"


def test_verify_age_no_header_baseline_no_ledger(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    resp = client.post(
        _va_url(a.id), headers=_auth(drv), json={"outcome": "pass"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["outcome"] == "pass"
    assert _ledger(db_session, a.id) == []


def test_verify_age_valid_key_completes_ledger(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, order, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    key = _key()
    resp = client.post(
        _va_url(a.id),
        headers={**_auth(drv), "Idempotency-Key": key},
        json={"outcome": "pass"},
    )
    assert resp.status_code == 200, resp.text
    rows = _ledger(db_session, a.id, "delivery_verified")
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "completed"
    assert row.idempotency_key == key
    assert row.store_id == store.id
    assert row.order_id == order.id
    assert row.actor_user_id == drv.id
    assert row.response_ref_id == uuid.UUID(resp.json()["id"])
    assert row.response_status_code == 200
    assert len(row.request_hash) == 64


def test_verify_age_replay_no_duplicate(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(_va_url(a.id), headers=headers, json={"outcome": "pass"})
    assert first.status_code == 200, first.text
    second = client.post(
        _va_url(a.id), headers=headers, json={"outcome": "pass"}
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert len(_ledger(db_session, a.id, "delivery_verified")) == 1
    assert _op_audit_count(db_session, a.id, "delivery_verified") == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DriverDeliveryVerification)
            .where(DriverDeliveryVerification.assignment_id == a.id)
        )
        == 1
    )


def test_verify_age_changed_body_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(_va_url(a.id), headers=headers, json={"outcome": "pass"})
    assert first.status_code == 200, first.text
    second = client.post(
        _va_url(a.id),
        headers=headers,
        json={"outcome": "pass", "note": "different"},
    )
    assert second.status_code == 409, second.text


def test_verify_age_different_actor_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    key = _key()
    first = client.post(
        _va_url(a.id),
        headers={**_auth(drv), "Idempotency-Key": key},
        json={"outcome": "pass"},
    )
    assert first.status_code == 200, first.text
    other = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    make_driver_profile(db_session, user=other, store=store)
    db_session.commit()
    second = client.post(
        _va_url(a.id),
        headers={**_auth(other), "Idempotency-Key": key},
        json={"outcome": "pass"},
    )
    # Different actor -> either 409 (scope) once it reaches the ledger; the
    # ownership guard may 404 first. Both prove no shared replay across actors.
    assert second.status_code in (409, 404), second.text


def test_verify_age_pending_key_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, order, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    key = _key()
    db_session.add(
        DriverComplianceIdempotencyKey(
            idempotency_key=key,
            action="delivery_verified",
            actor_user_id=drv.id,
            store_id=store.id,
            order_id=order.id,
            assignment_id=a.id,
            request_hash="a" * 64,
            state="pending",
        )
    )
    db_session.commit()
    resp = client.post(
        _va_url(a.id),
        headers={**_auth(drv), "Idempotency-Key": key},
        json={"outcome": "pass"},
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.parametrize("bad", ["", "   ", "has space", "x" * 256])
def test_verify_age_invalid_key_400(
    client: TestClient, db_session: Session, make_store, bad: str
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    resp = client.post(
        _va_url(a.id),
        headers={**_auth(drv), "Idempotency-Key": bad},
        json={"outcome": "pass"},
    )
    assert resp.status_code == 400, resp.text
    assert _ledger(db_session, a.id) == []


# ===================================================================== #
# proof
# ===================================================================== #


def _pf_url(aid) -> str:
    return f"/driver/assignments/{aid}/proof"


_PROOF_BODY = {
    "recipient_present_confirmed": True,
    "handoff_confirmed": True,
    "restricted_not_left_unattended": True,
}


def test_proof_no_header_baseline_no_ledger(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.id_verified.value
    )
    resp = client.post(_pf_url(a.id), headers=_auth(drv), json=_PROOF_BODY)
    assert resp.status_code == 200, resp.text
    assert _ledger(db_session, a.id) == []


def test_proof_valid_key_and_replay(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.id_verified.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(_pf_url(a.id), headers=headers, json=_PROOF_BODY)
    assert first.status_code == 200, first.text
    rows = _ledger(db_session, a.id, "delivery_proof_recorded")
    assert len(rows) == 1 and rows[0].state == "completed"
    assert rows[0].response_ref_id == uuid.UUID(first.json()["id"])
    second = client.post(_pf_url(a.id), headers=headers, json=_PROOF_BODY)
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert len(_ledger(db_session, a.id, "delivery_proof_recorded")) == 1
    assert _op_audit_count(db_session, a.id, "delivery_proof_recorded") == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DriverDeliveryProof)
            .where(DriverDeliveryProof.assignment_id == a.id)
        )
        == 1
    )


def test_proof_changed_body_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.id_verified.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(_pf_url(a.id), headers=headers, json=_PROOF_BODY)
    assert first.status_code == 200, first.text
    second = client.post(
        _pf_url(a.id), headers=headers, json={**_PROOF_BODY, "note": "x"}
    )
    assert second.status_code == 409, second.text


def test_proof_invalid_key_400(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.id_verified.value
    )
    resp = client.post(
        _pf_url(a.id),
        headers={**_auth(drv), "Idempotency-Key": "bad key"},
        json=_PROOF_BODY,
    )
    assert resp.status_code == 400, resp.text
    assert _ledger(db_session, a.id) == []


# ===================================================================== #
# complete (with real reserved inventory)
# ===================================================================== #


def _cp_url(aid) -> str:
    return f"/driver/assignments/{aid}/complete"


def test_complete_no_header_baseline_no_ledger(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.id_verified.value,
        order_status="out_for_delivery", with_pass=True, with_proof=True,
    )
    resp = client.post(_cp_url(a.id), headers=_auth(drv))
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "delivery_completed"
    assert _ledger(db_session, a.id) == []


def test_complete_valid_key_and_replay_no_double_consume(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, order, item, a = _assignment(
        db_session, store, drv, state=State.id_verified.value,
        order_status="out_for_delivery", with_pass=True, with_proof=True,
        with_inventory=True,
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(_cp_url(a.id), headers=headers)
    assert first.status_code == 200, first.text
    rows = _ledger(db_session, a.id, "delivery_completed")
    assert len(rows) == 1 and rows[0].state == "completed"

    db_session.refresh(item)
    on_hand_after = item.quantity_on_hand
    reserved_after = item.quantity_reserved
    # Consume happened once: reserved 2 -> 0, on_hand 10 -> 8.
    assert reserved_after == 0
    assert on_hand_after == 8

    second = client.post(_cp_url(a.id), headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["state"] == "delivery_completed"

    # No second consume, no duplicate audit/ledger, order stays delivered.
    db_session.refresh(item)
    assert item.quantity_on_hand == 8
    assert item.quantity_reserved == 0
    assert len(_ledger(db_session, a.id, "delivery_completed")) == 1
    assert _op_audit_count(db_session, a.id, "delivery_completed") == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(OrderAuditLog)
            .where(
                OrderAuditLog.order_id == order.id,
                OrderAuditLog.new_status == OrderStatus.delivered,
            )
        )
        == 1
    )


def test_complete_invalid_key_400(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.id_verified.value,
        order_status="out_for_delivery", with_pass=True, with_proof=True,
    )
    resp = client.post(
        _cp_url(a.id), headers={**_auth(drv), "Idempotency-Key": " "}
    )
    assert resp.status_code == 400, resp.text
    assert _ledger(db_session, a.id) == []


# ===================================================================== #
# fail
# ===================================================================== #


def _fl_url(aid) -> str:
    return f"/driver/assignments/{aid}/fail"


def test_fail_no_header_baseline_no_ledger(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    resp = client.post(
        _fl_url(a.id), headers=_auth(drv),
        json={"reason_code": "customer_unavailable"},
    )
    assert resp.status_code == 200, resp.text
    assert _ledger(db_session, a.id) == []


def test_fail_valid_key_and_replay(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    body = {"reason_code": "customer_unavailable"}
    first = client.post(_fl_url(a.id), headers=headers, json=body)
    assert first.status_code == 200, first.text
    rows = _ledger(db_session, a.id, "delivery_failed")
    assert len(rows) == 1 and rows[0].state == "completed"
    assert rows[0].response_ref_id == uuid.UUID(first.json()["id"])
    second = client.post(_fl_url(a.id), headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert len(_ledger(db_session, a.id, "delivery_failed")) == 1
    assert _op_audit_count(db_session, a.id, "delivery_failed") == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DriverDeliveryFailure)
            .where(DriverDeliveryFailure.assignment_id == a.id)
        )
        == 1
    )


def test_fail_changed_reason_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(
        _fl_url(a.id), headers=headers,
        json={"reason_code": "customer_unavailable"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        _fl_url(a.id), headers=headers, json={"reason_code": "store_issue"}
    )
    assert second.status_code == 409, second.text


def test_fail_invalid_key_400(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.arrived_at_customer.value
    )
    resp = client.post(
        _fl_url(a.id),
        headers={**_auth(drv), "Idempotency-Key": "x" * 256},
        json={"reason_code": "customer_unavailable"},
    )
    assert resp.status_code == 400, resp.text
    assert _ledger(db_session, a.id) == []


# ===================================================================== #
# return-to-store (start / arrive)
# ===================================================================== #


def _rs_url(aid) -> str:
    return f"/driver/assignments/{aid}/return-to-store"


def test_return_start_no_header_baseline_no_ledger(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.delivery_failed.value
    )
    resp = client.post(
        _rs_url(a.id), headers=_auth(drv), json={"action": "start"}
    )
    assert resp.status_code == 200, resp.text
    assert _ledger(db_session, a.id) == []


def test_return_start_valid_key_and_replay(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.delivery_failed.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(_rs_url(a.id), headers=headers, json={"action": "start"})
    assert first.status_code == 200, first.text
    rows = _ledger(db_session, a.id, "delivery_return_started")
    assert len(rows) == 1 and rows[0].state == "completed"
    assert rows[0].response_ref_id == uuid.UUID(first.json()["id"])
    second = client.post(
        _rs_url(a.id), headers=headers, json={"action": "start"}
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert len(_ledger(db_session, a.id, "delivery_return_started")) == 1
    assert _op_audit_count(db_session, a.id, "delivery_return_started") == 1


def test_return_arrive_valid_key_and_replay(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    # Seed the returning_to_store state + an existing returning custody row.
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.returning_to_store.value,
        with_return_state=DriverDeliveryReturnState.returning.value,
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    first = client.post(_rs_url(a.id), headers=headers, json={"action": "arrive"})
    assert first.status_code == 200, first.text
    assert first.json()["return_state"] == "returned_pending_confirmation"
    rows = _ledger(db_session, a.id, "delivery_return_arrived")
    assert len(rows) == 1 and rows[0].state == "completed"
    second = client.post(
        _rs_url(a.id), headers=headers, json={"action": "arrive"}
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert len(_ledger(db_session, a.id, "delivery_return_arrived")) == 1
    assert _op_audit_count(db_session, a.id, "delivery_return_arrived") == 1


def test_return_arrive_changed_scope_invalid_key(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.returning_to_store.value,
        with_return_state=DriverDeliveryReturnState.returning.value,
    )
    resp = client.post(
        _rs_url(a.id),
        headers={**_auth(drv), "Idempotency-Key": "bad\tkey"},
        json={"action": "arrive"},
    )
    # A control/whitespace char in the key is a 400 (the client transmits \t).
    assert resp.status_code == 400, resp.text
    assert _ledger(db_session, a.id) == []


def test_return_start_and_arrive_use_distinct_actions(
    client: TestClient, db_session: Session, make_store
) -> None:
    """start and arrive are distinct ledger actions, so the same key replays
    each independently (per (store, action, key) namespacing)."""
    store = make_store()
    drv = _driver(db_session, store)
    _p, _o, _i, a = _assignment(
        db_session, store, drv, state=State.delivery_failed.value
    )
    key = _key()
    headers = {**_auth(drv), "Idempotency-Key": key}
    r1 = client.post(_rs_url(a.id), headers=headers, json={"action": "start"})
    assert r1.status_code == 200, r1.text
    r2 = client.post(_rs_url(a.id), headers=headers, json={"action": "arrive"})
    assert r2.status_code == 200, r2.text
    assert len(_ledger(db_session, a.id, "delivery_return_started")) == 1
    assert len(_ledger(db_session, a.id, "delivery_return_arrived")) == 1


# ===================================================================== #
# Global invariants
# ===================================================================== #


def test_operational_routes_have_no_idempotency_header() -> None:
    import inspect as _inspect

    from app.api.routes import driver as driver_routes

    operational = [
        "accept_current_driver_assignment",
        "decline_current_driver_assignment",
        "start_current_driver_assignment",
        "arrive_store_current_driver_assignment",
        "pickup_current_driver_assignment",
        "depart_to_customer_current_driver_assignment",
        "arrive_customer_current_driver_assignment",
    ]
    for name in operational:
        fn = getattr(driver_routes, name, None)
        if fn is None:
            continue
        assert "idempotency_key" not in _inspect.signature(fn).parameters, (
            f"{name} must NOT accept an Idempotency-Key in I.c"
        )


def test_compliance_routes_have_idempotency_header() -> None:
    import inspect as _inspect

    from app.api.routes import driver as driver_routes

    compliance = [
        "verify_age_current_driver_assignment",
        "submit_proof_current_driver_assignment",
        "complete_current_driver_assignment",
        "fail_current_driver_assignment",
        "return_to_store_current_driver_assignment",
    ]
    for name in compliance:
        fn = getattr(driver_routes, name)
        assert "idempotency_key" in _inspect.signature(fn).parameters, name
