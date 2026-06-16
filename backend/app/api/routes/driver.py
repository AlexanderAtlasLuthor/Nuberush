"""Driver-facing routes (Dr.1.1.C / Dr.1.1.D / Dr.1.1.F / Dr.1.1.H / Dr.1.1.I).

Every endpoint is gated by `require_store_bound_driver` (Dr.1.1.B), so only
an exact, store-bound driver reaches it; staff/manager/owner/admin and
storeless drivers are rejected upstream with 403.

The driver runtime surface is five self-scoped, read-only GETs plus seven
driver-side mutations (Dr.1.1.I accept/decline, Dr.1.1.J start, Dr.1.1.K
arrive-store, Dr.1.1.L pickup, Dr.1.1.M depart-to-customer, Dr.1.1.N
arrive-customer):
  - GET  /driver/me                                       (Dr.1.1.C)
  - GET  /driver/eligibility                              (Dr.1.1.D)
  - GET  /driver/assignments                              (Dr.1.1.F)
  - GET  /driver/assignments/{id}                         (Dr.1.1.F)
  - GET  /driver/assignments/{id}/delivery-state          (Dr.1.1.H)
  - POST /driver/assignments/{id}/accept                  (Dr.1.1.I)
  - POST /driver/assignments/{id}/decline                 (Dr.1.1.I)
  - POST /driver/assignments/{id}/start                   (Dr.1.1.J)
  - POST /driver/assignments/{id}/arrive-store            (Dr.1.1.K)
  - POST /driver/assignments/{id}/pickup                  (Dr.1.1.L)
  - POST /driver/assignments/{id}/depart-to-customer      (Dr.1.1.M)
  - POST /driver/assignments/{id}/arrive-customer         (Dr.1.1.N)
  - POST /driver/assignments/{id}/verify-age              (Dr.1.2.C)
  - POST /driver/assignments/{id}/proof                   (Dr.1.2.D)
  - POST /driver/assignments/{id}/complete                (Dr.1.2.E)

accept/decline mutate ONLY the assignment's status + accepted_at/declined_at
(offered -> accepted/declined). start moves the assignment accepted -> started
and the operational state to en_route_to_store (no Order.status, no inventory).
arrive-store advances ONLY the operational state en_route_to_store ->
arrived_at_store (assignment stays started; no Order.status, no inventory).
pickup advances ONLY the operational state arrived_at_store -> picked_up
(assignment stays started; no Order.status, no OrderAuditLog, no inventory).
depart-to-customer advances ONLY the operational state picked_up ->
en_route_to_customer (assignment stays started; no Order.status, no
OrderAuditLog, no inventory).
arrive-customer advances ONLY the operational state en_route_to_customer ->
arrived_at_customer (assignment stays started; no Order.status, no
OrderAuditLog, no inventory, no ID verification).
verify-age (Dr.1.2.C) records a redaction-safe manual 21+ checklist result on
an arrived-at-customer assignment and, on a `pass`, advances ONLY the
operational state arrived_at_customer -> id_verified (assignment stays started;
no Order.status, no Order.age_verified_at, no OrderAuditLog, no inventory);
`fail` / `manual_review` record the attempt and keep the state at
arrived_at_customer.
proof (Dr.1.2.D) records a redaction-safe manual proof-of-delivery checklist on
an id_verified assignment (record-only: state stays id_verified; assignment
stays started; no Order.status, no Order.age_verified_at, no OrderAuditLog, no
inventory). It is idempotent per assignment and never stores a photo,
signature, or uploaded artifact.
complete (Dr.1.2.E) promotes a fully-verified, proven delivery: it advances the
operational state id_verified -> delivery_completed, closes the assignment
started -> completed, and promotes Order.status ready/out_for_delivery ->
delivered EXCLUSIVELY through the orders authority bridge (which owns the
inventory consume and the OrderAuditLog). The driver layer never writes
Order.status or touches inventory directly.
fail/return-to-store, store return confirmation, id-verification
(vendor/scan/OCR), go-online/go-offline, dispatch, GPS, and location are later
subphases and must not be added here. There is no PATCH/PUT/DELETE on the
/driver surface, and no POST beyond accept/decline/start/arrive-store/pickup/
depart-to-customer/arrive-customer/verify-age/proof/complete. The
delivery-state read (Dr.1.1.H) never materializes state.
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
from app.schemas.driver import DriverDeliveryProofRead
from app.schemas.driver import DriverDeliveryVerificationRead
from app.schemas.driver import DriverEligibilityRead
from app.schemas.driver import DriverProfileRead
from app.schemas.driver import DriverProofSubmitRequest
from app.schemas.driver import DriverVerifyAgeRequest
from app.services.driver import accept_driver_assignment
from app.services.driver import arrive_customer_driver_assignment
from app.services.driver import arrive_driver_assignment
from app.services.driver import decline_driver_assignment
from app.services.driver import depart_driver_assignment
from app.services.driver import evaluate_driver_eligibility
from app.services.driver import get_driver_assignment
from app.services.driver import get_driver_delivery_operational_state
from app.services.driver import get_driver_profile_for_user
from app.services.driver import list_driver_assignments
from app.services.driver import pickup_driver_assignment
from app.services.driver import complete_delivery_driver_assignment
from app.services.driver import start_driver_assignment
from app.services.driver import submit_proof_driver_assignment
from app.services.driver import verify_age_driver_assignment

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


@router.post(
    "/assignments/{assignment_id}/start",
    response_model=DriverDeliveryOperationalStateRead,
)
def start_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryOperationalStateRead:
    """Start the physical delivery of an accepted assignment (Dr.1.1.J).

    Moves the assignment accepted -> started and the operational state to
    `en_route_to_store` (creating it if absent), atomically. Idempotent once
    started / en_route_to_store; 409 if the delivery is already past
    en_route_to_store; 422 from any other assignment status or a terminal
    operational state; 404 (anti-enumeration) for a non-own / foreign /
    missing assignment. Returns the operational state; touches no Order.status
    or inventory.
    """
    return start_driver_assignment(db, current_user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/arrive-store",
    response_model=DriverDeliveryOperationalStateRead,
)
def arrive_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryOperationalStateRead:
    """Confirm physical arrival at the store for a started assignment (K).

    Advances ONLY the operational state en_route_to_store -> arrived_at_store.
    Idempotent once arrived_at_store (timestamps preserved); 409 if the
    delivery is already past arrived_at_store; 422 if the delivery is not yet
    en route (not_started / no state row), from a terminal operational state,
    or from an assignment status other than started; 404 (anti-enumeration)
    for a non-own / foreign / missing assignment. Returns the operational
    state. The assignment stays `started`; touches no Order.status, inventory,
    or assignment timestamp. Arrival never materializes state.
    """
    return arrive_driver_assignment(db, current_user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/pickup",
    response_model=DriverDeliveryOperationalStateRead,
)
def pickup_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryOperationalStateRead:
    """Confirm pickup of the order at the store for a started assignment (L).

    Advances ONLY the operational state arrived_at_store -> picked_up.
    Idempotent once picked_up (timestamps preserved); 409 if the delivery is
    already past picked_up; 422 if the delivery has not yet arrived at the store
    (not_started / en_route_to_store / pickup_started / no state row), from a
    terminal operational state, or from an assignment status other than started;
    404 (anti-enumeration) for a non-own / foreign / missing assignment. Returns
    the operational state. Per the approved L-mínima scope, the assignment stays
    `started` and this touches no Order.status, no OrderAuditLog, no inventory,
    and no assignment timestamp. Pickup never materializes state.
    """
    return pickup_driver_assignment(db, current_user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/depart-to-customer",
    response_model=DriverDeliveryOperationalStateRead,
)
def depart_to_customer_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryOperationalStateRead:
    """Depart the store toward the customer for a started assignment (M).

    Advances ONLY the operational state picked_up -> en_route_to_customer.
    Idempotent once en_route_to_customer (timestamps preserved); 409 if the
    delivery is already past en_route_to_customer; 422 if the delivery has not
    yet been picked up (not_started / en_route_to_store / arrived_at_store /
    pickup_started / no state row), from a terminal operational state, or from
    an assignment status other than started; 404 (anti-enumeration) for a
    non-own / foreign / missing assignment. Returns the operational state. Per
    the approved M-mínima scope, the assignment stays `started` and this
    touches no Order.status, no OrderAuditLog, no inventory, and no assignment
    timestamp. Depart never materializes state.
    """
    return depart_driver_assignment(db, current_user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/arrive-customer",
    response_model=DriverDeliveryOperationalStateRead,
)
def arrive_customer_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryOperationalStateRead:
    """Mark arrival at the customer for a started assignment (N).

    Advances ONLY the operational state en_route_to_customer ->
    arrived_at_customer. Idempotent once arrived_at_customer (timestamps
    preserved); 409 if the delivery is already past arrived_at_customer; 422 if
    the delivery is not yet en route to the customer (not_started /
    en_route_to_store / arrived_at_store / pickup_started / picked_up / no
    state row), from a terminal operational state, or from an assignment status
    other than started; 404 (anti-enumeration) for a non-own / foreign /
    missing assignment. Returns the operational state. Per the approved
    N-mínima scope, the assignment stays `started` and this touches no
    Order.status, no OrderAuditLog, no inventory, no assignment timestamp, and
    never starts ID verification. Arrive-customer never materializes state.
    """
    return arrive_customer_driver_assignment(db, current_user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/verify-age",
    response_model=DriverDeliveryVerificationRead,
)
def verify_age_current_driver_assignment(
    assignment_id: UUID,
    payload: DriverVerifyAgeRequest,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryVerificationRead:
    """Record a delivery-time 21+ / age verification result (Dr.1.2.C).

    Submits a backend-authorized, redaction-safe manual checklist outcome on an
    arrived-at-customer assignment. A `pass` advances the operational state
    arrived_at_customer -> id_verified; `fail` / `manual_review` record the
    attempt and keep the state at arrived_at_customer (routing a failed check
    to failed delivery / return-to-store is a later subphase). Re-issuing a
    `pass` once id_verified is idempotent (no new row); a `fail` /
    `manual_review` once id_verified is a 409. A state before
    arrived_at_customer / a missing state row / a terminal state / an
    assignment status other than `started` is a 422; any other later
    non-terminal state is a 409; a non-own / foreign / missing assignment is a
    404. The MVP is a manual checklist only (no OCR / scan / vendor /
    liveness). Returns the verification record (redaction-safe; no PII, no
    Order.status, no Order.age_verified_at, no inventory). Never materializes
    operational state.
    """
    return verify_age_driver_assignment(
        db, current_user, assignment_id, payload
    )


@router.post(
    "/assignments/{assignment_id}/proof",
    response_model=DriverDeliveryProofRead,
)
def submit_proof_current_driver_assignment(
    assignment_id: UUID,
    payload: DriverProofSubmitRequest,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryProofRead:
    """Record a redaction-safe proof of delivery (Dr.1.2.D).

    Submits a backend-authorized manual proof-of-delivery checklist on an
    id_verified assignment (all three handoff confirmations required and must
    be true). The first proof records a `DriverDeliveryProof`; a later proof on
    the same assignment is idempotent (returns the existing latest proof, no
    duplicate row). Proof is record-only: the operational state stays
    `id_verified` (promotion to delivery_completed / Order.status delivered is
    a later subphase). A state before id_verified (incl. arrived_at_customer /
    id_verification_pending) / a missing state row / a terminal state / an
    assignment status other than `started` is a 422; any other later
    non-terminal state is a 409; a non-own / foreign / missing assignment is a
    404. The MVP is a manual checklist only (no photo / signature / uploaded
    artifact). Returns the proof record (redaction-safe; no PII, no
    Order.status, no Order.age_verified_at, no inventory). Never materializes
    operational state.
    """
    return submit_proof_driver_assignment(
        db, current_user, assignment_id, payload
    )


@router.post(
    "/assignments/{assignment_id}/complete",
    response_model=DriverDeliveryOperationalStateRead,
)
def complete_current_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_store_bound_driver),
    db: Session = Depends(get_db),
) -> DriverDeliveryOperationalStateRead:
    """Complete a fully-verified, proven delivery (Dr.1.2.E).

    Gated on assignment.status == started, operational state id_verified, a
    passed verify-age, a recorded proof, and an order in ready /
    out_for_delivery. On success the operational state advances
    id_verified -> delivery_completed, the assignment closes started ->
    completed, and the commercial promotion to Order.status `delivered`
    (with its inventory consume and OrderAuditLog) goes exclusively through
    the orders authority bridge — the driver layer never writes Order.status
    or touches inventory. Idempotent once completed. A state before
    id_verified / a missing state row / a missing verification pass / a missing
    proof / a terminal state / an assignment status other than started is a
    422; returning_to_store or an inconsistent completed state is a 409; a
    non-own / foreign / missing assignment is a 404. Empty body; returns the
    operational state (delivery_completed).
    """
    return complete_delivery_driver_assignment(
        db, current_user, assignment_id
    )
