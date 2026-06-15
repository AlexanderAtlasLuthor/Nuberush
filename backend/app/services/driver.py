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


# --------------------------------------------------------------------- #
# Start delivery / en route to store (Dr.1.1.J)
# --------------------------------------------------------------------- #
#
# The bridge between the assignment lifecycle and the physical delivery flow.
# A driver STARTS an accepted assignment: the assignment moves
# accepted -> started AND the operational state is materialized/advanced to
# `en_route_to_store`, atomically (one commit, both rows row-locked). Self-
# scoped + store-bound, same anti-enumeration 404. It never touches
# Order.status, inventory, `accepted_at` / `declined_at` / `assigned_at` /
# `canceled_at` / `completed_at`, or any audit log, and it never adds an
# `started_at` column (the physical-flow timing lives in the operational
# state's `state_started_at` / `last_transition_at`).
#
# Valid assignment sources: `accepted` (real transition) and `started`
# (idempotent). Every other status is a 422 invalid transition. Operational
# state: none / not_started -> en_route_to_store (real); en_route_to_store ->
# idempotent (no timestamp rewrite); a later non-terminal physical state ->
# 409 (never regress); a terminal state -> 422.

# Physical states strictly after en_route_to_store but NOT terminal — starting
# again would regress the flow, so they are a 409 conflict.
_STARTED_PAST_EN_ROUTE_STATES: frozenset[str] = frozenset(
    {
        DriverDeliveryOperationalStateValue.arrived_at_store.value,
        DriverDeliveryOperationalStateValue.pickup_started.value,
        DriverDeliveryOperationalStateValue.picked_up.value,
        DriverDeliveryOperationalStateValue.en_route_to_customer.value,
        DriverDeliveryOperationalStateValue.arrived_at_customer.value,
        DriverDeliveryOperationalStateValue.id_verification_pending.value,
        DriverDeliveryOperationalStateValue.id_verified.value,
        DriverDeliveryOperationalStateValue.returning_to_store.value,
    }
)

# Terminal physical states — a finished/failed/returned/canceled delivery can
# never be (re)started; a 422 invalid transition.
_TERMINAL_OPERATIONAL_STATES: frozenset[str] = frozenset(
    {
        DriverDeliveryOperationalStateValue.delivery_completed.value,
        DriverDeliveryOperationalStateValue.delivery_failed.value,
        DriverDeliveryOperationalStateValue.returned_to_store.value,
        DriverDeliveryOperationalStateValue.canceled.value,
    }
)


def _apply_start_to_existing_state(
    db: Session,
    assignment: OrderDriverAssignment,
    operational_state: DriverDeliveryOperationalState,
) -> DriverDeliveryOperationalStateRead:
    """Advance a row-locked operational state for a start (Dr.1.1.J).

    The caller has already validated and locked the assignment (status in
    {accepted, started}) and locked this state row. Mutates within the
    caller's transaction and commits once.
    """
    en_route = DriverDeliveryOperationalStateValue.en_route_to_store.value
    not_started = DriverDeliveryOperationalStateValue.not_started.value
    started = OrderDriverAssignmentStatus.started.value
    current_state = operational_state.state

    if current_state == not_started:
        now = datetime.now(timezone.utc)
        operational_state.state = en_route
        operational_state.state_started_at = now
        operational_state.last_transition_at = now
        assignment.status = started
        db.commit()
        db.refresh(operational_state)
    elif current_state == en_route:
        # Idempotent: never rewrite the physical-flow timestamps. Keep the
        # assignment consistent (it should already be `started`).
        if assignment.status != started:
            assignment.status = started
        db.commit()
        db.refresh(operational_state)
    elif current_state in _TERMINAL_OPERATIONAL_STATES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Assignment cannot be started from operational state "
                f"'{current_state}'"
            ),
        )
    else:
        # arrived_at_store and later non-terminal physical states.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already past en_route_to_store",
        )

    return DriverDeliveryOperationalStateRead.model_validate(
        operational_state
    )


def _resolve_locked_owned_assignment(
    db: Session,
    driver_profile: DriverProfile,
    current_user: User,
    assignment_id: UUID,
) -> OrderDriverAssignment:
    """Load the own assignment FOR UPDATE, or raise the 404 scope boundary."""
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
    return assignment


def start_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverDeliveryOperationalStateRead:
    """Start the physical delivery of an accepted assignment (Dr.1.1.J).

    accepted -> started on the assignment, and the operational state is
    created (or advanced from not_started) to `en_route_to_store`, atomically.
    Idempotent once `started` / `en_route_to_store`. A later non-terminal
    physical state is a 409 (never regress); a terminal state, or an
    assignment status other than accepted/started, is a 422. Self-scoped +
    store-bound; a non-own/foreign/missing assignment is a 404. Returns the
    operational state. Never touches Order.status, inventory, or any other
    assignment timestamp.
    """
    accepted = OrderDriverAssignmentStatus.accepted.value
    started = OrderDriverAssignmentStatus.started.value
    en_route = DriverDeliveryOperationalStateValue.en_route_to_store.value

    driver_profile = get_driver_profile_for_user(db, current_user)

    # One retry to absorb a concurrent first-start that wins the
    # UNIQUE(assignment_id) race on the operational-state insert.
    for _attempt in range(2):
        assignment = _resolve_locked_owned_assignment(
            db, driver_profile, current_user, assignment_id
        )
        if assignment.status not in (accepted, started):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Assignment cannot be started from status "
                    f"'{assignment.status}'"
                ),
            )

        operational_state = db.scalar(
            select(DriverDeliveryOperationalState)
            .where(
                DriverDeliveryOperationalState.assignment_id
                == assignment.id
            )
            .with_for_update()
        )
        if operational_state is not None:
            return _apply_start_to_existing_state(
                db, assignment, operational_state
            )

        # No state yet — create it directly as en_route_to_store and move the
        # assignment to started in the same transaction.
        operational_state = DriverDeliveryOperationalState(
            assignment_id=assignment.id,
            order_id=assignment.order_id,
            driver_profile_id=assignment.driver_profile_id,
            store_id=assignment.store_id,
            state=en_route,
        )
        db.add(operational_state)
        assignment.status = started
        try:
            db.commit()
        except IntegrityError:
            # A concurrent caller created the state row first; retry the loop,
            # which will now find and advance the existing row idempotently.
            db.rollback()
            continue
        db.refresh(operational_state)
        return DriverDeliveryOperationalStateRead.model_validate(
            operational_state
        )

    # The retry observed a race; the row now exists — advance it.
    assignment = _resolve_locked_owned_assignment(
        db, driver_profile, current_user, assignment_id
    )
    if assignment.status not in (accepted, started):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Assignment cannot be started from status "
                f"'{assignment.status}'"
            ),
        )
    operational_state = db.scalar(
        select(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
        .with_for_update()
    )
    if operational_state is None:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not start delivery; please retry.",
        )
    return _apply_start_to_existing_state(db, assignment, operational_state)


# --------------------------------------------------------------------- #
# Arrival at store (Dr.1.1.K)
# --------------------------------------------------------------------- #
#
# The next physical step after Dr.1.1.J's start. A driver who has already
# started delivery and is `en_route_to_store` confirms physical ARRIVAL at the
# store: the operational state advances `en_route_to_store -> arrived_at_store`.
# Self-scoped + store-bound, same anti-enumeration 404 boundary. It NEVER
# touches Order.status, inventory, the assignment's `status` (which stays
# `started`), or any assignment timestamp (`assigned_at` / `accepted_at` /
# `declined_at` / `canceled_at` / `completed_at`), and writes no audit log.
#
# Unlike start, arrival NEVER creates the operational-state row — start is the
# only materializer. A missing row (or `not_started`) means the delivery is not
# yet en route, so arrival is a 422 precondition failure.
#
# Assignment source: only `started` is valid; every other status is a 422.
# Operational state: en_route_to_store -> arrived_at_store (real);
# arrived_at_store -> idempotent (no timestamp rewrite); not_started / missing
# -> 422 (not yet en route); a later non-terminal physical state -> 409 (never
# regress); a terminal state -> 422.

# Physical states strictly after arrived_at_store but NOT terminal — arriving
# again would regress the flow, so they are a 409 conflict.
_ARRIVED_PAST_STORE_STATES: frozenset[str] = frozenset(
    {
        DriverDeliveryOperationalStateValue.pickup_started.value,
        DriverDeliveryOperationalStateValue.picked_up.value,
        DriverDeliveryOperationalStateValue.en_route_to_customer.value,
        DriverDeliveryOperationalStateValue.arrived_at_customer.value,
        DriverDeliveryOperationalStateValue.id_verification_pending.value,
        DriverDeliveryOperationalStateValue.id_verified.value,
        DriverDeliveryOperationalStateValue.returning_to_store.value,
    }
)


def _apply_arrive_to_existing_state(
    db: Session,
    operational_state: DriverDeliveryOperationalState,
) -> DriverDeliveryOperationalStateRead:
    """Advance a row-locked operational state for an arrival (Dr.1.1.K).

    The caller has already validated and locked the assignment (status
    `started`) and locked this state row. Unlike start, this NEVER creates a
    row and NEVER mutates the assignment. Mutates within the caller's
    transaction and commits once.
    """
    en_route = DriverDeliveryOperationalStateValue.en_route_to_store.value
    arrived = DriverDeliveryOperationalStateValue.arrived_at_store.value
    not_started = DriverDeliveryOperationalStateValue.not_started.value
    current_state = operational_state.state

    if current_state == en_route:
        now = datetime.now(timezone.utc)
        operational_state.state = arrived
        operational_state.state_started_at = now
        operational_state.last_transition_at = now
        db.commit()
        db.refresh(operational_state)
    elif current_state == arrived:
        # Idempotent: never rewrite the physical-flow timestamps.
        db.commit()
        db.refresh(operational_state)
    elif current_state == not_started:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery not yet en route to store",
        )
    elif current_state in _TERMINAL_OPERATIONAL_STATES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Assignment cannot arrive at store from operational state "
                f"'{current_state}'"
            ),
        )
    else:
        # pickup_started and later non-terminal physical states.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already past arrived_at_store",
        )

    return DriverDeliveryOperationalStateRead.model_validate(
        operational_state
    )


def arrive_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverDeliveryOperationalStateRead:
    """Confirm physical arrival at the store for a started assignment (K).

    The operational state advances `en_route_to_store -> arrived_at_store`.
    Idempotent once `arrived_at_store` (timestamps preserved). A `not_started`
    or missing state row is a 422 "Delivery not yet en route to store" (arrival
    never materializes state). A later non-terminal physical state is a 409
    (never regress); a terminal state, or an assignment status other than
    `started`, is a 422. Self-scoped + store-bound; a non-own/foreign/missing
    assignment is a 404. Returns the operational state. Never touches
    Order.status, inventory, the assignment's status, or any assignment
    timestamp.
    """
    started = OrderDriverAssignmentStatus.started.value

    driver_profile = get_driver_profile_for_user(db, current_user)
    assignment = _resolve_locked_owned_assignment(
        db, driver_profile, current_user, assignment_id
    )
    if assignment.status != started:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Assignment cannot arrive at store from status "
                f"'{assignment.status}'"
            ),
        )

    operational_state = db.scalar(
        select(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
        .with_for_update()
    )
    if operational_state is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery not yet en route to store",
        )

    return _apply_arrive_to_existing_state(db, operational_state)


# --------------------------------------------------------------------- #
# Pickup at store (Dr.1.1.L — operational-only / L-mínima)
# --------------------------------------------------------------------- #
#
# The next physical step after Dr.1.1.K's arrival. A driver who has arrived at
# the store confirms PICKUP of the order: the operational state advances
# `arrived_at_store -> picked_up`. Self-scoped + store-bound, same anti-
# enumeration 404 boundary. Per the approved L-mínima scope this is OPERATIONAL
# STATE ONLY: it NEVER touches Order.status (no ready -> out_for_delivery, no
# OrderAuditLog), inventory, the assignment's `status` (which stays `started`),
# or any assignment timestamp. Order/OrderAuditLog/transition_order_status are
# deliberately NOT imported here — out_for_delivery is a future, dedicated phase
# (orders_rules §6/§8: driver<->orders bridging is staff-or-above + audited).
#
# Like arrive-store, pickup NEVER creates the operational-state row — start is
# the only materializer. A missing row (or any state before arrived_at_store)
# means the delivery has not yet arrived, so pickup is a 422 precondition
# failure.
#
# Assignment source: only `started` is valid; every other status is a 422.
# Operational state: arrived_at_store -> picked_up (real); picked_up ->
# idempotent (no timestamp rewrite); not_started / en_route_to_store /
# pickup_started / missing -> 422 (not yet arrived); a later non-terminal
# physical state -> 409 (never regress); a terminal state -> 422.

# Physical states strictly after picked_up but NOT terminal — picking up again
# would regress the flow, so they are a 409 conflict.
_PICKED_UP_PAST_STATES: frozenset[str] = frozenset(
    {
        DriverDeliveryOperationalStateValue.en_route_to_customer.value,
        DriverDeliveryOperationalStateValue.arrived_at_customer.value,
        DriverDeliveryOperationalStateValue.id_verification_pending.value,
        DriverDeliveryOperationalStateValue.id_verified.value,
        DriverDeliveryOperationalStateValue.returning_to_store.value,
    }
)

# Physical states at or before arrived_at_store's successor that are NOT yet a
# valid pickup source — the delivery has not (validly) arrived at the store.
# `pickup_started` is included: it is a finer-grained handoff state that L does
# not produce, and pickup advances arrived_at_store -> picked_up directly.
_BEFORE_PICKUP_STATES: frozenset[str] = frozenset(
    {
        DriverDeliveryOperationalStateValue.not_started.value,
        DriverDeliveryOperationalStateValue.en_route_to_store.value,
        DriverDeliveryOperationalStateValue.pickup_started.value,
    }
)


def _apply_pickup_to_existing_state(
    db: Session,
    operational_state: DriverDeliveryOperationalState,
) -> DriverDeliveryOperationalStateRead:
    """Advance a row-locked operational state for a pickup (Dr.1.1.L).

    The caller has already validated and locked the assignment (status
    `started`) and locked this state row. Like arrive-store, this NEVER creates
    a row and NEVER mutates the assignment, Order.status, or inventory. Mutates
    within the caller's transaction and commits once.
    """
    arrived = DriverDeliveryOperationalStateValue.arrived_at_store.value
    picked_up = DriverDeliveryOperationalStateValue.picked_up.value
    current_state = operational_state.state

    if current_state == arrived:
        now = datetime.now(timezone.utc)
        operational_state.state = picked_up
        operational_state.state_started_at = now
        operational_state.last_transition_at = now
        db.commit()
        db.refresh(operational_state)
    elif current_state == picked_up:
        # Idempotent: never rewrite the physical-flow timestamps.
        db.commit()
        db.refresh(operational_state)
    elif current_state in _BEFORE_PICKUP_STATES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery not yet arrived at store",
        )
    elif current_state in _TERMINAL_OPERATIONAL_STATES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery already ended",
        )
    else:
        # en_route_to_customer and later non-terminal physical states.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already past picked_up",
        )

    return DriverDeliveryOperationalStateRead.model_validate(
        operational_state
    )


def pickup_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverDeliveryOperationalStateRead:
    """Confirm pickup of the order at the store for a started assignment (L).

    The operational state advances `arrived_at_store -> picked_up`. Idempotent
    once `picked_up` (timestamps preserved). A state before arrived_at_store
    (not_started / en_route_to_store / pickup_started) or a missing state row is
    a 422 "Delivery not yet arrived at store" (pickup never materializes state).
    A later non-terminal physical state is a 409 (never regress); a terminal
    state, or an assignment status other than `started`, is a 422. Self-scoped +
    store-bound; a non-own/foreign/missing assignment is a 404. Returns the
    operational state. Never touches Order.status, inventory, the assignment's
    status, or any assignment timestamp.
    """
    started = OrderDriverAssignmentStatus.started.value

    driver_profile = get_driver_profile_for_user(db, current_user)
    assignment = _resolve_locked_owned_assignment(
        db, driver_profile, current_user, assignment_id
    )
    if assignment.status != started:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Assignment cannot pickup from status "
                f"'{assignment.status}'"
            ),
        )

    operational_state = db.scalar(
        select(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
        .with_for_update()
    )
    if operational_state is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery not yet arrived at store",
        )

    return _apply_pickup_to_existing_state(db, operational_state)


# Physical states strictly after en_route_to_customer but NOT terminal —
# departing again would regress the flow, so they are a 409 conflict.
_EN_ROUTE_CUSTOMER_PAST_STATES: frozenset[str] = frozenset(
    {
        DriverDeliveryOperationalStateValue.arrived_at_customer.value,
        DriverDeliveryOperationalStateValue.id_verification_pending.value,
        DriverDeliveryOperationalStateValue.id_verified.value,
        DriverDeliveryOperationalStateValue.returning_to_store.value,
    }
)

# Physical states at or before picked_up's predecessor that are NOT yet a
# valid depart-to-customer source — the order has not (validly) been picked
# up. `pickup_started` is included: it is a finer-grained handoff state that M
# does not produce, and depart advances picked_up -> en_route_to_customer
# directly.
_BEFORE_DEPART_STATES: frozenset[str] = frozenset(
    {
        DriverDeliveryOperationalStateValue.not_started.value,
        DriverDeliveryOperationalStateValue.en_route_to_store.value,
        DriverDeliveryOperationalStateValue.arrived_at_store.value,
        DriverDeliveryOperationalStateValue.pickup_started.value,
    }
)


def _apply_depart_to_customer_to_existing_state(
    db: Session,
    operational_state: DriverDeliveryOperationalState,
) -> DriverDeliveryOperationalStateRead:
    """Advance a row-locked operational state for a depart (Dr.1.1.M).

    The caller has already validated and locked the assignment (status
    `started`) and locked this state row. Like pickup, this NEVER creates a row
    and NEVER mutates the assignment, Order.status, OrderAuditLog, or inventory.
    Mutates within the caller's transaction and commits once.
    """
    picked_up = DriverDeliveryOperationalStateValue.picked_up.value
    en_route_customer = (
        DriverDeliveryOperationalStateValue.en_route_to_customer.value
    )
    current_state = operational_state.state

    if current_state == picked_up:
        now = datetime.now(timezone.utc)
        operational_state.state = en_route_customer
        operational_state.state_started_at = now
        operational_state.last_transition_at = now
        db.commit()
        db.refresh(operational_state)
    elif current_state == en_route_customer:
        # Idempotent: never rewrite the physical-flow timestamps.
        db.commit()
        db.refresh(operational_state)
    elif current_state in _BEFORE_DEPART_STATES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery not yet picked up",
        )
    elif current_state in _TERMINAL_OPERATIONAL_STATES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery already ended",
        )
    elif current_state in _EN_ROUTE_CUSTOMER_PAST_STATES:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already past en_route_to_customer",
        )
    else:
        # Defensive: any unexpected/unknown state is a non-permissive 409,
        # never a silent pass-through (mirrors pickup/start/arrive-store).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already past en_route_to_customer",
        )

    return DriverDeliveryOperationalStateRead.model_validate(
        operational_state
    )


def depart_driver_assignment(
    db: Session,
    current_user: User,
    assignment_id: UUID,
) -> DriverDeliveryOperationalStateRead:
    """Depart the store toward the customer for a started assignment (M).

    The operational state advances `picked_up -> en_route_to_customer`.
    Idempotent once `en_route_to_customer` (timestamps preserved). A state
    before picked_up (not_started / en_route_to_store / arrived_at_store /
    pickup_started) or a missing state row is a 422 "Delivery not yet picked
    up" (depart never materializes state). A later non-terminal physical state
    is a 409 (never regress); a terminal state, or an assignment status other
    than `started`, is a 422. Self-scoped + store-bound; a non-own/foreign/
    missing assignment is a 404. Returns the operational state. Never touches
    Order.status, OrderAuditLog, inventory, the assignment's status, or any
    assignment timestamp.
    """
    started = OrderDriverAssignmentStatus.started.value

    driver_profile = get_driver_profile_for_user(db, current_user)
    assignment = _resolve_locked_owned_assignment(
        db, driver_profile, current_user, assignment_id
    )
    if assignment.status != started:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Assignment cannot depart-to-customer from status "
                f"'{assignment.status}'"
            ),
        )

    operational_state = db.scalar(
        select(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
        .with_for_update()
    )
    if operational_state is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Delivery not yet picked up",
        )

    return _apply_depart_to_customer_to_existing_state(
        db, operational_state
    )
