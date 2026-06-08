// Tests for the real Admin Settings page.
//
// Stub `../../hooks` so we drive every query state without TanStack
// Query or the API. The page does not use react-router-dom hooks,
// useStoreContext, or useAuth — verified by the architecture
// assertion at the bottom of this file.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type {
  UseMutationResult,
  UseQueryResult,
} from "@tanstack/react-query";

import AdminSettingsPage from "../AdminSettingsPage";
import * as adminSettingsHooks from "../../hooks";
import type { AdminSettingsResponse } from "../../types";

vi.mock("../../hooks", () => ({
  useAdminSettingsQuery: vi.fn(),
  useUpdateAdminSettingsMutation: vi.fn(),
  adminSettingsKeys: { all: ["admin-settings"] as const },
}));

function asQueryResult(
  partial: Partial<UseQueryResult<AdminSettingsResponse>>,
): UseQueryResult<AdminSettingsResponse> {
  return {
    refetch: vi.fn(),
    isPending: false,
    isLoading: false,
    isError: false,
    isSuccess: false,
    isFetching: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseQueryResult<AdminSettingsResponse>;
}

function asMutationResult(
  partial: Partial<UseMutationResult> = {},
): UseMutationResult {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseMutationResult;
}

function makeSettings(
  overrides: Partial<AdminSettingsResponse> = {},
): AdminSettingsResponse {
  return {
    platform: {
      app_name: "NubeRush API",
      app_env: "production",
      app_debug: false,
      version: "0.1.0",
      default_jurisdiction: "FL",
      default_store_timezone: "America/New_York",
    },
    billing: {
      commission_rate_basis_points: 500,
      currency: "USD",
      delivered_orders_count: 1234,
      delivered_orders_total_amount: "98765.43",
    },
    compliance: {
      default_jurisdiction: "FL",
      allowed_count: 12,
      restricted_count: 3,
      banned_count: 1,
      blocked_count: 5,
    },
    operations: {
      default_alert_page_size: 50,
      max_alert_page_size: 200,
      default_aging_minutes: 1440,
      open_order_statuses: [
        "pending",
        "accepted",
        "preparing",
        "ready",
        "out_for_delivery",
      ],
    },
    notifications: {
      event_types: ["order.created", "order.delivered"],
    },
    admin_preferences: {
      admin_total: 4,
      admin_active: 3,
      default_locale: "en-US",
      default_timezone: "America/New_York",
    },
    editable: {
      platform_name: "NubeRush",
      support_email: null,
      default_locale: "en-US",
      default_timezone: "America/New_York",
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReset();
  vi.mocked(adminSettingsHooks.useUpdateAdminSettingsMutation).mockReset();
  vi.mocked(adminSettingsHooks.useUpdateAdminSettingsMutation).mockReturnValue(
    asMutationResult() as never,
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminSettingsPage", () => {
  it("renders the loading state while the query is loading", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isLoading: true, isPending: true }),
    );

    render(<AdminSettingsPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Loading admin settings…")).toBeInTheDocument();
  });

  it("renders the error state with a retry button when the query errors", () => {
    const refetch = vi.fn();
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("403 Forbidden"),
        refetch,
      }),
    );

    render(<AdminSettingsPage />);
    expect(
      screen.getByText("Could not load admin settings"),
    ).toBeInTheDocument();
    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the platform section with backend-provided metadata", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    const section = screen.getByTestId("settings-platform");
    expect(within(section).getByText("Platform configuration")).toBeInTheDocument();
    expect(
      within(section).getByTestId("settings-platform-value-app_name"),
    ).toHaveTextContent("NubeRush API");
    expect(
      within(section).getByTestId("settings-platform-value-app_env"),
    ).toHaveTextContent("production");
    expect(
      within(section).getByTestId("settings-platform-value-version"),
    ).toHaveTextContent("0.1.0");
    expect(
      within(section).getByTestId("settings-platform-value-app_debug"),
    ).toHaveTextContent("Disabled");
    expect(
      within(section).getByTestId(
        "settings-platform-value-default_store_timezone",
      ),
    ).toHaveTextContent("America/New_York");
  });

  it("formats commission rate from basis points and shows the delivered gross verbatim", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    const section = screen.getByTestId("settings-billing");
    expect(
      within(section).getByTestId("settings-billing-value-commission_rate"),
    ).toHaveTextContent("5.00 %");
    expect(
      within(section).getByText("5.00% platform commission"),
    ).toBeInTheDocument();
    expect(
      within(section).getByTestId(
        "settings-billing-value-delivered_orders_count",
      ),
    ).toHaveTextContent("1,234");
    expect(
      within(section).getByTestId(
        "settings-billing-value-delivered_orders_total",
      ),
    ).toHaveTextContent("98765.43 USD");
  });

  it("renders compliance counts verbatim from the backend", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    const section = screen.getByTestId("settings-compliance");
    expect(
      within(section).getByTestId("settings-compliance-value-allowed_count"),
    ).toHaveTextContent("12");
    expect(
      within(section).getByTestId(
        "settings-compliance-value-restricted_count",
      ),
    ).toHaveTextContent("3");
    expect(
      within(section).getByTestId("settings-compliance-value-banned_count"),
    ).toHaveTextContent("1");
    expect(
      within(section).getByTestId("settings-compliance-value-blocked_count"),
    ).toHaveTextContent("5");
  });

  it("renders every open order status from the backend list", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    const list = screen.getByTestId("settings-operations-open-statuses");
    for (const expected of [
      "pending",
      "accepted",
      "preparing",
      "ready",
      "out_for_delivery",
    ]) {
      expect(within(list).getByText(expected)).toBeInTheDocument();
    }
  });

  it("renders every notification event type from the backend list", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    const list = screen.getByTestId("settings-notifications-event-types");
    expect(within(list).getByText("order.created")).toBeInTheDocument();
    expect(within(list).getByText("order.delivered")).toBeInTheDocument();
  });

  it("renders admin user counts and preference defaults", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    const section = screen.getByTestId("settings-admin-preferences");
    expect(
      within(section).getByTestId(
        "settings-admin-preferences-value-admin_total",
      ),
    ).toHaveTextContent("4");
    expect(
      within(section).getByTestId(
        "settings-admin-preferences-value-admin_active",
      ),
    ).toHaveTextContent("3");
    expect(
      within(section).getByTestId(
        "settings-admin-preferences-value-default_locale",
      ),
    ).toHaveTextContent("en-US");
  });

  it("renders the editable form and keeps every read-only section present", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    // Editable surface present (F2.27.10).
    expect(screen.getByTestId("admin-settings-form")).toBeInTheDocument();
    expect(screen.getByTestId("settings-editable")).toBeInTheDocument();
    expect(screen.getByTestId("admin-settings-submit")).toBeInTheDocument();
    // Every existing read-only section is still rendered.
    for (const testId of [
      "settings-platform",
      "settings-billing",
      "settings-compliance",
      "settings-operations",
      "settings-notifications",
      "settings-admin-preferences",
    ]) {
      expect(screen.getByTestId(testId)).toBeInTheDocument();
    }
  });

  it("read-only sections contain no inputs (only the editable card has them)", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    for (const testId of [
      "settings-platform",
      "settings-billing",
      "settings-compliance",
      "settings-operations",
      "settings-notifications",
      "settings-admin-preferences",
    ]) {
      const section = screen.getByTestId(testId);
      expect(within(section).queryByRole("textbox")).toBeNull();
    }
  });

  it("seeds the editable inputs from the backend snapshot", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSettings({
          editable: {
            platform_name: "Acme Co",
            support_email: "ops@example.com",
            default_locale: "es-MX",
            default_timezone: "America/Chicago",
          },
        }),
      }),
    );

    render(<AdminSettingsPage />);
    expect(screen.getByTestId("admin-settings-platform-name")).toHaveValue(
      "Acme Co",
    );
    expect(screen.getByTestId("admin-settings-support-email")).toHaveValue(
      "ops@example.com",
    );
    // Save disabled until something changes.
    expect(screen.getByTestId("admin-settings-submit")).toBeDisabled();
  });

  it("editing a field enables Save and submits only the changed fields", () => {
    const mutate = vi.fn();
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );
    vi.mocked(
      adminSettingsHooks.useUpdateAdminSettingsMutation,
    ).mockReturnValue(asMutationResult({ mutate }) as never);

    render(<AdminSettingsPage />);
    const submit = screen.getByTestId("admin-settings-submit");
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByTestId("admin-settings-platform-name"), {
      target: { value: "Renamed Platform" },
    });
    expect(submit).toBeEnabled();

    fireEvent.click(submit);
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate).toHaveBeenCalledWith({ platform_name: "Renamed Platform" });
  });

  it("blocks Save when a local validation rule fails", () => {
    const mutate = vi.fn();
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );
    vi.mocked(
      adminSettingsHooks.useUpdateAdminSettingsMutation,
    ).mockReturnValue(asMutationResult({ mutate }) as never);

    render(<AdminSettingsPage />);
    // Invalid email blocks submission.
    fireEvent.change(screen.getByTestId("admin-settings-support-email"), {
      target: { value: "not-an-email" },
    });
    expect(screen.getByTestId("admin-settings-submit")).toBeDisabled();
    expect(mutate).not.toHaveBeenCalled();
  });

  it("surfaces a mutation API error in the form", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );
    vi.mocked(
      adminSettingsHooks.useUpdateAdminSettingsMutation,
    ).mockReturnValue(
      asMutationResult({
        isError: true,
        error: new Error("422 Unprocessable Entity"),
      }) as never,
    );

    render(<AdminSettingsPage />);
    expect(screen.getByTestId("admin-settings-form-error")).toHaveTextContent(
      "422 Unprocessable Entity",
    );
  });

  it("renders without an AuthProvider, StoreProvider, or router in the tree", () => {
    // Architecture guard: if the page accidentally pulled in
    // useAuth / useStoreContext / useParams / useLocation, rendering
    // here would throw. We assert it does not.
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );
    render(<AdminSettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Admin Settings" }),
    ).toBeInTheDocument();
  });
});
