"""Driver-facing routes (Dr.1.1.C / Dr.1.1.D / Dr.1.1.F).

Every endpoint is gated by `require_store_bound_driver` (Dr.1.1.B), so only
an exact, store-bound driver reaches it; staff/manager/owner/admin and
storeless drivers are rejected upstream with 403.

The driver runtime surface is four self-scoped, read-only GETs:
  - GET /driver/me                      (Dr.1.1.C)
  - GET /driver/eligibility             (Dr.1.1.D)
  - GET /driver/assignments             (Dr.1.1.F)
  - GET /driver/assignments/{id}        (Dr.1.1.F)

Dispatch, accept/decline, go-online/go-offline, active delivery, proof of
delivery, and any mutating action are later Dr.1.1 subphases and must not be
added here. There is no POST/PATCH/DELETE on the /driver surface.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import require_store_bound_driver
from app.db.models import OrderDriverAssignmentStatus
from app.db.models import User
from app.db.session import get_db
from app.schemas.driver import DriverAssignmentListResponse
from app.schemas.driver import DriverAssignmentRead
from app.schemas.driver import DriverEligibilityRead
from app.schemas.driver import DriverProfileRead
from app.services.driver import evaluate_driver_eligibility
from app.services.driver import get_driver_assignment
from app.services.driver import get_driver_profile_for_user
from app.services.driver import list_driver_assignments

router = APIRouter(prefix="/driver", tags=["driver"])


@router.get("/me", response_model=DriverProfileRead)
def read_current_driver_profile(
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverProfileRead:
    return get_driver_profile_for_user(db, current_user)


@router.get("/eligibility", response_model=DriverEligibilityRead)
def read_current_driver_eligibility(
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverEligibilityRead:
    """Backend-authoritative go-online eligibility for the current driver.

    Read-only. A missing profile is a normal ineligibility result (200 with
    a `driver_profile_missing` blocker), not a 404. An inactive user cannot
    reach this endpoint — get_current_user rejects inactive users with 403
    upstream — so the `user_inactive` blocker is observable only at the
    service level.
    """
    return evaluate_driver_eligibility(db, current_user)


@router.get("/assignments", response_model=DriverAssignmentListResponse)
def list_current_driver_assignments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: OrderDriverAssignmentStatus | None = Query(default=None),
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverAssignmentListResponse:
    """List the current driver's own assignments (Dr.1.1.F).

    Read-only and self-scoped: a driver sees only their own assignments,
    bound to their own store. With no `status` filter the default view is the
    active lifecycle states (offered / accepted / assigned / started);
    terminal states are queryable explicitly via `status`. Exposes no
    customer PII.
    """
    return list_driver_assignments(
        db,
        current_user,
        limit=limit,
        offset=offset,
        status=status,
    )


@router.get(
    "/assignments/{assignment_id}", response_model=DriverAssignmentRead
)
def read_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverAssignmentRead:
    """Read one of the current driver's own assignments (Dr.1.1.F).

    Read-only and self-scoped. An assignment that does not exist or belongs
    to another driver or store returns 404 — existence is never leaked across
    the scope boundary. Exposes no customer PII.
    """
    return get_driver_assignment(db, current_user, assignment_id)
