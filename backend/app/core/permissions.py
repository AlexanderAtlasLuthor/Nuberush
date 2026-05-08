from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole


def resolve_store_scope(
    current_user: User, requested_store_id: UUID | None
) -> UUID | None:
    """Decide which store_id should scope a query for the current user.

    Returns:
      - admin: the requested_store_id verbatim (None means "global scope",
        used by dashboards or aggregate endpoints).
      - non-admin: the user's own store_id. The caller may pass
        `requested_store_id=None` to mean "scope to my store" (default
        for non-admin) or pass their own store_id explicitly. Any other
        value is rejected with 403.

    Raises HTTPException; this helper assumes it runs inside an HTTP
    request, same convention as the other permission helpers.

    Note: this function does NOT verify the store exists or is active.
    Combine with `require_store_member` or an explicit lookup when those
    guarantees are needed.
    """
    if current_user.role == UserRole.admin:
        return requested_store_id

    if current_user.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not bound to a store.",
        )

    if (
        requested_store_id is not None
        and requested_store_id != current_user.store_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this store.",
        )

    return current_user.store_id


# Matrix of which caller role can create which target roles. Anything not in
# the set on the right is rejected. driver/staff can never create users.
USER_CREATION_MATRIX: dict[UserRole, frozenset[UserRole]] = {
    UserRole.admin: frozenset(
        {UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver}
    ),
    UserRole.owner: frozenset({UserRole.manager, UserRole.staff, UserRole.driver}),
    UserRole.manager: frozenset({UserRole.staff, UserRole.driver}),
    UserRole.staff: frozenset(),
    UserRole.driver: frozenset(),
}


def can_caller_create_role(caller_role: UserRole, target_role: UserRole) -> bool:
    return target_role in USER_CREATION_MATRIX.get(caller_role, frozenset())


def resolve_target_store_id(
    caller: User,
    target_role: UserRole,
    requested_store_id: UUID | None,
) -> UUID | None:
    """Validate and resolve the store_id a new user should be created under.

    Raises HTTPException with the appropriate status code on violation.
    Returns the final store_id (may be None for admin targets).
    """
    if target_role == UserRole.admin:
        if requested_store_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin users must not be bound to a store.",
            )
        return None

    if caller.role == UserRole.admin:
        if requested_store_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{target_role.value} users must be assigned to a store.",
            )
        return requested_store_id

    # Owner and manager creating non-admin users: forced to caller's own store.
    if caller.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not bound to a store and cannot create store users.",
        )

    if requested_store_id is not None and requested_store_id != caller.store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create users in another store.",
        )

    return caller.store_id


# Matrix of which caller role can ASSIGN which target role through the
# role-change endpoint. Mirrors USER_CREATION_MATRIX in shape but is a
# distinct contract: creation runs at user birth, assignment runs on an
# existing user. Keeping the two separate makes it explicit when one
# changes without the other.
USER_ROLE_UPDATE_MATRIX: dict[UserRole, frozenset[UserRole]] = {
    UserRole.admin: frozenset(
        {
            UserRole.admin,
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        }
    ),
    UserRole.owner: frozenset(
        {UserRole.manager, UserRole.staff, UserRole.driver}
    ),
    UserRole.manager: frozenset({UserRole.staff, UserRole.driver}),
    UserRole.staff: frozenset(),
    UserRole.driver: frozenset(),
}


def can_caller_assign_role(
    caller_role: UserRole, target_role: UserRole
) -> bool:
    return target_role in USER_ROLE_UPDATE_MATRIX.get(
        caller_role, frozenset()
    )


# Matrix of which caller role can MODIFY (update profile, deactivate,
# reactivate) a target user with a given role. The rule is "manage your
# strict subordinates plus your own rank, never higher". Admin sees
# everyone; staff and driver manage no one.
_USER_MODIFY_MATRIX: dict[UserRole, frozenset[UserRole]] = {
    UserRole.admin: frozenset(
        {
            UserRole.admin,
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        }
    ),
    UserRole.owner: frozenset(
        {UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver}
    ),
    UserRole.manager: frozenset(
        {UserRole.manager, UserRole.staff, UserRole.driver}
    ),
    UserRole.staff: frozenset(),
    UserRole.driver: frozenset(),
}


# Matrix of which caller role can DEACTIVATE/REACTIVATE a target user.
# Stricter than _USER_MODIFY_MATRIX: managers cannot toggle peers, only
# strict subordinates (staff, driver). Owners may toggle anyone in the
# store except admin. Admin may toggle anyone (last-admin and self
# guards still apply).
_USER_LIFECYCLE_MATRIX: dict[UserRole, frozenset[UserRole]] = {
    UserRole.admin: frozenset(
        {
            UserRole.admin,
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        }
    ),
    UserRole.owner: frozenset(
        {UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver}
    ),
    UserRole.manager: frozenset({UserRole.staff, UserRole.driver}),
    UserRole.staff: frozenset(),
    UserRole.driver: frozenset(),
}


def _forbid(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail=detail
    )


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
    )


def _assert_same_store_or_admin(actor: User, target: User) -> None:
    """Tenancy guard for any user-management action.

    Admin is global; non-admin actors must operate inside their own
    store. A non-admin actor without a `store_id` is treated as a
    structural error (see `resolve_store_scope`) and rejected with
    403 to match the rest of the codebase.
    """
    if actor.role == UserRole.admin:
        return
    if actor.store_id is None:
        raise _forbid("User is not bound to a store.")
    if target.store_id is None or target.store_id != actor.store_id:
        raise _forbid("You do not have access to this user.")


def assert_can_modify_user(actor: User, target: User) -> None:
    """Authorize a non-lifecycle update (full_name/phone)."""
    allowed = _USER_MODIFY_MATRIX.get(actor.role, frozenset())
    if target.role not in allowed:
        raise _forbid("You cannot modify this user.")
    _assert_same_store_or_admin(actor, target)


def assert_can_change_user_role(
    actor: User, target: User, new_role: UserRole
) -> None:
    """Authorize a role change.

    Two checks: the actor must currently be allowed to manage the
    target's CURRENT role, and the actor must be allowed to assign
    the NEW role per `USER_ROLE_UPDATE_MATRIX`. The first prevents a
    manager from "promoting" a peer they could not otherwise touch;
    the second prevents privilege escalation (manager assigning
    `manager`, owner assigning `owner` or `admin`).
    """
    modifiable = _USER_MODIFY_MATRIX.get(actor.role, frozenset())
    if target.role not in modifiable:
        raise _forbid("You cannot modify this user.")
    if not can_caller_assign_role(actor.role, new_role):
        raise _forbid(
            f"You cannot assign role '{new_role.value}'."
        )
    _assert_same_store_or_admin(actor, target)


def assert_can_deactivate_user(
    db: Session, actor: User, target: User
) -> None:
    """Authorize a deactivation (set is_active=False).

    Includes the last-active-admin guard: the system must always have
    at least one active admin, so disabling the last one is rejected
    with 422. Self-deactivation is also blocked with 422 — locking
    yourself out is a footgun, never a feature.
    """
    if target.id == actor.id:
        raise _unprocessable("You cannot deactivate yourself.")

    allowed = _USER_LIFECYCLE_MATRIX.get(actor.role, frozenset())
    if target.role not in allowed:
        raise _forbid("You cannot deactivate this user.")
    _assert_same_store_or_admin(actor, target)

    if target.role == UserRole.admin and target.is_active:
        active_admin_count = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.admin, User.is_active.is_(True))
        )
        if active_admin_count is not None and active_admin_count <= 1:
            raise _unprocessable(
                "Cannot deactivate the last active admin."
            )


def assert_can_reactivate_user(actor: User, target: User) -> None:
    """Authorize a reactivation (set is_active=True). Same RBAC matrix
    as deactivation but no last-admin / self-target invariants."""
    allowed = _USER_LIFECYCLE_MATRIX.get(actor.role, frozenset())
    if target.role not in allowed:
        raise _forbid("You cannot reactivate this user.")
    _assert_same_store_or_admin(actor, target)


def assert_user_store_invariant(
    user_role: UserRole, store_id: UUID | None
) -> None:
    """Enforce the cross-field rule that admins are global and
    non-admins are store-bound. The DB column is nullable so the rule
    cannot live in a CHECK constraint; this helper is the canonical
    enforcement point used by both role changes and store assignments.
    """
    if user_role == UserRole.admin:
        if store_id is not None:
            raise _unprocessable(
                "Admin users must not be bound to a store."
            )
    else:
        if store_id is None:
            raise _unprocessable(
                f"{user_role.value} users must be assigned to a store."
            )


def assert_active_store_for_assignment(
    db: Session, store_id: UUID
) -> Store:
    """Resolve a store_id to an active row or raise.

    404 when missing, 400 when inactive — same shape as
    `require_store_member`. Returns the row so callers can avoid a
    second lookup.
    """
    store = db.scalar(select(Store).where(Store.id == store_id))
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )
    if not store.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Store is inactive.",
        )
    return store
