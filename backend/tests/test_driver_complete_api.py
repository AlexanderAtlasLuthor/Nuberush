"""Dr.1.2.E — complete-delivery API tests.

Confirms POST /driver/assignments/{id}/complete: the 200 happy path
(response state delivery_completed), idempotency, the compliance gate (proof +
verify-age pass required), the 422/409 guards, the role/store/auth gates, and a
redaction-safe response.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryProof
from app.db.models import DriverDeliveryProofMethod
from app.db.models import DriverDeliveryVerification
from app.db.models import DriverDeliveryVerificationMethod
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


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

_FORBIDDEN_KEYS = {
    "order_status",
    "inventory",
    "customer",
    "customer_user_id",
    "email",
    "phone",
    "address",
    "total_amount",
    "age_verified_at",
    "id_number",
    "id_image_url",
    "signature",
    "customer_photo",
    "proof_file_url",
    "artifact_url",
}


def _url(assignment_id) -> str:
    return f"/driver/assignments/{assignment_id}/complete"


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "CDA-Store") -> Store:
        store = Store(name=name, code=f"cda-{uuid.uuid4().hex[:8]}")
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
    order_status: str = "ready",
    state: str | None = State.id_verified.value,
    with_pass: bool = True,
    with_proof: bool = True,
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
    db_session.commit()
    return profile, order, assignment


# --------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------- #


def test_complete_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile, order, assignment = _setup(db_session, store, user)
    resp = client.post(_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == _STATE_KEYS
    assert body["state"] == "delivery_completed"
    assert body["assignment_id"] == str(assignment.id)


def test_complete_idempotent(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    first = client.post(_url(assignment.id), headers=_auth(user))
    second = client.post(_url(assignment.id), headers=_auth(user))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["state"] == "delivery_completed"


def test_response_no_sensitive_fields(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user)
    body = client.post(_url(assignment.id), headers=_auth(user)).json()
    for forbidden in _FORBIDDEN_KEYS:
        assert forbidden not in body, forbidden


# --------------------------------------------------------------------- #
# Compliance gate
# --------------------------------------------------------------------- #


def test_no_proof_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user, with_proof=False)
    resp = client.post(_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


def test_no_verify_age_pass_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(db_session, store, user, with_pass=False)
    resp = client.post(_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


def test_arrived_at_customer_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(
        db_session,
        store,
        user,
        state=State.arrived_at_customer.value,
        with_pass=False,
        with_proof=False,
    )
    resp = client.post(_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


def test_terminal_state_422(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(
        db_session,
        store,
        user,
        state=State.delivery_failed.value,
        with_pass=False,
        with_proof=False,
    )
    resp = client.post(_url(assignment.id), headers=_auth(user))
    assert resp.status_code == 422, resp.text


def test_order_not_completable_409(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    _p, _o, assignment = _setup(
        db_session, store, user, order_status="preparing"
    )
    resp = client.post(_url(assignment.id), headers=_auth(user))
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
    other_store = make_store(name="CDA-Other")
    other = _driver(db_session, other_store)
    make_driver_profile(db_session, user=other, store=other_store)
    resp = client.post(_url(assignment.id), headers=_auth(other))
    assert resp.status_code == 404, resp.text


def test_missing_assignment_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)
    resp = client.post(_url(uuid.uuid4()), headers=_auth(user))
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
    resp = client.post(_url(assignment.id), headers=_auth(staff))
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
    resp = client.post(_url(assignment.id), headers=_auth(storeless))
    assert resp.status_code == 403, resp.text
