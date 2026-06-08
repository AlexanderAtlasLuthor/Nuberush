"""HTTP layer for inventory items, logs and stock movements.

Thin: parse, authorize, call service, return. Every business rule
(locking, sellability, audit log, atomic mutation) lives in
`app.services.inventory`. The router only enforces:

  - authentication (Bearer)
  - role gates via the S2.3 aliases
  - tenancy on store-scoped paths via require_store_member
  - tenancy on item-scoped paths via _assert_can_access_store
    (store_id is loaded from the item, never trusted from the
    request)

Mapping of access tiers:

  Reads (list inventory, list logs, get item):
      admin / owner / manager / staff   →  allowed
      driver / anon                     →  denied

  Setup + manager-level movements (create item, threshold, status,
  receive, adjust, damage):
      admin / owner / manager           →  allowed
      staff / driver / anon             →  denied

  Staff-level movements (sell, reserve, release, return):
      admin / owner / manager / staff   →  allowed
      driver / anon                     →  denied
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Query
from fastapi import UploadFile
from fastapi import status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.api.deps import require_manager_or_above
from app.api.deps import require_staff_or_above
from app.api.deps import require_store_member
from app.db.models import InventoryStatus
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_db
from app.schemas.inventory import AdjustStockRequest
from app.schemas.inventory import DamageStockRequest
from app.schemas.inventory import InventoryItemCreate
from app.schemas.inventory import InventoryItemListResponse
from app.schemas.inventory import InventoryItemRead
from app.schemas.inventory import InventoryLogRead
from app.schemas.inventory import ReceiveStockRequest
from app.schemas.inventory import ReleaseReservationRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import ReturnStockRequest
from app.schemas.inventory import SaleStockRequest
from app.schemas.inventory_import import InventoryImportConfirmResponse
from app.schemas.inventory_import import InventoryImportPreviewResponse
from app.services import inventory as svc
from app.services import inventory_import as import_svc


router = APIRouter(tags=["inventory"])


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


def _assert_can_access_store(current_user: User, store_id: UUID) -> None:
    """Tenancy gate for /inventory/{item_id}/... endpoints.

    The store_id is loaded from the item (never trusted from the
    request body or path). Admin bypasses; non-admin must have
    caller.store_id == item.store_id. Mirrors the rules enforced by
    require_store_member but operates on already-loaded state.
    """
    if current_user.role == UserRole.admin:
        return
    if current_user.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not bound to a store.",
        )
    if current_user.store_id != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this store.",
        )


def _read_validated_import_upload(file: UploadFile) -> bytes:
    """Validate upload metadata, read the bytes, validate the real size.

    Centralizes the upload contract shared by the preview and confirm
    endpoints. Translates a controlled `InventoryImportValidationError`
    into a clean HTTP error carrying a stable machine `code`. The
    multipart `Content-Length`/`size` is advisory, so the authoritative
    size check runs against the bytes actually read.
    """
    try:
        import_svc.validate_inventory_import_upload_metadata(
            file.filename or "",
            file.content_type,
            file.size if file.size is not None else 1,
        )
        data = file.file.read()
        import_svc.validate_inventory_import_size(len(data))
    except import_svc.InventoryImportValidationError as exc:
        raise _import_error(exc) from exc
    return data


def _import_error(
    exc: import_svc.InventoryImportValidationError,
) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


def _assert_create_missing_allowed(
    current_user: User, create_missing: bool
) -> None:
    """Catalog creation via import is admin-only (F2.27.9).

    The base import gate is `require_manager_or_above`; opting into
    `create_missing` (which creates global Product/ProductVariant rows)
    escalates the requirement to admin. Managers/owners get a 403.
    """
    if create_missing and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only admins can create products and variants during an "
                "inventory import."
            ),
        )


# --------------------------------------------------------------------- #
# Reads (require_staff_or_above; driver/anon denied)
# --------------------------------------------------------------------- #


@router.get(
    "/stores/{store_id}/inventory",
    response_model=InventoryItemListResponse,
    dependencies=[Depends(require_store_member)],
)
def list_store_inventory(
    store_id: UUID,
    low_stock_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> InventoryItemListResponse:
    items = svc.list_inventory_for_store(
        db,
        store_id,
        low_stock_only=low_stock_only,
        limit=limit,
        offset=offset,
    )
    total = svc.count_inventory_for_store(
        db, store_id, low_stock_only=low_stock_only
    )
    return InventoryItemListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/inventory/{item_id}",
    response_model=InventoryItemRead,
)
def get_inventory_item(
    item_id: UUID,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return item


@router.get(
    "/stores/{store_id}/inventory/logs",
    response_model=list[InventoryLogRead],
    dependencies=[Depends(require_store_member)],
)
def list_store_inventory_logs(
    store_id: UUID,
    limit: int = 100,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> list:
    return svc.list_inventory_logs_for_store(db, store_id, limit=limit)


@router.get(
    "/inventory/{item_id}/logs",
    response_model=list[InventoryLogRead],
)
def list_inventory_item_logs(
    item_id: UUID,
    limit: int = 100,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> list:
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.list_inventory_logs_for_item(db, item_id, limit=limit)


# --------------------------------------------------------------------- #
# Setup (require_manager_or_above; staff/driver/anon denied)
# --------------------------------------------------------------------- #


@router.post(
    "/stores/{store_id}/inventory/items",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_store_member)],
)
def create_inventory_item(
    store_id: UUID,
    payload: InventoryItemCreate,
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return svc.create_inventory_item(
        db, store_id, payload, actor_user_id=current_user.id
    )


# --------------------------------------------------------------------- #
# Excel inventory import (F2.27.8; require_manager_or_above)
# --------------------------------------------------------------------- #
#
# Two store-scoped endpoints accept a QuickBooks POS `.xlsx` export as a
# multipart upload. RBAC mirrors the rest of the setup tier:
# require_store_member gates tenancy (admin → any store, owner/manager →
# own store, staff/cross-store → 403) and require_manager_or_above gates
# the role. Preview performs NO DB writes; confirm applies the import in
# a single all-or-nothing transaction and audits via InventoryLog.


@router.post(
    "/stores/{store_id}/inventory/import/preview",
    response_model=InventoryImportPreviewResponse,
    dependencies=[Depends(require_store_member)],
)
def preview_inventory_import(
    store_id: UUID,
    file: UploadFile = File(...),
    create_missing: bool = Form(default=False),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
) -> InventoryImportPreviewResponse:
    _assert_create_missing_allowed(current_user, create_missing)
    data = _read_validated_import_upload(file)
    try:
        workbook = import_svc.parse_quickbooks_inventory_workbook(data)
    except import_svc.InventoryImportValidationError as exc:
        raise _import_error(exc) from exc
    return import_svc.build_inventory_import_preview(
        db, store_id, workbook, create_missing=create_missing
    )


@router.post(
    "/stores/{store_id}/inventory/import/confirm",
    response_model=InventoryImportConfirmResponse,
    dependencies=[Depends(require_store_member)],
)
def confirm_inventory_import(
    store_id: UUID,
    file: UploadFile = File(...),
    create_missing: bool = Form(default=False),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
) -> InventoryImportConfirmResponse:
    _assert_create_missing_allowed(current_user, create_missing)
    data = _read_validated_import_upload(file)
    try:
        workbook = import_svc.parse_quickbooks_inventory_workbook(data)
        return import_svc.confirm_inventory_import(
            db,
            store_id,
            workbook,
            actor_user_id=current_user.id,
            create_missing=create_missing,
        )
    except import_svc.InventoryImportValidationError as exc:
        raise _import_error(exc) from exc


@router.patch(
    "/inventory/{item_id}/threshold",
    response_model=InventoryItemRead,
)
def patch_inventory_threshold(
    item_id: UUID,
    reorder_threshold: Annotated[int, Body(embed=True, ge=0)],
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.update_inventory_threshold(db, item_id, reorder_threshold)


@router.patch(
    "/inventory/{item_id}/status",
    response_model=InventoryItemRead,
)
def patch_inventory_status(
    item_id: UUID,
    new_status: Annotated[InventoryStatus, Body(embed=True, alias="status")],
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.update_inventory_status(db, item_id, new_status)


# --------------------------------------------------------------------- #
# Manager-level movements (require_manager_or_above)
# --------------------------------------------------------------------- #


@router.post(
    "/inventory/{item_id}/receive",
    response_model=InventoryItemRead,
)
def post_receive(
    item_id: UUID,
    payload: ReceiveStockRequest,
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.receive_stock(db, item_id, payload, current_user.id)


@router.post(
    "/inventory/{item_id}/adjust",
    response_model=InventoryItemRead,
)
def post_adjust(
    item_id: UUID,
    payload: AdjustStockRequest,
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.adjust_stock(db, item_id, payload, current_user.id)


@router.post(
    "/inventory/{item_id}/damage",
    response_model=InventoryItemRead,
)
def post_damage(
    item_id: UUID,
    payload: DamageStockRequest,
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.record_damage(db, item_id, payload, current_user.id)


# --------------------------------------------------------------------- #
# Staff-level movements (require_staff_or_above)
# --------------------------------------------------------------------- #


@router.post(
    "/inventory/{item_id}/sell",
    response_model=InventoryItemRead,
)
def post_sell(
    item_id: UUID,
    payload: SaleStockRequest,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.sell_inventory(db, item_id, payload, current_user.id)


@router.post(
    "/inventory/{item_id}/reserve",
    response_model=InventoryItemRead,
)
def post_reserve(
    item_id: UUID,
    payload: ReserveStockRequest,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.reserve_inventory(db, item_id, payload, current_user.id)


@router.post(
    "/inventory/{item_id}/release",
    response_model=InventoryItemRead,
)
def post_release(
    item_id: UUID,
    payload: ReleaseReservationRequest,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.release_reservation(db, item_id, payload, current_user.id)


@router.post(
    "/inventory/{item_id}/return",
    response_model=InventoryItemRead,
)
def post_return(
    item_id: UUID,
    payload: ReturnStockRequest,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    item = svc.get_inventory_item(db, item_id)
    _assert_can_access_store(current_user, item.store_id)
    return svc.return_to_inventory(db, item_id, payload, current_user.id)


# --------------------------------------------------------------------- #
# Admin global feed (F2.18.1)
# --------------------------------------------------------------------- #
#
# Read-only, admin-only, cross-store inventory list. Lives on the
# inventory router so the inventory module owns its admin entry point
# (mirrors `/admin/audit` co-located in the audit router). RBAC is
# `require_admin` only — no tenancy gate, since admins can see every
# store. The store-scoped `GET /stores/{store_id}/inventory` is
# preserved unchanged for non-admin operational use.


@router.get(
    "/admin/inventory",
    response_model=InventoryItemListResponse,
)
def list_admin_inventory_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    store_id: UUID | None = Query(None),
    q: str | None = Query(None, max_length=200),
    low_stock: bool = Query(False),
    product_id: UUID | None = Query(None),
    variant_id: UUID | None = Query(None),
    inventory_status: InventoryStatus | None = Query(None, alias="status"),
) -> InventoryItemListResponse:
    return svc.list_admin_inventory(
        db,
        actor=actor,
        limit=limit,
        offset=offset,
        store_id=store_id,
        q=q,
        low_stock=low_stock,
        product_id=product_id,
        variant_id=variant_id,
        inventory_status=inventory_status,
    )
