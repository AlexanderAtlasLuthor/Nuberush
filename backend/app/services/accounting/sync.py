"""Manual inventory push preview + confirm + sync-ledger service (F2.27.9.D).

Backend-only orchestration of a MANUAL, NubeRush-authoritative outbound
inventory push to QuickBooks, on top of the F2.27.9.A ledger tables, the
F2.27.9.B OAuth/client foundation, and the F2.27.9.C mappings.

Central authority rule (hard invariant):
  - NubeRush `InventoryItem.quantity_on_hand` is authoritative and is the value
    pushed OUT to QuickBooks. QuickBooks quantity is informational only and is
    NEVER read back into NubeRush. This module NEVER mutates `InventoryItem`,
    `InventoryLog`, `Product`, or `ProductVariant`, and NEVER touches
    `services.inventory`. It only writes the accounting ledger
    (`AccountingSyncLog` / `AccountingSyncLogItem`) and bookkeeping timestamps
    on the integration / mapping rows.

Scope guard: there is NO scheduler, NO background job, NO automatic sync, NO
item create/delete, and NO product auto-create. `preview` performs ZERO writes
and ZERO QuickBooks calls; `confirm` is the only path that writes the ledger and
calls the QuickBooks client.

Token handling: `preview` never decrypts a token (it makes no QuickBooks call).
`confirm` decrypts the access token in memory only to call the client; the token
is never returned, never logged, and a decrypt/config failure is recorded as a
sanitized ledger failure — never as a raw error.
"""
from __future__ import annotations

from collections import Counter
from datetime import UTC
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import TokenEncryptionError
from app.core.encryption import decrypt_token
from app.db.models import AccountingSyncLog
from app.db.models import AccountingSyncLogItem
from app.db.models import InventoryItem
from app.db.models import ProductVariantAccountingMapping
from app.db.models import StoreAccountingIntegration
from app.schemas.accounting import InventoryPushPreviewItem
from app.schemas.accounting import InventoryPushPreviewResponse
from app.services.accounting import oauth as oauth_svc
from app.services.accounting.quickbooks_client import QuickBooksClientError
from app.services.accounting.quickbooks_client import QuickBooksConfigError
from app.services.accounting.quickbooks_client import QuickBooksRateLimitError


_SYNC_TYPE_INVENTORY_PUSH = "inventory_push"
_DIRECTION_PUSH = "push"
_TRIGGER_MANUAL = "manual"

_NO_INVENTORY_DETAIL = (
    "No NubeRush inventory record for this variant in this store."
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------- #


def _require_connected_integration(
    db: Session, store_id: UUID
) -> StoreAccountingIntegration:
    """Resolve the store's QuickBooks integration or raise.

    404 when the store has no QuickBooks integration; 409 when it exists but is
    not `connected`. Mirrors the C mapping service's tenancy gate.
    """
    integration = oauth_svc.get_integration(db, store_id=store_id)
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No QuickBooks integration for this store.",
        )
    if integration.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="QuickBooks integration is not connected.",
        )
    return integration


def _load_sync_enabled_mappings(
    db: Session, integration_id: UUID
) -> list[ProductVariantAccountingMapping]:
    """Return the integration's `sync_enabled` mappings, oldest first."""
    return list(
        db.scalars(
            select(ProductVariantAccountingMapping)
            .where(
                ProductVariantAccountingMapping.integration_id
                == integration_id,
                ProductVariantAccountingMapping.sync_enabled.is_(True),
            )
            .order_by(ProductVariantAccountingMapping.created_at)
        ).all()
    )


def _read_quantity_on_hand(
    db: Session, store_id: UUID, variant_id: UUID
) -> int | None:
    """Read NubeRush authoritative quantity for (store, variant).

    Returns None when no inventory record exists — missing is NOT treated as
    zero, so a missing record is skipped rather than pushing a 0 that could
    wrongly zero out the QuickBooks mirror. Read-only: never mutates inventory.
    """
    inventory = db.scalar(
        select(InventoryItem).where(
            InventoryItem.store_id == store_id,
            InventoryItem.variant_id == variant_id,
        )
    )
    if inventory is None:
        return None
    return inventory.quantity_on_hand


def _error_code(exc: QuickBooksClientError) -> str:
    """Map a client error to a short, sanitized machine code (no body/token)."""
    if isinstance(exc, QuickBooksRateLimitError):
        return "rate_limited"
    if isinstance(exc, QuickBooksConfigError):
        return "not_configured"
    return "push_failed"


def _summarize_failures(codes: list[str]) -> str | None:
    """Build a sanitized error summary from machine codes only.

    Carries counts of machine codes — never a token, an auth header, or a raw
    Intuit response body.
    """
    if not codes:
        return None
    counts = Counter(codes)
    parts = [f"{count}x {code}" for code, count in sorted(counts.items())]
    return "QuickBooks inventory push reported failures: " + ", ".join(parts)


# --------------------------------------------------------------------- #
# Preview — read-only, no writes, no QuickBooks call
# --------------------------------------------------------------------- #


def build_inventory_push_preview(
    db: Session, *, store_id: UUID
) -> InventoryPushPreviewResponse:
    """Build a read-only preview of the proposed inventory push.

    Requires a connected integration. Loads `sync_enabled` mappings, reads the
    NubeRush authoritative quantity for each, and proposes a push (or a skip
    when no inventory record exists). Performs NO DB write, NO QuickBooks call,
    NO token decrypt, and creates NO ledger rows. `quickbooks_quantity_on_hand`
    is left None (informational, not fetched here).
    """
    integration = _require_connected_integration(db, store_id)
    mappings = _load_sync_enabled_mappings(db, integration.id)

    items: list[InventoryPushPreviewItem] = []
    to_push = 0
    skipped = 0
    for mapping in mappings:
        quantity = _read_quantity_on_hand(
            db, integration.store_id, mapping.variant_id
        )
        if quantity is None:
            skipped += 1
            action = "skip"
            issue: str | None = _NO_INVENTORY_DETAIL
        else:
            to_push += 1
            action = "push"
            issue = None
        items.append(
            InventoryPushPreviewItem(
                variant_id=mapping.variant_id,
                external_item_id=mapping.external_item_id,
                external_item_name=mapping.external_item_name,
                nube_quantity_on_hand=quantity,
                quickbooks_quantity_on_hand=None,
                proposed_action=action,
                sync_enabled=mapping.sync_enabled,
                issue=issue,
            )
        )

    return InventoryPushPreviewResponse(
        store_id=integration.store_id,
        integration_id=integration.id,
        total_mappings=len(mappings),
        items_to_push=to_push,
        items_skipped=skipped,
        items=items,
    )


# --------------------------------------------------------------------- #
# Confirm — create the ledger, push outbound, close the run
# --------------------------------------------------------------------- #


def _finalize_fatal(
    db: Session,
    log: AccountingSyncLog,
    *,
    seen: int,
    failed: int,
    error_summary: str,
) -> tuple[AccountingSyncLog, list[AccountingSyncLogItem]]:
    """Close a run that failed before any per-item push (no item rows)."""
    log.items_seen = seen
    log.items_failed = failed
    log.status = "failed"
    log.finished_at = _utcnow()
    log.error_summary = error_summary
    db.commit()
    db.refresh(log)
    return log, []


def confirm_inventory_push(
    db: Session, *, store_id: UUID, actor_user_id: UUID | None
) -> tuple[AccountingSyncLog, list[AccountingSyncLogItem]]:
    """Execute a manual inventory push and record the sync ledger.

    Creates one `AccountingSyncLog` (inventory_push / push / manual) and, for
    each `sync_enabled` mapping, pushes the NubeRush authoritative quantity to
    QuickBooks and records an `AccountingSyncLogItem` (updated / skipped /
    failed). Updates `mapping.last_synced_at` only on a successful push and
    `integration.last_sync_at` when at least one push succeeded.

    Terminal status: `succeeded` (no failures), `partial` (some pushed, some
    failed), or `failed` (all failed, or a fatal no-mappings / token / config
    condition). NEVER mutates InventoryItem / InventoryLog / Product /
    ProductVariant and NEVER reads QuickBooks quantity back into NubeRush.
    """
    integration = _require_connected_integration(db, store_id)
    mappings = _load_sync_enabled_mappings(db, integration.id)

    log = AccountingSyncLog(
        store_id=integration.store_id,
        integration_id=integration.id,
        sync_type=_SYNC_TYPE_INVENTORY_PUSH,
        direction=_DIRECTION_PUSH,
        status="running",
        trigger=_TRIGGER_MANUAL,
        started_at=_utcnow(),
        items_seen=0,
        items_created=0,
        items_updated=0,
        items_skipped=0,
        items_failed=0,
        actor_user_id=actor_user_id,
    )
    db.add(log)
    db.flush()  # assign log.id without committing yet

    # Fatal: no sync-enabled mappings to push (no-item condition).
    if not mappings:
        return _finalize_fatal(
            db, log, seen=0, failed=0,
            error_summary="No sync-enabled mappings to push.",
        )

    # Resolve the token + client ONCE. A decrypt/config failure is fatal for the
    # whole run and is recorded as a sanitized ledger failure (no token/body).
    try:
        if not integration.access_token_encrypted:
            raise TokenEncryptionError("missing access token")
        access_token = decrypt_token(integration.access_token_encrypted)
        client = oauth_svc.resolve_quickbooks_client()
    except (TokenEncryptionError, QuickBooksConfigError):
        return _finalize_fatal(
            db, log, seen=len(mappings), failed=len(mappings),
            error_summary="QuickBooks is not available for inventory sync.",
        )

    now = _utcnow()
    items: list[AccountingSyncLogItem] = []
    seen = updated = skipped = failed = 0
    failure_codes: list[str] = []

    for mapping in mappings:
        seen += 1
        quantity = _read_quantity_on_hand(
            db, integration.store_id, mapping.variant_id
        )
        if quantity is None:
            skipped += 1
            items.append(
                AccountingSyncLogItem(
                    sync_log_id=log.id,
                    variant_id=mapping.variant_id,
                    external_item_id=mapping.external_item_id,
                    external_item_name=mapping.external_item_name,
                    outcome="skipped",
                    error_code="no_inventory_record",
                    error_message=_NO_INVENTORY_DETAIL,
                )
            )
            continue

        try:
            client.update_item_quantity(
                access_token=access_token,
                realm_id=integration.realm_id or "",
                external_item_id=mapping.external_item_id,
                quantity_on_hand=float(quantity),
                environment=integration.environment,
            )
        except QuickBooksClientError as exc:
            failed += 1
            code = _error_code(exc)
            failure_codes.append(code)
            items.append(
                AccountingSyncLogItem(
                    sync_log_id=log.id,
                    variant_id=mapping.variant_id,
                    external_item_id=mapping.external_item_id,
                    external_item_name=mapping.external_item_name,
                    outcome="failed",
                    error_code=code,
                    # `str(exc)` is sanitized by contract (status code only).
                    error_message=str(exc),
                )
            )
            continue

        updated += 1
        mapping.last_synced_at = now  # only on a successful push
        items.append(
            AccountingSyncLogItem(
                sync_log_id=log.id,
                variant_id=mapping.variant_id,
                external_item_id=mapping.external_item_id,
                external_item_name=mapping.external_item_name,
                outcome="updated",
                error_code=None,
                error_message=None,
            )
        )

    for item in items:
        db.add(item)

    log.items_seen = seen
    log.items_updated = updated
    log.items_skipped = skipped
    log.items_failed = failed
    log.finished_at = _utcnow()
    if failed == 0:
        log.status = "succeeded"
    elif updated == 0:
        log.status = "failed"
        log.error_summary = _summarize_failures(failure_codes)
    else:
        log.status = "partial"
        log.error_summary = _summarize_failures(failure_codes)

    # Integration bookkeeping: stamp last_sync_at only if something was pushed.
    if updated > 0:
        integration.last_sync_at = log.finished_at

    db.commit()
    db.refresh(log)
    return log, items


# --------------------------------------------------------------------- #
# Ledger reads
# --------------------------------------------------------------------- #


def list_sync_runs(
    db: Session, *, store_id: UUID, limit: int = 50, offset: int = 0
) -> tuple[list[AccountingSyncLog], int]:
    """Return (runs, total) for THIS store only, newest first.

    Tenancy-scoped by `store_id`: store A never sees store B's runs. Read-only.
    """
    where = AccountingSyncLog.store_id == store_id
    total = db.scalar(
        select(func.count()).select_from(AccountingSyncLog).where(where)
    )
    rows = list(
        db.scalars(
            select(AccountingSyncLog)
            .where(where)
            .order_by(AccountingSyncLog.started_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, int(total or 0)


def get_sync_run_detail(
    db: Session, *, run_id: UUID
) -> tuple[AccountingSyncLog, list[AccountingSyncLogItem]]:
    """Return one sync run + its per-item outcomes (admin-global read).

    404 when the run does not exist. Read-only — no secrets, no raw payload.
    """
    log = db.scalar(
        select(AccountingSyncLog).where(AccountingSyncLog.id == run_id)
    )
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found."
        )
    items = list(
        db.scalars(
            select(AccountingSyncLogItem)
            .where(AccountingSyncLogItem.sync_log_id == run_id)
            .order_by(AccountingSyncLogItem.created_at)
        ).all()
    )
    return log, items
