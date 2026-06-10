"""Pydantic v2 read schemas for the QuickBooks / accounting foundation
(F2.27.9.A).

These freeze the READ-SAFE wire contract for the accounting integration,
mapping, and sync-ledger surfaces. This subphase ships the schemas only: NO
route consumes them yet.

SECURITY — the read schemas are an allow-list, and they deliberately OMIT every
piece of secret material:
  - NO `access_token_encrypted` / `refresh_token_encrypted` (not even the
    ciphertext leaves the backend);
  - NO `client_secret`, authorization header, OAuth `code`/`state`, or any
    plaintext token;
  - NO raw QuickBooks payload/body.
Only non-secret connection metadata, token *expiry* timestamps (for refresh
bookkeeping in a later subphase), mappings, and ledger rows are exposed.

Design rules mirror `app.schemas.regulatory_ingestion`:
  - `provider` / `status` / `environment` / `sync_type` / `direction` /
    `trigger` / `outcome` are closed value sets defined HERE as str enums, not
    in the ORM: the DB columns are `varchar` discriminators guarded by CHECK
    constraints (no PG enum). The varchar columns hydrate into these enums.
  - Read schemas use `from_attributes=True` and do NOT set `extra="forbid"`,
    following the repo convention for read-only projections.
"""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


__all__ = [
    "AccountingProvider",
    "AccountingIntegrationStatus",
    "AccountingEnvironment",
    "AccountingSyncType",
    "AccountingSyncDirection",
    "AccountingSyncStatus",
    "AccountingSyncTrigger",
    "AccountingSyncItemOutcome",
    "StoreAccountingIntegrationRead",
    "ProductVariantAccountingMappingRead",
    "AccountingSyncLogItemRead",
    "AccountingSyncLogRead",
    "AccountingSyncLogDetailResponse",
    # F2.27.9.C — item discovery + variant<->item mapping
    "QuickBooksItemRead",
    "QuickBooksItemListResponse",
    "AccountingMappingCreateRequest",
    "AccountingMappingUpdateRequest",
    "AccountingMappingRead",
    "AccountingMappingListResponse",
    # F2.27.9.D — inventory push preview + confirm + sync ledger
    "InventoryPushPreviewRequest",
    "InventoryPushPreviewItem",
    "InventoryPushPreviewResponse",
    "InventoryPushConfirmRequest",
    "InventoryPushConfirmResponse",
    "AccountingSyncLogListResponse",
]


class AccountingProvider(str, enum.Enum):
    """Supported external accounting provider. QuickBooks only in F2.27.9."""

    quickbooks = "quickbooks"


class AccountingIntegrationStatus(str, enum.Enum):
    """Connection lifecycle of a store's accounting integration.

    `disconnected` (the default for a fresh/never-connected row) → `connected`
    once OAuth completes; `expired` when a token refresh can no longer succeed;
    `error` on a non-recoverable connection fault. No status here implies any
    inventory mutation.
    """

    connected = "connected"
    disconnected = "disconnected"
    expired = "expired"
    error = "error"


class AccountingEnvironment(str, enum.Enum):
    """Intuit environment the integration targets."""

    sandbox = "sandbox"
    production = "production"


class AccountingSyncType(str, enum.Enum):
    """What kind of sync a ledger row records.

    `item_discovery` / `mapping_pull` are inbound reads used only to build
    variant<->item mappings; `inventory_push` is the NubeRush-authoritative
    outbound write. None of these mutate NubeRush inventory.
    """

    item_discovery = "item_discovery"
    mapping_pull = "mapping_pull"
    inventory_push = "inventory_push"


class AccountingSyncDirection(str, enum.Enum):
    """Direction of a sync run relative to NubeRush."""

    pull = "pull"
    push = "push"


class AccountingSyncStatus(str, enum.Enum):
    """Lifecycle of a sync run.

    `running` while in flight; one of `succeeded` / `failed` / `partial` once
    finished. Observability only.
    """

    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    partial = "partial"


class AccountingSyncTrigger(str, enum.Enum):
    """How a sync run was started.

    Only `manual` is produced in F2.27.9; `scheduled` is a future-ready value
    (no automated scheduling exists or is implemented).
    """

    manual = "manual"
    scheduled = "scheduled"


class AccountingSyncItemOutcome(str, enum.Enum):
    """What one item became during a sync run."""

    created = "created"
    updated = "updated"
    skipped = "skipped"
    failed = "failed"


class StoreAccountingIntegrationRead(BaseModel):
    """Read-safe projection of a store's accounting integration.

    Exposes connection metadata and token *expiry* timestamps ONLY. The
    encrypted token columns (`access_token_encrypted` /
    `refresh_token_encrypted`), the client secret, and any plaintext token are
    intentionally absent — they must never leave the backend.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    provider: AccountingProvider
    status: AccountingIntegrationStatus
    environment: AccountingEnvironment
    realm_id: str | None
    scopes: str | None
    connected_by_user_id: UUID | None
    access_token_expires_at: datetime | None
    refresh_token_expires_at: datetime | None
    disconnected_at: datetime | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductVariantAccountingMappingRead(BaseModel):
    """Read-safe projection of a variant <-> external-item mapping."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    integration_id: UUID
    store_id: UUID
    variant_id: UUID
    provider: AccountingProvider
    external_item_id: str
    external_item_name: str | None
    sync_enabled: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AccountingSyncLogItemRead(BaseModel):
    """Read-safe projection of one per-item sync outcome (append-only).

    Carries no raw payload/body, secret, token, or auth header — only the
    stable `external_item_id` / `external_item_name`, the `outcome`, and a
    short machine `error_code` + human `error_message`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sync_log_id: UUID
    variant_id: UUID | None
    external_item_id: str | None
    external_item_name: str | None
    outcome: AccountingSyncItemOutcome
    error_code: str | None
    error_message: str | None
    created_at: datetime


class AccountingSyncLogRead(BaseModel):
    """Read-safe projection of one sync run (the ledger header)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    integration_id: UUID
    sync_type: AccountingSyncType
    direction: AccountingSyncDirection
    status: AccountingSyncStatus
    trigger: AccountingSyncTrigger
    started_at: datetime
    finished_at: datetime | None
    items_seen: int
    items_created: int
    items_updated: int
    items_skipped: int
    items_failed: int
    error_summary: str | None
    actor_user_id: UUID | None
    created_at: datetime


class AccountingSyncLogDetailResponse(BaseModel):
    """A single sync run plus its per-item outcomes (the run detail view)."""

    log: AccountingSyncLogRead
    items: list[AccountingSyncLogItemRead]


# ===================================================================== #
# F2.27.9.C — item discovery + variant <-> QuickBooks item mapping.
#
# Read-safe discovery summaries and the mapping CRUD wire contract. These never
# expose tokens/ciphertext/secrets or a raw QuickBooks payload, and they carry
# NO inventory-mutation intent (no quantity write field, no sync flag).
# ===================================================================== #


class QuickBooksItemRead(BaseModel):
    """A sanitized QuickBooks item summary returned by discovery.

    Projection only — never the raw Intuit payload. `quantity_on_hand` is
    informational; NubeRush remains authoritative and nothing here mutates it.
    """

    model_config = ConfigDict(from_attributes=True)

    external_item_id: str
    name: str | None
    sku: str | None
    description: str | None
    unit_price: float | None
    purchase_cost: float | None
    quantity_on_hand: float | None


class QuickBooksItemListResponse(BaseModel):
    """Envelope for a discovery listing of QuickBooks items."""

    items: list[QuickBooksItemRead]
    total: int = Field(ge=0)


class AccountingMappingCreateRequest(BaseModel):
    """Create a variant <-> external-item mapping.

    `extra="forbid"` rejects stray fields (e.g. any attempt to smuggle a
    quantity/sync intent) with 422. There is deliberately NO quantity or
    sync-confirm field — this subphase only links a variant to an external item.
    """

    model_config = ConfigDict(extra="forbid")

    variant_id: UUID
    external_item_id: str = Field(min_length=1, max_length=255)
    external_item_name: str | None = Field(default=None, max_length=255)
    sync_enabled: bool = True


class AccountingMappingUpdateRequest(BaseModel):
    """Partial update of a mapping. All fields optional; unset fields untouched.

    `extra="forbid"` blocks any inventory-write/quantity/sync-confirm field.
    """

    model_config = ConfigDict(extra="forbid")

    external_item_id: str | None = Field(default=None, min_length=1, max_length=255)
    external_item_name: str | None = Field(default=None, max_length=255)
    sync_enabled: bool | None = None


class AccountingMappingRead(ProductVariantAccountingMappingRead):
    """Read-safe mapping projection (alias of the A-phase mapping read).

    Inherits the full read-safe field set; declared as a distinct name so the
    F2.27.9.C route surface reads clearly and the OpenAPI schema is explicit.
    """


class AccountingMappingListResponse(BaseModel):
    """Paginated envelope for a store/integration's mappings."""

    items: list[AccountingMappingRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


# ===================================================================== #
# F2.27.9.D — inventory push preview + confirm + sync ledger.
#
# Manual, NubeRush-authoritative outbound push: NubeRush
# `InventoryItem.quantity_on_hand` is mirrored TO QuickBooks. NubeRush is never
# overwritten from QuickBooks. The request schemas are `extra="forbid"` and
# carry NO quantity-override / sync-direction / inventory-pull field, so a
# client cannot smuggle a QuickBooks -> NubeRush write or a quantity override.
# No schema here exposes a token, ciphertext, secret, auth header, or raw
# QuickBooks payload/body.
# ===================================================================== #


class InventoryPushPreviewRequest(BaseModel):
    """Body for the preview request (no fields).

    Deliberately empty + `extra="forbid"`: preview takes no client input. A
    smuggled `quantity_override` / `sync_confirm` / `store_id` / token field is
    rejected with 422. Sent as an optional body.
    """

    model_config = ConfigDict(extra="forbid")


class InventoryPushPreviewItem(BaseModel):
    """One proposed inventory push line in a preview (read-only, no write)."""

    model_config = ConfigDict(from_attributes=True)

    variant_id: UUID
    external_item_id: str
    external_item_name: str | None
    # NubeRush is authoritative; this is the value that WOULD be pushed.
    nube_quantity_on_hand: int | None
    # Informational only and NOT fetched during preview (left None) so preview
    # makes no QuickBooks call and no DB write; never written back to NubeRush.
    quickbooks_quantity_on_hand: float | None = None
    proposed_action: str  # "push" | "skip"
    sync_enabled: bool
    issue: str | None = None


class InventoryPushPreviewResponse(BaseModel):
    """Preview summary + per-item proposed pushes. No DB/QuickBooks side effects."""

    store_id: UUID
    integration_id: UUID
    total_mappings: int = Field(ge=0)
    items_to_push: int = Field(ge=0)
    items_skipped: int = Field(ge=0)
    items: list[InventoryPushPreviewItem]


class InventoryPushConfirmRequest(BaseModel):
    """Body for the confirm request (no fields).

    Deliberately empty + `extra="forbid"`: confirm pushes the CURRENT NubeRush
    quantities. A smuggled `quantity_override` / `quickbooks_quantity` /
    inventory-pull field is rejected with 422 — there is no way to inject a
    quantity or reverse the sync direction. Sent as an optional body.
    """

    model_config = ConfigDict(extra="forbid")


class InventoryPushConfirmResponse(AccountingSyncLogDetailResponse):
    """Confirm result: the created push run header + its per-item outcomes.

    Structurally the sync-run detail (ledger header + items). No token,
    ciphertext, secret, or raw QuickBooks payload is present.
    """


class AccountingSyncLogListResponse(BaseModel):
    """Paginated envelope for a store's sync-run ledger headers."""

    items: list[AccountingSyncLogRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
