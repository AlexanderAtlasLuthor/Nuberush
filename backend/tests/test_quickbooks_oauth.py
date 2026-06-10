"""Tests for the QuickBooks OAuth service (F2.27.9.B).

Covers signed-state security (binding / expiry / tamper / missing), the connect
authorize URL, and the callback/disconnect DB flow. The QuickBooks client is
replaced by a fake (monkeypatched factory) so NO real network and NO real
credentials are used; tokens are encrypted before any DB write.
"""
from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Callable

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_quickbooks_settings
from app.core.encryption import decrypt_token
from app.db.models import Store
from app.db.models import StoreAccountingIntegration
from app.db.models import User
from app.db.models import UserRole
from app.services.accounting import oauth as oauth_svc
from app.services.accounting.oauth import OAuthStateError
from app.services.accounting.quickbooks_client import QuickBooksConfigError
from app.services.accounting.quickbooks_client import TokenResult
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Fakes / fixtures
# --------------------------------------------------------------------- #


class FakeQuickBooksClient:
    """In-memory stand-in for QuickBooksClient — no network."""

    def __init__(self) -> None:
        self.revoked: list[str] = []
        self.exchanged: list[str] = []

    def exchange_code(self, *, code, redirect_uri=None) -> TokenResult:
        self.exchanged.append(code)
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


@pytest.fixture
def qb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure QuickBooks settings (state secret + encryption key, etc.)."""
    monkeypatch.setenv("QUICKBOOKS_CLIENT_ID", "cid")
    monkeypatch.setenv("QUICKBOOKS_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("QUICKBOOKS_REDIRECT_URL", "https://app.example/cb")
    monkeypatch.setenv("QUICKBOOKS_ENVIRONMENT", "sandbox")
    monkeypatch.setenv(
        "QUICKBOOKS_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )
    monkeypatch.setenv("QUICKBOOKS_OAUTH_STATE_SECRET", "state-signing-secret")
    monkeypatch.setenv("QUICKBOOKS_OAUTH_STATE_TTL_SECONDS", "600")
    get_quickbooks_settings.cache_clear()
    yield
    get_quickbooks_settings.cache_clear()


@pytest.fixture
def store(db_session: Session) -> Store:
    s = Store(name="QB Store", code=f"qb-{uuid.uuid4().hex[:8]}")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def admin(db_session: Session) -> User:
    return central_make_user(db_session, role=UserRole.admin)


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeQuickBooksClient:
    fake = FakeQuickBooksClient()
    monkeypatch.setattr(oauth_svc, "resolve_quickbooks_client", lambda: fake)
    return fake


# --------------------------------------------------------------------- #
# State signing / verification
# --------------------------------------------------------------------- #


def test_state_round_trip_binds_store_and_actor(qb_env: None) -> None:
    store_id, actor_id = uuid.uuid4(), uuid.uuid4()
    state = oauth_svc.mint_state(store_id=store_id, actor_user_id=actor_id)
    verified = oauth_svc.verify_state(state)
    assert verified.store_id == store_id
    assert verified.actor_user_id == actor_id
    assert verified.nonce  # a binding nonce is present


def test_state_is_signed_distinct_secret_rejected(
    qb_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = oauth_svc.mint_state(
        store_id=uuid.uuid4(), actor_user_id=uuid.uuid4()
    )
    # Rotate the signing secret: the old state must no longer verify.
    monkeypatch.setenv("QUICKBOOKS_OAUTH_STATE_SECRET", "a-different-secret")
    get_quickbooks_settings.cache_clear()
    with pytest.raises(OAuthStateError):
        oauth_svc.verify_state(state)


def test_state_tamper_rejected(qb_env: None) -> None:
    state = oauth_svc.mint_state(
        store_id=uuid.uuid4(), actor_user_id=uuid.uuid4()
    )
    payload_b64, sig = state.split(".")
    # Flip a character in the payload — signature no longer matches.
    tampered_payload = ("A" if payload_b64[0] != "A" else "B") + payload_b64[1:]
    with pytest.raises(OAuthStateError):
        oauth_svc.verify_state(f"{tampered_payload}.{sig}")
    # Flip the signature too.
    tampered_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    with pytest.raises(OAuthStateError):
        oauth_svc.verify_state(f"{payload_b64}.{tampered_sig}")


def test_state_expired_rejected(
    qb_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Negative TTL => exp in the past => immediately expired.
    monkeypatch.setenv("QUICKBOOKS_OAUTH_STATE_TTL_SECONDS", "-10")
    get_quickbooks_settings.cache_clear()
    state = oauth_svc.mint_state(
        store_id=uuid.uuid4(), actor_user_id=uuid.uuid4()
    )
    with pytest.raises(OAuthStateError):
        oauth_svc.verify_state(state)


@pytest.mark.parametrize("bad", ["", "nodot", "a.b.c", "onlyone."])
def test_malformed_or_missing_state_rejected(qb_env: None, bad: str) -> None:
    with pytest.raises(OAuthStateError):
        oauth_svc.verify_state(bad)


def test_mint_state_without_secret_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No QUICKBOOKS_OAUTH_STATE_SECRET set (isolation default is empty).
    get_quickbooks_settings.cache_clear()
    with pytest.raises(QuickBooksConfigError):
        oauth_svc.mint_state(
            store_id=uuid.uuid4(), actor_user_id=uuid.uuid4()
        )


# --------------------------------------------------------------------- #
# Authorize URL
# --------------------------------------------------------------------- #


def test_build_authorize_url(qb_env: None) -> None:
    state = oauth_svc.mint_state(
        store_id=uuid.uuid4(), actor_user_id=uuid.uuid4()
    )
    url = oauth_svc.build_authorize_url(state=state)
    assert url.startswith("https://appcenter.intuit.com/connect/oauth2?")
    assert "client_id=cid" in url
    assert "response_type=code" in url
    assert "state=" in url


# --------------------------------------------------------------------- #
# Callback exchange: encrypt + upsert
# --------------------------------------------------------------------- #


def test_callback_encrypts_tokens_before_db_write(
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    integration = oauth_svc.exchange_callback_code(
        db_session, code="auth-code", realm_id="REALM-1", state=state
    )

    # Stored values are CIPHERTEXT, not plaintext, and decrypt back.
    assert integration.access_token_encrypted is not None
    assert integration.access_token_encrypted != "ACCESS-PLAINTEXT"
    assert "ACCESS-PLAINTEXT" not in integration.access_token_encrypted
    assert decrypt_token(integration.access_token_encrypted) == "ACCESS-PLAINTEXT"
    assert decrypt_token(integration.refresh_token_encrypted) == "REFRESH-PLAINTEXT"


def test_callback_upserts_connected_integration_from_state(
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    integration = oauth_svc.exchange_callback_code(
        db_session, code="auth-code", realm_id="REALM-9", state=state
    )
    # store_id + connected_by come from the VERIFIED STATE (no query store_id).
    assert integration.store_id == store.id
    assert integration.connected_by_user_id == admin.id
    assert integration.status == "connected"
    assert integration.environment == "sandbox"
    assert integration.realm_id == "REALM-9"
    assert integration.disconnected_at is None


def test_callback_is_idempotent_upsert(
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    s1 = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    first = oauth_svc.exchange_callback_code(
        db_session, code="c1", realm_id="R1", state=s1
    )
    s2 = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    second = oauth_svc.exchange_callback_code(
        db_session, code="c2", realm_id="R2", state=s2
    )
    assert first.id == second.id  # same row updated, not duplicated
    count = db_session.scalar(
        select(func.count())
        .select_from(StoreAccountingIntegration)
        .where(StoreAccountingIntegration.store_id == store.id)
    )
    assert count == 1


def test_callback_rejects_invalid_state_before_any_write(
    db_session: Session,
    qb_env: None,
    store: Store,
    fake_client: FakeQuickBooksClient,
) -> None:
    with pytest.raises(OAuthStateError):
        oauth_svc.exchange_callback_code(
            db_session, code="c", realm_id="R", state="garbage.state"
        )
    # No integration row was created, and no exchange was attempted.
    count = db_session.scalar(
        select(func.count()).select_from(StoreAccountingIntegration)
    )
    assert count == 0
    assert fake_client.exchanged == []


# --------------------------------------------------------------------- #
# Disconnect
# --------------------------------------------------------------------- #


def test_disconnect_nulls_tokens_and_marks_disconnected(
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    fake_client: FakeQuickBooksClient,
) -> None:
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    oauth_svc.exchange_callback_code(
        db_session, code="c", realm_id="R", state=state
    )

    integration = oauth_svc.disconnect_integration(db_session, store_id=store.id)
    assert integration is not None
    assert integration.status == "disconnected"
    assert integration.disconnected_at is not None
    assert integration.access_token_encrypted is None
    assert integration.refresh_token_encrypted is None
    assert integration.access_token_expires_at is None
    assert integration.refresh_token_expires_at is None
    # Best-effort revoke was attempted with the (decrypted) refresh token.
    assert "REFRESH-PLAINTEXT" in fake_client.revoked


def test_disconnect_missing_integration_returns_none(
    db_session: Session, qb_env: None, store: Store
) -> None:
    assert oauth_svc.disconnect_integration(db_session, store_id=store.id) is None


def test_disconnect_swallows_revoke_failure(
    db_session: Session,
    qb_env: None,
    store: Store,
    admin: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.accounting.quickbooks_client import QuickBooksClientError

    class BoomClient(FakeQuickBooksClient):
        def revoke_token(self, *, token) -> None:
            raise QuickBooksClientError("revoke failed")

    monkeypatch.setattr(
        oauth_svc, "resolve_quickbooks_client", lambda: BoomClient()
    )
    state = oauth_svc.mint_state(store_id=store.id, actor_user_id=admin.id)
    oauth_svc.exchange_callback_code(
        db_session, code="c", realm_id="R", state=state
    )
    # Even if revoke raises, disconnect completes locally.
    integration = oauth_svc.disconnect_integration(db_session, store_id=store.id)
    assert integration.status == "disconnected"
    assert integration.access_token_encrypted is None
