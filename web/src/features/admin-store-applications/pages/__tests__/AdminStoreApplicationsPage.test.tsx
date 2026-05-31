// F2.24.C7: tests for AdminStoreApplicationsPage (the queue list).
//
// Stubs `../../hooks` so the page renders mocked query results without
// TanStack Query, the API layer or the network. Rendered through a
// MemoryRouter so detail-route Links resolve.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminStoreApplicationsPage from "../AdminStoreApplicationsPage";
import * as hooks from "../../hooks";
import type {
  StoreApplicationListItem,
  StoreApplicationListResponse,
} from "../../types";

vi.mock("../../hooks", () => ({
  useAdminStoreApplicationsQuery: vi.fn(),
}));

const APP_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const APP_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

function makeItem(
  overrides: Partial<StoreApplicationListItem> = {},
): StoreApplicationListItem {
  return {
    id: APP_A,
    business_name: "Acme Vapor Co",
    business_type: "Smoke shop",
    owner_full_name: "Ada Lovelace",
    owner_email: "ada@example.com",
    status: "pending_review",
    location_count: 2,
    estimated_weekly_orders: 120,
    city: "Brooklyn",
    state: "NY",
    submitted_at: "2026-05-01T12:00:00Z",
    reviewed_at: null,
    created_at: "2026-05-01T11:00:00Z",
    ...overrides,
  };
}

function asQueryResult(
  partial: Partial<UseQueryResult<StoreApplicationListResponse>>,
): UseQueryResult<StoreApplicationListResponse> {
  return partial as UseQueryResult<StoreApplicationListResponse>;
}

function setQuery(
  partial: Partial<UseQueryResult<StoreApplicationListResponse>>,
) {
  vi.mocked(hooks.useAdminStoreApplicationsQuery).mockReturnValue(
    asQueryResult(partial),
  );
}

function withRouter(node: ReactNode) {
  return (
    <MemoryRouter initialEntries={["/app/admin/applications"]}>
      {node}
    </MemoryRouter>
  );
}

function successData(
  items: StoreApplicationListItem[],
  total = items.length,
): StoreApplicationListResponse {
  return { items, total, limit: 25, offset: 0 };
}

beforeEach(() => {
  vi.mocked(hooks.useAdminStoreApplicationsQuery).mockReset();
  setQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: successData([]),
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminStoreApplicationsPage — chrome", () => {
  it("renders the heading and description", () => {
    render(withRouter(<AdminStoreApplicationsPage />));
    expect(
      screen.getByRole("heading", { level: 1, name: "Store applications" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/merchant onboarding applications/i),
    ).toBeInTheDocument();
  });

  it("calls the query with default pagination filters", () => {
    render(withRouter(<AdminStoreApplicationsPage />));
    const lastCall = vi
      .mocked(hooks.useAdminStoreApplicationsQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ limit: 25, offset: 0 });
  });
});

describe("AdminStoreApplicationsPage — states", () => {
  it("renders the loading state", () => {
    setQuery({ isLoading: true, isError: false, isSuccess: false });
    render(withRouter(<AdminStoreApplicationsPage />));
    expect(screen.getByText(/loading applications/i)).toBeInTheDocument();
  });

  it("renders the error state", () => {
    setQuery({
      isLoading: false,
      isError: true,
      isSuccess: false,
      error: new Error("down"),
      refetch: vi.fn() as never,
    });
    render(withRouter(<AdminStoreApplicationsPage />));
    expect(
      screen.getByText("Could not load applications"),
    ).toBeInTheDocument();
  });

  it("renders the empty state", () => {
    setQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: successData([]),
    });
    render(withRouter(<AdminStoreApplicationsPage />));
    expect(screen.getByText("No applications found")).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-applications-pagination"),
    ).not.toBeInTheDocument();
  });

  it("renders application rows and a mobile card representation", () => {
    setQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: successData([makeItem({ id: APP_A }), makeItem({ id: APP_B })], 2),
    });
    render(withRouter(<AdminStoreApplicationsPage />));
    expect(screen.getAllByTestId("store-application-row")).toHaveLength(2);
    expect(screen.getAllByTestId("store-application-card")).toHaveLength(2);
  });

  it("links a row to its detail page", () => {
    setQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: successData([makeItem({ id: APP_A })], 1),
    });
    render(withRouter(<AdminStoreApplicationsPage />));
    expect(
      screen.getByTestId("store-application-review-link"),
    ).toHaveAttribute("href", `/app/admin/applications/${APP_A}`);
  });
});

describe("AdminStoreApplicationsPage — filters & pagination", () => {
  it("selecting a status calls the query with that status", () => {
    render(withRouter(<AdminStoreApplicationsPage />));
    fireEvent.change(
      screen.getByTestId("store-applications-status-native"),
      { target: { value: "approved" } },
    );
    const lastCall = vi
      .mocked(hooks.useAdminStoreApplicationsQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ status: "approved", offset: 0 });
  });

  it("clicking Next advances the offset", () => {
    setQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: { items: [makeItem()], total: 100, limit: 25, offset: 0 },
    });
    render(withRouter(<AdminStoreApplicationsPage />));
    fireEvent.click(screen.getByTestId("store-applications-pagination-next"));
    const lastCall = vi
      .mocked(hooks.useAdminStoreApplicationsQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]?.offset).toBe(25);
  });

  it("renders the total count when there are items", () => {
    setQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: { items: [makeItem()], total: 42, limit: 25, offset: 0 },
    });
    render(withRouter(<AdminStoreApplicationsPage />));
    expect(
      within(screen.getByTestId("store-applications-total")).getByText(
        /42/,
      ),
    ).toBeInTheDocument();
  });
});
