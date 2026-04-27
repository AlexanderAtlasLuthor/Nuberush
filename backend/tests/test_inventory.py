"""Integration tests for the inventory module (S4).

Locks in the behaviours validated manually during S4.1–S4.5:
  - schema validators (no DB)
  - service layer transactions (per-test session)
  - API RBAC + tenancy (TestClient)
  - compliance cascade (banned product → items quarantined, no
    InventoryLog row written)
  - sellability gate (banned/inactive/quarantined blocks sale)

Style mirrors tests/test_products.py.
"""

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.core.security import hash_password
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.inventory import AdjustStockRequest
from app.schemas.inventory import DamageStockRequest
from app.schemas.inventory import InventoryItemCreate
from app.schemas.inventory import ReceiveStockRequest
from app.schemas.inventory import ReleaseReservationRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import ReturnStockRequest
from app.schemas.inventory import SaleStockRequest
from app.services import inventory as inv
from app.services import products as prod_svc
from app.schemas.products import ProductComplianceUpdate


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(code: str | None = None) -> Store:
        store = Store(name="Inv-QA", code=code or f"iq-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session, make_store) -> Callable[..., User]:
    def _create(role: UserRole, store_id: uuid.UUID | None = None) -> User:
        if role == UserRole.admin:
            sid = None
        else:
            sid = store_id if store_id is not None else make_store().id
        user = User(
            full_name=f"Inv {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("supersecret123"),
            role=role,
            store_id=sid,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
        is_active: bool = True,
    ) -> Product:
        product = Product(
            name=f"P-{uuid.uuid4().hex[:6]}",
            category="vape",
            compliance_status=compliance_status,
            allowed_for_sale=allowed_for_sale,
            is_active=is_active,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


@pytest.fixture
def make_variant(
    db_session: Session, make_product
) -> Callable[..., ProductVariant]:
    def _create(
        product: Product | None = None,
        is_active: bool = True,
    ) -> ProductVariant:
        prod = product if product is not None else make_product()
        variant = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=is_active,
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_item(
    db_session: Session, make_store, make_variant
) -> Callable[..., InventoryItem]:
    def _create(
        store: Store | None = None,
        variant: ProductVariant | None = None,
        quantity_on_hand: int = 10,
        quantity_reserved: int = 0,
        status: InventoryStatus = InventoryStatus.available,
    ) -> InventoryItem:
        s = store if store is not None else make_store()
        v = variant if variant is not None else make_variant()
        item = InventoryItem(
            store_id=s.id,
            variant_id=v.id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            status=status,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


# --------------------------------------------------------------------- #
# Schema validators (no DB)
# --------------------------------------------------------------------- #


class TestInventoryItemCreateSchema:
    def test_minimal_payload(self):
        payload = InventoryItemCreate(variant_id=uuid.uuid4())
        assert payload.quantity_on_hand == 0
        assert payload.quantity_reserved == 0
        assert payload.status == InventoryStatus.available

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            InventoryItemCreate(variant_id=uuid.uuid4(), quantity_on_hand=-1)

    def test_reserved_exceeding_on_hand_rejected(self):
        with pytest.raises(ValidationError):
            InventoryItemCreate(
                variant_id=uuid.uuid4(),
                quantity_on_hand=2,
                quantity_reserved=5,
            )


class TestMovementSchemaRules:
    @pytest.mark.parametrize(
        "schema_cls,extra",
        [
            (ReceiveStockRequest, {}),
            (DamageStockRequest, {"reason": "broken"}),
            (SaleStockRequest, {}),
            (ReserveStockRequest, {}),
            (ReleaseReservationRequest, {}),
            (ReturnStockRequest, {"reason": "defect"}),
        ],
    )
    def test_quantity_must_be_positive(self, schema_cls, extra):
        for bad in (0, -1):
            with pytest.raises(ValidationError):
                schema_cls(quantity=bad, **extra)

    def test_adjust_delta_non_zero(self):
        AdjustStockRequest(delta=5, reason="ok")
        AdjustStockRequest(delta=-5, reason="ok")
        with pytest.raises(ValidationError):
            AdjustStockRequest(delta=0, reason="ok")

    @pytest.mark.parametrize(
        "schema_cls,base",
        [
            (AdjustStockRequest, {"delta": 1}),
            (DamageStockRequest, {"quantity": 1}),
            (ReturnStockRequest, {"quantity": 1}),
        ],
    )
    def test_required_reason(self, schema_cls, base):
        for bad_reason in ["", "   "]:
            with pytest.raises(ValidationError):
                schema_cls(**base, reason=bad_reason)
        # also rejects missing reason
        with pytest.raises(ValidationError):
            schema_cls(**base)

    def test_reference_must_be_paired(self):
        ref_id = uuid.uuid4()
        SaleStockRequest(quantity=1)
        SaleStockRequest(quantity=1, reference_type="order", reference_id=ref_id)
        with pytest.raises(ValidationError):
            SaleStockRequest(quantity=1, reference_type="order")
        with pytest.raises(ValidationError):
            SaleStockRequest(quantity=1, reference_id=ref_id)


# --------------------------------------------------------------------- #
# Service layer — movements
# --------------------------------------------------------------------- #


class TestServiceMovements:
    def test_receive_increases_on_hand_and_writes_log(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=5)
        result = inv.receive_stock(
            db_session, item.id,
            ReceiveStockRequest(quantity=3),
            admin.id,
        )
        assert result.quantity_on_hand == 8
        log = db_session.scalar(
            select(InventoryLog).where(InventoryLog.inventory_item_id == item.id)
        )
        assert log is not None
        assert log.quantity_delta == 3
        assert log.quantity_after == 8

    def test_adjust_signed_delta(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=10)
        inv.adjust_stock(
            db_session, item.id,
            AdjustStockRequest(delta=-3, reason="recount"),
            admin.id,
        )
        db_session.refresh(item)
        assert item.quantity_on_hand == 7

    def test_sale_uses_available_not_on_hand(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=10, quantity_reserved=8)
        # available = 2; selling 3 must fail even though on_hand=10
        with pytest.raises(Exception) as excinfo:
            inv.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=3), admin.id,
            )
        assert excinfo.value.status_code == 422  # type: ignore[attr-defined]
        assert "available" in excinfo.value.detail.lower()  # type: ignore[attr-defined]

    def test_reserve_release_round_trip(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=10)
        inv.reserve_inventory(
            db_session, item.id,
            ReserveStockRequest(quantity=4), admin.id,
        )
        db_session.refresh(item)
        assert item.quantity_reserved == 4
        inv.release_reservation(
            db_session, item.id,
            ReleaseReservationRequest(quantity=4), admin.id,
        )
        db_session.refresh(item)
        assert item.quantity_reserved == 0

    def test_release_more_than_reserved_rejected(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_reserved=2, quantity_on_hand=5)
        with pytest.raises(Exception) as excinfo:
            inv.release_reservation(
                db_session, item.id,
                ReleaseReservationRequest(quantity=5), admin.id,
            )
        assert excinfo.value.status_code == 422  # type: ignore[attr-defined]

    def test_return_increases_on_hand(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=5)
        inv.return_to_inventory(
            db_session, item.id,
            ReturnStockRequest(quantity=2, reason="customer return"),
            admin.id,
        )
        db_session.refresh(item)
        assert item.quantity_on_hand == 7


class TestServiceSellabilityGate:
    def test_quarantined_blocks_sale(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=10, status=InventoryStatus.quarantined)
        with pytest.raises(Exception) as excinfo:
            inv.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422  # type: ignore[attr-defined]
        assert "quarantined" in excinfo.value.detail.lower()  # type: ignore[attr-defined]

    def test_quarantined_blocks_reserve(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=10, status=InventoryStatus.quarantined)
        with pytest.raises(Exception) as excinfo:
            inv.reserve_inventory(
                db_session, item.id,
                ReserveStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422  # type: ignore[attr-defined]

    def test_receive_works_on_quarantined(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=5, status=InventoryStatus.quarantined)
        inv.receive_stock(
            db_session, item.id,
            ReceiveStockRequest(quantity=3), admin.id,
        )
        db_session.refresh(item)
        assert item.quantity_on_hand == 8

    def test_inactive_variant_blocks_sale(
        self, db_session: Session, make_variant, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        variant = make_variant(is_active=False)
        item = make_item(variant=variant, quantity_on_hand=10)
        with pytest.raises(Exception) as excinfo:
            inv.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422  # type: ignore[attr-defined]


class TestServiceAtomicity:
    def test_failed_sale_leaves_no_log_and_no_change(
        self, db_session: Session, make_item, make_user
    ):
        admin = make_user(UserRole.admin)
        item = make_item(quantity_on_hand=2)
        n_before = db_session.scalar(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == item.id
            )
        )
        with pytest.raises(Exception):
            inv.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=99), admin.id,
            )
        db_session.refresh(item)
        assert item.quantity_on_hand == 2
        n_after = db_session.scalar(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == item.id
            )
        )
        assert n_before == n_after  # both None, or both same row count


# --------------------------------------------------------------------- #
# Compliance cascade
# --------------------------------------------------------------------- #


class TestComplianceCascade:
    def test_ban_quarantines_all_items_for_product(
        self,
        db_session: Session,
        make_store,
        make_product,
        make_variant,
        make_item,
        make_user,
    ):
        admin = make_user(UserRole.admin)
        product = make_product()
        v1 = make_variant(product=product)
        v2 = make_variant(product=product)
        s1 = make_store()
        s2 = make_store()
        items = [
            make_item(store=s1, variant=v1),
            make_item(store=s1, variant=v2),
            make_item(store=s2, variant=v1),
        ]
        # Control: another product's item must NOT be touched
        other_product = make_product()
        other_variant = make_variant(product=other_product)
        other_item = make_item(store=s1, variant=other_variant)

        prod_svc.set_product_compliance(
            db_session,
            product.id,
            ProductComplianceUpdate(
                compliance_status=ComplianceStatus.banned,
                allowed_for_sale=False,
                reason="test ban",
            ),
            actor=admin,
        )

        for i in items:
            db_session.refresh(i)
            assert i.status == InventoryStatus.quarantined
        db_session.refresh(other_item)
        assert other_item.status == InventoryStatus.available

    def test_cascade_writes_no_inventory_log(
        self,
        db_session: Session,
        make_product,
        make_variant,
        make_item,
        make_user,
    ):
        admin = make_user(UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(variant=variant)

        n_before = len(
            list(
                db_session.scalars(
                    select(InventoryLog).where(
                        InventoryLog.inventory_item_id == item.id
                    )
                ).all()
            )
        )

        prod_svc.set_product_compliance(
            db_session,
            product.id,
            ProductComplianceUpdate(
                compliance_status=ComplianceStatus.banned,
                allowed_for_sale=False,
                reason="cascade-no-log",
            ),
            actor=admin,
        )

        db_session.refresh(item)
        assert item.status == InventoryStatus.quarantined
        n_after = len(
            list(
                db_session.scalars(
                    select(InventoryLog).where(
                        InventoryLog.inventory_item_id == item.id
                    )
                ).all()
            )
        )
        assert n_before == n_after, (
            "Compliance cascade must not write InventoryLog rows; "
            f"{n_before} → {n_after}"
        )

    def test_reverse_transition_does_not_lift_quarantine(
        self,
        db_session: Session,
        make_product,
        make_variant,
        make_item,
        make_user,
    ):
        admin = make_user(UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(variant=variant)

        # Ban
        prod_svc.set_product_compliance(
            db_session,
            product.id,
            ProductComplianceUpdate(
                compliance_status=ComplianceStatus.banned,
                allowed_for_sale=False,
                reason="ban",
            ),
            actor=admin,
        )
        db_session.refresh(item)
        assert item.status == InventoryStatus.quarantined

        # Re-allow
        prod_svc.set_product_compliance(
            db_session,
            product.id,
            ProductComplianceUpdate(
                compliance_status=ComplianceStatus.allowed,
                allowed_for_sale=True,
                reason="cleared",
            ),
            actor=admin,
        )
        db_session.refresh(item)
        # Items must STAY quarantined (rules §6: no auto-lift)
        assert item.status == InventoryStatus.quarantined


# --------------------------------------------------------------------- #
# API — RBAC + tenancy
# --------------------------------------------------------------------- #
#
# These tests use the live FastAPI app via `client`. They share the seed
# strategy of test_products.py: build users/stores/items via fixtures,
# then hit endpoints with appropriate Bearer tokens.


class TestApiReadAccess:
    @pytest.mark.parametrize(
        "role,expected",
        [
            (UserRole.admin, 200),
            (UserRole.owner, 200),
            (UserRole.manager, 200),
            (UserRole.staff, 200),
            (UserRole.driver, 403),
        ],
    )
    def test_list_store_inventory_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        role: UserRole,
        expected: int,
    ):
        store = make_store()
        user = make_user(role, store_id=store.id)
        resp = client.get(
            f"/stores/{store.id}/inventory", headers=_auth(user)
        )
        assert resp.status_code == expected

    def test_list_store_inventory_anon(
        self, client: TestClient, make_store
    ):
        store = make_store()
        resp = client.get(f"/stores/{store.id}/inventory")
        assert resp.status_code == 401


class TestApiManagerTier:
    @pytest.mark.parametrize(
        "role,expected",
        [
            (UserRole.admin, 200),
            (UserRole.owner, 200),
            (UserRole.manager, 200),
            (UserRole.staff, 403),
            (UserRole.driver, 403),
        ],
    )
    def test_receive_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        role: UserRole,
        expected: int,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        user = make_user(role, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/receive",
            headers=_auth(user),
            json={"quantity": 1},
        )
        assert resp.status_code == expected


class TestApiStaffTier:
    @pytest.mark.parametrize(
        "role,expected",
        [
            (UserRole.admin, 200),
            (UserRole.owner, 200),
            (UserRole.manager, 200),
            (UserRole.staff, 200),
            (UserRole.driver, 403),
        ],
    )
    def test_sell_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        role: UserRole,
        expected: int,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        user = make_user(role, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/sell",
            headers=_auth(user),
            json={"quantity": 1},
        )
        assert resp.status_code == expected


class TestApiTenancy:
    def test_cross_store_manager_blocked_from_item(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store_a = make_store(code="store-a")
        store_b = make_store(code="store-b")
        item_in_a = make_item(store=store_a)
        manager_b = make_user(UserRole.manager, store_id=store_b.id)
        resp = client.post(
            f"/inventory/{item_in_a.id}/receive",
            headers=_auth(manager_b),
            json={"quantity": 1},
        )
        assert resp.status_code == 403

    def test_admin_crosses_stores(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store_a = make_store(code="store-a")
        store_b = make_store(code="store-b")
        item_in_a = make_item(store=store_a)
        admin = make_user(UserRole.admin)
        resp = client.get(
            f"/inventory/{item_in_a.id}", headers=_auth(admin)
        )
        assert resp.status_code == 200
        resp = client.get(
            f"/stores/{store_b.id}/inventory", headers=_auth(admin)
        )
        assert resp.status_code == 200


class TestApiErrorMapping:
    def test_oversell_returns_422(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=2)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/sell",
            headers=_auth(staff),
            json={"quantity": 99},
        )
        assert resp.status_code == 422
        assert "available" in resp.json()["detail"].lower()

    def test_missing_item_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            f"/inventory/{uuid.uuid4()}", headers=_auth(admin)
        )
        assert resp.status_code == 404

    def test_duplicate_create_returns_409(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
    ):
        store = make_store()
        variant = make_variant()
        admin = make_user(UserRole.admin)
        # First create
        first = client.post(
            f"/stores/{store.id}/inventory/items",
            headers=_auth(admin),
            json={"variant_id": str(variant.id), "quantity_on_hand": 5},
        )
        assert first.status_code == 201
        # Duplicate
        dup = client.post(
            f"/stores/{store.id}/inventory/items",
            headers=_auth(admin),
            json={"variant_id": str(variant.id), "quantity_on_hand": 0},
        )
        assert dup.status_code == 409
