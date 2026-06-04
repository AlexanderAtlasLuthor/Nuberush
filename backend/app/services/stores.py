"""Service layer for stores (F2.14.2 + F2.17.2).

F2.14.2 owned the store-profile flow that powers Store Settings:
`get_store` and a partial `update_store` over the two editable fields
(`name`, `timezone`).

F2.17.2 adds the Admin Stores backend foundation: `list_stores`,
`create_store`, `deactivate_store`, `reactivate_store`. These four
operations are admin-only and route through the same `/stores`
namespace; `/admin/stores` is intentionally NOT introduced (mirrors
F2.15's choice to extend `/auth/users` instead of `/admin/users`).

Conventions (consistent with `app.services.users` and
`app.services.products`):

- Each function takes a Session as its first argument and is
  responsible for its own commit/rollback. Routers do not need to
  catch IntegrityError — this layer translates it to HTTP 422.

- RBAC for the four new functions lives in this module via
  `_assert_admin_caller`, mirroring `app.services.users`. This avoids
  inventing a new guard and keeps the source of truth for "who can do
  what" co-located with the operation. The route layer in F2.17.3
  may still apply existing dependencies (e.g. `require_store_member`)
  on GET/PATCH paths but does not need to duplicate the admin check.

- Lifecycle (`deactivate_store` / `reactivate_store`) is NOT
  idempotent. Already-inactive deactivate → 422; already-active
  reactivate → 422. This matches the F2.17.0 contract: callers must
  see explicit conflict rather than a silent no-op.

- `update_store` PATCH semantics are unchanged. Lifecycle flows
  exclusively through the dedicated deactivate/reactivate endpoints,
  not through PATCH. `code` remains immutable post-create (the
  `StoreUpdate` schema does not expose it).

Out of scope for this module (deferred):
  - Owner/user assignment at create time.
  - Audit trail for create / lifecycle changes (no `StoreAuditLog`,
    no `AuditSource.store` enum value in F2.17).
  - Address/contact/preferences/business_hours/status fields
    (would require a migration).
  - Bulk operations.
"""

from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.stores import StoreCreate
from app.schemas.stores import StoreListResponse
from app.schemas.stores import StoreRead
from app.schemas.stores import StoreUpdate
from app.services.operational_audit import write_operational_audit_log


_MAX_LIST_LIMIT = 100


def build_store_audit_snapshot(store: Store) -> dict[str, object]:
    """Small, stable, allow-listed snapshot of a store for the operational
    audit trail (F2.26.1.D).

    Only the real `Store` columns the operational-audit allow-list permits
    for a `store` target (`name`, `code`, `is_active`, `timezone`). No
    invented fields (slug/status/address/phone do not exist on the model),
    and no secrets — stores carry none. All values are JSON-safe scalars;
    the writer re-applies the allow-list + redaction as defense-in-depth.
    """
    return {
        "name": store.name,
        "code": store.code,
        "is_active": store.is_active,
        "timezone": store.timezone,
    }


def _assert_admin_caller(actor: User) -> None:
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _assert_list_pagination(limit: int, offset: int) -> None:
    if limit < 1 or limit > _MAX_LIST_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"limit must be between 1 and {_MAX_LIST_LIMIT}."
            ),
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be greater than or equal to 0.",
        )


def get_store(db: Session, store_id: UUID) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )
    return store


def update_store(
    db: Session,
    store_id: UUID,
    payload: StoreUpdate,
    *,
    actor: User,
) -> Store:
    """Apply a partial update to a store profile.

    Only fields that the caller actually sent are mutated
    (`exclude_unset=True`). The `StoreUpdate` schema restricts those
    to `name` and `timezone`; this function does not enforce that
    list itself, so any future schema change must remain consistent
    with the F2.14 contract.

    F2.26.1.D: `actor` is now required so the mutation can leave an
    operational audit event (`store_updated`) in the SAME transaction
    as the field change. The route already resolves the caller via
    `require_owner_or_admin` and threads it here.
    """
    store = get_store(db, store_id)
    before = build_store_audit_snapshot(store)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(store, field, value)

    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="store",
        target_id=store.id,
        action="store_updated",
        store_id=store.id,
        before=before,
        after=build_store_audit_snapshot(store),
        metadata={"source": "stores.update_store"},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Store update violates database constraints.",
        ) from exc
    db.refresh(store)
    return store


def list_stores(
    db: Session,
    *,
    actor: User,
    limit: int = 25,
    offset: int = 0,
    is_active: bool | None = None,
    q: str | None = None,
) -> StoreListResponse:
    """Paginated admin list of stores.

    Admin-only. Non-admin callers receive 403 before any DB work.

    Filters:
      - `is_active`: optional bool. `None` means "any state".
      - `q`: optional ILIKE over `name` and `code`. Trimmed; empty or
        whitespace-only collapses to no filter ("search what you
        mean") so accidental whitespace from form payloads does not
        produce an empty result set.

    Sort: `created_at DESC`, with `id ASC` as a stable tie-breaker so
    pages remain deterministic across identical timestamps.

    `total` is computed before pagination so callers can render totals
    without re-querying.
    """
    _assert_admin_caller(actor)
    _assert_list_pagination(limit, offset)

    stmt = select(Store)
    count_stmt = select(func.count()).select_from(Store)

    if is_active is not None:
        stmt = stmt.where(Store.is_active.is_(is_active))
        count_stmt = count_stmt.where(Store.is_active.is_(is_active))

    if q is not None:
        trimmed = q.strip()
        if trimmed:
            pattern = f"%{trimmed}%"
            search = or_(
                Store.name.ilike(pattern),
                Store.code.ilike(pattern),
            )
            stmt = stmt.where(search)
            count_stmt = count_stmt.where(search)

    stmt = stmt.order_by(Store.created_at.desc(), Store.id.asc())
    stmt = stmt.limit(limit).offset(offset)

    rows = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0

    return StoreListResponse(
        items=[StoreRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def create_store(
    db: Session,
    *,
    actor: User,
    payload: StoreCreate,
) -> StoreRead:
    """Admin-only store creation.

    Stores are active on creation (the model's server default backs
    this, but we set it explicitly to make intent obvious). `code`
    is unique at the DB layer; a duplicate surfaces as HTTP 422 via
    IntegrityError translation, with a clean rollback so the session
    remains usable.

    No owner assignment and no audit event in F2.17 — both are
    deliberately deferred.
    """
    _assert_admin_caller(actor)

    store = Store(
        name=payload.name,
        code=payload.code,
        timezone=payload.timezone,
        is_active=True,
    )
    db.add(store)
    try:
        # Flush first so the server-generated id is populated and any
        # duplicate-code violation surfaces here. The operational audit
        # row is then appended to the SAME transaction as the store
        # insert: one commit persists both, and any failure rolls back
        # both, so a rolled-back create never leaves an audit row.
        db.flush()
        write_operational_audit_log(
            db,
            actor_user_id=actor.id,
            target_type="store",
            target_id=store.id,
            action="store_created",
            store_id=store.id,
            before=None,
            after=build_store_audit_snapshot(store),
            metadata={"source": "stores.create_store"},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Store creation violates database constraints.",
        ) from exc
    db.refresh(store)
    return StoreRead.model_validate(store)


def deactivate_store(
    db: Session,
    *,
    actor: User,
    store_id: UUID,
) -> StoreRead:
    """Admin-only deactivation.

    Not idempotent: deactivating an already-inactive store raises
    422. The conflict makes accidental double-clicks visible to the
    caller and keeps audit reasoning crisp once a store-lifecycle
    audit source lands in a later phase.
    """
    _assert_admin_caller(actor)
    store = get_store(db, store_id)
    if not store.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Store is already inactive.",
        )
    before = build_store_audit_snapshot(store)
    store.is_active = False

    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="store",
        target_id=store.id,
        action="store_deactivated",
        store_id=store.id,
        before=before,
        after=build_store_audit_snapshot(store),
        metadata={"source": "stores.deactivate_store"},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Store deactivation violates database constraints.",
        ) from exc
    db.refresh(store)
    return StoreRead.model_validate(store)


def reactivate_store(
    db: Session,
    *,
    actor: User,
    store_id: UUID,
) -> StoreRead:
    """Admin-only reactivation.

    Not idempotent: reactivating an already-active store raises 422.
    Symmetric to `deactivate_store`.
    """
    _assert_admin_caller(actor)
    store = get_store(db, store_id)
    if store.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Store is already active.",
        )
    before = build_store_audit_snapshot(store)
    store.is_active = True

    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="store",
        target_id=store.id,
        action="store_activated",
        store_id=store.id,
        before=before,
        after=build_store_audit_snapshot(store),
        metadata={"source": "stores.reactivate_store"},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Store reactivation violates database constraints.",
        ) from exc
    db.refresh(store)
    return StoreRead.model_validate(store)
