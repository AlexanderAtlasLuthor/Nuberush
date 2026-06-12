"""Dr.1.1.F — driver assigned-delivery read service tests.

Exercises `list_driver_assignments` and `get_driver_assignment`: self-scoping
by `DriverProfile`, store binding, the default active-status filter vs the
explicit `status` filter, ordering, pagination, the 404 boundaries, and the
read-only (no-mutation) guarantee.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DriverProfile
from app.db.models import Order
from app.db.models import OrderDriverAssignment
from app.db.models import OrderDriverAssignmentStatus
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services.driver import get_driver_assignment
from app.services.driver import list_driver_assignments
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DAS-Store") -> Store:
        store = Store(name=name, code=f"das-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def _ids(response) -> list:
    return [item.id for item in response.items]


# --------------------------------------------------------------------- #
# 1-3. Self-scope + tenancy
# --------------------------------------------------------------------- #


def test_list_returns_only_current_drivers_assignments(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    my_profile = make_driver_profile(db_session, user=me, store=store)
    order = make_order(db_session, store=store)
    mine = make_order_driver_assignment(
        db_session, order=order, driver_profile=my_profile, store=store
    )

    # Another driver in the SAME store with their own assignment.
    other_user = _driver(db_session, store)
    other_profile = make_driver_profile(
        db_session, user=other_user, store=store
    )
    other_order = make_order(db_session, store=store)
    other_assignment = make_order_driver_assignment(
        db_session,
        order=other_order,
        driver_profile=other_profile,
        store=store,
    )

    resp = list_driver_assignments(db_session, me, limit=50, offset=0)

    assert _ids(resp) == [mine.id]
    assert resp.total == 1
    assert other_assignment.id not in _ids(resp)


def test_list_excludes_other_store_assignments(
    db_session: Session, make_store
) -> None:
    store_a = make_store("store-a")
    me = _driver(db_session, store_a)
    my_profile = make_driver_profile(db_session, user=me, store=store_a)
    order_a = make_order(db_session, store=store_a)
    mine = make_order_driver_assignment(
        db_session, order=order_a, driver_profile=my_profile, store=store_a
    )

    # An assignment in another store that points at MY profile id would be a
    # tenancy break — the store filter must still exclude it.
    store_b = make_store("store-b")
    order_b = make_order(db_session, store=store_b)
    foreign = make_order_driver_assignment(
        db_session,
        order=order_b,
        driver_profile=my_profile,
        store=store_b,
    )

    resp = list_driver_assignments(db_session, me, limit=50, offset=0)

    assert _ids(resp) == [mine.id]
    assert foreign.id not in _ids(resp)


# --------------------------------------------------------------------- #
# 4-7. get_driver_assignment scope + 404s
# --------------------------------------------------------------------- #


def test_get_returns_own_assignment(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    my_profile = make_driver_profile(db_session, user=me, store=store)
    order = make_order(db_session, store=store)
    mine = make_order_driver_assignment(
        db_session, order=order, driver_profile=my_profile, store=store
    )

    result = get_driver_assignment(db_session, me, mine.id)
    assert result.id == mine.id
    assert result.driver_profile_id == my_profile.id
    assert result.store_id == store.id


def test_get_other_driver_assignment_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    make_driver_profile(db_session, user=me, store=store)

    other_user = _driver(db_session, store)
    other_profile = make_driver_profile(
        db_session, user=other_user, store=store
    )
    other_order = make_order(db_session, store=store)
    other_assignment = make_order_driver_assignment(
        db_session,
        order=other_order,
        driver_profile=other_profile,
        store=store,
    )

    with pytest.raises(HTTPException) as exc:
        get_driver_assignment(db_session, me, other_assignment.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


def test_get_other_store_assignment_404(
    db_session: Session, make_store
) -> None:
    store_a = make_store("store-a")
    me = _driver(db_session, store_a)
    my_profile = make_driver_profile(db_session, user=me, store=store_a)

    store_b = make_store("store-b")
    order_b = make_order(db_session, store=store_b)
    foreign = make_order_driver_assignment(
        db_session,
        order=order_b,
        driver_profile=my_profile,
        store=store_b,
    )

    with pytest.raises(HTTPException) as exc:
        get_driver_assignment(db_session, me, foreign.id)
    assert exc.value.status_code == 404


def test_get_nonexistent_assignment_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    make_driver_profile(db_session, user=me, store=store)

    with pytest.raises(HTTPException) as exc:
        get_driver_assignment(db_session, me, uuid.uuid4())
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# 8-10. Default status filter vs explicit filter
# --------------------------------------------------------------------- #


def _seed_all_statuses(
    db_session: Session, store: Store, profile: DriverProfile
) -> dict:
    """One assignment per status value, returns {status_value: id}."""
    ids: dict = {}
    for status in OrderDriverAssignmentStatus:
        order = make_order(db_session, store=store)
        assignment = make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
            status=status.value,
        )
        ids[status.value] = assignment.id
    return ids


def test_default_list_includes_active_statuses(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=me, store=store)
    ids = _seed_all_statuses(db_session, store, profile)

    resp = list_driver_assignments(db_session, me, limit=200, offset=0)
    returned = set(_ids(resp))

    for active in ("offered", "accepted", "assigned", "started"):
        assert ids[active] in returned


def test_default_list_excludes_terminal_statuses(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=me, store=store)
    ids = _seed_all_statuses(db_session, store, profile)

    resp = list_driver_assignments(db_session, me, limit=200, offset=0)
    returned = set(_ids(resp))

    for terminal in ("declined", "expired", "completed", "canceled"):
        assert ids[terminal] not in returned
    assert resp.total == 4


@pytest.mark.parametrize(
    "status",
    [
        OrderDriverAssignmentStatus.declined,
        OrderDriverAssignmentStatus.expired,
        OrderDriverAssignmentStatus.completed,
        OrderDriverAssignmentStatus.canceled,
    ],
)
def test_status_filter_allows_terminal_statuses(
    db_session: Session, make_store, status
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=me, store=store)
    ids = _seed_all_statuses(db_session, store, profile)

    resp = list_driver_assignments(
        db_session, me, limit=200, offset=0, status=status
    )

    assert _ids(resp) == [ids[status.value]]
    assert resp.total == 1


# --------------------------------------------------------------------- #
# 11. Pagination
# --------------------------------------------------------------------- #


def test_limit_and_offset(db_session: Session, make_store) -> None:
    store = make_store()
    me = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=me, store=store)

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    created = []
    for i in range(5):
        order = make_order(db_session, store=store)
        a = make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
            status="assigned",
            created_at=base + timedelta(minutes=i),
        )
        created.append(a)

    # created_at desc => newest (i=4) first.
    expected_desc = [a.id for a in reversed(created)]

    page1 = list_driver_assignments(db_session, me, limit=2, offset=0)
    page2 = list_driver_assignments(db_session, me, limit=2, offset=2)
    page3 = list_driver_assignments(db_session, me, limit=2, offset=4)

    assert page1.total == 5
    assert _ids(page1) == expected_desc[0:2]
    assert _ids(page2) == expected_desc[2:4]
    assert _ids(page3) == expected_desc[4:5]


# --------------------------------------------------------------------- #
# 12. Ordering created_at desc, id desc
# --------------------------------------------------------------------- #


def test_ordering_created_at_desc_then_id_desc(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=me, store=store)

    older_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

    older = make_order_driver_assignment(
        db_session,
        order=make_order(db_session, store=store),
        driver_profile=profile,
        store=store,
        status="assigned",
        created_at=older_at,
    )
    # Two with an identical created_at — id desc breaks the tie.
    tie_a = make_order_driver_assignment(
        db_session,
        order=make_order(db_session, store=store),
        driver_profile=profile,
        store=store,
        status="assigned",
        created_at=newer_at,
    )
    tie_b = make_order_driver_assignment(
        db_session,
        order=make_order(db_session, store=store),
        driver_profile=profile,
        store=store,
        status="assigned",
        created_at=newer_at,
    )

    resp = list_driver_assignments(db_session, me, limit=50, offset=0)
    returned = _ids(resp)

    # Both newer rows precede the older one.
    assert returned[2] == older.id
    # Within the tie, higher id first.
    higher, lower = sorted([tie_a.id, tie_b.id], reverse=True)
    assert returned[0] == higher
    assert returned[1] == lower


# --------------------------------------------------------------------- #
# 13. Driver without profile -> 404
# --------------------------------------------------------------------- #


def test_list_driver_without_profile_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)  # no profile provisioned

    with pytest.raises(HTTPException) as exc:
        list_driver_assignments(db_session, me, limit=50, offset=0)
    assert exc.value.status_code == 404


def test_get_driver_without_profile_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    me = _driver(db_session, store)

    with pytest.raises(HTTPException) as exc:
        get_driver_assignment(db_session, me, uuid.uuid4())
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# Non-blocking profile states still read (inactive / pending / rejected)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("status_value", "approval_value"),
    [
        ("inactive", "approved"),
        ("active", "pending"),
        ("active", "rejected"),
    ],
)
def test_non_blocking_profile_states_still_read(
    db_session: Session, make_store, status_value, approval_value
) -> None:
    store = make_store()
    me = _driver(db_session, store)
    profile = make_driver_profile(
        db_session,
        user=me,
        store=store,
        status=status_value,
        approval_status=approval_value,
    )
    order = make_order(db_session, store=store)
    mine = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    resp = list_driver_assignments(db_session, me, limit=50, offset=0)
    assert _ids(resp) == [mine.id]
    assert get_driver_assignment(db_session, me, mine.id).id == mine.id


# --------------------------------------------------------------------- #
# 14. No mutation
# --------------------------------------------------------------------- #


def test_reads_do_not_mutate(db_session: Session, make_store) -> None:
    store = make_store()
    me = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=me, store=store)
    order = make_order(db_session, store=store, status="pending")
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    order_status_before = order.status
    assignment_status_before = assignment.status
    assignment_updated_before = assignment.updated_at
    order_count_before = db_session.scalar(
        select(func.count()).select_from(Order)
    )
    assignment_count_before = db_session.scalar(
        select(func.count()).select_from(OrderDriverAssignment)
    )

    list_driver_assignments(db_session, me, limit=50, offset=0)
    get_driver_assignment(db_session, me, assignment.id)

    db_session.refresh(order)
    db_session.refresh(assignment)

    assert order.status == order_status_before
    assert assignment.status == assignment_status_before
    assert assignment.updated_at == assignment_updated_before
    assert (
        db_session.scalar(select(func.count()).select_from(Order))
        == order_count_before
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(OrderDriverAssignment)
        )
        == assignment_count_before
    )
