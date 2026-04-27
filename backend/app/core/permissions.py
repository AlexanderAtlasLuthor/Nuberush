from uuid import UUID

from fastapi import HTTPException
from fastapi import status

from app.db.models import User
from app.db.models import UserRole


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
