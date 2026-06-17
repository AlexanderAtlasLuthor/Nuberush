"""Dr.1.2.I.b — compliance idempotency ledger: model + helper unit tests.

Covers the ``driver_compliance_idempotency_keys`` table constraints (UNIQUE
scope, state/action/request_hash CHECKs, nullable assignment_id) and the
``app.services.compliance_idempotency`` helper: key validation (400), the
stable request hash, the claim/replay/conflict state machine, completion, and
the no-raw-payload / no-response-body guarantee.

The migration's upgrade/downgrade reversibility is exercised by the
``alembic downgrade -1 && alembic upgrade head`` step in the I.b validation
sequence (running a destructive downgrade inside the shared-DB pytest session
would corrupt sibling tests), so here we assert the live, upgraded schema.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DriverComplianceIdempotencyKey
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
from app.schemas.orders import StoreConfirmDriverReturnRequest
from app.services.compliance_idempotency import claim_or_replay
from app.services.compliance_idempotency import complete_claim
from app.services.compliance_idempotency import (
    compute_compliance_request_hash,
)
from app.services.compliance_idempotency import validate_idempotency_key
from tests.helpers.auth import make_user as central_make_user

_HASH = "a" * 64
_ACTION = "delivery_return_confirmed"


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "CIK-Store") -> Store:
        store = Store(name=name, code=f"cik-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def scope(db_session: Session, make_store):
    """A realistic claim scope: store + actor + a persisted order."""
    store = make_store()
    actor = central_make_user(
        db_session, role=UserRole.manager, store_id=store.id
    )
    order = Order(
        store_id=store.id,
        idempotency_key=f"cik-{uuid.uuid4().hex}",
        status=OrderStatus.out_for_delivery,
        subtotal_amount=Decimal("20.00"),
        total_amount=Decimal("20.00"),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return {"store": store, "actor": actor, "order": order}


# --------------------------------------------------------------------- #
# Model / migration (live schema + constraints)
# --------------------------------------------------------------------- #


def test_table_and_indexes_exist(db_session: Session) -> None:
    insp = inspect(db_session.get_bind())
    assert insp.has_table("driver_compliance_idempotency_keys")
    index_names = {
        i["name"]
        for i in insp.get_indexes("driver_compliance_idempotency_keys")
    }
    assert "ix_driver_compliance_idempotency_keys_created_at" in index_names
    assert "ix_driver_compliance_idempotency_keys_expires_at" in index_names
    assert (
        "ix_driver_compliance_idempotency_keys_store_action" in index_names
    )


def _row(scope, **overrides) -> DriverComplianceIdempotencyKey:
    base = dict(
        idempotency_key=f"key-{uuid.uuid4().hex}",
        action=_ACTION,
        actor_user_id=scope["actor"].id,
        store_id=scope["store"].id,
        order_id=scope["order"].id,
        assignment_id=None,
        request_hash=_HASH,
        state="pending",
    )
    base.update(overrides)
    return DriverComplianceIdempotencyKey(**base)


def test_unique_scope_enforced(db_session: Session, scope) -> None:
    key = f"dup-{uuid.uuid4().hex}"
    db_session.add(_row(scope, idempotency_key=key))
    db_session.commit()
    db_session.add(_row(scope, idempotency_key=key))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_state_check_rejects_invalid(db_session: Session, scope) -> None:
    db_session.add(_row(scope, state="bogus"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_action_check_rejects_invalid(db_session: Session, scope) -> None:
    db_session.add(_row(scope, action="not_a_compliance_action"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_request_hash_length_enforced(db_session: Session, scope) -> None:
    db_session.add(_row(scope, request_hash="tooshort"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_assignment_id_nullable(db_session: Session, scope) -> None:
    row = _row(scope, assignment_id=None)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.assignment_id is None


# --------------------------------------------------------------------- #
# Key validation
# --------------------------------------------------------------------- #


def test_valid_key_returned_unchanged() -> None:
    assert validate_idempotency_key("abc-123_DEF") == "abc-123_DEF"


@pytest.mark.parametrize("bad", ["", "   ", "\t", "\n"])
def test_empty_or_whitespace_key_rejected(bad: str) -> None:
    with pytest.raises(HTTPException) as exc:
        validate_idempotency_key(bad)
    assert exc.value.status_code == 400


def test_too_long_key_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_idempotency_key("x" * 256)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("bad", ["has space", "ctrl\x01char", "tab\tinside"])
def test_malformed_key_rejected(bad: str) -> None:
    with pytest.raises(HTTPException) as exc:
        validate_idempotency_key(bad)
    assert exc.value.status_code == 400


# --------------------------------------------------------------------- #
# Request hash
# --------------------------------------------------------------------- #


def test_request_hash_is_64_hex_and_stable() -> None:
    payload = StoreConfirmDriverReturnRequest(
        received_confirmed=True, note="x"
    )
    h1 = compute_compliance_request_hash(_ACTION, payload)
    h2 = compute_compliance_request_hash(_ACTION, payload)
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)
    assert h1 == h2


def test_request_hash_changes_with_body_and_action() -> None:
    a = compute_compliance_request_hash(
        _ACTION,
        StoreConfirmDriverReturnRequest(received_confirmed=True, note="a"),
    )
    b = compute_compliance_request_hash(
        _ACTION,
        StoreConfirmDriverReturnRequest(received_confirmed=True, note="b"),
    )
    c = compute_compliance_request_hash(
        "delivery_failed",
        StoreConfirmDriverReturnRequest(received_confirmed=True, note="a"),
    )
    assert a != b
    assert a != c


# --------------------------------------------------------------------- #
# claim_or_replay / complete_claim
# --------------------------------------------------------------------- #


def _claim(db, scope, *, key, hash_=_HASH, actor=None, order=None):
    return claim_or_replay(
        db,
        idempotency_key=key,
        action=_ACTION,
        actor_user_id=(actor or scope["actor"]).id,
        store_id=scope["store"].id,
        order_id=(order or scope["order"]).id,
        assignment_id=None,
        request_hash=hash_,
    )


def test_new_key_inserts_pending_claim(db_session: Session, scope) -> None:
    key = f"new-{uuid.uuid4().hex}"
    result = _claim(db_session, scope, key=key)
    assert result.replayed is False
    assert result.claim.state == "pending"
    assert result.claim.idempotency_key == key
    assert result.claim.response_ref_id is None


def test_complete_claim_marks_completed(db_session: Session, scope) -> None:
    result = _claim(db_session, scope, key=f"c-{uuid.uuid4().hex}")
    ref = scope["order"].id
    complete_claim(
        db_session,
        claim=result.claim,
        response_ref_id=ref,
        response_status_code=200,
        completed_at=_now(),
    )
    assert result.claim.state == "completed"
    assert result.claim.response_ref_id == ref
    assert result.claim.response_status_code == 200
    assert result.claim.completed_at is not None


def test_same_key_same_hash_same_scope_replays(
    db_session: Session, scope
) -> None:
    key = f"replay-{uuid.uuid4().hex}"
    first = _claim(db_session, scope, key=key)
    complete_claim(
        db_session,
        claim=first.claim,
        response_ref_id=scope["order"].id,
        completed_at=_now(),
    )
    db_session.commit()
    again = _claim(db_session, scope, key=key)
    assert again.replayed is True
    assert again.claim.response_ref_id == scope["order"].id


def _complete_and_commit(db_session, result, scope) -> None:
    complete_claim(
        db_session,
        claim=result.claim,
        response_ref_id=scope["order"].id,
        completed_at=_now(),
    )
    db_session.commit()


def test_same_key_different_hash_409(db_session: Session, scope) -> None:
    key = f"h-{uuid.uuid4().hex}"
    _complete_and_commit(db_session, _claim(db_session, scope, key=key), scope)
    with pytest.raises(HTTPException) as exc:
        _claim(db_session, scope, key=key, hash_="b" * 64)
    assert exc.value.status_code == 409


def test_same_key_different_actor_409(
    db_session: Session, scope, make_store
) -> None:
    key = f"a-{uuid.uuid4().hex}"
    _complete_and_commit(db_session, _claim(db_session, scope, key=key), scope)
    other_actor = central_make_user(
        db_session, role=UserRole.manager, store_id=scope["store"].id
    )
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        _claim(db_session, scope, key=key, actor=other_actor)
    assert exc.value.status_code == 409


def test_same_key_different_order_scope_409(
    db_session: Session, scope
) -> None:
    key = f"o-{uuid.uuid4().hex}"
    _complete_and_commit(db_session, _claim(db_session, scope, key=key), scope)
    other_order = Order(
        store_id=scope["store"].id,
        idempotency_key=f"cik-{uuid.uuid4().hex}",
        status=OrderStatus.out_for_delivery,
        subtotal_amount=Decimal("5.00"),
        total_amount=Decimal("5.00"),
    )
    db_session.add(other_order)
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        _claim(db_session, scope, key=key, order=other_order)
    assert exc.value.status_code == 409


def test_pending_key_in_progress_409(db_session: Session, scope) -> None:
    key = f"p-{uuid.uuid4().hex}"
    _claim(db_session, scope, key=key)  # left pending
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        _claim(db_session, scope, key=key)
    assert exc.value.status_code == 409


def test_different_store_same_key_is_separate_claim(
    db_session: Session, scope, make_store
) -> None:
    """Keys are namespaced per (store, action) by the UNIQUE constraint, so the
    same key under a different store is a distinct claim, not a conflict."""
    key = f"s-{uuid.uuid4().hex}"
    _complete_and_commit(db_session, _claim(db_session, scope, key=key), scope)
    store2 = make_store()
    actor2 = central_make_user(
        db_session, role=UserRole.manager, store_id=store2.id
    )
    order2 = Order(
        store_id=store2.id,
        idempotency_key=f"cik-{uuid.uuid4().hex}",
        status=OrderStatus.out_for_delivery,
        subtotal_amount=Decimal("5.00"),
        total_amount=Decimal("5.00"),
    )
    db_session.add(order2)
    db_session.commit()
    result = claim_or_replay(
        db_session,
        idempotency_key=key,
        action=_ACTION,
        actor_user_id=actor2.id,
        store_id=store2.id,
        order_id=order2.id,
        assignment_id=None,
        request_hash=_HASH,
    )
    assert result.replayed is False
    assert result.claim.state == "pending"


def test_unknown_action_is_programming_error(
    db_session: Session, scope
) -> None:
    with pytest.raises(ValueError):
        claim_or_replay(
            db_session,
            idempotency_key=f"x-{uuid.uuid4().hex}",
            action="totally_unknown",
            actor_user_id=scope["actor"].id,
            store_id=scope["store"].id,
            order_id=scope["order"].id,
            assignment_id=None,
            request_hash=_HASH,
        )


def test_ledger_stores_no_raw_payload_or_response_body(
    db_session: Session, scope
) -> None:
    """The ledger row carries only a digest + a reference id — never the raw
    request body or any response body."""
    col_names = {
        c.name for c in DriverComplianceIdempotencyKey.__table__.columns
    }
    for forbidden in {
        "request_body",
        "request_payload",
        "payload",
        "response_body",
        "response",
        "body",
        "headers",
        "token",
    }:
        assert forbidden not in col_names
    result = _claim(db_session, scope, key=f"redact-{uuid.uuid4().hex}")
    complete_claim(
        db_session,
        claim=result.claim,
        response_ref_id=scope["order"].id,
        completed_at=_now(),
    )
    # Only the hash + reference id are stored; the 64-char digest is opaque.
    assert result.claim.request_hash == _HASH
    assert result.claim.response_ref_id == scope["order"].id
