"""Variant <-> QuickBooks item mapping + item discovery service (F2.27.9.C).

Backend-only mapping CRUD and read-only QuickBooks item discovery on top of the
F2.27.9.A storage and the F2.27.9.B OAuth/client foundation.

Hard invariants (NubeRush stays authoritative; QuickBooks is a mirror only):
  - Tenancy: every operation is scoped to the route `store_id` via the store's
    QuickBooks integration. A mapping belongs to exactly one integration, and a
    mapping from another store/integration is invisible (404) — no cross-store
    read or write.
  - Catalog: `product_variants` is a GLOBAL catalog (no store ownership column),
    so a mapping validates that the variant EXISTS; it does not invent a
    variant store_id. The mapping's `store_id` is taken from the integration.
  - Uniqueness: at most one mapping per (integration, variant) and per
    (integration, external_item_id) — enforced by the A-phase DB constraints
    and surfaced here as 409.
  - This module NEVER mutates Product, ProductVariant, InventoryItem, or
    InventoryLog; NEVER writes to QuickBooks; NEVER creates a sync log; and
    NEVER auto-creates a product. Token material is decrypted only in-memory for
    the discovery call and is never returned.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_quickbooks_settings
from app.core.encryption import TokenEncryptionError
from app.core.encryption import decrypt_token
from app.db.models import ProductVariant
from app.db.models import ProductVariantAccountingMapping
from app.db.models import StoreAccountingIntegration
from app.schemas.accounting import AccountingMappingCreateRequest
from app.schemas.accounting import AccountingMappingUpdateRequest
from app.schemas.accounting import QuickBooksItemRead
from app.services.accounting import oauth as oauth_svc
from app.services.accounting.oauth import PROVIDER_QUICKBOOKS
from app.services.accounting.quickbooks_client import QuickBooksClientError
from app.services.accounting.quickbooks_client import QuickBooksConfigError


_DUPLICATE_DETAIL = (
    "A mapping for this variant or external item already exists "
    "for this integration."
)


def _require_integration(
    db: Session, store_id: UUID, *, must_be_connected: bool
) -> StoreAccountingIntegration:
    """Resolve the store's QuickBooks integration, or raise.

    404 when the store has no QuickBooks integration; 409 when it exists but is
    not `connected` (only enforced for operations that need a live connection).
    """
    integration = db.scalar(
        select(StoreAccountingIntegration).where(
            StoreAccountingIntegration.store_id == store_id,
            StoreAccountingIntegration.provider == PROVIDER_QUICKBOOKS,
        )
    )
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No QuickBooks integration for this store.",
        )
    if must_be_connected and integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="QuickBooks integration is not connected.",
        )
    return integration


def list_quickbooks_items(
    db: Session, *, store_id: UUID
) -> list[QuickBooksItemRead]:
    """Read-only discovery of QuickBooks items for mapping.

    Requires a connected integration. Decrypts the stored access token in
    memory ONLY to make the call; the token is never returned or logged. Any
    config/token/client failure is mapped to a sanitized HTTP error.
    """
    integration = _require_integration(db, store_id, must_be_connected=True)
    if not integration.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="QuickBooks integration is not connected.",
        )
    try:
        access_token = decrypt_token(integration.access_token_encrypted)
    except TokenEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks access token could not be read.",
        ) from exc

    settings = get_quickbooks_settings()
    try:
        client = oauth_svc.resolve_quickbooks_client()
        summaries = client.list_items(
            access_token=access_token,
            realm_id=integration.realm_id or "",
            environment=integration.environment,
            max_items=settings.quickbooks_max_items_per_run,
        )
    except QuickBooksConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except QuickBooksClientError as exc:
        # Bare, secret-free upstream failure.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return [QuickBooksItemRead.model_validate(s) for s in summaries]


def list_mappings(
    db: Session, *, store_id: UUID, limit: int = 100, offset: int = 0
) -> tuple[list[ProductVariantAccountingMapping], int]:
    """Return (mappings, total) for the store's integration only.

    Tenancy-scoped: only mappings belonging to THIS store's integration are
    returned — store A can never see store B's mappings.
    """
    integration = _require_integration(db, store_id, must_be_connected=False)
    where = ProductVariantAccountingMapping.integration_id == integration.id
    total = db.scalar(
        select(func.count())
        .select_from(ProductVariantAccountingMapping)
        .where(where)
    )
    rows = list(
        db.scalars(
            select(ProductVariantAccountingMapping)
            .where(where)
            .order_by(ProductVariantAccountingMapping.created_at)
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, int(total or 0)


def create_mapping(
    db: Session, *, store_id: UUID, payload: AccountingMappingCreateRequest
) -> ProductVariantAccountingMapping:
    """Create a variant <-> external-item mapping for the store's integration.

    Validates the integration is connected and the variant exists. The DB
    uniqueness constraints (variant and external item, per integration) surface
    as 409. Mutates ONLY the mapping table — no product/inventory write.
    """
    integration = _require_integration(db, store_id, must_be_connected=True)

    variant = db.scalar(
        select(ProductVariant).where(ProductVariant.id == payload.variant_id)
    )
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown product variant.",
        )

    mapping = ProductVariantAccountingMapping(
        integration_id=integration.id,
        store_id=integration.store_id,
        variant_id=payload.variant_id,
        provider=PROVIDER_QUICKBOOKS,
        external_item_id=payload.external_item_id,
        external_item_name=payload.external_item_name,
        sync_enabled=payload.sync_enabled,
    )
    db.add(mapping)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL
        ) from exc
    db.refresh(mapping)
    return mapping


def update_mapping(
    db: Session,
    *,
    store_id: UUID,
    mapping_id: UUID,
    payload: AccountingMappingUpdateRequest,
) -> ProductVariantAccountingMapping:
    """Partial update (incl. toggling `sync_enabled`) of a mapping.

    Tenancy-scoped: a mapping that does not belong to THIS store's integration
    is reported as 404 (no cross-store update, no enumeration). Mutates ONLY the
    mapping row.
    """
    integration = _require_integration(db, store_id, must_be_connected=False)
    mapping = db.scalar(
        select(ProductVariantAccountingMapping).where(
            ProductVariantAccountingMapping.id == mapping_id
        )
    )
    if mapping is None or mapping.integration_id != integration.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found."
        )

    if payload.external_item_id is not None:
        mapping.external_item_id = payload.external_item_id
    if payload.external_item_name is not None:
        mapping.external_item_name = payload.external_item_name
    if payload.sync_enabled is not None:
        mapping.sync_enabled = payload.sync_enabled

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL
        ) from exc
    db.refresh(mapping)
    return mapping
