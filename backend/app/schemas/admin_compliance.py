"""Pydantic v2 schemas for the admin compliance surfaces (F2.20.2).

Wire contract for:

  - `GET /admin/compliance`              → AdminComplianceSummary
  - `GET /admin/compliance/products`     → AdminComplianceProductsListResponse

Design rules (locked by F2.20.0):

- Backend-computed only. No persisted incidents/tasks/queue rows —
  each section is derived from `Product` and
  `ProductComplianceAuditLog` at request time.

- `ProductRead` and `ProductComplianceAuditLogRead` are reused from
  `app.schemas.products` so the admin compliance surfaces never
  diverge from those canonical projections.

- Owned wrappers use `ConfigDict(extra="forbid")` to match the
  admin dashboard / operations / products envelope policy: a
  miswired service or a future field addition surfaces as a 500
  rather than a silent drop.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.schemas.products import ProductComplianceAuditLogRead
from app.schemas.products import ProductRead


# --------------------------------------------------------------------- #
# GET /admin/compliance
# --------------------------------------------------------------------- #


class AdminComplianceProductCounts(BaseModel):
    """Product population counts by compliance / sale state.

    Sources (F2.20.0 §7):

      - total                : every row in `products`.
      - allowed              : `compliance_status == allowed`.
      - restricted           : `compliance_status == restricted`.
      - banned               : `compliance_status == banned`.
      - blocked              : shared compliance blocker predicate
                               (F2.20.0 §8): allowed_for_sale = false
                               OR compliance_status IN
                               (restricted, banned).
      - allowed_for_sale     : `allowed_for_sale == true`.
      - not_allowed_for_sale : `allowed_for_sale == false`.
      - inactive             : `is_active == false`.

    These counts can overlap conceptually (a banned product is also
    not_allowed_for_sale and is included in blocked). Each field is
    an independent category count.
    """

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    allowed: int = Field(ge=0)
    restricted: int = Field(ge=0)
    banned: int = Field(ge=0)
    blocked: int = Field(ge=0)
    allowed_for_sale: int = Field(ge=0)
    not_allowed_for_sale: int = Field(ge=0)
    inactive: int = Field(ge=0)


class AdminComplianceReviewSummary(BaseModel):
    """Bounded recent tail of compliance review activity.

    `recent_count` is the size of the `recent` list returned by
    this call — NOT a lifetime count of audit rows. The list is
    capped at a service-owned bound (see
    `app.services.admin_compliance._RECENT_REVIEWS_LIMIT`) and
    ordered deterministically by `created_at DESC, id DESC` so
    consecutive calls return the same tail.
    """

    model_config = ConfigDict(extra="forbid")

    recent_count: int = Field(ge=0)
    recent: list[ProductComplianceAuditLogRead]


class AdminComplianceQueueCounts(BaseModel):
    """Compliance queue cardinalities (F2.20.0 §7).

    - total              : count of products matching the shared
                           compliance blocker predicate.
    - banned             : count of `compliance_status == banned`.
    - restricted         : count of `compliance_status == restricted`.
    - not_allowed_for_sale: count of `allowed_for_sale == false`.

    The component counts overlap: `total` is the union (via blocker
    predicate), while `banned`, `restricted`, and
    `not_allowed_for_sale` are independent category counts.
    """

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    banned: int = Field(ge=0)
    restricted: int = Field(ge=0)
    not_allowed_for_sale: int = Field(ge=0)


class AdminComplianceSummary(BaseModel):
    """Top-level response for `GET /admin/compliance`.

    Bundles product counts, the recent-reviews tail, and queue
    cardinalities. Read-only, admin-only, computed-on-request.
    """

    model_config = ConfigDict(extra="forbid")

    products: AdminComplianceProductCounts
    reviews: AdminComplianceReviewSummary
    queue: AdminComplianceQueueCounts


# --------------------------------------------------------------------- #
# GET /admin/compliance/products
# --------------------------------------------------------------------- #


class AdminComplianceProductsListResponse(BaseModel):
    """Paginated response envelope for the admin compliance queue.

    Same shape as `AdminProductsListResponse` so admin clients can
    reuse pagination controls. `total` is the count of matches
    BEFORE pagination is applied.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[ProductRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
