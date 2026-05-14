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

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import case
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_app_settings
from app.db.models import ComplianceStatus
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_settings import AdminBillingSettings
from app.schemas.admin_settings import AdminCompliancePolicySettings
from app.schemas.admin_settings import AdminNotificationSettings
from app.schemas.admin_settings import AdminOperationsSettings
from app.schemas.admin_settings import AdminPlatformSettings
from app.schemas.admin_settings import AdminPreferencesSettings
from app.schemas.admin_settings import AdminSettingsResponse


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

    return AdminSettingsResponse(
        platform=_platform_section(),
        billing=_billing_section(db),
        compliance=_compliance_section(db),
        operations=_operations_section(),
        notifications=_notifications_section(),
        admin_preferences=_admin_preferences_section(db),
    )
