"""Tests for the staging seed tool (F2.27.2).

Exercises `scripts.seed_sample_data.run_seed` — the testable core of the
seed CLI — fully offline against the transactional test database. No real
Supabase project, no service-role key, no remote storage: the seed creates
only `public`-schema rows and (for product images) metadata-only rows.

Coverage:
  A. dry-run writes nothing
  B. a real run creates the base demo fixtures
  C. a second run is idempotent (stable counts)
  D. production-like targets are rejected
  E. product image metadata is idempotent
  F. regulatory fixtures are idempotent
  G. no real Supabase env is required
"""

import os

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import InventoryItem
from app.db.models import Order
from app.db.models import OrderItem
from app.db.models import Product
from app.db.models import ProductImage
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryProductMatch
from app.db.models import RegulatorySource
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from scripts.seed_sample_data import ADMIN_EMAIL
from scripts.seed_sample_data import SeedTargetError
from scripts.seed_sample_data import run_seed
from scripts.seed_sample_data import validate_target


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


# --------------------------------------------------------------------- #
# A. dry-run writes nothing
# --------------------------------------------------------------------- #


def test_dry_run_writes_nothing(db_session: Session) -> None:
    summary = run_seed(db_session, target=None, dry_run=True)

    # The plan reports work it WOULD do...
    assert summary.dry_run is True
    assert summary.counts["stores"].created == len(
        ["demo-a", "demo-b"]
    )
    assert summary.counts["users"].created > 0

    # ...but the transaction was rolled back: nothing persisted.
    assert _count(db_session, Store) == 0
    assert _count(db_session, User) == 0
    assert _count(db_session, Product) == 0
    assert _count(db_session, Order) == 0


def test_dry_run_allowed_without_target(db_session: Session) -> None:
    # A write-free preview needs no --target.
    summary = run_seed(db_session, target=None, dry_run=True)
    assert summary.target is None
    assert _count(db_session, Store) == 0


# --------------------------------------------------------------------- #
# B. a real run creates the base demo fixtures
# --------------------------------------------------------------------- #


def test_seed_creates_base_data(db_session: Session) -> None:
    run_seed(db_session, target="local", dry_run=False)

    codes = set(db_session.scalars(select(Store.code)).all())
    assert {"demo-a", "demo-b"} <= codes

    # Global admin.
    admin = db_session.scalar(select(User).where(User.email == ADMIN_EMAIL))
    assert admin is not None
    assert admin.role == UserRole.admin
    assert admin.store_id is None
    # Seeded users are app-records only — no Supabase identity yet.
    assert admin.auth_user_id is None

    # Per-store role users exist for both demo stores.
    for code in ("demo-a", "demo-b"):
        for local_part in (
            "owner",
            "manager",
            "staff1",
            "staff2",
            "driver",
        ):
            email = f"{local_part}@{code}.nuberush.dev"
            user = db_session.scalar(
                select(User).where(User.email == email)
            )
            assert user is not None, email

    assert _count(db_session, Product) == 20
    assert _count(db_session, ProductVariant) > 20
    assert _count(db_session, InventoryItem) > 0
    assert _count(db_session, Order) > 0
    assert _count(db_session, OrderItem) > 0


# --------------------------------------------------------------------- #
# C. a second run is idempotent
# --------------------------------------------------------------------- #


def test_second_run_is_idempotent(db_session: Session) -> None:
    run_seed(db_session, target="local", dry_run=False)

    snapshot = {
        model: _count(db_session, model)
        for model in (
            Store,
            User,
            Product,
            ProductVariant,
            InventoryItem,
            Order,
            OrderItem,
        )
    }

    second = run_seed(db_session, target="local", dry_run=False)

    for model, before in snapshot.items():
        assert _count(db_session, model) == before, model.__name__

    # Everything the second run touched was already present.
    assert second.counts["stores"].created == 0
    assert second.counts["users"].created == 0
    assert second.counts["products"].created == 0
    assert second.counts["variants"].created == 0
    assert second.counts["orders"].created == 0


# --------------------------------------------------------------------- #
# D. production-like targets are rejected
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "blocked", ["production", "prod", "live", "main-prod", "PROD", " Production "]
)
def test_production_targets_are_blocked(
    db_session: Session, blocked: str
) -> None:
    # Rejected even when only previewing.
    with pytest.raises(SeedTargetError):
        validate_target(blocked, dry_run=True)
    with pytest.raises(SeedTargetError):
        validate_target(blocked, dry_run=False)
    # And the orchestrator refuses too, writing nothing.
    with pytest.raises(SeedTargetError):
        run_seed(db_session, target=blocked, dry_run=False)
    assert _count(db_session, Store) == 0


def test_write_requires_target(db_session: Session) -> None:
    with pytest.raises(SeedTargetError):
        validate_target(None, dry_run=False)


def test_unknown_target_is_rejected(db_session: Session) -> None:
    with pytest.raises(SeedTargetError):
        validate_target("qa", dry_run=False)


# --------------------------------------------------------------------- #
# E. product image metadata is idempotent
# --------------------------------------------------------------------- #


def test_product_image_metadata_idempotent(db_session: Session) -> None:
    run_seed(db_session, target="local", dry_run=False)
    first = _count(db_session, ProductImage)
    assert first > 0

    run_seed(db_session, target="local", dry_run=False)
    assert _count(db_session, ProductImage) == first

    # Metadata-only: object keys are deterministic placeholders, never a
    # real uploaded object.
    keys = list(db_session.scalars(select(ProductImage.object_key)).all())
    assert all(k.startswith("products/demo/") for k in keys)


# --------------------------------------------------------------------- #
# F. regulatory fixtures are idempotent
# --------------------------------------------------------------------- #


def test_regulatory_fixtures_idempotent(db_session: Session) -> None:
    run_seed(db_session, target="local", dry_run=False)

    snapshot = {
        model: _count(db_session, model)
        for model in (
            RegulatorySource,
            RegulatoryNotice,
            RegulatoryProductMatch,
            ComplianceAlert,
            RegulatoryDecisionAuditLog,
        )
    }
    # The minimal fixture creates exactly one of each.
    for model, count in snapshot.items():
        assert count == 1, model.__name__

    run_seed(db_session, target="local", dry_run=False)

    for model, before in snapshot.items():
        assert _count(db_session, model) == before, model.__name__

    # Advisory only — the fixture never bans/holds a real product.
    alert = db_session.scalar(select(ComplianceAlert))
    assert alert is not None
    product = db_session.get(Product, alert.product_id)
    assert product is not None
    assert product.allowed_for_sale is True


# --------------------------------------------------------------------- #
# G. no real Supabase env is required
# --------------------------------------------------------------------- #


def test_seed_needs_no_supabase_env(db_session: Session) -> None:
    # The autouse settings-isolation fixture strips these; the seed path
    # must run green without them.
    assert os.environ.get("SUPABASE_URL") is None
    assert os.environ.get("SUPABASE_SERVICE_ROLE_KEY") is None

    summary = run_seed(db_session, target="local", dry_run=False)
    assert summary.counts["stores"].created == 2
