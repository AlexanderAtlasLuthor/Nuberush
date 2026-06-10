"""QuickBooks OAuth connect/callback/disconnect service (F2.27.9.B).

Owns the server-side OAuth handshake on top of `QuickBooksClient`:

  - `mint_state` / `verify_state` — a short-lived, HMAC-signed `state` that
    carries the CSRF + tenant + actor binding;
  - `build_authorize_url` — the Intuit consent URL;
  - `exchange_callback_code` — verify state, exchange the code, ENCRYPT tokens,
    upsert the `store_accounting_integrations` row as `connected`;
  - `disconnect_integration` — best-effort revoke, then null the encrypted
    tokens and mark `disconnected`.

Security model for the state (the callback's trust anchor):
  - SIGNED with HMAC-SHA256 over the configured server-only secret, compared
    with `hmac.compare_digest` (tamper-resistant);
  - bound to `store_id`, `actor_user_id`, and a random `nonce`;
  - SHORT TTL via an embedded `exp` (expired state rejected);
  - the callback derives `store_id` and `actor_user_id` from the VERIFIED state
    only — never from a query parameter (no tenant/actor spoofing).

Statelessness note: the state is self-contained (no server-side nonce store),
so it is signed + expiring + bound but not single-use within its short TTL.
True one-time use (replay defense inside the TTL window) would require a
server-side nonce ledger and is a documented follow-up — intentionally NOT
added here (it would mean a new table, out of F2.27.9.B scope).

Token material (access/refresh tokens) lives only inside this service and the
`QuickBooksClient`; it is ENCRYPTED via `app.core.encryption` before any DB
write and is NEVER returned through an API schema.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_quickbooks_settings
from app.core.encryption import TokenEncryptionError
from app.core.encryption import decrypt_token
from app.core.encryption import encrypt_token
from app.db.models import StoreAccountingIntegration
from app.services.accounting.quickbooks_client import DEFAULT_SCOPE
from app.services.accounting.quickbooks_client import INTUIT_AUTHORIZE_URL
from app.services.accounting.quickbooks_client import QuickBooksClient
from app.services.accounting.quickbooks_client import QuickBooksClientError
from app.services.accounting.quickbooks_client import QuickBooksConfigError


PROVIDER_QUICKBOOKS = "quickbooks"


class OAuthStateError(Exception):
    """A missing / malformed / tampered / expired OAuth state.

    Bare message by contract — it never echoes the state token, its payload,
    or any signature, so a rejected callback cannot leak material.
    """


@dataclass(frozen=True)
class VerifiedState:
    """The trusted binding recovered from a verified OAuth state."""

    store_id: UUID
    actor_user_id: UUID
    nonce: str


# --------------------------------------------------------------------- #
# Signed state
# --------------------------------------------------------------------- #


def _state_secret() -> str:
    secret = get_quickbooks_settings().quickbooks_oauth_state_secret.strip()
    if not secret:
        raise QuickBooksConfigError(
            "QUICKBOOKS_OAUTH_STATE_SECRET is not configured."
        )
    return secret


def _sign(payload_b64: bytes, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), payload_b64, hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def mint_state(*, store_id: UUID, actor_user_id: UUID) -> str:
    """Return a signed, short-lived state bound to store + actor + nonce."""
    settings = get_quickbooks_settings()
    secret = _state_secret()
    ttl = int(settings.quickbooks_oauth_state_ttl_seconds)
    exp = int(datetime.now(UTC).timestamp()) + ttl
    payload = {
        "store_id": str(store_id),
        "actor_user_id": str(actor_user_id),
        "nonce": secrets.token_urlsafe(16),
        "exp": exp,
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).rstrip(b"=")
    signature = _sign(payload_b64, secret)
    return f"{payload_b64.decode('ascii')}.{signature}"


def verify_state(state: str) -> VerifiedState:
    """Verify a state's signature + expiry and return its trusted binding.

    Raises `OAuthStateError` on any missing/malformed/tampered/expired state.
    The message never echoes the state.
    """
    if not state or not isinstance(state, str):
        raise OAuthStateError("Missing OAuth state.")
    secret = _state_secret()
    parts = state.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise OAuthStateError("Malformed OAuth state.")
    payload_b64_str, signature = parts

    expected = _sign(payload_b64_str.encode("ascii"), secret)
    if not hmac.compare_digest(signature, expected):
        raise OAuthStateError("Invalid OAuth state signature.")

    try:
        padded = payload_b64_str + "=" * (-len(payload_b64_str) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        store_id = UUID(str(payload["store_id"]))
        actor_user_id = UUID(str(payload["actor_user_id"]))
        nonce = str(payload["nonce"])
        exp = int(payload["exp"])
    except (ValueError, KeyError, TypeError) as exc:
        raise OAuthStateError("Malformed OAuth state payload.") from exc

    if int(datetime.now(UTC).timestamp()) > exp:
        raise OAuthStateError("OAuth state has expired.")

    return VerifiedState(
        store_id=store_id, actor_user_id=actor_user_id, nonce=nonce
    )


# --------------------------------------------------------------------- #
# Authorize URL + client factory
# --------------------------------------------------------------------- #


def build_authorize_url(*, state: str, scope: str = DEFAULT_SCOPE) -> str:
    """Build the Intuit consent URL for the connect step.

    Raises `QuickBooksConfigError` if the client id / redirect URL is unset.
    """
    settings = get_quickbooks_settings()
    client_id = settings.quickbooks_client_id.strip()
    redirect_uri = settings.quickbooks_redirect_url.strip()
    if not client_id:
        raise QuickBooksConfigError("QUICKBOOKS_CLIENT_ID is not configured.")
    if not redirect_uri:
        raise QuickBooksConfigError(
            "QUICKBOOKS_REDIRECT_URL is not configured."
        )
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": scope,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{INTUIT_AUTHORIZE_URL}?{query}"


def resolve_quickbooks_client() -> QuickBooksClient:
    """Build a `QuickBooksClient` from settings.

    Factory seam: tests monkeypatch this to inject a fake client, so no real
    Intuit call is made. Raises `QuickBooksConfigError` (via the client
    constructor) when client id/secret are unset.
    """
    settings = get_quickbooks_settings()
    return QuickBooksClient(
        client_id=settings.quickbooks_client_id.strip(),
        client_secret=settings.quickbooks_client_secret.strip(),
        redirect_uri=settings.quickbooks_redirect_url.strip(),
        timeout=settings.quickbooks_timeout_seconds,
    )


# --------------------------------------------------------------------- #
# Integration lookup / upsert / disconnect
# --------------------------------------------------------------------- #


def get_integration(
    db: Session, *, store_id: UUID
) -> StoreAccountingIntegration | None:
    """Return the store's QuickBooks integration row, or None."""
    return db.scalar(
        select(StoreAccountingIntegration).where(
            StoreAccountingIntegration.store_id == store_id,
            StoreAccountingIntegration.provider == PROVIDER_QUICKBOOKS,
        )
    )


def exchange_callback_code(
    db: Session, *, code: str, realm_id: str, state: str
) -> StoreAccountingIntegration:
    """Verify state, exchange the code for tokens, encrypt + persist.

    `store_id` and `connected_by_user_id` come from the VERIFIED state, never
    from a query parameter. Tokens are encrypted before the DB write; ciphertext
    is what is persisted. Returns the upserted (connected) integration row.
    """
    verified = verify_state(state)

    client = resolve_quickbooks_client()
    token_result = client.exchange_code(code=code)

    access_enc = encrypt_token(token_result.access_token)
    refresh_enc = encrypt_token(token_result.refresh_token)

    environment = get_quickbooks_settings().quickbooks_environment.strip() or (
        "sandbox"
    )

    integration = get_integration(db, store_id=verified.store_id)
    if integration is None:
        integration = StoreAccountingIntegration(
            store_id=verified.store_id,
            provider=PROVIDER_QUICKBOOKS,
        )
        db.add(integration)

    integration.status = "connected"
    integration.environment = environment
    integration.realm_id = realm_id
    integration.access_token_encrypted = access_enc
    integration.refresh_token_encrypted = refresh_enc
    integration.access_token_expires_at = token_result.access_token_expires_at
    integration.refresh_token_expires_at = (
        token_result.refresh_token_expires_at
    )
    integration.scopes = token_result.scopes
    integration.connected_by_user_id = verified.actor_user_id
    integration.disconnected_at = None

    db.commit()
    db.refresh(integration)
    return integration


def disconnect_integration(
    db: Session, *, store_id: UUID
) -> StoreAccountingIntegration | None:
    """Best-effort revoke at Intuit, then null tokens + mark disconnected.

    Returns the disconnected integration, or None if the store has none.
    Mapping and sync-ledger rows are intentionally left untouched.
    """
    integration = get_integration(db, store_id=store_id)
    if integration is None:
        return None

    # Best-effort revoke: decrypt the refresh token (preferred) or access token
    # and ask Intuit to revoke it. Any failure (decrypt or HTTP) is swallowed so
    # a disconnect always completes locally — the local tokens are nulled below
    # regardless.
    encrypted = (
        integration.refresh_token_encrypted
        or integration.access_token_encrypted
    )
    if encrypted:
        try:
            client = resolve_quickbooks_client()
            client.revoke_token(token=decrypt_token(encrypted))
        except (QuickBooksClientError, TokenEncryptionError):
            pass

    integration.access_token_encrypted = None
    integration.refresh_token_encrypted = None
    integration.access_token_expires_at = None
    integration.refresh_token_expires_at = None
    integration.status = "disconnected"
    integration.disconnected_at = datetime.now(UTC)

    db.commit()
    db.refresh(integration)
    return integration
