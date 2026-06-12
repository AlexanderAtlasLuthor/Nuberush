"""Driver-facing routes (Dr.1.1.C).

The entire driver runtime surface for Dr.1.1.C is a single self-scoped read:
GET /driver/me. It is gated by `require_store_bound_driver` (Dr.1.1.B), so
only an exact, store-bound driver reaches it; staff/manager/owner/admin and
storeless drivers are rejected upstream with 403.

No other /driver/* route exists yet. Eligibility (/driver/eligibility),
assignments, active delivery, and any POST action are later Dr.1.1 subphases
and must not be added here.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_store_bound_driver
from app.db.models import User
from app.db.session import get_db
from app.schemas.driver import DriverProfileRead
from app.services.driver import get_driver_profile_for_user

router = APIRouter(prefix="/driver", tags=["driver"])


@router.get("/me", response_model=DriverProfileRead)
def read_current_driver_profile(
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverProfileRead:
    return get_driver_profile_for_user(db, current_user)
