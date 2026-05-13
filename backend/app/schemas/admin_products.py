"""Pydantic v2 schemas for the admin products list (F2.20.1).

Wire contract for `GET /admin/products`: an admin-only, read-only,
paginated, filterable list of global products.

Design rules (locked by F2.20.0):

- The list envelope mirrors the pagination shape used by the other
  admin list endpoints (`items` / `total` / `limit` / `offset`). The
  service guarantees `total` is the match count BEFORE pagination,
  matching the F2.20.0 §6 rules.

- `ProductRead` is reused as-is from `app.schemas.products`. There is
  no admin-specific projection — admins read the same product row
  shape as the rest of the API.

- `extra="forbid"` on the wrapper matches the admin dashboard /
  operations envelope policy: a miswired service or a future field
  addition surfaces as a 500 rather than a silent drop.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.schemas.products import ProductRead


class AdminProductsListResponse(BaseModel):
    """Paginated response envelope for `GET /admin/products`.

    `total` is the count of products matching the filters BEFORE
    `limit`/`offset` are applied; `limit` and `offset` echo the
    request so callers can render pagination controls without
    re-deriving them.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[ProductRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
