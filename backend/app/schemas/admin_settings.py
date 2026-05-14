"""Pydantic v2 schemas for the admin settings snapshot.

Wire contract for `GET /admin/settings`: a single aggregate response
that bundles the platform configuration, billing/commission model,
compliance policy defaults, operational defaults, notification event
catalog and admin preferences.

Design rules (mirroring `admin_dashboard.py` / `admin_operations.py`):

- Read-only. There is no persistence layer behind this endpoint —
  every value is either a server constant (locked by the codebase) or
  a count derived from existing tables on each request.

- Six sub-sections (one per cluster shown on the Admin Settings
  surface). Each is a separate `BaseModel` so callers can refer to a
  single section in isolation when needed.

- All sub-models forbid extras (`extra="forbid"`) so a future field
  addition surfaces as a 500 rather than a silent drop.

- No mutation schema. The contract intentionally does not expose
  PATCH/PUT for settings — billing/commission, compliance policy and
  notification defaults are platform constants today.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.db.models import OrderStatus


class AdminPlatformSettings(BaseModel):
    """Platform-level metadata sourced from `AppSettings`.

    `app_name`, `app_env` and `app_debug` come straight from the
    process config (`app.core.config.get_app_settings`). `version`
    mirrors the FastAPI `app.version` string so the UI doesn't have
    to scrape it from another endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    app_name: str = Field(min_length=1)
    app_env: str = Field(min_length=1)
    app_debug: bool
    version: str = Field(min_length=1)
    default_jurisdiction: str = Field(min_length=1)
    default_store_timezone: str = Field(min_length=1)


class AdminBillingSettings(BaseModel):
    """Platform billing / commission configuration.

    No billing tables exist today; the platform charges a flat
    commission rate set in code. The shape is a real read of those
    constants, not a fake-data simulation: the same values are used
    by the service layer when (eventually) computing commission
    payouts.

    `delivered_orders_count` and `delivered_orders_total_amount`
    surface the gross flow the commission policy would currently
    apply to. They are aggregates over `orders` filtered to the
    `delivered` status — not a payout figure, not an invoice.
    """

    model_config = ConfigDict(extra="forbid")

    commission_rate_basis_points: int = Field(ge=0, le=10_000)
    currency: str = Field(min_length=3, max_length=3)
    delivered_orders_count: int = Field(ge=0)
    delivered_orders_total_amount: str = Field(min_length=1)


class AdminCompliancePolicySettings(BaseModel):
    """Compliance policy defaults + a snapshot of product counts.

    `default_jurisdiction` mirrors the `Product.jurisdiction` server
    default. The four count fields are independent group aggregates
    over the products table.
    """

    model_config = ConfigDict(extra="forbid")

    default_jurisdiction: str = Field(min_length=1)
    allowed_count: int = Field(ge=0)
    restricted_count: int = Field(ge=0)
    banned_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)


class AdminOperationsSettings(BaseModel):
    """Operational defaults used by the admin operations alert feed.

    Locked by `app.services.admin_operations` and mirrored here so
    the settings page reflects what the system actually applies. The
    open order status list is the canonical "open" set shared by the
    dashboard `open_count` and the alert generator `aging_order`.
    """

    model_config = ConfigDict(extra="forbid")

    default_alert_page_size: int = Field(ge=1, le=200)
    max_alert_page_size: int = Field(ge=1, le=200)
    default_aging_minutes: int = Field(ge=1)
    open_order_statuses: list[OrderStatus]


class AdminNotificationSettings(BaseModel):
    """Notification event catalog.

    No notification persistence exists today. The list of event types
    is a locked server constant — the same names the API emits in
    audit rows and order transitions. Surfacing them here lets
    operators see what events the platform recognises without
    inventing a delivery channel.
    """

    model_config = ConfigDict(extra="forbid")

    event_types: list[str]


class AdminPreferencesSettings(BaseModel):
    """Admin user preferences snapshot.

    `admin_total` and `admin_active` are aggregates over the `users`
    table filtered to `role = admin`. The locale / timezone defaults
    are the platform constants new admin sessions inherit when none
    is overridden.
    """

    model_config = ConfigDict(extra="forbid")

    admin_total: int = Field(ge=0)
    admin_active: int = Field(ge=0)
    default_locale: str = Field(min_length=2)
    default_timezone: str = Field(min_length=1)


class AdminSettingsResponse(BaseModel):
    """Top-level response for `GET /admin/settings`.

    Bundles every settings cluster. Read-only, admin-only,
    computed-on-request. No persistence layer backs this shape; the
    service layer derives every value from existing tables and
    locked constants on every call.
    """

    model_config = ConfigDict(extra="forbid")

    platform: AdminPlatformSettings
    billing: AdminBillingSettings
    compliance: AdminCompliancePolicySettings
    operations: AdminOperationsSettings
    notifications: AdminNotificationSettings
    admin_preferences: AdminPreferencesSettings
