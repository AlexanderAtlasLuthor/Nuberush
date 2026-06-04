"""Service layer for users management (F2.15.2).

Owns the business logic for the operational user-management surface
(list / read / update / deactivate / reactivate / change role / assign
store). Routers in F2.15.3 are thin: parse, authorize, call, return.

F2.22.2.F note: identity and credentials now live entirely in Supabase
Auth. There is no local password column and no admin-set-password
service here — password changes go through Supabase.

Conventions (consistent with `app.services.stores` and
`app.services.products`):

- Every function takes the DB session as its first argument and is
  responsible for its own commit/rollback.
- Read functions raise HTTPException(404) on missing rows so routers
  can `raise` directly without extra branching.
- RBAC and tenancy guards live in `app.core.permissions`. This module
  composes them; it does not re-encode the rules. That keeps a single
  source of truth for the "who can do what" matrix.
- Mutation functions write only the columns the contract permits. The
  schemas (with `extra="forbid"`) prevent privileged fields from ever
  reaching this layer; this module never relies on a deny-list.
- Status codes match the existing repo:
    * 403 for RBAC / tenancy refusals.
    * 404 for missing resources.
    * 400 for inactive stores during assignment (mirrors
      `require_store_member`).
    * 422 for self-target / last-admin / store-invariant violations.

Out of scope here (handled elsewhere or deferred):
  - User creation lives in `POST /auth/users` and is unchanged.
  - Password reset, invitation flows, MFA, SSO — owned by Supabase
    Auth, not this module.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import assert_active_store_for_assignment
from app.core.permissions import assert_can_change_user_role
from app.core.permissions import assert_can_deactivate_user
from app.core.permissions import assert_can_modify_user
from app.core.permissions import assert_can_reactivate_user
from app.core.permissions import assert_user_store_invariant
from app.db.models import User
from app.db.models import UserRole
from app.schemas.users import UserRoleChangeRequest
from app.schemas.users import UserStoreAssignmentRequest
from app.schemas.users import UserUpdateRequest
from app.services.operational_audit import write_operational_audit_log


def build_user_audit_snapshot(user: User) -> dict[str, object]:
    """Small, stable, allow-listed snapshot of a user for the operational
    audit trail (F2.26.1.C).

    Only the fields the operational-audit allow-list already permits for a
    `user` target (`role`, `store_id`, `is_active`, `full_name`, `phone`).
    `email` and `auth_user_id` are intentionally excluded (PII / identity
    bridge), and no password/token/secret is ever read here. `role` is
    reduced to its string value and `store_id` to a string so the dict is
    JSON-safe and stable; the writer re-applies the allow-list + redaction
    as defense-in-depth.
    """
    return {
        "role": user.role.value,
        "store_id": str(user.store_id) if user.store_id is not None else None,
        "is_active": user.is_active,
        "full_name": user.full_name,
        "phone": user.phone,
    }


# Roles allowed to access the user-management surface. staff and
# driver are operational roles and never see this layer.
_MANAGEMENT_ROLES: frozenset[UserRole] = frozenset(
    {UserRole.admin, UserRole.owner, UserRole.manager}
)


def _assert_management_caller(actor: User) -> None:
    if actor.role not in _MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )


def _assert_admin_caller(actor: User) -> None:
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


def _get_user_for_management_or_forbidden(
    db: Session, user_id: UUID, *, actor: User
) -> User:
    """Tenant-safe lookup for the user-management surface.

    Mirrors the existence-collapse rule the codebase already uses for
    `require_store_member`: a non-admin caller cannot probe whether a
    user_id exists by observing 404 vs 403, so for non-admin actors we
    return 403 in BOTH the missing-row and out-of-scope cases.

    Admin actors continue to see 404 for genuinely missing rows so an
    admin tooling caller can distinguish "user deleted" from "user
    exists but action rejected by invariant" — that signal is useful
    in admin contexts and not exploitable, since admin already has
    global visibility.

    The downstream `assert_can_*` helpers run unchanged on the
    returned `User` and surface 403 for cross-store / matrix
    rejections — same code path the existence-collapse uses, so a
    non-admin attacker sees a uniform 403 response regardless of
    whether the UUID was unknown, in another store, or owned by an
    admin.
    """
    user = db.get(User, user_id)
    if user is None:
        if actor.role == UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this user.",
        )
    return user


def _commit_or_translate(db: Session, *, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc


# --------------------------------------------------------------------- #
# Read paths
# --------------------------------------------------------------------- #


def _resolve_list_store_scope(
    actor: User, requested_store_id: UUID | None
) -> UUID | None:
    """Decide which store_id should scope the list query.

    Distinct from `permissions.resolve_store_scope` because the rule
    here is operationally narrower: management roles ALWAYS see only
    their own store on `/users`, never another store, and never global
    scope. Admin sees what they ask for (None == global, UUID == that
    store). A non-admin without `store_id` is a structural bug and is
    rejected with 403.
    """
    if actor.role == UserRole.admin:
        return requested_store_id

    if actor.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not bound to a store.",
        )

    if (
        requested_store_id is not None
        and requested_store_id != actor.store_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this store.",
        )

    return actor.store_id


def list_users(
    db: Session,
    *,
    actor: User,
    role: UserRole | None = None,
    is_active: bool | None = None,
    store_id: UUID | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict:
    """Paginated list of users visible to `actor`.

    Returns a dict shaped exactly like `UserListResponse`
    (`items`/`total`/`limit`/`offset`) so the route layer can construct
    the response model directly without remapping fields.
    """
    _assert_management_caller(actor)
    effective_store_id = _resolve_list_store_scope(actor, store_id)

    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if effective_store_id is not None:
        stmt = stmt.where(User.store_id == effective_store_id)
        count_stmt = count_stmt.where(User.store_id == effective_store_id)

    if role is not None:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)

    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
        count_stmt = count_stmt.where(User.is_active.is_(is_active))

    if q:
        pattern = f"%{q.strip()}%"
        if pattern != "%%":
            search = or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                User.phone.ilike(pattern),
            )
            stmt = stmt.where(search)
            count_stmt = count_stmt.where(search)

    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)

    items = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_user(db: Session, user_id: UUID, *, actor: User) -> User:
    """Read a single user under the same RBAC + tenancy rules used by
    profile updates. Read parity with update keeps the matrix simple
    and means a caller cannot probe the existence of users they may
    not modify."""
    _assert_management_caller(actor)
    target = _get_user_for_management_or_forbidden(db, user_id, actor=actor)
    assert_can_modify_user(actor, target)
    return target


# --------------------------------------------------------------------- #
# Profile update
# --------------------------------------------------------------------- #


def update_user(
    db: Session,
    user_id: UUID,
    payload: UserUpdateRequest,
    *,
    actor: User,
) -> User:
    """Apply a partial profile update.

    Only the fields the schema exposes (`full_name`, `phone`) reach
    the User row. Privileged columns are blocked at the schema layer
    (`extra="forbid"`); this function does not maintain a deny-list.
    """
    _assert_management_caller(actor)
    target = _get_user_for_management_or_forbidden(db, user_id, actor=actor)
    assert_can_modify_user(actor, target)

    before = build_user_audit_snapshot(target)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(target, field, value)

    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="user",
        target_id=target.id,
        action="user_updated",
        store_id=target.store_id,
        before=before,
        after=build_user_audit_snapshot(target),
        metadata={"source": "users.update_user"},
    )

    _commit_or_translate(
        db, detail="User update violates database constraints."
    )
    db.refresh(target)
    return target


# --------------------------------------------------------------------- #
# Lifecycle: deactivate / reactivate
# --------------------------------------------------------------------- #


def deactivate_user(
    db: Session, user_id: UUID, *, actor: User
) -> User:
    _assert_management_caller(actor)
    target = _get_user_for_management_or_forbidden(db, user_id, actor=actor)
    assert_can_deactivate_user(db, actor, target)

    before = build_user_audit_snapshot(target)
    target.is_active = False

    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="user",
        target_id=target.id,
        action="user_deactivated",
        store_id=target.store_id,
        before=before,
        after=build_user_audit_snapshot(target),
        metadata={"source": "users.deactivate_user"},
    )

    _commit_or_translate(
        db, detail="User deactivation violates database constraints."
    )
    db.refresh(target)
    return target


def reactivate_user(
    db: Session, user_id: UUID, *, actor: User
) -> User:
    _assert_management_caller(actor)
    target = _get_user_for_management_or_forbidden(db, user_id, actor=actor)
    assert_can_reactivate_user(actor, target)

    # Reactivating a non-admin without a store would create a logically
    # inconsistent active user. The store-invariant helper raises 422
    # with the canonical message; admins skip the check by design.
    assert_user_store_invariant(target.role, target.store_id)

    before = build_user_audit_snapshot(target)
    target.is_active = True

    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="user",
        target_id=target.id,
        action="user_activated",
        store_id=target.store_id,
        before=before,
        after=build_user_audit_snapshot(target),
        metadata={"source": "users.reactivate_user"},
    )

    _commit_or_translate(
        db, detail="User reactivation violates database constraints."
    )
    db.refresh(target)
    return target


# --------------------------------------------------------------------- #
# Role change
# --------------------------------------------------------------------- #


def change_user_role(
    db: Session,
    user_id: UUID,
    payload: UserRoleChangeRequest,
    *,
    actor: User,
) -> User:
    _assert_management_caller(actor)
    target = _get_user_for_management_or_forbidden(db, user_id, actor=actor)

    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot change your own role.",
        )

    new_role = payload.role
    assert_can_change_user_role(actor, target, new_role)

    before = build_user_audit_snapshot(target)

    # Cross-field invariant: admins are global, non-admins are
    # store-bound. Promoting to admin clears store_id; demoting from
    # admin requires the target to already have a store assigned
    # (admins use POST /users/{id}/store to set one before the
    # demotion). Surfacing both as 422 keeps the contract uniform.
    if new_role == UserRole.admin:
        target.store_id = None
    else:
        if target.store_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{new_role.value} users must be assigned to a store "
                    f"before changing role."
                ),
            )

    target.role = new_role

    # store_id semantics (F2.26.1.C): use the FINAL store binding —
    # NULL when the user is now admin/global, the store when store-bound.
    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="user",
        target_id=target.id,
        action="user_role_changed",
        store_id=target.store_id,
        before=before,
        after=build_user_audit_snapshot(target),
        metadata={"source": "users.change_user_role"},
    )

    _commit_or_translate(
        db, detail="User role change violates database constraints."
    )
    db.refresh(target)
    return target


# --------------------------------------------------------------------- #
# Store assignment
# --------------------------------------------------------------------- #


def assign_user_store(
    db: Session,
    user_id: UUID,
    payload: UserStoreAssignmentRequest,
    *,
    actor: User,
) -> User:
    """Set or clear a user's store_id. Admin-only.

    Owners and managers can move users between stores only by
    creating a fresh user under the new store, which is the simplest
    safe path and matches how the org actually onboards.
    """
    _assert_admin_caller(actor)
    target = _get_user_or_404(db, user_id)

    before = build_user_audit_snapshot(target)
    previous_store_id = target.store_id

    if target.role == UserRole.admin:
        if payload.store_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Admin users must not be bound to a store.",
            )
        target.store_id = None
    else:
        if payload.store_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{target.role.value} users must be assigned to a store."
                ),
            )
        # Resolves existence + active state. 404 / 400 mirror
        # `require_store_member` so the route layer behavior is the
        # same whether the call comes from /users or /stores.
        assert_active_store_for_assignment(db, payload.store_id)
        target.store_id = payload.store_id

    # store_id semantics (F2.26.1.C): an assignment scopes the event to the
    # store the user now belongs to; a removal scopes it to the store the
    # user was removed FROM (the new binding is NULL/global).
    if target.store_id is None:
        action = "user_store_removed"
        event_store_id = previous_store_id
    else:
        action = "user_store_assigned"
        event_store_id = target.store_id

    write_operational_audit_log(
        db,
        actor_user_id=actor.id,
        target_type="user",
        target_id=target.id,
        action=action,
        store_id=event_store_id,
        before=before,
        after=build_user_audit_snapshot(target),
        metadata={"source": "users.assign_user_store"},
    )

    _commit_or_translate(
        db, detail="Store assignment violates database constraints."
    )
    db.refresh(target)
    return target
