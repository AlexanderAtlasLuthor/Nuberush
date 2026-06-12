"""Driver domain service (Dr.1.1.C / Dr.1.1.D).

Read-only, self-scoped driver reads. Dr.1.1.C resolves the current driver's
`DriverProfile`; Dr.1.1.D adds the backend-authoritative go-online
eligibility computation. Neither mutates the database, provisions a profile,
or consults assignments, orders, or inventory — those are later subphases.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.db.models import DriverApprovalStatus
from app.db.models import DriverDeliveryOperationalState
from app.db.models import DriverDeliveryOperationalStateValue
from app.db.models import DriverProfile
from app.db.models import DriverProfileStatus
from app.db.models import OrderDriverAssignment
from app.db.models import OrderDriverAssignmentStatus
from app.db.models import User
from app.db.models import UserRole
from app.schemas.driver import DriverAssignmentListResponse
from app.schemas.driver import DriverAssignmentRead
from app.schemas.driver import DriverDeliveryOperationalStateRead
from app.schemas.driver import DriverEligibilityBlocker
from app.schemas.driver import DriverEligibilityBlockerCode
from app.schemas.driver import DriverEligibilityBlockerSeverity
from app.schemas.driver import DriverEligibilityBlockerSource
from app.schemas.driver import DriverEligibilityRead

# Assignment statuses that count as "active" for a driver's default list view
# (Dr.1.1.F). Terminal/dead states (declined, expired, completed, canceled)
# are excluded by default but remain explicitly queryable via the `status`
# filter. This is the ASSIGNMENT lifecycle (Dr.1.1.A §10) — never delivery
# operational micro-states.
_DEFAULT_ACTIVE_ASSIGNMENT_STATUSES: tuple[OrderDriverAssignmentStatus, ...] = (
    OrderDriverAssignmentStatus.offered,
    OrderDriverAssignmentStatus.accepted,
    OrderDriverAssignmentStatus.assigned,
    OrderDriverAssignmentStatus.started,
)


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


# --------------------------------------------------------------------- #
# Assigned-delivery reads (Dr.1.1.F)
# --------------------------------------------------------------------- #
#
# Read-only, self-scoped, store-bound views of the driver's own
# `OrderDriverAssignment` rows. Every query is double-scoped:
#   driver_profile_id == the current user's own profile  AND
#   store_id          == current_user.store_id
# so a driver can never see another driver's or another store's assignments.
# Neither function mutates, flushes, or commits, and neither reads the
# customer `User` — no PII ever leaves this layer.


def list_driver_assignments(
    db: Session,
    current_user: User,
    *,
    limit: int,
    offset: int,
    status: OrderDriverAssignmentStatus | None = None,
) -> DriverAssignmentListResponse:
    """List the current driver's own assignments (Dr.1.1.F).

    Self-scoped by `DriverProfile` and store-bound by `current_user.store_id`.
    With no `status` filter, returns only the active lifecycle states
    (offered / accepted / assigned / started); terminal states are excluded
    by default but can be requested explicitly via `status`.

    Ordered by `created_at` desc, then `id` desc as a stable tiebreaker.
    Returns the page plus the total count of matching rows. Read-only: it
    never mutates, flushes, or commits, and never consults customer data.

    A driver with no provisioned profile raises 404 via
    `get_driver_profile_for_user`. An `inactive` profile or `pending` /
    `rejected` approval does NOT block these reads.
    """
    driver_profile = get_driver_profile_for_user(db, current_user)

    filters = [
        OrderDriverAssignment.driver_profile_id == driver_profile.id,
        OrderDriverAssignment.store_id == current_user.store_id,
    ]
    if status is None:
        filters.append(
            OrderDriverAssignment.status.in_(
                [s.value for s in _DEFAULT_ACTIVE_ASSIGNMENT_STATUSES]
            )
        )
    else:
        filters.append(OrderDriverAssignment.status == status.value)

    total = db.scalar(
        select(func.count())
        .select_from(OrderDriverAssignment)
        .where(*filters)
    )

    rows = db.scalars(
        select(OrderDriverAssignment)
        .where(*filters)
        .order_by(
            OrderDriverAssignment.created_at.desc(),
            OrderDriverAssignment.id.desc(),
        )
        .options(
            selectinload(OrderDriverAssignment.order),
            selectinload(OrderDriverAssignment.store),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return DriverAssignmentListResponse(
        items=[DriverAssignmentRead.model_validate(row) for row in rows],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


def get_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverAssignmentRead:
    """Return one of the current driver's own assignments (Dr.1.1.F).

    Self-scoped by `DriverProfile` and store-bound by `current_user.store_id`.
    An assignment that does not exist, or belongs to another driver or
    another store, is indistinguishable from the driver's perspective: all
    three raise 404 "Driver assignment not found" so existence is never
    leaked across the scope boundary. Read-only — never mutates.

    A driver with no provisioned profile raises 404 via
    `get_driver_profile_for_user`.
    """
    driver_profile = get_driver_profile_for_user(db, current_user)

    assignment = db.scalar(
        select(OrderDriverAssignment)
        .where(
            OrderDriverAssignment.id == assignment_id,
            OrderDriverAssignment.driver_profile_id == driver_profile.id,
            OrderDriverAssignment.store_id == current_user.store_id,
        )
        .options(
            selectinload(OrderDriverAssignment.order),
            selectinload(OrderDriverAssignment.store),
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver assignment not found",
        )

    return DriverAssignmentRead.model_validate(assignment)


# --------------------------------------------------------------------- #
# Delivery operational state reads (Dr.1.1.G.3)
# --------------------------------------------------------------------- #
#
# Internal / read-safe foundation for the THIRD domain axis (physical driver
# delivery flow). Both functions are self-scoped by `DriverProfile` and
# store-bound by `current_user.store_id`, reusing the same anti-enumeration
# 404 boundary as `get_driver_assignment`. There is NO transition logic here:
# `ensure_*` only materializes the initial `not_started` row; it never accepts
# an arbitrary state, never advances one, and never mutates the order, the
# assignment, inventory, or any audit/event log. Neither function is wired to
# an endpoint in G.3.


def _resolve_owned_assignment(
    db: Session,
    driver_profile: DriverProfile,
    current_user: User,
    assignment_id: UUID,
) -> OrderDriverAssignment:
    """Return the assignment iff it belongs to this driver and store.

    Raises 404 "Driver assignment not found" otherwise — a non-existent
    assignment, another driver's, or another store's are indistinguishable so
    existence never leaks across the scope boundary.
    """
    assignment = db.scalar(
        select(OrderDriverAssignment).where(
            OrderDriverAssignment.id == assignment_id,
            OrderDriverAssignment.driver_profile_id == driver_profile.id,
            OrderDriverAssignment.store_id == current_user.store_id,
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver assignment not found",
        )
    return assignment


def get_driver_delivery_operational_state(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverDeliveryOperationalStateRead:
    """Return the operational state of one of the driver's own assignments.

    Read-only and self-scoped (Dr.1.1.G.3). The assignment is resolved under
    the driver + store scope first; if it is not the driver's own, a generic
    404 "Driver assignment not found" is raised (anti-enumeration). If the
    assignment IS the driver's own but has no operational-state row yet, a
    distinct 404 "Driver delivery operational state not found" is raised — a
    pure `get_*` never materializes state. Never mutates, commits, or flushes.
    """
    driver_profile = get_driver_profile_for_user(db, current_user)
    assignment = _resolve_owned_assignment(
        db, driver_profile, current_user, assignment_id
    )

    operational_state = db.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id,
            DriverDeliveryOperationalState.driver_profile_id
            == driver_profile.id,
            DriverDeliveryOperationalState.store_id == current_user.store_id,
        )
    )
    if operational_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver delivery operational state not found",
        )

    return DriverDeliveryOperationalStateRead.model_validate(
        operational_state
    )


def ensure_driver_delivery_operational_state(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverDeliveryOperationalStateRead:
    """Return (creating if absent) the assignment's initial operational state.

    Self-scoped (Dr.1.1.G.3): the assignment must belong to the current driver
    and store, else 404 "Driver assignment not found" (anti-enumeration). If a
    state row already exists it is returned unchanged; otherwise exactly one
    row is created with `state = not_started` and anchors copied from the
    assignment.

    Idempotent: concurrent first-calls are guarded by the UNIQUE(assignment_id)
    constraint — on a race the IntegrityError is swallowed and the now-existing
    row is returned. This is the ONLY write in the operational-state layer for
    G.3; it never accepts an external state, advances a state, or mutates the
    order, the assignment, inventory, or any audit log.
    """
    driver_profile = get_driver_profile_for_user(db, current_user)
    assignment = _resolve_owned_assignment(
        db, driver_profile, current_user, assignment_id
    )

    existing = db.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    if existing is not None:
        return DriverDeliveryOperationalStateRead.model_validate(existing)

    operational_state = DriverDeliveryOperationalState(
        assignment_id=assignment.id,
        order_id=assignment.order_id,
        driver_profile_id=assignment.driver_profile_id,
        store_id=assignment.store_id,
        state=DriverDeliveryOperationalStateValue.not_started.value,
    )
    db.add(operational_state)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent caller won the UNIQUE(assignment_id) race; return the
        # row they created instead of duplicating or failing.
        db.rollback()
        existing = db.scalar(
            select(DriverDeliveryOperationalState).where(
                DriverDeliveryOperationalState.assignment_id == assignment.id
            )
        )
        if existing is None:
            raise
        return DriverDeliveryOperationalStateRead.model_validate(existing)

    db.refresh(operational_state)
    return DriverDeliveryOperationalStateRead.model_validate(
        operational_state
    )


# --------------------------------------------------------------------- #
# Assignment accept / decline (Dr.1.1.I)
# --------------------------------------------------------------------- #
#
# The first driver-side MUTATIONS. A driver accepts or declines one of their
# OWN offered assignments. These are self-scoped + store-bound, reuse the same
# anti-enumeration 404 boundary, and mutate ONLY the assignment's `status` and
# its `accepted_at` / `declined_at` timestamp. They never touch Order.status,
# inventory, the operational-state row (no `ensure_*`), `assigned_at` /
# `canceled_at` / `completed_at`, or any audit log.
#
# Only `offered` is a valid source: offered -> accepted (accept) and
# offered -> declined (decline). Repeating the SAME decision is idempotent
# (200, timestamp not rewritten). The OPPOSITE terminal decision is a 409
# conflict. Every other source status (expired / canceled / completed /
# started / assigned) is a 422 invalid transition — mirroring the
# 422-for-transition / 409-for-conflict convention in `services.orders`.


def _decide_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
    *,
    accept: bool,
) -> DriverAssignmentRead:
    """Shared accept/decline core. `accept=True` accepts, else declines.

    The assignment is loaded under a row lock (`with_for_update`) so the
    status is re-checked against fresh state before mutating — two concurrent
    decisions cannot both win. Mutates only `status` + the decision's
    timestamp; commits once.
    """
    driver_profile = get_driver_profile_for_user(db, current_user)

    assignment = db.scalar(
        select(OrderDriverAssignment)
        .where(
            OrderDriverAssignment.id == assignment_id,
            OrderDriverAssignment.driver_profile_id == driver_profile.id,
            OrderDriverAssignment.store_id == current_user.store_id,
        )
        .with_for_update()
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver assignment not found",
        )

    offered = OrderDriverAssignmentStatus.offered.value
    target = (
        OrderDriverAssignmentStatus.accepted.value
        if accept
        else OrderDriverAssignmentStatus.declined.value
    )
    opposite = (
        OrderDriverAssignmentStatus.declined.value
        if accept
        else OrderDriverAssignmentStatus.accepted.value
    )
    verb = "accepted" if accept else "declined"
    current = assignment.status

    if current == offered:
        assignment.status = target
        now = datetime.now(timezone.utc)
        if accept:
            assignment.accepted_at = now
        else:
            assignment.declined_at = now
        db.commit()
        db.refresh(assignment)
    elif current == target:
        # Idempotent repeat of the same decision: return unchanged, never
        # rewrite the timestamp. Release the row lock.
        db.commit()
    elif current == opposite:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Assignment already {opposite}",
        )
    else:
        # expired / canceled / completed / started / assigned.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Assignment cannot be {verb} from status '{current}'"
            ),
        )

    return DriverAssignmentRead.model_validate(assignment)


def accept_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverAssignmentRead:
    """Accept one of the current driver's own offered assignments (Dr.1.1.I).

    offered -> accepted (sets `accepted_at`). An already-accepted assignment
    is returned idempotently (200, `accepted_at` unchanged). An already-
    declined assignment is a 409 conflict. Any other source status is a 422
    invalid transition. Self-scoped + store-bound; a non-own/foreign/missing
    assignment is a 404 "Driver assignment not found". Mutates only the
    assignment's status/`accepted_at`; touches nothing else.
    """
    return _decide_driver_assignment(
        db, current_user, assignment_id, accept=True
    )


def decline_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverAssignmentRead:
    """Decline one of the current driver's own offered assignments (Dr.1.1.I).

    offered -> declined (sets `declined_at`). An already-declined assignment
    is returned idempotently (200, `declined_at` unchanged). An already-
    accepted assignment is a 409 conflict. Any other source status is a 422
    invalid transition. Self-scoped + store-bound; a non-own/foreign/missing
    assignment is a 404 "Driver assignment not found". Mutates only the
    assignment's status/`declined_at`; touches nothing else.
    """
    return _decide_driver_assignment(
        db, current_user, assignment_id, accept=False
    )
