from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.supabase_auth import SupabaseAuthError
from app.core.supabase_auth import verify_supabase_jwt
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_db


# auto_error=False so we control the response code/headers ourselves;
# FastAPI's default is 403, we want 401 with a WWW-Authenticate header.
bearer_scheme = HTTPBearer(auto_error=False)

WWW_AUTH_HEADER = {"WWW-Authenticate": "Bearer"}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=WWW_AUTH_HEADER,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Supabase access token.

    F2.22.2.D: the Bearer token is a Supabase-issued JWT, verified against
    the project JWKS by `verify_supabase_jwt`. The token establishes
    IDENTITY only — its `sub` is `auth.users.id`, matched against
    `public.users.auth_user_id`. role / store_id / is_active and every
    permission decision come from the `public.users` row, never from
    token claims.
    """
    if credentials is None:
        raise _unauthorized("Not authenticated")
    if credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")

    try:
        token_payload = verify_supabase_jwt(credentials.credentials)
    except SupabaseAuthError as exc:
        # Uniform 401 for every verification failure (bad signature,
        # wrong audience/issuer, expired, malformed, non-UUID sub) so a
        # caller cannot probe which check failed.
        raise _unauthorized("Invalid token") from exc

    # Bridge: Supabase identity (sub) -> public.users via auth_user_id.
    user = db.scalar(
        select(User).where(User.auth_user_id == token_payload.sub)
    )
    if user is None:
        # Token verified, but no public.users row maps to this identity.
        # Same 401/"Invalid token" as a bad token: an unmapped identity
        # is not an authenticated NubeRush user.
        raise _unauthorized("Invalid token")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def require_roles(*allowed_roles: UserRole):
    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return role_dependency


# Role aliases. These are the shapes endpoints should reach for; the bare
# `require_roles` factory stays available for one-off combinations.
#
# Hierarchy semantics:
#   admin > owner > manager > {staff, driver}
# `staff` and `driver` are sibling operational roles, not stacked. An
# in-store endpoint that uses `require_staff_or_above` does NOT admit
# drivers, and a delivery endpoint that uses `require_driver_or_above`
# does NOT admit staff. Management roles pass either gate.
_ADMIN_ONLY = frozenset({UserRole.admin})
_OWNER_OR_ADMIN = frozenset({UserRole.admin, UserRole.owner})
_MANAGER_OR_ABOVE = frozenset({UserRole.admin, UserRole.owner, UserRole.manager})
_STAFF_OR_ABOVE = frozenset(
    {UserRole.admin, UserRole.owner, UserRole.manager, UserRole.staff}
)
_DRIVER_OR_ABOVE = frozenset(
    {UserRole.admin, UserRole.owner, UserRole.manager, UserRole.driver}
)


def _enforce_roles(allowed: frozenset[UserRole], user: User) -> User:
    if user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    return _enforce_roles(_ADMIN_ONLY, current_user)


def require_owner_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    return _enforce_roles(_OWNER_OR_ADMIN, current_user)


def require_manager_or_above(
    current_user: User = Depends(get_current_user),
) -> User:
    return _enforce_roles(_MANAGER_OR_ABOVE, current_user)


def require_staff_or_above(
    current_user: User = Depends(get_current_user),
) -> User:
    return _enforce_roles(_STAFF_OR_ABOVE, current_user)


def require_driver_or_above(
    current_user: User = Depends(get_current_user),
) -> User:
    return _enforce_roles(_DRIVER_OR_ABOVE, current_user)


# Exact-driver gate (Dr.1.1.B). Distinct from `require_driver_or_above`:
# that alias admits management (admin/owner/manager) alongside drivers for
# oversight-style endpoints. `require_driver` admits ONLY UserRole.driver,
# so a future /driver/* surface can gate on "driver and nobody else"
# without accidentally letting a manager or admin drive. It is intentionally
# NOT wired to any route in Dr.1.1.B — it only prepares the contract.
_DRIVER_ONLY = frozenset({UserRole.driver})


def require_driver(current_user: User = Depends(get_current_user)) -> User:
    return _enforce_roles(_DRIVER_ONLY, current_user)


def require_store_bound_driver(
    current_user: User = Depends(require_driver),
) -> User:
    """Validate that the actor is a driver bound to a store (Dr.1.1.B).

    Future-facing foundation for /driver/* routes under the store-bound
    driver tenancy decision (Dr.1.1.A §4). It asserts ONLY two things:

      - the actor is exactly a driver (via `require_driver`), and
      - the driver carries a store_id (non-admins are store-bound).

    It deliberately does NOT authorize a delivery or an assignment, and
    does NOT consult DriverProfile or OrderDriverAssignment — neither
    exists yet (those arrive in Dr.1.1.C / Dr.1.1.E). It is a role+tenancy
    actor check, not a resource-ownership check. Per-assignment binding is
    a later contract (Dr.1.1.F).
    """
    if current_user.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver is not bound to a store.",
        )
    return current_user


def require_store_member(
    store_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that enforces tenancy on a path/query store_id.

    Behaviour:
      - admin: passes for any existing+active store; 404 if not found,
        400 if the store exists but is inactive.
      - non-admin without store_id: 403.
      - non-admin trying a store other than their own: 403, regardless of
        whether that other store exists. We deliberately collapse "wrong
        store" and "no such store" into the same response so a tenant
        cannot probe the existence of unrelated stores by status code.
      - non-admin accessing their own store: 200 unless the store row is
        missing (404, defense-in-depth) or inactive (400).
    """
    if current_user.role == UserRole.admin:
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
        return current_user

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

    store = db.scalar(select(Store).where(Store.id == store_id))
    if store is None:
        # FK with ON DELETE SET NULL means we'd usually have hit the prior
        # 403 already, but cover the race window explicitly.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )
    if not store.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Store is inactive.",
        )
    return current_user
