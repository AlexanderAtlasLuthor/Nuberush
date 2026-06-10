"""API-level tests for the admin QuickBooks OAuth routes (F2.27.9.B).

Exercises connect / callback / disconnect / integration-status via the FastAPI
TestClient:
  - admin-only RBAC on connect/disconnect/status (non-admin 403, anon 401);
  - the callback is unauthenticated-but-state-verified (Intuit redirect): it
    rejects missing/invalid params and persists ENCRYPTED tokens only;
  - NO response exposes token material / ciphertext / secrets;
  - NO mapping / item-discovery / sync routes exist yet.

The QuickBooks client is replaced by a fake (monkeypatched factory) — NO real
network, NO real credentials.
"""
from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_quickbooks_settings
from app.core.encryption import decrypt_token
from app.core.encryption import encrypt_token
from app.db.models import AccountingSyncLog
from app.db.models import InventoryItem
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import StoreAccountingIntegration
from app.db.models import User
from app.db.models import UserRole
from app.services.accounting import oauth as oauth_svc
from app.services.accounting.quickbooks_client import QuickBooksClientError
from app.services.accounting.quickbooks_client import (
    QuickBooksItemQuantityUpdateResult,
)
from app.services.accounting.quickbooks_client import QuickBooksItemSummary
from app.services.accounting.quickbooks_client import TokenResult
from cryptography.fernet import Fernet
from decimal import Decimal
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


CONNECT = "/admin/stores/{sid}/accounting/quickbooks/connect"
DISCONNECT = "/admin/stores/{sid}/accounting/quickbooks/disconnect"
INTEGRATION = "/admin/stores/{sid}/accounting/quickbooks/integration"
CALLBACK = "/admin/accounting/quickbooks/callback"
ITEMS = "/admin/stores/{sid}/accounting/quickbooks/items"
MAPPINGS = "/admin/stores/{sid}/accounting/quickbooks/mappings"
MAPPING = "/admin/stores/{sid}/accounting/quickbooks/mappings/{mid}"
PREVIEW = "/admin/stores/{sid}/accounting/quickbooks/sync/preview"
CONFIRM = "/admin/stores/{sid}/accounting/quickbooks/sync/confirm"
SYNC_RUNS = "/admin/stores/{sid}/accounting/quickbooks/sync-runs"
SYNC_RUN_DETAIL = "/admin/accounting/sync-runs/{rid}"

_TOKEN_LEAK_KEYS = {
    "access_token",
    "refresh_token",
    "access_token_encrypted",
    "refresh_token_encrypted",
    "client_secret",
    "code",
    "state",
    "authorization",
}
_TOKEN_LEAK_VALUES = ("ACCESS-PLAINTEXT", "REFRESH-PLAINTEXT")


class FakeQuickBooksClient:
    def __init__(self) -> None:
        self.revoked: list[str] = []
        self.pushed: list[tuple[str, float]] = []
        self.fail_ids: set[str] = set()

    def exchange_code(self, *, code, redirect_uri=None) -> TokenResult:
        now = datetime.now(UTC)
        return TokenResult(
            access_token="ACCESS-PLAINTEXT",
            refresh_token="REFRESH-PLAINTEXT",
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now + timedelta(days=100),
            scopes="com.intuit.quickbooks.accounting",
            token_type="bearer",
        )

    def revoke_token(self, *, token) -> None:
        self.revoked.append(token)

    def list_items(self, *, access_token, realm_id, environment, max_items):
        return [
            QuickBooksItemSummary(
                external_item_id="QB-1",
                name="Widget",
                sku="W-1",
                description="A widget",
                unit_price=9.99,
                purchase_cost=4.5,
                quantity_on_hand=12.0,
            )
        ]

    def update_item_quantity(
        self,
        *,
        access_token,
        realm_id,
        external_item_id,
        quantity_on_hand,
        environment="sandbox",
        **_,
    ) -> QuickBooksItemQuantityUpdateResult:
        self.pushed.append((external_item_id, quantity_on_hand))
        if external_item_id in self.fail_ids:
            raise QuickBooksClientError(
                "QuickBooks item update was rejected (status 400)."
            )
        # The echoed 999 is informational — the service must NEVER write it back
        # into NubeRush inventory.
        return QuickBooksItemQuantityUpdateResult(
            external_item_id=external_item_id,
            pushed_quantity=float(quantity_on_hand),
            quickbooks_quantity_on_hand=999.0,
            sync_token="1",
            attempts=1,
        )


def _assert_no_token_leak(payload) -> None:
    """Recursively assert no token/secret keys or known plaintext values."""
    text = str(payload)
    for v in _TOKEN_LEAK_VALUES:
        assert v not in text, f"plaintext token leaked: {v}"

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k.lower() not in _TOKEN_LEAK_KEYS, f"leak key: {k}"
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(payload)


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def qb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUICKBOOKS_CLIENT_ID", "cid")
    monkeypatch.setenv("QUICKBOOKS_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("QUICKBOOKS_REDIRECT_URL", "https://app.example/cb")
    monkeypatch.setenv("QUICKBOOKS_ENVIRONMENT", "sandbox")
    monkeypatch.setenv(
        "QUICKBOOKS_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )
    monkeypatch.setenv("QUICKBOOKS_OAUTH_STATE_SECRET", "state-secret")
    monkeypatch.setenv("QUICKBOOKS_OAUTH_STATE_TTL_SECONDS", "600")
    get_quickbooks_settings.cache_clear()
    yield
    get_quickbooks_settings.cache_clear()


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeQuickBooksClient:
    fake = FakeQuickBooksClient()
    monkeypatch.setattr(oauth_svc, "resolve_quickbooks_client", lambda: fake)
    return fake


@pytest.fixture
def store(db_session: Session) -> Store:
    s = Store(name="QB API Store", code=f"qa-{uuid.uuid4().hex[:8]}")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def admin(db_session: Session) -> User:
    return central_make_user(db_session, role=UserRole.admin)


# --------------------------------------------------------------------- #
# RBAC — admin-only on connect / disconnect / status
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
)
def test_connect_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store, role: UserRole
) -> None:
    user = central_make_user(db_session, role=role, store_id=store.id)
    resp = client.post(CONNECT.format(sid=store.id), headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_connect_unauthenticated_is_401(
    client: TestClient, store: Store
) -> None:
    resp = client.post(CONNECT.format(sid=store.id))
    assert resp.status_code == 401, resp.text


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
)
def test_disconnect_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store, role: UserRole
) -> None:
    user = central_make_user(db_session, role=role, store_id=store.id)
    resp = client.post(DISCONNECT.format(sid=store.id), headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_integration_status_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store
) -> None:
    owner = central_make_user(db_session, role=UserRole.owner, store_id=store.id)
    resp = client.get(INTEGRATION.format(sid=store.id), headers=_auth(owner))
    assert resp.status_code == 403, resp.text


def test_integration_status_unauthenticated_is_401(
    client: TestClient, store: Store
) -> None:
    resp = client.get(INTEGRATION.format(sid=store.id))
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------- #
# Connect
# --------------------------------------------------------------------- #


def test_connect_returns_authorize_url(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
) -> None:
    resp = client.post(CONNECT.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["authorize_url"].startswith(
        "https://appcenter.intuit.com/connect/oauth2?"
    )
    assert data["provider"] == "quickbooks"
    assert data["store_id"] == str(store.id)
    _assert_no_token_leak(data)
    # No token DB row is written during connect.
    count = db_session.scalar(
        select(func.count())
        .select_from(StoreAccountingIntegration)
        .where(StoreAccountingIntegration.store_id == store.id)
    )
    assert count == 0


def test_connect_validates_store_exists(
    client: TestClient, qb_env: None, admin: User
) -> None:
    resp = client.post(
        CONNECT.format(sid=uuid.uuid4()), headers=_auth(admin)
    )
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------- #
# Callback
# --------------------------------------------------------------------- #


def test_callback_rejects_missing_params(
    client: TestClient, qb_env: None
) -> None:
    # No code/state/realmId at all.
    assert client.get(CALLBACK).status_code == 400
    # Missing realmId.
    assert (
        client.get(CALLBACK, params={"code": "c", "state": "s"}).status_code
        == 400
    )
    # Missing code.
    assert (
        client.get(
            CALLBACK, params={"state": "s", "realmId": "R"}
        ).status_code
        == 400
    )


def test_callback_rejects_invalid_state(
    client: TestClient, qb_env: None, fake_client: FakeQuickBooksClient
) -> None:
    resp = client.get(
        CALLBACK,
        params={"code": "c", "state": "forged.state", "realmId": "R"},
    )
    assert resp.status_code == 400, resp.text


def test_callback_success_persists_encrypted_tokens_only(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    resp = client.get(
        CALLBACK,
        params={"code": "auth-code", "state": state, "realmId": "REALM-1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["connected"] is True
    assert data["status"] == "connected"
    assert data["realm_id"] == "REALM-1"
    assert data["store_id"] == str(store.id)
    _assert_no_token_leak(data)

    # DB row holds ciphertext only (decryptable back to the plaintext).
    integration = db_session.scalar(
        select(StoreAccountingIntegration).where(
            StoreAccountingIntegration.store_id == store.id
        )
    )
    assert integration is not None
    enc = integration.access_token_encrypted
    assert enc and enc != "ACCESS-PLAINTEXT"
    assert decrypt_token(enc) == "ACCESS-PLAINTEXT"
    assert integration.connected_by_user_id == admin.id


def test_callback_does_not_trust_query_store_id(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    other = Store(name="Other", code=f"ot-{uuid.uuid4().hex[:8]}")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    # State binds the REAL store; a spoofed store_id query param is ignored.
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    resp = client.get(
        CALLBACK,
        params={
            "code": "c",
            "state": state,
            "realmId": "R",
            "store_id": str(other.id),  # attacker-controlled, must be ignored
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["store_id"] == str(store.id)
    # No integration landed on the spoofed store.
    spoofed = db_session.scalar(
        select(StoreAccountingIntegration).where(
            StoreAccountingIntegration.store_id == other.id
        )
    )
    assert spoofed is None


# --------------------------------------------------------------------- #
# Disconnect
# --------------------------------------------------------------------- #


def test_disconnect_nulls_tokens_and_hides_material(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    # Connect first via the service, then disconnect via the API.
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    oauth_svc.exchange_callback_code(
        db_session, code="c", realm_id="R", state=state
    )

    resp = client.post(DISCONNECT.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "disconnected"
    assert data["connected"] is False
    assert data["disconnected_at"] is not None
    _assert_no_token_leak(data)

    db_session.expire_all()
    integration = db_session.scalar(
        select(StoreAccountingIntegration).where(
            StoreAccountingIntegration.store_id == store.id
        )
    )
    assert integration.access_token_encrypted is None
    assert integration.refresh_token_encrypted is None


def test_disconnect_missing_integration_is_404(
    client: TestClient, qb_env: None, store: Store, admin: User
) -> None:
    resp = client.post(DISCONNECT.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------- #
# Integration status
# --------------------------------------------------------------------- #


def test_integration_status_absent_is_disconnected(
    client: TestClient, store: Store, admin: User
) -> None:
    resp = client.get(INTEGRATION.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["connected"] is False
    assert data["status"] == "disconnected"
    assert data["integration_id"] is None
    _assert_no_token_leak(data)


def test_integration_status_present_is_connected(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    oauth_svc.exchange_callback_code(
        db_session, code="c", realm_id="REALM-7", state=state
    )
    resp = client.get(INTEGRATION.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["connected"] is True
    assert data["status"] == "connected"
    assert data["realm_id"] == "REALM-7"
    _assert_no_token_leak(data)


# --------------------------------------------------------------------- #
# Scope guard: no mapping / discovery / sync routes exist yet
# --------------------------------------------------------------------- #


# ===================================================================== #
# F2.27.9.C — item discovery + mapping API
# ===================================================================== #


@pytest.fixture
def connected_integration(
    db_session: Session, qb_env: None, store: Store
) -> StoreAccountingIntegration:
    integ = StoreAccountingIntegration(
        store_id=store.id,
        provider="quickbooks",
        status="connected",
        environment="sandbox",
        realm_id="REALM-1",
        access_token_encrypted=encrypt_token("AT"),
        refresh_token_encrypted=encrypt_token("RT"),
    )
    db_session.add(integ)
    db_session.commit()
    db_session.refresh(integ)
    return integ


@pytest.fixture
def variant(db_session: Session) -> ProductVariant:
    product = Product(name="API Product", category="vape")
    db_session.add(product)
    db_session.flush()
    v = ProductVariant(
        product_id=product.id,
        sku=f"SKU-{uuid.uuid4().hex[:10]}",
        price=Decimal("9.99"),
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


# --- RBAC: items / mappings are admin-only --------------------------------- #


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
)
def test_items_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store, role: UserRole
) -> None:
    user = central_make_user(db_session, role=role, store_id=store.id)
    resp = client.get(ITEMS.format(sid=store.id), headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_items_unauthenticated_is_401(client: TestClient, store: Store) -> None:
    assert client.get(ITEMS.format(sid=store.id)).status_code == 401


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
)
def test_mappings_list_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store, role: UserRole
) -> None:
    user = central_make_user(db_session, role=role, store_id=store.id)
    resp = client.get(MAPPINGS.format(sid=store.id), headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_mappings_post_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store
) -> None:
    owner = central_make_user(db_session, role=UserRole.owner, store_id=store.id)
    resp = client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(owner),
        json={"variant_id": str(uuid.uuid4()), "external_item_id": "QB-1"},
    )
    assert resp.status_code == 403, resp.text


def test_mappings_patch_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store
) -> None:
    owner = central_make_user(db_session, role=UserRole.owner, store_id=store.id)
    resp = client.patch(
        MAPPING.format(sid=store.id, mid=uuid.uuid4()),
        headers=_auth(owner),
        json={"sync_enabled": False},
    )
    assert resp.status_code == 403, resp.text


def test_mappings_post_unauthenticated_is_401(
    client: TestClient, store: Store
) -> None:
    resp = client.post(
        MAPPINGS.format(sid=store.id),
        json={"variant_id": str(uuid.uuid4()), "external_item_id": "QB-1"},
    )
    assert resp.status_code == 401, resp.text


# --- Item discovery -------------------------------------------------------- #


def test_get_items_returns_safe_summaries(
    client: TestClient,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    fake_client: FakeQuickBooksClient,
) -> None:
    resp = client.get(ITEMS.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["external_item_id"] == "QB-1"
    assert item["name"] == "Widget"
    assert set(item.keys()) == {
        "external_item_id", "name", "sku", "description",
        "unit_price", "purchase_cost", "quantity_on_hand",
    }
    _assert_no_token_leak(data)


def test_get_items_without_integration_is_404(
    client: TestClient, qb_env: None, store: Store, admin: User
) -> None:
    resp = client.get(ITEMS.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 404, resp.text


# --- Mapping create / list / update --------------------------------------- #


def test_create_and_list_mapping(
    client: TestClient,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    variant: ProductVariant,
) -> None:
    resp = client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={
            "variant_id": str(variant.id),
            "external_item_id": "QB-100",
            "external_item_name": "Mapped Widget",
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["variant_id"] == str(variant.id)
    assert created["external_item_id"] == "QB-100"
    assert created["sync_enabled"] is True
    _assert_no_token_leak(created)

    listing = client.get(MAPPINGS.format(sid=store.id), headers=_auth(admin))
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["external_item_id"] == "QB-100"
    _assert_no_token_leak(body)


def test_patch_mapping_updates(
    client: TestClient,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    variant: ProductVariant,
) -> None:
    created = client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={"variant_id": str(variant.id), "external_item_id": "QB-1"},
    ).json()
    resp = client.patch(
        MAPPING.format(sid=store.id, mid=created["id"]),
        headers=_auth(admin),
        json={"external_item_name": "Renamed", "sync_enabled": False},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["external_item_name"] == "Renamed"
    assert data["sync_enabled"] is False
    _assert_no_token_leak(data)


def test_create_mapping_invalid_variant_is_422(
    client: TestClient,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
) -> None:
    resp = client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={"variant_id": str(uuid.uuid4()), "external_item_id": "QB-1"},
    )
    assert resp.status_code == 422, resp.text


def test_store_a_cannot_update_store_b_mapping(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    variant: ProductVariant,
) -> None:
    # Mapping created in store A.
    created = client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={"variant_id": str(variant.id), "external_item_id": "QB-A"},
    ).json()

    # Store B (separate, connected) tries to PATCH store A's mapping by id.
    store_b = Store(name="B", code=f"b-{uuid.uuid4().hex[:8]}")
    db_session.add(store_b)
    db_session.commit()
    db_session.refresh(store_b)
    db_session.add(
        StoreAccountingIntegration(
            store_id=store_b.id, provider="quickbooks", status="connected",
            environment="sandbox", realm_id="R2",
            access_token_encrypted=encrypt_token("AT2"),
        )
    )
    db_session.commit()

    resp = client.patch(
        MAPPING.format(sid=store_b.id, mid=created["id"]),
        headers=_auth(admin),
        json={"sync_enabled": False},
    )
    assert resp.status_code == 404, resp.text
    # And store B's mapping listing does not include store A's mapping.
    listing = client.get(MAPPINGS.format(sid=store_b.id), headers=_auth(admin)).json()
    assert listing["total"] == 0


# ===================================================================== #
# F2.27.9.D — inventory push preview + confirm + sync-run ledger API
# ===================================================================== #


def _push_inventory(db_session: Session, store: Store, variant: ProductVariant,
                    quantity: int) -> InventoryItem:
    item = InventoryItem(
        store_id=store.id, variant_id=variant.id, quantity_on_hand=quantity
    )
    db_session.add(item)
    db_session.commit()
    return item


# --- RBAC: all four D routes are admin-only ------------------------------- #


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
)
def test_sync_preview_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store, role: UserRole
) -> None:
    user = central_make_user(db_session, role=role, store_id=store.id)
    resp = client.post(PREVIEW.format(sid=store.id), headers=_auth(user))
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
)
def test_sync_confirm_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store, role: UserRole
) -> None:
    user = central_make_user(db_session, role=role, store_id=store.id)
    resp = client.post(CONFIRM.format(sid=store.id), headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_sync_runs_forbidden_for_non_admin(
    client: TestClient, db_session: Session, store: Store
) -> None:
    owner = central_make_user(db_session, role=UserRole.owner, store_id=store.id)
    resp = client.get(SYNC_RUNS.format(sid=store.id), headers=_auth(owner))
    assert resp.status_code == 403, resp.text


def test_sync_run_detail_forbidden_for_non_admin(
    client: TestClient, db_session: Session
) -> None:
    owner = central_make_user(db_session, role=UserRole.owner)
    resp = client.get(
        SYNC_RUN_DETAIL.format(rid=uuid.uuid4()), headers=_auth(owner)
    )
    assert resp.status_code == 403, resp.text


def test_sync_routes_unauthenticated_are_401(
    client: TestClient, store: Store
) -> None:
    assert client.post(PREVIEW.format(sid=store.id)).status_code == 401
    assert client.post(CONFIRM.format(sid=store.id)).status_code == 401
    assert client.get(SYNC_RUNS.format(sid=store.id)).status_code == 401
    assert (
        client.get(SYNC_RUN_DETAIL.format(rid=uuid.uuid4())).status_code == 401
    )


# --- Preview (no write) --------------------------------------------------- #


def test_preview_returns_safe_proposed_pushes(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    variant: ProductVariant,
    fake_client: FakeQuickBooksClient,
) -> None:
    client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={"variant_id": str(variant.id), "external_item_id": "QB-1"},
    )
    _push_inventory(db_session, store, variant, 12)

    resp = client.post(PREVIEW.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_mappings"] == 1
    assert data["items_to_push"] == 1
    item = data["items"][0]
    assert item["external_item_id"] == "QB-1"
    assert item["nube_quantity_on_hand"] == 12
    assert item["proposed_action"] == "push"
    _assert_no_token_leak(data)

    # Preview created NO sync log and made NO QuickBooks push.
    assert db_session.scalar(
        select(func.count()).select_from(AccountingSyncLog)
    ) == 0
    assert fake_client.pushed == []


def test_preview_rejects_smuggled_field(
    client: TestClient,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
) -> None:
    resp = client.post(
        PREVIEW.format(sid=store.id),
        headers=_auth(admin),
        json={"quickbooks_quantity": 5},
    )
    assert resp.status_code == 422, resp.text


# --- Confirm (creates the ledger) ----------------------------------------- #


def test_confirm_creates_run_and_pushes_nube_quantity(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    variant: ProductVariant,
    fake_client: FakeQuickBooksClient,
) -> None:
    client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={"variant_id": str(variant.id), "external_item_id": "QB-100"},
    )
    _push_inventory(db_session, store, variant, 33)

    resp = client.post(CONFIRM.format(sid=store.id), headers=_auth(admin))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["log"]["status"] == "succeeded"
    assert data["log"]["sync_type"] == "inventory_push"
    assert data["log"]["direction"] == "push"
    assert data["log"]["items_updated"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["outcome"] == "updated"
    _assert_no_token_leak(data)

    # NubeRush-authoritative quantity pushed OUT; QuickBooks never overwrites it.
    assert fake_client.pushed == [("QB-100", 33.0)]
    inv = db_session.scalar(
        select(InventoryItem).where(
            InventoryItem.store_id == store.id,
            InventoryItem.variant_id == variant.id,
        )
    )
    assert inv.quantity_on_hand == 33


def test_confirm_rejects_smuggled_quantity_override(
    client: TestClient,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
) -> None:
    resp = client.post(
        CONFIRM.format(sid=store.id),
        headers=_auth(admin),
        json={"quantity_override": 99},
    )
    assert resp.status_code == 422, resp.text


# --- Sync-run ledger reads ------------------------------------------------ #


def test_sync_runs_listing_is_store_scoped_and_safe(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    variant: ProductVariant,
    fake_client: FakeQuickBooksClient,
) -> None:
    client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={"variant_id": str(variant.id), "external_item_id": "QB-1"},
    )
    _push_inventory(db_session, store, variant, 5)
    client.post(CONFIRM.format(sid=store.id), headers=_auth(admin))

    store_b = Store(name="B", code=f"b-{uuid.uuid4().hex[:8]}")
    db_session.add(store_b)
    db_session.commit()
    db_session.refresh(store_b)

    listing = client.get(SYNC_RUNS.format(sid=store.id), headers=_auth(admin))
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["store_id"] == str(store.id)
    _assert_no_token_leak(body)

    # Store B (no runs) sees an empty, isolated ledger.
    other = client.get(SYNC_RUNS.format(sid=store_b.id), headers=_auth(admin))
    assert other.json()["total"] == 0


def test_sync_run_detail_returns_safe_payload(
    client: TestClient,
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    connected_integration: StoreAccountingIntegration,
    variant: ProductVariant,
    fake_client: FakeQuickBooksClient,
) -> None:
    client.post(
        MAPPINGS.format(sid=store.id),
        headers=_auth(admin),
        json={"variant_id": str(variant.id), "external_item_id": "QB-1"},
    )
    _push_inventory(db_session, store, variant, 7)
    confirm = client.post(
        CONFIRM.format(sid=store.id), headers=_auth(admin)
    ).json()
    run_id = confirm["log"]["id"]

    resp = client.get(SYNC_RUN_DETAIL.format(rid=run_id), headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["log"]["id"] == run_id
    assert len(data["items"]) == 1
    assert data["items"][0]["outcome"] == "updated"
    _assert_no_token_leak(data)


def test_sync_run_detail_unknown_is_404(
    client: TestClient, admin: User
) -> None:
    resp = client.get(
        SYNC_RUN_DETAIL.format(rid=uuid.uuid4()), headers=_auth(admin)
    )
    assert resp.status_code == 404, resp.text


def test_route_surface_includes_d_and_no_scheduler() -> None:
    from app.main import app

    accounting_paths = [
        r.path for r in app.routes if "accounting" in getattr(r, "path", "")
    ]
    # B (OAuth) + C (discovery/mapping) routes remain present...
    assert any(p.endswith("/quickbooks/connect") for p in accounting_paths)
    assert any(p.endswith("/quickbooks/callback") for p in accounting_paths)
    assert any(p.endswith("/quickbooks/disconnect") for p in accounting_paths)
    assert any(p.endswith("/quickbooks/integration") for p in accounting_paths)
    assert any(p.endswith("/quickbooks/items") for p in accounting_paths)
    assert any(p.endswith("/quickbooks/mappings") for p in accounting_paths)
    assert any(
        p.endswith("/quickbooks/mappings/{mapping_id}") for p in accounting_paths
    )
    # ...and the D (sync) surface is now present.
    assert any(p.endswith("/quickbooks/sync/preview") for p in accounting_paths)
    assert any(p.endswith("/quickbooks/sync/confirm") for p in accounting_paths)
    assert any(p.endswith("/quickbooks/sync-runs") for p in accounting_paths)
    assert any(
        p.endswith("/accounting/sync-runs/{run_id}") for p in accounting_paths
    )
    # No scheduler / background / cron route was introduced.
    for p in accounting_paths:
        for banned in ("schedule", "cron", "worker", "background", "job"):
            assert banned not in p
