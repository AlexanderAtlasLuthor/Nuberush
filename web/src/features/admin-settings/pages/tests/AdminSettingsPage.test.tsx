// Tests for the real Admin Settings page.
//
// Stub `../../hooks` so we drive every query state without TanStack
// Query or the API. The page does not use react-router-dom hooks,
// useStoreContext, or useAuth — verified by the architecture
// assertion at the bottom of this file.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminSettingsPage from "../AdminSettingsPage";
import * as adminSettingsHooks from "../../hooks";
import type { AdminSettingsResponse } from "../../types";

vi.mock("../../hooks", () => ({
  useAdminSettingsQuery: vi.fn(),
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
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReset();
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

  it("does NOT render any mutation buttons (no Save, no Edit, no Update)", () => {
    vi.mocked(adminSettingsHooks.useAdminSettingsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSettings() }),
    );

    render(<AdminSettingsPage />);
    expect(screen.queryByRole("button", { name: /save/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /edit/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /update/i })).toBeNull();
    // No textbox / form inputs either — the page is read-only.
    expect(screen.queryByRole("textbox")).toBeNull();
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
