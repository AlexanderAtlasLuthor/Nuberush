"""Service-layer tests for the admin dashboard aggregator (F2.19.1).

Exercises `app.services.admin_dashboard.get_admin_dashboard_summary`
against the real test DB via the `db_session` fixture from conftest.

Covers (per F2.19.1 requirements):

  1. Admin happy path.
  2. Non-admin forbidden (every non-admin role).
  3. Store counts: total / active / inactive.
  4. User counts: total / active.
  5. Low stock count: `quantity_on_hand - quantity_reserved
     <= reorder_threshold`.
  6. Orders by_status: every status counted correctly.
  7. Open orders: includes pending, accepted, preparing, ready,
     out_for_delivery; excludes delivered, canceled, returned.
  8. Recent orders: created_at DESC, bounded to 5.
  9. Compliance blocked count: allowed_for_sale=False AND/OR banned
     status (constraint-respecting); restricted also counted per the
     locked contract.
  10. Recent audit: ordered DESC by created_at, bounded to 5.
  11. Read-only: no mutations introduced by the service.

Style mirrors test_inventory_services.py / test_audit_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductApprovalStatus
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services import admin_dashboard as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *, name: str = "Dash-Svc", is_active: bool = True
    ) -> Store:
        store = Store(
            name=name,
            code=f"ds-{uuid.uuid4().hex[:8]}",
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
        store_id: uuid.UUID | None = None,
        is_active: bool = True,
    ) -> User:
        # admin users carry no store; non-admin must have a store_id.
        sid = None if role == UserRole.admin else store_id
        user = User(
            full_name=f"DashSvc {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            role=role,
            store_id=sid,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def make_admin(make_user) -> Callable[..., User]:
    def _create() -> User:
        return make_user(role=UserRole.admin)

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        *,
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
        is_active: bool = True,
        approval_status: ProductApprovalStatus = ProductApprovalStatus.approved,
    ) -> Product:
        rejection_reason: str | None = (
            "Fixture-rejected"
            if approval_status == ProductApprovalStatus.rejected
            else None
        )
        product = Product(
            name=f"P-{uuid.uuid4().hex[:6]}",
            category="vape",
            compliance_status=compliance_status,
            allowed_for_sale=allowed_for_sale,
            is_active=is_active,
            approval_status=approval_status,
            rejection_reason=rejection_reason,
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
    def _create(*, product: Product | None = None) -> ProductVariant:
        prod = product if product is not None else make_product()
        variant = ProductVariant(
            product_id=prod.id,
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
def make_item(
    db_session: Session, make_store, make_variant
) -> Callable[..., InventoryItem]:
    def _create(
        *,
        store: Store | None = None,
        variant: ProductVariant | None = None,
        quantity_on_hand: int = 10,
        quantity_reserved: int = 0,
        reorder_threshold: int = 0,
        item_status: InventoryStatus = InventoryStatus.available,
    ) -> InventoryItem:
        s = store if store is not None else make_store()
        v = variant if variant is not None else make_variant()
        item = InventoryItem(
            store_id=s.id,
            variant_id=v.id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            reorder_threshold=reorder_threshold,
            status=item_status,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


@pytest.fixture
def make_order(db_session: Session) -> Callable[..., Order]:
    def _create(
        *,
        store: Store,
        order_status: OrderStatus = OrderStatus.pending,
        created_at: datetime | None = None,
    ) -> Order:
        order = Order(
            store_id=store.id,
            idempotency_key=f"idem-{uuid.uuid4().hex[:8]}",
            status=order_status,
            subtotal_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        if created_at is not None:
            order.created_at = created_at
            db_session.commit()
            db_session.refresh(order)
        return order

    return _create


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
        quantity_after: int = 15,
        actor: User | None = None,
        created_at: datetime | None = None,
    ) -> InventoryLog:
        log = InventoryLog(
            inventory_item_id=item.id,
            store_id=item.store_id,
            variant_id=item.variant_id,
            performed_by_user_id=actor.id if actor is not None else None,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            quantity_after=quantity_after,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            log.created_at = created_at
            db_session.commit()
            db_session.refresh(log)
        return log

    return _create


# --------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------- #


class TestRBAC:
    def test_admin_happy_path_empty_db(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.stores.total == 0
        assert summary.users.total == 1  # the admin we just created
        assert summary.users.active == 1
        assert summary.inventory.low_stock_count == 0
        assert summary.orders.open_count == 0
        # Histogram densified: every OrderStatus key present, all zero.
        assert set(summary.orders.by_status.keys()) == set(OrderStatus)
        assert all(v == 0 for v in summary.orders.by_status.values())
        assert summary.orders.recent == []
        assert summary.compliance.blocked_count == 0
        assert summary.products.pending_approvals_count == 0
        assert summary.recent_audit == []

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_forbidden(
        self,
        db_session: Session,
        make_store,
        make_user,
        role: UserRole,
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_admin_dashboard_summary(db_session, actor=actor)
        assert excinfo.value.status_code == 403


# --------------------------------------------------------------------- #
# Store counts
# --------------------------------------------------------------------- #


class TestStoreCounts:
    def test_total_active_inactive(
        self, db_session: Session, make_admin, make_store
    ):
        admin = make_admin()
        # 3 active, 2 inactive
        for _ in range(3):
            make_store(is_active=True)
        for _ in range(2):
            make_store(is_active=False)

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.stores.total == 5
        assert summary.stores.active == 3
        assert summary.stores.inactive == 2


# --------------------------------------------------------------------- #
# User counts
# --------------------------------------------------------------------- #


class TestUserCounts:
    def test_total_and_active(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_user,
    ):
        admin = make_admin()  # 1 active user (the admin)
        store = make_store()
        # 2 more active users
        make_user(role=UserRole.owner, store_id=store.id, is_active=True)
        make_user(role=UserRole.staff, store_id=store.id, is_active=True)
        # 1 inactive user
        make_user(
            role=UserRole.manager, store_id=store.id, is_active=False
        )

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.users.total == 4
        assert summary.users.active == 3


# --------------------------------------------------------------------- #
# Inventory low stock
# --------------------------------------------------------------------- #


class TestInventoryLowStock:
    def test_low_stock_predicate(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        store = make_store()

        # Available = qoh - qreserved. Low-stock when <= reorder_threshold.
        # Low-stock case 1: qoh=2, qreserved=0, threshold=5 → avail=2 <= 5.
        make_item(
            store=store,
            quantity_on_hand=2,
            quantity_reserved=0,
            reorder_threshold=5,
        )
        # Low-stock case 2: qoh=0, qreserved=0, threshold=0 → avail=0 <= 0.
        make_item(
            store=store,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )
        # Low-stock case 3: qoh=10, qreserved=8, threshold=3 → avail=2 <= 3.
        make_item(
            store=store,
            quantity_on_hand=10,
            quantity_reserved=8,
            reorder_threshold=3,
        )
        # Not low-stock: qoh=10, qreserved=0, threshold=3 → avail=10 > 3.
        make_item(
            store=store,
            quantity_on_hand=10,
            quantity_reserved=0,
            reorder_threshold=3,
        )

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.inventory.low_stock_count == 3


# --------------------------------------------------------------------- #
# Orders by status / open count
# --------------------------------------------------------------------- #


class TestOrdersByStatus:
    def test_histogram_densified(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        # 2 pending, 1 accepted, 1 delivered, 1 canceled
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.accepted)
        make_order(store=store, order_status=OrderStatus.delivered)
        make_order(store=store, order_status=OrderStatus.canceled)

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        by_status = summary.orders.by_status
        # Every status key present.
        assert set(by_status.keys()) == set(OrderStatus)
        assert by_status[OrderStatus.pending] == 2
        assert by_status[OrderStatus.accepted] == 1
        assert by_status[OrderStatus.preparing] == 0
        assert by_status[OrderStatus.ready] == 0
        assert by_status[OrderStatus.out_for_delivery] == 0
        assert by_status[OrderStatus.delivered] == 1
        assert by_status[OrderStatus.canceled] == 1
        assert by_status[OrderStatus.returned] == 0


class TestOpenOrders:
    def test_open_count_covers_all_open_statuses(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        # 1 per open status (5 total).
        for open_s in (
            OrderStatus.pending,
            OrderStatus.accepted,
            OrderStatus.preparing,
            OrderStatus.ready,
            OrderStatus.out_for_delivery,
        ):
            make_order(store=store, order_status=open_s)
        # 1 per terminal status — must NOT be counted as open.
        for closed_s in (
            OrderStatus.delivered,
            OrderStatus.canceled,
            OrderStatus.returned,
        ):
            make_order(store=store, order_status=closed_s)

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.orders.open_count == 5

    def test_open_count_excludes_closed_only_db(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        make_order(store=store, order_status=OrderStatus.delivered)
        make_order(store=store, order_status=OrderStatus.canceled)
        make_order(store=store, order_status=OrderStatus.returned)

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.orders.open_count == 0


# --------------------------------------------------------------------- #
# Recent orders
# --------------------------------------------------------------------- #


class TestRecentOrders:
    def test_recent_orders_desc_and_bounded_to_5(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        # Create 8 orders with strictly increasing created_at.
        created_orders: list[Order] = []
        for index in range(8):
            order = make_order(
                store=store,
                order_status=OrderStatus.pending,
                created_at=base + timedelta(minutes=index),
            )
            created_orders.append(order)

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        # Bounded to 5.
        assert len(summary.orders.recent) == 5
        # DESC by created_at → newest 5 (indices 7..3).
        expected_ids = [o.id for o in reversed(created_orders[-5:])]
        returned_ids = [o.id for o in summary.orders.recent]
        assert returned_ids == expected_ids
        # Sanity: created_at strictly decreasing in the response.
        timestamps = [o.created_at for o in summary.orders.recent]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_recent_orders_empty_when_no_orders(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.orders.recent == []


# --------------------------------------------------------------------- #
# Compliance blocked count
# --------------------------------------------------------------------- #


class TestComplianceBlockedCount:
    def test_allowed_for_sale_false_is_counted(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        admin = make_admin()
        # 1 product blocked via allowed_for_sale=False (status allowed).
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )
        # 1 product not blocked.
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.compliance.blocked_count == 1

    def test_banned_status_is_counted(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        admin = make_admin()
        # banned implies allowed_for_sale=False by DB CHECK constraint.
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.compliance.blocked_count == 1

    def test_restricted_with_allowed_true_still_counted(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        """The locked contract counts restricted as a blocking status
        even when allowed_for_sale is still True (e.g. policy ramp).
        """
        admin = make_admin()
        make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.compliance.blocked_count == 1

    def test_no_blockers(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.compliance.blocked_count == 0


# --------------------------------------------------------------------- #
# Products: pending approvals count
# --------------------------------------------------------------------- #


class TestProductsPendingApprovalsCount:
    def test_counts_only_pending_rows(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(approval_status=ProductApprovalStatus.pending)
        make_product(approval_status=ProductApprovalStatus.pending)
        make_product(approval_status=ProductApprovalStatus.approved)
        make_product(approval_status=ProductApprovalStatus.rejected)

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.products.pending_approvals_count == 2

    def test_zero_when_no_pending_rows_exist(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        # Only approved + rejected exist — neither is "work to do".
        make_product(approval_status=ProductApprovalStatus.approved)
        make_product(approval_status=ProductApprovalStatus.rejected)

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.products.pending_approvals_count == 0

    def test_independent_from_compliance_state(
        self, db_session: Session, make_admin, make_product
    ):
        """Pending count ignores compliance fields by design.

        A store-proposed product always lands `compliance_status=allowed`
        and `allowed_for_sale=true` (service-forced), but the predicate
        must not depend on those — only `approval_status`.
        """
        admin = make_admin()
        make_product(
            approval_status=ProductApprovalStatus.pending,
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        # A non-pending product with the same compliance state should
        # NOT be counted.
        make_product(
            approval_status=ProductApprovalStatus.approved,
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.products.pending_approvals_count == 1


# --------------------------------------------------------------------- #
# Recent audit
# --------------------------------------------------------------------- #


class TestRecentAudit:
    def test_recent_audit_desc_and_bounded_to_5(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_admin()
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        logs = [
            make_inventory_log(
                item=item,
                actor=admin,
                created_at=base + timedelta(minutes=index),
            )
            for index in range(8)
        ]

        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert len(summary.recent_audit) == 5
        returned_ids = [event.id for event in summary.recent_audit]
        expected_ids = [log.id for log in reversed(logs[-5:])]
        assert returned_ids == expected_ids

    def test_recent_audit_empty_when_no_logs(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        summary = svc.get_admin_dashboard_summary(db_session, actor=admin)
        assert summary.recent_audit == []


# --------------------------------------------------------------------- #
# Read-only invariants
# --------------------------------------------------------------------- #


class TestReadOnly:
    def test_service_does_not_create_or_alter_rows(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
        make_variant,
        make_item,
        make_order,
        make_inventory_log,
    ):
        admin = make_admin()
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        order = make_order(store=store, order_status=OrderStatus.pending)
        make_inventory_log(item=item, actor=admin)

        def _snapshot() -> dict[str, int]:
            return {
                "stores": db_session.scalar(
                    select(func.count()).select_from(Store)
                ),
                "users": db_session.scalar(
                    select(func.count()).select_from(User)
                ),
                "items": db_session.scalar(
                    select(func.count()).select_from(InventoryItem)
                ),
                "orders": db_session.scalar(
                    select(func.count()).select_from(Order)
                ),
                "products": db_session.scalar(
                    select(func.count()).select_from(Product)
                ),
                "logs": db_session.scalar(
                    select(func.count()).select_from(InventoryLog)
                ),
                "order_audit": db_session.scalar(
                    select(func.count()).select_from(OrderAuditLog)
                ),
            }

        baseline = _snapshot()

        # Call the service repeatedly — it must be idempotent.
        for _ in range(3):
            svc.get_admin_dashboard_summary(db_session, actor=admin)

        # Counts must be unchanged afterwards.
        assert _snapshot() == baseline

        # Order row content unchanged (status / created_at unaffected).
        db_session.refresh(order)
        assert order.status == OrderStatus.pending
