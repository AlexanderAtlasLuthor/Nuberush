"""F2.22.4.D — schema/model coverage for product_images.

These tests cover the metadata schema only: the ORM model, the
``unique(product_id)`` constraint, and the ``ProductImageRead`` /
``ProductRead.primary_image`` Pydantic surface. Upload endpoints,
signed-URL generation and Supabase Storage calls land in later
subphases and are explicitly out of scope here.
"""
from __future__ import annotations

import uuid
from typing import Callable

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductImage
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.products import ProductImageRead
from app.schemas.products import ProductRead
from tests.helpers.auth import make_user as central_make_user


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        store = Store(name="Img-QA", code=f"iq-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_admin_user(db_session: Session) -> Callable[..., User]:
    def _create() -> User:
        return central_make_user(
            db_session,
            role=UserRole.admin,
            store_id=None,
            full_name="Image Admin",
            is_active=True,
        )

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create() -> Product:
        product = Product(
            name=f"Img-{uuid.uuid4().hex[:6]}",
            category="vape",
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
            is_active=True,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


@pytest.fixture
def make_image(
    db_session: Session,
    make_admin_user: Callable[..., User],
) -> Callable[..., ProductImage]:
    def _create(
        product: Product,
        *,
        object_key: str | None = None,
        uploader: User | None = None,
    ) -> ProductImage:
        image = ProductImage(
            product_id=product.id,
            object_key=object_key or f"{product.id}/{uuid.uuid4().hex}.jpg",
            uploaded_by_user_id=(uploader or make_admin_user()).id,
        )
        db_session.add(image)
        db_session.commit()
        db_session.refresh(image)
        return image

    return _create


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------


class TestProductImageModel:
    def test_creates_with_required_fields(
        self,
        db_session: Session,
        make_product: Callable[..., Product],
        make_admin_user: Callable[..., User],
    ) -> None:
        product = make_product()
        admin = make_admin_user()

        image = ProductImage(
            product_id=product.id,
            object_key=f"{product.id}/cover.png",
            uploaded_by_user_id=admin.id,
        )
        db_session.add(image)
        db_session.commit()
        db_session.refresh(image)

        assert image.id is not None
        assert image.product_id == product.id
        assert image.uploaded_by_user_id == admin.id
        assert image.object_key == f"{product.id}/cover.png"
        assert image.created_at is not None
        assert image.updated_at is not None

    def test_unique_product_id_blocks_second_image(
        self,
        db_session: Session,
        make_product: Callable[..., Product],
        make_image: Callable[..., ProductImage],
        make_admin_user: Callable[..., User],
    ) -> None:
        product = make_product()
        make_image(product)

        duplicate = ProductImage(
            product_id=product.id,
            object_key=f"{product.id}/second.png",
            uploaded_by_user_id=make_admin_user().id,
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_product_primary_image_relationship_loads(
        self,
        db_session: Session,
        make_product: Callable[..., Product],
        make_image: Callable[..., ProductImage],
    ) -> None:
        product = make_product()
        assert product.primary_image is None

        image = make_image(product)
        db_session.expire(product, ["primary_image"])
        assert product.primary_image is not None
        assert product.primary_image.id == image.id


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TestProductReadPrimaryImage:
    def test_product_read_primary_image_none_when_absent(
        self,
        make_product: Callable[..., Product],
    ) -> None:
        product = make_product()
        read = ProductRead.model_validate(product)
        assert read.primary_image is None

    def test_product_read_exposes_primary_image_when_present(
        self,
        db_session: Session,
        make_product: Callable[..., Product],
        make_image: Callable[..., ProductImage],
    ) -> None:
        product = make_product()
        image = make_image(product, object_key=f"{product.id}/hero.webp")
        db_session.expire(product, ["primary_image"])

        read = ProductRead.model_validate(product)
        assert read.primary_image is not None
        assert read.primary_image.id == image.id
        assert read.primary_image.object_key == f"{product.id}/hero.webp"


class TestProductImageReadPublicUrl:
    def test_public_url_is_none_when_supabase_url_missing(
        self,
        db_session: Session,
        make_product: Callable[..., Product],
        make_image: Callable[..., ProductImage],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # conftest._isolate_settings_env already strips SUPABASE_URL.
        # Re-clear the cache so settings reflect the stripped env.
        from app.core.config import get_supabase_auth_settings

        get_supabase_auth_settings.cache_clear()

        product = make_product()
        image = make_image(product)
        read = ProductImageRead.model_validate(image)

        assert read.public_url is None

    def test_public_url_built_from_supabase_url_when_configured(
        self,
        db_session: Session,
        make_product: Callable[..., Product],
        make_image: Callable[..., ProductImage],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        from app.core.config import get_supabase_auth_settings

        get_supabase_auth_settings.cache_clear()

        product = make_product()
        image = make_image(product, object_key="prod-1/hero.png")
        read = ProductImageRead.model_validate(image)

        assert read.public_url == (
            "https://example.supabase.co/storage/v1/object/public/"
            "product-images/prod-1/hero.png"
        )

        get_supabase_auth_settings.cache_clear()
