"""Driver-facing routes (Dr.1.1.C).

The entire driver runtime surface for Dr.1.1.C is a single self-scoped read:
GET /driver/me. It is gated by `require_store_bound_driver` (Dr.1.1.B), so
only an exact, store-bound driver reaches it; staff/manager/owner/admin and
storeless drivers are rejected upstream with 403.

The driver runtime surface is two self-scoped reads: GET /driver/me and
GET /driver/eligibility. Assignments, active delivery, and any POST action
(go-online/go-offline included) are later Dr.1.1 subphases and must not be
added here.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_store_bound_driver
from app.db.models import User
from app.db.session import get_db
from app.schemas.driver import DriverEligibilityRead
from app.schemas.driver import DriverProfileRead
from app.services.driver import evaluate_driver_eligibility
from app.services.driver import get_driver_profile_for_user

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
