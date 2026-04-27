from uuid import UUID

from fastapi import HTTPException
from fastapi import status

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
