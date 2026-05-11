"""Schema-only tests for the unified audit feed (F2.16.1).

No DB. Exercises every validator in app.schemas.audit:
  - AuditSource enum membership
  - AuditEntityType enum membership
  - AuditEventRead required / nullable / validated fields, ORM hydration
  - AuditEventListResponse envelope bounds and serialization

Style mirrors tests/test_users_schemas.py and
tests/test_inventory_schemas.py: SimpleNamespace for ORM round-trip,
pytest.raises(ValidationError) for negative cases.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.audit import AuditEntityType
from app.schemas.audit import AuditEventListResponse
from app.schemas.audit import AuditEventRead
from app.schemas.audit import AuditSource


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


def _valid_event_payload(**overrides) -> dict:
    """Minimal valid AuditEventRead payload. Defaults to an inventory
    movement so individual tests can flip just the fields they care
    about without re-stating the unrelated ones.
    """
    payload = {
        "id": uuid4(),
        "source": AuditSource.inventory,
        "store_id": uuid4(),
        "actor_id": uuid4(),
        "action": "receipt",
        "entity_type": AuditEntityType.inventory_item,
        "entity_id": uuid4(),
        "summary": "receipt Δ=+10 after=42",
        "metadata": {"quantity_delta": 10, "quantity_after": 42},
        "created_at": datetime.now(UTC),
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- #
# AuditSource
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value", ["inventory", "order", "product_compliance"]
)
def test_audit_source_accepts_valid_values(value: str):
    assert AuditSource(value).value == value


def test_audit_source_rejects_unknown_value():
    with pytest.raises(ValueError):
        AuditSource("user_audit")


def test_audit_source_rejects_empty_value():
    with pytest.raises(ValueError):
        AuditSource("")


# --------------------------------------------------------------------- #
# AuditEntityType
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value", ["inventory_item", "order", "product"]
)
def test_audit_entity_type_accepts_valid_values(value: str):
    assert AuditEntityType(value).value == value


def test_audit_entity_type_rejects_unknown_value():
    with pytest.raises(ValueError):
        AuditEntityType("user")


def test_audit_entity_type_rejects_empty_value():
    with pytest.raises(ValueError):
        AuditEntityType("")


# --------------------------------------------------------------------- #
# AuditEventRead — accepts events from each source
# --------------------------------------------------------------------- #


def test_audit_event_accepts_inventory_event():
    payload = _valid_event_payload(
        source=AuditSource.inventory,
        action="receipt",
        entity_type=AuditEntityType.inventory_item,
    )
    event = AuditEventRead.model_validate(payload)
    assert event.source is AuditSource.inventory
    assert event.entity_type is AuditEntityType.inventory_item
    assert event.action == "receipt"


def test_audit_event_accepts_order_event():
    payload = _valid_event_payload(
        source=AuditSource.order,
        action="status_changed",
        entity_type=AuditEntityType.order,
        summary="pending → accepted",
        metadata={
            "previous_status": "pending",
            "new_status": "accepted",
            "reason": None,
        },
    )
    event = AuditEventRead.model_validate(payload)
    assert event.source is AuditSource.order
    assert event.entity_type is AuditEntityType.order
    assert event.action == "status_changed"
    assert event.metadata["new_status"] == "accepted"


def test_audit_event_accepts_product_compliance_event():
    payload = _valid_event_payload(
        source=AuditSource.product_compliance,
        action="compliance_changed",
        entity_type=AuditEntityType.product,
        summary="allowed/True → banned/False",
        metadata={
            "previous_compliance_status": "allowed",
            "new_compliance_status": "banned",
            "previous_allowed_for_sale": True,
            "new_allowed_for_sale": False,
            "reason": "regulator notice",
        },
    )
    event = AuditEventRead.model_validate(payload)
    assert event.source is AuditSource.product_compliance
    assert event.entity_type is AuditEntityType.product
    assert event.action == "compliance_changed"
    assert event.metadata["new_compliance_status"] == "banned"


# --------------------------------------------------------------------- #
# AuditEventRead — nullable fields
# --------------------------------------------------------------------- #


def test_audit_event_accepts_null_store_id():
    payload = _valid_event_payload(store_id=None)
    event = AuditEventRead.model_validate(payload)
    assert event.store_id is None


def test_audit_event_accepts_null_actor_id():
    payload = _valid_event_payload(actor_id=None)
    event = AuditEventRead.model_validate(payload)
    assert event.actor_id is None


def test_audit_event_accepts_both_store_and_actor_null():
    payload = _valid_event_payload(store_id=None, actor_id=None)
    event = AuditEventRead.model_validate(payload)
    assert event.store_id is None
    assert event.actor_id is None


# --------------------------------------------------------------------- #
# AuditEventRead — metadata
# --------------------------------------------------------------------- #


def test_audit_event_accepts_metadata_dict():
    payload = _valid_event_payload(
        metadata={"some_int": 1, "some_str": "x", "nested": {"k": "v"}}
    )
    event = AuditEventRead.model_validate(payload)
    assert event.metadata == {
        "some_int": 1,
        "some_str": "x",
        "nested": {"k": "v"},
    }


def test_audit_event_metadata_defaults_to_empty_dict():
    payload = _valid_event_payload()
    payload.pop("metadata")
    event = AuditEventRead.model_validate(payload)
    assert event.metadata == {}


def test_audit_event_accepts_empty_metadata_dict():
    payload = _valid_event_payload(metadata={})
    event = AuditEventRead.model_validate(payload)
    assert event.metadata == {}


# --------------------------------------------------------------------- #
# AuditEventRead — action validation
# --------------------------------------------------------------------- #


def test_audit_event_rejects_empty_action():
    payload = _valid_event_payload(action="")
    with pytest.raises(ValidationError):
        AuditEventRead.model_validate(payload)


def test_audit_event_rejects_whitespace_action():
    payload = _valid_event_payload(action="   ")
    with pytest.raises(ValidationError):
        AuditEventRead.model_validate(payload)


def test_audit_event_trims_action_whitespace():
    payload = _valid_event_payload(action="  receipt  ")
    event = AuditEventRead.model_validate(payload)
    assert event.action == "receipt"


# --------------------------------------------------------------------- #
# AuditEventRead — summary validation
# --------------------------------------------------------------------- #


def test_audit_event_rejects_empty_summary():
    payload = _valid_event_payload(summary="")
    with pytest.raises(ValidationError):
        AuditEventRead.model_validate(payload)


def test_audit_event_rejects_whitespace_summary():
    payload = _valid_event_payload(summary="\t \n")
    with pytest.raises(ValidationError):
        AuditEventRead.model_validate(payload)


def test_audit_event_trims_summary_whitespace():
    payload = _valid_event_payload(summary="  receipt Δ=+10  ")
    event = AuditEventRead.model_validate(payload)
    assert event.summary == "receipt Δ=+10"


# --------------------------------------------------------------------- #
# AuditEventRead — enum validation on source / entity_type
# --------------------------------------------------------------------- #


def test_audit_event_rejects_invalid_source():
    payload = _valid_event_payload()
    payload["source"] = "user_audit"
    with pytest.raises(ValidationError):
        AuditEventRead.model_validate(payload)


def test_audit_event_rejects_invalid_entity_type():
    payload = _valid_event_payload()
    payload["entity_type"] = "user"
    with pytest.raises(ValidationError):
        AuditEventRead.model_validate(payload)


def test_audit_event_accepts_source_as_string_value():
    payload = _valid_event_payload()
    payload["source"] = "order"
    payload["entity_type"] = "order"
    event = AuditEventRead.model_validate(payload)
    assert event.source is AuditSource.order
    assert event.entity_type is AuditEntityType.order


# --------------------------------------------------------------------- #
# AuditEventRead — required fields
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "source",
        "action",
        "entity_type",
        "entity_id",
        "summary",
        "created_at",
    ],
)
def test_audit_event_rejects_missing_required_field(missing_field: str):
    payload = _valid_event_payload()
    payload.pop(missing_field)
    with pytest.raises(ValidationError):
        AuditEventRead.model_validate(payload)


# --------------------------------------------------------------------- #
# AuditEventRead — serialization of UUID / datetime
# --------------------------------------------------------------------- #


def test_audit_event_serializes_uuid_and_datetime_in_json():
    event_id = uuid4()
    store_id = uuid4()
    actor_id = uuid4()
    entity_id = uuid4()
    created_at = datetime(2026, 5, 11, 12, 34, 56, tzinfo=UTC)
    payload = _valid_event_payload(
        id=event_id,
        store_id=store_id,
        actor_id=actor_id,
        entity_id=entity_id,
        created_at=created_at,
    )
    event = AuditEventRead.model_validate(payload)
    dumped = event.model_dump(mode="json")
    assert dumped["id"] == str(event_id)
    assert dumped["store_id"] == str(store_id)
    assert dumped["actor_id"] == str(actor_id)
    assert dumped["entity_id"] == str(entity_id)
    assert dumped["created_at"].startswith("2026-05-11T12:34:56")
    assert dumped["source"] == "inventory"
    assert dumped["entity_type"] == "inventory_item"


def test_audit_event_serializes_null_fields_as_none():
    payload = _valid_event_payload(store_id=None, actor_id=None)
    event = AuditEventRead.model_validate(payload)
    dumped = event.model_dump(mode="json")
    assert dumped["store_id"] is None
    assert dumped["actor_id"] is None


# --------------------------------------------------------------------- #
# AuditEventRead — ORM-like hydration via from_attributes
# --------------------------------------------------------------------- #


def test_audit_event_hydrates_from_orm_like_object():
    event_id = uuid4()
    store_id = uuid4()
    actor_id = uuid4()
    entity_id = uuid4()
    created_at = datetime.now(UTC)
    orm_like = SimpleNamespace(
        id=event_id,
        source=AuditSource.inventory,
        store_id=store_id,
        actor_id=actor_id,
        action="adjustment",
        entity_type=AuditEntityType.inventory_item,
        entity_id=entity_id,
        summary="adjustment Δ=-3",
        metadata={"quantity_delta": -3, "quantity_after": 39},
        created_at=created_at,
    )
    event = AuditEventRead.model_validate(orm_like)
    assert event.id == event_id
    assert event.source is AuditSource.inventory
    assert event.store_id == store_id
    assert event.actor_id == actor_id
    assert event.action == "adjustment"
    assert event.entity_id == entity_id
    assert event.metadata["quantity_delta"] == -3
    assert event.created_at == created_at


def test_audit_event_hydrates_from_orm_like_with_string_enums():
    """Aggregator service may build SimpleNamespaces with bare string
    source/entity_type values; the schema must coerce them to enum
    members."""
    orm_like = SimpleNamespace(
        id=uuid4(),
        source="order",
        store_id=uuid4(),
        actor_id=None,
        action="order_canceled",
        entity_type="order",
        entity_id=uuid4(),
        summary="ready → canceled",
        metadata={"reason": "customer request"},
        created_at=datetime.now(UTC),
    )
    event = AuditEventRead.model_validate(orm_like)
    assert event.source is AuditSource.order
    assert event.entity_type is AuditEntityType.order


# --------------------------------------------------------------------- #
# AuditEventListResponse
# --------------------------------------------------------------------- #


def test_audit_list_response_accepts_multiple_items():
    items = [
        AuditEventRead.model_validate(_valid_event_payload()),
        AuditEventRead.model_validate(
            _valid_event_payload(
                source=AuditSource.order,
                action="status_changed",
                entity_type=AuditEntityType.order,
                summary="pending → accepted",
            )
        ),
        AuditEventRead.model_validate(
            _valid_event_payload(
                source=AuditSource.product_compliance,
                action="compliance_changed",
                entity_type=AuditEntityType.product,
                summary="allowed → restricted",
            )
        ),
    ]
    envelope = AuditEventListResponse(
        items=items, total=3, limit=50, offset=0
    )
    assert envelope.total == 3
    assert envelope.limit == 50
    assert envelope.offset == 0
    assert len(envelope.items) == 3
    assert envelope.items[1].source is AuditSource.order


def test_audit_list_response_accepts_empty_items_with_total_zero():
    envelope = AuditEventListResponse(
        items=[], total=0, limit=50, offset=0
    )
    assert envelope.items == []
    assert envelope.total == 0


def test_audit_list_response_accepts_total_greater_than_items():
    """Total reflects pre-pagination count; items reflect the current
    page. A 100-row feed paged at limit=50 yields items=50, total=100."""
    items = [
        AuditEventRead.model_validate(_valid_event_payload())
        for _ in range(2)
    ]
    envelope = AuditEventListResponse(
        items=items, total=100, limit=2, offset=0
    )
    assert envelope.total == 100
    assert len(envelope.items) == 2


def test_audit_list_response_rejects_negative_total():
    with pytest.raises(ValidationError):
        AuditEventListResponse(items=[], total=-1, limit=50, offset=0)


def test_audit_list_response_rejects_zero_limit():
    with pytest.raises(ValidationError):
        AuditEventListResponse(items=[], total=0, limit=0, offset=0)


def test_audit_list_response_rejects_negative_limit():
    with pytest.raises(ValidationError):
        AuditEventListResponse(items=[], total=0, limit=-5, offset=0)


def test_audit_list_response_rejects_negative_offset():
    with pytest.raises(ValidationError):
        AuditEventListResponse(items=[], total=0, limit=50, offset=-1)


def test_audit_list_response_accepts_offset_zero():
    envelope = AuditEventListResponse(
        items=[], total=0, limit=50, offset=0
    )
    assert envelope.offset == 0


def test_audit_list_response_serializes_envelope_in_json():
    item = AuditEventRead.model_validate(_valid_event_payload())
    envelope = AuditEventListResponse(
        items=[item], total=1, limit=25, offset=50
    )
    dumped = envelope.model_dump(mode="json")
    assert dumped["total"] == 1
    assert dumped["limit"] == 25
    assert dumped["offset"] == 50
    assert isinstance(dumped["items"], list)
    assert len(dumped["items"]) == 1
    assert dumped["items"][0]["source"] == "inventory"
    assert isinstance(dumped["items"][0]["id"], str)
    UUID(dumped["items"][0]["id"])  # parseable UUID string
