// Real Admin Settings page over the `GET /admin/settings` backend.
//
// Mounted at /app/admin/settings. Replaces the AdminSettingsPlaceholder
// from `route-components.tsx`. Read-only by contract: the page
// renders backend-computed values only — the frontend never invents
// platform settings, never simulates billing flows, never persists a
// policy change.
//
// Wiring:
//   useAdminSettingsQuery()
//     -> SettingsSection × 6 (platform, billing, compliance,
//                             operations, notifications, admin prefs)
//
// Architecture rules in force here (mirroring AdminCompliancePage /
// AdminOperationsPage):
//   - No fetch, no apiRequest, no axios, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend is the security authority; non-admin callers get an
//     ApiError(403) which surfaces in the error state.
//   - No useStoreContext — platform settings are global.
//   - No useMutation here — every cluster on this page is read-only
//     by contract today. Adding a PATCH surface requires a backend
//     contract change first.
//   - No client-side derivation of policy values; the commission
//     percentage is formatted by dividing the wire basis points by
//     100 (presentation only).
//   - No fake rows, no placeholder data.

import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { getApiErrorMessage } from "@/api";

import {
  useAdminSettingsQuery,
  useUpdateAdminSettingsMutation,
} from "../hooks";
import { AdminSettingsForm } from "../components/AdminSettingsForm";
import { SettingsSection } from "../components/SettingsSection";
import type {
  AdminBillingSettings,
  AdminCompliancePolicySettings,
  AdminNotificationSettings,
  AdminOperationsSettings,
  AdminPlatformSettings,
  AdminPreferencesSettings,
  AdminSettingsResponse,
} from "../types";

function formatCommissionRate(basisPoints: number): string {
  // Basis points → percent. 500 bps == 5.00 %. Pure presentation;
  // the source of truth stays the integer on the wire.
  return `${(basisPoints / 100).toFixed(2)} %`;
}

function formatCurrencyAmount(amount: string, currency: string): string {
  return `${amount} ${currency}`;
}

function PageHeader() {
  return (
    <header>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Admin · Settings
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Admin Settings
      </h1>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        Platform settings for NubeRush operators. Every value below
        reflects the current platform configuration and live operational
        data.
      </p>
    </header>
  );
}

function StringList({ items, testId }: { items: string[]; testId: string }) {
  if (items.length === 0) {
    return (
      <span className="text-sm text-muted-foreground" data-testid={`${testId}-empty`}>
        None
      </span>
    );
  }
  return (
    <ul className="flex flex-wrap gap-1.5" data-testid={testId}>
      {items.map((item) => (
        <li key={item}>
          <Badge variant="secondary" className="font-mono text-[11px]">
            {item}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

function PlatformCard({ platform }: { platform: AdminPlatformSettings }) {
  return (
    <SettingsSection
      testId="settings-platform"
      title="Platform configuration"
      description="Core platform configuration for this environment."
      fields={[
        { key: "app_name", label: "App name", value: platform.app_name },
        {
          key: "app_env",
          label: "Environment",
          value: (
            <Badge variant="outline" className="font-mono text-[11px]">
              {platform.app_env}
            </Badge>
          ),
        },
        {
          key: "version",
          label: "Version",
          value: (
            <span className="font-mono text-sm">{platform.version}</span>
          ),
        },
        {
          key: "app_debug",
          label: "Debug mode",
          value: platform.app_debug ? "Enabled" : "Disabled",
        },
        {
          key: "default_jurisdiction",
          label: "Default jurisdiction",
          value: platform.default_jurisdiction,
        },
        {
          key: "default_store_timezone",
          label: "Default store timezone",
          value: (
            <span className="font-mono text-sm">
              {platform.default_store_timezone}
            </span>
          ),
        },
      ]}
    />
  );
}

function BillingCard({ billing }: { billing: AdminBillingSettings }) {
  return (
    <SettingsSection
      testId="settings-billing"
      title="Billing / commission"
      description="Platform commission policy and the gross flow it currently applies to. The aggregate covers delivered orders only."
      fields={[
        {
          key: "commission_rate",
          label: "Commission rate",
          value: formatCommissionRate(billing.commission_rate_basis_points),
          hint: `${(billing.commission_rate_basis_points / 100).toFixed(2)}% platform commission`,
        },
        {
          key: "currency",
          label: "Currency",
          value: (
            <Badge variant="outline" className="font-mono text-[11px]">
              {billing.currency}
            </Badge>
          ),
        },
        {
          key: "delivered_orders_count",
          label: "Delivered orders",
          value: billing.delivered_orders_count.toLocaleString(),
        },
        {
          key: "delivered_orders_total",
          label: "Delivered gross",
          value: formatCurrencyAmount(
            billing.delivered_orders_total_amount,
            billing.currency,
          ),
        },
      ]}
    />
  );
}

function ComplianceCard({
  compliance,
}: {
  compliance: AdminCompliancePolicySettings;
}) {
  return (
    <SettingsSection
      testId="settings-compliance"
      title="Compliance policy"
      description="Compliance defaults and a snapshot of product counts by status. Blocked counts apply the platform's shared compliance rules."
      fields={[
        {
          key: "default_jurisdiction",
          label: "Default jurisdiction",
          value: compliance.default_jurisdiction,
        },
        {
          key: "allowed_count",
          label: "Allowed products",
          value: compliance.allowed_count.toLocaleString(),
        },
        {
          key: "restricted_count",
          label: "Restricted products",
          value: compliance.restricted_count.toLocaleString(),
        },
        {
          key: "banned_count",
          label: "Banned products",
          value: compliance.banned_count.toLocaleString(),
        },
        {
          key: "blocked_count",
          label: "Blocked from sale",
          value: compliance.blocked_count.toLocaleString(),
          hint: "Products that are restricted, banned, or not allowed for sale.",
        },
      ]}
    />
  );
}

function OperationsCard({
  operations,
}: {
  operations: AdminOperationsSettings;
}) {
  return (
    <SettingsSection
      testId="settings-operations"
      title="Operational defaults"
      description="Defaults the operations alert feed applies when no explicit parameters are provided."
      fields={[
        {
          key: "default_alert_page_size",
          label: "Default alert page size",
          value: operations.default_alert_page_size.toLocaleString(),
        },
        {
          key: "max_alert_page_size",
          label: "Max alert page size",
          value: operations.max_alert_page_size.toLocaleString(),
        },
        {
          key: "default_aging_minutes",
          label: "Default aging threshold",
          value: `${operations.default_aging_minutes.toLocaleString()} min`,
          hint: "Applied to aging-order alerts when no threshold is supplied.",
        },
        {
          key: "open_order_statuses",
          label: "Open order statuses",
          value: (
            <StringList
              items={operations.open_order_statuses}
              testId="settings-operations-open-statuses"
            />
          ),
        },
      ]}
    />
  );
}

function NotificationsCard({
  notifications,
}: {
  notifications: AdminNotificationSettings;
}) {
  return (
    <SettingsSection
      testId="settings-notifications"
      title="Notifications"
      description="Event catalog the platform recognises. Channel delivery and per-user routing are not yet exposed; this list is the contract a future notification surface will subscribe against."
      fields={[
        {
          key: "event_types",
          label: "Event types",
          value: (
            <StringList
              items={notifications.event_types}
              testId="settings-notifications-event-types"
            />
          ),
        },
      ]}
    />
  );
}

function AdminPreferencesCard({
  preferences,
}: {
  preferences: AdminPreferencesSettings;
}) {
  return (
    <SettingsSection
      testId="settings-admin-preferences"
      title="Admin preferences"
      description="Defaults inherited by new admin sessions and the current admin user population."
      fields={[
        {
          key: "admin_total",
          label: "Admin users",
          value: preferences.admin_total.toLocaleString(),
        },
        {
          key: "admin_active",
          label: "Active admin users",
          value: preferences.admin_active.toLocaleString(),
        },
        {
          key: "default_locale",
          label: "Default locale",
          value: (
            <span className="font-mono text-sm">
              {preferences.default_locale}
            </span>
          ),
        },
        {
          key: "default_timezone",
          label: "Default timezone",
          value: (
            <span className="font-mono text-sm">
              {preferences.default_timezone}
            </span>
          ),
        },
      ]}
    />
  );
}

function EditableSettingsCard({ data }: { data: AdminSettingsResponse }) {
  const mutation = useUpdateAdminSettingsMutation();
  return (
    <AdminSettingsForm
      editable={data.editable}
      isPending={mutation.isPending}
      errorMessage={
        mutation.isError ? getApiErrorMessage(mutation.error) : null
      }
      onSubmit={(payload) => mutation.mutate(payload)}
    />
  );
}

function SettingsContent({ data }: { data: AdminSettingsResponse }) {
  return (
    <div className="space-y-5">
      <EditableSettingsCard data={data} />
      <PlatformCard platform={data.platform} />
      <BillingCard billing={data.billing} />
      <ComplianceCard compliance={data.compliance} />
      <OperationsCard operations={data.operations} />
      <NotificationsCard notifications={data.notifications} />
      <AdminPreferencesCard preferences={data.admin_preferences} />
    </div>
  );
}

export default function AdminSettingsPage() {
  const query = useAdminSettingsQuery();

  return (
    <div
      className="p-6 md:p-8 space-y-6 max-w-5xl"
      data-testid="admin-settings-page"
    >
      <PageHeader />

      {query.isLoading ? (
        <LoadingState message="Loading admin settings…" />
      ) : query.isError ? (
        <ErrorState
          title="Could not load admin settings"
          message={getApiErrorMessage(query.error)}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : query.isSuccess && query.data ? (
        <SettingsContent data={query.data} />
      ) : null}
    </div>
  );
}
