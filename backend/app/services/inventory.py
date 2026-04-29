"""Service layer for inventory items, logs and stock movements.

Materializes the rules in `app.domain.inventory_rules`. Routers in
S4.5 will be thin: parse, authorize, call, return.

Transactional contract for every mutation:

  1. Lock the inventory_items row with SELECT ... FOR UPDATE.
  2. Validate (sellability + status + variant active + quantity).
  3. Mutate quantity_on_hand and/or quantity_reserved.
  4. Append exactly one InventoryLog row to the same session.
  5. Commit. On any IntegrityError the rollback discards both the
     mutation and the log row together.

Compliance propagation (banned product → quarantined items) is
NOT implemented here. That belongs to S4.4 in services/products.py.
"""

from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import ProductVariant
from app.db.models import Store
from app.schemas.inventory import AdjustStockRequest
from app.schemas.inventory import DamageStockRequest
from app.schemas.inventory import InventoryItemCreate
from app.schemas.inventory import ReceiveStockRequest
from app.schemas.inventory import ReleaseReservationRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import ReturnStockRequest
from app.schemas.inventory import SaleStockRequest
from app.services.products import assert_product_sellable


# Operational statuses allowed for inventory items in MVP. The legacy
# enum values `reserved` and `sold` are intentionally rejected
# (see inventory_rules §3 and §4): reservation state lives in
# quantity_reserved, sales are implicit (units gone). Allowing those
# values would create two parallel representations of the same fact.
_MVP_OPERATIONAL_STATUSES: frozenset[InventoryStatus] = frozenset(
    {
        InventoryStatus.available,
        InventoryStatus.flagged,
        InventoryStatus.quarantined,
    }
)


# --------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------- #


def _inventory_item_load_options():
    """Eager-load options for the variant + product chain.

    Used by every read path (`list_inventory_for_store`,
    `get_inventory_item`, `_lock_inventory_item`) and by the
    post-mutation re-query so that response serialization never
    triggers per-row lazy loads. `selectinload` issues two extra
    bulk SELECTs regardless of N — `1 (items) + 1 (variants) +
    1 (products)` total — vs. the `2N+1` cost of default lazy
    loading on a list endpoint. See `domain/inventory_rules.py` for
    the broader transactional contract.
    """
    return selectinload(InventoryItem.variant).selectinload(
        ProductVariant.product
    )


def _get_inventory_item_eager(
    db: Session, item_id: UUID
) -> InventoryItem | None:
    """Read an inventory item with `variant` and `variant.product`
    pre-loaded. Returns None when the row is missing — callers
    decide whether that is a 404 (`get_inventory_item`) or an
    invariant violation (post-mutation refresh).

    Does NOT take a lock; not for use inside a mutation transaction.
    """
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.id == item_id)
        .options(_inventory_item_load_options())
    )
    return db.scalar(stmt)


def _refresh_eager(db: Session, item: InventoryItem) -> InventoryItem:
    """Replacement for `db.refresh(item)` in mutation paths.

    After a successful commit, SQLAlchemy expires loaded attributes,
    so accessing `item.variant.product` would lazy-load. Re-querying
    with the eager-load options gives a fully-populated object that
    Pydantic can serialize without further round-trips.

    The row is guaranteed to exist post-commit (the caller just
    mutated it inside the same transaction). The 404 branch covers a
    pathological race window where a concurrent CASCADE delete from
    a parent variant or store removed the row between commit and
    re-query — surfacing it as a clean 404 beats a 500.
    """
    refreshed = _get_inventory_item_eager(db, item.id)
    if refreshed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found.",
        )
    return refreshed


def _lock_inventory_item(db: Session, item_id: UUID) -> InventoryItem:
    """Load the inventory item with a row-level lock and eager-loaded
    variant + product.

    Issues `SELECT ... FOR UPDATE`. The lock is held until the
    surrounding transaction commits or rolls back; concurrent calls
    on the same item serialize at the DB level. The eager-load
    options issue separate (unlocked) SELECTs for the variant and
    product so that downstream sellability checks
    (`_assert_item_operable`, which reads `item.variant.product`)
    do not fire lazy loads inside the locked transaction. Raises 404
    when the row is missing.
    """
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.id == item_id)
        .options(_inventory_item_load_options())
        .with_for_update()
    )
    item = db.scalar(stmt)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found.",
        )
    return item


def _write_inventory_log(
    db: Session,
    *,
    item: InventoryItem,
    movement_type: InventoryMovementType,
    quantity_delta: int,
    quantity_after: int,
    actor_user_id: UUID | None,
    reason: str | None = None,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
) -> InventoryLog:
    """Append an InventoryLog row to the session.

    Does NOT commit. The caller commits as part of the same
    transaction that performed the mutation, so the log row and the
    quantity change land or roll back together.
    """
    log = InventoryLog(
        inventory_item_id=item.id,
        store_id=item.store_id,
        variant_id=item.variant_id,
        performed_by_user_id=actor_user_id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        quantity_after=quantity_after,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.add(log)
    return log


def _assert_item_operable(item: InventoryItem) -> None:
    """Sellability gate for sale and reserve only.

    Three independent checks, each surfaced as 422:
      - underlying product is sellable per S3 rules
      - variant.is_active is True
      - item.status == available

    Receipts, adjustments, damage records, returns and reservation
    releases MUST NOT call this — they are how operators correct or
    rebuild stock that may not currently be sellable.
    """
    variant = item.variant
    product = variant.product

    assert_product_sellable(product)

    if not variant.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Variant is not active.",
        )

    if item.status != InventoryStatus.available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Inventory item status is "
                f"'{item.status.value}'; sale and reserve are blocked."
            ),
        )


def _assert_stock_available(item: InventoryItem, quantity: int) -> None:
    """Compares against quantity_available, never quantity_on_hand.

    See inventory_rules §10. Selling against on_hand alone would let
    the seller hand over units that another customer has already
    reserved.
    """
    available = item.quantity_on_hand - item.quantity_reserved
    if available < quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Insufficient stock: requested {quantity}, "
                f"available {available} "
                f"(on_hand={item.quantity_on_hand}, "
                f"reserved={item.quantity_reserved})."
            ),
        )


def _assert_reserved_available(item: InventoryItem, quantity: int) -> None:
    """Used by release_reservation to make sure we do not push
    quantity_reserved below zero."""
    if item.quantity_reserved < quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot release {quantity} units: only "
                f"{item.quantity_reserved} are reserved."
            ),
        )


def _commit_or_translate(db: Session) -> None:
    """Commit the current transaction or translate IntegrityError
    from the inventory CHECK constraints into a clean 422.

    The DB-level CHECKs (quantity_on_hand >= 0,
    quantity_reserved >= 0, quantity_reserved <= quantity_on_hand,
    quantity_delta != 0, quantity_after >= 0) act as a backstop. The
    service-layer validations should normally catch every violation
    first; this branch exists to make sure clients never see a
    raw psycopg message.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stock mutation violates database constraints.",
        ) from exc


# --------------------------------------------------------------------- #
# Read functions
# --------------------------------------------------------------------- #


def get_inventory_item(db: Session, item_id: UUID) -> InventoryItem:
    """Read a single inventory item with variant + product pre-loaded.

    Eager-loaded so `InventoryItemRead` can serialize the nested
    summary without a follow-up lazy load. Raises 404 when missing.
    """
    item = _get_inventory_item_eager(db, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found.",
        )
    return item


def _inventory_store_filters(
    store_id: UUID,
    low_stock_only: bool,
):
    filters = [InventoryItem.store_id == store_id]
    if low_stock_only:
        filters.append(
            (InventoryItem.quantity_on_hand - InventoryItem.quantity_reserved)
            <= InventoryItem.reorder_threshold
        )
    return tuple(filters)


def list_inventory_for_store(
    db: Session,
    store_id: UUID,
    *,
    low_stock_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[InventoryItem]:
    """List inventory items for a store with variant + product pre-loaded.

    `low_stock_only=True` filters to items where
    `quantity_on_hand - quantity_reserved <= reorder_threshold`,
    so dashboards don't need to compute it client-side.

    Uses `selectinload` for the variant + product chain. Total queries
    are `1 (items) + 1 (variants) + 1 (products) = 3`, regardless of
    how many items the store carries (avoids 2N+1).
    """
    stmt = (
        select(InventoryItem)
        .where(*_inventory_store_filters(store_id, low_stock_only))
        .options(_inventory_item_load_options())
        .order_by(InventoryItem.created_at.asc(), InventoryItem.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


def count_inventory_for_store(
    db: Session,
    store_id: UUID,
    *,
    low_stock_only: bool = False,
) -> int:
    stmt = (
        select(func.count())
        .select_from(InventoryItem)
        .where(*_inventory_store_filters(store_id, low_stock_only))
    )
    return int(db.scalar(stmt) or 0)


def list_inventory_logs_for_store(
    db: Session,
    store_id: UUID,
    *,
    limit: int = 100,
) -> list[InventoryLog]:
    stmt = (
        select(InventoryLog)
        .where(InventoryLog.store_id == store_id)
        .order_by(InventoryLog.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def list_inventory_logs_for_item(
    db: Session,
    item_id: UUID,
    *,
    limit: int = 100,
) -> list[InventoryLog]:
    stmt = (
        select(InventoryLog)
        .where(InventoryLog.inventory_item_id == item_id)
        .order_by(InventoryLog.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


# --------------------------------------------------------------------- #
# Setup functions
# --------------------------------------------------------------------- #


def create_inventory_item(
    db: Session,
    store_id: UUID,
    payload: InventoryItemCreate,
    actor_user_id: UUID | None = None,
) -> InventoryItem:
    """Create a new inventory item for the (store, variant) pair.

    UNIQUE(store_id, variant_id) → 409 on duplicates so a tenant
    cannot accidentally create two rows for the same SKU. A missing
    parent store is surfaced as 404 instead of letting the FK fall
    through as a 500.

    Note: `actor_user_id` is accepted for symmetry with the
    movement functions and to support a future "creation log"; in
    MVP the creation event is not logged separately because no
    quantities mutate yet (the initial fill arrives via a receive
    movement after the row exists).
    """
    if db.get(Store, store_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )

    item = InventoryItem(
        store_id=store_id,
        variant_id=payload.variant_id,
        quantity_on_hand=payload.quantity_on_hand,
        quantity_reserved=payload.quantity_reserved,
        reorder_threshold=payload.reorder_threshold,
        status=payload.status,
    )
    db.add(item)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig).lower() if exc.orig is not None else ""
        if "uq_inventory_store_variant" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inventory item already exists for this store and variant.",
            ) from exc
        if "product_variants" in message or "variant_id" in message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Variant not found.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Inventory item violates database constraints.",
        ) from exc

    return _refresh_eager(db, item)


def update_inventory_threshold(
    db: Session,
    item_id: UUID,
    reorder_threshold: int,
) -> InventoryItem:
    if reorder_threshold < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="reorder_threshold must be >= 0.",
        )

    item = _lock_inventory_item(db, item_id)
    item.reorder_threshold = reorder_threshold
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def update_inventory_status(
    db: Session,
    item_id: UUID,
    new_status: InventoryStatus,
) -> InventoryItem:
    """Set a new operational status. Only `available`, `flagged` and
    `quarantined` are accepted in MVP per inventory_rules §4.

    The lock is taken so a status flip cannot interleave with an
    in-flight sale or reserve on the same item.
    """
    if new_status not in _MVP_OPERATIONAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"InventoryStatus.{new_status.value} is not a valid MVP "
                f"operational status."
            ),
        )

    item = _lock_inventory_item(db, item_id)
    item.status = new_status
    _commit_or_translate(db)
    return _refresh_eager(db, item)


# --------------------------------------------------------------------- #
# Movement functions
# --------------------------------------------------------------------- #


def receive_stock(
    db: Session,
    item_id: UUID,
    payload: ReceiveStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """Stock arriving from a supplier or transfer in.

    Allowed regardless of item.status — operators may receive
    units even into a flagged or quarantined slot in order to
    reconstitute records. quantity_reserved is untouched.
    """
    item = _receive_stock_locked(db, item_id, payload, actor_user_id)
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def _receive_stock_locked(
    db: Session,
    item_id: UUID,
    payload: ReceiveStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """No-commit core of receive_stock. Suitable for composing inside
    an outer transaction (e.g. orders coordinator).

    Same lock + validation + log semantics as the public function;
    the caller controls commit/rollback.
    """
    item = _lock_inventory_item(db, item_id)

    item.quantity_on_hand += payload.quantity

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.receipt,
        quantity_delta=payload.quantity,
        quantity_after=item.quantity_on_hand,
        actor_user_id=actor_user_id,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )

    return item


def adjust_stock(
    db: Session,
    item_id: UUID,
    payload: AdjustStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """Manual correction with a signed delta. Reason is mandatory at
    the schema layer.

    The new quantity_on_hand cannot drop below quantity_reserved —
    that would mean the store has reservations on stock it no
    longer holds. We surface that as 422 explicitly because the DB
    CHECK would otherwise fire with a less actionable message.
    """
    item = _adjust_stock_locked(db, item_id, payload, actor_user_id)
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def _adjust_stock_locked(
    db: Session,
    item_id: UUID,
    payload: AdjustStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """No-commit core of adjust_stock."""
    item = _lock_inventory_item(db, item_id)

    new_qoh = item.quantity_on_hand + payload.delta
    if new_qoh < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Adjustment would drop quantity_on_hand below zero "
                f"(current={item.quantity_on_hand}, delta={payload.delta})."
            ),
        )
    if new_qoh < item.quantity_reserved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Adjustment would leave quantity_on_hand ({new_qoh}) "
                f"below quantity_reserved ({item.quantity_reserved})."
            ),
        )

    item.quantity_on_hand = new_qoh

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.adjustment,
        quantity_delta=payload.delta,
        quantity_after=item.quantity_on_hand,
        actor_user_id=actor_user_id,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )
    return item


def record_damage(
    db: Session,
    item_id: UUID,
    payload: DamageStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """Records units lost (broken, expired, spilled). Reason
    mandatory at the schema layer. quantity_reserved is untouched."""
    item = _record_damage_locked(db, item_id, payload, actor_user_id)
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def _record_damage_locked(
    db: Session,
    item_id: UUID,
    payload: DamageStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """No-commit core of record_damage."""
    item = _lock_inventory_item(db, item_id)

    new_qoh = item.quantity_on_hand - payload.quantity
    if new_qoh < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Damage exceeds quantity_on_hand "
                f"(on_hand={item.quantity_on_hand}, "
                f"requested={payload.quantity})."
            ),
        )
    if new_qoh < item.quantity_reserved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Damage would leave quantity_on_hand ({new_qoh}) "
                f"below quantity_reserved ({item.quantity_reserved})."
            ),
        )

    item.quantity_on_hand = new_qoh

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.damage,
        quantity_delta=-payload.quantity,
        quantity_after=item.quantity_on_hand,
        actor_user_id=actor_user_id,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )
    return item


def sell_inventory(
    db: Session,
    item_id: UUID,
    payload: SaleStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """Sale path. Triggers the full sellability gate:
      - product is sellable per S3 rules
      - variant.is_active
      - item.status == available
      - quantity_available >= requested

    Compares requested units against (on_hand - reserved), never
    against on_hand alone (inventory_rules §10).
    """
    item = _sell_inventory_locked(db, item_id, payload, actor_user_id)
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def _sell_inventory_locked(
    db: Session,
    item_id: UUID,
    payload: SaleStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """No-commit core of sell_inventory."""
    item = _lock_inventory_item(db, item_id)

    _assert_item_operable(item)
    _assert_stock_available(item, payload.quantity)

    item.quantity_on_hand -= payload.quantity

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.sale,
        quantity_delta=-payload.quantity,
        quantity_after=item.quantity_on_hand,
        actor_user_id=actor_user_id,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )
    return item


def reserve_inventory(
    db: Session,
    item_id: UUID,
    payload: ReserveStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """Reserve units for a pending order. Same sellability gate as
    sale plus a quantity_available check; the reservation increases
    quantity_reserved without touching quantity_on_hand."""
    item = _reserve_inventory_locked(db, item_id, payload, actor_user_id)
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def _reserve_inventory_locked(
    db: Session,
    item_id: UUID,
    payload: ReserveStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """No-commit core of reserve_inventory. Used by orders coordinator
    so multi-item reservations can roll back atomically."""
    item = _lock_inventory_item(db, item_id)

    _assert_item_operable(item)
    _assert_stock_available(item, payload.quantity)

    item.quantity_reserved += payload.quantity

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.reservation,
        quantity_delta=payload.quantity,
        quantity_after=item.quantity_reserved,
        actor_user_id=actor_user_id,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )
    return item


def release_reservation(
    db: Session,
    item_id: UUID,
    payload: ReleaseReservationRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """Release of a previously made reservation. Decreases
    quantity_reserved without touching quantity_on_hand. Logged as
    `cancellation` per inventory_rules §3 — the released units
    return to the available pool."""
    item = _release_reservation_locked(db, item_id, payload, actor_user_id)
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def _release_reservation_locked(
    db: Session,
    item_id: UUID,
    payload: ReleaseReservationRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """No-commit core of release_reservation. Used by orders coordinator
    on cancellation paths."""
    item = _lock_inventory_item(db, item_id)

    _assert_reserved_available(item, payload.quantity)

    item.quantity_reserved -= payload.quantity

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.cancellation,
        quantity_delta=-payload.quantity,
        quantity_after=item.quantity_reserved,
        actor_user_id=actor_user_id,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )
    return item


def return_to_inventory(
    db: Session,
    item_id: UUID,
    payload: ReturnStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """Customer return. Reason mandatory at the schema layer.
    quantity_on_hand increases; quantity_reserved is untouched.
    Allowed regardless of item.status (a banned product can still
    accept its inventory back)."""
    item = _return_to_inventory_locked(db, item_id, payload, actor_user_id)
    _commit_or_translate(db)
    return _refresh_eager(db, item)


def _return_to_inventory_locked(
    db: Session,
    item_id: UUID,
    payload: ReturnStockRequest,
    actor_user_id: UUID | None,
) -> InventoryItem:
    """No-commit core of return_to_inventory. Used by orders coordinator
    on returned-status transitions."""
    item = _lock_inventory_item(db, item_id)

    item.quantity_on_hand += payload.quantity

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.return_,
        quantity_delta=payload.quantity,
        quantity_after=item.quantity_on_hand,
        actor_user_id=actor_user_id,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
    )
    return item


# --------------------------------------------------------------------- #
# Composite movement: consume reservation (used by orders on DELIVERED)
# --------------------------------------------------------------------- #


def _consume_reserved_inventory_locked(
    db: Session,
    item_id: UUID,
    quantity: int,
    *,
    actor_user_id: UUID | None,
    order_id: UUID,
    expected_store_id: UUID | None = None,
    reason: str | None = None,
) -> InventoryItem:
    """Atomically consume `quantity` units that were previously
    reserved for an order: decrement BOTH quantity_reserved AND
    quantity_on_hand by the same amount.

    Intended for the orders coordinator's DELIVERED transition
    (see app.domain.orders_rules §3). Writes ONE inventory_log row
    of movement_type=sale tied to the order via reference_id.

    Validations:
      - quantity > 0
      - item exists (via the row lock)
      - if expected_store_id is given, item.store_id must match
        (defense-in-depth against cross-store consumption bugs)
      - quantity_reserved >= quantity (cannot consume more than was
        reserved)
      - quantity_on_hand >= quantity (cannot push qoh negative;
        DB CHECK is a backstop)
      - sellability gate (compliance, variant.is_active,
        item.status == available) — re-asserted at consume time so
        a product banned BETWEEN reserve and delivered cannot be
        sold (orders_rules §7).

    NO commit. NO refresh. Caller controls transaction boundary.
    """
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="quantity must be greater than zero.",
        )

    item = _lock_inventory_item(db, item_id)

    if expected_store_id is not None and item.store_id != expected_store_id:
        # Defensive: the orders coordinator must resolve the right
        # inventory_item via (store_id, variant_id) UNIQUE pair. A
        # mismatch here means the caller picked the wrong row and
        # would consume from another store's stock.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Inventory item does not belong to the expected store.",
        )

    _assert_item_operable(item)

    if item.quantity_reserved < quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot consume {quantity} units: only "
                f"{item.quantity_reserved} are reserved."
            ),
        )
    if item.quantity_on_hand < quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot consume {quantity} units: only "
                f"{item.quantity_on_hand} on hand."
            ),
        )

    item.quantity_reserved -= quantity
    item.quantity_on_hand -= quantity

    _write_inventory_log(
        db,
        item=item,
        movement_type=InventoryMovementType.sale,
        quantity_delta=-quantity,
        quantity_after=item.quantity_on_hand,
        actor_user_id=actor_user_id,
        reason=reason,
        reference_type="order",
        reference_id=order_id,
    )
    return item


def consume_reserved_inventory(
    db: Session,
    item_id: UUID,
    quantity: int,
    *,
    actor_user_id: UUID | None,
    order_id: UUID,
    expected_store_id: UUID | None = None,
    reason: str | None = None,
) -> InventoryItem:
    """Public wrapper around `_consume_reserved_inventory_locked`
    that commits in its own transaction. Useful for direct
    administrative use; the orders coordinator will call the
    locked helper instead so the consume is atomic with the order
    state transition and the order audit log row.
    """
    item = _consume_reserved_inventory_locked(
        db,
        item_id,
        quantity,
        actor_user_id=actor_user_id,
        order_id=order_id,
        expected_store_id=expected_store_id,
        reason=reason,
    )
    _commit_or_translate(db)
    return _refresh_eager(db, item)
