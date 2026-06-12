"""Driver domain service (Dr.1.1.C).

Read-only, self-scoped access to a driver's own profile. This is the entire
driver service surface for Dr.1.1.C: it resolves the current driver's
`DriverProfile` and nothing more. It never mutates the database, never
provisions a profile, and never consults assignments, eligibility, orders, or
inventory — those are later Dr.1.1 subphases.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverProfile
from app.db.models import User
from app.db.models import UserRole


def get_driver_profile_for_user(
    db: Session, current_user: User
) -> DriverProfile:
    """Return the current user's own driver profile.

    Authority model (Dr.1.1.A): the backend decides; the app reads. This
    helper assumes the actor already passed `require_store_bound_driver`
    (exact driver + store-bound), but re-checks the role defensively.

    Raises:
      - 403 if the actor is not a driver (defense in depth).
      - 404 if the driver has no provisioned profile yet.
      - 403 if the profile's store_id does not match the user's store_id
        (a cross-table integrity guard; denied rather than leaked).

    An `inactive` profile or a `pending` / `rejected` approval_status is NOT
    blocked here — the profile is returned with its status reflected. The
    can_go_online decision belongs to Dr.1.1.D, not to this read.
    """
    if current_user.role != UserRole.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )

    profile = db.scalar(
        select(DriverProfile).where(
            DriverProfile.user_id == current_user.id
        )
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found",
        )

    if profile.store_id != current_user.store_id:
        # The profile and the user disagree on which store the driver
        # belongs to — a structural integrity error. Deny without echoing
        # either store id.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this driver profile.",
        )

    return profile
