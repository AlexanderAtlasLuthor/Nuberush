"""HTTP layer for the admin QuickBooks accounting integration (F2.27.9.B/.C).

Admin-only routes that drive the OAuth connect/callback/disconnect handshake
(F2.27.9.B) plus read-only item discovery and variant<->item mapping CRUD
(F2.27.9.C). They authorize via `require_admin`, validate the store, delegate to
`app.services.accounting.{oauth,mappings}`, and return ONLY read-safe schemas —
no token material, ciphertext, client secret, OAuth code, or raw Intuit body
ever leaves these routes.

Scope: OAuth connection + item discovery + mapping management (F2.27.9.B/.C)
plus the manual inventory push preview/confirm + sync-run ledger reads
(F2.27.9.D). The push is outbound and NubeRush-authoritative: NubeRush
`InventoryItem.quantity_on_hand` is mirrored TO QuickBooks; QuickBooks quantity
is never read back and NubeRush inventory is never mutated here. There is NO
scheduler / background job / automatic sync — every sync is a manual,
admin-initiated request.

Callback auth note
------------------
`GET /admin/accounting/quickbooks/callback` is the Intuit browser redirect
target. A redirected browser cannot carry the app's Supabase `Authorization:
Bearer` header, so this one route cannot use `require_admin`. Its security comes
instead from the signed `state`: the state is minted ONLY inside the
admin-gated connect endpoint, is HMAC-signed, short-lived, and bound to
`store_id` + `actor_user_id`. The callback verifies the signature + expiry and
derives the store and actor from the VERIFIED state — never from a query
parameter. A missing/forged/expired state is rejected. This is the standard,
repo-consistent secure OAuth callback pattern; no insecure workaround is used.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import get_quickbooks_settings
from app.core.permissions import assert_active_store_for_assignment
from app.db.models import User
from app.db.session import get_db
from app.schemas.accounting import AccountingIntegrationStatus
from app.schemas.accounting import AccountingMappingCreateRequest
from app.schemas.accounting import AccountingMappingListResponse
from app.schemas.accounting import AccountingMappingRead
from app.schemas.accounting import AccountingMappingUpdateRequest
from app.schemas.accounting import AccountingProvider
from app.schemas.accounting import AccountingSyncLogDetailResponse
from app.schemas.accounting import AccountingSyncLogItemRead
from app.schemas.accounting import AccountingSyncLogListResponse
from app.schemas.accounting import AccountingSyncLogRead
from app.schemas.accounting import InventoryPushConfirmRequest
from app.schemas.accounting import InventoryPushConfirmResponse
from app.schemas.accounting import InventoryPushPreviewRequest
from app.schemas.accounting import InventoryPushPreviewResponse
from app.schemas.accounting import QuickBooksItemListResponse
from app.schemas.accounting_oauth import QuickBooksCallbackResponse
from app.schemas.accounting_oauth import QuickBooksConnectResponse
from app.schemas.accounting_oauth import QuickBooksDisconnectResponse
from app.schemas.accounting_oauth import QuickBooksIntegrationStatusResponse
from app.services.accounting import mappings as mappings_svc
from app.services.accounting import oauth as oauth_svc
from app.services.accounting import sync as sync_svc
from app.services.accounting.oauth import OAuthStateError
from app.services.accounting.quickbooks_client import QuickBooksClientError
from app.services.accounting.quickbooks_client import QuickBooksConfigError


router = APIRouter(tags=["admin-accounting"])


def _config_error(detail: str) -> HTTPException:
    # 503: the integration is not configured/available, not a client fault.
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail
    )


# --------------------------------------------------------------------- #
# Connect — mint signed state + return the Intuit consent URL
# --------------------------------------------------------------------- #


@router.post(
    "/admin/stores/{store_id}/accounting/quickbooks/connect",
    response_model=QuickBooksConnectResponse,
)
def connect_quickbooks_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuickBooksConnectResponse:
    assert_active_store_for_assignment(db, store_id)
    try:
        state = oauth_svc.mint_state(
            store_id=store_id, actor_user_id=actor.id
        )
        authorize_url = oauth_svc.build_authorize_url(state=state)
    except QuickBooksConfigError as exc:
        raise _config_error(str(exc)) from exc
    settings = get_quickbooks_settings()
    return QuickBooksConnectResponse(
        store_id=store_id,
        authorize_url=authorize_url,
        state_ttl_seconds=int(settings.quickbooks_oauth_state_ttl_seconds),
    )


# --------------------------------------------------------------------- #
# Callback — verify state, exchange code, persist encrypted tokens
# --------------------------------------------------------------------- #


@router.get(
    "/admin/accounting/quickbooks/callback",
    response_model=QuickBooksCallbackResponse,
)
def quickbooks_callback_endpoint(
    db: Session = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    realm_id: str | None = Query(default=None, alias="realmId"),
    error: str | None = Query(default=None),
) -> QuickBooksCallbackResponse:
    # Intuit signalled a denial/error: reject without echoing the value.
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QuickBooks authorization was not granted.",
        )
    if not code or not state or not realm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required callback parameters.",
        )

    try:
        integration = oauth_svc.exchange_callback_code(
            db, code=code, realm_id=realm_id, state=state
        )
    except OAuthStateError as exc:
        # Tampered / expired / missing-binding state.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except QuickBooksConfigError as exc:
        raise _config_error(str(exc)) from exc
    except QuickBooksClientError as exc:
        # Upstream OAuth/transport failure — bare, secret-free message.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return QuickBooksCallbackResponse(
        integration_id=integration.id,
        store_id=integration.store_id,
        provider=AccountingProvider(integration.provider),
        status=AccountingIntegrationStatus(integration.status),
        environment=integration.environment,
        realm_id=integration.realm_id,
        connected=integration.status == "connected",
        created_at=integration.created_at,
        last_sync_at=integration.last_sync_at,
    )


# --------------------------------------------------------------------- #
# Disconnect — best-effort revoke + null tokens
# --------------------------------------------------------------------- #


@router.post(
    "/admin/stores/{store_id}/accounting/quickbooks/disconnect",
    response_model=QuickBooksDisconnectResponse,
)
def disconnect_quickbooks_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuickBooksDisconnectResponse:
    assert_active_store_for_assignment(db, store_id)
    integration = oauth_svc.disconnect_integration(db, store_id=store_id)
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No QuickBooks integration for this store.",
        )
    return QuickBooksDisconnectResponse(
        integration_id=integration.id,
        store_id=integration.store_id,
        provider=AccountingProvider(integration.provider),
        status=AccountingIntegrationStatus(integration.status),
        connected=integration.status == "connected",
        disconnected_at=integration.disconnected_at,
    )


# --------------------------------------------------------------------- #
# Integration status
# --------------------------------------------------------------------- #


@router.get(
    "/admin/stores/{store_id}/accounting/quickbooks/integration",
    response_model=QuickBooksIntegrationStatusResponse,
)
def quickbooks_integration_status_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuickBooksIntegrationStatusResponse:
    assert_active_store_for_assignment(db, store_id)
    integration = oauth_svc.get_integration(db, store_id=store_id)
    if integration is None:
        return QuickBooksIntegrationStatusResponse(
            store_id=store_id,
            connected=False,
            status=AccountingIntegrationStatus.disconnected,
        )
    return QuickBooksIntegrationStatusResponse(
        store_id=integration.store_id,
        connected=integration.status == "connected",
        status=AccountingIntegrationStatus(integration.status),
        integration_id=integration.id,
        environment=integration.environment,
        realm_id=integration.realm_id,
        created_at=integration.created_at,
        disconnected_at=integration.disconnected_at,
        last_sync_at=integration.last_sync_at,
    )


# --------------------------------------------------------------------- #
# F2.27.9.C — item discovery + variant <-> item mapping
# --------------------------------------------------------------------- #


@router.get(
    "/admin/stores/{store_id}/accounting/quickbooks/items",
    response_model=QuickBooksItemListResponse,
)
def list_quickbooks_items_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuickBooksItemListResponse:
    assert_active_store_for_assignment(db, store_id)
    items = mappings_svc.list_quickbooks_items(db, store_id=store_id)
    return QuickBooksItemListResponse(items=items, total=len(items))


@router.get(
    "/admin/stores/{store_id}/accounting/quickbooks/mappings",
    response_model=AccountingMappingListResponse,
)
def list_accounting_mappings_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AccountingMappingListResponse:
    assert_active_store_for_assignment(db, store_id)
    rows, total = mappings_svc.list_mappings(
        db, store_id=store_id, limit=limit, offset=offset
    )
    return AccountingMappingListResponse(
        items=[AccountingMappingRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/admin/stores/{store_id}/accounting/quickbooks/mappings",
    response_model=AccountingMappingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_accounting_mapping_endpoint(
    store_id: UUID,
    payload: AccountingMappingCreateRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AccountingMappingRead:
    assert_active_store_for_assignment(db, store_id)
    mapping = mappings_svc.create_mapping(db, store_id=store_id, payload=payload)
    return AccountingMappingRead.model_validate(mapping)


@router.patch(
    "/admin/stores/{store_id}/accounting/quickbooks/mappings/{mapping_id}",
    response_model=AccountingMappingRead,
)
def update_accounting_mapping_endpoint(
    store_id: UUID,
    mapping_id: UUID,
    payload: AccountingMappingUpdateRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AccountingMappingRead:
    assert_active_store_for_assignment(db, store_id)
    mapping = mappings_svc.update_mapping(
        db, store_id=store_id, mapping_id=mapping_id, payload=payload
    )
    return AccountingMappingRead.model_validate(mapping)


# --------------------------------------------------------------------- #
# F2.27.9.D — manual inventory push preview + confirm + sync-run ledger
# --------------------------------------------------------------------- #


@router.post(
    "/admin/stores/{store_id}/accounting/quickbooks/sync/preview",
    response_model=InventoryPushPreviewResponse,
)
def preview_inventory_push_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    payload: InventoryPushPreviewRequest | None = None,
) -> InventoryPushPreviewResponse:
    # Read-only: no DB write, no QuickBooks call. `payload` is an empty,
    # extra-forbidding body so a smuggled quantity/override field 422s.
    assert_active_store_for_assignment(db, store_id)
    return sync_svc.build_inventory_push_preview(db, store_id=store_id)


@router.post(
    "/admin/stores/{store_id}/accounting/quickbooks/sync/confirm",
    response_model=InventoryPushConfirmResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_inventory_push_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    payload: InventoryPushConfirmRequest | None = None,
) -> InventoryPushConfirmResponse:
    assert_active_store_for_assignment(db, store_id)
    log, items = sync_svc.confirm_inventory_push(
        db, store_id=store_id, actor_user_id=actor.id
    )
    return InventoryPushConfirmResponse(
        log=AccountingSyncLogRead.model_validate(log),
        items=[AccountingSyncLogItemRead.model_validate(i) for i in items],
    )


@router.get(
    "/admin/stores/{store_id}/accounting/quickbooks/sync-runs",
    response_model=AccountingSyncLogListResponse,
)
def list_sync_runs_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AccountingSyncLogListResponse:
    assert_active_store_for_assignment(db, store_id)
    rows, total = sync_svc.list_sync_runs(
        db, store_id=store_id, limit=limit, offset=offset
    )
    return AccountingSyncLogListResponse(
        items=[AccountingSyncLogRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/accounting/sync-runs/{run_id}",
    response_model=AccountingSyncLogDetailResponse,
)
def get_sync_run_detail_endpoint(
    run_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AccountingSyncLogDetailResponse:
    # Admin-global read (no store_id in the path): admin-only, and the response
    # exposes no token / ciphertext / raw QuickBooks payload.
    log, items = sync_svc.get_sync_run_detail(db, run_id=run_id)
    return AccountingSyncLogDetailResponse(
        log=AccountingSyncLogRead.model_validate(log),
        items=[AccountingSyncLogItemRead.model_validate(i) for i in items],
    )
