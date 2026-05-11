"""Schema-only tests for the stores module (F2.14.1 + F2.17.1).

No DB. Exercises:
  - StoreRead hydrating from an ORM-like object via `from_attributes`.
  - StoreUpdate partial / trim / non-empty / length validation.
  - StoreUpdate `extra="forbid"` rejecting read-only columns.
  - StoreCreate (F2.17.1): required-field trim, default timezone,
    `extra="forbid"` rejecting read-only columns and fields that would
    require a migration to back.
  - StoreListResponse (F2.17.1): paginated envelope bounds.

Style mirrors tests/test_inventory_schemas.py: SimpleNamespace for the
ORM round-trip and pytest.raises(ValidationError) for negative cases.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.stores import StoreCreate
from app.schemas.stores import StoreListResponse
from app.schemas.stores import StoreRead
from app.schemas.stores import StoreUpdate


# --------------------------------------------------------------------- #
# StoreRead
# --------------------------------------------------------------------- #


def test_store_read_serializes_existing_fields():
    now = datetime.now(UTC)
    store_id = uuid4()
    orm_like = SimpleNamespace(
        id=store_id,
        name="Acme HQ",
        code="ACME-HQ",
        is_active=True,
        timezone="America/New_York",
        created_at=now,
        updated_at=now,
    )

    read = StoreRead.model_validate(orm_like)

    assert read.id == store_id
    assert read.name == "Acme HQ"
    assert read.code == "ACME-HQ"
    assert read.is_active is True
    assert read.timezone == "America/New_York"
    assert read.created_at == now
    assert read.updated_at == now


# --------------------------------------------------------------------- #
# StoreUpdate — happy path
# --------------------------------------------------------------------- #


def test_store_update_accepts_name():
    payload = StoreUpdate.model_validate({"name": "New Name"})
    assert payload.name == "New Name"
    assert payload.timezone is None


def test_store_update_accepts_timezone():
    payload = StoreUpdate.model_validate({"timezone": "America/Chicago"})
    assert payload.timezone == "America/Chicago"
    assert payload.name is None


def test_store_update_accepts_partial_payload_name_only():
    payload = StoreUpdate.model_validate({"name": "Solo Name"})
    dump = payload.model_dump(exclude_unset=True)
    assert dump == {"name": "Solo Name"}


def test_store_update_accepts_partial_payload_timezone_only():
    payload = StoreUpdate.model_validate({"timezone": "America/Chicago"})
    dump = payload.model_dump(exclude_unset=True)
    assert dump == {"timezone": "America/Chicago"}


def test_store_update_accepts_empty_payload():
    payload = StoreUpdate.model_validate({})
    assert payload.name is None
    assert payload.timezone is None
    assert payload.model_dump(exclude_unset=True) == {}


def test_store_update_trims_name():
    payload = StoreUpdate.model_validate({"name": "  Trimmed  "})
    assert payload.name == "Trimmed"


def test_store_update_trims_timezone():
    payload = StoreUpdate.model_validate({"timezone": "  America/Chicago  "})
    assert payload.timezone == "America/Chicago"


# --------------------------------------------------------------------- #
# StoreUpdate — rejection: empty / whitespace strings
# --------------------------------------------------------------------- #


def test_store_update_rejects_empty_name():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"name": ""})


def test_store_update_rejects_whitespace_name():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"name": "   "})


def test_store_update_rejects_empty_timezone():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"timezone": ""})


def test_store_update_rejects_whitespace_timezone():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"timezone": "   "})


# --------------------------------------------------------------------- #
# StoreUpdate — rejection: length bounds (mirror DB VARCHAR limits)
# --------------------------------------------------------------------- #


def test_store_update_rejects_name_over_150():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"name": "x" * 151})


def test_store_update_rejects_timezone_over_50():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"timezone": "x" * 51})


# --------------------------------------------------------------------- #
# StoreUpdate — rejection: extra fields are forbidden
# --------------------------------------------------------------------- #


def test_store_update_rejects_extra_code():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"code": "ANY-CODE"})


def test_store_update_rejects_extra_is_active():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"is_active": False})


def test_store_update_rejects_extra_created_at():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate(
            {"created_at": datetime.now(UTC).isoformat()}
        )


def test_store_update_rejects_extra_updated_at():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate(
            {"updated_at": datetime.now(UTC).isoformat()}
        )


def test_store_update_rejects_unknown_extra_field():
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"foo": "bar"})


# --------------------------------------------------------------------- #
# StoreCreate — happy path
# --------------------------------------------------------------------- #


def test_store_create_accepts_valid_payload():
    payload = StoreCreate.model_validate(
        {"name": "Acme HQ", "code": "ACME-HQ", "timezone": "America/Chicago"}
    )
    assert payload.name == "Acme HQ"
    assert payload.code == "ACME-HQ"
    assert payload.timezone == "America/Chicago"


def test_store_create_applies_default_timezone_when_omitted():
    payload = StoreCreate.model_validate({"name": "Acme HQ", "code": "ACME-HQ"})
    assert payload.timezone == "America/New_York"


def test_store_create_trims_name():
    payload = StoreCreate.model_validate(
        {"name": "  Acme HQ  ", "code": "ACME-HQ"}
    )
    assert payload.name == "Acme HQ"


def test_store_create_trims_code():
    payload = StoreCreate.model_validate(
        {"name": "Acme HQ", "code": "  ACME-HQ  "}
    )
    assert payload.code == "ACME-HQ"


def test_store_create_trims_timezone():
    payload = StoreCreate.model_validate(
        {
            "name": "Acme HQ",
            "code": "ACME-HQ",
            "timezone": "  America/Chicago  ",
        }
    )
    assert payload.timezone == "America/Chicago"


# --------------------------------------------------------------------- #
# StoreCreate — rejection: empty / whitespace strings
# --------------------------------------------------------------------- #


def test_store_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate({"name": "", "code": "ACME-HQ"})


def test_store_create_rejects_whitespace_name():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate({"name": "   ", "code": "ACME-HQ"})


def test_store_create_rejects_empty_code():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate({"name": "Acme HQ", "code": ""})


def test_store_create_rejects_whitespace_code():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate({"name": "Acme HQ", "code": "   "})


def test_store_create_rejects_empty_timezone():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {"name": "Acme HQ", "code": "ACME-HQ", "timezone": ""}
        )


def test_store_create_rejects_whitespace_timezone():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {"name": "Acme HQ", "code": "ACME-HQ", "timezone": "   "}
        )


# --------------------------------------------------------------------- #
# StoreCreate — rejection: extra fields are forbidden
# --------------------------------------------------------------------- #


def test_store_create_rejects_unknown_extra_field():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {"name": "Acme HQ", "code": "ACME-HQ", "foo": "bar"}
        )


def test_store_create_rejects_is_active():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {"name": "Acme HQ", "code": "ACME-HQ", "is_active": True}
        )


def test_store_create_rejects_id():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {"name": "Acme HQ", "code": "ACME-HQ", "id": str(uuid4())}
        )


def test_store_create_rejects_created_at():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {
                "name": "Acme HQ",
                "code": "ACME-HQ",
                "created_at": datetime.now(UTC).isoformat(),
            }
        )


def test_store_create_rejects_updated_at():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {
                "name": "Acme HQ",
                "code": "ACME-HQ",
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )


def test_store_create_rejects_contact_email():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {
                "name": "Acme HQ",
                "code": "ACME-HQ",
                "contact_email": "hello@acme.test",
            }
        )


def test_store_create_rejects_contact_phone():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {
                "name": "Acme HQ",
                "code": "ACME-HQ",
                "contact_phone": "+1 555 0100",
            }
        )


def test_store_create_rejects_address():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {
                "name": "Acme HQ",
                "code": "ACME-HQ",
                "address": "1 Test Way",
            }
        )


def test_store_create_rejects_preferences():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {
                "name": "Acme HQ",
                "code": "ACME-HQ",
                "preferences": {"theme": "dark"},
            }
        )


def test_store_create_rejects_business_hours():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {
                "name": "Acme HQ",
                "code": "ACME-HQ",
                "business_hours": "9-5",
            }
        )


def test_store_create_rejects_status():
    with pytest.raises(ValidationError):
        StoreCreate.model_validate(
            {"name": "Acme HQ", "code": "ACME-HQ", "status": "active"}
        )


# --------------------------------------------------------------------- #
# StoreListResponse
# --------------------------------------------------------------------- #


def _store_read_sample() -> StoreRead:
    now = datetime.now(UTC)
    return StoreRead.model_validate(
        SimpleNamespace(
            id=uuid4(),
            name="Acme HQ",
            code="ACME-HQ",
            is_active=True,
            timezone="America/New_York",
            created_at=now,
            updated_at=now,
        )
    )


def test_store_list_response_accepts_valid_envelope():
    item = _store_read_sample()
    response = StoreListResponse.model_validate(
        {"items": [item.model_dump()], "total": 1, "limit": 25, "offset": 0}
    )
    assert response.total == 1
    assert response.limit == 25
    assert response.offset == 0
    assert len(response.items) == 1
    assert response.items[0].id == item.id


def test_store_list_response_accepts_empty_items():
    response = StoreListResponse.model_validate(
        {"items": [], "total": 0, "limit": 25, "offset": 0}
    )
    assert response.items == []
    assert response.total == 0
    assert response.limit == 25
    assert response.offset == 0


def test_store_list_response_rejects_negative_total():
    with pytest.raises(ValidationError):
        StoreListResponse.model_validate(
            {"items": [], "total": -1, "limit": 25, "offset": 0}
        )


def test_store_list_response_rejects_limit_below_one():
    with pytest.raises(ValidationError):
        StoreListResponse.model_validate(
            {"items": [], "total": 0, "limit": 0, "offset": 0}
        )


def test_store_list_response_rejects_negative_offset():
    with pytest.raises(ValidationError):
        StoreListResponse.model_validate(
            {"items": [], "total": 0, "limit": 25, "offset": -1}
        )
