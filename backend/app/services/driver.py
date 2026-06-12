"""Driver domain service (Dr.1.1.C / Dr.1.1.D).

Read-only, self-scoped driver reads. Dr.1.1.C resolves the current driver's
`DriverProfile`; Dr.1.1.D adds the backend-authoritative go-online
eligibility computation. Neither mutates the database, provisions a profile,
or consults assignments, orders, or inventory — those are later subphases.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverApprovalStatus
from app.db.models import DriverProfile
from app.db.models import DriverProfileStatus
from app.db.models import User
from app.db.models import UserRole
from app.schemas.driver import DriverEligibilityBlocker
from app.schemas.driver import DriverEligibilityBlockerCode
from app.schemas.driver import DriverEligibilityBlockerSeverity
from app.schemas.driver import DriverEligibilityBlockerSource
from app.schemas.driver import DriverEligibilityRead


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


def _blocker(
    code: DriverEligibilityBlockerCode,
    source: DriverEligibilityBlockerSource,
    message: str,
) -> DriverEligibilityBlocker:
    return DriverEligibilityBlocker(
        code=code,
        message=message,
        source=source,
        severity=DriverEligibilityBlockerSeverity.blocker,
    )


def evaluate_driver_eligibility(
    db: Session, current_user: User
) -> DriverEligibilityRead:
    """Compute whether the current driver may go online (Dr.1.1.D).

    Backend-authoritative and read-only. It reads existing user / store /
    driver-profile state and reports structured `blockers`; it never mutates
    anything and never performs an actual go-online transition.

    Authority model: assumes the actor already passed
    `require_store_bound_driver` (exact driver + store-bound), but re-checks
    both defensively.

    Behaviour differs from `get_driver_profile_for_user` in one key way: a
    MISSING profile is a normal ineligibility result (200 + blocker), NOT a
    404. So this function queries the profile directly and treats `None` as a
    blocker rather than reusing that helper.

    Raises (hard errors, not ineligibility):
      - 403 if the actor is not a driver.
      - 403 if the driver is not bound to a store.
      - 403 if an existing profile's store_id disagrees with the user's
        store_id (structural integrity error).

    Returns `DriverEligibilityRead` for every other case, accumulating all
    applicable blockers. `can_go_online` is true only when no blocker applies.
    """
    if current_user.role != UserRole.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )
    if current_user.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver is not bound to a store.",
        )

    blockers: list[DriverEligibilityBlocker] = []

    user_active = bool(current_user.is_active)
    if not user_active:
        # Reachable only at the service level: get_current_user rejects
        # inactive users with 403 before any handler runs. Computed anyway
        # so the backend authority is complete and internally consistent.
        blockers.append(
            _blocker(
                DriverEligibilityBlockerCode.user_inactive,
                DriverEligibilityBlockerSource.user,
                "User account is inactive.",
            )
        )

    profile = db.scalar(
        select(DriverProfile).where(
            DriverProfile.user_id == current_user.id
        )
    )

    driver_status: str | None = None
    driver_approval_status: str | None = None
    store_active: bool | None = None

    if profile is None:
        blockers.append(
            _blocker(
                DriverEligibilityBlockerCode.driver_profile_missing,
                DriverEligibilityBlockerSource.driver_profile,
                "No driver profile has been provisioned.",
            )
        )
    else:
        if profile.store_id != current_user.store_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this driver profile.",
            )

        driver_status = profile.status
        driver_approval_status = profile.approval_status

        store = profile.store
        if store is None:
            blockers.append(
                _blocker(
                    DriverEligibilityBlockerCode.store_missing,
                    DriverEligibilityBlockerSource.store,
                    "The driver's store could not be found.",
                )
            )
        else:
            store_active = bool(store.is_active)
            if not store_active:
                blockers.append(
                    _blocker(
                        DriverEligibilityBlockerCode.store_inactive,
                        DriverEligibilityBlockerSource.store,
                        "The driver's store is inactive.",
                    )
                )

        if profile.status == DriverProfileStatus.inactive.value:
            blockers.append(
                _blocker(
                    DriverEligibilityBlockerCode.driver_profile_inactive,
                    DriverEligibilityBlockerSource.driver_profile,
                    "The driver profile is inactive.",
                )
            )

        if profile.approval_status == DriverApprovalStatus.pending.value:
            blockers.append(
                _blocker(
                    DriverEligibilityBlockerCode.driver_approval_pending,
                    DriverEligibilityBlockerSource.driver_profile,
                    "The driver profile is pending approval.",
                )
            )
        elif (
            profile.approval_status == DriverApprovalStatus.rejected.value
        ):
            blockers.append(
                _blocker(
                    DriverEligibilityBlockerCode.driver_approval_rejected,
                    DriverEligibilityBlockerSource.driver_profile,
                    "The driver profile approval was rejected.",
                )
            )

    return DriverEligibilityRead(
        can_go_online=not blockers,
        blockers=blockers,
        driver_status=driver_status,
        driver_approval_status=driver_approval_status,
        user_active=user_active,
        store_active=store_active,
        evaluated_at=datetime.now(timezone.utc),
    )
