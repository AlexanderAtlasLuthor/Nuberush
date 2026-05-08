"""Schema-only tests for the stores module (F2.14.1).

No DB. Exercises:
  - StoreRead hydrating from an ORM-like object via `from_attributes`.
  - StoreUpdate partial / trim / non-empty / length validation.
  - StoreUpdate `extra="forbid"` rejecting read-only columns.

Style mirrors tests/test_inventory_schemas.py: SimpleNamespace for the
ORM round-trip and pytest.raises(ValidationError) for negative cases.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
