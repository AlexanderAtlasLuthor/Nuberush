"""Service-layer tests for the unified audit feed (F2.16.2).

Exercises `app.services.audit.list_store_audit` against the real test
DB via the `db_session` fixture from conftest. Covers:

  - RBAC + tenancy (admin / owner / manager / staff / driver matrix,
    cross-store probe collapse, unknown-store, inactive store).
  - Source normalization for `inventory_logs`, `order_audit_logs`,
    and `product_compliance_audit_logs`.
  - Compliance scoping via the
    `ProductComplianceAuditLog -> ProductVariant -> InventoryItem`
    join, including the no-leak case (other store) and dedupe (same
    store, multiple variants/items).
  - Merge / stable sort / post-merge pagination / total accounting.
  - All filters (`source`, `entity_type`, `action`, `actor_id`,
    `date_from`, `date_to`).
  - Pagination bounds (limit min/max, negative offset).

No routes are exercised here — F2.16.3 covers API-level concerns.

Style mirrors tests/test_users_service.py and
tests/test_inventory_services.py: direct DB inserts via existing
models, helper fixtures for stores / users / products / variants /
items / log rows, `pytest.raises(HTTPException)` with status code
asserts on negative paths.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Any
from typing import Callable
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import OperationalAuditLog
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.audit import AuditEntityType
from app.schemas.audit import AuditSource
from app.services import audit as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *, name: str = "Audit-Svc", is_active: bool = True
    ) -> Store:
        store = Store(
            name=name,
            code=f"aud-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _create(
        *,
        role: UserRole,
        store_id: UUID | None = None,
        is_active: bool = True,
    ) -> User:
        user = User(
            full_name=f"User {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            role=role,
            store_id=store_id,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        *,
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
def make_variant(db_session: Session) -> Callable[..., ProductVariant]:
    def _create(*, product: Product) -> ProductVariant:
        variant = ProductVariant(
            product_id=product.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_item(db_session: Session) -> Callable[..., InventoryItem]:
    def _create(
        *,
        store: Store,
        variant: ProductVariant,
        quantity_on_hand: int = 10,
    ) -> InventoryItem:
        item = InventoryItem(
            store_id=store.id,
            variant_id=variant.id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=0,
            reorder_threshold=0,
            status=InventoryStatus.available,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


@pytest.fixture
def make_order(db_session: Session) -> Callable[..., Order]:
    def _create(*, store: Store) -> Order:
        order = Order(
            store_id=store.id,
            idempotency_key=f"idem-{uuid.uuid4().hex[:8]}",
            status=OrderStatus.pending,
            subtotal_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order

    return _create


def _pin_created_at(
    db_session: Session, row: Any, when: datetime
) -> None:
    """Override the server_default `created_at` so sort/pagination
    tests are deterministic. Same idea as `_pin_created_at` in
    test_inventory_services.py but operates on one row at a time."""
    row.created_at = when
    db_session.commit()
    db_session.refresh(row)


@pytest.fixture
def make_inventory_log(
    db_session: Session,
) -> Callable[..., InventoryLog]:
    def _create(
        *,
        item: InventoryItem,
        movement_type: InventoryMovementType = (
            InventoryMovementType.receipt
        ),
        quantity_delta: int = 5,
        quantity_after: int | None = None,
        actor: User | None = None,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> InventoryLog:
        log = InventoryLog(
            inventory_item_id=item.id,
            store_id=item.store_id,
            variant_id=item.variant_id,
            performed_by_user_id=actor.id if actor is not None else None,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            quantity_after=(
                quantity_after
                if quantity_after is not None
                else max(item.quantity_on_hand + quantity_delta, 0)
            ),
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            _pin_created_at(db_session, log, created_at)
        return log

    return _create


@pytest.fixture
def make_order_audit_log(
    db_session: Session,
) -> Callable[..., OrderAuditLog]:
    def _create(
        *,
        order: Order,
        action: str = "status_changed",
        previous_status: OrderStatus | None = OrderStatus.pending,
        new_status: OrderStatus = OrderStatus.accepted,
        actor: User | None = None,
        reason: str | None = None,
        created_at: datetime | None = None,
    ) -> OrderAuditLog:
        log = OrderAuditLog(
            order_id=order.id,
            store_id=order.store_id,
            performed_by_user_id=actor.id if actor is not None else None,
            previous_status=previous_status,
            new_status=new_status,
            action=action,
            reason=reason,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            _pin_created_at(db_session, log, created_at)
        return log

    return _create


@pytest.fixture
def make_compliance_audit_log(
    db_session: Session,
) -> Callable[..., ProductComplianceAuditLog]:
    def _create(
        *,
        product: Product,
        previous_compliance_status: ComplianceStatus = (
            ComplianceStatus.allowed
        ),
        new_compliance_status: ComplianceStatus = (
            ComplianceStatus.restricted
        ),
        previous_allowed_for_sale: bool = True,
        new_allowed_for_sale: bool = False,
        reason: str = "policy update",
        actor: User | None = None,
        created_at: datetime | None = None,
    ) -> ProductComplianceAuditLog:
        log = ProductComplianceAuditLog(
            product_id=product.id,
            previous_compliance_status=previous_compliance_status,
            new_compliance_status=new_compliance_status,
            previous_allowed_for_sale=previous_allowed_for_sale,
            new_allowed_for_sale=new_allowed_for_sale,
            reason=reason,
            changed_by_user_id=actor.id if actor is not None else None,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            _pin_created_at(db_session, log, created_at)
        return log

    return _create


# --------------------------------------------------------------------- #
# RBAC / store access
# --------------------------------------------------------------------- #


class TestRBAC:
    def test_admin_can_list_existing_active_store(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        assert result.items == []
        assert result.total == 0
        assert result.limit == 50
        assert result.offset == 0

    @pytest.mark.parametrize(
        "role", [UserRole.owner, UserRole.manager, UserRole.staff]
    )
    def test_non_admin_can_list_own_store(
        self, db_session, make_store, make_user, role
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=actor
        )
        assert result.total == 0

    def test_driver_forbidden(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        driver = make_user(role=UserRole.driver, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=driver
            )
        assert excinfo.value.status_code == 403

    @pytest.mark.parametrize(
        "role", [UserRole.owner, UserRole.manager, UserRole.staff]
    )
    def test_non_admin_cross_store_forbidden(
        self, db_session, make_store, make_user, role
    ):
        store_a = make_store()
        store_b = make_store()
        actor = make_user(role=role, store_id=store_a.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store_b.id, actor=actor
            )
        assert excinfo.value.status_code == 403

    def test_non_admin_unknown_store_returns_403(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store_id=store.id)
        unknown_store_id = uuid.uuid4()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=unknown_store_id, actor=owner
            )
        # Existence-probe collapse: must look identical to cross-store.
        assert excinfo.value.status_code == 403

    def test_admin_unknown_store_returns_404(
        self, db_session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=uuid.uuid4(), actor=admin
            )
        assert excinfo.value.status_code == 404

    def test_admin_inactive_store_returns_400(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(is_active=False)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=admin
            )
        assert excinfo.value.status_code == 400

    def test_non_admin_own_inactive_store_returns_400(
        self, db_session, make_store, make_user
    ):
        store = make_store(is_active=False)
        owner = make_user(role=UserRole.owner, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=owner
            )
        assert excinfo.value.status_code == 400

    def test_non_admin_without_store_id_returns_403(
        self, db_session, make_store, make_user
    ):
        # A non-admin without store_id is structurally invalid but the
        # guard must still surface it as 403, not 500.
        store = make_store()
        rogue = User(
            full_name="Rogue",
            email=f"rogue-{uuid.uuid4().hex[:8]}@example.com",
            role=UserRole.owner,
            store_id=None,
            is_active=True,
        )
        db_session.add(rogue)
        db_session.commit()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=rogue
            )
        assert excinfo.value.status_code == 403


# --------------------------------------------------------------------- #
# Source normalization
# --------------------------------------------------------------------- #


class TestInventoryNormalization:
    def test_inventory_log_normalized(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        actor = make_user(role=UserRole.manager, store_id=store.id)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        log = make_inventory_log(
            item=item,
            movement_type=InventoryMovementType.receipt,
            quantity_delta=5,
            quantity_after=15,
            actor=actor,
            reason="restock",
            reference_type="purchase_order",
            reference_id=uuid.uuid4(),
        )

        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        assert result.total == 1
        ev = result.items[0]
        assert ev.id == log.id
        assert ev.source == AuditSource.inventory
        assert ev.store_id == store.id
        assert ev.actor_id == actor.id
        assert ev.action == "receipt"
        assert ev.entity_type == AuditEntityType.inventory_item
        assert ev.entity_id == item.id
        assert "receipt" in ev.summary.lower()
        assert ev.metadata["quantity_delta"] == 5
        assert ev.metadata["quantity_after"] == 15
        assert ev.metadata["reason"] == "restock"
        assert ev.metadata["reference_type"] == "purchase_order"
        # UUID-typed metadata values are pre-stringified for JSON safety.
        assert isinstance(ev.metadata["variant_id"], str)
        UUID(ev.metadata["variant_id"])  # parseable
        assert isinstance(ev.metadata["reference_id"], str)


class TestOrderNormalization:
    def test_order_audit_log_normalized(
        self,
        db_session,
        make_store,
        make_user,
        make_order,
        make_order_audit_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        actor = make_user(role=UserRole.staff, store_id=store.id)
        order = make_order(store=store)
        log = make_order_audit_log(
            order=order,
            action="status_changed",
            previous_status=OrderStatus.pending,
            new_status=OrderStatus.accepted,
            actor=actor,
            reason="customer confirmed",
        )

        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        assert result.total == 1
        ev = result.items[0]
        assert ev.id == log.id
        assert ev.source == AuditSource.order
        assert ev.store_id == store.id
        assert ev.actor_id == actor.id
        assert ev.action == "status_changed"
        assert ev.entity_type == AuditEntityType.order
        assert ev.entity_id == order.id
        assert ev.metadata["previous_status"] == "pending"
        assert ev.metadata["new_status"] == "accepted"
        assert ev.metadata["reason"] == "customer confirmed"

    def test_order_audit_log_with_null_previous_status(
        self,
        db_session,
        make_store,
        make_user,
        make_order,
        make_order_audit_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        order = make_order(store=store)
        make_order_audit_log(
            order=order,
            action="order_created",
            previous_status=None,
            new_status=OrderStatus.pending,
        )
        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        assert result.total == 1
        assert result.items[0].metadata["previous_status"] is None
        assert result.items[0].metadata["new_status"] == "pending"


class TestComplianceNormalization:
    def test_compliance_audit_normalized_via_inventory_join(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        make_item(store=store, variant=variant)
        log = make_compliance_audit_log(
            product=product,
            previous_compliance_status=ComplianceStatus.allowed,
            new_compliance_status=ComplianceStatus.banned,
            previous_allowed_for_sale=True,
            new_allowed_for_sale=False,
            reason="regulator notice",
            actor=admin,
        )

        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        assert result.total == 1
        ev = result.items[0]
        assert ev.id == log.id
        assert ev.source == AuditSource.product_compliance
        # Compliance row gets the REQUESTED store_id (the log has no
        # store_id column of its own).
        assert ev.store_id == store.id
        assert ev.actor_id == admin.id
        assert ev.action == "compliance_changed"
        assert ev.entity_type == AuditEntityType.product
        assert ev.entity_id == product.id
        assert ev.metadata["previous_compliance_status"] == "allowed"
        assert ev.metadata["new_compliance_status"] == "banned"
        assert ev.metadata["previous_allowed_for_sale"] is True
        assert ev.metadata["new_allowed_for_sale"] is False
        assert ev.metadata["reason"] == "regulator notice"

    def test_compliance_row_absent_for_store_without_inventory(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        store_a = make_store()
        store_b = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        # Only store_a carries inventory for the product.
        make_item(store=store_a, variant=variant)
        make_compliance_audit_log(product=product, actor=admin)

        feed_b = svc.list_store_audit(
            db_session, store_id=store_b.id, actor=admin
        )
        assert feed_b.total == 0
        assert feed_b.items == []

        feed_a = svc.list_store_audit(
            db_session, store_id=store_a.id, actor=admin
        )
        assert feed_a.total == 1

    def test_compliance_row_not_duplicated_with_multiple_variants_or_items(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant1 = make_variant(product=product)
        variant2 = make_variant(product=product)
        # Two variants of the same product, both stocked in the same
        # store. The compliance row must appear ONCE per store feed.
        make_item(store=store, variant=variant1)
        make_item(store=store, variant=variant2)
        log = make_compliance_audit_log(product=product, actor=admin)

        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        assert result.total == 1
        assert result.items[0].id == log.id


# --------------------------------------------------------------------- #
# Merge / stable sort / pagination
# --------------------------------------------------------------------- #


class TestMergeSortPagination:
    def test_feed_merges_all_three_sources(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
        make_compliance_audit_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)

        make_inventory_log(item=item)
        make_order_audit_log(order=order)
        make_compliance_audit_log(product=product, actor=admin)

        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        sources = {e.source for e in result.items}
        assert sources == {
            AuditSource.inventory,
            AuditSource.order,
            AuditSource.product_compliance,
        }
        assert result.total == 3

    def test_created_at_desc_ordering(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)

        t_old = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        t_mid = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        t_new = datetime(2026, 1, 1, 15, 0, 0, tzinfo=UTC)
        make_inventory_log(item=item, quantity_delta=1, created_at=t_old)
        make_inventory_log(item=item, quantity_delta=2, created_at=t_new)
        make_inventory_log(item=item, quantity_delta=3, created_at=t_mid)

        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        timestamps = [e.created_at for e in result.items]
        assert timestamps == [t_new, t_mid, t_old]

    def test_tie_break_by_source_then_id(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
        make_compliance_audit_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)
        same_t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

        inv = make_inventory_log(item=item, created_at=same_t)
        ordr = make_order_audit_log(order=order, created_at=same_t)
        comp = make_compliance_audit_log(
            product=product, actor=admin, created_at=same_t
        )

        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        # Tie on created_at; expected source order is alphabetical:
        #   inventory, order, product_compliance.
        sources_in_order = [e.source.value for e in result.items]
        assert sources_in_order == [
            "inventory",
            "order",
            "product_compliance",
        ]
        # Spot-check that the IDs picked up match the rows we wrote.
        ids_in_order = [e.id for e in result.items]
        assert ids_in_order == [inv.id, ordr.id, comp.id]

    def test_tie_break_by_id_within_same_source(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        same_t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

        logs = [
            make_inventory_log(item=item, quantity_delta=i + 1, created_at=same_t)
            for i in range(3)
        ]
        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin
        )
        ids_in_order = [e.id for e in result.items]
        expected = sorted([log.id for log in logs], key=lambda u: str(u))
        assert ids_in_order == expected

    def test_limit_offset_applied_after_merge(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        # Five inventory logs, newest first when sorted DESC.
        logs = []
        for i in range(5):
            logs.append(
                make_inventory_log(
                    item=item,
                    quantity_delta=i + 1,
                    created_at=base + timedelta(minutes=i),
                )
            )

        page = svc.list_store_audit(
            db_session,
            store_id=store.id,
            actor=admin,
            limit=2,
            offset=1,
        )
        assert page.total == 5
        assert page.limit == 2
        assert page.offset == 1
        assert len(page.items) == 2
        # Sorted DESC by created_at: logs[4] then logs[3] then logs[2].
        # Page offset=1 skips logs[4]; returns logs[3], logs[2].
        assert page.items[0].id == logs[3].id
        assert page.items[1].id == logs[2].id

    def test_offset_beyond_total_returns_empty_items(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        make_inventory_log(item=item)
        make_inventory_log(item=item)

        page = svc.list_store_audit(
            db_session,
            store_id=store.id,
            actor=admin,
            limit=50,
            offset=10,
        )
        assert page.total == 2
        assert page.items == []
        assert page.offset == 10


# --------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------- #


class TestFilters:
    @pytest.fixture
    def seeded(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
        make_compliance_audit_log,
    ):
        """One row per source, with distinct actors and timestamps so
        every filter has a positive and negative target to hit."""
        store = make_store()
        admin = make_user(role=UserRole.admin)
        inv_actor = make_user(role=UserRole.manager, store_id=store.id)
        ord_actor = make_user(role=UserRole.staff, store_id=store.id)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)

        t_inv = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)
        t_ord = datetime(2026, 1, 2, 8, 0, 0, tzinfo=UTC)
        t_comp = datetime(2026, 1, 3, 8, 0, 0, tzinfo=UTC)

        inv = make_inventory_log(
            item=item,
            movement_type=InventoryMovementType.adjustment,
            quantity_delta=-2,
            actor=inv_actor,
            reason="loss",
            created_at=t_inv,
        )
        ordr = make_order_audit_log(
            order=order,
            action="order_canceled",
            previous_status=OrderStatus.pending,
            new_status=OrderStatus.canceled,
            actor=ord_actor,
            reason="customer",
            created_at=t_ord,
        )
        comp = make_compliance_audit_log(
            product=product, actor=admin, created_at=t_comp
        )

        return {
            "store": store,
            "admin": admin,
            "inv_actor": inv_actor,
            "ord_actor": ord_actor,
            "product": product,
            "inv": inv,
            "ordr": ordr,
            "comp": comp,
            "t_inv": t_inv,
            "t_ord": t_ord,
            "t_comp": t_comp,
        }

    @pytest.mark.parametrize(
        "source,expected_id_key",
        [
            (AuditSource.inventory, "inv"),
            (AuditSource.order, "ordr"),
            (AuditSource.product_compliance, "comp"),
        ],
    )
    def test_source_filter_isolates_each_source(
        self, db_session, seeded, source, expected_id_key
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            source=source,
        )
        assert result.total == 1
        assert result.items[0].source == source
        assert result.items[0].id == seeded[expected_id_key].id

    @pytest.mark.parametrize(
        "entity_type,expected_id_key",
        [
            (AuditEntityType.inventory_item, "inv"),
            (AuditEntityType.order, "ordr"),
            (AuditEntityType.product, "comp"),
        ],
    )
    def test_entity_type_filter_isolates_each_source(
        self, db_session, seeded, entity_type, expected_id_key
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            entity_type=entity_type,
        )
        assert result.total == 1
        assert result.items[0].entity_type == entity_type
        assert result.items[0].id == seeded[expected_id_key].id

    def test_action_filter_matches_inventory_movement_type(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            action="adjustment",
        )
        assert result.total == 1
        assert result.items[0].id == seeded["inv"].id

    def test_action_filter_matches_order_action(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            action="order_canceled",
        )
        assert result.total == 1
        assert result.items[0].id == seeded["ordr"].id

    def test_action_filter_compliance_matches_compliance_changed(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            action="compliance_changed",
        )
        # Only compliance has action="compliance_changed".
        assert result.total == 1
        assert result.items[0].id == seeded["comp"].id

    def test_action_filter_nonmatching_returns_empty(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            action="nonexistent_action",
        )
        assert result.total == 0
        assert result.items == []

    def test_actor_id_filter_matches_inventory_actor(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            actor_id=seeded["inv_actor"].id,
        )
        assert result.total == 1
        assert result.items[0].id == seeded["inv"].id

    def test_actor_id_filter_matches_order_actor(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            actor_id=seeded["ord_actor"].id,
        )
        assert result.total == 1
        assert result.items[0].id == seeded["ordr"].id

    def test_actor_id_filter_matches_compliance_actor(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            actor_id=seeded["admin"].id,
        )
        assert result.total == 1
        assert result.items[0].id == seeded["comp"].id

    def test_actor_id_filter_unknown_user_returns_empty(
        self, db_session, seeded
    ):
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            actor_id=uuid.uuid4(),
        )
        assert result.total == 0

    def test_date_from_filters_older_rows_out(
        self, db_session, seeded
    ):
        # Cut between t_inv (Jan 1) and t_ord (Jan 2).
        cutoff = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            date_from=cutoff,
        )
        ids = {e.id for e in result.items}
        assert seeded["inv"].id not in ids
        assert seeded["ordr"].id in ids
        assert seeded["comp"].id in ids
        assert result.total == 2

    def test_date_to_filters_newer_rows_out(
        self, db_session, seeded
    ):
        cutoff = datetime(2026, 1, 2, 23, 59, 59, tzinfo=UTC)
        result = svc.list_store_audit(
            db_session,
            store_id=seeded["store"].id,
            actor=seeded["admin"],
            date_to=cutoff,
        )
        ids = {e.id for e in result.items}
        assert seeded["comp"].id not in ids
        assert seeded["inv"].id in ids
        assert seeded["ordr"].id in ids
        assert result.total == 2


# --------------------------------------------------------------------- #
# Pagination bounds (service-level guards)
# --------------------------------------------------------------------- #


class TestPaginationGuards:
    def test_limit_1_accepted(self, db_session, make_store, make_user):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin, limit=1
        )
        assert result.limit == 1

    def test_limit_200_accepted(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin, limit=200
        )
        assert result.limit == 200

    def test_limit_0_rejected(self, db_session, make_store, make_user):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=admin, limit=0
            )
        assert excinfo.value.status_code == 422

    def test_limit_negative_rejected(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=admin, limit=-1
            )
        assert excinfo.value.status_code == 422

    def test_limit_over_200_rejected(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=admin, limit=201
            )
        assert excinfo.value.status_code == 422

    def test_offset_negative_rejected(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_store_audit(
                db_session, store_id=store.id, actor=admin, offset=-1
            )
        assert excinfo.value.status_code == 422

    def test_offset_zero_accepted(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        result = svc.list_store_audit(
            db_session, store_id=store.id, actor=admin, offset=0
        )
        assert result.offset == 0


# --------------------------------------------------------------------- #
# Cross-store leak guard (inventory + order sources)
# --------------------------------------------------------------------- #


class TestCrossStoreIsolation:
    def test_inventory_row_in_other_store_not_returned(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        store_a = make_store()
        store_b = make_store()
        admin = make_user(role=UserRole.admin)
        product = make_product()
        variant_a = make_variant(product=product)
        variant_b = make_variant(product=product)
        item_a = make_item(store=store_a, variant=variant_a)
        item_b = make_item(store=store_b, variant=variant_b)
        make_inventory_log(item=item_a)
        make_inventory_log(item=item_b)

        feed_a = svc.list_store_audit(
            db_session, store_id=store_a.id, actor=admin
        )
        assert feed_a.total == 1
        assert feed_a.items[0].store_id == store_a.id

    def test_order_row_in_other_store_not_returned(
        self,
        db_session,
        make_store,
        make_user,
        make_order,
        make_order_audit_log,
    ):
        store_a = make_store()
        store_b = make_store()
        admin = make_user(role=UserRole.admin)
        order_a = make_order(store=store_a)
        order_b = make_order(store=store_b)
        make_order_audit_log(order=order_a)
        make_order_audit_log(order=order_b)

        feed_a = svc.list_store_audit(
            db_session, store_id=store_a.id, actor=admin
        )
        assert feed_a.total == 1
        assert feed_a.items[0].store_id == store_a.id


# --------------------------------------------------------------------- #
# F2.17.4 — list_admin_audit
# --------------------------------------------------------------------- #


_NON_ADMIN_AUDIT_ROLES = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


class TestAdminAuditRBAC:
    def test_admin_can_call_without_store_id(
        self, db_session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        result = svc.list_admin_audit(db_session, actor=admin)
        assert result.limit == 50
        assert result.offset == 0
        # Envelope shape comes from AuditEventListResponse.
        assert hasattr(result, "items")
        assert hasattr(result, "total")

    @pytest.mark.parametrize("role", _NON_ADMIN_AUDIT_ROLES)
    def test_non_admin_forbidden(
        self, db_session, make_store, make_user, role
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_audit(db_session, actor=actor)
        assert excinfo.value.status_code == 403


class TestAdminAuditGlobalCoverage:
    def test_global_feed_includes_inventory(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        log = make_inventory_log(item=item)

        result = svc.list_admin_audit(db_session, actor=admin)

        inv_events = [
            e for e in result.items if e.source == AuditSource.inventory
        ]
        assert any(e.id == log.id for e in inv_events)

    def test_global_feed_includes_order(
        self,
        db_session,
        make_store,
        make_user,
        make_order,
        make_order_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        order = make_order(store=store)
        log = make_order_audit_log(order=order)

        result = svc.list_admin_audit(db_session, actor=admin)

        order_events = [
            e for e in result.items if e.source == AuditSource.order
        ]
        assert any(e.id == log.id for e in order_events)

    def test_global_feed_includes_compliance(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        make_item(store=store, variant=variant)
        log = make_compliance_audit_log(product=product)

        result = svc.list_admin_audit(db_session, actor=admin)

        compliance_events = [
            e
            for e in result.items
            if e.source == AuditSource.product_compliance
        ]
        assert any(e.id == log.id for e in compliance_events)

    def test_global_feed_includes_events_from_multiple_stores(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item_a = make_item(store=store_a, variant=variant)
        item_b = make_item(store=store_b, variant=variant)
        log_a = make_inventory_log(item=item_a)
        log_b = make_inventory_log(item=item_b)

        result = svc.list_admin_audit(db_session, actor=admin)

        store_ids = {
            e.store_id
            for e in result.items
            if e.id in {log_a.id, log_b.id}
        }
        assert store_ids == {store_a.id, store_b.id}


class TestAdminAuditEnvelopeAndPagination:
    def test_envelope_shape(self, db_session, make_user):
        admin = make_user(role=UserRole.admin)
        result = svc.list_admin_audit(db_session, actor=admin)
        assert result.limit == 50
        assert result.offset == 0
        assert isinstance(result.items, list)
        assert isinstance(result.total, int)

    def test_total_is_pre_pagination(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        for _ in range(5):
            make_inventory_log(item=item)

        result = svc.list_admin_audit(
            db_session, actor=admin, limit=2, source=AuditSource.inventory
        )
        assert result.total == 5
        assert len(result.items) == 2

    def test_pagination_limit_offset(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        for _ in range(5):
            make_inventory_log(item=item)

        page = svc.list_admin_audit(
            db_session,
            actor=admin,
            limit=2,
            offset=2,
            source=AuditSource.inventory,
        )
        assert page.limit == 2
        assert page.offset == 2
        assert len(page.items) == 2

    def test_limit_one_works(self, db_session, make_user):
        admin = make_user(role=UserRole.admin)
        result = svc.list_admin_audit(db_session, actor=admin, limit=1)
        assert result.limit == 1

    def test_limit_two_hundred_works(self, db_session, make_user):
        admin = make_user(role=UserRole.admin)
        result = svc.list_admin_audit(db_session, actor=admin, limit=200)
        assert result.limit == 200

    def test_limit_zero_rejected(self, db_session, make_user):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_audit(db_session, actor=admin, limit=0)
        assert excinfo.value.status_code == 422

    def test_limit_above_max_rejected(self, db_session, make_user):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_audit(db_session, actor=admin, limit=201)
        assert excinfo.value.status_code == 422

    def test_negative_offset_rejected(self, db_session, make_user):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_audit(db_session, actor=admin, offset=-1)
        assert excinfo.value.status_code == 422


class TestAdminAuditStoreFilter:
    def test_store_id_filter_scopes_feed(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item_a = make_item(store=store_a, variant=variant)
        item_b = make_item(store=store_b, variant=variant)
        make_inventory_log(item=item_a)
        make_inventory_log(item=item_b)

        result = svc.list_admin_audit(
            db_session, actor=admin, store_id=store_a.id
        )
        for event in result.items:
            assert event.store_id == store_a.id

    def test_unknown_store_id_returns_404(
        self, db_session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_audit(
                db_session, actor=admin, store_id=uuid.uuid4()
            )
        assert excinfo.value.status_code == 404

    def test_store_id_filter_works_for_inventory(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item_a = make_item(store=store_a, variant=variant)
        item_b = make_item(store=store_b, variant=variant)
        log_a = make_inventory_log(item=item_a)
        log_b = make_inventory_log(item=item_b)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            store_id=store_a.id,
            source=AuditSource.inventory,
        )
        ids = {e.id for e in result.items}
        assert log_a.id in ids
        assert log_b.id not in ids

    def test_store_id_filter_works_for_order(
        self,
        db_session,
        make_store,
        make_user,
        make_order,
        make_order_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        order_a = make_order(store=store_a)
        order_b = make_order(store=store_b)
        log_a = make_order_audit_log(order=order_a)
        log_b = make_order_audit_log(order=order_b)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            store_id=store_a.id,
            source=AuditSource.order,
        )
        ids = {e.id for e in result.items}
        assert log_a.id in ids
        assert log_b.id not in ids

    def test_store_id_filter_works_for_compliance(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product_a = make_product()
        product_b = make_product()
        variant_a = make_variant(product=product_a)
        variant_b = make_variant(product=product_b)
        make_item(store=store_a, variant=variant_a)
        make_item(store=store_b, variant=variant_b)
        log_a = make_compliance_audit_log(product=product_a)
        log_b = make_compliance_audit_log(product=product_b)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            store_id=store_a.id,
            source=AuditSource.product_compliance,
        )
        ids = {e.id for e in result.items}
        assert log_a.id in ids
        assert log_b.id not in ids


class TestAdminAuditSourceFilters:
    def test_source_inventory_only(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)
        make_inventory_log(item=item)
        make_order_audit_log(order=order)
        make_compliance_audit_log(product=product)

        result = svc.list_admin_audit(
            db_session, actor=admin, source=AuditSource.inventory
        )
        for event in result.items:
            assert event.source == AuditSource.inventory

    def test_source_order_only(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)
        make_inventory_log(item=item)
        make_order_audit_log(order=order)
        make_compliance_audit_log(product=product)

        result = svc.list_admin_audit(
            db_session, actor=admin, source=AuditSource.order
        )
        for event in result.items:
            assert event.source == AuditSource.order

    def test_source_compliance_only(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)
        make_inventory_log(item=item)
        make_order_audit_log(order=order)
        make_compliance_audit_log(product=product)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            source=AuditSource.product_compliance,
        )
        for event in result.items:
            assert event.source == AuditSource.product_compliance


class TestAdminAuditNonSourceFilters:
    def test_entity_type_filter_narrows(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)
        make_inventory_log(item=item)
        make_order_audit_log(order=order)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            entity_type=AuditEntityType.order,
        )
        for event in result.items:
            assert event.entity_type == AuditEntityType.order

    def test_action_filter_narrows(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        receipt = make_inventory_log(
            item=item, movement_type=InventoryMovementType.receipt
        )
        adjustment = make_inventory_log(
            item=item, movement_type=InventoryMovementType.adjustment
        )

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            action=InventoryMovementType.receipt.value,
        )
        ids = {e.id for e in result.items}
        assert receipt.id in ids
        assert adjustment.id not in ids

    def test_actor_id_filter_narrows(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        actor_one = make_user(role=UserRole.manager, store_id=store.id)
        actor_two = make_user(role=UserRole.manager, store_id=store.id)
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        log_one = make_inventory_log(item=item, actor=actor_one)
        log_two = make_inventory_log(item=item, actor=actor_two)

        result = svc.list_admin_audit(
            db_session, actor=admin, actor_id=actor_one.id
        )
        ids = {e.id for e in result.items}
        assert log_one.id in ids
        assert log_two.id not in ids


class TestAdminAuditDateFilters:
    def test_date_from_excludes_older(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)

        old = make_inventory_log(
            item=item,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        recent = make_inventory_log(
            item=item,
            created_at=datetime(2026, 5, 1, tzinfo=UTC),
        )

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            date_from=datetime(2026, 3, 1, tzinfo=UTC),
        )
        ids = {e.id for e in result.items}
        assert recent.id in ids
        assert old.id not in ids

    def test_date_to_excludes_newer(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)

        old = make_inventory_log(
            item=item,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        recent = make_inventory_log(
            item=item,
            created_at=datetime(2026, 5, 1, tzinfo=UTC),
        )

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            date_to=datetime(2026, 3, 1, tzinfo=UTC),
        )
        ids = {e.id for e in result.items}
        assert old.id in ids
        assert recent.id not in ids

    def test_date_window(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)

        before = make_inventory_log(
            item=item,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        inside = make_inventory_log(
            item=item,
            created_at=datetime(2026, 3, 15, tzinfo=UTC),
        )
        after = make_inventory_log(
            item=item,
            created_at=datetime(2026, 6, 1, tzinfo=UTC),
        )

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            date_from=datetime(2026, 2, 1, tzinfo=UTC),
            date_to=datetime(2026, 4, 1, tzinfo=UTC),
        )
        ids = {e.id for e in result.items}
        assert inside.id in ids
        assert before.id not in ids
        assert after.id not in ids


class TestAdminAuditSorting:
    def test_created_at_desc(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)

        older = make_inventory_log(
            item=item,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        middle = make_inventory_log(
            item=item,
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        newest = make_inventory_log(
            item=item,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
        )

        result = svc.list_admin_audit(
            db_session, actor=admin, source=AuditSource.inventory
        )
        ids_in_order = [e.id for e in result.items]
        assert ids_in_order.index(newest.id) < ids_in_order.index(middle.id)
        assert ids_in_order.index(middle.id) < ids_in_order.index(older.id)

    def test_source_asc_tie_breaker(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
        make_order_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store)

        same_ts = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
        inv_log = make_inventory_log(item=item, created_at=same_ts)
        ord_log = make_order_audit_log(order=order, created_at=same_ts)

        result = svc.list_admin_audit(db_session, actor=admin)
        # AuditSource.inventory.value == "inventory" < "order"
        # ASC by source → inventory event must come before order event
        # within the same created_at bucket.
        ids_in_order = [e.id for e in result.items]
        assert ids_in_order.index(inv_log.id) < ids_in_order.index(
            ord_log.id
        )

    def test_id_asc_tie_breaker(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)

        same_ts = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
        a = make_inventory_log(item=item, created_at=same_ts)
        b = make_inventory_log(item=item, created_at=same_ts)

        result = svc.list_admin_audit(
            db_session, actor=admin, source=AuditSource.inventory
        )
        ids_in_order = [e.id for e in result.items]
        # Same source + same created_at → id ASC tie-breaker.
        smaller_id = min(a.id, b.id, key=str)
        assert ids_in_order[0] == smaller_id


class TestAdminAuditComplianceFanOut:
    def test_compliance_fans_out_per_affected_store(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product = make_product()
        variant = make_variant(product=product)
        make_item(store=store_a, variant=variant)
        make_item(store=store_b, variant=variant)
        log = make_compliance_audit_log(product=product)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            source=AuditSource.product_compliance,
        )

        compliance_events = [e for e in result.items if e.id == log.id]
        store_ids = {e.store_id for e in compliance_events}
        assert store_ids == {store_a.id, store_b.id}

    def test_compliance_does_not_duplicate_same_log_store_pair(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        # Two variants, two items in the same store — the join would
        # otherwise enumerate 2 rows for one (log, store) pair.
        variant_one = make_variant(product=product)
        variant_two = make_variant(product=product)
        make_item(store=store, variant=variant_one)
        make_item(store=store, variant=variant_two)
        log = make_compliance_audit_log(product=product)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            source=AuditSource.product_compliance,
        )
        matching = [e for e in result.items if e.id == log.id]
        assert len(matching) == 1
        assert matching[0].store_id == store.id

    def test_compliance_with_store_filter_returns_only_affected_store(
        self,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
        make_compliance_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        product = make_product()
        variant = make_variant(product=product)
        make_item(store=store_a, variant=variant)
        make_item(store=store_b, variant=variant)
        log = make_compliance_audit_log(product=product)

        result = svc.list_admin_audit(
            db_session,
            actor=admin,
            source=AuditSource.product_compliance,
            store_id=store_a.id,
        )
        compliance_events = [e for e in result.items if e.id == log.id]
        assert len(compliance_events) == 1
        assert compliance_events[0].store_id == store_a.id


# ===================================================================== #
# F2.26.2.B — Source binding generalization (`_SOURCE_ENTITY_BINDING`
# now maps a source to a SET of entity types; `_source_applies` honors it
# by membership). The operational normalizer is NOT wired yet, so a
# `source=operational` service query yields an empty page (200, not 500).
# ===================================================================== #


class TestSourceBindingGeneralization:
    def test_binding_shape_is_sets(self):
        # Every binding value is now a set/frozenset of entity types.
        for source, entities in svc._SOURCE_ENTITY_BINDING.items():
            assert isinstance(entities, (set, frozenset)), source
            assert all(
                isinstance(e, AuditEntityType) for e in entities
            ), source

    def test_existing_sources_keep_singleton_entities(self):
        assert svc._SOURCE_ENTITY_BINDING[AuditSource.inventory] == frozenset(
            {AuditEntityType.inventory_item}
        )
        assert svc._SOURCE_ENTITY_BINDING[AuditSource.order] == frozenset(
            {AuditEntityType.order}
        )
        assert svc._SOURCE_ENTITY_BINDING[
            AuditSource.product_compliance
        ] == frozenset({AuditEntityType.product})

    def test_operational_binds_user_and_store(self):
        assert svc._SOURCE_ENTITY_BINDING[AuditSource.operational] == frozenset(
            {AuditEntityType.user, AuditEntityType.store}
        )

    # ---- A. existing singleton behavior via _source_applies ---------- #

    def test_inventory_applies_to_inventory_item(self):
        assert svc._source_applies(
            AuditSource.inventory,
            source=AuditSource.inventory,
            entity_type=AuditEntityType.inventory_item,
        )

    def test_inventory_does_not_apply_to_user(self):
        assert not svc._source_applies(
            AuditSource.inventory,
            source=AuditSource.inventory,
            entity_type=AuditEntityType.user,
        )

    def test_order_applies_to_order(self):
        assert svc._source_applies(
            AuditSource.order,
            source=AuditSource.order,
            entity_type=AuditEntityType.order,
        )

    def test_product_compliance_applies_to_product(self):
        assert svc._source_applies(
            AuditSource.product_compliance,
            source=AuditSource.product_compliance,
            entity_type=AuditEntityType.product,
        )

    def test_source_mismatch_short_circuits(self):
        # candidate inventory, but caller asked for operational → skip.
        assert not svc._source_applies(
            AuditSource.inventory,
            source=AuditSource.operational,
            entity_type=None,
        )

    # ---- B. operational binding behavior ----------------------------- #

    def test_operational_applies_with_no_entity_filter(self):
        assert svc._source_applies(
            AuditSource.operational, source=AuditSource.operational,
            entity_type=None,
        )

    def test_operational_applies_to_user(self):
        assert svc._source_applies(
            AuditSource.operational, source=AuditSource.operational,
            entity_type=AuditEntityType.user,
        )

    def test_operational_applies_to_store(self):
        assert svc._source_applies(
            AuditSource.operational, source=AuditSource.operational,
            entity_type=AuditEntityType.store,
        )

    def test_operational_does_not_apply_to_order(self):
        assert not svc._source_applies(
            AuditSource.operational, source=AuditSource.operational,
            entity_type=AuditEntityType.order,
        )

    def test_operational_does_not_apply_to_product(self):
        assert not svc._source_applies(
            AuditSource.operational, source=AuditSource.operational,
            entity_type=AuditEntityType.product,
        )

    def test_no_filters_admits_every_source(self):
        # source=None, entity_type=None → every source applies conceptually.
        for candidate in svc._SOURCE_ENTITY_BINDING:
            assert svc._source_applies(
                candidate, source=None, entity_type=None
            )


class TestOperationalFeedEmptyWhenNoRows:
    """With NO operational rows present, a `source=operational` query (or
    a `user`-entity query) must return an empty page — 200, never 500 —
    on both the store and admin feeds. (Pre-F2.26.2.D this also proved the
    source was unwired; post-wiring it proves the empty-DB invariant.)"""

    def test_store_feed_operational_source_returns_empty(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        result = svc.list_store_audit(
            db_session,
            store_id=store.id,
            actor=actor,
            source=AuditSource.operational,
        )
        assert result.items == []
        assert result.total == 0

    def test_admin_feed_operational_source_returns_empty(
        self, db_session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        result = svc.list_admin_audit(
            db_session, actor=admin, source=AuditSource.operational
        )
        assert result.items == []
        assert result.total == 0

    def test_store_feed_entity_user_returns_empty(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        result = svc.list_store_audit(
            db_session,
            store_id=store.id,
            actor=actor,
            entity_type=AuditEntityType.user,
        )
        assert result.items == []
        assert result.total == 0


# ===================================================================== #
# F2.26.2.C — Operational audit normalizer (`_query_operational_events`).
# Tested directly (the normalizer is NOT yet wired into list_*_audit).
# Operational rows are created directly via the committed model for
# focused coverage.
# ===================================================================== #


def _make_op_log(
    db: Session,
    *,
    target_type: str,
    action: str,
    store_id=None,
    actor_user_id=None,
    before=None,
    after=None,
    event_metadata=None,
    created_at=None,
) -> OperationalAuditLog:
    log = OperationalAuditLog(
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=uuid.uuid4(),
        action=action,
        store_id=store_id,
        before=before,
        after=after,
        event_metadata=event_metadata,
    )
    if created_at is not None:
        log.created_at = created_at
    db.add(log)
    db.flush()
    return log


def _op(db, **kw):
    return svc._query_operational_events(
        db,
        store_id=kw.get("store_id"),
        action=kw.get("action"),
        actor_id=kw.get("actor_id"),
        date_from=kw.get("date_from"),
        date_to=kw.get("date_to"),
        entity_type=kw.get("entity_type"),
    )


class TestOperationalNormalizer:
    # A. user event
    def test_normalizes_user_event(self, db_session, make_store, make_user):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        row = _make_op_log(
            db_session,
            target_type="user",
            action="user_updated",
            store_id=store.id,
            actor_user_id=actor.id,
            before={"full_name": "Old"},
            after={"full_name": "New"},
            event_metadata={"source": "users.update_user"},
        )
        events = _op(db_session, store_id=store.id)
        assert len(events) == 1
        ev = events[0]
        assert ev.id == row.id
        assert ev.source == AuditSource.operational
        assert ev.entity_type == AuditEntityType.user
        assert ev.entity_id == row.target_id
        assert ev.actor_id == actor.id
        assert ev.action == "user_updated"
        assert ev.summary == "User updated"
        assert ev.metadata["before"] == {"full_name": "Old"}
        assert ev.metadata["after"] == {"full_name": "New"}
        assert ev.metadata["source"] == "users.update_user"

    # B. store event
    def test_normalizes_store_event(self, db_session, make_store, make_user):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        _make_op_log(
            db_session,
            target_type="store",
            action="store_updated",
            store_id=store.id,
            actor_user_id=actor.id,
        )
        events = _op(db_session, store_id=store.id)
        assert len(events) == 1
        assert events[0].entity_type == AuditEntityType.store
        assert events[0].summary == "Store updated"

    # C. concrete store_id excludes NULL global and other store
    def test_store_filter_excludes_null_and_other_store(
        self, db_session, make_store, make_user
    ):
        store_a = make_store()
        store_b = make_store()
        actor = make_user(role=UserRole.admin)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store_a.id, actor_user_id=actor.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store_b.id, actor_user_id=actor.id)
        _make_op_log(db_session, target_type="user", action="user_role_changed",
                     store_id=None, actor_user_id=actor.id)  # global
        events = _op(db_session, store_id=store_a.id)
        assert len(events) == 1
        assert all(ev.store_id == store_a.id for ev in events)

    # D. admin/global no store filter -> global NULL + store-scoped
    def test_global_includes_null_and_scoped(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=actor.id)
        _make_op_log(db_session, target_type="user", action="user_role_changed",
                     store_id=None, actor_user_id=actor.id)
        events = _op(db_session, store_id=None)
        assert len(events) == 2
        scopes = {ev.store_id for ev in events}
        assert store.id in scopes and None in scopes

    # E. filter by action
    def test_filter_by_action(self, db_session, make_store, make_user):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=actor.id)
        _make_op_log(db_session, target_type="store", action="store_deactivated",
                     store_id=store.id, actor_user_id=actor.id)
        events = _op(db_session, store_id=store.id, action="store_deactivated")
        assert len(events) == 1
        assert events[0].action == "store_deactivated"

    # F. filter by actor_id
    def test_filter_by_actor_id(self, db_session, make_store, make_user):
        store = make_store()
        a1 = make_user(role=UserRole.admin)
        a2 = make_user(role=UserRole.owner, store_id=store.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=a1.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=a2.id)
        events = _op(db_session, store_id=store.id, actor_id=a1.id)
        assert len(events) == 1
        assert events[0].actor_id == a1.id

    # G. filter by date_from / date_to
    def test_filter_by_date_range(self, db_session, make_store, make_user):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        old = datetime(2020, 1, 1, tzinfo=UTC)
        new = datetime(2026, 1, 1, tzinfo=UTC)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=actor.id, created_at=old)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=actor.id, created_at=new)
        cutoff = datetime(2023, 1, 1, tzinfo=UTC)
        after_events = _op(db_session, store_id=store.id, date_from=cutoff)
        before_events = _op(db_session, store_id=store.id, date_to=cutoff)
        assert len(after_events) == 1 and after_events[0].created_at == new
        assert len(before_events) == 1 and before_events[0].created_at == old

    # H. entity_type row-level filter
    def test_entity_type_user_and_store_rowlevel(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        _make_op_log(db_session, target_type="user", action="user_updated",
                     store_id=store.id, actor_user_id=actor.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=actor.id)
        users = _op(db_session, store_id=store.id, entity_type=AuditEntityType.user)
        stores = _op(db_session, store_id=store.id, entity_type=AuditEntityType.store)
        assert len(users) == 1 and users[0].entity_type == AuditEntityType.user
        assert len(stores) == 1 and stores[0].entity_type == AuditEntityType.store

    # I. entity_type incompatible with operational -> []
    def test_entity_type_incompatible_returns_empty(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        _make_op_log(db_session, target_type="user", action="user_updated",
                     store_id=store.id, actor_user_id=actor.id)
        assert _op(db_session, store_id=store.id,
                   entity_type=AuditEntityType.order) == []

    # J. unknown target_type row is skipped, not raised
    def test_unknown_target_type_is_skipped(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        # A valid row plus a malformed one (bypasses the writer's taxonomy).
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=store.id, actor_user_id=actor.id)
        _make_op_log(db_session, target_type="spaceship", action="store_updated",
                     store_id=store.id, actor_user_id=actor.id)
        events = _op(db_session, store_id=store.id)
        assert len(events) == 1
        assert events[0].entity_type == AuditEntityType.store

    # K. metadata safety: before/after present (even None), no mutation
    def test_metadata_includes_before_after_safely(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        meta = {"source": "users.deactivate_user"}
        _make_op_log(db_session, target_type="user", action="user_deactivated",
                     store_id=store.id, actor_user_id=actor.id,
                     before={"is_active": True}, after={"is_active": False},
                     event_metadata=meta)
        events = _op(db_session, store_id=store.id)
        md = events[0].metadata
        assert md["before"] == {"is_active": True}
        assert md["after"] == {"is_active": False}
        assert md["source"] == "users.deactivate_user"
        # original event_metadata dict not mutated with before/after keys
        assert "before" not in meta and "after" not in meta

    def test_metadata_includes_before_after_when_none(
        self, db_session, make_store, make_user
    ):
        store = make_store()
        actor = make_user(role=UserRole.admin)
        _make_op_log(db_session, target_type="store", action="store_created",
                     store_id=store.id, actor_user_id=actor.id,
                     before=None, after={"name": "X"})
        ev = _op(db_session, store_id=store.id)[0]
        assert ev.metadata["before"] is None
        assert ev.metadata["after"] == {"name": "X"}


# ===================================================================== #
# F2.26.2.D — Operational events WIRED into the unified feed
# (`list_store_audit` / `list_admin_audit`). Visibility, filters,
# mixed-source sort/pagination, and metadata are exercised end-to-end
# through the public service entry points.
# ===================================================================== #


class TestOperationalFeedWiring:
    # A. admin global sees operational global (NULL) + all store-scoped
    def test_admin_global_includes_null_and_all_stores(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        sb = make_store()
        _make_op_log(db_session, target_type="user",
                     action="user_role_changed", store_id=None,
                     actor_user_id=admin.id)  # global
        _make_op_log(db_session, target_type="store",
                     action="store_updated", store_id=sa.id,
                     actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store",
                     action="store_updated", store_id=sb.id,
                     actor_user_id=admin.id)
        res = svc.list_admin_audit(db_session, actor=admin)
        ops = [e for e in res.items if e.source == AuditSource.operational]
        scopes = {e.store_id for e in ops}
        assert len(ops) == 3
        assert None in scopes and sa.id in scopes and sb.id in scopes

    # B. admin store-filtered excludes global NULL and other store
    def test_admin_store_filter_excludes_global_and_other(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        sb = make_store()
        _make_op_log(db_session, target_type="user",
                     action="user_role_changed", store_id=None,
                     actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store",
                     action="store_updated", store_id=sa.id,
                     actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store",
                     action="store_updated", store_id=sb.id,
                     actor_user_id=admin.id)
        res = svc.list_admin_audit(db_session, actor=admin, store_id=sa.id)
        ops = [e for e in res.items if e.source == AuditSource.operational]
        assert len(ops) == 1 and ops[0].store_id == sa.id

    # C. store feed scoped: only this store, no global, no other store
    def test_store_feed_scoped(
        self, db_session, make_store, make_user
    ):
        sa = make_store()
        sb = make_store()
        actor = make_user(role=UserRole.owner, store_id=sa.id)
        admin = make_user(role=UserRole.admin)
        _make_op_log(db_session, target_type="user",
                     action="user_role_changed", store_id=None,
                     actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store",
                     action="store_updated", store_id=sa.id,
                     actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store",
                     action="store_updated", store_id=sb.id,
                     actor_user_id=admin.id)
        res = svc.list_store_audit(db_session, store_id=sa.id, actor=actor)
        ops = [e for e in res.items if e.source == AuditSource.operational]
        assert len(ops) == 1 and ops[0].store_id == sa.id

    # D. source=operational returns only operational rows (a non-op row
    # in the same store must be excluded by the filter).
    def test_source_operational_only(
        self, db_session, make_store, make_user, make_order,
        make_order_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        make_order_audit_log(order=make_order(store=sa))  # non-operational
        # Sanity: with no source filter, both sources are present.
        unfiltered = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin
        )
        assert {e.source for e in unfiltered.items} == {
            AuditSource.operational, AuditSource.order
        }
        res = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin,
            source=AuditSource.operational,
        )
        assert res.items, "expected at least one operational event"
        assert all(e.source == AuditSource.operational for e in res.items)

    # E / F. entity filters
    def test_entity_user_returns_only_user_ops(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        _make_op_log(db_session, target_type="user", action="user_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        res = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin,
            entity_type=AuditEntityType.user,
        )
        assert res.items
        assert all(e.entity_type == AuditEntityType.user for e in res.items)

    def test_entity_store_returns_only_store_ops(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        _make_op_log(db_session, target_type="user", action="user_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        res = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin,
            entity_type=AuditEntityType.store,
        )
        assert res.items
        assert all(e.entity_type == AuditEntityType.store for e in res.items)

    # G. combined source/entity filters
    def test_combined_source_entity_filters(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        _make_op_log(db_session, target_type="user", action="user_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id)

        def feed(**kw):
            return svc.list_store_audit(
                db_session, store_id=sa.id, actor=admin, **kw
            ).items

        op_user = feed(source=AuditSource.operational,
                       entity_type=AuditEntityType.user)
        op_store = feed(source=AuditSource.operational,
                        entity_type=AuditEntityType.store)
        op_order = feed(source=AuditSource.operational,
                        entity_type=AuditEntityType.order)
        inv_user = feed(source=AuditSource.inventory,
                        entity_type=AuditEntityType.user)
        assert all(e.entity_type == AuditEntityType.user for e in op_user) and op_user
        assert all(e.entity_type == AuditEntityType.store for e in op_store) and op_store
        assert op_order == []
        assert inv_user == []

    # H. action filter
    def test_action_filter(self, db_session, make_store, make_user):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        _make_op_log(db_session, target_type="user", action="user_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        _make_op_log(db_session, target_type="user", action="user_deactivated",
                     store_id=sa.id, actor_user_id=admin.id)
        res = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin, action="user_updated"
        )
        ops = [e for e in res.items if e.source == AuditSource.operational]
        assert len(ops) == 1 and ops[0].action == "user_updated"

    # I. actor filter
    def test_actor_filter(self, db_session, make_store, make_user):
        admin = make_user(role=UserRole.admin)
        owner = make_user(role=UserRole.owner, store_id=None)
        sa = make_store()
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=owner.id)
        res = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin, actor_id=owner.id
        )
        ops = [e for e in res.items if e.source == AuditSource.operational]
        assert len(ops) == 1 and ops[0].actor_id == owner.id

    # J. date filters
    def test_date_filters(self, db_session, make_store, make_user):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        old = datetime(2020, 1, 1, tzinfo=UTC)
        new = datetime(2026, 1, 1, tzinfo=UTC)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id, created_at=old)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id, created_at=new)
        cutoff = datetime(2023, 1, 1, tzinfo=UTC)
        recent = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin, date_from=cutoff
        ).items
        older = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin, date_to=cutoff
        ).items
        assert len(recent) == 1 and recent[0].created_at == new
        assert len(older) == 1 and older[0].created_at == old

    # K. mixed-source sort + pagination determinism + pre-pagination total
    def test_mixed_source_sort_and_pagination(
        self, db_session, make_store, make_user, make_order,
        make_order_audit_log,
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        same = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        # An order-source row and an operational row at the SAME instant.
        # Within a created_at tie the feed sorts by source.value ASC, and
        # "operational" < "order" (the 2nd char 'p' < 'r'), so operational
        # comes first — deterministically.
        make_order_audit_log(order=make_order(store=sa), created_at=same)
        _make_op_log(db_session, target_type="store", action="store_updated",
                     store_id=sa.id, actor_user_id=admin.id, created_at=same)
        res = svc.list_store_audit(db_session, store_id=sa.id, actor=admin)
        assert res.total == 2  # pre-pagination
        assert [e.source.value for e in res.items] == ["operational", "order"]
        # pagination: limit 1 → first (operational); offset 1 → second (order)
        page1 = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin, limit=1, offset=0
        )
        page2 = svc.list_store_audit(
            db_session, store_id=sa.id, actor=admin, limit=1, offset=1
        )
        assert page1.total == 2 and page2.total == 2
        assert page1.items[0].source.value == "operational"
        assert page2.items[0].source.value == "order"

    # M. metadata mapping in the feed
    def test_feed_operational_metadata_includes_before_after(
        self, db_session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        sa = make_store()
        _make_op_log(
            db_session, target_type="user", action="user_deactivated",
            store_id=sa.id, actor_user_id=admin.id,
            before={"is_active": True}, after={"is_active": False},
            event_metadata={"source": "users.deactivate_user"},
        )
        res = svc.list_store_audit(db_session, store_id=sa.id, actor=admin)
        ev = [e for e in res.items if e.source == AuditSource.operational][0]
        assert ev.metadata["before"] == {"is_active": True}
        assert ev.metadata["after"] == {"is_active": False}
        assert ev.metadata["source"] == "users.deactivate_user"
        assert ev.summary == "User deactivated"
