"""Writer helper for the operational audit trail (F2.26.1.B).

This module is the ONLY sanctioned way to append a row to
`operational_audit_logs`. It owns the closed event taxonomy, the
before/after allow-lists, and the sensitive-key redaction that keep the
audit trail honest and safe.

Boundaries (F2.26.1.B scope — writer only):

- This helper does `db.add(log)` and nothing else. It NEVER commits,
  rolls back, or flushes — the caller owns the transaction so the audit
  row lands (or rolls back) atomically with the business mutation it
  records. That integration is F2.26.1.C/D, not here.
- It does NOT read or touch the unified audit feed
  (`app.services.audit`), its schemas, users/stores services, routes,
  compliance, or notifications.
- No `AuditSource` / `AuditEntityType` enum is referenced; the unified
  feed integration (F2.26.2) maps these rows later.

Taxonomy (closed): `target_type` is one of {user, store}; each target
type admits a fixed action set. An unknown target type, an unknown
action, or an action that does not belong to the given target type is a
programming error and raises `ValueError`.

Safety: `before`/`after` are filtered to a per-target allow-list of
non-sensitive columns; `metadata` is free-form but deep-stripped of any
key whose name matches a sensitive term. Nested dicts/lists are scrubbed
too, and UUIDs are coerced to strings so the JSONB payload is always
JSON-safe. Raw payloads are never stored wholesale.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import OperationalAuditLog


# --------------------------------------------------------------------- #
# Closed taxonomy
# --------------------------------------------------------------------- #

TARGET_USER = "user"
TARGET_STORE = "store"
# Dr.1.2.I.a — driver delivery compliance trail. A delivery_assignment row
# records a compliance action against an OrderDriverAssignment (the target_id);
# `action` stays a varchar (no migration), so the taxonomy below is the only
# source of truth for what is permitted.
TARGET_DELIVERY_ASSIGNMENT = "delivery_assignment"

# Action sets per target type. Adding an action means extending the set
# here (and, for the model, nothing — `action` is a varchar). The union
# is used to distinguish "unknown action" from "action/target mismatch".
_ACTIONS_BY_TARGET: dict[str, frozenset[str]] = {
    TARGET_USER: frozenset(
        {
            "user_created",
            "user_updated",
            "user_role_changed",
            "user_store_assigned",
            "user_store_removed",
            "user_activated",
            "user_deactivated",
        }
    ),
    TARGET_STORE: frozenset(
        {
            "store_created",
            "store_updated",
            "store_activated",
            "store_deactivated",
        }
    ),
    TARGET_DELIVERY_ASSIGNMENT: frozenset(
        {
            "delivery_verified",
            "delivery_proof_recorded",
            "delivery_completed",
            "delivery_failed",
            "delivery_return_started",
            "delivery_return_arrived",
            "delivery_return_confirmed",
        }
    ),
}

_ALL_ACTIONS: frozenset[str] = frozenset().union(
    *_ACTIONS_BY_TARGET.values()
)


# --------------------------------------------------------------------- #
# before/after allow-lists (per target type)
# --------------------------------------------------------------------- #
#
# Only these columns may be captured in before/after. The lists are a
# safe subset of the REAL model columns (verified against
# app.db.models.User / Store): `email` and `auth_user_id` are
# intentionally excluded (PII / identity-bridge), and store fields that
# do not exist on the model are not invented.

_ALLOWED_FIELDS_BY_TARGET: dict[str, frozenset[str]] = {
    # User real columns: id, store_id, full_name, email, auth_user_id,
    # phone, role, is_active, created_at, updated_at. Audited subset:
    TARGET_USER: frozenset(
        {"role", "store_id", "is_active", "full_name", "phone"}
    ),
    # Store real columns: id, name, code, is_active, timezone,
    # created_at, updated_at. Audited subset (no slug/status/address/
    # phone — those columns do not exist on the model):
    TARGET_STORE: frozenset({"name", "code", "is_active", "timezone"}),
    # Dr.1.2.I.a — only non-PII lifecycle discriminators of the delivery
    # compliance flow: the operational-state value, the assignment status,
    # the return custody state, the failure reason code, and the
    # verification outcome. NEVER raw ID / proof / photo / location / PII.
    TARGET_DELIVERY_ASSIGNMENT: frozenset(
        {"status", "state", "return_state", "reason_code", "outcome"}
    ),
}


# --------------------------------------------------------------------- #
# Sensitive-key redaction
# --------------------------------------------------------------------- #
#
# A key is redacted (dropped) if its lowercased name contains ANY of
# these terms. Substring matching is deliberate so `access_token`,
# `x-refresh-token`, `Authorization`, `supabase_url`, etc. are all
# caught. Applied recursively to nested dicts and lists.

_SENSITIVE_TERMS: tuple[str, ...] = (
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "auth_token",
    "secret",
    "api_key",
    "jwt",
    "authorization",
    "supabase",
    "email_verification_token",
    "reset_token",
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(term in lowered for term in _SENSITIVE_TERMS)


def _json_safe(value: Any) -> Any:
    """Coerce a value into a JSON-safe form, recursively dropping any
    sensitive keys from nested dicts and scrubbing nested lists.

    UUIDs become strings (matching the repo's `str(value)` convention in
    `app.services.audit._coerce_uuid_str`). Scalars pass through.
    """
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return _scrub_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _scrub_mapping(data: dict[Any, Any]) -> dict[str, Any]:
    """Drop sensitive keys (recursively) and JSON-normalize the rest."""
    cleaned: dict[str, Any] = {}
    for raw_key, raw_value in data.items():
        key = str(raw_key)
        if _is_sensitive_key(key):
            continue
        cleaned[key] = _json_safe(raw_value)
    return cleaned


def _filter_allow_list(
    data: dict[str, Any] | None, target_type: str
) -> dict[str, Any] | None:
    """Keep only allow-listed columns for `before`/`after`, then scrub.

    Returns None for a None input. A dict that has no allow-listed keys
    collapses to `{}` — the row still records that a snapshot was
    provided without leaking anything outside the allow-list.
    """
    if data is None:
        return None
    allowed = _ALLOWED_FIELDS_BY_TARGET[target_type]
    kept = {
        key: value
        for key, value in data.items()
        if key in allowed and not _is_sensitive_key(key)
    }
    # Defensive: scrub the kept values too, in case an allowed field ever
    # carries a nested structure with a sensitive key.
    return _scrub_mapping(kept)


def _sanitize_metadata(
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Scrub free-form metadata: drop sensitive keys (recursively),
    JSON-normalize the rest. No allow-list — metadata is operator
    context (e.g. `reason`, `source`) — but never raw payloads, headers,
    tokens, or secrets."""
    if metadata is None:
        return None
    return _scrub_mapping(metadata)


def _coerce_id(value: UUID | str | None) -> UUID | None:
    """Normalize an id input (UUID or string) to a UUID, or None."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


# --------------------------------------------------------------------- #
# Public writer
# --------------------------------------------------------------------- #


def write_operational_audit_log(
    db: Session,
    *,
    actor_user_id: UUID | str | None,
    target_type: str,
    target_id: UUID | str,
    action: str,
    store_id: UUID | str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> OperationalAuditLog:
    """Append one operational audit row to the session (no commit).

    Validates the closed taxonomy, filters `before`/`after` to the
    per-target allow-list, redacts sensitive keys from every payload,
    builds an `OperationalAuditLog`, and `db.add()`s it. Returns the
    (unflushed) object so a caller can inspect it if needed.

    Raises `ValueError` for taxonomy violations (unknown target_type,
    unknown action, or action that does not belong to the target_type)
    and for a missing `target_id`. These are programming errors at the
    (future) call sites, not user input.

    The caller owns the transaction. This helper never commits, rolls
    back, or flushes.
    """
    if target_type not in _ACTIONS_BY_TARGET:
        raise ValueError(
            f"Unknown operational audit target_type: {target_type!r}. "
            f"Expected one of {sorted(_ACTIONS_BY_TARGET)}."
        )
    if action not in _ALL_ACTIONS:
        raise ValueError(
            f"Unknown operational audit action: {action!r}."
        )
    if action not in _ACTIONS_BY_TARGET[target_type]:
        raise ValueError(
            f"Action {action!r} does not belong to target_type "
            f"{target_type!r}. Allowed: "
            f"{sorted(_ACTIONS_BY_TARGET[target_type])}."
        )

    resolved_target_id = _coerce_id(target_id)
    if resolved_target_id is None:
        raise ValueError("target_id is required.")

    log = OperationalAuditLog(
        actor_user_id=_coerce_id(actor_user_id),
        target_type=target_type,
        target_id=resolved_target_id,
        action=action,
        store_id=_coerce_id(store_id),
        before=_filter_allow_list(before, target_type),
        after=_filter_allow_list(after, target_type),
        # Column is "metadata"; the model attribute is `event_metadata`.
        event_metadata=_sanitize_metadata(metadata),
    )
    db.add(log)
    return log
