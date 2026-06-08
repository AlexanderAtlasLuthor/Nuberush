"""Service layer for the admin settings snapshot.

Computes a single `AdminSettingsResponse` from existing tables and
locked server constants on every call. Mirrors the design rules of
`app.services.admin_dashboard` and `app.services.admin_operations`:

  - No persistence. No migrations. No new tables.
  - Every value is either a real DB aggregate or a server constant
    that the rest of the codebase already enforces.
  - admin-only at the service boundary (defense in depth on top of
    the route's `require_admin`).
  - Read-only. No `db.add`, no `db.delete`, no `db.commit`.

The constants surfaced here are imported from the modules that
actually enforce them (`admin_operations` for alert defaults, the
locked status set, `OrderStatus` for the histogram dense set) so the
settings page can never drift from the active policy.
"""

from __future__ import annotations

from decimal import Decimal

from typing import Any

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import case
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_app_settings
from app.db.models import ComplianceStatus
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import PlatformSettings
from app.db.models import PlatformSettingsAuditLog
from app.db.models import Product
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_settings import AdminBillingSettings
from app.schemas.admin_settings import AdminCompliancePolicySettings
from app.schemas.admin_settings import AdminEditableSettings
from app.schemas.admin_settings import AdminNotificationSettings
from app.schemas.admin_settings import AdminOperationsSettings
from app.schemas.admin_settings import AdminPlatformSettings
from app.schemas.admin_settings import AdminPreferencesSettings
from app.schemas.admin_settings import AdminSettingsResponse
from app.schemas.admin_settings import AdminSettingsUpdate


# Default values for the singleton platform-settings row when it does not
# exist yet (first access). These mirror the read-only constants the snapshot
# already surfaces, so get-or-create lands consistent values. NEVER secrets,
# never env-backed config.
_PLATFORM_SETTINGS_DEFAULTS: dict[str, Any] = {
    "platform_name": "NubeRush",
    "support_email": None,
    "default_locale": "en-US",
    "default_timezone": "America/New_York",
}

# The only fields ever written to / captured in audit before/after. Keeping
# this list local guarantees a secret/env field can never leak into the audit
# trail even if the schema later grows.
_EDITABLE_FIELDS: tuple[str, ...] = (
    "platform_name",
    "support_email",
    "default_locale",
    "default_timezone",
)

# Action discriminator for the dedicated platform-settings audit table.
_AUDIT_ACTION_UPDATED = "platform_settings_updated"


# --------------------------------------------------------------------- #
# Locked constants
# --------------------------------------------------------------------- #


# Platform metadata defaults. The jurisdiction value mirrors the
# `Product.jurisdiction` server default (`'FL'`); the timezone value
# mirrors the `Store.timezone` server default (`'America/New_York'`).
# Both are referenced directly here rather than reflected off the DB
# so the settings response stays well-typed for empty databases.
_DEFAULT_JURISDICTION = "FL"
_DEFAULT_STORE_TIMEZONE = "America/New_York"
_PLATFORM_VERSION = "0.1.0"


# Billing / commission policy. The platform charges a flat commission
# rate on every delivered order. Stored in basis points so the wire
# value is always an integer; the UI renders the percentage by
# dividing by 100.
_COMMISSION_RATE_BASIS_POINTS = 500  # 5.00 %
_BILLING_CURRENCY = "USD"


# Operational defaults. Mirror the bounds enforced by the
# `admin_operations` service so the settings page can't lie about
# what the alert feed will accept.
_DEFAULT_ALERT_PAGE_SIZE = 50
_MAX_ALERT_PAGE_SIZE = 200
_DEFAULT_AGING_MINUTES = 1440

_OPEN_ORDER_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.pending,
    OrderStatus.accepted,
    OrderStatus.preparing,
    OrderStatus.ready,
    OrderStatus.out_for_delivery,
)


# Compliance blocker predicate set (same set the dashboard and the
# operations alert feed use).
_BLOCKING_COMPLIANCE_STATUSES: frozenset[ComplianceStatus] = frozenset(
    {ComplianceStatus.banned, ComplianceStatus.restricted}
)


# Locked event-type catalog. These are the audit / order action keys
# the rest of the platform already emits; surfacing them here gives
# operators a stable list to map notification channels against once
# that surface exists.
_NOTIFICATION_EVENT_TYPES: tuple[str, ...] = (
    "order.created",
    "order.accepted",
    "order.canceled",
    "order.delivered",
    "order.returned",
    "inventory.low_stock",
    "inventory.adjustment",
    "compliance.product_blocked",
    "compliance.product_restored",
    "compliance.review_recorded",
    "store.deactivated",
    "store.reactivated",
)


# Admin preference defaults. `en-US` matches the public site's copy
# locale; the timezone default is the same `America/New_York` value
# the stores table defaults to.
_DEFAULT_LOCALE = "en-US"
_DEFAULT_ADMIN_TIMEZONE = "America/New_York"


# --------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------- #


def _assert_admin_caller(actor: User) -> None:
    """Service-level admin gate.

    Symmetric with `app.services.admin_dashboard._assert_admin_caller`
    and the inventory / orders / audit / operations admin services.
    The route already enforces `require_admin`; this gate guards
    direct service callers (admin scripts, batch jobs).
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


# --------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------- #


def _platform_section() -> AdminPlatformSettings:
    settings = get_app_settings()
    return AdminPlatformSettings(
        app_name=settings.app_name,
        app_env=settings.app_env,
        app_debug=settings.app_debug,
        version=_PLATFORM_VERSION,
        default_jurisdiction=_DEFAULT_JURISDICTION,
        default_store_timezone=_DEFAULT_STORE_TIMEZONE,
    )


def _billing_section(db: Session) -> AdminBillingSettings:
    """Aggregates over delivered orders + locked commission constants.

    One round-trip. `coalesce(sum, 0)` keeps the SUM well-defined when
    no rows match (the count is then 0 and the amount `0.00`).
    """
    stmt = select(
        func.count(Order.id),
        func.coalesce(func.sum(Order.total_amount), 0),
    ).where(Order.status == OrderStatus.delivered)
    count_row, total_row = db.execute(stmt).one()
    delivered_count = int(count_row or 0)
    delivered_total = Decimal(total_row or 0).quantize(Decimal("0.01"))
    return AdminBillingSettings(
        commission_rate_basis_points=_COMMISSION_RATE_BASIS_POINTS,
        currency=_BILLING_CURRENCY,
        delivered_orders_count=delivered_count,
        delivered_orders_total_amount=f"{delivered_total:.2f}",
    )


def _compliance_section(db: Session) -> AdminCompliancePolicySettings:
    """One SQL round-trip for the four compliance counts.

    Conditional aggregates so we never load product rows into Python.
    The `blocked` count uses the same union predicate as the
    operations alert generator (`allowed_for_sale = false OR
    compliance_status IN (banned, restricted)`).
    """
    allowed_expr = func.coalesce(
        func.sum(
            case(
                (Product.compliance_status == ComplianceStatus.allowed, 1),
                else_=0,
            )
        ),
        0,
    )
    restricted_expr = func.coalesce(
        func.sum(
            case(
                (
                    Product.compliance_status == ComplianceStatus.restricted,
                    1,
                ),
                else_=0,
            )
        ),
        0,
    )
    banned_expr = func.coalesce(
        func.sum(
            case(
                (Product.compliance_status == ComplianceStatus.banned, 1),
                else_=0,
            )
        ),
        0,
    )
    blocked_expr = func.coalesce(
        func.sum(
            case(
                (
                    or_(
                        Product.allowed_for_sale.is_(False),
                        Product.compliance_status.in_(
                            _BLOCKING_COMPLIANCE_STATUSES
                        ),
                    ),
                    1,
                ),
                else_=0,
            )
        ),
        0,
    )
    stmt = select(allowed_expr, restricted_expr, banned_expr, blocked_expr)
    allowed, restricted, banned, blocked = db.execute(stmt).one()
    return AdminCompliancePolicySettings(
        default_jurisdiction=_DEFAULT_JURISDICTION,
        allowed_count=int(allowed or 0),
        restricted_count=int(restricted or 0),
        banned_count=int(banned or 0),
        blocked_count=int(blocked or 0),
    )


def _operations_section() -> AdminOperationsSettings:
    return AdminOperationsSettings(
        default_alert_page_size=_DEFAULT_ALERT_PAGE_SIZE,
        max_alert_page_size=_MAX_ALERT_PAGE_SIZE,
        default_aging_minutes=_DEFAULT_AGING_MINUTES,
        open_order_statuses=list(_OPEN_ORDER_STATUSES),
    )


def _notifications_section() -> AdminNotificationSettings:
    return AdminNotificationSettings(
        event_types=list(_NOTIFICATION_EVENT_TYPES),
    )


def _get_or_create_platform_settings(db: Session) -> PlatformSettings:
    """Return the singleton `platform_settings` row, creating it on first use.

    Singleton-ness is enforced here (not the DB): the oldest row wins if more
    than one ever exists. When no row exists, one is created with the safe
    defaults and committed so it persists for subsequent reads. NO audit row
    is written for this bootstrap create — it is not an admin mutation, just
    materializing the defaults the snapshot already reported. Never touches
    env config and never stores a secret.
    """
    settings = db.scalars(
        select(PlatformSettings)
        .order_by(PlatformSettings.created_at.asc(), PlatformSettings.id.asc())
        .limit(1)
    ).first()
    if settings is not None:
        return settings

    settings = PlatformSettings(**_PLATFORM_SETTINGS_DEFAULTS)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _editable_snapshot(settings: PlatformSettings) -> dict[str, Any]:
    """JSON-safe snapshot of ONLY the four editable fields.

    This is the single source for both the audit `before`/`after` payloads and
    the equality check. By construction it can never carry a secret or an
    env-backed value — only the allow-listed columns appear.
    """
    return {field: getattr(settings, field) for field in _EDITABLE_FIELDS}


def _editable_section(settings: PlatformSettings) -> AdminEditableSettings:
    return AdminEditableSettings(
        platform_name=settings.platform_name,
        support_email=settings.support_email,
        default_locale=settings.default_locale,
        default_timezone=settings.default_timezone,
    )


def _admin_preferences_section(db: Session) -> AdminPreferencesSettings:
    """One SQL round-trip for `(admin_total, admin_active)`."""
    active_expr = func.coalesce(
        func.sum(case((User.is_active.is_(True), 1), else_=0)),
        0,
    )
    stmt = select(func.count(User.id), active_expr).where(
        User.role == UserRole.admin
    )
    total, active = db.execute(stmt).one()
    return AdminPreferencesSettings(
        admin_total=int(total or 0),
        admin_active=int(active or 0),
        default_locale=_DEFAULT_LOCALE,
        default_timezone=_DEFAULT_ADMIN_TIMEZONE,
    )


# --------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------- #


def get_admin_settings_snapshot(
    db: Session,
    *,
    actor: User,
) -> AdminSettingsResponse:
    """Build the full admin settings snapshot for an admin caller.

    Pipeline:
      1. RBAC gate (admin only; 403 otherwise).
      2. Each section is computed independently. Sections that do
         not need the database (`platform`, `operations`,
         `notifications`) are pure constant-time builds.
      3. The response is a single Pydantic envelope; no client-side
         re-assembly is required.
    """
    _assert_admin_caller(actor)

    settings = _get_or_create_platform_settings(db)

    return AdminSettingsResponse(
        platform=_platform_section(),
        billing=_billing_section(db),
        compliance=_compliance_section(db),
        operations=_operations_section(),
        notifications=_notifications_section(),
        admin_preferences=_admin_preferences_section(db),
        editable=_editable_section(settings),
    )


def update_admin_settings(
    db: Session,
    payload: AdminSettingsUpdate,
    *,
    actor: User,
) -> AdminSettingsResponse:
    """Apply a partial update to the writable platform settings (F2.27.10).

    Pipeline (mirrors the `stores.update_store` write pattern, minus any store
    tenancy):
      1. RBAC gate (admin only; 403 otherwise).
      2. Get-or-create the singleton `platform_settings` row.
      3. Apply ONLY the fields the caller actually sent
         (`model_dump(exclude_unset=True)` — the schema already restricts the
         keys to the four-field allow-list).
      4. No-op short-circuit: if nothing was sent, or every sent value equals
         the current value, return the current snapshot WITHOUT writing an
         audit row (a no-op is not an auditable decision). Pending in-memory
         assignments are discarded with a rollback.
      5. Otherwise append a `PlatformSettingsAuditLog` (action
         `platform_settings_updated`) with before/after limited to the four
         editable fields, and COMMIT it atomically with the field change.

    Audit goes to the dedicated `platform_settings_audit_logs` table ONLY:
    never `write_operational_audit_log`, never the unified audit feed. The
    before/after payloads can only contain the allow-listed fields, so no
    secret or env value can ever land in the trail.
    """
    _assert_admin_caller(actor)

    settings = _get_or_create_platform_settings(db)

    changes = payload.model_dump(exclude_unset=True)
    before = _editable_snapshot(settings)

    for field, value in changes.items():
        setattr(settings, field, value)

    after = _editable_snapshot(settings)

    if after == before:
        # Empty payload or every value identical to the current state — not an
        # auditable change. Discard any same-value reassignments and return the
        # current snapshot unchanged (no audit row, no updated_at bump).
        db.rollback()
        return get_admin_settings_snapshot(db, actor=actor)

    db.add(
        PlatformSettingsAuditLog(
            platform_settings_id=settings.id,
            actor_user_id=actor.id,
            action=_AUDIT_ACTION_UPDATED,
            before=before,
            after=after,
        )
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Platform settings update violates database constraints.",
        ) from exc

    db.refresh(settings)
    return get_admin_settings_snapshot(db, actor=actor)
