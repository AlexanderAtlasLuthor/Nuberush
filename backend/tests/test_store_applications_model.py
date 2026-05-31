"""DB-level model + constraint tests for store applications (F2.24.C1).

Exercises the persisted foundation against the real (migrated) Postgres
test database:
  - The enum + models import and a pending_review row persists with the
    expected server defaults.
  - The CHECK constraints hold:
      * a non-approved row may not carry provisioning links;
      * an approved row must carry both provisioning links;
      * rejected ⇔ rejection_reason;
      * terms_accepted ⇒ terms_accepted_at;
      * location_count > 0.
  - public_lookup_token is unique.
  - The append-only audit table persists rows and cascades on application
    delete.
  - The expected columns and indexes exist (migration inspection).

Style mirrors tests/test_product_images.py (local make_* fixtures over the
transactional db_session, IntegrityError assertions for DB constraints).
"""
from __future__ import annotations

import uuid
from typing import Callable

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import StoreApplication
from app.db.models import StoreApplicationAuditLog
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        store = Store(name="App-QA", code=f"aq-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_admin(db_session: Session) -> Callable[..., User]:
    def _create() -> User:
        return central_make_user(
            db_session,
            role=UserRole.admin,
            store_id=None,
            full_name="App Reviewer",
            is_active=True,
        )

    return _create


def _app_kwargs(**overrides) -> dict:
    data = dict(
        business_name="Acme Vapes",
        business_type="vape_shop",
        owner_full_name="Jane Owner",
        owner_email="jane@example.com",
        owner_phone="+1 555 0100",
        address_line_1="1 Test Way",
        city="Miami",
        state="FL",
        postal_code="33101",
        status=StoreApplicationStatus.pending_review,
    )
    data.update(overrides)
    return data


# --------------------------------------------------------------------- #
# 1. Import + persistence
# --------------------------------------------------------------------- #


def test_models_and_enum_importable():
    assert StoreApplication.__tablename__ == "store_applications"
    assert (
        StoreApplicationAuditLog.__tablename__
        == "store_application_audit_logs"
    )
    assert [s.value for s in StoreApplicationStatus] == [
        "draft",
        "submitted",
        "pending_review",
        "approved",
        "rejected",
    ]


def test_pending_review_application_persists_with_defaults(
    db_session: Session,
):
    application = StoreApplication(**_app_kwargs())
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    assert application.id is not None
    assert application.status is StoreApplicationStatus.pending_review
    # Server defaults.
    assert application.country == "US"
    assert application.location_count == 1
    assert application.terms_accepted is False
    assert application.public_lookup_token
    assert len(application.public_lookup_token) == 32  # uuid hex, no dashes
    assert application.created_at is not None
    assert application.updated_at is not None
    # No provisioning yet.
    assert application.provisioned_store_id is None
    assert application.provisioned_owner_user_id is None


def test_status_defaults_to_draft_when_omitted(db_session: Session):
    kwargs = _app_kwargs()
    kwargs.pop("status")
    application = StoreApplication(**kwargs)
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    assert application.status is StoreApplicationStatus.draft


# --------------------------------------------------------------------- #
# 2. Provisioning-link constraints
# --------------------------------------------------------------------- #


def test_pending_review_cannot_have_provisioned_store(
    db_session: Session, make_store: Callable[..., Store]
):
    store = make_store()
    application = StoreApplication(
        **_app_kwargs(provisioned_store_id=store.id)
    )
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_pending_review_cannot_have_provisioned_owner(
    db_session: Session, make_admin: Callable[..., User]
):
    owner = make_admin()
    application = StoreApplication(
        **_app_kwargs(provisioned_owner_user_id=owner.id)
    )
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_approved_application_requires_both_links(
    db_session: Session,
    make_store: Callable[..., Store],
    make_admin: Callable[..., User],
):
    store = make_store()
    owner = make_admin()
    application = StoreApplication(
        **_app_kwargs(
            status=StoreApplicationStatus.approved,
            provisioned_store_id=store.id,
            provisioned_owner_user_id=owner.id,
        )
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    assert application.status is StoreApplicationStatus.approved
    assert application.provisioned_store_id == store.id
    assert application.provisioned_owner_user_id == owner.id


def test_approved_without_store_is_rejected(
    db_session: Session, make_admin: Callable[..., User]
):
    owner = make_admin()
    application = StoreApplication(
        **_app_kwargs(
            status=StoreApplicationStatus.approved,
            provisioned_owner_user_id=owner.id,
        )
    )
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_approved_without_owner_is_rejected(
    db_session: Session, make_store: Callable[..., Store]
):
    store = make_store()
    application = StoreApplication(
        **_app_kwargs(
            status=StoreApplicationStatus.approved,
            provisioned_store_id=store.id,
        )
    )
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 3. rejection_reason constraint
# --------------------------------------------------------------------- #


def test_rejected_requires_rejection_reason(db_session: Session):
    application = StoreApplication(
        **_app_kwargs(status=StoreApplicationStatus.rejected)
    )
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_rejected_with_reason_persists(db_session: Session):
    application = StoreApplication(
        **_app_kwargs(
            status=StoreApplicationStatus.rejected,
            rejection_reason="incomplete license documents",
        )
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    assert application.status is StoreApplicationStatus.rejected
    assert application.rejection_reason == "incomplete license documents"


def test_non_rejected_cannot_carry_rejection_reason(db_session: Session):
    application = StoreApplication(
        **_app_kwargs(
            status=StoreApplicationStatus.pending_review,
            rejection_reason="should not be here",
        )
    )
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 4. Other CHECK constraints
# --------------------------------------------------------------------- #


def test_terms_accepted_requires_timestamp(db_session: Session):
    application = StoreApplication(**_app_kwargs(terms_accepted=True))
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_terms_accepted_with_timestamp_persists(db_session: Session):
    from datetime import UTC
    from datetime import datetime

    application = StoreApplication(
        **_app_kwargs(
            terms_accepted=True,
            terms_accepted_at=datetime.now(UTC),
        )
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    assert application.terms_accepted is True
    assert application.terms_accepted_at is not None


def test_location_count_must_be_positive(db_session: Session):
    application = StoreApplication(**_app_kwargs(location_count=0))
    db_session.add(application)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 5. public_lookup_token uniqueness
# --------------------------------------------------------------------- #


def test_public_lookup_token_is_unique(db_session: Session):
    token = uuid.uuid4().hex
    first = StoreApplication(**_app_kwargs(public_lookup_token=token))
    db_session.add(first)
    db_session.commit()

    second = StoreApplication(**_app_kwargs(public_lookup_token=token))
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 5b. Active-owner-email partial unique index (F2.24.C2 dedup guard)
# --------------------------------------------------------------------- #


def test_two_active_applications_same_email_violate_unique_index(
    db_session: Session,
):
    first = StoreApplication(**_app_kwargs(owner_email="dup@x.com"))
    db_session.add(first)
    db_session.commit()

    # A second ACTIVE (pending_review) application for the same email is
    # blocked by uq_store_applications_active_owner_email.
    second = StoreApplication(**_app_kwargs(owner_email="dup@x.com"))
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_active_email_index_ignores_rejected_rows(db_session: Session):
    rejected = StoreApplication(
        **_app_kwargs(
            owner_email="reapply@x.com",
            status=StoreApplicationStatus.rejected,
            rejection_reason="incomplete",
        )
    )
    db_session.add(rejected)
    db_session.commit()

    # A new ACTIVE application for the same email is allowed because the
    # prior one is rejected (excluded by the partial index predicate).
    fresh = StoreApplication(**_app_kwargs(owner_email="reapply@x.com"))
    db_session.add(fresh)
    db_session.commit()
    db_session.refresh(fresh)
    assert fresh.status is StoreApplicationStatus.pending_review


def test_active_owner_email_index_exists_and_is_unique(test_engine: Engine):
    indexes = inspect(test_engine).get_indexes("store_applications")
    by_name = {ix["name"]: ix for ix in indexes}
    assert "uq_store_applications_active_owner_email" in by_name
    assert by_name["uq_store_applications_active_owner_email"]["unique"] is True


# --------------------------------------------------------------------- #
# 6. Audit log table
# --------------------------------------------------------------------- #


def test_audit_log_persists_and_cascades_on_delete(
    db_session: Session, make_admin: Callable[..., User]
):
    actor = make_admin()
    application = StoreApplication(**_app_kwargs())
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    log = StoreApplicationAuditLog(
        application_id=application.id,
        event_type="application_created",
        actor_user_id=actor.id,
        message="created by test",
        payload={"source": "public", "step": 1},
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    assert log.id is not None
    assert log.event_type == "application_created"
    assert log.payload == {"source": "public", "step": 1}
    assert log.created_at is not None

    # ON DELETE CASCADE: removing the application removes its audit rows.
    log_id = log.id
    db_session.delete(application)
    db_session.commit()
    assert (
        db_session.get(StoreApplicationAuditLog, log_id) is None
    )


def test_audit_log_event_type_must_be_non_empty(
    db_session: Session,
):
    application = StoreApplication(**_app_kwargs())
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    log = StoreApplicationAuditLog(
        application_id=application.id,
        event_type="",
    )
    db_session.add(log)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 7. Migration inspection — columns + indexes exist
# --------------------------------------------------------------------- #


def test_store_applications_columns_exist(test_engine: Engine):
    cols = {c["name"] for c in inspect(test_engine).get_columns(
        "store_applications"
    )}
    expected = {
        "id",
        "business_name",
        "business_type",
        "owner_full_name",
        "owner_email",
        "owner_phone",
        "business_phone",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
        "location_count",
        "estimated_weekly_orders",
        "hours_of_operation",
        "website_url",
        "social_url",
        "notes",
        "terms_accepted",
        "terms_accepted_at",
        "status",
        "submitted_at",
        "reviewed_at",
        "reviewed_by_user_id",
        "rejection_reason",
        "provisioned_store_id",
        "provisioned_owner_user_id",
        "public_lookup_token",
        "created_at",
        "updated_at",
    }
    assert expected <= cols


def test_store_applications_indexes_exist(test_engine: Engine):
    index_names = {
        ix["name"]
        for ix in inspect(test_engine).get_indexes("store_applications")
    }
    expected = {
        "ix_store_applications_status",
        "ix_store_applications_owner_email",
        "ix_store_applications_submitted_at",
        "ix_store_applications_public_lookup_token",
        "ix_store_applications_reviewed_by_user_id",
        "ix_store_applications_provisioned_store_id",
        "ix_store_applications_provisioned_owner_user_id",
    }
    assert expected <= index_names


def test_public_lookup_token_index_is_unique(test_engine: Engine):
    indexes = inspect(test_engine).get_indexes("store_applications")
    token_ix = next(
        ix
        for ix in indexes
        if ix["name"] == "ix_store_applications_public_lookup_token"
    )
    assert token_ix["unique"] is True


def test_audit_log_columns_exist(test_engine: Engine):
    cols = {c["name"] for c in inspect(test_engine).get_columns(
        "store_application_audit_logs"
    )}
    expected = {
        "id",
        "application_id",
        "event_type",
        "actor_user_id",
        "message",
        "payload",
        "created_at",
    }
    assert expected <= cols
