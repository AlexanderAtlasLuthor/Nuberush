"""Tests for the inventory push preview/confirm + sync-ledger service (F2.27.9.D).

Service-level coverage over the transactional db_session with a FAKE QuickBooks
client (NO network, NO credentials):
  - preview is read-only: no DB write, no ledger row, no QuickBooks call;
  - confirm creates an AccountingSyncLog + per-item AccountingSyncLogItem rows,
    pushes the NubeRush-authoritative quantity, and NEVER pulls QuickBooks
    quantity back into NubeRush;
  - status succeeded / partial / failed + counters are computed correctly;
  - mapping.last_synced_at and integration.last_sync_at update correctly;
  - NO InventoryItem / InventoryLog / Product / ProductVariant mutation;
  - tenancy: sync-run listing is store-scoped; detail is admin-global by id.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Callable

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_quickbooks_settings
from app.core.encryption import encrypt_token
from app.db.models import AccountingSyncLog
from app.db.models import AccountingSyncLogItem
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import ProductVariantAccountingMapping
from app.db.models import Store
from app.db.models import StoreAccountingIntegration
from app.services.accounting import oauth as oauth_svc
from app.services.accounting import sync as sync_svc
from app.services.accounting.quickbooks_client import QuickBooksClientError
from app.services.accounting.quickbooks_client import (
    QuickBooksItemQuantityUpdateResult,
)


# The distinctive plaintext access token lets leak assertions be meaningful.
_ACCESS_PLAINTEXT = "ACCESS-TOKEN-PLAINTEXT"
# What the fake QuickBooks echoes back AFTER a write — must NEVER land in
# NubeRush inventory.
_QB_ECHO_QTY = 999.0


# --------------------------------------------------------------------- #
# Fake QuickBooks client (no network)
# --------------------------------------------------------------------- #


class FakeQB:
    def __init__(self, *, fail_ids: set[str] | None = None) -> None:
        self.calls: list[SimpleNamespace] = []
        self.fail_ids = set(fail_ids or set())

    def update_item_quantity(
        self,
        *,
        access_token: str,
        realm_id: str,
        external_item_id: str,
        quantity_on_hand: float,
        environment: str = "sandbox",
        **_: object,
    ) -> QuickBooksItemQuantityUpdateResult:
        self.calls.append(
            SimpleNamespace(
                access_token=access_token,
                realm_id=realm_id,
                external_item_id=external_item_id,
                quantity_on_hand=quantity_on_hand,
                environment=environment,
            )
        )
        if external_item_id in self.fail_ids:
            raise QuickBooksClientError(
                "QuickBooks item update was rejected (status 400)."
            )
        return QuickBooksItemQuantityUpdateResult(
            external_item_id=external_item_id,
            pushed_quantity=float(quantity_on_hand),
            quickbooks_quantity_on_hand=_QB_ECHO_QTY,
            sync_token="1",
            attempts=1,
        )


# --------------------------------------------------------------------- #
# Fixtures
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
def fake_qb(monkeypatch: pytest.MonkeyPatch) -> FakeQB:
    fake = FakeQB()
    monkeypatch.setattr(
        oauth_svc, "resolve_quickbooks_client", lambda: fake
    )
    return fake


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        s = Store(name="Sync Store", code=f"sync-{uuid.uuid4().hex[:8]}")
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    return _create


@pytest.fixture
def make_variant(db_session: Session) -> Callable[..., ProductVariant]:
    def _create() -> ProductVariant:
        product = Product(name="Sync Product", category="vape")
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
    def _create(
        store: Store,
        *,
        status: str = "connected",
        access_plaintext: str | None = _ACCESS_PLAINTEXT,
        access_ciphertext: str | None = None,
    ) -> StoreAccountingIntegration:
        if access_ciphertext is not None:
            enc = access_ciphertext
        elif access_plaintext is not None:
            enc = encrypt_token(access_plaintext)
        else:
            enc = None
        integration = StoreAccountingIntegration(
            store_id=store.id,
            provider="quickbooks",
            status=status,
            environment="sandbox",
            realm_id="REALM-1",
            access_token_encrypted=enc,
            refresh_token_encrypted=encrypt_token("RT") if enc else None,
        )
        db_session.add(integration)
        db_session.commit()
        db_session.refresh(integration)
        return integration

    return _create


@pytest.fixture
def make_mapping(
    db_session: Session,
) -> Callable[..., ProductVariantAccountingMapping]:
    def _create(
        integration: StoreAccountingIntegration,
        variant: ProductVariant,
        *,
        external_item_id: str | None = None,
        sync_enabled: bool = True,
    ) -> ProductVariantAccountingMapping:
        mapping = ProductVariantAccountingMapping(
            integration_id=integration.id,
            store_id=integration.store_id,
            variant_id=variant.id,
            provider="quickbooks",
            external_item_id=external_item_id or f"QB-{uuid.uuid4().hex[:6]}",
            external_item_name="Widget",
            sync_enabled=sync_enabled,
        )
        db_session.add(mapping)
        db_session.commit()
        db_session.refresh(mapping)
        return mapping

    return _create


@pytest.fixture
def make_inventory(db_session: Session) -> Callable[..., InventoryItem]:
    def _create(
        store: Store, variant: ProductVariant, quantity_on_hand: int
    ) -> InventoryItem:
        item = InventoryItem(
            store_id=store.id,
            variant_id=variant.id,
            quantity_on_hand=quantity_on_hand,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


def _ledger_counts(db: Session) -> dict:
    return {
        "log": db.scalar(select(func.count()).select_from(AccountingSyncLog)),
        "item": db.scalar(
            select(func.count()).select_from(AccountingSyncLogItem)
        ),
        "inv_item": db.scalar(select(func.count()).select_from(InventoryItem)),
        "inv_log": db.scalar(select(func.count()).select_from(InventoryLog)),
        "product": db.scalar(select(func.count()).select_from(Product)),
        "variant": db.scalar(select(func.count()).select_from(ProductVariant)),
    }


# ===================================================================== #
# Preview — read-only
# ===================================================================== #


def test_preview_returns_proposed_updates(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v1, v2 = make_variant(), make_variant()
    make_mapping(integ, v1, external_item_id="QB-1")
    make_mapping(integ, v2, external_item_id="QB-2")
    make_inventory(store, v1, 7)
    make_inventory(store, v2, 3)

    preview = sync_svc.build_inventory_push_preview(db_session, store_id=store.id)
    assert preview.store_id == store.id
    assert preview.integration_id == integ.id
    assert preview.total_mappings == 2
    assert preview.items_to_push == 2
    assert preview.items_skipped == 0
    quantities = {i.external_item_id: i.nube_quantity_on_hand for i in preview.items}
    assert quantities == {"QB-1": 7, "QB-2": 3}
    assert all(i.proposed_action == "push" for i in preview.items)
    # QuickBooks current quantity is NOT fetched during preview.
    assert all(i.quickbooks_quantity_on_hand is None for i in preview.items)


def test_preview_does_not_write_db_or_call_quickbooks(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, fake_qb,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v = make_variant()
    make_mapping(integ, v, external_item_id="QB-1")
    make_inventory(store, v, 5)

    before = _ledger_counts(db_session)
    sync_svc.build_inventory_push_preview(db_session, store_id=store.id)
    after = _ledger_counts(db_session)
    assert after == before  # no ledger/inventory/catalog rows created
    assert fake_qb.calls == []  # preview never calls the QuickBooks client


def test_preview_skips_disabled_mappings(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v_on, v_off = make_variant(), make_variant()
    make_mapping(integ, v_on, external_item_id="QB-ON", sync_enabled=True)
    make_mapping(integ, v_off, external_item_id="QB-OFF", sync_enabled=False)
    make_inventory(store, v_on, 4)
    make_inventory(store, v_off, 9)

    preview = sync_svc.build_inventory_push_preview(db_session, store_id=store.id)
    ext_ids = {i.external_item_id for i in preview.items}
    assert ext_ids == {"QB-ON"}  # disabled mapping excluded
    assert preview.total_mappings == 1


def test_preview_missing_inventory_marked_skip(
    db_session, make_store, make_variant, make_integration, make_mapping,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v = make_variant()
    make_mapping(integ, v, external_item_id="QB-1")
    # No InventoryItem for this variant/store.

    preview = sync_svc.build_inventory_push_preview(db_session, store_id=store.id)
    assert preview.items_to_push == 0
    assert preview.items_skipped == 1
    item = preview.items[0]
    assert item.proposed_action == "skip"
    assert item.nube_quantity_on_hand is None
    assert item.issue is not None


def test_preview_missing_integration_rejected(
    db_session, make_store,
) -> None:
    store = make_store()
    with pytest.raises(HTTPException) as exc:
        sync_svc.build_inventory_push_preview(db_session, store_id=store.id)
    assert exc.value.status_code == 404


def test_preview_disconnected_integration_rejected(
    db_session, make_store, make_integration,
) -> None:
    store = make_store()
    make_integration(store, status="disconnected", access_plaintext=None)
    with pytest.raises(HTTPException) as exc:
        sync_svc.build_inventory_push_preview(db_session, store_id=store.id)
    assert exc.value.status_code == 409


# ===================================================================== #
# Confirm — ledger + outbound push
# ===================================================================== #


def test_confirm_all_success_creates_ledger_and_pushes(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, fake_qb,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v1, v2 = make_variant(), make_variant()
    m1 = make_mapping(integ, v1, external_item_id="QB-1")
    m2 = make_mapping(integ, v2, external_item_id="QB-2")
    make_inventory(store, v1, 42)
    make_inventory(store, v2, 8)

    log, items = sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )
    assert log.status == "succeeded"
    assert log.sync_type == "inventory_push"
    assert log.direction == "push"
    assert log.trigger == "manual"
    assert log.items_seen == 2
    assert log.items_updated == 2
    assert log.items_skipped == 0
    assert log.items_failed == 0
    assert log.finished_at is not None
    assert {i.outcome for i in items} == {"updated"}

    # NubeRush-authoritative quantities were pushed (NOT QuickBooks values).
    pushed = {c.external_item_id: c.quantity_on_hand for c in fake_qb.calls}
    assert pushed == {"QB-1": 42.0, "QB-2": 8.0}
    assert all(c.access_token == _ACCESS_PLAINTEXT for c in fake_qb.calls)

    # last_synced_at set on both mappings; integration.last_sync_at stamped.
    db_session.refresh(m1)
    db_session.refresh(m2)
    db_session.refresh(integ)
    assert m1.last_synced_at is not None
    assert m2.last_synced_at is not None
    assert integ.last_sync_at is not None


def test_confirm_pushes_nube_quantity_and_never_imports_qb_quantity(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, fake_qb,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v = make_variant()
    make_mapping(integ, v, external_item_id="QB-1")
    inv = make_inventory(store, v, 42)

    sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )
    # The fake echoes back 999; NubeRush inventory must remain 42 (no import).
    db_session.refresh(inv)
    assert inv.quantity_on_hand == 42
    assert fake_qb.calls[0].quantity_on_hand == 42.0


def test_confirm_partial_when_some_fail(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, monkeypatch,
) -> None:
    fake = FakeQB(fail_ids={"QB-FAIL"})
    monkeypatch.setattr(oauth_svc, "resolve_quickbooks_client", lambda: fake)

    store = make_store()
    integ = make_integration(store)
    v_ok, v_bad = make_variant(), make_variant()
    m_ok = make_mapping(integ, v_ok, external_item_id="QB-OK")
    m_bad = make_mapping(integ, v_bad, external_item_id="QB-FAIL")
    make_inventory(store, v_ok, 10)
    make_inventory(store, v_bad, 20)

    log, items = sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )
    assert log.status == "partial"
    assert log.items_updated == 1
    assert log.items_failed == 1
    assert log.error_summary is not None
    outcomes = {i.external_item_id: i.outcome for i in items}
    assert outcomes == {"QB-OK": "updated", "QB-FAIL": "failed"}

    # last_synced_at only on the successful mapping; integration stamped.
    db_session.refresh(m_ok)
    db_session.refresh(m_bad)
    db_session.refresh(integ)
    assert m_ok.last_synced_at is not None
    assert m_bad.last_synced_at is None
    assert integ.last_sync_at is not None


def test_confirm_all_fail_is_failed_and_no_integration_stamp(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, monkeypatch,
) -> None:
    fake = FakeQB(fail_ids={"QB-A", "QB-B"})
    monkeypatch.setattr(oauth_svc, "resolve_quickbooks_client", lambda: fake)

    store = make_store()
    integ = make_integration(store)
    v1, v2 = make_variant(), make_variant()
    make_mapping(integ, v1, external_item_id="QB-A")
    make_mapping(integ, v2, external_item_id="QB-B")
    make_inventory(store, v1, 1)
    make_inventory(store, v2, 2)

    log, items = sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )
    assert log.status == "failed"
    assert log.items_updated == 0
    assert log.items_failed == 2
    assert {i.outcome for i in items} == {"failed"}
    db_session.refresh(integ)
    assert integ.last_sync_at is None  # nothing pushed -> no stamp


def test_confirm_counters_with_mixed_outcomes(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, monkeypatch,
) -> None:
    fake = FakeQB(fail_ids={"QB-FAIL"})
    monkeypatch.setattr(oauth_svc, "resolve_quickbooks_client", lambda: fake)

    store = make_store()
    integ = make_integration(store)
    v_ok, v_fail, v_skip = make_variant(), make_variant(), make_variant()
    make_mapping(integ, v_ok, external_item_id="QB-OK")
    make_mapping(integ, v_fail, external_item_id="QB-FAIL")
    make_mapping(integ, v_skip, external_item_id="QB-SKIP")
    make_inventory(store, v_ok, 5)
    make_inventory(store, v_fail, 6)
    # v_skip has NO inventory -> skipped.

    log, items = sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )
    assert log.items_seen == 3
    assert log.items_updated == 1
    assert log.items_failed == 1
    assert log.items_skipped == 1
    assert log.status == "partial"  # at least one updated, at least one failed
    outcomes = {i.external_item_id: i.outcome for i in items}
    assert outcomes == {
        "QB-OK": "updated", "QB-FAIL": "failed", "QB-SKIP": "skipped",
    }


def test_confirm_no_mappings_creates_failed_log(
    db_session, make_store, make_integration, fake_qb,
) -> None:
    store = make_store()
    make_integration(store)

    log, items = sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )
    assert log.status == "failed"
    assert log.items_seen == 0
    assert items == []
    assert log.error_summary == "No sync-enabled mappings to push."
    assert fake_qb.calls == []


def test_confirm_token_decrypt_failure_is_sanitized_failed_log(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, fake_qb,
) -> None:
    store = make_store()
    integ = make_integration(store, access_ciphertext="not-valid-fernet")
    v = make_variant()
    make_mapping(integ, v, external_item_id="QB-1")
    make_inventory(store, v, 5)

    log, items = sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )
    assert log.status == "failed"
    assert items == []
    assert log.error_summary is not None
    assert "not-valid-fernet" not in log.error_summary
    assert _ACCESS_PLAINTEXT not in (log.error_summary or "")
    # No QuickBooks push attempted when the token cannot be read.
    assert fake_qb.calls == []


def test_confirm_does_not_mutate_inventory_catalog_or_logs(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, fake_qb,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v = make_variant()
    make_mapping(integ, v, external_item_id="QB-1")
    inv = make_inventory(store, v, 15)

    inv_count = db_session.scalar(
        select(func.count()).select_from(InventoryItem)
    )
    inv_log_count = db_session.scalar(
        select(func.count()).select_from(InventoryLog)
    )
    product_count = db_session.scalar(select(func.count()).select_from(Product))
    variant_count = db_session.scalar(
        select(func.count()).select_from(ProductVariant)
    )

    sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )

    db_session.refresh(inv)
    assert inv.quantity_on_hand == 15  # unchanged
    assert inv_count == db_session.scalar(
        select(func.count()).select_from(InventoryItem)
    )
    assert inv_log_count == db_session.scalar(
        select(func.count()).select_from(InventoryLog)
    )
    assert product_count == db_session.scalar(
        select(func.count()).select_from(Product)
    )
    assert variant_count == db_session.scalar(
        select(func.count()).select_from(ProductVariant)
    )


def test_confirm_disconnected_integration_rejected_no_log(
    db_session, make_store, make_integration,
) -> None:
    store = make_store()
    make_integration(store, status="disconnected", access_plaintext=None)
    before = db_session.scalar(
        select(func.count()).select_from(AccountingSyncLog)
    )
    with pytest.raises(HTTPException) as exc:
        sync_svc.confirm_inventory_push(
            db_session, store_id=store.id, actor_user_id=None
        )
    assert exc.value.status_code == 409
    after = db_session.scalar(
        select(func.count()).select_from(AccountingSyncLog)
    )
    assert after == before  # no ledger side effect on a rejected confirm


# ===================================================================== #
# Ledger reads — tenancy + detail
# ===================================================================== #


def test_list_sync_runs_is_store_scoped(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, fake_qb,
) -> None:
    store_a, store_b = make_store(), make_store()
    integ_a = make_integration(store_a)
    make_integration(store_b)
    v = make_variant()
    make_mapping(integ_a, v, external_item_id="QB-1")
    make_inventory(store_a, v, 3)
    sync_svc.confirm_inventory_push(
        db_session, store_id=store_a.id, actor_user_id=None
    )

    rows_a, total_a = sync_svc.list_sync_runs(db_session, store_id=store_a.id)
    assert total_a == 1
    assert all(r.store_id == store_a.id for r in rows_a)
    rows_b, total_b = sync_svc.list_sync_runs(db_session, store_id=store_b.id)
    assert total_b == 0
    assert rows_b == []


def test_get_sync_run_detail_returns_items(
    db_session, make_store, make_variant, make_integration, make_mapping,
    make_inventory, fake_qb,
) -> None:
    store = make_store()
    integ = make_integration(store)
    v = make_variant()
    make_mapping(integ, v, external_item_id="QB-1")
    make_inventory(store, v, 11)
    log, _ = sync_svc.confirm_inventory_push(
        db_session, store_id=store.id, actor_user_id=None
    )

    detail_log, detail_items = sync_svc.get_sync_run_detail(
        db_session, run_id=log.id
    )
    assert detail_log.id == log.id
    assert len(detail_items) == 1
    assert detail_items[0].outcome == "updated"


def test_get_sync_run_detail_unknown_is_404(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        sync_svc.get_sync_run_detail(db_session, run_id=uuid.uuid4())
    assert exc.value.status_code == 404
