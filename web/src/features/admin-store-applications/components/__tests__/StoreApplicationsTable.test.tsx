// F2.24.C7: tests for StoreApplicationsTable (desktop table + mobile
// cards + loading/error/empty delegation).

import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { StoreApplicationsTable } from "../StoreApplicationsTable";
import type { StoreApplicationListItem } from "../../types";

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

function withRouter(node: ReactNode) {
  return <MemoryRouter>{node}</MemoryRouter>;
}

describe("StoreApplicationsTable", () => {
  it("renders the loading state", () => {
    render(withRouter(<StoreApplicationsTable applications={[]} isLoading />));
    expect(screen.getByText(/loading applications/i)).toBeInTheDocument();
  });

  it("renders the error state with retry", () => {
    const retry = vi.fn();
    render(
      withRouter(
        <StoreApplicationsTable
          applications={[]}
          error={new Error("boom")}
          onRetry={retry}
        />,
      ),
    );
    expect(
      screen.getByText("Could not load applications"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalled();
  });

  it("renders the empty state", () => {
    render(withRouter(<StoreApplicationsTable applications={[]} />));
    expect(screen.getByText("No applications found")).toBeInTheDocument();
  });

  it("renders one desktop row per application", () => {
    const items = [
      makeItem({ id: APP_A, business_name: "Acme" }),
      makeItem({ id: APP_B, business_name: "Bravo" }),
    ];
    render(withRouter(<StoreApplicationsTable applications={items} />));
    const rows = screen.getAllByTestId("store-application-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Acme")).toBeInTheDocument();
  });

  it("links each row to the detail route", () => {
    render(
      withRouter(
        <StoreApplicationsTable applications={[makeItem({ id: APP_A })]} />,
      ),
    );
    expect(
      screen.getByTestId("store-application-review-link"),
    ).toHaveAttribute("href", `/app/admin/applications/${APP_A}`);
  });

  it("renders a mobile card representation", () => {
    const items = [
      makeItem({ id: APP_A, business_name: "Acme" }),
      makeItem({ id: APP_B, business_name: "Bravo" }),
    ];
    render(withRouter(<StoreApplicationsTable applications={items} />));
    expect(
      screen.getByTestId("store-applications-cards"),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("store-application-card")).toHaveLength(2);
  });
});
