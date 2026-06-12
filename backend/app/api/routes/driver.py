"""Driver-facing routes (Dr.1.1.C / Dr.1.1.D / Dr.1.1.F / Dr.1.1.H / Dr.1.1.I).

Every endpoint is gated by `require_store_bound_driver` (Dr.1.1.B), so only
an exact, store-bound driver reaches it; staff/manager/owner/admin and
storeless drivers are rejected upstream with 403.

The driver runtime surface is five self-scoped, read-only GETs plus the first
two driver-side mutations (Dr.1.1.I accept/decline):
  - GET  /driver/me                                       (Dr.1.1.C)
  - GET  /driver/eligibility                              (Dr.1.1.D)
  - GET  /driver/assignments                              (Dr.1.1.F)
  - GET  /driver/assignments/{id}                         (Dr.1.1.F)
  - GET  /driver/assignments/{id}/delivery-state          (Dr.1.1.H)
  - POST /driver/assignments/{id}/accept                  (Dr.1.1.I)
  - POST /driver/assignments/{id}/decline                 (Dr.1.1.I)

accept/decline mutate ONLY the assignment's status + accepted_at/declined_at
(offered -> accepted/declined). Start/pickup/proof/complete/fail/return,
go-online/go-offline, dispatch, GPS, and ID verification are later subphases
and must not be added here. There is no PATCH/PUT/DELETE on the /driver
surface, and no POST beyond accept/decline. The delivery-state read (Dr.1.1.H)
never materializes state (`ensure_*` is not used here).
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
from app.schemas.driver import DriverDeliveryOperationalStateRead
from app.schemas.driver import DriverEligibilityRead
from app.schemas.driver import DriverProfileRead
from app.services.driver import accept_driver_assignment
from app.services.driver import decline_driver_assignment
from app.services.driver import evaluate_driver_eligibility
from app.services.driver import get_driver_assignment
from app.services.driver import get_driver_delivery_operational_state
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


@router.get(
    "/assignments/{assignment_id}/delivery-state",
    response_model=DriverDeliveryOperationalStateRead,
)
def read_current_driver_delivery_state(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryOperationalStateRead:
    """Read the persisted delivery operational state of an own assignment.

    Read-only and self-scoped (Dr.1.1.H). The assignment must belong to the
    current driver and store, else 404 "Driver assignment not found"
    (anti-enumeration). If the assignment IS the driver's own but has no
    operational-state row yet, a distinct 404 "Driver delivery operational
    state not found" is raised — this endpoint never materializes state
    (`ensure_*` belongs to a future action subphase and is not used here).
    Exposes no customer PII.
    """
    return get_driver_delivery_operational_state(
        db=db, current_user=current_user, assignment_id=assignment_id
    )


@router.post(
    "/assignments/{assignment_id}/accept",
    response_model=DriverAssignmentRead,
)
def accept_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverAssignmentRead:
    """Accept one of the current driver's own offered assignments (Dr.1.1.I).

    offered -> accepted; idempotent on an already-accepted assignment (200,
    `accepted_at` unchanged); 409 if already declined; 422 from any other
    status; 404 (anti-enumeration) for a non-own / foreign / missing
    assignment. Mutates only the assignment's status + `accepted_at`.
    """
    return accept_driver_assignment(db, current_user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/decline",
    response_model=DriverAssignmentRead,
)
def decline_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverAssignmentRead:
    """Decline one of the current driver's own offered assignments (Dr.1.1.I).

    offered -> declined; idempotent on an already-declined assignment (200,
    `declined_at` unchanged); 409 if already accepted; 422 from any other
    status; 404 (anti-enumeration) for a non-own / foreign / missing
    assignment. Mutates only the assignment's status + `declined_at`.
    """
    return decline_driver_assignment(db, current_user, assignment_id)
