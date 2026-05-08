"""Service layer for stores (F2.14.2).

Owns the business logic for the store-profile flow that powers Store
Settings. This module is deliberately thin: read-by-id and a partial
update over the two editable fields (`name`, `timezone`).

Conventions (consistent with `app.services.products`):

- Each function takes a Session as its first argument and is
  responsible for its own commit/rollback. Routers do not need to
  catch IntegrityError — this layer translates it to HTTP 422.

- `get_store` raises HTTPException(404) when the row is missing so
  routers can `raise` directly without extra branching.

- `update_store` applies `payload.model_dump(exclude_unset=True)`,
  which keeps PATCH semantics: omitted fields are not touched. The
  schema (`StoreUpdate` with `extra="forbid"`) is the gate that
  prevents non-editable fields (`id`, `code`, `is_active`,
  `created_at`, `updated_at`) from reaching this function — never
  rely on a deny-list here.

Out of scope for this module (handled elsewhere or deferred):
  - RBAC and tenancy guards (route layer in F2.14.3 via the
    existing `require_owner_or_admin` + `require_store_member`
    dependencies).
  - Audit logging (no `StoreAuditLog` exists in F2.14).
  - Lifecycle changes to `is_active` (admin tooling, not settings).
"""

from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Store
from app.schemas.stores import StoreUpdate


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
) -> Store:
    """Apply a partial update to a store profile.

    Only fields that the caller actually sent are mutated
    (`exclude_unset=True`). The `StoreUpdate` schema restricts those
    to `name` and `timezone`; this function does not enforce that
    list itself, so any future schema change must remain consistent
    with the F2.14 contract.
    """
    store = get_store(db, store_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(store, field, value)
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
