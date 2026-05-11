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

from app.core.security import hash_password
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
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
            password_hash=hash_password("irrelevant-pw-1234"),
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
            password_hash=hash_password("x" * 12),
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
