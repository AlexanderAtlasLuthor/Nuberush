"""Tests for the variant <-> QuickBooks mapping + discovery service (F2.27.9.C).

Service-level coverage over the transactional db_session:
  - create/list/update mappings + sync_enabled toggle;
  - per-integration uniqueness (variant + external item) enforced;
  - cross-store tenancy isolation (store A cannot touch store B mappings);
  - invalid variant / missing / disconnected integration rejected;
  - item discovery via a FAKE client (no network, no credentials);
  - NO Product / ProductVariant / InventoryItem / InventoryLog / sync-log
    mutation.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_quickbooks_settings
from app.core.encryption import encrypt_token
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import AccountingSyncLog
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import ProductVariantAccountingMapping
from app.db.models import Store
from app.db.models import StoreAccountingIntegration
from app.schemas.accounting import AccountingMappingCreateRequest
from app.schemas.accounting import AccountingMappingUpdateRequest
from app.services.accounting import mappings as mappings_svc
from app.services.accounting import oauth as oauth_svc
from app.services.accounting.quickbooks_client import QuickBooksItemSummary


# --------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------- #


@pytest.fixture
def qb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "QUICKBOOKS_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )
    monkeypatch.setenv("QUICKBOOKS_MAX_ITEMS_PER_RUN", "100")
    get_quickbooks_settings.cache_clear()
    yield
    get_quickbooks_settings.cache_clear()


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        s = Store(name="Map Store", code=f"map-{uuid.uuid4().hex[:8]}")
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    return _create


@pytest.fixture
def make_variant(db_session: Session) -> Callable[..., ProductVariant]:
    def _create() -> ProductVariant:
        product = Product(name="Map Product", category="vape")
        db_session.add(product)
        db_session.flush()
        variant = ProductVariant(
            product_id=product.id,
            sku=f"SKU-{uuid.uuid4().hex[:10]}",
            price=Decimal("9.99"),
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_integration(
    db_session: Session, qb_env: None
) -> Callable[..., StoreAccountingIntegration]:
    def _create(store: Store, *, status: str = "connected", with_tokens: bool = True):
        integration = StoreAccountingIntegration(
            store_id=store.id,
            provider="quickbooks",
            status=status,
            environment="sandbox",
            realm_id="REALM-1",
            access_token_encrypted=encrypt_token("AT") if with_tokens else None,
            refresh_token_encrypted=encrypt_token("RT") if with_tokens else None,
        )
        db_session.add(integration)
        db_session.commit()
        db_session.refresh(integration)
        return integration

    return _create


def _create_req(variant_id, **over) -> AccountingMappingCreateRequest:
    return AccountingMappingCreateRequest(
        variant_id=variant_id,
        external_item_id=over.get("external_item_id", f"QB-{uuid.uuid4().hex[:6]}"),
        external_item_name=over.get("external_item_name", "Widget"),
        sync_enabled=over.get("sync_enabled", True),
    )


# --------------------------------------------------------------------- #
# create / list / update
# --------------------------------------------------------------------- #


def test_create_mapping_succeeds(
    db_session: Session,
    make_store,
    make_variant,
    make_integration,
) -> None:
    store = make_store()
    integration = make_integration(store)
    variant = make_variant()

    mapping = mappings_svc.create_mapping(
        db_session,
        store_id=store.id,
        payload=_create_req(variant.id, external_item_id="QB-1"),
    )
    assert mapping.id is not None
    assert mapping.integration_id == integration.id
    assert mapping.store_id == integration.store_id == store.id
    assert mapping.variant_id == variant.id
    assert mapping.provider == "quickbooks"
    assert mapping.external_item_id == "QB-1"
    assert mapping.sync_enabled is True


def test_list_mappings_is_store_scoped(
    db_session: Session,
    make_store,
    make_variant,
    make_integration,
) -> None:
    store_a, store_b = make_store(), make_store()
    int_a, int_b = make_integration(store_a), make_integration(store_b)
    v1, v2 = make_variant(), make_variant()
    mappings_svc.create_mapping(
        db_session, store_id=store_a.id, payload=_create_req(v1.id)
    )
    mappings_svc.create_mapping(
        db_session, store_id=store_b.id, payload=_create_req(v2.id)
    )

    rows_a, total_a = mappings_svc.list_mappings(db_session, store_id=store_a.id)
    assert total_a == 1
    assert all(m.integration_id == int_a.id for m in rows_a)
    rows_b, total_b = mappings_svc.list_mappings(db_session, store_id=store_b.id)
    assert total_b == 1
    assert all(m.integration_id == int_b.id for m in rows_b)


def test_update_mapping_changes_fields(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store = make_store()
    make_integration(store)
    variant = make_variant()
    mapping = mappings_svc.create_mapping(
        db_session,
        store_id=store.id,
        payload=_create_req(variant.id, external_item_id="QB-OLD"),
    )
    updated = mappings_svc.update_mapping(
        db_session,
        store_id=store.id,
        mapping_id=mapping.id,
        payload=AccountingMappingUpdateRequest(
            external_item_id="QB-NEW", external_item_name="Renamed"
        ),
    )
    assert updated.external_item_id == "QB-NEW"
    assert updated.external_item_name == "Renamed"


def test_toggle_sync_enabled(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store = make_store()
    make_integration(store)
    variant = make_variant()
    mapping = mappings_svc.create_mapping(
        db_session, store_id=store.id, payload=_create_req(variant.id)
    )
    assert mapping.sync_enabled is True
    toggled = mappings_svc.update_mapping(
        db_session,
        store_id=store.id,
        mapping_id=mapping.id,
        payload=AccountingMappingUpdateRequest(sync_enabled=False),
    )
    assert toggled.sync_enabled is False


# --------------------------------------------------------------------- #
# uniqueness / tenancy / validation
# --------------------------------------------------------------------- #


def test_duplicate_variant_same_integration_rejected(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store = make_store()
    make_integration(store)
    variant = make_variant()
    mappings_svc.create_mapping(
        db_session, store_id=store.id, payload=_create_req(variant.id, external_item_id="A")
    )
    with pytest.raises(HTTPException) as exc:
        mappings_svc.create_mapping(
            db_session,
            store_id=store.id,
            payload=_create_req(variant.id, external_item_id="B"),
        )
    assert exc.value.status_code == 409


def test_duplicate_external_item_same_integration_rejected(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store = make_store()
    make_integration(store)
    v1, v2 = make_variant(), make_variant()
    mappings_svc.create_mapping(
        db_session, store_id=store.id, payload=_create_req(v1.id, external_item_id="QB-SAME")
    )
    with pytest.raises(HTTPException) as exc:
        mappings_svc.create_mapping(
            db_session,
            store_id=store.id,
            payload=_create_req(v2.id, external_item_id="QB-SAME"),
        )
    assert exc.value.status_code == 409


def test_same_variant_and_external_item_allowed_across_integrations(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store_a, store_b = make_store(), make_store()
    make_integration(store_a)
    make_integration(store_b)
    variant = make_variant()  # global catalog variant

    m_a = mappings_svc.create_mapping(
        db_session, store_id=store_a.id, payload=_create_req(variant.id, external_item_id="QB-X")
    )
    m_b = mappings_svc.create_mapping(
        db_session, store_id=store_b.id, payload=_create_req(variant.id, external_item_id="QB-X")
    )
    # Same variant + same external id is fine in DIFFERENT integrations.
    assert m_a.id != m_b.id
    assert m_a.integration_id != m_b.integration_id


def test_cross_store_mapping_update_is_404(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store_a, store_b = make_store(), make_store()
    make_integration(store_a)
    make_integration(store_b)
    variant = make_variant()
    mapping_a = mappings_svc.create_mapping(
        db_session, store_id=store_a.id, payload=_create_req(variant.id)
    )
    # Store B trying to update store A's mapping -> 404 (no enumeration).
    with pytest.raises(HTTPException) as exc:
        mappings_svc.update_mapping(
            db_session,
            store_id=store_b.id,
            mapping_id=mapping_a.id,
            payload=AccountingMappingUpdateRequest(sync_enabled=False),
        )
    assert exc.value.status_code == 404


def test_invalid_variant_rejected(
    db_session: Session, make_store, make_integration
) -> None:
    store = make_store()
    make_integration(store)
    with pytest.raises(HTTPException) as exc:
        mappings_svc.create_mapping(
            db_session, store_id=store.id, payload=_create_req(uuid.uuid4())
        )
    assert exc.value.status_code == 422


def test_missing_integration_rejected(
    db_session: Session, make_store, make_variant
) -> None:
    store = make_store()  # no integration
    variant = make_variant()
    with pytest.raises(HTTPException) as exc:
        mappings_svc.create_mapping(
            db_session, store_id=store.id, payload=_create_req(variant.id)
        )
    assert exc.value.status_code == 404


def test_disconnected_integration_rejected(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store = make_store()
    make_integration(store, status="disconnected", with_tokens=False)
    variant = make_variant()
    with pytest.raises(HTTPException) as exc:
        mappings_svc.create_mapping(
            db_session, store_id=store.id, payload=_create_req(variant.id)
        )
    assert exc.value.status_code == 409


# --------------------------------------------------------------------- #
# No inventory / catalog / sync-log mutation
# --------------------------------------------------------------------- #


def test_mapping_ops_do_not_mutate_catalog_or_inventory(
    db_session: Session, make_store, make_variant, make_integration
) -> None:
    store = make_store()
    make_integration(store)
    variant = make_variant()

    def counts() -> dict:
        return {
            "product": db_session.scalar(select(func.count()).select_from(Product)),
            "variant": db_session.scalar(select(func.count()).select_from(ProductVariant)),
            "inv_item": db_session.scalar(select(func.count()).select_from(InventoryItem)),
            "inv_log": db_session.scalar(select(func.count()).select_from(InventoryLog)),
            "sync_log": db_session.scalar(select(func.count()).select_from(AccountingSyncLog)),
        }

    before = counts()
    mapping = mappings_svc.create_mapping(
        db_session, store_id=store.id, payload=_create_req(variant.id)
    )
    mappings_svc.update_mapping(
        db_session,
        store_id=store.id,
        mapping_id=mapping.id,
        payload=AccountingMappingUpdateRequest(sync_enabled=False),
    )
    after = counts()
    assert after == before  # NOTHING in catalog/inventory/sync-log changed


# --------------------------------------------------------------------- #
# Item discovery (fake client, no network)
# --------------------------------------------------------------------- #


def test_list_quickbooks_items_returns_safe_summaries(
    db_session: Session,
    make_store,
    make_integration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = make_store()
    make_integration(store)

    captured: dict = {}

    class FakeClient:
        def list_items(self, *, access_token, realm_id, environment, max_items):
            captured["access_token"] = access_token
            captured["realm_id"] = realm_id
            captured["environment"] = environment
            captured["max_items"] = max_items
            return [
                QuickBooksItemSummary(
                    external_item_id="1", name="Widget", sku="W-1",
                    description=None, unit_price=1.0, purchase_cost=None,
                    quantity_on_hand=5.0,
                )
            ]

    monkeypatch.setattr(oauth_svc, "resolve_quickbooks_client", lambda: FakeClient())

    items = mappings_svc.list_quickbooks_items(db_session, store_id=store.id)
    assert len(items) == 1
    assert items[0].external_item_id == "1"
    assert items[0].name == "Widget"
    # Decrypted token was passed to the client (in memory only) + realm/env.
    assert captured["access_token"] == "AT"
    assert captured["realm_id"] == "REALM-1"
    assert captured["environment"] == "sandbox"
    assert captured["max_items"] == 100


def test_list_quickbooks_items_requires_connected_integration(
    db_session: Session, make_store, make_variant
) -> None:
    store = make_store()  # no integration
    with pytest.raises(HTTPException) as exc:
        mappings_svc.list_quickbooks_items(db_session, store_id=store.id)
    assert exc.value.status_code == 404
