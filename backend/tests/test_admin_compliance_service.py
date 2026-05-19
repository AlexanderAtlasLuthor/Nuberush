"""Service-layer tests for admin compliance oversight (F2.20.2).

Exercises:

  - `app.services.admin_compliance.get_admin_compliance_summary`
  - `app.services.admin_compliance.list_admin_compliance_products`
  - `app.services.compliance_predicates.product_compliance_blocker_predicate`

against the real test DB via the `db_session` fixture from conftest.

Covers (per F2.20.2 requirements):

  1. RBAC: admin happy path / non-admin forbidden for both
     summary and queue.
  2. Summary product counts (eight categories).
  3. Shared blocker-predicate consistency: the count from
     `_compute_product_counts` matches a direct query using the
     shared predicate, and matches the default queue total.
  4. Bounded, deterministic recent-reviews tail.
  5. Default queue behavior (blocker predicate union).
  6. Queue filters (q / compliance_status / allowed_for_sale /
     is_active / combined).
  7. Pagination: total before pagination, limit/offset.
  8. Deterministic ordering.
  9. Read-only invariants.

Style mirrors test_admin_products_service.py + test_admin_dashboard_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services import admin_compliance as svc
from app.services.compliance_predicates import (
    product_compliance_blocker_predicate,
)


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(*, is_active: bool = True) -> Store:
        store = Store(
            name=f"CmpSvc-{uuid.uuid4().hex[:6]}",
            code=f"cs-{uuid.uuid4().hex[:8]}",
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
        sid = None if role == UserRole.admin else store_id
        user = User(
            full_name=f"CmpSvc {role.value}",
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
        name: str | None = None,
        brand: str | None = None,
        category: str = "vape",
        description: str | None = None,
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
        is_active: bool = True,
    ) -> Product:
        product = Product(
            name=name or f"P-{uuid.uuid4().hex[:6]}",
            brand=brand,
            category=category,
            description=description,
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
def make_audit(db_session: Session) -> Callable[..., ProductComplianceAuditLog]:
    def _create(
        *,
        product: Product,
        previous_compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        new_compliance_status: ComplianceStatus = ComplianceStatus.restricted,
        previous_allowed_for_sale: bool = True,
        new_allowed_for_sale: bool = True,
        reason: str = "routine review",
        changed_by_user: User | None = None,
        created_at: datetime | None = None,
    ) -> ProductComplianceAuditLog:
        row = ProductComplianceAuditLog(
            product_id=product.id,
            previous_compliance_status=previous_compliance_status,
            new_compliance_status=new_compliance_status,
            previous_allowed_for_sale=previous_allowed_for_sale,
            new_allowed_for_sale=new_allowed_for_sale,
            reason=reason,
            changed_by_user_id=(
                changed_by_user.id if changed_by_user is not None else None
            ),
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        if created_at is not None:
            # `product_compliance_audit_logs` has no `BEFORE UPDATE`
            # trigger (append-only table), so direct assignment + commit
            # sticks.
            row.created_at = created_at
            db_session.commit()
            db_session.refresh(row)
        return row

    return _create


# --------------------------------------------------------------------- #
# A. RBAC
# --------------------------------------------------------------------- #


class TestSummaryRBAC:
    def test_admin_happy_path_empty_db(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        response = svc.get_admin_compliance_summary(
            db_session, actor=admin
        )
        assert response.products.total == 0
        assert response.products.allowed == 0
        assert response.products.blocked == 0
        assert response.reviews.recent_count == 0
        assert response.reviews.recent == []
        assert response.queue.total == 0

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
            svc.get_admin_compliance_summary(db_session, actor=actor)
        assert excinfo.value.status_code == 403


class TestQueueRBAC:
    def test_admin_happy_path_empty_db(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.items == []
        assert response.total == 0
        assert response.limit == 50
        assert response.offset == 0

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
            svc.list_admin_compliance_products(
                db_session, actor=actor
            )
        assert excinfo.value.status_code == 403


# --------------------------------------------------------------------- #
# B. Summary counts
# --------------------------------------------------------------------- #


class TestSummaryCounts:
    def test_all_eight_counts_reflect_seeded_state(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        # 1 allowed + allowed_for_sale + active
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
            is_active=True,
        )
        # 1 restricted + allowed_for_sale=true + active (still a blocker)
        make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
            is_active=True,
        )
        # 1 banned + allowed_for_sale=false (CHECK constraint) + active
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
            is_active=True,
        )
        # 1 allowed but allowed_for_sale=false (still a blocker)
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
            is_active=True,
        )
        # 1 allowed + allowed_for_sale=true but inactive
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
            is_active=False,
        )

        response = svc.get_admin_compliance_summary(
            db_session, actor=admin
        )
        counts = response.products

        assert counts.total == 5
        assert counts.allowed == 3        # 1 allowed-allowed, 1 allowed-blocked, 1 allowed-inactive
        assert counts.restricted == 1
        assert counts.banned == 1
        # Blocker predicate: restricted (1) + banned (1) +
        # allowed-with-allowed_for_sale=false (1) = 3.
        assert counts.blocked == 3
        # allowed_for_sale=true: allowed-allowed-active +
        # restricted-allowed_for_sale-true + allowed-inactive = 3
        assert counts.allowed_for_sale == 3
        # allowed_for_sale=false: banned + allowed-blocked = 2
        assert counts.not_allowed_for_sale == 2
        # inactive: just the one with is_active=False.
        assert counts.inactive == 1


# --------------------------------------------------------------------- #
# C. Shared blocker predicate consistency
# --------------------------------------------------------------------- #


class TestBlockerPredicateConsistency:
    def test_blocked_count_matches_direct_predicate_query(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        # Mix of blockers and non-blockers.
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )

        summary = svc.get_admin_compliance_summary(
            db_session, actor=admin
        )
        direct = db_session.scalar(
            select(func.count())
            .select_from(Product)
            .where(product_compliance_blocker_predicate())
        )
        assert summary.products.blocked == direct
        assert summary.queue.total == direct

    def test_blocker_predicate_includes_allowed_for_sale_false(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_blocker_predicate_includes_restricted(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_blocker_predicate_includes_banned(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_blocker_predicate_excludes_allowed_plus_allowed_for_sale(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 0
        assert response.items == []


# --------------------------------------------------------------------- #
# D. Review tail
# --------------------------------------------------------------------- #


class TestReviewTail:
    def test_recent_is_bounded_to_ten(
        self,
        db_session: Session,
        make_admin,
        make_product,
        make_audit,
    ):
        admin = make_admin()
        product = make_product()
        for _ in range(15):
            make_audit(product=product)
        response = svc.get_admin_compliance_summary(
            db_session, actor=admin
        )
        assert len(response.reviews.recent) == 10
        assert response.reviews.recent_count == 10

    def test_recent_ordered_by_created_at_desc(
        self,
        db_session: Session,
        make_admin,
        make_product,
        make_audit,
    ):
        admin = make_admin()
        product = make_product()
        base = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        oldest = make_audit(
            product=product, created_at=base - timedelta(hours=2)
        )
        middle = make_audit(
            product=product, created_at=base - timedelta(hours=1)
        )
        newest = make_audit(
            product=product, created_at=base,
        )

        response = svc.get_admin_compliance_summary(
            db_session, actor=admin
        )
        returned_ids = [r.id for r in response.reviews.recent]
        assert returned_ids == [newest.id, middle.id, oldest.id]

    def test_recent_count_equals_returned_size(
        self,
        db_session: Session,
        make_admin,
        make_product,
        make_audit,
    ):
        admin = make_admin()
        product = make_product()
        for _ in range(3):
            make_audit(product=product)
        response = svc.get_admin_compliance_summary(
            db_session, actor=admin
        )
        assert response.reviews.recent_count == 3
        assert len(response.reviews.recent) == 3


# --------------------------------------------------------------------- #
# E. Queue counts
# --------------------------------------------------------------------- #


class TestQueueCounts:
    def test_queue_total_matches_blocker_predicate_union(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )

        response = svc.get_admin_compliance_summary(
            db_session, actor=admin
        )
        # 3 blockers (banned + restricted + allowed-with-afs=false).
        assert response.queue.total == 3
        assert response.queue.banned == 1
        assert response.queue.restricted == 1
        # not_allowed_for_sale: banned + allowed-with-afs=false = 2
        assert response.queue.not_allowed_for_sale == 2


# --------------------------------------------------------------------- #
# F. Default queue behavior
# --------------------------------------------------------------------- #


class TestDefaultQueueBehavior:
    def test_default_includes_restricted(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        restricted = make_product(
            compliance_status=ComplianceStatus.restricted
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 1
        assert response.items[0].id == restricted.id

    def test_default_includes_banned(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        banned = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 1
        assert response.items[0].id == banned.id

    def test_default_includes_allowed_for_sale_false(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_default_excludes_allowed_plus_allowed_for_sale(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert response.total == 0


# --------------------------------------------------------------------- #
# G. Queue filters
# --------------------------------------------------------------------- #


class TestQueueFilters:
    def test_q_filter(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(
            name="MangoBan",
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        make_product(
            name="StrawBan",
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin, q="mango"
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_explicit_compliance_status_filter_overrides_default_queue(
        self, db_session: Session, make_admin, make_product
    ):
        """When a caller passes `compliance_status=allowed`, the
        default blocker predicate is NOT applied (F2.20.2 contract),
        so allowed products become visible through this endpoint.
        """
        admin = make_admin()
        allowed = make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        make_product(
            compliance_status=ComplianceStatus.restricted,
        )
        response = svc.list_admin_compliance_products(
            db_session,
            actor=admin,
            compliance_status=ComplianceStatus.allowed,
        )
        assert response.total == 1
        assert response.items[0].id == allowed.id

    def test_explicit_compliance_status_restricted(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        restricted = make_product(
            compliance_status=ComplianceStatus.restricted
        )
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        response = svc.list_admin_compliance_products(
            db_session,
            actor=admin,
            compliance_status=ComplianceStatus.restricted,
        )
        assert response.total == 1
        assert response.items[0].id == restricted.id

    def test_explicit_allowed_for_sale_true_overrides_default_queue(
        self, db_session: Session, make_admin, make_product
    ):
        """`allowed_for_sale=true` disables the default blocker
        predicate so the caller can intentionally inspect rows
        currently allowed for sale.
        """
        admin = make_admin()
        yes = make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin, allowed_for_sale=True
        )
        assert response.total == 1
        assert response.items[0].id == yes.id

    def test_explicit_allowed_for_sale_false(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        no1 = make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )
        no2 = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin, allowed_for_sale=False
        )
        assert response.total == 2
        returned_ids = {item.id for item in response.items}
        assert returned_ids == {no1.id, no2.id}

    def test_is_active_filter_combines_with_default_queue(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        # Two blockers: one active, one inactive.
        inactive_blocker = make_product(
            compliance_status=ComplianceStatus.restricted,
            is_active=False,
        )
        make_product(
            compliance_status=ComplianceStatus.restricted,
            is_active=True,
        )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin, is_active=False
        )
        assert response.total == 1
        assert response.items[0].id == inactive_blocker.id

    def test_combined_q_plus_compliance_status(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(
            name="Mango",
            compliance_status=ComplianceStatus.restricted,
        )
        make_product(
            name="Mango2",
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        make_product(
            name="Strawberry",
            compliance_status=ComplianceStatus.restricted,
        )
        response = svc.list_admin_compliance_products(
            db_session,
            actor=admin,
            q="mango",
            compliance_status=ComplianceStatus.restricted,
        )
        assert response.total == 1
        assert response.items[0].id == target.id


# --------------------------------------------------------------------- #
# H. Pagination + ordering
# --------------------------------------------------------------------- #


class TestQueuePagination:
    def test_total_before_pagination(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(5):
            make_product(
                compliance_status=ComplianceStatus.restricted
            )
        response = svc.list_admin_compliance_products(
            db_session, actor=admin, limit=2, offset=0
        )
        assert response.total == 5
        assert len(response.items) == 2

    def test_offset_advances(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(5):
            make_product(
                compliance_status=ComplianceStatus.restricted
            )
        first = svc.list_admin_compliance_products(
            db_session, actor=admin, limit=2, offset=0
        )
        second = svc.list_admin_compliance_products(
            db_session, actor=admin, limit=2, offset=2
        )
        first_ids = {item.id for item in first.items}
        second_ids = {item.id for item in second.items}
        assert first_ids.isdisjoint(second_ids)

    def test_repeated_calls_return_same_order(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(6):
            make_product(
                compliance_status=ComplianceStatus.restricted
            )
        first = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        second = svc.list_admin_compliance_products(
            db_session, actor=admin
        )
        assert [i.id for i in first.items] == [
            i.id for i in second.items
        ]


# --------------------------------------------------------------------- #
# I. Read-only invariants
# --------------------------------------------------------------------- #


class TestReadOnly:
    def test_repeated_calls_do_not_mutate_state(
        self,
        db_session: Session,
        make_admin,
        make_product,
        make_audit,
    ):
        admin = make_admin()
        p_blocker = make_product(
            compliance_status=ComplianceStatus.restricted
        )
        p_allowed = make_product(
            compliance_status=ComplianceStatus.allowed,
        )
        make_audit(product=p_blocker)

        def _snapshot() -> dict:
            return {
                "products": db_session.scalar(
                    select(func.count()).select_from(Product)
                ),
                "audits": db_session.scalar(
                    select(func.count()).select_from(
                        ProductComplianceAuditLog
                    )
                ),
                "p_blocker_status": db_session.get(
                    Product, p_blocker.id
                ).compliance_status,
                "p_allowed_status": db_session.get(
                    Product, p_allowed.id
                ).compliance_status,
            }

        baseline = _snapshot()

        for _ in range(3):
            svc.get_admin_compliance_summary(db_session, actor=admin)
            svc.list_admin_compliance_products(
                db_session, actor=admin
            )

        assert _snapshot() == baseline
