// Admin settings wire types.
//
// 1:1 mirror of the FastAPI admin-settings contract introduced in
// `backend/app/schemas/admin_settings.py` and `app/api/routes/
// admin_settings.py` (GET /admin/settings). Field names and casing
// match the JSON over the wire exactly (snake_case).
//
// Hard rules baked in (mirroring admin-compliance / admin-operations
// types):
//   - No derived/display-only fields. Everything that ends up on the
//     UI lives on the wire as the backend produced it.
//   - No mutation request types. The settings page is read-only; the
//     backend exposes no PATCH/PUT contract for these clusters.
//   - No store_id anywhere — platform settings are global.
//   - No frontend-only enums; the open order statuses arrive as
//     strings from the backend `OrderStatus` enum.

export interface AdminPlatformSettings {
  app_name: string;
  app_env: string;
  app_debug: boolean;
  version: string;
  default_jurisdiction: string;
  default_store_timezone: string;
}

export interface AdminBillingSettings {
  /** Commission rate in basis points (1/100th of 1 percent). */
  commission_rate_basis_points: number;
  /** ISO 4217 alpha-3 currency code. */
  currency: string;
  delivered_orders_count: number;
  /** Decimal string (two fractional digits) — never a JS number. */
  delivered_orders_total_amount: string;
}

export interface AdminCompliancePolicySettings {
  default_jurisdiction: string;
  allowed_count: number;
  restricted_count: number;
  banned_count: number;
  blocked_count: number;
}

export interface AdminOperationsSettings {
  default_alert_page_size: number;
  max_alert_page_size: number;
  default_aging_minutes: number;
  /** `OrderStatus` literals as they appear on the wire. */
  open_order_statuses: string[];
}

export interface AdminNotificationSettings {
  event_types: string[];
}

export interface AdminPreferencesSettings {
  admin_total: number;
  admin_active: number;
  default_locale: string;
  default_timezone: string;
}

/**
 * The writable platform-settings cluster (F2.27.10). These four values are
 * PERSISTED (singleton `platform_settings` row) and editable via
 * `PATCH /admin/settings`. `support_email` is nullable (an operator may clear
 * it). Everything else on the response stays read-only.
 */
export interface AdminEditableSettings {
  platform_name: string;
  support_email: string | null;
  default_locale: string;
  default_timezone: string;
}

export interface AdminSettingsResponse {
  platform: AdminPlatformSettings;
  billing: AdminBillingSettings;
  compliance: AdminCompliancePolicySettings;
  operations: AdminOperationsSettings;
  notifications: AdminNotificationSettings;
  admin_preferences: AdminPreferencesSettings;
  editable: AdminEditableSettings;
}

/**
 * Partial-update request for the writable cluster (F2.27.10). Mirrors the
 * backend `AdminSettingsUpdate` (snake_case, all optional). Only fields the
 * user actually changed should be sent; `support_email` may be sent as an
 * empty string to clear it (the backend normalizes blank → null).
 */
export interface AdminSettingsUpdateRequest {
  platform_name?: string;
  support_email?: string | null;
  default_locale?: string;
  default_timezone?: string;
}
