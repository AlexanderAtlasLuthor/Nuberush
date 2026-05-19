"""Schema-only tests for the users module (F2.15.1).

No DB. Exercises:
  - UserUpdateRequest field-by-field rules (trim, length, optional,
    `extra="forbid"`, prohibited privileged fields).
  - UserRoleChangeRequest accepts every UserRole and rejects unknown.
  - UserStoreAssignmentRequest accepts UUID + null.
  - UserListResponse envelope serialization + pagination bounds.

Style mirrors tests/test_stores_schemas.py and test_inventory_schemas.py:
SimpleNamespace for ORM round-trips, pytest.raises(ValidationError) for
negative cases.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import UserRole
from app.schemas.users import UserListResponse
from app.schemas.users import UserRoleChangeRequest
from app.schemas.users import UserStoreAssignmentRequest
from app.schemas.users import UserUpdateRequest


# --------------------------------------------------------------------- #
# UserUpdateRequest — full_name
# --------------------------------------------------------------------- #


def test_user_update_accepts_full_name():
    payload = UserUpdateRequest.model_validate({"full_name": "Jane Doe"})
    assert payload.full_name == "Jane Doe"
    assert payload.phone is None


def test_user_update_trims_full_name():
    payload = UserUpdateRequest.model_validate({"full_name": "  Jane Doe  "})
    assert payload.full_name == "Jane Doe"


def test_user_update_rejects_empty_full_name():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"full_name": ""})


def test_user_update_rejects_whitespace_full_name():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"full_name": "   "})


def test_user_update_rejects_full_name_over_150():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"full_name": "x" * 151})


def test_user_update_accepts_full_name_at_150():
    payload = UserUpdateRequest.model_validate({"full_name": "x" * 150})
    assert payload.full_name == "x" * 150


# --------------------------------------------------------------------- #
# UserUpdateRequest — phone
# --------------------------------------------------------------------- #


def test_user_update_accepts_phone():
    payload = UserUpdateRequest.model_validate({"phone": "+1-555-0100"})
    assert payload.phone == "+1-555-0100"


def test_user_update_trims_phone():
    payload = UserUpdateRequest.model_validate({"phone": "  +1-555-0100  "})
    assert payload.phone == "+1-555-0100"


def test_user_update_accepts_phone_null():
    payload = UserUpdateRequest.model_validate({"phone": None})
    assert payload.phone is None


def test_user_update_phone_empty_string_becomes_null():
    payload = UserUpdateRequest.model_validate({"phone": ""})
    assert payload.phone is None


def test_user_update_phone_whitespace_only_becomes_null():
    payload = UserUpdateRequest.model_validate({"phone": "   "})
    assert payload.phone is None


def test_user_update_rejects_phone_over_30():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"phone": "1" * 31})


def test_user_update_accepts_phone_at_30():
    payload = UserUpdateRequest.model_validate({"phone": "1" * 30})
    assert payload.phone == "1" * 30


# --------------------------------------------------------------------- #
# UserUpdateRequest — partial / empty payload
# --------------------------------------------------------------------- #


def test_user_update_accepts_empty_payload():
    payload = UserUpdateRequest.model_validate({})
    assert payload.full_name is None
    assert payload.phone is None
    assert payload.model_dump(exclude_unset=True) == {}


def test_user_update_accepts_partial_full_name_only():
    payload = UserUpdateRequest.model_validate({"full_name": "Solo"})
    assert payload.model_dump(exclude_unset=True) == {"full_name": "Solo"}


def test_user_update_accepts_partial_phone_only():
    payload = UserUpdateRequest.model_validate({"phone": "+1-555-0100"})
    assert payload.model_dump(exclude_unset=True) == {"phone": "+1-555-0100"}


# --------------------------------------------------------------------- #
# UserUpdateRequest — extra fields are forbidden
# --------------------------------------------------------------------- #


def test_user_update_rejects_unknown_extra_field():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"nickname": "Janie"})


def test_user_update_rejects_id():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"id": str(uuid4())})


def test_user_update_rejects_email():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"email": "x@example.com"})


def test_user_update_rejects_role():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"role": "owner"})


def test_user_update_rejects_store_id():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"store_id": str(uuid4())})


def test_user_update_rejects_is_active():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"is_active": False})


def test_user_update_rejects_password_hash():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate({"password_hash": "x" * 60})


def test_user_update_rejects_created_at():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate(
            {"created_at": "2026-01-01T00:00:00Z"}
        )


def test_user_update_rejects_updated_at():
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate(
            {"updated_at": "2026-01-01T00:00:00Z"}
        )


# --------------------------------------------------------------------- #
# UserRoleChangeRequest
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role",
    ["admin", "owner", "manager", "staff", "driver"],
)
def test_user_role_change_accepts_each_known_role(role: str):
    payload = UserRoleChangeRequest.model_validate({"role": role})
    assert payload.role == UserRole(role)


def test_user_role_change_rejects_invalid_role():
    with pytest.raises(ValidationError):
        UserRoleChangeRequest.model_validate({"role": "superuser"})


def test_user_role_change_rejects_empty_role():
    with pytest.raises(ValidationError):
        UserRoleChangeRequest.model_validate({"role": ""})


def test_user_role_change_rejects_extra_fields():
    with pytest.raises(ValidationError):
        UserRoleChangeRequest.model_validate(
            {"role": "owner", "store_id": str(uuid4())}
        )


def test_user_role_change_requires_role():
    with pytest.raises(ValidationError):
        UserRoleChangeRequest.model_validate({})


# --------------------------------------------------------------------- #
# UserStoreAssignmentRequest
# --------------------------------------------------------------------- #


def test_user_store_assignment_accepts_uuid():
    store_id = uuid4()
    payload = UserStoreAssignmentRequest.model_validate(
        {"store_id": str(store_id)}
    )
    assert payload.store_id == store_id


def test_user_store_assignment_accepts_null():
    payload = UserStoreAssignmentRequest.model_validate({"store_id": None})
    assert payload.store_id is None


def test_user_store_assignment_rejects_non_uuid_string():
    with pytest.raises(ValidationError):
        UserStoreAssignmentRequest.model_validate({"store_id": "not-a-uuid"})


def test_user_store_assignment_rejects_extra_fields():
    with pytest.raises(ValidationError):
        UserStoreAssignmentRequest.model_validate(
            {"store_id": str(uuid4()), "role": "owner"}
        )


# --------------------------------------------------------------------- #
# UserListResponse
# --------------------------------------------------------------------- #


def _orm_like_user():
    return SimpleNamespace(
        id=uuid4(),
        full_name="Jane Doe",
        email="jane@example.com",
        role=UserRole.owner,
        store_id=uuid4(),
        is_active=True,
    )


def test_user_list_response_serializes_envelope():
    user = _orm_like_user()
    response = UserListResponse.model_validate(
        {
            "items": [user],
            "total": 1,
            "limit": 25,
            "offset": 0,
        }
    )
    assert len(response.items) == 1
    assert response.items[0].id == user.id
    assert response.items[0].full_name == "Jane Doe"
    assert response.items[0].email == "jane@example.com"
    assert response.items[0].role == UserRole.owner
    assert response.total == 1
    assert response.limit == 25
    assert response.offset == 0


def test_user_list_response_accepts_empty_items():
    response = UserListResponse.model_validate(
        {"items": [], "total": 0, "limit": 25, "offset": 0}
    )
    assert response.items == []
    assert response.total == 0


def test_user_list_response_rejects_negative_total():
    with pytest.raises(ValidationError):
        UserListResponse.model_validate(
            {"items": [], "total": -1, "limit": 25, "offset": 0}
        )


def test_user_list_response_rejects_zero_limit():
    with pytest.raises(ValidationError):
        UserListResponse.model_validate(
            {"items": [], "total": 0, "limit": 0, "offset": 0}
        )


def test_user_list_response_rejects_negative_limit():
    with pytest.raises(ValidationError):
        UserListResponse.model_validate(
            {"items": [], "total": 0, "limit": -5, "offset": 0}
        )


def test_user_list_response_rejects_negative_offset():
    with pytest.raises(ValidationError):
        UserListResponse.model_validate(
            {"items": [], "total": 0, "limit": 25, "offset": -1}
        )


def test_user_list_response_accepts_zero_offset():
    response = UserListResponse.model_validate(
        {"items": [], "total": 0, "limit": 1, "offset": 0}
    )
    assert response.offset == 0
