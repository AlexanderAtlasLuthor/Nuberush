"""Read-safe response schemas for the QuickBooks OAuth flow (F2.27.9.B).

These freeze the wire contract for connect / callback / disconnect / status.
They are an ALLOW-LIST and deliberately OMIT every piece of token/secret
material:
  - NO access_token / refresh_token (plaintext OR `*_encrypted` ciphertext);
  - NO client_secret, Authorization header, OAuth `code`, or `state`;
  - NO raw QuickBooks payload or raw error body.
Only non-secret connection metadata (status, environment, realm id, timestamps,
and the consent `authorize_url`) is exposed.

Closed value sets reuse the enums defined in `app.schemas.accounting`.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.accounting import AccountingEnvironment
from app.schemas.accounting import AccountingIntegrationStatus
from app.schemas.accounting import AccountingProvider


__all__ = [
    "QuickBooksConnectResponse",
    "QuickBooksCallbackResponse",
    "QuickBooksDisconnectResponse",
    "QuickBooksIntegrationStatusResponse",
]


class QuickBooksConnectResponse(BaseModel):
    """Returned by connect: the Intuit consent URL the admin should open.

    No DB token row is written during connect; the integration is persisted
    only after the callback completes the handshake.
    """

    store_id: UUID
    provider: AccountingProvider = AccountingProvider.quickbooks
    authorize_url: str
    state_ttl_seconds: int


class QuickBooksCallbackResponse(BaseModel):
    """Returned by the callback after a successful token exchange.

    Reports the now-connected integration's non-secret metadata only.
    """

    integration_id: UUID
    store_id: UUID
    provider: AccountingProvider
    status: AccountingIntegrationStatus
    environment: AccountingEnvironment
    realm_id: str | None
    connected: bool
    created_at: datetime
    last_sync_at: datetime | None


class QuickBooksDisconnectResponse(BaseModel):
    """Returned by disconnect after tokens are revoked/nulled."""

    integration_id: UUID
    store_id: UUID
    provider: AccountingProvider
    status: AccountingIntegrationStatus
    connected: bool
    disconnected_at: datetime | None


class QuickBooksIntegrationStatusResponse(BaseModel):
    """Returned by the status endpoint.

    For a store with no integration, `connected` is False, `status` is
    `disconnected`, and the optional fields are null.
    """

    store_id: UUID
    provider: AccountingProvider = AccountingProvider.quickbooks
    connected: bool
    status: AccountingIntegrationStatus
    integration_id: UUID | None = None
    environment: AccountingEnvironment | None = None
    realm_id: str | None = None
    created_at: datetime | None = None
    disconnected_at: datetime | None = None
    last_sync_at: datetime | None = None
