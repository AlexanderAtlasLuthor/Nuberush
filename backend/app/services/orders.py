"""Service layer for orders — the transaction coordinator.

Materializes the rules in `app.domain.orders_rules` (FROZEN for S5).
This module owns the order lifecycle, the totals computation, the
audit log writes and the integration with the inventory ``_locked``
helpers from S5.3.

Transactional contract (orders_rules §9):

  - This module is the COORDINATOR. It opens a single transaction per
    write operation, calls inventory ``_locked`` helpers (which must
    NOT commit), writes the audit log row, and commits exactly once
    at the end.
  - On any failure mid-flow, the coordinator rolls back the whole
    transaction. There is no partial state — no Order row, no
    OrderItem rows, no inventory mutations, no inventory_log rows
    and no order_audit_log row land on disk.
  - Concurrency is handled by the inventory row lock that
    ``_lock_inventory_item`` already takes inside every ``_locked``
    helper. This module does not introduce a new lock.

Trust boundary (orders_rules §2):

  - The frontend supplies ``variant_id`` + ``quantity`` per line and
    an ``idempotency_key`` per request. Everything else (totals,
    snapshots, inventory binding, lifecycle timestamps, status,
    audit log) is computed or resolved server-side. Schemas with
    ``extra="forbid"`` enforce that at the API boundary; this module
    enforces it again by ignoring everything except the contract
    fields.

Money (orders_rules §5):

  - All money is ``Decimal`` end-to-end. Totals are recomputed from
    DB-resolved unit prices on every create. ``tax_amount = 0`` is
    the MVP contract.

Compliance (orders_rules §7):

  - ``assert_product_sellable`` is the canonical gate. It is invoked
    on CREATE (via ``_reserve_inventory_locked`` -> ``_assert_item_operable``)
    and re-invoked on DELIVERED (via
    ``_consume_reserved_inventory_locked`` -> ``_assert_item_operable``).
    Cancel and return paths skip the gate by design.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.db.models import DriverDeliveryOperationalState
from app.db.models import DriverDeliveryOperationalStateValue
from app.db.models import DriverDeliveryReturn
from app.db.models import DriverDeliveryReturnState
from app.db.models import InventoryItem
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderDriverAssignment
from app.db.models import OrderDriverAssignmentStatus
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.inventory import ReleaseReservationRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import ReturnStockRequest
from app.schemas.orders import OrderCancelRequest
from app.schemas.orders import OrderCreate
from app.schemas.orders import OrderListResponse
from app.schemas.orders import OrderReturnRequest
from app.schemas.orders import OrderStatusUpdate
from app.schemas.orders import StoreConfirmDriverReturnRequest
from app.services import inventory as inv
from app.services.operational_audit import TARGET_DELIVERY_ASSIGNMENT
from app.services.operational_audit import write_operational_audit_log


# Action strings written to OrderAuditLog.action. Kept here so callers
# of the audit log API can match against them without magic strings.
ACTION_ORDER_CREATED = "order_created"
ACTION_STATUS_CHANGED = "status_changed"
ACTION_ORDER_CANCELED = "order_canceled"
ACTION_ORDER_DELIVERED = "order_delivered"
ACTION_ORDER_RETURNED = "order_returned"


# Allowed lifecycle transitions (orders_rules §3, §6). Mapping
# previous_status -> set of valid new_status values. ``canceled`` and
# ``returned`` are terminal (absent from the keys → no transition out).
_ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.pending: frozenset(
        {OrderStatus.accepted, OrderStatus.canceled}
    ),
    OrderStatus.accepted: frozenset(
        {OrderStatus.preparing, OrderStatus.canceled}
    ),
    OrderStatus.preparing: frozenset(
        {OrderStatus.ready, OrderStatus.canceled}
    ),
    OrderStatus.ready: frozenset(
        {
            OrderStatus.out_for_delivery,
            OrderStatus.delivered,
            OrderStatus.canceled,
        }
    ),
    OrderStatus.out_for_delivery: frozenset(
        {OrderStatus.delivered, OrderStatus.canceled}
    ),
    OrderStatus.delivered: frozenset({OrderStatus.returned}),
}


# Statuses from which a cancel is permitted. Cancel from delivered or
# returned must use the return flow instead.
_CANCELABLE_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.pending,
        OrderStatus.accepted,
        OrderStatus.preparing,
        OrderStatus.ready,
        OrderStatus.out_for_delivery,
    }
)


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _commit_or_translate(db: Session) -> None:
    """Commit and translate IntegrityError into a clean 4xx.

    Mirrors the pattern used by inventory service. The orders module's
    schema-layer + service-layer validations should normally catch
    every violation first; this branch shields clients from raw
    psycopg messages if anything slips through (e.g. a concurrent
    duplicate idempotency_key insert).
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig).lower() if exc.orig is not None else ""
        if "uq_orders_store_idempotency_key" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate idempotency_key for this store.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order mutation violates database constraints.",
        ) from exc


def _resolve_inventory_item(
    db: Session, store_id: UUID, variant_id: UUID
) -> InventoryItem:
    """Resolve the inventory item that backs a given variant in a store.

    Uses UNIQUE(store_id, variant_id) so the resolution is unambiguous.
    Resolving by ``variant_id`` alone would be a cross-tenant bug
    (orders_rules §1) — callers MUST pass the order's store_id.
    """
    stmt = select(InventoryItem).where(
        InventoryItem.store_id == store_id,
        InventoryItem.variant_id == variant_id,
    )
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"No inventory item exists for variant {variant_id} "
                f"in this store."
            ),
        )
    return item


def _calculate_order_totals(
    order_items: list[OrderItem],
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (subtotal, tax, total) from already-snapshotted lines.

    ``tax_amount = 0`` in MVP (orders_rules §5). ``total_amount =
    subtotal_amount + tax_amount``.
    """
    subtotal: Decimal = sum(
        (item.line_total for item in order_items),
        start=Decimal("0.00"),
    )
    tax = Decimal("0.00")
    total = subtotal + tax
    return subtotal, tax, total


def _assert_valid_transition(
    previous_status: OrderStatus, new_status: OrderStatus
) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(previous_status, frozenset())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid transition {previous_status.value} -> "
                f"{new_status.value}."
            ),
        )


def _write_order_audit_log(
    db: Session,
    order: Order,
    *,
    previous_status: OrderStatus | None,
    new_status: OrderStatus,
    action: str,
    reason: str | None,
    actor_user_id: UUID | None,
) -> OrderAuditLog:
    """Append one OrderAuditLog row to the session. Does NOT commit."""
    audit = OrderAuditLog(
        order_id=order.id,
        store_id=order.store_id,
        performed_by_user_id=actor_user_id,
        previous_status=previous_status,
        new_status=new_status,
        action=action,
        reason=reason,
    )
    db.add(audit)
    return audit


def _order_read_load_options():
    """Eager-load every relationship needed by OrderRead responses."""
    return selectinload(Order.items).selectinload(
        OrderItem.variant
    ).selectinload(ProductVariant.product)


def _load_order(db: Session, order_id: UUID) -> Order:
    """Load an order with its items eagerly. Raises 404 if missing."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(_order_read_load_options())
    )
    order = db.scalar(stmt)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )
    return order


def _find_existing_idempotent_order(
    db: Session, store_id: UUID, idempotency_key: str
) -> Order | None:
    stmt = (
        select(Order)
        .where(
            Order.store_id == store_id,
            Order.idempotency_key == idempotency_key,
        )
        .options(_order_read_load_options())
    )
    return db.scalar(stmt)


# --------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------- #


def _apply_order_list_filters(
    stmt,
    *,
    store_id: UUID,
    status: OrderStatus | None = None,  # noqa: A002 - public arg name
    created_from: datetime | None = None,
    created_to: datetime | None = None,
):
    stmt = stmt.where(Order.store_id == store_id)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if created_from is not None:
        stmt = stmt.where(Order.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(Order.created_at <= created_to)
    return stmt


def get_order(db: Session, order_id: UUID) -> Order:
    return _load_order(db, order_id)


def list_orders_for_store(
    db: Session,
    store_id: UUID,
    *,
    status: OrderStatus | None = None,  # noqa: A002 — public arg name
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Order]:
    stmt = select(Order).options(_order_read_load_options())
    stmt = _apply_order_list_filters(
        stmt,
        store_id=store_id,
        status=status,
        created_from=created_from,
        created_to=created_to,
    )
    stmt = (
        stmt.order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


def count_orders_for_store(
    db: Session,
    store_id: UUID,
    *,
    status: OrderStatus | None = None,  # noqa: A002 - public arg name
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> int:
    stmt = select(func.count()).select_from(Order)
    stmt = _apply_order_list_filters(
        stmt,
        store_id=store_id,
        status=status,
        created_from=created_from,
        created_to=created_to,
    )
    return int(db.scalar(stmt) or 0)


# --------------------------------------------------------------------- #
# Admin global feed (F2.18.1B)
# --------------------------------------------------------------------- #


def _apply_admin_order_filters(
    stmt,
    *,
    store_id: UUID | None,
    order_status: OrderStatus | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    """Attach the F2.18.1B admin filter set to a SELECT on Order.

    Distinct from `_apply_order_list_filters` because the admin path
    accepts an *optional* `store_id` (cross-store when omitted) and
    intentionally has no store-scoped requirement. The store-scoped
    helper stays unchanged so the existing `/stores/{store_id}/orders`
    behavior is preserved byte-for-byte.
    """
    if store_id is not None:
        stmt = stmt.where(Order.store_id == store_id)
    if order_status is not None:
        stmt = stmt.where(Order.status == order_status)
    if date_from is not None:
        stmt = stmt.where(Order.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Order.created_at <= date_to)
    return stmt


def list_admin_orders(
    db: Session,
    *,
    actor: User,
    store_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    order_status: OrderStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> OrderListResponse:
    """Global admin orders feed (F2.18.1B).

    Admin-only entry point. Cross-store read with optional `store_id`
    scope. Reuses `OrderRead` and `OrderListResponse` unchanged. Sort
    is `created_at DESC, id ASC` (deterministic; most recent orders
    first, with id ASC as the stable tie-breaker — consistent with the
    rest of the admin namespace).

    Behavior:

      - Non-admin actor → 403 (HTTPException).
      - `store_id` provided and not found → 404. Inactive stores are
        explicitly allowed (admin retains visibility into deactivated
        stores), matching `list_admin_audit` and `list_admin_inventory`
        precedent.
      - `store_id` omitted → returns orders across every store.
      - `order_status` exact match on `Order.status`.
      - `date_from` / `date_to` apply as inclusive bounds on
        `Order.created_at` (>= and <=, matching the existing
        store-scoped `_apply_order_list_filters` semantics).
      - Pagination: `1 <= limit <= 200`, `offset >= 0` (enforced at
        the route layer via `Query(...)`). `total` is computed
        pre-pagination.
      - Eager-loads `items` → `variant` → `product` via
        `_order_read_load_options()` so the response can be serialized
        without N+1 lazy reads.

    Read-only. No mutation, no audit log writes, no inventory side
    effects. The store-scoped `list_orders_for_store` and
    `count_orders_for_store` are untouched.

    The `q` filter is intentionally **not** implemented in F2.18.1B:
    the Order model has no clean text-search target (no name/code
    field; `idempotency_key` and `notes` are operational metadata, not
    user-facing search keys). Skipping it keeps the admin surface
    aligned with the F2.18.0 contract §8.2 for `/admin/orders`.
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )

    if store_id is not None:
        store = db.scalar(select(Store).where(Store.id == store_id))
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found.",
            )

    filter_kwargs = dict(
        store_id=store_id,
        order_status=order_status,
        date_from=date_from,
        date_to=date_to,
    )

    count_stmt = _apply_admin_order_filters(
        select(func.count()).select_from(Order),
        **filter_kwargs,
    )
    total = int(db.scalar(count_stmt) or 0)

    items_stmt = _apply_admin_order_filters(
        select(Order).options(_order_read_load_options()),
        **filter_kwargs,
    )
    items_stmt = (
        items_stmt.order_by(Order.created_at.desc(), Order.id.asc())
        .limit(limit)
        .offset(offset)
    )
    items = list(db.scalars(items_stmt).all())

    return OrderListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def list_order_audit_logs(
    db: Session, order_id: UUID
) -> list[OrderAuditLog]:
    """Return every audit row for an order ordered by created_at asc.

    Raises 404 if the order itself does not exist so callers do not
    receive an empty list for a non-existent order.
    """
    if db.get(Order, order_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )
    stmt = (
        select(OrderAuditLog)
        .where(OrderAuditLog.order_id == order_id)
        .order_by(OrderAuditLog.created_at.asc())
    )
    return list(db.scalars(stmt).all())


# --------------------------------------------------------------------- #
# Reservation helpers (used by create_order)
# --------------------------------------------------------------------- #


def _reserve_order_items(
    db: Session,
    order: Order,
    payload_items,
    actor_user_id: UUID | None,
) -> list[OrderItem]:
    """Reserve every line item and create OrderItem rows.

    For each line:
      1. Resolve the inventory_item via (store_id, variant_id).
      2. Call ``_reserve_inventory_locked`` (which validates
         sellability, item.status and stock availability).
      3. Snapshot ``unit_price`` from ``ProductVariant.price`` and
         compute ``line_total = unit_price * quantity``.
      4. Build the OrderItem row.

    Does NOT commit. The caller commits once after the audit log is
    written. If any line raises, the caller must roll back.
    """
    created: list[OrderItem] = []
    for line in payload_items:
        variant = db.get(ProductVariant, line.variant_id)
        if variant is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Variant {line.variant_id} not found.",
            )

        item = _resolve_inventory_item(db, order.store_id, line.variant_id)

        inv._reserve_inventory_locked(
            db,
            item.id,
            ReserveStockRequest(
                quantity=line.quantity,
                reference_type="order",
                reference_id=order.id,
            ),
            actor_user_id,
        )

        unit_price: Decimal = variant.price
        line_total = unit_price * line.quantity

        order_item = OrderItem(
            order_id=order.id,
            variant_id=line.variant_id,
            inventory_item_id=item.id,
            quantity=line.quantity,
            unit_price=unit_price,
            line_total=line_total,
        )
        db.add(order_item)
        created.append(order_item)
    return created


def _consume_order_reservations(
    db: Session, order: Order, actor_user_id: UUID | None
) -> None:
    """Consume every line item's reservation atomically (DELIVERED).

    Each line uses ``_consume_reserved_inventory_locked`` so the call
    re-checks sellability — protecting against the compliance race
    where a product is banned between reserve and deliver
    (orders_rules §7). Cross-store consumption is blocked via
    ``expected_store_id``.
    """
    for line in order.items:
        inv._consume_reserved_inventory_locked(
            db,
            line.inventory_item_id,
            line.quantity,
            actor_user_id=actor_user_id,
            order_id=order.id,
            expected_store_id=order.store_id,
        )


def _release_order_reservations(
    db: Session, order: Order, actor_user_id: UUID | None
) -> None:
    """Release every line item's reservation (CANCEL)."""
    for line in order.items:
        inv._release_reservation_locked(
            db,
            line.inventory_item_id,
            ReleaseReservationRequest(
                quantity=line.quantity,
                reference_type="order",
                reference_id=order.id,
            ),
            actor_user_id,
        )


def _return_order_items_to_inventory(
    db: Session,
    order: Order,
    actor_user_id: UUID | None,
    *,
    reason: str,
) -> None:
    """Replenish ``quantity_on_hand`` for every line (RETURN)."""
    for line in order.items:
        inv._return_to_inventory_locked(
            db,
            line.inventory_item_id,
            ReturnStockRequest(
                quantity=line.quantity,
                reason=reason,
                reference_type="order",
                reference_id=order.id,
            ),
            actor_user_id,
        )


def _recheck_order_sellability(db: Session, order: Order) -> None:
    """Re-run sellability gate per item before DELIVERED.

    The actual gate fires inside ``_consume_reserved_inventory_locked``
    via ``_assert_item_operable``. This helper exists for symmetry
    with the rules document; calling it explicitly before the consume
    loop would double-check the same items. We rely on the consume
    loop to keep the audit log consistent (sellability failure
    aborts the delivered transition cleanly).
    """
    # No-op: gate lives in the consume helper. See orders_rules §7.
    return None


# --------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------- #


def create_order(
    db: Session,
    store_id: UUID,
    payload: OrderCreate,
    actor_user_id: UUID | None,
    *,
    customer_user_id: UUID | None = None,
) -> Order:
    """Create a pending order and reserve its inventory atomically.

    Single transaction (orders_rules §9). Sequence:

      1. Idempotency check: existing (store_id, idempotency_key) →
         return existing order, no mutation.
      2. Validate store exists.
      3. Build the Order row with status=pending and default totals.
      4. Reserve every line item (validates sellability + stock,
         resolves inventory_item, snapshots unit_price).
      5. Compute totals from snapshotted line_totals.
      6. Write order_created audit log.
      7. Commit once.

    On any failure the whole transaction is rolled back: no Order, no
    OrderItem, no reservation, no inventory_log, no audit_log.
    """
    existing = _find_existing_idempotent_order(
        db, store_id, payload.idempotency_key
    )
    if existing is not None:
        return existing

    if db.get(Store, store_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )

    order = Order(
        store_id=store_id,
        customer_user_id=customer_user_id,
        idempotency_key=payload.idempotency_key,
        status=OrderStatus.pending,
        subtotal_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
        notes=payload.notes,
    )
    db.add(order)
    # Flush so the Order has an id we can reference from inventory
    # logs and order items without committing.
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig).lower() if exc.orig is not None else ""
        if "uq_orders_store_idempotency_key" in message:
            replay = _find_existing_idempotent_order(
                db, store_id, payload.idempotency_key
            )
            if replay is not None:
                return replay
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate idempotency_key for this store.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order creation violates database constraints.",
        ) from exc

    try:
        order_items = _reserve_order_items(
            db, order, payload.items, actor_user_id
        )
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order creation violates database constraints.",
        )

    subtotal, tax, total = _calculate_order_totals(order_items)
    order.subtotal_amount = subtotal
    order.tax_amount = tax
    order.total_amount = total

    _write_order_audit_log(
        db,
        order,
        previous_status=None,
        new_status=OrderStatus.pending,
        action=ACTION_ORDER_CREATED,
        reason=None,
        actor_user_id=actor_user_id,
    )

    _commit_or_translate(db)
    return _load_order(db, order.id)


# --------------------------------------------------------------------- #
# State transitions
# --------------------------------------------------------------------- #


def transition_order_status(
    db: Session,
    order_id: UUID,
    payload: OrderStatusUpdate,
    actor_user_id: UUID | None,
) -> Order:
    """Forward state transitions other than cancel/return.

    Routes ``ready/out_for_delivery → delivered`` through the
    inventory consume path; routes ``→ canceled`` callers to the
    dedicated ``cancel_order`` endpoint with a 422 (cancel requires
    a reason). Pure status-only transitions only set the matching
    timestamp field.
    """
    if payload.new_status == OrderStatus.canceled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Use the cancel endpoint to cancel an order.",
        )
    if payload.new_status == OrderStatus.returned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Use the return endpoint to return an order.",
        )

    order = _load_order(db, order_id)
    previous_status = order.status
    _assert_valid_transition(previous_status, payload.new_status)

    if payload.new_status == OrderStatus.delivered:
        _consume_order_reservations(db, order, actor_user_id)
        order.delivered_at = _utcnow()
        action = ACTION_ORDER_DELIVERED
    else:
        if payload.new_status == OrderStatus.accepted:
            order.accepted_at = _utcnow()
        action = ACTION_STATUS_CHANGED

    order.status = payload.new_status

    _write_order_audit_log(
        db,
        order,
        previous_status=previous_status,
        new_status=payload.new_status,
        action=action,
        reason=payload.reason,
        actor_user_id=actor_user_id,
    )

    _commit_or_translate(db)
    return _load_order(db, order.id)


def _cancel_order_core(
    db: Session,
    order: Order,
    reason: str,
    actor_user_id: UUID | None,
) -> None:
    """Non-committing cancel mechanics for a loaded order.

    Validates the transition, releases every line reservation (no
    ``quantity_on_hand`` change), sets ``status = canceled`` /
    ``canceled_at`` / ``cancel_reason`` and writes the audit row. The CALLER
    owns the transaction and commits exactly once — this lets the store
    return-confirmation bridge (Dr.1.2.H) cancel the order atomically alongside
    its DriverDeliveryReturn confirmation. Behaviour is identical to the
    pre-existing inline cancel mechanics; no new inventory code.
    """
    previous_status = order.status
    if previous_status not in _CANCELABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot cancel an order in status "
                f"'{previous_status.value}'."
            ),
        )
    _assert_valid_transition(previous_status, OrderStatus.canceled)

    _release_order_reservations(db, order, actor_user_id)

    order.status = OrderStatus.canceled
    order.canceled_at = _utcnow()
    order.cancel_reason = reason

    _write_order_audit_log(
        db,
        order,
        previous_status=previous_status,
        new_status=OrderStatus.canceled,
        action=ACTION_ORDER_CANCELED,
        reason=reason,
        actor_user_id=actor_user_id,
    )


def cancel_order(
    db: Session,
    order_id: UUID,
    payload: OrderCancelRequest,
    actor_user_id: UUID | None,
) -> Order:
    """Cancel an order from any pre-delivered status.

    Releases the reservation on every line item, sets
    ``status = canceled``, ``canceled_at`` and ``cancel_reason``,
    writes the audit log row and commits once.
    """
    order = _load_order(db, order_id)
    _cancel_order_core(db, order, payload.reason, actor_user_id)
    _commit_or_translate(db)
    return _load_order(db, order.id)


def return_order(
    db: Session,
    order_id: UUID,
    payload: OrderReturnRequest,
    actor_user_id: UUID | None,
) -> Order:
    """Mark a delivered order as returned and replenish stock.

    Only allowed from ``delivered`` (orders_rules §3). Replenishes
    ``quantity_on_hand`` for every line via
    ``_return_to_inventory_locked``, sets ``returned_at``, writes the
    audit log and commits once.
    """
    order = _load_order(db, order_id)
    previous_status = order.status
    if previous_status != OrderStatus.delivered:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot return an order in status "
                f"'{previous_status.value}'."
            ),
        )
    _assert_valid_transition(previous_status, OrderStatus.returned)

    _return_order_items_to_inventory(
        db, order, actor_user_id, reason=payload.reason
    )

    order.status = OrderStatus.returned
    order.returned_at = _utcnow()

    _write_order_audit_log(
        db,
        order,
        previous_status=previous_status,
        new_status=OrderStatus.returned,
        action=ACTION_ORDER_RETURNED,
        reason=payload.reason,
        actor_user_id=actor_user_id,
    )

    _commit_or_translate(db)
    return _load_order(db, order.id)


# --------------------------------------------------------------------- #
# Driver completion bridge (Dr.1.2.E)
# --------------------------------------------------------------------- #


def complete_order_via_driver(
    db: Session,
    order_id: UUID,
    actor_user_id: UUID | None,
) -> Order:
    """Driver-originated commercial completion: ready/out_for_delivery ->
    delivered (Dr.1.2.E bridge).

    This is the ONLY sanctioned way for the driver layer to promote an order to
    ``delivered``: the driver service proposes the outcome and this orders
    authority validates and applies the commercial change. It reuses the
    existing delivered machinery unchanged — the same ``_assert_valid_transition``
    gate, the same ``_consume_order_reservations`` inventory path (so stock is
    consumed exactly as the staff-driven ``transition_order_status`` does), and
    the same ``_write_order_audit_log`` (action ``order_delivered``, carrying the
    driver's ``actor_user_id``). It does NOT relax ``_ALLOWED_TRANSITIONS`` and
    NEVER permits pending/accepted/preparing -> delivered.

    Atomicity: this bridge does NOT commit. The caller (the driver service)
    owns the transaction so the operational-state advance, the assignment
    closure, this commercial change, the inventory consume, and the audit row
    all land or roll back together.

    The order row is locked FOR UPDATE. An already-``delivered`` order is
    idempotent (returned unchanged, never re-consumed or re-audited). Any status
    other than ready / out_for_delivery / delivered is a 409 (the order is not
    commercially completable yet). A missing order is a 404.
    """
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(_order_read_load_options())
        .with_for_update()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    previous_status = order.status
    if previous_status == OrderStatus.delivered:
        # Idempotent: already delivered — never re-consume inventory or write a
        # duplicate audit row.
        return order

    if previous_status not in (
        OrderStatus.ready,
        OrderStatus.out_for_delivery,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Order cannot be completed by the driver from status "
                f"'{previous_status.value}'."
            ),
        )

    # Reuse the exact delivered machinery (no behavioural change): assert the
    # transition, consume the reservation, set delivered_at, flip status, audit.
    _assert_valid_transition(previous_status, OrderStatus.delivered)
    _consume_order_reservations(db, order, actor_user_id)
    order.delivered_at = _utcnow()
    order.status = OrderStatus.delivered
    _write_order_audit_log(
        db,
        order,
        previous_status=previous_status,
        new_status=OrderStatus.delivered,
        action=ACTION_ORDER_DELIVERED,
        reason="completed by driver",
        actor_user_id=actor_user_id,
    )
    return order


# --------------------------------------------------------------------- #
# Store return confirmation (Dr.1.2.H)
# --------------------------------------------------------------------- #
#
# An authorized store actor (manager-or-above; tenancy enforced at the route)
# confirms physical receipt of a failed-delivery return after the driver has
# reached returned_to_store / returned_pending_confirmation. In one transaction
# this stamps the DriverDeliveryReturn as confirmed and cancels the order
# (releasing the held reservation via the existing cancel core — quantity_on_hand
# is never touched, no restock, no consume). The operational state is left at
# returned_to_store, and the OrderAuditLog is written by the cancel core.

_CANCEL_REASON_DRIVER_RETURN = "driver return confirmed by store"


def _load_locked_order_for_confirm(db: Session, order_id: UUID) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(_order_read_load_options())
        .with_for_update()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )
    return order


def confirm_driver_return_for_store(
    db: Session,
    order_id: UUID,
    payload: StoreConfirmDriverReturnRequest,
    current_user: User,
) -> tuple[Order, DriverDeliveryReturn]:
    """Confirm store receipt of a returned failed delivery (Dr.1.2.H).

    Stamps the order's DriverDeliveryReturn as ``confirmed`` (with
    ``confirmed_at`` / ``confirmed_by_user_id``) and cancels the order via the
    non-committing cancel core (releasing the held reservation, no
    quantity_on_hand change), then closes the assignment to ``canceled`` — all
    in a single transaction. The operational state stays ``returned_to_store``.

    Gates: the order must exist; a DriverDeliveryReturn must exist for it; its
    ``return_state`` must be ``returned_pending_confirmation`` (else 409); the
    assignment's operational state must be ``returned_to_store`` (else 409); the
    assignment must still be ``started`` (else 409); the order must be cancelable
    (else 422). Idempotent: an already-``confirmed`` return whose order is
    ``canceled`` and assignment ``canceled`` returns the existing pair without a
    second release or duplicate audit; any inconsistent confirmed state is a 409.
    A missing order or return record is a 404. Tenancy is enforced by the route.
    """
    order = _load_locked_order_for_confirm(db, order_id)

    driver_return = db.scalars(
        select(DriverDeliveryReturn)
        .where(DriverDeliveryReturn.order_id == order_id)
        .order_by(DriverDeliveryReturn.created_at.desc())
        .with_for_update()
    ).first()
    if driver_return is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No driver return to confirm for this order.",
        )

    assignment = db.scalar(
        select(OrderDriverAssignment)
        .where(OrderDriverAssignment.id == driver_return.assignment_id)
        .with_for_update()
    )
    operational_state = db.scalar(
        select(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id
            == driver_return.assignment_id
        )
        .with_for_update()
    )

    confirmed = DriverDeliveryReturnState.confirmed.value
    returned_pending = (
        DriverDeliveryReturnState.returned_pending_confirmation.value
    )
    returned_to_store = (
        DriverDeliveryOperationalStateValue.returned_to_store.value
    )
    assignment_canceled = OrderDriverAssignmentStatus.canceled.value
    assignment_started = OrderDriverAssignmentStatus.started.value

    # Idempotent replay: an already-confirmed, fully-consistent return.
    if driver_return.return_state == confirmed:
        consistent = (
            order.status == OrderStatus.canceled
            and assignment is not None
            and assignment.status == assignment_canceled
            and driver_return.confirmed_at is not None
            and driver_return.confirmed_by_user_id is not None
        )
        if consistent:
            db.rollback()
            return order, driver_return
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Driver return confirmation is in an inconsistent state.",
        )

    if driver_return.return_state != returned_pending:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Driver return is not awaiting confirmation "
                f"(return_state '{driver_return.return_state}')."
            ),
        )

    if assignment is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No driver return to confirm for this order.",
        )

    if (
        operational_state is None
        or operational_state.state != returned_to_store
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery is not in returned_to_store state.",
        )

    if assignment.status != assignment_started:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Assignment cannot confirm return from status "
                f"'{assignment.status}'."
            ),
        )

    # Cancelability is gated BEFORE any mutation so a non-cancelable order
    # leaves the return record untouched (no partial confirm).
    if order.status not in _CANCELABLE_STATUSES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot confirm a driver return for an order in status "
                f"'{order.status.value}'."
            ),
        )

    # Snapshot pre-mutation discriminators for the audit before/after.
    prev_order_status = order.status.value
    prev_return_state = driver_return.return_state

    # Stamp the custody record as confirmed (the only place this is allowed).
    now = _utcnow()
    driver_return.return_state = confirmed
    driver_return.confirmed_at = now
    driver_return.confirmed_by_user_id = current_user.id
    if payload.note is not None:
        driver_return.note = payload.note

    # Cancel the order through the shared, non-committing cancel core: releases
    # the held reservation (no quantity_on_hand change) and writes the audit row.
    # Raises 422 if the order is not cancelable (e.g. delivered).
    _cancel_order_core(
        db, order, _CANCEL_REASON_DRIVER_RETURN, current_user.id
    )

    # Close the assignment; the operational state stays returned_to_store.
    assignment.status = assignment_canceled

    # Redacted operational audit (Dr.1.2.I.a) — same transaction, non-committing.
    write_operational_audit_log(
        db,
        actor_user_id=current_user.id,
        target_type=TARGET_DELIVERY_ASSIGNMENT,
        target_id=assignment.id,
        action="delivery_return_confirmed",
        store_id=order.store_id,
        before={
            "status": prev_order_status,
            "return_state": prev_return_state,
        },
        after={
            "status": OrderStatus.canceled.value,
            "return_state": confirmed,
        },
        metadata={
            "source": "confirm_driver_return",
            "reason": "store_confirmed_return",
        },
    )

    _commit_or_translate(db)
    db.refresh(driver_return)
    return _load_order(db, order_id), driver_return
