"""Schema-only tests for the store-applications domain (F2.24.C1).

No DB. Exercises:
  - StoreApplicationStatus enum surface (re-export from app.db.models).
  - StoreApplicationRead / StoreApplicationListItem hydrating from an
    ORM-like object via `from_attributes`.
  - StoreApplicationBase required-field + length + bounds validation.
  - StoreApplicationCreateInternal owner-email + country normalization and
    required-string trimming (the service-layer normalization the F2.24
    plan defers from the model layer).
  - StoreApplicationListResponse paginated envelope bounds.
  - StoreApplicationAuditLogRead projection (with and without payload).

Style mirrors tests/test_stores_schemas.py.
"""
from __future__ import annotations

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import StoreApplicationStatus as ModelStatus
from app.schemas.store_applications import StoreApplicationAuditLogRead
from app.schemas.store_applications import StoreApplicationBase
from app.schemas.store_applications import StoreApplicationCreateInternal
from app.schemas.store_applications import StoreApplicationListItem
from app.schemas.store_applications import StoreApplicationListResponse
from app.schemas.store_applications import StoreApplicationRead
from app.schemas.store_applications import StoreApplicationStatus


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


def _intake_kwargs(**overrides) -> dict:
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
    )
    data.update(overrides)
    return data


def _read_namespace(**overrides) -> SimpleNamespace:
    now = datetime.now(UTC)
    data = dict(
        id=uuid4(),
        business_name="Acme Vapes",
        business_type="vape_shop",
        owner_full_name="Jane Owner",
        owner_email="jane@example.com",
        owner_phone="+1 555 0100",
        business_phone=None,
        address_line_1="1 Test Way",
        address_line_2=None,
        city="Miami",
        state="FL",
        postal_code="33101",
        country="US",
        location_count=1,
        estimated_weekly_orders=None,
        hours_of_operation=None,
        website_url=None,
        social_url=None,
        notes=None,
        terms_accepted=False,
        terms_accepted_at=None,
        status=ModelStatus.pending_review,
        submitted_at=now,
        reviewed_at=None,
        reviewed_by_user_id=None,
        rejection_reason=None,
        provisioned_store_id=None,
        provisioned_owner_user_id=None,
        public_lookup_token="abc123",
        created_at=now,
        updated_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


# --------------------------------------------------------------------- #
# Enum
# --------------------------------------------------------------------- #


def test_status_enum_is_the_model_enum():
    # The schema layer re-exports the ORM enum: same object, not a copy.
    assert StoreApplicationStatus is ModelStatus


def test_status_enum_values():
    assert [s.value for s in StoreApplicationStatus] == [
        "draft",
        "submitted",
        "pending_review",
        "approved",
        "rejected",
    ]


# --------------------------------------------------------------------- #
# StoreApplicationBase — validation
# --------------------------------------------------------------------- #


def test_base_accepts_valid_intake():
    base = StoreApplicationBase.model_validate(_intake_kwargs())
    assert base.business_name == "Acme Vapes"
    assert base.country == "US"  # default
    assert base.location_count == 1  # default
    assert base.terms_accepted is False  # default
    assert base.estimated_weekly_orders is None


def test_base_rejects_missing_business_name():
    payload = _intake_kwargs()
    payload.pop("business_name")
    with pytest.raises(ValidationError):
        StoreApplicationBase.model_validate(payload)


def test_base_rejects_invalid_owner_email():
    with pytest.raises(ValidationError):
        StoreApplicationBase.model_validate(
            _intake_kwargs(owner_email="not-an-email")
        )


def test_base_rejects_business_name_over_200():
    with pytest.raises(ValidationError):
        StoreApplicationBase.model_validate(
            _intake_kwargs(business_name="x" * 201)
        )


def test_base_rejects_country_not_two_chars():
    with pytest.raises(ValidationError):
        StoreApplicationBase.model_validate(_intake_kwargs(country="USA"))


def test_base_rejects_location_count_below_one():
    with pytest.raises(ValidationError):
        StoreApplicationBase.model_validate(_intake_kwargs(location_count=0))


def test_base_rejects_negative_estimated_weekly_orders():
    with pytest.raises(ValidationError):
        StoreApplicationBase.model_validate(
            _intake_kwargs(estimated_weekly_orders=-1)
        )


# --------------------------------------------------------------------- #
# StoreApplicationCreateInternal — normalization
# --------------------------------------------------------------------- #


def test_create_internal_lowercases_and_trims_email():
    model = StoreApplicationCreateInternal.model_validate(
        _intake_kwargs(owner_email="  Jane.Owner@Example.COM  ")
    )
    assert model.owner_email == "jane.owner@example.com"


def test_create_internal_trims_required_strings():
    model = StoreApplicationCreateInternal.model_validate(
        _intake_kwargs(business_name="  Acme Vapes  ", city="  Miami  ")
    )
    assert model.business_name == "Acme Vapes"
    assert model.city == "Miami"


def test_create_internal_rejects_whitespace_only_required():
    with pytest.raises(ValidationError):
        StoreApplicationCreateInternal.model_validate(
            _intake_kwargs(business_name="   ")
        )


def test_create_internal_uppercases_country():
    model = StoreApplicationCreateInternal.model_validate(
        _intake_kwargs(country="us")
    )
    assert model.country == "US"


# --------------------------------------------------------------------- #
# StoreApplicationRead — hydration
# --------------------------------------------------------------------- #


def test_read_hydrates_all_fields_from_orm_like():
    ns = _read_namespace()
    read = StoreApplicationRead.model_validate(ns)
    assert read.id == ns.id
    assert read.business_name == "Acme Vapes"
    assert read.status is ModelStatus.pending_review
    assert read.public_lookup_token == "abc123"
    assert read.provisioned_store_id is None
    assert read.created_at == ns.created_at
    assert read.updated_at == ns.updated_at


def test_read_carries_provisioning_links_when_set():
    store_id = uuid4()
    owner_id = uuid4()
    ns = _read_namespace(
        status=ModelStatus.approved,
        provisioned_store_id=store_id,
        provisioned_owner_user_id=owner_id,
    )
    read = StoreApplicationRead.model_validate(ns)
    assert read.status is ModelStatus.approved
    assert read.provisioned_store_id == store_id
    assert read.provisioned_owner_user_id == owner_id


# --------------------------------------------------------------------- #
# StoreApplicationListItem + ListResponse
# --------------------------------------------------------------------- #


def test_list_item_hydrates_condensed_fields():
    ns = _read_namespace()
    item = StoreApplicationListItem.model_validate(ns)
    assert item.id == ns.id
    assert item.business_name == "Acme Vapes"
    assert item.owner_email == "jane@example.com"
    assert item.status is ModelStatus.pending_review
    assert item.city == "Miami"


def test_list_response_accepts_valid_envelope():
    item = StoreApplicationListItem.model_validate(_read_namespace())
    response = StoreApplicationListResponse.model_validate(
        {"items": [item.model_dump()], "total": 1, "limit": 25, "offset": 0}
    )
    assert response.total == 1
    assert len(response.items) == 1


def test_list_response_rejects_negative_total():
    with pytest.raises(ValidationError):
        StoreApplicationListResponse.model_validate(
            {"items": [], "total": -1, "limit": 25, "offset": 0}
        )


def test_list_response_rejects_limit_below_one():
    with pytest.raises(ValidationError):
        StoreApplicationListResponse.model_validate(
            {"items": [], "total": 0, "limit": 0, "offset": 0}
        )


# --------------------------------------------------------------------- #
# StoreApplicationAuditLogRead
# --------------------------------------------------------------------- #


def test_audit_log_read_hydrates_with_payload():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        application_id=uuid4(),
        event_type="application_created",
        actor_user_id=uuid4(),
        message="created by public intake",
        payload={"source": "public"},
        created_at=now,
    )
    log = StoreApplicationAuditLogRead.model_validate(ns)
    assert log.event_type == "application_created"
    assert log.payload == {"source": "public"}
    assert log.message == "created by public intake"


def test_audit_log_read_hydrates_without_payload_or_actor():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        application_id=uuid4(),
        event_type="application_rejected",
        actor_user_id=None,
        message=None,
        payload=None,
        created_at=now,
    )
    log = StoreApplicationAuditLogRead.model_validate(ns)
    assert log.actor_user_id is None
    assert log.payload is None
    assert log.message is None
