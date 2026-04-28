"""Schema-only tests for the orders module (S5.4).

No DB. Exercises every validator in app.schemas.orders, with special
emphasis on the trust-boundary rules from `app.domain.orders_rules`
(§2): the frontend MUST NOT supply totals, snapshots or the inventory
binding. Each prohibited field is asserted to produce a 422 via
``extra="forbid"``.
"""

from datetime import UTC
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import OrderStatus
from app.schemas.orders import OrderAuditLogRead
from app.schemas.orders import OrderCancelRequest
from app.schemas.orders import OrderCreate
from app.schemas.orders import OrderItemCreate
from app.schemas.orders import OrderItemRead
from app.schemas.orders import OrderRead
from app.schemas.orders import OrderReturnRequest
from app.schemas.orders import OrderStatusUpdate


# --------------------------------------------------------------------- #
# OrderItemCreate
# --------------------------------------------------------------------- #


class TestOrderItemCreate:
    def test_minimal_valid_payload(self):
        variant_id = uuid4()
        item = OrderItemCreate(variant_id=variant_id, quantity=1)
        assert item.variant_id == variant_id
        assert item.quantity == 1

    def test_quantity_zero_fails(self):
        with pytest.raises(ValidationError):
            OrderItemCreate(variant_id=uuid4(), quantity=0)

    def test_quantity_negative_fails(self):
        with pytest.raises(ValidationError):
            OrderItemCreate(variant_id=uuid4(), quantity=-1)

    def test_quantity_must_be_integer(self):
        with pytest.raises(ValidationError):
            OrderItemCreate(variant_id=uuid4(), quantity="abc")

    def test_variant_id_must_be_uuid(self):
        with pytest.raises(ValidationError):
            OrderItemCreate(variant_id="not-a-uuid", quantity=1)

    @pytest.mark.parametrize(
        "forbidden_key,forbidden_value",
        [
            ("unit_price", "9.99"),
            ("line_total", "19.98"),
            ("inventory_item_id", str(uuid4())),
            ("id", str(uuid4())),
            ("order_id", str(uuid4())),
            ("created_at", datetime.now(UTC).isoformat()),
            ("updated_at", datetime.now(UTC).isoformat()),
        ],
    )
    def test_forbids_server_managed_field(
        self, forbidden_key, forbidden_value
    ):
        # Trust boundary (orders_rules §2): the client must not send
        # monetary snapshots or the inventory binding.
        with pytest.raises(ValidationError) as excinfo:
            OrderItemCreate(
                variant_id=uuid4(),
                quantity=1,
                **{forbidden_key: forbidden_value},
            )
        assert "extra" in str(excinfo.value).lower() or forbidden_key in str(
            excinfo.value
        )


# --------------------------------------------------------------------- #
# OrderCreate
# --------------------------------------------------------------------- #


def _valid_items(n: int = 1) -> list[dict]:
    return [{"variant_id": uuid4(), "quantity": 1} for _ in range(n)]


class TestOrderCreate:
    def test_minimal_valid_payload(self):
        items = _valid_items(2)
        order = OrderCreate(idempotency_key="abc-123", items=items)
        assert order.idempotency_key == "abc-123"
        assert len(order.items) == 2
        assert order.notes is None

    def test_with_notes(self):
        order = OrderCreate(
            idempotency_key="key",
            items=_valid_items(),
            notes="walk-in customer",
        )
        assert order.notes == "walk-in customer"

    def test_idempotency_key_required(self):
        with pytest.raises(ValidationError):
            OrderCreate(items=_valid_items())

    def test_idempotency_key_empty_fails(self):
        with pytest.raises(ValidationError):
            OrderCreate(idempotency_key="", items=_valid_items())

    def test_idempotency_key_whitespace_only_fails(self):
        with pytest.raises(ValidationError):
            OrderCreate(idempotency_key="   ", items=_valid_items())

    def test_idempotency_key_stripped(self):
        order = OrderCreate(
            idempotency_key="  abc-123  ", items=_valid_items()
        )
        assert order.idempotency_key == "abc-123"

    def test_idempotency_key_max_length(self):
        with pytest.raises(ValidationError):
            OrderCreate(
                idempotency_key="x" * 129, items=_valid_items()
            )

    def test_items_required(self):
        with pytest.raises(ValidationError):
            OrderCreate(idempotency_key="key")

    def test_items_empty_fails(self):
        with pytest.raises(ValidationError):
            OrderCreate(idempotency_key="key", items=[])

    def test_duplicate_variant_id_fails(self):
        variant_id = uuid4()
        with pytest.raises(ValidationError) as excinfo:
            OrderCreate(
                idempotency_key="key",
                items=[
                    {"variant_id": variant_id, "quantity": 1},
                    {"variant_id": variant_id, "quantity": 2},
                ],
            )
        assert "duplicate" in str(excinfo.value).lower()

    def test_distinct_variant_ids_pass(self):
        order = OrderCreate(
            idempotency_key="key",
            items=[
                {"variant_id": uuid4(), "quantity": 1},
                {"variant_id": uuid4(), "quantity": 2},
                {"variant_id": uuid4(), "quantity": 3},
            ],
        )
        assert len(order.items) == 3

    def test_notes_empty_string_fails(self):
        with pytest.raises(ValidationError):
            OrderCreate(
                idempotency_key="key", items=_valid_items(), notes=""
            )

    def test_notes_whitespace_only_fails(self):
        with pytest.raises(ValidationError):
            OrderCreate(
                idempotency_key="key", items=_valid_items(), notes="   "
            )

    def test_notes_stripped(self):
        order = OrderCreate(
            idempotency_key="key",
            items=_valid_items(),
            notes="  hello  ",
        )
        assert order.notes == "hello"

    @pytest.mark.parametrize(
        "forbidden_key,forbidden_value",
        [
            ("subtotal_amount", "9.99"),
            ("tax_amount", "0.50"),
            ("total_amount", "10.49"),
            ("status", "pending"),
            ("id", str(uuid4())),
            ("store_id", str(uuid4())),
            ("customer_user_id", str(uuid4())),
            ("created_at", datetime.now(UTC).isoformat()),
            ("updated_at", datetime.now(UTC).isoformat()),
            ("accepted_at", datetime.now(UTC).isoformat()),
            ("delivered_at", datetime.now(UTC).isoformat()),
            ("canceled_at", datetime.now(UTC).isoformat()),
            ("returned_at", datetime.now(UTC).isoformat()),
            ("cancel_reason", "any"),
            ("age_verified_at", datetime.now(UTC).isoformat()),
            ("age_verified_by_user_id", str(uuid4())),
        ],
    )
    def test_forbids_server_managed_field(
        self, forbidden_key, forbidden_value
    ):
        with pytest.raises(ValidationError) as excinfo:
            OrderCreate(
                idempotency_key="key",
                items=_valid_items(),
                **{forbidden_key: forbidden_value},
            )
        assert "extra" in str(excinfo.value).lower() or forbidden_key in str(
            excinfo.value
        )


# --------------------------------------------------------------------- #
# OrderItemRead
# --------------------------------------------------------------------- #


class TestOrderItemRead:
    def test_hydrates_from_orm_like_object(self):
        item_id = uuid4()
        order_id = uuid4()
        variant_id = uuid4()
        inventory_item_id = uuid4()
        now = datetime.now(UTC)
        row = SimpleNamespace(
            id=item_id,
            order_id=order_id,
            variant_id=variant_id,
            inventory_item_id=inventory_item_id,
            quantity=3,
            unit_price=Decimal("9.99"),
            line_total=Decimal("29.97"),
            created_at=now,
            updated_at=now,
        )
        out = OrderItemRead.model_validate(row)
        assert out.id == item_id
        assert out.order_id == order_id
        assert out.variant_id == variant_id
        assert out.inventory_item_id == inventory_item_id
        assert out.quantity == 3
        assert out.unit_price == Decimal("9.99")
        assert out.line_total == Decimal("29.97")


# --------------------------------------------------------------------- #
# OrderRead
# --------------------------------------------------------------------- #


def _orm_order(items: list[SimpleNamespace] | None = None) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        store_id=uuid4(),
        customer_user_id=None,
        idempotency_key="key-1",
        status=OrderStatus.pending,
        subtotal_amount=Decimal("9.99"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("9.99"),
        age_verified_at=None,
        age_verified_by_user_id=None,
        accepted_at=None,
        canceled_at=None,
        delivered_at=None,
        returned_at=None,
        cancel_reason=None,
        notes=None,
        created_at=now,
        updated_at=now,
        items=items or [],
    )


class TestOrderRead:
    def test_hydrates_from_orm_like_object(self):
        row = _orm_order()
        out = OrderRead.model_validate(row)
        assert out.idempotency_key == "key-1"
        assert out.status == OrderStatus.pending
        assert out.subtotal_amount == Decimal("9.99")
        assert out.tax_amount == Decimal("0.00")
        assert out.total_amount == Decimal("9.99")
        assert out.items == []

    def test_hydrates_with_nested_items(self):
        now = datetime.now(UTC)
        item_row = SimpleNamespace(
            id=uuid4(),
            order_id=uuid4(),
            variant_id=uuid4(),
            inventory_item_id=uuid4(),
            quantity=2,
            unit_price=Decimal("4.99"),
            line_total=Decimal("9.98"),
            created_at=now,
            updated_at=now,
        )
        row = _orm_order(items=[item_row])
        out = OrderRead.model_validate(row)
        assert len(out.items) == 1
        assert out.items[0].quantity == 2
        assert out.items[0].line_total == Decimal("9.98")


# --------------------------------------------------------------------- #
# OrderStatusUpdate
# --------------------------------------------------------------------- #


class TestOrderStatusUpdate:
    @pytest.mark.parametrize("status", list(OrderStatus))
    def test_accepts_every_order_status(self, status: OrderStatus):
        # Schema accepts any enum value; the service enforces the
        # transition matrix (orders_rules §3, §6).
        payload = OrderStatusUpdate(new_status=status)
        assert payload.new_status == status

    def test_reason_optional(self):
        payload = OrderStatusUpdate(new_status=OrderStatus.accepted)
        assert payload.reason is None

    def test_reason_stripped(self):
        payload = OrderStatusUpdate(
            new_status=OrderStatus.accepted, reason="  ok  "
        )
        assert payload.reason == "ok"

    def test_reason_empty_fails(self):
        with pytest.raises(ValidationError):
            OrderStatusUpdate(new_status=OrderStatus.accepted, reason="")

    def test_reason_whitespace_only_fails(self):
        with pytest.raises(ValidationError):
            OrderStatusUpdate(
                new_status=OrderStatus.accepted, reason="   "
            )

    def test_invalid_status_fails(self):
        with pytest.raises(ValidationError):
            OrderStatusUpdate(new_status="not-a-status")

    def test_status_required(self):
        with pytest.raises(ValidationError):
            OrderStatusUpdate()

    def test_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            OrderStatusUpdate(
                new_status=OrderStatus.accepted, status="pending"
            )


# --------------------------------------------------------------------- #
# OrderCancelRequest
# --------------------------------------------------------------------- #


class TestOrderCancelRequest:
    def test_valid_payload(self):
        payload = OrderCancelRequest(reason="customer changed mind")
        assert payload.reason == "customer changed mind"

    def test_reason_required(self):
        with pytest.raises(ValidationError):
            OrderCancelRequest()

    def test_reason_empty_fails(self):
        with pytest.raises(ValidationError):
            OrderCancelRequest(reason="")

    def test_reason_whitespace_only_fails(self):
        with pytest.raises(ValidationError):
            OrderCancelRequest(reason="   ")

    def test_reason_stripped(self):
        assert (
            OrderCancelRequest(reason="  out of stock  ").reason
            == "out of stock"
        )

    def test_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            OrderCancelRequest(reason="ok", status="canceled")


# --------------------------------------------------------------------- #
# OrderReturnRequest
# --------------------------------------------------------------------- #


class TestOrderReturnRequest:
    def test_valid_payload(self):
        payload = OrderReturnRequest(reason="defective unit")
        assert payload.reason == "defective unit"

    def test_reason_required(self):
        with pytest.raises(ValidationError):
            OrderReturnRequest()

    def test_reason_empty_fails(self):
        with pytest.raises(ValidationError):
            OrderReturnRequest(reason="")

    def test_reason_whitespace_only_fails(self):
        with pytest.raises(ValidationError):
            OrderReturnRequest(reason="   ")

    def test_reason_stripped(self):
        assert (
            OrderReturnRequest(reason="  warranty  ").reason
            == "warranty"
        )

    def test_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            OrderReturnRequest(reason="ok", status="returned")


# --------------------------------------------------------------------- #
# OrderAuditLogRead
# --------------------------------------------------------------------- #


class TestOrderAuditLogRead:
    def test_hydrates_from_orm_like_object(self):
        row = SimpleNamespace(
            id=uuid4(),
            order_id=uuid4(),
            store_id=uuid4(),
            performed_by_user_id=uuid4(),
            previous_status=OrderStatus.pending,
            new_status=OrderStatus.accepted,
            action="transition",
            reason="ready to fulfill",
            created_at=datetime.now(UTC),
        )
        out = OrderAuditLogRead.model_validate(row)
        assert out.previous_status == OrderStatus.pending
        assert out.new_status == OrderStatus.accepted
        assert out.action == "transition"
        assert out.reason == "ready to fulfill"

    def test_previous_status_can_be_none(self):
        # Creation events have no previous_status.
        row = SimpleNamespace(
            id=uuid4(),
            order_id=uuid4(),
            store_id=uuid4(),
            performed_by_user_id=None,
            previous_status=None,
            new_status=OrderStatus.pending,
            action="create",
            reason=None,
            created_at=datetime.now(UTC),
        )
        out = OrderAuditLogRead.model_validate(row)
        assert out.previous_status is None
        assert out.performed_by_user_id is None
        assert out.reason is None
