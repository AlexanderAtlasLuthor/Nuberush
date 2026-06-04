"""Service layer for merchant/store applications (F2.24.C2).

C2 owns the PUBLIC intake path only: an unauthenticated applicant submits
business + owner details and an inert `StoreApplication` is created in
`pending_review`. This module deliberately does NOT create a store, a
public user, a Supabase Auth record, owner/admin access, or send a real
email — all of that belongs to the future admin-approval and email
subphases.

Conventions (consistent with `app.services.stores` /
`app.services.users`):

- Each function takes a Session as its first argument and owns its own
  commit. The dedup conflict is raised as a clean 409 before any write.
- RBAC is not enforced here because the only caller is the public,
  unauthenticated route. The route applies NO auth dependency; this
  service must never grant or assume any privilege.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Literal
from uuid import UUID
from uuid import uuid4

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_app_settings
from app.core.config import get_email_settings
from app.db.models import Store
from app.db.models import StoreApplication
from app.db.models import StoreApplicationAuditLog
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.models import UserRole
from app.schemas.store_applications import StoreApplicationCreateInternal
from app.schemas.store_applications import StoreApplicationListItem
from app.schemas.store_applications import StoreApplicationListResponse
from app.schemas.store_applications import StoreApplicationRejectRequest
from app.schemas.store_applications import StoreApplicationSubmitRequest
from app.services import email_templates
from app.services import supabase_admin
from app.services.email_sender import BusinessEmailEvent
from app.services.email_sender import BusinessEmailMessage
from app.services.email_sender import EmailSenderError
from app.services.email_sender import send_business_email
from app.services.supabase_admin import SupabaseAdminError


logger = logging.getLogger(__name__)


# A normalized owner_email that already has an application in any of these
# statuses blocks a new submission (409). Only a previously `rejected`
# application lets the same email apply again — the applicant has been
# turned away and may legitimately re-apply.
_ACTIVE_DEDUP_STATUSES: tuple[StoreApplicationStatus, ...] = (
    StoreApplicationStatus.draft,
    StoreApplicationStatus.submitted,
    StoreApplicationStatus.pending_review,
    StoreApplicationStatus.approved,
)


def _duplicate_conflict() -> HTTPException:
    """The single 409 used by both the dedup pre-check and the race handler."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="An application for this email is already in progress.",
    )


def _write_email_triggered_audit(
    db: Session,
    *,
    application_id: UUID,
    event: BusinessEmailEvent,
    status: Literal["sent", "failed"],
    provider: str,
    recipient: str,
    error_type: str | None = None,
) -> None:
    """Persist one `email_triggered` audit row (F2.25.3).

    Post-commit, isolated, non-blocking: this owns its own transaction on
    the already-clean session and is called only AFTER the business
    transaction has committed. The payload is deliberately secret- and
    body-free — it records the business event, the configured provider, the
    sent/failed outcome and (on failure) the exception CLASS name only. It
    never carries the message body, subject, exception message, provider
    response, Authorization header, or RESEND_API_KEY.

    Any failure writing the audit is rolled back, logged (secret-free) and
    SWALLOWED — a committed submit/approve/reject must never become a 5xx
    because its audit row could not be written.
    """
    payload: dict[str, object | None] = {
        "event": event,
        "provider": provider,
        "status": status,
        "provider_message_id": None,
        "source": "business_email",
        "recipient": recipient,
    }
    if status == "failed" and error_type is not None:
        payload["error_type"] = error_type

    try:
        audit = StoreApplicationAuditLog(
            application_id=application_id,
            event_type="email_triggered",
            actor_user_id=None,  # system-triggered side-effect, not a user action
            message=(
                f"Business email '{event}' send attempt recorded: {status}."
            ),
            payload=payload,
        )
        db.add(audit)
        db.commit()
    except Exception:  # noqa: BLE001 — audit must never undo the business commit
        db.rollback()
        logger.exception(
            "Failed to write email_triggered audit for application %s "
            "(event=%s, status=%s); the business change was committed and "
            "is unaffected.",
            application_id,
            event,
            status,
        )


def _send_business_email_and_audit(
    db: Session,
    *,
    application_id: UUID,
    message: BusinessEmailMessage,
) -> None:
    """Send a business email post-commit, then record an audit row.

    Called only AFTER the business transaction has committed and the row
    refreshed. The send failure is logged and SWALLOWED (a committed
    submit/approve/reject must still return its success response), and the
    outcome — sent or failed — is recorded via `_write_email_triggered_audit`
    in its own isolated, non-blocking transaction.

    `application_id` and the recipient are captured as primitives before any
    audit commit so the audit write does not depend on the (now re-expirable)
    ORM application instance.
    """
    event = message.event_type
    recipient = message.to_email
    provider = get_email_settings().email_provider

    status: Literal["sent", "failed"] = "sent"
    error_type: str | None = None

    try:
        send_business_email(message)
    except EmailSenderError:
        status = "failed"
        error_type = "EmailSenderError"
        logger.exception(
            "Sender failed for %s email; the business change was committed "
            "and is unaffected.",
            event,
        )
    except Exception as exc:  # noqa: BLE001 — any failure must not undo commit
        status = "failed"
        error_type = type(exc).__name__
        logger.exception(
            "Unexpected failure sending %s email; the business change was "
            "committed and is unaffected.",
            event,
        )

    # Outer guard in addition to the helper's own swallow: even a catastrophic
    # failure of the audit path (or a replaced helper) must never turn a
    # committed submit/approve/reject into a 5xx.
    try:
        _write_email_triggered_audit(
            db,
            application_id=application_id,
            event=event,
            status=status,
            provider=provider,
            recipient=recipient,
            error_type=error_type,
        )
    except Exception:  # noqa: BLE001 — audit must never undo the business commit
        logger.exception(
            "email_triggered audit path failed for application %s (event=%s); "
            "the business change was committed and is unaffected.",
            application_id,
            event,
        )


def _notify_application_submitted(
    db: Session, application: StoreApplication
) -> None:
    """Send the `store_application_submitted` email + audit (F2.25.3)."""
    _send_business_email_and_audit(
        db,
        application_id=application.id,
        message=email_templates.build_submitted_email(application),
    )


def create_store_application(
    db: Session,
    *,
    payload: StoreApplicationSubmitRequest,
) -> StoreApplication:
    """Create an inert, pending-review store application from a public submit.

    Normalizes the payload, enforces the conservative dedup rule, writes
    the `StoreApplication` row plus an `application_created` audit log, and
    fires the (no-op) email seam. Returns the persisted application; the
    route maps it to the minimal public response DTO.
    """
    # Re-run the server-side normalization seam from C1 (idempotent — the
    # request schema already lowercased the email / trimmed strings).
    internal = StoreApplicationCreateInternal.model_validate(
        payload.model_dump()
    )

    # Conservative dedup, fast path: block a second active/pending/approved
    # application for the same normalized owner_email with a clean 409. A
    # prior `rejected` row does not block re-application. This pre-check is
    # not race-safe on its own (two concurrent public submissions can both
    # pass it), so the DB-level partial unique index
    # `uq_store_applications_active_owner_email` is the authoritative guard;
    # the IntegrityError handler below translates a lost race to the same
    # 409.
    existing = db.scalar(
        select(StoreApplication.id).where(
            StoreApplication.owner_email == internal.owner_email,
            StoreApplication.status.in_(_ACTIVE_DEDUP_STATUSES),
        )
    )
    if existing is not None:
        raise _duplicate_conflict()

    now = datetime.now(UTC)
    application = StoreApplication(
        **internal.model_dump(),
        status=StoreApplicationStatus.pending_review,
        submitted_at=now,
        terms_accepted_at=now,
    )
    # Terms acceptance is gated at the request layer (422 if not true); set
    # the server-side flag + timestamp authoritatively here regardless of
    # the inbound value so the row is internally consistent.
    application.terms_accepted = True
    db.add(application)

    try:
        # flush() assigns application.id and surfaces the partial-unique
        # collision (the lost-race duplicate) before we build the audit row.
        db.flush()
        audit = StoreApplicationAuditLog(
            application_id=application.id,
            event_type="application_created",
            actor_user_id=None,  # public, unauthenticated submission
            message="Public store application submitted for review.",
            payload={"source": "public_intake"},
        )
        db.add(audit)
        db.commit()
    except IntegrityError:
        # A concurrent submission for the same owner_email committed first
        # and the partial unique index rejected this one. Roll back and
        # return the same clean 409 as the fast-path pre-check — never a
        # raw 500, and the audit row is never persisted.
        db.rollback()
        raise _duplicate_conflict()

    db.refresh(application)

    _notify_application_submitted(db, application)

    return application


# --------------------------------------------------------------------- #
# Admin review surface (F2.24.C3)
# --------------------------------------------------------------------- #


def _assert_admin(actor: User) -> None:
    """Defense-in-depth admin gate (the route also applies require_admin)."""
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _notify_application_rejected(
    db: Session, application: StoreApplication
) -> None:
    """Send the `store_application_rejected` email + audit (F2.25.3)."""
    _send_business_email_and_audit(
        db,
        application_id=application.id,
        message=email_templates.build_rejected_email(application),
    )


def list_store_applications(
    db: Session,
    *,
    status_filter: StoreApplicationStatus | None = None,
    q: str | None = None,
    limit: int,
    offset: int,
) -> StoreApplicationListResponse:
    """Admin-only paginated list of store applications.

    Optional `status_filter` narrows to one lifecycle state; optional `q`
    does a case-insensitive match across business name, owner name and
    owner email. Newest first. `total` is the pre-pagination count.
    """
    conditions = []
    if status_filter is not None:
        conditions.append(StoreApplication.status == status_filter)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conditions.append(
            or_(
                StoreApplication.business_name.ilike(like),
                StoreApplication.owner_full_name.ilike(like),
                StoreApplication.owner_email.ilike(like),
            )
        )

    count_stmt = select(func.count()).select_from(StoreApplication)
    rows_stmt = select(StoreApplication)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        rows_stmt = rows_stmt.where(*conditions)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        # id.desc() is a deterministic tiebreaker so pagination is stable
        # when created_at values collide (matches the orders.py /
        # stores.py list convention).
        rows_stmt.order_by(
            StoreApplication.created_at.desc(), StoreApplication.id.desc()
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return StoreApplicationListResponse(
        items=[StoreApplicationListItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_store_application(
    db: Session, application_id: UUID
) -> StoreApplication:
    """Fetch one application by id, 404 if it does not exist."""
    application = db.get(StoreApplication, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store application not found.",
        )
    return application


def reject_store_application(
    db: Session,
    application_id: UUID,
    payload: StoreApplicationRejectRequest,
    *,
    actor: User,
) -> StoreApplication:
    """Reject a pending-review application (admin-only).

    Sets status=rejected with the (non-blank) reason, stamps the reviewer
    and timestamp, and writes an `application_rejected` audit row in the
    same transaction. Creates no store, user, or auth record. Only a
    `pending_review` application is eligible; any other state is a 409.
    """
    _assert_admin(actor)
    application = get_store_application(db, application_id)
    if application.status != StoreApplicationStatus.pending_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending_review applications can be rejected.",
        )

    application.status = StoreApplicationStatus.rejected
    application.rejection_reason = payload.rejection_reason
    application.reviewed_by_user_id = actor.id
    application.reviewed_at = datetime.now(UTC)

    audit = StoreApplicationAuditLog(
        application_id=application.id,
        event_type="application_rejected",
        actor_user_id=actor.id,
        message="Store application rejected by admin review.",
        payload={"source": "admin_review"},
    )
    db.add(audit)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection violates database constraints.",
        ) from exc

    db.refresh(application)
    _notify_application_rejected(db, application)
    return application


def _notify_application_approved(
    db: Session, application: StoreApplication
) -> None:
    """Send the `store_application_approved` email + audit (F2.25.3).

    Called only AFTER the approval transaction has committed (store + owner
    provisioned) and the row refreshed. Send + audit failures are swallowed
    so a committed approval still returns its 200; this seam never re-raises
    and never touches the provisioning/auth-cleanup paths above it.
    """
    _send_business_email_and_audit(
        db,
        application_id=application.id,
        message=email_templates.build_approved_email(application),
    )


def _notify_owner_activation(application: StoreApplication) -> None:
    """Trigger a Supabase-sent owner password-setup email (F2.25.4).

    Called only AFTER the approval transaction has committed and the row
    refreshed. The owner's Supabase `auth.users` record already exists (made
    at approval with a never-exposed random password); this asks Supabase
    Auth to email the owner a set-password/recovery link back to the
    frontend `/auth/callback`, where the owner chooses their own password.
    Supabase owns the token and sends the email — FastAPI never sees the
    token and never sends a plaintext password.

    Safe-by-default and non-blocking: when `APP_PUBLIC_BASE_URL` is blank
    (the default, e.g. dev/test) the trigger is skipped entirely. Any
    failure is logged (secret-free) and SWALLOWED — a committed approval
    must never become a 5xx, and the activation email is never allowed to
    roll back the store/owner/application provisioning above it.
    """
    base_url = get_app_settings().app_public_base_url.strip().rstrip("/")
    if not base_url:
        logger.info(
            "APP_PUBLIC_BASE_URL not configured; skipping owner activation "
            "email for application %s.",
            application.id,
        )
        return

    redirect_to = f"{base_url}/auth/callback"
    try:
        supabase_admin.send_password_setup_email(
            application.owner_email, redirect_to=redirect_to
        )
    except SupabaseAdminError:
        logger.exception(
            "Supabase password-setup email failed for application %s; the "
            "approval was committed and is unaffected.",
            application.id,
        )
    except Exception:  # noqa: BLE001 — activation must not undo the commit
        logger.exception(
            "Unexpected failure sending owner activation email for "
            "application %s; the approval was committed and is unaffected.",
            application.id,
        )


def _notify_store_onboarding(
    db: Session, application: StoreApplication
) -> None:
    """Send the tokenless store-onboarding business email (F2.25.6).

    Called post-commit after approval. Points the owner at the in-app
    onboarding landing page (`/app/store/onboarding`); carries no auth
    token. Routes through `_send_business_email_and_audit`, so it sends via
    `send_business_email`, records an `email_triggered` audit row, and
    swallows any failure — a committed approval is never rolled back.

    Safe-by-default: when `APP_PUBLIC_BASE_URL` is blank (the default, e.g.
    dev/test) the onboarding email is skipped entirely. The onboarding route
    itself always exists; only the email is gated.
    """
    base_url = get_app_settings().app_public_base_url.strip().rstrip("/")
    if not base_url:
        logger.info(
            "APP_PUBLIC_BASE_URL not configured; skipping store onboarding "
            "email for application %s.",
            application.id,
        )
        return

    onboarding_url = f"{base_url}/app/store/onboarding"
    _send_business_email_and_audit(
        db,
        application_id=application.id,
        message=email_templates.build_onboarding_email(
            application, onboarding_url=onboarding_url
        ),
    )


def _rollback_auth_user(auth_user_id: UUID) -> None:
    """Best-effort delete of a Supabase auth user after a failed DB commit.

    Mirrors `app.api.routes.auth._rollback_supabase_auth_user`: prevents an
    `auth.users` row orphaned without a `public.users` mapping. A failed
    cleanup is logged (no secrets) rather than masking the original error.
    """
    try:
        supabase_admin.delete_auth_user(auth_user_id)
    except SupabaseAdminError:
        logger.warning(
            "Failed to roll back Supabase auth user %s after a store "
            "application approval DB failure; manual cleanup of the orphaned "
            "auth.users row may be required.",
            auth_user_id,
        )


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _store_code_from(business_name: str) -> str:
    """Derive a unique, human-ish store code from the business name.

    Slugifies the name (bounded so `<slug>-<8 hex>` fits Store.code's
    VARCHAR(50)) and appends a random suffix so two stores with the same
    name never collide on `Store.code`'s unique constraint. A residual
    collision (astronomically unlikely) surfaces as an IntegrityError that
    the approval transaction translates to a clean 409.
    """
    slug = _SLUG_RE.sub("-", business_name.strip().lower()).strip("-")
    slug = slug[:40] or "store"
    return f"{slug}-{uuid4().hex[:8]}"


def approve_store_application(
    db: Session,
    application_id: UUID,
    *,
    actor: User,
) -> StoreApplication:
    """Atomically approve a pending application, provisioning store + owner.

    The single path from inert application data to an active store with an
    owner identity (F2.24.C4). Concurrency-safe and atomic:

    - The application row is locked with `FOR UPDATE`, so two admins
      double-clicking approve serialize; the loser re-reads `approved` and
      gets a clean 409, never creating a duplicate store/owner/auth user.
    - The Supabase auth user is created only after the lock + pending check.
      If the DB commit then fails (e.g. a unique-email race), the DB is
      rolled back AND the orphaned auth user is deleted, mirroring the
      `POST /auth/users` rollback contract.
    - The owner role is hardcoded to `owner`; nothing from the application
      or request can influence role (no admin is ever created here).

    404 if missing, 409 if not pending, 409 if the owner email already has
    an account, 502 if the identity provider fails.
    """
    _assert_admin(actor)

    # Lock the application row so concurrent approvals serialize. Re-read
    # under the lock to confirm it is still pending.
    application = db.scalar(
        select(StoreApplication)
        .where(StoreApplication.id == application_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store application not found.",
        )
    if application.status != StoreApplicationStatus.pending_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending_review applications can be approved.",
        )

    owner_email = application.owner_email.strip().lower()

    # An owner email that already maps to a user means this person already
    # has an identity — refuse rather than minting a second auth user.
    if db.scalar(select(User.id).where(User.email == owner_email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this owner email.",
        )

    # 1. Store (flush to obtain its id; not yet committed). A store-code
    #    collision here is PRE-auth, so it just rolls back with a 409 — no
    #    identity-provider cleanup is needed.
    #    business_name is VARCHAR(200) on the application but Store.name is
    #    VARCHAR(150); truncate at the source so a long (but valid) business
    #    name yields a meaningful store name instead of a DataError 500.
    store = Store(
        name=application.business_name[:150],
        code=_store_code_from(application.business_name),
    )
    db.add(store)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The application could not be approved due to a conflict.",
        ) from exc

    # 2. Identity provider FIRST among external effects. The owner has no
    #    password (public intake collected none); mint a strong random one
    #    they never see — credential setup is a later invite/reset flow
    #    (C8). The created user is email-confirmed by supabase_admin.
    try:
        auth_user_id = supabase_admin.create_auth_user(
            email=owner_email,
            password=secrets.token_urlsafe(32),
            user_metadata={
                "full_name": application.owner_full_name,
                "nuberush_role": UserRole.owner.value,
                "nuberush_store_id": str(store.id),
            },
        )
    except SupabaseAdminError as exc:
        db.rollback()
        logger.warning("Supabase auth user creation failed on approval: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create the owner with the identity provider.",
        ) from exc

    # 3-5. Owner + application transition + audit, all under one guard. Any
    #      DB IntegrityError from here on (owner email / auth_user_id unique
    #      race, store-id FK, etc.) surfaces at flush OR commit, so the whole
    #      region is wrapped: roll back the DB and delete the orphaned auth
    #      user so neither side is left dangling. Owner role is hardcoded to
    #      `owner` — nothing from the application can influence it.
    try:
        owner = User(
            full_name=application.owner_full_name,
            email=owner_email,
            phone=application.owner_phone,
            role=UserRole.owner,
            store_id=store.id,
            is_active=True,
            auth_user_id=auth_user_id,
        )
        db.add(owner)
        db.flush()  # assigns owner.id; fires unique violations here

        now = datetime.now(UTC)
        application.status = StoreApplicationStatus.approved
        application.provisioned_store_id = store.id
        application.provisioned_owner_user_id = owner.id
        application.reviewed_by_user_id = actor.id
        application.reviewed_at = now
        application.rejection_reason = None

        # Explicit increasing timestamps so the detail feed renders
        # store → owner → approved in order (created_at + id sort).
        db.add_all(
            [
                StoreApplicationAuditLog(
                    application_id=application.id,
                    event_type="store_provisioned",
                    actor_user_id=actor.id,
                    message="Store provisioned on approval.",
                    payload={
                        "source": "admin_approval",
                        "store_id": str(store.id),
                    },
                    created_at=now,
                ),
                StoreApplicationAuditLog(
                    application_id=application.id,
                    event_type="owner_provisioned",
                    actor_user_id=actor.id,
                    message="Owner user provisioned on approval.",
                    payload={
                        "source": "admin_approval",
                        "owner_user_id": str(owner.id),
                    },
                    created_at=now + timedelta(microseconds=1),
                ),
                StoreApplicationAuditLog(
                    application_id=application.id,
                    event_type="application_approved",
                    actor_user_id=actor.id,
                    message="Store application approved by admin review.",
                    payload={"source": "admin_approval"},
                    created_at=now + timedelta(microseconds=2),
                ),
            ]
        )
        db.commit()
    except IntegrityError as exc:
        # A concurrent approval / duplicate owner email won the race after
        # the auth user was created. Roll back the DB and delete the
        # orphaned auth user, then return a clean 409 (never a raw 500).
        db.rollback()
        _rollback_auth_user(auth_user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The application could not be approved due to a conflict.",
        ) from exc
    except Exception as exc:
        # Any OTHER DB failure after the auth user exists — a deadlock /
        # lock-wait timeout / dropped connection (realistic while the row is
        # held FOR UPDATE) — must STILL roll back and delete the orphaned
        # auth.users row, never leave it dangling. Mirrors the broad guard in
        # app.api.routes.auth.create_user. Surfaced as a controlled 500.
        db.rollback()
        _rollback_auth_user(auth_user_id)
        logger.warning("DB failure after auth user create on approval: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The application could not be approved.",
        ) from exc

    db.refresh(application)
    _notify_application_approved(db, application)
    _notify_owner_activation(application)
    _notify_store_onboarding(db, application)
    return application
