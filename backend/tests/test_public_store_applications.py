"""Tests for the public store-application intake API (F2.24.C2).

Covers POST /public/store-applications end to end through the FastAPI
TestClient plus the service-level side effects, asserting the C2 boundary:
a submission creates ONE inert pending-review application + one audit row,
and creates NO store, NO user, and NO Supabase Auth record.

Style mirrors the existing API test suites (TestClient `client`, the
transactional `db_session`, the autouse `supabase_admin_fake`).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import StoreApplication
from app.db.models import StoreApplicationAuditLog
from app.db.models import StoreApplicationStatus
from app.db.models import User


_ENDPOINT = "/public/store-applications"


def _valid_body(**overrides) -> dict:
    body = {
        "business_name": "Acme Vapes",
        "business_type": "vape_shop",
        "owner_full_name": "Jane Owner",
        "owner_email": "jane@example.com",
        "owner_phone": "+1 555 0100",
        "business_phone": "+1 555 0199",
        "address_line_1": "1 Test Way",
        "city": "Miami",
        "state": "FL",
        "postal_code": "33101",
        "country": "US",
        "location_count": 2,
        "estimated_weekly_orders": 150,
        "hours_of_operation": "Mon-Fri 9-5",
        "terms_accepted": True,
    }
    body.update(overrides)
    return body


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def _only_application(db: Session) -> StoreApplication:
    apps = db.scalars(select(StoreApplication)).all()
    assert len(apps) == 1, f"expected exactly one application, got {len(apps)}"
    return apps[0]


# --------------------------------------------------------------------- #
# Happy path + server-side stamping
# --------------------------------------------------------------------- #


def test_submit_creates_pending_review_application(
    client: TestClient, db_session: Session
):
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending_review"
    assert body["message"] == "Application submitted for review."
    assert uuid.UUID(body["id"])  # parses

    application = _only_application(db_session)
    assert application.status is StoreApplicationStatus.pending_review
    assert str(application.id) == body["id"]


def test_submit_normalizes_owner_email_lowercase(
    client: TestClient, db_session: Session
):
    resp = client.post(
        _ENDPOINT, json=_valid_body(owner_email="Jane.Owner@Example.COM")
    )
    assert resp.status_code == 201, resp.text
    application = _only_application(db_session)
    assert application.owner_email == "jane.owner@example.com"


def test_submit_sets_submitted_at(client: TestClient, db_session: Session):
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    application = _only_application(db_session)
    assert application.submitted_at is not None


def test_submit_sets_terms_accepted_at(
    client: TestClient, db_session: Session
):
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    application = _only_application(db_session)
    assert application.terms_accepted is True
    assert application.terms_accepted_at is not None


def test_submit_creates_application_created_audit_log(
    client: TestClient, db_session: Session
):
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    application = _only_application(db_session)

    logs = db_session.scalars(
        select(StoreApplicationAuditLog).where(
            StoreApplicationAuditLog.application_id == application.id
        )
    ).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.event_type == "application_created"
    assert log.actor_user_id is None
    assert log.payload == {"source": "public_intake"}


# --------------------------------------------------------------------- #
# Boundary: no store / user / auth provisioning
# --------------------------------------------------------------------- #


def test_submit_does_not_create_store(
    client: TestClient, db_session: Session
):
    before = _count(db_session, Store)
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    assert _count(db_session, Store) == before


def test_submit_does_not_create_user(
    client: TestClient, db_session: Session
):
    before = _count(db_session, User)
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    assert _count(db_session, User) == before


def test_submit_does_not_call_supabase_auth(
    client: TestClient, supabase_admin_fake
):
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    assert supabase_admin_fake.created == []
    assert supabase_admin_fake.deleted == []


# --------------------------------------------------------------------- #
# Validation rejections (422)
# --------------------------------------------------------------------- #


def test_submit_rejects_terms_not_accepted(client: TestClient):
    resp = client.post(_ENDPOINT, json=_valid_body(terms_accepted=False))
    assert resp.status_code == 422, resp.text


def test_submit_rejects_missing_required_field(client: TestClient):
    body = _valid_body()
    del body["business_name"]
    resp = client.post(_ENDPOINT, json=body)
    assert resp.status_code == 422, resp.text


def test_submit_rejects_blank_required_field(client: TestClient):
    resp = client.post(_ENDPOINT, json=_valid_body(business_name="   "))
    assert resp.status_code == 422, resp.text


def test_submit_rejects_invalid_email(client: TestClient):
    resp = client.post(_ENDPOINT, json=_valid_body(owner_email="not-an-email"))
    assert resp.status_code == 422, resp.text


def test_submit_rejects_non_positive_location_count(client: TestClient):
    resp = client.post(_ENDPOINT, json=_valid_body(location_count=0))
    assert resp.status_code == 422, resp.text


def test_submit_rejects_negative_estimated_weekly_orders(client: TestClient):
    resp = client.post(
        _ENDPOINT, json=_valid_body(estimated_weekly_orders=-1)
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "field, value",
    [
        ("status", "approved"),
        ("role", "admin"),
        ("store_id", str(uuid.uuid4())),
        ("user_id", str(uuid.uuid4())),
        ("auth_user_id", str(uuid.uuid4())),
        ("is_admin", True),
        ("provisioned_store_id", str(uuid.uuid4())),
        ("provisioned_owner_user_id", str(uuid.uuid4())),
        ("public_lookup_token", "smuggled-token"),
        ("reviewed_by_user_id", str(uuid.uuid4())),
        ("id", str(uuid.uuid4())),
    ],
)
def test_submit_rejects_mass_assignment_fields(
    client: TestClient, db_session: Session, field: str, value
):
    resp = client.post(_ENDPOINT, json=_valid_body(**{field: value}))
    assert resp.status_code == 422, resp.text
    # Nothing should have been written.
    assert _count(db_session, StoreApplication) == 0


# --------------------------------------------------------------------- #
# Deduplication
# --------------------------------------------------------------------- #


def test_duplicate_active_application_returns_409(
    client: TestClient, db_session: Session
):
    first = client.post(_ENDPOINT, json=_valid_body())
    assert first.status_code == 201, first.text

    second = client.post(
        _ENDPOINT, json=_valid_body(business_name="Acme Vapes Two")
    )
    assert second.status_code == 409, second.text
    # Still only the first application.
    assert _count(db_session, StoreApplication) == 1


def test_duplicate_active_dedup_is_case_insensitive(
    client: TestClient, db_session: Session
):
    first = client.post(_ENDPOINT, json=_valid_body(owner_email="dup@x.com"))
    assert first.status_code == 201, first.text
    second = client.post(_ENDPOINT, json=_valid_body(owner_email="DUP@X.COM"))
    assert second.status_code == 409, second.text


def test_reapplication_allowed_after_rejection(
    client: TestClient, db_session: Session
):
    # Seed a prior REJECTED application for the same email directly.
    rejected = StoreApplication(
        business_name="Old Try",
        business_type="vape_shop",
        owner_full_name="Jane Owner",
        owner_email="jane@example.com",
        owner_phone="+1 555 0100",
        address_line_1="1 Test Way",
        city="Miami",
        state="FL",
        postal_code="33101",
        status=StoreApplicationStatus.rejected,
        rejection_reason="incomplete documents",
    )
    db_session.add(rejected)
    db_session.commit()

    resp = client.post(_ENDPOINT, json=_valid_body(owner_email="jane@example.com"))
    assert resp.status_code == 201, resp.text
    # The rejected row plus the new pending_review row coexist.
    apps = db_session.scalars(
        select(StoreApplication).where(
            StoreApplication.owner_email == "jane@example.com"
        )
    ).all()
    assert len(apps) == 2
    statuses = {a.status for a in apps}
    assert StoreApplicationStatus.rejected in statuses
    assert StoreApplicationStatus.pending_review in statuses


# --------------------------------------------------------------------- #
# Auth posture
# --------------------------------------------------------------------- #


def test_endpoint_is_unauthenticated(client: TestClient):
    # No Authorization header at all → still succeeds.
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text


def test_submit_response_exposes_only_safe_fields(client: TestClient):
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    assert set(resp.json().keys()) == {"id", "status", "message"}


def test_submit_grants_no_admin_user(
    client: TestClient, db_session: Session
):
    resp = client.post(_ENDPOINT, json=_valid_body())
    assert resp.status_code == 201, resp.text
    from app.db.models import UserRole

    admin_count = db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.admin)
    )
    assert admin_count == 0


def test_protected_route_still_requires_auth(client: TestClient):
    # C2 must not weaken auth: an authenticated route still 401s without a
    # token. (Independent of the JWKS verifier — this is the missing-header
    # path.)
    resp = client.get("/auth/me")
    assert resp.status_code == 401, resp.text
