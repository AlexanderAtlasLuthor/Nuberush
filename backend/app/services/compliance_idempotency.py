"""Strong compliance idempotency ledger helper (Dr.1.2.I.b).

Centralized claim / replay / completion for the
``driver_compliance_idempotency_keys`` ledger. The ledger lets a compliance
mutation be retried safely under an ``Idempotency-Key``: the first request
*claims* the key (a ``pending`` row), runs the business mutation, and *completes*
the claim — all in one transaction. A retry with the same key + same payload +
same scope *replays* the recorded outcome by reloading the canonical object
from ``response_ref_id`` (no response body is stored). A reused key with a
different payload or scope, or a key whose claim is still in progress, is a
409 conflict.

Boundaries (I.b — orders-side pilot only):

- This module owns key validation, request hashing, and the claim/complete
  state machine. It NEVER commits, rolls back, or flushes on the success
  path beyond the single ``flush`` needed to surface a UNIQUE race — the
  caller owns the transaction so the ledger row lands (or rolls back)
  atomically with the business mutation.
- It stores ONLY a sha256 ``request_hash`` digest and a ``response_ref_id``
  (a stable id the caller can reload from). It NEVER stores the raw request
  body, the response body, headers, tokens, or any sensitive field.
- The Idempotency-Key header is OPTIONAL. A missing key is handled by the
  caller (current state-inferred behavior); this module is only reached when
  a key is present.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DriverComplianceIdempotencyKey
from app.db.models import _COMPLIANCE_IDEMPOTENCY_ACTIONS


# --------------------------------------------------------------------- #
# Taxonomy / constants
# --------------------------------------------------------------------- #

#: Closed set of actions a compliance idempotency claim may carry. Mirrors the
#: model-level CHECK (and the operational-audit delivery taxonomy). I.b only
#: wires ``delivery_return_confirmed``; the rest are reserved for I.c.
COMPLIANCE_IDEMPOTENCY_ACTIONS: frozenset[str] = frozenset(
    _COMPLIANCE_IDEMPOTENCY_ACTIONS
)

STATE_PENDING = "pending"
STATE_COMPLETED = "completed"

#: Max accepted Idempotency-Key length (matches the varchar(255) column).
MAX_IDEMPOTENCY_KEY_LENGTH = 255


# --------------------------------------------------------------------- #
# Key validation
# --------------------------------------------------------------------- #


def validate_idempotency_key(raw: str) -> str:
    """Validate a caller-supplied Idempotency-Key, returning it unchanged.

    Conservative, format-agnostic rules (not UUID-only): the key must be a
    non-empty, non-whitespace-only, printable token of at most 255 chars with
    no control/whitespace characters. A ``None`` key is the caller's "no
    ledger" signal and must be handled before calling this — passing ``None``
    here is a programming error.

    Raises ``HTTPException(400)`` for an empty / whitespace-only / too-long /
    malformed key. The raw value is never logged or stored.
    """
    if raw is None:  # pragma: no cover - defensive; caller guards None
        raise ValueError("validate_idempotency_key requires a non-None key.")

    if raw.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key must not be empty or whitespace-only.",
        )
    if len(raw) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Idempotency-Key exceeds the maximum length of "
                f"{MAX_IDEMPOTENCY_KEY_LENGTH} characters."
            ),
        )
    # No control characters and no internal whitespace: a single opaque token.
    if any((ch.isspace() or not ch.isprintable()) for ch in raw):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key contains invalid characters.",
        )
    return raw


# --------------------------------------------------------------------- #
# Request hashing
# --------------------------------------------------------------------- #


def compute_compliance_request_hash(
    action: str, payload: BaseModel | dict[str, Any]
) -> str:
    """Compute a stable sha256 hex digest over ``action`` + validated body.

    The body is taken AFTER Pydantic validation and serialized canonically
    (sorted keys, compact separators, JSON-mode coercion for UUID/datetime so
    re-ordering or equivalent representations hash identically). ``None`` fields
    are included consistently. Only the 64-char digest is ever persisted — the
    raw body is never stored.
    """
    if isinstance(payload, BaseModel):
        body: Any = payload.model_dump(mode="json")
    else:
        body = payload
    canonical = {"action": action, "body": body}
    blob = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- #
# Claim / replay
# --------------------------------------------------------------------- #


@dataclass
class ClaimResult:
    """Outcome of :func:`claim_or_replay`.

    ``replayed`` is ``True`` when an existing completed claim matched (the
    caller must reload from ``claim.response_ref_id`` instead of re-running the
    business mutation). ``replayed`` is ``False`` when a fresh ``pending`` claim
    was inserted (the caller must execute the mutation and then call
    :func:`complete_claim`). ``claim`` is the ledger row in both cases.
    """

    replayed: bool
    claim: DriverComplianceIdempotencyKey


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _scope_matches(
    claim: DriverComplianceIdempotencyKey,
    *,
    action: str,
    actor_user_id: UUID | None,
    order_id: UUID | None,
    assignment_id: UUID | None,
) -> bool:
    return (
        claim.action == action
        and claim.actor_user_id == actor_user_id
        and claim.order_id == order_id
        and claim.assignment_id == assignment_id
    )


def claim_or_replay(
    db: Session,
    *,
    idempotency_key: str,
    action: str,
    actor_user_id: UUID | None,
    store_id: UUID,
    order_id: UUID | None,
    assignment_id: UUID | None,
    request_hash: str,
    expires_at: Any | None = None,
) -> ClaimResult:
    """Claim ``idempotency_key`` for ``action`` or detect a replay/conflict.

    Looks up the existing claim for ``(store_id, action, idempotency_key)`` and:

    - **completed + same hash + same scope** → returns a replay result
      (caller reloads from ``response_ref_id``);
    - **completed + different request_hash** → 409 (same key, different body);
    - **completed + different actor/order/assignment** → 409 (different scope);
    - **pending** → 409 (a request with this key is already in progress);
    - **absent** → inserts a fresh ``pending`` row and returns a claim result.

    The insert is ``flush``ed so a concurrent inserter's UNIQUE violation is
    surfaced here and resolved (replay or 409) rather than corrupting the
    business commit. ``action`` must be in the closed taxonomy (programming
    error otherwise).
    """
    if action not in COMPLIANCE_IDEMPOTENCY_ACTIONS:
        raise ValueError(
            f"Unknown compliance idempotency action: {action!r}."
        )

    existing = db.scalar(
        select(DriverComplianceIdempotencyKey)
        .where(
            DriverComplianceIdempotencyKey.store_id == store_id,
            DriverComplianceIdempotencyKey.action == action,
            DriverComplianceIdempotencyKey.idempotency_key
            == idempotency_key,
        )
        .with_for_update()
    )
    if existing is not None:
        return _resolve_existing(
            existing,
            action=action,
            actor_user_id=actor_user_id,
            order_id=order_id,
            assignment_id=assignment_id,
            request_hash=request_hash,
        )

    claim = DriverComplianceIdempotencyKey(
        idempotency_key=idempotency_key,
        action=action,
        actor_user_id=actor_user_id,
        store_id=store_id,
        order_id=order_id,
        assignment_id=assignment_id,
        request_hash=request_hash,
        state=STATE_PENDING,
        expires_at=expires_at,
    )
    db.add(claim)
    try:
        db.flush()
    except IntegrityError as exc:
        # A concurrent request claimed the same (store, action, key) between
        # our SELECT and INSERT. Roll back, re-read, and resolve as a
        # replay/conflict against the now-visible row.
        db.rollback()
        message = str(exc.orig).lower() if exc.orig is not None else ""
        if (
            "uq_driver_compliance_idempotency_keys_scope" not in message
        ):  # pragma: no cover - unexpected constraint
            raise
        winner = db.scalar(
            select(DriverComplianceIdempotencyKey).where(
                DriverComplianceIdempotencyKey.store_id == store_id,
                DriverComplianceIdempotencyKey.action == action,
                DriverComplianceIdempotencyKey.idempotency_key
                == idempotency_key,
            )
        )
        if winner is None:  # pragma: no cover - racing rollback edge
            raise _conflict(
                "A request with this Idempotency-Key is already in progress."
            ) from exc
        return _resolve_existing(
            winner,
            action=action,
            actor_user_id=actor_user_id,
            order_id=order_id,
            assignment_id=assignment_id,
            request_hash=request_hash,
        )
    return ClaimResult(replayed=False, claim=claim)


def _resolve_existing(
    existing: DriverComplianceIdempotencyKey,
    *,
    action: str,
    actor_user_id: UUID | None,
    order_id: UUID | None,
    assignment_id: UUID | None,
    request_hash: str,
) -> ClaimResult:
    """Map an existing ledger row to a replay result or a 409 conflict."""
    if existing.state == STATE_PENDING:
        raise _conflict(
            "A request with this Idempotency-Key is already in progress."
        )
    # state == completed
    if existing.request_hash != request_hash:
        raise _conflict(
            "Idempotency-Key was already used with a different request "
            "payload."
        )
    if not _scope_matches(
        existing,
        action=action,
        actor_user_id=actor_user_id,
        order_id=order_id,
        assignment_id=assignment_id,
    ):
        raise _conflict(
            "Idempotency-Key was already used for a different request scope."
        )
    return ClaimResult(replayed=True, claim=existing)


# --------------------------------------------------------------------- #
# Completion
# --------------------------------------------------------------------- #


def complete_claim(
    db: Session,
    *,
    claim: DriverComplianceIdempotencyKey,
    response_ref_id: UUID,
    response_status_code: int = 200,
    completed_at: Any,
) -> DriverComplianceIdempotencyKey:
    """Mark a ``pending`` claim ``completed`` (no commit).

    Stamps ``state='completed'`` with the stable ``response_ref_id`` the caller
    can later reload from, the ``response_status_code`` (default 200), and
    ``completed_at``. Never commits/rolls back — the caller commits this in the
    SAME transaction as the business mutation, so the claim and its effect are
    atomic. No response body is stored.
    """
    claim.state = STATE_COMPLETED
    claim.response_ref_id = response_ref_id
    claim.response_status_code = response_status_code
    claim.completed_at = completed_at
    db.add(claim)
    return claim
