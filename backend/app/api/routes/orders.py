"""HTTP layer for the orders module (S5.6).

Thin: parse, authorize, call service, return. Every business rule
(idempotency, totals, sellability gate, audit log, atomic mutation,
state machine) lives in `app.services.orders` and the inventory
``_locked`` helpers that service uses. The router only enforces:

  - authentication (Bearer)
  - role gates via the S2.3 aliases
  - tenancy on store-scoped paths via ``require_store_member``
  - tenancy on order-scoped paths via ``_assert_can_access_store``
    (store_id is loaded from the order, never trusted from the
    request)

Mapping of access tiers (orders_rules §6):

  Reads (list, get, audit logs) and pre-delivered transitions
  (create, accepted, preparing, ready, out_for_delivery, delivered):
      admin / owner / manager / staff   →  allowed
      driver / anon                     →  denied

  Cancel and return (operational sign-off required):
      admin / owner / manager           →  allowed
      staff / driver / anon             →  denied
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy.orm import Session

from app.api.deps import require_manager_or_above
from app.api.deps import require_staff_or_above
from app.api.deps import require_store_member
from app.db.models import OrderStatus
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_db
from app.schemas.orders import OrderAuditLogRead
from app.schemas.orders import OrderCancelRequest
from app.schemas.orders import OrderCreate
from app.schemas.orders import OrderListResponse
from app.schemas.orders import OrderRead
from app.schemas.orders import OrderReturnRequest
from app.schemas.orders import OrderStatusUpdate
from app.services import orders as svc


router = APIRouter(tags=["orders"])


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


def _assert_can_access_store(current_user: User, store_id: UUID) -> None:
    """Tenancy gate for /orders/{order_id}/... endpoints.

    The store_id is loaded from the order (never trusted from the
    request body or path). Admin bypasses; non-admin must have
    caller.store_id == order.store_id. Mirrors the rules enforced by
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
# Create + list (store-scoped)
# --------------------------------------------------------------------- #


@router.post(
    "/stores/{store_id}/orders",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_store_member)],
)
def create_order(
    store_id: UUID,
    payload: OrderCreate,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    return svc.create_order(
        db,
        store_id,
        payload,
        actor_user_id=current_user.id,
        customer_user_id=current_user.id,
    )


@router.get(
    "/stores/{store_id}/orders",
    response_model=OrderListResponse,
    dependencies=[Depends(require_store_member)],
)
def list_store_orders(
    store_id: UUID,
    # Aliased to "status" so the query param is `?status=pending` while
    # the local name avoids shadowing the imported `fastapi.status`.
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> OrderListResponse:
    items = svc.list_orders_for_store(
        db,
        store_id,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    total = svc.count_orders_for_store(
        db,
        store_id,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
    )
    return OrderListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------- #
# Per-order reads (order-scoped)
# --------------------------------------------------------------------- #


@router.get(
    "/orders/{order_id}",
    response_model=OrderRead,
)
def get_order(
    order_id: UUID,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    order = svc.get_order(db, order_id)
    _assert_can_access_store(current_user, order.store_id)
    return order


@router.get(
    "/orders/{order_id}/audit-logs",
    response_model=list[OrderAuditLogRead],
)
def list_order_audit_logs(
    order_id: UUID,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> list:
    # Load first so the tenancy gate can use order.store_id; service
    # itself will 404 if the order is missing.
    order = svc.get_order(db, order_id)
    _assert_can_access_store(current_user, order.store_id)
    return svc.list_order_audit_logs(db, order_id)


# --------------------------------------------------------------------- #
# State transitions
# --------------------------------------------------------------------- #


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderRead,
)
def patch_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
):
    # Service rejects ``→ canceled`` / ``→ returned`` here with 422 and
    # routes operators to the dedicated cancel/return endpoints.
    order = svc.get_order(db, order_id)
    _assert_can_access_store(current_user, order.store_id)
    return svc.transition_order_status(
        db, order_id, payload, actor_user_id=current_user.id
    )


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderRead,
)
def post_cancel_order(
    order_id: UUID,
    payload: OrderCancelRequest,
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    order = svc.get_order(db, order_id)
    _assert_can_access_store(current_user, order.store_id)
    return svc.cancel_order(
        db, order_id, payload, actor_user_id=current_user.id
    )


@router.post(
    "/orders/{order_id}/return",
    response_model=OrderRead,
)
def post_return_order(
    order_id: UUID,
    payload: OrderReturnRequest,
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    order = svc.get_order(db, order_id)
    _assert_can_access_store(current_user, order.store_id)
    return svc.return_order(
        db, order_id, payload, actor_user_id=current_user.id
    )
