import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import * as authModule from "@/auth";

import * as hooks from "../../hooks";
import type { StoreRegulatoryAlertsResponse } from "../../types";
import StoreRegulatoryPage from "../StoreRegulatoryPage";

vi.mock("@/auth", async () => {
  const actual = await vi.importActual<typeof import("@/auth")>("@/auth");
  return {
    ...actual,
    useStoreContext: vi.fn(),
  };
});

vi.mock("../../hooks", () => ({
  useStoreRegulatoryAlertsQuery: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

const ALERT = {
  id: "22222222-2222-2222-2222-222222222222",
  notice_id: "44444444-4444-4444-4444-444444444444",
  product_id: "33333333-3333-3333-3333-333333333333",
  severity: "high" as const,
  status: "open" as const,
  recommended_action: "hold" as const,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  notice_title: "Enforcement recall",
  notice_type: "enforcement_notice" as const,
  notice_published_at: "2025-12-31T00:00:00Z",
  product_name: "Mango Vape",
};

const RESPONSE: StoreRegulatoryAlertsResponse = {
  items: [ALERT],
  total: 1,
  limit: 25,
  offset: 0,
};

function asQueryResult(
  partial: Partial<UseQueryResult<StoreRegulatoryAlertsResponse>>,
): UseQueryResult<StoreRegulatoryAlertsResponse> {
  return {
    isPending: false,
    isLoading: false,
    isFetching: false,
    isError: false,
    isSuccess: false,
    data: undefined,
    error: null,
    refetch: vi.fn(),
    ...partial,
  } as unknown as UseQueryResult<StoreRegulatoryAlertsResponse>;
}

function mockStoreContext(currentStoreId: string | null) {
  vi.mocked(authModule.useStoreContext).mockReturnValue({
    currentStoreId,
    hasStoreContext: currentStoreId !== null,
    isStoreRequired: false,
    storeError: null,
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/app/store/regulatory"]}>
      <StoreRegulatoryPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReset();
  vi.mocked(authModule.useStoreContext).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("StoreRegulatoryPage", () => {
  it("renders the page shell with a no-store message when storeId is null", () => {
    mockStoreContext(null);
    vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReturnValue(
      asQueryResult({ isPending: true, fetchStatus: "idle" } as never),
    );
    renderPage();
    expect(screen.getByTestId("store-regulatory-page")).toBeInTheDocument();
    expect(
      screen.getByTestId("store-regulatory-no-store"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-regulatory-loading"),
    ).not.toBeInTheDocument();
  });

  it("shows a loading state when storeId exists and query is pending", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReturnValue(
      asQueryResult({ isPending: true }),
    );
    renderPage();
    expect(
      screen.getByTestId("store-regulatory-loading"),
    ).toBeInTheDocument();
  });

  it("shows an error state with a working Retry button", () => {
    mockStoreContext(STORE_ID);
    const refetch = vi.fn();
    vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("nope") as unknown as Error,
        refetch,
      }),
    );
    renderPage();
    expect(screen.getByTestId("store-regulatory-error")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("store-regulatory-retry"));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("shows an empty state when the store has no alerts", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: { items: [], total: 0, limit: 25, offset: 0 },
      }),
    );
    renderPage();
    expect(screen.getByTestId("store-regulatory-empty")).toBeInTheDocument();
  });

  it("renders an alert card from API data with read-only fields", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: RESPONSE }),
    );
    renderPage();

    const list = screen.getByTestId("store-regulatory-alerts");
    const card = within(list).getByTestId("store-regulatory-alert-card");
    expect(within(card).getByText("Mango Vape")).toBeInTheDocument();
    expect(
      within(card).getByText(/Enforcement recall/),
    ).toBeInTheDocument();
    // Badges render the advisory signals.
    expect(
      within(card).getByTestId("regulatory-severity-high"),
    ).toBeInTheDocument();
    expect(
      within(card).getByTestId("regulatory-status-open"),
    ).toBeInTheDocument();
    expect(
      within(card).getByTestId("regulatory-recommended-action-hold"),
    ).toBeInTheDocument();
  });

  it("updates filter query state when a filter changes", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: RESPONSE }),
    );
    renderPage();

    fireEvent.change(screen.getByTestId("store-regulatory-filter-status"), {
      target: { value: "dismissed" },
    });

    // Latest call to the hook reflects the new filter snapshot.
    const calls = vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mock.calls;
    const lastFilters = calls[calls.length - 1][1];
    expect(lastFilters).toEqual({ status: "dismissed" });
  });

  it("renders no lifecycle action controls", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(hooks.useStoreRegulatoryAlertsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: RESPONSE }),
    );
    renderPage();

    expect(
      screen.queryByRole("button", { name: /acknowledge/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /dismiss/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /resolve/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("regulatory-action"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("regulatory-resolution"),
    ).not.toBeInTheDocument();
  });
});
