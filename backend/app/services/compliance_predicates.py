"""Shared compliance-blocker predicate (F2.20.0 §8).

One source of truth for the question "is this product blocked from
sale?". Used by the F2.20 admin compliance service to count and
list blocked products without re-deriving the rule in each call
site.

Locked definition (F2.20.0 §8):

    Product.allowed_for_sale == false
    OR Product.compliance_status IN (restricted, banned)

The equivalent rule is also expressed inline by the F2.19 admin
dashboard (`_BLOCKING_COMPLIANCE_STATUSES` in
`app.services.admin_dashboard`) and the F2.19 admin operations
alerts feed (`_BLOCKING_COMPLIANCE_STATUSES` in
`app.services.admin_operations`). The F2.20.0 contract calls those
out as drift-risk siblings; this module is the new shared
definition for F2.20 code, and the predicate-consistency test in
`test_admin_compliance_service.py` pins it.

Refactoring F2.19 to also import from here is intentionally
deferred — F2.20.0 §13 sequences the subphases such that F2.20.2
implements only the admin compliance backend, and changing F2.19
services in this subphase would require regression coverage we are
saving for F2.20.7.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement
from sqlalchemy import or_

from app.db.models import ComplianceStatus
from app.db.models import Product


# Tuple, not set, so SQLAlchemy's `in_(...)` produces deterministic
# parameter ordering (sets have non-deterministic iteration order in
# CPython for enums in some cases, and tuples make the produced SQL
# stable across runs — useful when comparing query plans / logs).
BLOCKING_COMPLIANCE_STATUSES: tuple[ComplianceStatus, ...] = (
    ComplianceStatus.restricted,
    ComplianceStatus.banned,
)


def product_compliance_blocker_predicate() -> ColumnElement[bool]:
    """Return the SQLAlchemy boolean clause that identifies a
    compliance blocker.

    Use anywhere the F2.20 admin compliance code needs to filter
    or count products "blocked from sale". Always call the function
    fresh — SQLAlchemy boolean clauses are reusable but binding
    them once and reusing the same instance across `where(...)`
    calls is brittle if anyone ever mutates the clause in place.
    """
    return or_(
        Product.allowed_for_sale.is_(False),
        Product.compliance_status.in_(BLOCKING_COMPLIANCE_STATUSES),
    )
