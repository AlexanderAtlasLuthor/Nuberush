"""Pydantic v2 schemas for the users module (F2.15.1).

Contracts for the Users Management surface: a paginated list response
and four mutation request shapes used by admin/owner flows.

Design rules baked in:

- `UserListResponse` is the canonical paginated envelope. It reuses
  `UserRead` from `app.schemas.auth` so the user shape stays in one
  place (single source of truth for what a user looks like on the
  wire).

- All mutation requests set `extra="forbid"`. Callers cannot smuggle
  privileged fields (`id`, `email`, `role`, `store_id`, `is_active`,
  `created_at`, `updated_at`) through the generic profile-update
  endpoint. Role and store-assignment changes
  go through their own dedicated request schemas with their own
  authorization rules in the service layer (F2.15.2).

- Editable string fields are trimmed and length-bounded to mirror the
  `users` DB columns, so a request that would later fail at the
  CHECK / VARCHAR layer surfaces as a clean 422.

- `phone` accepts `null` and treats empty / whitespace-only strings as
  `null`. The DB column is nullable and form payloads commonly submit
  empty strings to clear a value; collapsing them to `null` keeps
  service-layer logic simple ("set what you mean").

- This module deliberately does NOT enforce the cross-field rule that
  admin users have `store_id IS NULL` and non-admin users have a
  `store_id`. That belongs in the service layer (F2.15.2) where the
  caller's role and the target user's existing role are both in
  scope.
"""

from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from app.db.models import UserRole
from app.schemas.auth import UserRead


# --------------------------------------------------------------------- #
# List response
# --------------------------------------------------------------------- #


class UserListResponse(BaseModel):
    """Paginated response for GET /users."""

    items: list[UserRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


# --------------------------------------------------------------------- #
# Profile update
# --------------------------------------------------------------------- #


class UserUpdateRequest(BaseModel):
    """Partial profile update.

    Only `full_name` and `phone` are editable here. Every other column
    on `users` is rejected with 422 thanks to `extra="forbid"`. Length
    bounds mirror the DB VARCHAR limits.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("full_name")
    @classmethod
    def _strip_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("full_name must not be empty when provided")
        return stripped

    @field_validator("phone")
    @classmethod
    def _strip_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


# --------------------------------------------------------------------- #
# Role change
# --------------------------------------------------------------------- #


class UserRoleChangeRequest(BaseModel):
    """Body for the role-change endpoint.

    The validity of a role transition (who may promote/demote whom,
    and whether the target's `store_id` must change as a side effect)
    is enforced in the service layer (F2.15.2), not here.
    """

    model_config = ConfigDict(extra="forbid")

    role: UserRole


# --------------------------------------------------------------------- #
# Store assignment
# --------------------------------------------------------------------- #


class UserStoreAssignmentRequest(BaseModel):
    """Body for the store-assignment endpoint.

    `null` is accepted because admin users have no store. The service
    layer owns the rule that admin must have `store_id IS NULL` and
    non-admin must reference a real, existing store.
    """

    model_config = ConfigDict(extra="forbid")

    store_id: UUID | None = None
