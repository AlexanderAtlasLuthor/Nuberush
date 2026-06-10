"""DB-level model + constraint tests for the accounting foundation (F2.27.9.A).

Exercises the persisted QuickBooks/accounting storage against the real
(migrated) Postgres test database:
  - an integration / mapping / sync-log / sync-log-item each insert and link;
  - provider / status / environment / sync_type / direction / trigger / outcome
    CHECK constraints reject bad values;
  - UNIQUE(store_id, provider), UNIQUE(integration_id, variant_id) and
    UNIQUE(integration_id, external_item_id) are enforced;
  - sync-log counters default to 0;
  - NO table carries a plaintext token / secret / raw-payload column — the only
    token columns are `access_token_encrypted` / `refresh_token_encrypted`;
  - the read schemas never expose the encrypted token columns;
  - an encrypted token round-trips through the integration row;
  - deleting an integration cascades to mappings, sync logs and their items;
  - the Supabase deny-all RLS migration exists for all four tables.

Style mirrors tests/test_regulatory_ingestion_models.py (local make_* helpers
over the transactional db_session, IntegrityError for DB constraints). This
subphase ships storage only: no OAuth flow, client, mapping service, sync
orchestrator, scheduler, or route is involved, and nothing here mutates
inventory, products, or compliance.
"""
from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_quickbooks_settings
from app.core.encryption import decrypt_token
from app.core.encryption import encrypt_token
from app.db.models import AccountingSyncLog
from app.db.models import AccountingSyncLogItem
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import ProductVariantAccountingMapping
from app.db.models import Store
from app.db.models import StoreAccountingIntegration
from app.db.models import User
from app.db.models import UserRole
from app.schemas.accounting import AccountingSyncLogItemRead
from app.schemas.accounting import AccountingSyncLogRead
from app.schemas.accounting import ProductVariantAccountingMappingRead
from app.schemas.accounting import StoreAccountingIntegrationRead
from tests.helpers.auth import make_user as central_make_user


# Column names that must NEVER exist on any accounting table: plaintext token
# material, secrets, auth headers, and raw external payloads/bodies. Note the
# legitimate token columns are the *_encrypted variants, which are NOT in this
# set, so an exact-name disjointness check is correct.
FORBIDDEN_COLUMN_NAMES = {
    "raw_payload",
    "payload",
    "raw_body",
    "body",
    "raw",
    "request_body",
    "response_body",
    "secret",
    "client_secret",
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "plaintext_token",
    "authorization",
    "authorization_header",
    "auth_header",
    "credentials",
}


# --------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(**over) -> Store:
        store = Store(
            name=over.get("name", "Acct-QA"),
            code=over.get("code", f"acct-{uuid.uuid4().hex[:8]}"),
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_variant(db_session: Session) -> Callable[..., ProductVariant]:
    def _create(**over) -> ProductVariant:
        product = Product(
            name=over.get("product_name", "Acct Product"),
            category=over.get("category", "vape"),
        )
        db_session.add(product)
        db_session.flush()
        variant = ProductVariant(
            product_id=product.id,
            sku=over.get("sku", f"SKU-{uuid.uuid4().hex[:10]}"),
            price=over.get("price", Decimal("9.99")),
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def admin(db_session: Session) -> User:
    return central_make_user(db_session, role=UserRole.admin)


@pytest.fixture
def make_integration(
    db_session: Session, make_store: Callable[..., Store]
) -> Callable[..., StoreAccountingIntegration]:
    def _create(store: Store | None = None, **over) -> StoreAccountingIntegration:
        store = store or make_store()
        integration = StoreAccountingIntegration(
            store_id=store.id,
            **{
                key: over[key]
                for key in (
                    "provider",
                    "status",
                    "environment",
                    "realm_id",
                    "access_token_encrypted",
                    "refresh_token_encrypted",
                    "scopes",
                    "connected_by_user_id",
                )
                if key in over
            },
        )
        db_session.add(integration)
        db_session.commit()
        db_session.refresh(integration)
        return integration

    return _create


@pytest.fixture
def make_sync_log(
    db_session: Session,
) -> Callable[..., AccountingSyncLog]:
    def _create(
        integration: StoreAccountingIntegration, **over
    ) -> AccountingSyncLog:
        log = AccountingSyncLog(
            store_id=integration.store_id,
            integration_id=integration.id,
            sync_type=over.get("sync_type", "inventory_push"),
            direction=over.get("direction", "push"),
            status=over.get("status", "running"),
            trigger=over.get("trigger", "manual"),
            started_at=over.get("started_at", datetime.now(UTC)),
            **{
                key: over[key]
                for key in (
                    "finished_at",
                    "items_seen",
                    "items_created",
                    "items_updated",
                    "items_skipped",
                    "items_failed",
                    "error_summary",
                    "actor_user_id",
                )
                if key in over
            },
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        return log

    return _create


@pytest.fixture
def with_encryption_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("QUICKBOOKS_TOKEN_ENCRYPTION_KEY", key)
    get_quickbooks_settings.cache_clear()
    try:
        yield key
    finally:
        get_quickbooks_settings.cache_clear()


# --------------------------------------------------------------------- #
# 1. Rows persist + defaults
# --------------------------------------------------------------------- #


def test_integration_persists_with_safe_defaults(
    make_integration: Callable[..., StoreAccountingIntegration],
) -> None:
    integration = make_integration()

    assert integration.id is not None
    # Server defaults make a fresh row safe + unconnected.
    assert integration.provider == "quickbooks"
    assert integration.status == "disconnected"
    assert integration.environment == "sandbox"
    # No token material on a fresh row.
    assert integration.access_token_encrypted is None
    assert integration.refresh_token_encrypted is None
    assert integration.realm_id is None
    assert isinstance(integration.created_at, datetime)
    assert isinstance(integration.updated_at, datetime)


def test_integration_links_to_store_and_user(
    make_store: Callable[..., Store],
    make_integration: Callable[..., StoreAccountingIntegration],
    admin: User,
) -> None:
    store = make_store()
    integration = make_integration(store, connected_by_user_id=admin.id)

    assert integration.store_id == store.id
    assert integration.store is store
    assert integration.connected_by_user_id == admin.id
    assert integration.connected_by_user is admin


def test_mapping_persists_and_links(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    make_variant: Callable[..., ProductVariant],
) -> None:
    integration = make_integration()
    variant = make_variant()
    mapping = ProductVariantAccountingMapping(
        integration_id=integration.id,
        store_id=integration.store_id,
        variant_id=variant.id,
        external_item_id="QB-ITEM-1",
        external_item_name="Widget",
    )
    db_session.add(mapping)
    db_session.commit()
    db_session.refresh(mapping)

    assert mapping.id is not None
    assert mapping.provider == "quickbooks"
    assert mapping.sync_enabled is True
    assert mapping.integration is integration
    assert mapping.variant is variant
    db_session.refresh(integration)
    assert mapping in integration.mappings


def test_sync_log_persists_and_links(
    make_integration: Callable[..., StoreAccountingIntegration],
    make_sync_log: Callable[..., AccountingSyncLog],
    admin: User,
) -> None:
    integration = make_integration()
    log = make_sync_log(integration, actor_user_id=admin.id)

    assert log.id is not None
    assert log.integration is integration
    assert log.store_id == integration.store_id
    assert log.actor_user_id == admin.id


def test_sync_log_item_persists_and_links(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    make_sync_log: Callable[..., AccountingSyncLog],
) -> None:
    integration = make_integration()
    log = make_sync_log(integration)
    item = AccountingSyncLogItem(
        sync_log_id=log.id,
        external_item_id="QB-ITEM-9",
        external_item_name="Gadget",
        outcome="created",
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.id is not None
    assert item.sync_log is log
    # variant_id is optional on a discovery/inbound item.
    assert item.variant_id is None
    db_session.refresh(log)
    assert item in log.items


# --------------------------------------------------------------------- #
# 2. Valid discriminator values persist
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "status", ["connected", "disconnected", "expired", "error"]
)
def test_valid_integration_status_persists(
    make_integration: Callable[..., StoreAccountingIntegration],
    status: str,
) -> None:
    integration = make_integration(status=status)
    assert integration.status == status


@pytest.mark.parametrize("environment", ["sandbox", "production"])
def test_valid_integration_environment_persists(
    make_integration: Callable[..., StoreAccountingIntegration],
    environment: str,
) -> None:
    integration = make_integration(environment=environment)
    assert integration.environment == environment


@pytest.mark.parametrize(
    "sync_type", ["item_discovery", "mapping_pull", "inventory_push"]
)
@pytest.mark.parametrize("direction", ["pull", "push"])
def test_valid_sync_type_and_direction_persist(
    make_integration: Callable[..., StoreAccountingIntegration],
    make_sync_log: Callable[..., AccountingSyncLog],
    sync_type: str,
    direction: str,
) -> None:
    integration = make_integration()
    log = make_sync_log(integration, sync_type=sync_type, direction=direction)
    assert log.sync_type == sync_type
    assert log.direction == direction


@pytest.mark.parametrize("outcome", ["created", "updated", "skipped", "failed"])
def test_valid_item_outcome_persists(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    make_sync_log: Callable[..., AccountingSyncLog],
    outcome: str,
) -> None:
    integration = make_integration()
    log = make_sync_log(integration)
    item = AccountingSyncLogItem(sync_log_id=log.id, outcome=outcome)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    assert item.outcome == outcome


# --------------------------------------------------------------------- #
# 3. Invalid discriminator values rejected by CHECK constraints
# --------------------------------------------------------------------- #


def test_invalid_provider_rejected(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store()
    db_session.add(
        StoreAccountingIntegration(store_id=store.id, provider="xero")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_status_rejected(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store()
    db_session.add(
        StoreAccountingIntegration(store_id=store.id, status="pending")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_environment_rejected(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store()
    db_session.add(
        StoreAccountingIntegration(store_id=store.id, environment="staging")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "field,value",
    [
        ("sync_type", "full_export"),
        ("direction", "both"),
        ("status", "done"),
        ("trigger", "webhook"),
    ],
)
def test_invalid_sync_log_discriminators_rejected(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    field: str,
    value: str,
) -> None:
    integration = make_integration()
    kwargs = dict(
        store_id=integration.store_id,
        integration_id=integration.id,
        sync_type="inventory_push",
        direction="push",
        status="running",
        trigger="manual",
        started_at=datetime.now(UTC),
    )
    kwargs[field] = value
    db_session.add(AccountingSyncLog(**kwargs))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_negative_sync_log_counter_rejected(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
) -> None:
    integration = make_integration()
    db_session.add(
        AccountingSyncLog(
            store_id=integration.store_id,
            integration_id=integration.id,
            sync_type="inventory_push",
            direction="push",
            status="running",
            trigger="manual",
            started_at=datetime.now(UTC),
            items_failed=-1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_item_outcome_rejected(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    make_sync_log: Callable[..., AccountingSyncLog],
) -> None:
    integration = make_integration()
    log = make_sync_log(integration)
    db_session.add(
        AccountingSyncLogItem(sync_log_id=log.id, outcome="deduped")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# 4. Unique constraints
# --------------------------------------------------------------------- #


def test_unique_store_provider_enforced(
    db_session: Session,
    make_store: Callable[..., Store],
    make_integration: Callable[..., StoreAccountingIntegration],
) -> None:
    store = make_store()
    make_integration(store)  # first quickbooks integration for the store
    db_session.add(
        StoreAccountingIntegration(store_id=store.id, provider="quickbooks")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_integration_variant_enforced(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    make_variant: Callable[..., ProductVariant],
) -> None:
    integration = make_integration()
    variant = make_variant()
    db_session.add(
        ProductVariantAccountingMapping(
            integration_id=integration.id,
            store_id=integration.store_id,
            variant_id=variant.id,
            external_item_id="QB-A",
        )
    )
    db_session.commit()

    # Same (integration, variant) again — even with a different external item.
    db_session.add(
        ProductVariantAccountingMapping(
            integration_id=integration.id,
            store_id=integration.store_id,
            variant_id=variant.id,
            external_item_id="QB-B",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_integration_external_item_enforced(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    make_variant: Callable[..., ProductVariant],
) -> None:
    integration = make_integration()
    variant_a = make_variant()
    variant_b = make_variant()
    db_session.add(
        ProductVariantAccountingMapping(
            integration_id=integration.id,
            store_id=integration.store_id,
            variant_id=variant_a.id,
            external_item_id="QB-SAME",
        )
    )
    db_session.commit()

    # Different variant, same external item id within the integration.
    db_session.add(
        ProductVariantAccountingMapping(
            integration_id=integration.id,
            store_id=integration.store_id,
            variant_id=variant_b.id,
            external_item_id="QB-SAME",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# 5. Counter defaults
# --------------------------------------------------------------------- #


def test_sync_log_counters_default_to_zero(
    make_integration: Callable[..., StoreAccountingIntegration],
    make_sync_log: Callable[..., AccountingSyncLog],
) -> None:
    integration = make_integration()
    log = make_sync_log(integration)  # no counters passed -> server defaults
    assert log.items_seen == 0
    assert log.items_created == 0
    assert log.items_updated == 0
    assert log.items_skipped == 0
    assert log.items_failed == 0
    assert log.finished_at is None
    assert log.error_summary is None


# --------------------------------------------------------------------- #
# 6. No plaintext token / secret / raw-payload columns anywhere
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "model",
    [
        StoreAccountingIntegration,
        ProductVariantAccountingMapping,
        AccountingSyncLog,
        AccountingSyncLogItem,
    ],
)
def test_no_forbidden_columns(model: type) -> None:
    columns = set(model.__table__.columns.keys())
    assert columns.isdisjoint(FORBIDDEN_COLUMN_NAMES)


def test_integration_token_columns_are_encrypted_only() -> None:
    columns = set(StoreAccountingIntegration.__table__.columns.keys())
    # The ONLY columns holding token *material* are the encrypted ones. The
    # `*_expires_at` columns also contain the substring "token" but are plain
    # timestamps, so they are excluded from the material check.
    token_material_columns = {
        c for c in columns if "token" in c and not c.endswith("_expires_at")
    }
    assert token_material_columns == {
        "access_token_encrypted",
        "refresh_token_encrypted",
    }
    # And no plaintext-token column slipped in.
    assert "access_token" not in columns
    assert "refresh_token" not in columns


# --------------------------------------------------------------------- #
# 7. Read schemas never expose encrypted tokens / secrets
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "schema",
    [
        StoreAccountingIntegrationRead,
        ProductVariantAccountingMappingRead,
        AccountingSyncLogRead,
        AccountingSyncLogItemRead,
    ],
)
def test_read_schemas_do_not_expose_secrets(schema: type) -> None:
    fields = set(schema.model_fields)
    assert "access_token_encrypted" not in fields
    assert "refresh_token_encrypted" not in fields
    assert fields.isdisjoint(FORBIDDEN_COLUMN_NAMES)


def test_integration_read_schema_hydrates_without_tokens(
    make_store: Callable[..., Store],
    make_integration: Callable[..., StoreAccountingIntegration],
    with_encryption_key: str,
) -> None:
    store = make_store()
    integration = make_integration(
        store,
        status="connected",
        realm_id="123456789",
        access_token_encrypted=encrypt_token("access-secret"),
        refresh_token_encrypted=encrypt_token("refresh-secret"),
        scopes="com.intuit.quickbooks.accounting",
    )
    read = StoreAccountingIntegrationRead.model_validate(integration)
    dumped = read.model_dump()

    assert read.status.value == "connected"
    assert read.realm_id == "123456789"
    # No token material in the serialized projection.
    assert "access_token_encrypted" not in dumped
    assert "refresh_token_encrypted" not in dumped
    assert "access-secret" not in str(dumped)
    assert "refresh-secret" not in str(dumped)


# --------------------------------------------------------------------- #
# 8. Encrypted token round-trips through the DB row
# --------------------------------------------------------------------- #


def test_encrypted_token_round_trips_in_db(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    with_encryption_key: str,
) -> None:
    secret = "qb-refresh-token-abc-123"
    integration = make_integration()
    integration.access_token_encrypted = encrypt_token(secret)
    db_session.commit()
    db_session.refresh(integration)

    # What is stored is ciphertext, not the plaintext.
    assert integration.access_token_encrypted != secret
    assert secret not in integration.access_token_encrypted
    # And it decrypts back to the original.
    assert decrypt_token(integration.access_token_encrypted) == secret


# --------------------------------------------------------------------- #
# 9. Cascade delete: integration -> mappings + sync logs -> items
# --------------------------------------------------------------------- #


def test_deleting_integration_cascades(
    db_session: Session,
    make_integration: Callable[..., StoreAccountingIntegration],
    make_sync_log: Callable[..., AccountingSyncLog],
    make_variant: Callable[..., ProductVariant],
) -> None:
    integration = make_integration()
    variant = make_variant()
    mapping = ProductVariantAccountingMapping(
        integration_id=integration.id,
        store_id=integration.store_id,
        variant_id=variant.id,
        external_item_id="QB-CASCADE",
    )
    db_session.add(mapping)
    log = make_sync_log(integration)
    item = AccountingSyncLogItem(sync_log_id=log.id, outcome="created")
    db_session.add(item)
    db_session.commit()

    mapping_id, log_id, item_id = mapping.id, log.id, item.id

    db_session.delete(integration)
    db_session.commit()

    assert (
        db_session.scalar(
            select(ProductVariantAccountingMapping).where(
                ProductVariantAccountingMapping.id == mapping_id
            )
        )
        is None
    )
    assert (
        db_session.scalar(
            select(AccountingSyncLog).where(AccountingSyncLog.id == log_id)
        )
        is None
    )
    assert (
        db_session.scalar(
            select(AccountingSyncLogItem).where(
                AccountingSyncLogItem.id == item_id
            )
        )
        is None
    )


# --------------------------------------------------------------------- #
# 10. Supabase deny-all RLS migration exists for all four tables
# --------------------------------------------------------------------- #


def test_rls_deny_all_migration_exists_for_accounting_tables() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    migrations_dir = repo_root / "supabase" / "migrations"
    matches = list(migrations_dir.glob("*_accounting_integrations_rls.sql"))
    assert matches, "accounting RLS deny-all migration is missing"

    sql = matches[0].read_text()
    tables = (
        "store_accounting_integrations",
        "product_variant_accounting_mappings",
        "accounting_sync_logs",
        "accounting_sync_log_items",
    )
    for table in tables:
        assert (
            f"ALTER TABLE public.{table}" in sql
        ), f"{table} not toggled in RLS migration"
    # Look only at executable SQL — drop comment lines so a "-- No CREATE
    # POLICY ..." note or aligned-whitespace formatting doesn't trip the guards.
    executable = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    collapsed = " ".join(executable.split())  # normalize runs of whitespace
    # Every accounting table is ENABLE + FORCE, and no positive policy exists.
    assert collapsed.count("ENABLE ROW LEVEL SECURITY") >= len(tables)
    assert collapsed.count("FORCE ROW LEVEL SECURITY") >= len(tables)
    assert "CREATE POLICY" not in executable
