"""Schema-only tests for the inventory module (S4).

No DB. Exercises every validator in app.schemas.inventory:
  - InventoryItemCreate quantity / threshold rules
  - InventoryItemUpdate threshold + status rules
  - Movement schemas: positive quantity vs signed delta
  - Reason mandatory/optional per movement type
  - reference_type + reference_id pair rule
  - Read schemas hydrating from ORM-like objects

Style mirrors tests/test_products.py: parametrize for matrices,
SimpleNamespace for ORM round-trip checks.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import ComplianceStatus
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.schemas.inventory import AdjustStockRequest
from app.schemas.inventory import DamageStockRequest
from app.schemas.inventory import InventoryItemCreate
from app.schemas.inventory import InventoryItemRead
from app.schemas.inventory import InventoryItemUpdate
from app.schemas.inventory import InventoryLogRead
from app.schemas.inventory import ReceiveStockRequest
from app.schemas.inventory import ReleaseReservationRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import ReturnStockRequest
from app.schemas.inventory import SaleStockRequest


def _make_orm_like_inventory_item(
    *,
    variant_overrides: dict | None = None,
    product_overrides: dict | None = None,
    item_overrides: dict | None = None,
):
    """Build a SimpleNamespace tree that mirrors the ORM shape needed
    by `InventoryItemRead.model_validate(...)` after BIE.1.

    Centralised so that adding/removing fields on the summary schemas
    only changes one place. Defaults reflect a typical "available, in
    stock, sellable" item.
    """
    now = datetime.now(UTC)
    product_kwargs = {
        "id": uuid4(),
        "name": "ACME Vape",
        "brand": "ACME",
        "category": "vape",
        "compliance_status": ComplianceStatus.allowed,
        "allowed_for_sale": True,
        "is_active": True,
        **(product_overrides or {}),
    }
    product = SimpleNamespace(**product_kwargs)

    variant_kwargs = {
        "id": uuid4(),
        "sku": "ACME-001",
        "flavor": "mint",
        "size_label": "2ml",
        "is_active": True,
        "product": product,
        **(variant_overrides or {}),
    }
    variant = SimpleNamespace(**variant_kwargs)

    item_kwargs = {
        "id": uuid4(),
        "store_id": uuid4(),
        "variant_id": variant.id,
        "quantity_on_hand": 10,
        "quantity_reserved": 2,
        "reorder_threshold": 3,
        "status": InventoryStatus.available,
        "last_counted_at": None,
        "created_at": now,
        "updated_at": now,
        "variant": variant,
        **(item_overrides or {}),
    }
    item = SimpleNamespace(**item_kwargs)
    return item, variant, product


# --------------------------------------------------------------------- #
# InventoryItemCreate
# --------------------------------------------------------------------- #


class TestInventoryItemCreate:
    def test_valid_payload_passes(self):
        variant_id = uuid4()
        payload = InventoryItemCreate(
            variant_id=variant_id,
            quantity_on_hand=10,
            quantity_reserved=2,
            reorder_threshold=5,
            status=InventoryStatus.available,
        )
        assert payload.variant_id == variant_id
        assert payload.quantity_on_hand == 10
        assert payload.quantity_reserved == 2
        assert payload.reorder_threshold == 5

    def test_minimal_payload_uses_zero_defaults(self):
        payload = InventoryItemCreate(variant_id=uuid4())
        assert payload.quantity_on_hand == 0
        assert payload.quantity_reserved == 0
        assert payload.reorder_threshold == 0
        assert payload.status == InventoryStatus.available

    def test_negative_quantity_on_hand_fails(self):
        with pytest.raises(ValidationError):
            InventoryItemCreate(variant_id=uuid4(), quantity_on_hand=-1)

    def test_negative_quantity_reserved_fails(self):
        with pytest.raises(ValidationError):
            InventoryItemCreate(variant_id=uuid4(), quantity_reserved=-1)

    def test_negative_reorder_threshold_fails(self):
        with pytest.raises(ValidationError):
            InventoryItemCreate(variant_id=uuid4(), reorder_threshold=-1)

    def test_reserved_exceeding_on_hand_fails(self):
        with pytest.raises(ValidationError) as excinfo:
            InventoryItemCreate(
                variant_id=uuid4(),
                quantity_on_hand=2,
                quantity_reserved=5,
            )
        assert "quantity_reserved" in str(excinfo.value)

    def test_reserved_equal_to_on_hand_passes(self):
        # Edge case — equality is allowed (DB CHECK is `<=`)
        payload = InventoryItemCreate(
            variant_id=uuid4(),
            quantity_on_hand=3,
            quantity_reserved=3,
        )
        assert payload.quantity_reserved == 3


# --------------------------------------------------------------------- #
# InventoryItemUpdate
# --------------------------------------------------------------------- #


class TestInventoryItemUpdate:
    def test_empty_payload_passes(self):
        # Fully partial — no fields required
        payload = InventoryItemUpdate()
        assert payload.reorder_threshold is None
        assert payload.status is None

    def test_threshold_zero_passes(self):
        assert InventoryItemUpdate(reorder_threshold=0).reorder_threshold == 0

    def test_threshold_positive_passes(self):
        assert InventoryItemUpdate(reorder_threshold=10).reorder_threshold == 10

    def test_negative_threshold_fails(self):
        with pytest.raises(ValidationError):
            InventoryItemUpdate(reorder_threshold=-1)

    @pytest.mark.parametrize(
        "value",
        [
            InventoryStatus.available,
            InventoryStatus.flagged,
            InventoryStatus.quarantined,
            InventoryStatus.reserved,  # accepted at schema layer; service rejects
            InventoryStatus.sold,
        ],
    )
    def test_status_accepts_inventory_status(self, value: InventoryStatus):
        # The schema accepts any enum value; the service is responsible
        # for rejecting the legacy `reserved`/`sold` per inventory_rules §4.
        payload = InventoryItemUpdate(status=value)
        assert payload.status == value


# --------------------------------------------------------------------- #
# Movement schemas — quantity rules
# --------------------------------------------------------------------- #


_QUANTITY_SCHEMAS: list[tuple[type, dict]] = [
    (ReceiveStockRequest, {}),
    (DamageStockRequest, {"reason": "broken"}),
    (SaleStockRequest, {}),
    (ReserveStockRequest, {}),
    (ReleaseReservationRequest, {}),
    (ReturnStockRequest, {"reason": "defect"}),
]


class TestMovementQuantityRules:
    @pytest.mark.parametrize("schema_cls,extra", _QUANTITY_SCHEMAS)
    def test_quantity_one_passes(self, schema_cls, extra):
        obj = schema_cls(quantity=1, **extra)
        assert obj.quantity == 1

    @pytest.mark.parametrize("schema_cls,extra", _QUANTITY_SCHEMAS)
    def test_quantity_zero_fails(self, schema_cls, extra):
        with pytest.raises(ValidationError):
            schema_cls(quantity=0, **extra)

    @pytest.mark.parametrize("schema_cls,extra", _QUANTITY_SCHEMAS)
    def test_quantity_negative_fails(self, schema_cls, extra):
        with pytest.raises(ValidationError):
            schema_cls(quantity=-1, **extra)


class TestAdjustStockDeltaRule:
    def test_positive_delta_passes(self):
        assert AdjustStockRequest(delta=5, reason="recount").delta == 5

    def test_negative_delta_passes(self):
        assert AdjustStockRequest(delta=-3, reason="loss").delta == -3

    def test_delta_zero_fails(self):
        with pytest.raises(ValidationError):
            AdjustStockRequest(delta=0, reason="no-op")


# --------------------------------------------------------------------- #
# Movement schemas — reason rules
# --------------------------------------------------------------------- #


class TestRequiredReasonMovements:
    """Adjust, damage and return require a non-empty reason."""

    @pytest.mark.parametrize(
        "schema_cls,base",
        [
            (AdjustStockRequest, {"delta": 1}),
            (DamageStockRequest, {"quantity": 1}),
            (ReturnStockRequest, {"quantity": 1}),
        ],
    )
    def test_reason_missing_fails(self, schema_cls, base):
        with pytest.raises(ValidationError):
            schema_cls(**base)

    @pytest.mark.parametrize(
        "schema_cls,base",
        [
            (AdjustStockRequest, {"delta": 1}),
            (DamageStockRequest, {"quantity": 1}),
            (ReturnStockRequest, {"quantity": 1}),
        ],
    )
    def test_reason_empty_fails(self, schema_cls, base):
        with pytest.raises(ValidationError):
            schema_cls(**base, reason="")

    @pytest.mark.parametrize(
        "schema_cls,base",
        [
            (AdjustStockRequest, {"delta": 1}),
            (DamageStockRequest, {"quantity": 1}),
            (ReturnStockRequest, {"quantity": 1}),
        ],
    )
    def test_reason_whitespace_fails(self, schema_cls, base):
        with pytest.raises(ValidationError):
            schema_cls(**base, reason="   ")

    @pytest.mark.parametrize(
        "schema_cls,base",
        [
            (AdjustStockRequest, {"delta": 1}),
            (DamageStockRequest, {"quantity": 1}),
            (ReturnStockRequest, {"quantity": 1}),
        ],
    )
    def test_reason_trimmed(self, schema_cls, base):
        obj = schema_cls(**base, reason="  legit reason  ")
        assert obj.reason == "legit reason"


class TestOptionalReasonMovements:
    """Receive, sale, reserve and release accept omitted reason."""

    @pytest.mark.parametrize(
        "schema_cls",
        [
            ReceiveStockRequest,
            SaleStockRequest,
            ReserveStockRequest,
            ReleaseReservationRequest,
        ],
    )
    def test_reason_omitted_passes(self, schema_cls):
        obj = schema_cls(quantity=1)
        assert obj.reason is None

    @pytest.mark.parametrize(
        "schema_cls",
        [
            ReceiveStockRequest,
            SaleStockRequest,
            ReserveStockRequest,
            ReleaseReservationRequest,
        ],
    )
    def test_reason_explicit_none_passes(self, schema_cls):
        obj = schema_cls(quantity=1, reason=None)
        assert obj.reason is None

    @pytest.mark.parametrize(
        "schema_cls",
        [
            ReceiveStockRequest,
            SaleStockRequest,
            ReserveStockRequest,
            ReleaseReservationRequest,
        ],
    )
    def test_whitespace_reason_still_rejected_when_provided(self, schema_cls):
        # Optional doesn't mean "anything"; whitespace-only is rejected.
        with pytest.raises(ValidationError):
            schema_cls(quantity=1, reason="   ")


# --------------------------------------------------------------------- #
# Reference pair rule
# --------------------------------------------------------------------- #


class TestReferencePairRule:
    def test_both_null_passes(self):
        obj = SaleStockRequest(quantity=1)
        assert obj.reference_type is None
        assert obj.reference_id is None

    def test_both_set_passes(self):
        ref_id = uuid4()
        obj = SaleStockRequest(
            quantity=1, reference_type="order", reference_id=ref_id
        )
        assert obj.reference_type == "order"
        assert obj.reference_id == ref_id

    def test_only_reference_type_fails(self):
        with pytest.raises(ValidationError):
            SaleStockRequest(quantity=1, reference_type="order")

    def test_only_reference_id_fails(self):
        with pytest.raises(ValidationError):
            SaleStockRequest(quantity=1, reference_id=uuid4())

    def test_pair_rule_applies_to_other_movements(self):
        # The rule lives on the shared base class, so it's identical
        # across every movement schema.
        ref_id = uuid4()
        for schema_cls in (
            ReceiveStockRequest,
            ReserveStockRequest,
            ReleaseReservationRequest,
        ):
            with pytest.raises(ValidationError):
                schema_cls(quantity=1, reference_type="order")
            with pytest.raises(ValidationError):
                schema_cls(quantity=1, reference_id=ref_id)


# --------------------------------------------------------------------- #
# Read schemas — ORM hydration
# --------------------------------------------------------------------- #


class TestReadSchemas:
    def test_inventory_item_read_validates_orm_like_object(self):
        # BIE.1 added a non-optional `variant` (with nested product).
        # The helper builds the full ORM-like tree; assertions below
        # cover the original quantity/status fields that this test
        # was guarding before enrichment.
        item, _, _ = _make_orm_like_inventory_item()
        read = InventoryItemRead.model_validate(item)
        assert read.quantity_on_hand == 10
        assert read.quantity_reserved == 2
        assert read.status == InventoryStatus.available

    def test_inventory_item_read_includes_variant_summary(self):
        item, variant, _ = _make_orm_like_inventory_item(
            variant_overrides={"sku": "ABC-XYZ", "flavor": "menthol"}
        )
        read = InventoryItemRead.model_validate(item)
        assert read.variant.id == variant.id
        assert read.variant.sku == "ABC-XYZ"
        assert read.variant.flavor == "menthol"
        assert read.variant.is_active is True

    def test_inventory_item_read_includes_product_summary(self):
        item, _, product = _make_orm_like_inventory_item(
            product_overrides={
                "name": "Coca-Cola Classic",
                "brand": "Coca-Cola",
                "category": "beverage",
            }
        )
        read = InventoryItemRead.model_validate(item)
        assert read.variant.product.id == product.id
        assert read.variant.product.name == "Coca-Cola Classic"
        assert read.variant.product.brand == "Coca-Cola"
        assert read.variant.product.category == "beverage"
        assert read.variant.product.allowed_for_sale is True
        assert read.variant.product.is_active is True

    def test_inventory_item_read_serializes_compliance_status(self):
        # BIE.1 introduced ComplianceStatus to the inventory response
        # tree (previously products-only). Round-trip through Pydantic
        # to confirm the enum keeps its wire value.
        item, _, _ = _make_orm_like_inventory_item(
            product_overrides={"compliance_status": ComplianceStatus.banned}
        )
        read = InventoryItemRead.model_validate(item)
        assert read.variant.product.compliance_status == ComplianceStatus.banned
        dumped = read.model_dump(mode="json")
        assert dumped["variant"]["product"]["compliance_status"] == "banned"

    def test_inventory_log_read_validates_orm_like_object(self):
        now = datetime.now(UTC)
        ref_id = uuid4()
        log = SimpleNamespace(
            id=uuid4(),
            inventory_item_id=uuid4(),
            store_id=uuid4(),
            variant_id=uuid4(),
            performed_by_user_id=uuid4(),
            movement_type=InventoryMovementType.sale,
            quantity_delta=-1,
            quantity_after=9,
            reason=None,
            reference_type="order",
            reference_id=ref_id,
            created_at=now,
        )
        read = InventoryLogRead.model_validate(log)
        assert read.movement_type == InventoryMovementType.sale
        assert read.quantity_delta == -1
        assert read.quantity_after == 9
        assert read.reference_id == ref_id
