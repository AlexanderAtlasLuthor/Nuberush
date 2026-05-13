"""Service-layer tests for the admin products list (F2.20.1).

Exercises `app.services.admin_products.list_admin_products` against
the real test DB via the `db_session` fixture from conftest.

Covers (per F2.20.1 requirements):

  1. Admin happy path / envelope.
  2. Non-admin forbidden (every non-admin role).
  3. Pagination: total before pagination, limit/offset.
  4. `q` search across name / brand / category / description.
  5. `compliance_status` filter.
  6. `allowed_for_sale` filter.
  7. `is_active` filter.
  8. `category` filter (case-insensitive, trim).
  9. Deterministic ordering (updated_at DESC, created_at DESC,
     name ASC, id ASC).
  10. Read-only invariants (no row count / field drift across calls).

Style mirrors test_admin_operations_service.py + test_admin_dashboard_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services import admin_products as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(*, is_active: bool = True) -> Store:
        store = Store(
            name=f"APSvc-{uuid.uuid4().hex[:6]}",
            code=f"ap-{uuid.uuid4().hex[:8]}",
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
            full_name=f"APSvc {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            password_hash=hash_password("supersecret123"),
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


def _pin_products_timestamps(
    db_session: Session,
    rows: list[Product],
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> None:
    """Pin `created_at` and/or `updated_at` while temporarily
    disabling the BEFORE UPDATE trigger that would clobber
    `updated_at` with `now()`.

    Used in deterministic-ordering tests where products need
    controlled timestamps.
    """
    db_session.execute(
        text("ALTER TABLE products DISABLE TRIGGER trg_products_set_updated_at")
    )
    try:
        for row in rows:
            if created_at is not None:
                row.created_at = created_at
            if updated_at is not None:
                row.updated_at = updated_at
        db_session.commit()
    finally:
        db_session.execute(
            text("ALTER TABLE products ENABLE TRIGGER trg_products_set_updated_at")
        )
        db_session.commit()
    for row in rows:
        db_session.refresh(row)


# --------------------------------------------------------------------- #
# A. RBAC + envelope
# --------------------------------------------------------------------- #


class TestRBAC:
    def test_admin_happy_path_empty_db(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        response = svc.list_admin_products(db_session, actor=admin)
        assert response.items == []
        assert response.total == 0
        assert response.limit == 50
        assert response.offset == 0

    def test_admin_happy_path_with_rows(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        product = make_product()
        response = svc.list_admin_products(db_session, actor=admin)
        assert response.total == 1
        assert len(response.items) == 1
        assert response.items[0].id == product.id

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
            svc.list_admin_products(db_session, actor=actor)
        assert excinfo.value.status_code == 403


# --------------------------------------------------------------------- #
# B. Pagination
# --------------------------------------------------------------------- #


class TestPagination:
    def test_total_before_pagination(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(5):
            make_product()
        response = svc.list_admin_products(
            db_session, actor=admin, limit=2, offset=0
        )
        assert response.total == 5
        assert len(response.items) == 2

    def test_offset_advances_through_rows(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(5):
            make_product()
        first = svc.list_admin_products(
            db_session, actor=admin, limit=2, offset=0
        )
        second = svc.list_admin_products(
            db_session, actor=admin, limit=2, offset=2
        )
        first_ids = {item.id for item in first.items}
        second_ids = {item.id for item in second.items}
        assert first_ids.isdisjoint(second_ids)
        assert len(first.items) == 2
        assert len(second.items) == 2

    def test_offset_beyond_total_returns_empty(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product()
        response = svc.list_admin_products(
            db_session, actor=admin, limit=10, offset=999
        )
        assert response.total == 1
        assert response.items == []


# --------------------------------------------------------------------- #
# C. `q` filter
# --------------------------------------------------------------------- #


class TestQFilter:
    def test_q_matches_name(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(name="Mango Ice")
        make_product(name="Strawberry Burst")
        response = svc.list_admin_products(
            db_session, actor=admin, q="mango"
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_q_matches_brand(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(name="Whatever", brand="NubeBrand")
        make_product(name="Other", brand="SomethingElse")
        response = svc.list_admin_products(
            db_session, actor=admin, q="nubebrand"
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_q_matches_category(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(category="edibles")
        make_product(category="vape")
        response = svc.list_admin_products(
            db_session, actor=admin, q="edibles"
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_q_matches_description(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(description="contains nicotine salts")
        make_product(description="other description")
        response = svc.list_admin_products(
            db_session, actor=admin, q="nicotine"
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_q_is_case_insensitive(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(name="UpperCASE Name")
        response = svc.list_admin_products(
            db_session, actor=admin, q="uppercase"
        )
        assert response.total == 1
        assert response.items[0].id == target.id

    def test_q_empty_string_returns_all(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(3):
            make_product()
        response = svc.list_admin_products(
            db_session, actor=admin, q=""
        )
        assert response.total == 3

    def test_q_whitespace_only_returns_all(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(3):
            make_product()
        response = svc.list_admin_products(
            db_session, actor=admin, q="   "
        )
        assert response.total == 3


# --------------------------------------------------------------------- #
# D. Compliance status filter
# --------------------------------------------------------------------- #


class TestComplianceStatusFilter:
    def test_filter_allowed_only(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        allowed = make_product(
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
        response = svc.list_admin_products(
            db_session,
            actor=admin,
            compliance_status=ComplianceStatus.allowed,
        )
        assert response.total == 1
        assert response.items[0].id == allowed.id

    def test_filter_restricted_only(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(compliance_status=ComplianceStatus.allowed)
        restricted = make_product(
            compliance_status=ComplianceStatus.restricted
        )
        response = svc.list_admin_products(
            db_session,
            actor=admin,
            compliance_status=ComplianceStatus.restricted,
        )
        assert response.total == 1
        assert response.items[0].id == restricted.id

    def test_filter_banned_only(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(compliance_status=ComplianceStatus.allowed)
        banned = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        response = svc.list_admin_products(
            db_session,
            actor=admin,
            compliance_status=ComplianceStatus.banned,
        )
        assert response.total == 1
        assert response.items[0].id == banned.id


# --------------------------------------------------------------------- #
# E. allowed_for_sale filter
# --------------------------------------------------------------------- #


class TestAllowedForSaleFilter:
    def test_filter_true(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        yes = make_product(allowed_for_sale=True)
        make_product(allowed_for_sale=False)
        response = svc.list_admin_products(
            db_session, actor=admin, allowed_for_sale=True
        )
        assert response.total == 1
        assert response.items[0].id == yes.id

    def test_filter_false(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(allowed_for_sale=True)
        no = make_product(allowed_for_sale=False)
        response = svc.list_admin_products(
            db_session, actor=admin, allowed_for_sale=False
        )
        assert response.total == 1
        assert response.items[0].id == no.id


# --------------------------------------------------------------------- #
# F. is_active filter
# --------------------------------------------------------------------- #


class TestIsActiveFilter:
    def test_filter_true(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        active = make_product(is_active=True)
        make_product(is_active=False)
        response = svc.list_admin_products(
            db_session, actor=admin, is_active=True
        )
        assert response.total == 1
        assert response.items[0].id == active.id

    def test_filter_false(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(is_active=True)
        inactive = make_product(is_active=False)
        response = svc.list_admin_products(
            db_session, actor=admin, is_active=False
        )
        assert response.total == 1
        assert response.items[0].id == inactive.id


# --------------------------------------------------------------------- #
# G. Category filter
# --------------------------------------------------------------------- #


class TestCategoryFilter:
    def test_exact_match(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        vape = make_product(category="vape")
        make_product(category="edibles")
        response = svc.list_admin_products(
            db_session, actor=admin, category="vape"
        )
        assert response.total == 1
        assert response.items[0].id == vape.id

    def test_case_insensitive(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        vape = make_product(category="Vape")
        response = svc.list_admin_products(
            db_session, actor=admin, category="VAPE"
        )
        assert response.total == 1
        assert response.items[0].id == vape.id

    def test_empty_category_treated_as_not_provided(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(category="vape")
        make_product(category="edibles")
        response = svc.list_admin_products(
            db_session, actor=admin, category=""
        )
        assert response.total == 2

    def test_whitespace_category_treated_as_not_provided(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        make_product(category="vape")
        make_product(category="edibles")
        response = svc.list_admin_products(
            db_session, actor=admin, category="   "
        )
        assert response.total == 2


# --------------------------------------------------------------------- #
# H. Deterministic ordering
# --------------------------------------------------------------------- #


class TestDeterministicOrdering:
    def test_updated_at_desc_is_primary_key(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        older = make_product()
        newer = make_product()
        # Pin updated_at to known distinct values.
        _pin_products_timestamps(
            db_session,
            [older],
            updated_at=datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
        )
        _pin_products_timestamps(
            db_session,
            [newer],
            updated_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        )
        response = svc.list_admin_products(db_session, actor=admin)
        assert [item.id for item in response.items] == [
            newer.id,
            older.id,
        ]

    def test_name_then_id_tiebreaker(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        a = make_product(name="Apple")
        b = make_product(name="Banana")
        c = make_product(name="Cherry")
        # Pin all to the same created_at and updated_at so the primary
        # two keys collapse and only (name ASC, id ASC) drives order.
        pinned = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
        _pin_products_timestamps(
            db_session, [a, b, c],
            created_at=pinned, updated_at=pinned,
        )
        response = svc.list_admin_products(db_session, actor=admin)
        returned_names = [item.name for item in response.items]
        assert returned_names == ["Apple", "Banana", "Cherry"]

    def test_repeated_calls_return_same_order(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        for _ in range(6):
            make_product()
        first = svc.list_admin_products(db_session, actor=admin)
        second = svc.list_admin_products(db_session, actor=admin)
        assert [i.id for i in first.items] == [i.id for i in second.items]


# --------------------------------------------------------------------- #
# I. Combined filters
# --------------------------------------------------------------------- #


class TestCombinedFilters:
    def test_q_plus_compliance_status(
        self, db_session: Session, make_admin, make_product
    ):
        admin = make_admin()
        target = make_product(
            name="Mango Vape",
            compliance_status=ComplianceStatus.restricted,
        )
        make_product(
            name="Mango Vape Allowed",
            compliance_status=ComplianceStatus.allowed,
        )
        make_product(
            name="Strawberry Vape",
            compliance_status=ComplianceStatus.restricted,
        )
        response = svc.list_admin_products(
            db_session,
            actor=admin,
            q="mango",
            compliance_status=ComplianceStatus.restricted,
        )
        assert response.total == 1
        assert response.items[0].id == target.id


# --------------------------------------------------------------------- #
# J. Read-only invariants
# --------------------------------------------------------------------- #


class TestReadOnly:
    def test_repeated_calls_create_no_rows_or_field_drift(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        admin = make_admin()
        p1 = make_product(name="Persistent")
        p2 = make_product(name="Stable")

        def _snapshot() -> dict:
            count = db_session.scalar(
                select(func.count()).select_from(Product)
            )
            row1 = db_session.get(Product, p1.id)
            row2 = db_session.get(Product, p2.id)
            return {
                "count": count,
                "p1": (
                    row1.name,
                    row1.brand,
                    row1.category,
                    row1.compliance_status,
                    row1.allowed_for_sale,
                    row1.is_active,
                ),
                "p2": (
                    row2.name,
                    row2.brand,
                    row2.category,
                    row2.compliance_status,
                    row2.allowed_for_sale,
                    row2.is_active,
                ),
            }

        baseline = _snapshot()

        for _ in range(3):
            response = svc.list_admin_products(db_session, actor=admin)
            assert response.total == 2

        assert _snapshot() == baseline
