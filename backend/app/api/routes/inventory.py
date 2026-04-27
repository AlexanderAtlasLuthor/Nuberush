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
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

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
from app.schemas.inventory import InventoryItemRead
from app.schemas.inventory import InventoryLogRead
from app.schemas.inventory import ReceiveStockRequest
from app.schemas.inventory import ReleaseReservationRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import ReturnStockRequest
from app.schemas.inventory import SaleStockRequest
from app.services import inventory as svc


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


# --------------------------------------------------------------------- #
# Reads (require_staff_or_above; driver/anon denied)
# --------------------------------------------------------------------- #


@router.get(
    "/stores/{store_id}/inventory",
    response_model=list[InventoryItemRead],
    dependencies=[Depends(require_store_member)],
)
def list_store_inventory(
    store_id: UUID,
    low_stock_only: bool = False,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> list:
    return svc.list_inventory_for_store(
        db, store_id, low_stock_only=low_stock_only
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
