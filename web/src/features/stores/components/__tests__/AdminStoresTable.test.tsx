// F2.18.3: tests for AdminStoresTable.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { AdminStoresTable } from "../AdminStoresTable";
import type { StoreProfile } from "../../types";

function makeStore(overrides: Partial<StoreProfile> = {}): StoreProfile {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Acme",
    code: "ACME",
    is_active: true,
    timezone: "America/New_York",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    ...overrides,
  };
}

function withRouter(node: ReactNode) {
  return <MemoryRouter>{node}</MemoryRouter>;
}

describe("AdminStoresTable", () => {
  it("renders LoadingState when isLoading is true", () => {
    render(withRouter(<AdminStoresTable stores={[]} isLoading />));
    expect(screen.getByText(/loading stores/i)).toBeInTheDocument();
  });

  it("renders ErrorState with retry when error is set", () => {
    const retry = vi.fn();
    render(
      withRouter(
        <AdminStoresTable
          stores={[]}
          error={new Error("boom")}
          onRetry={retry}
        />,
      ),
    );
    expect(screen.getByText("Could not load stores")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalled();
  });

  it("renders EmptyState when stores list is empty", () => {
    render(withRouter(<AdminStoresTable stores={[]} />));
    expect(screen.getByText("No stores found")).toBeInTheDocument();
  });

  it("renders one row per store with name/code/timezone columns", () => {
    const stores = [
      makeStore({ id: "a", name: "Acme", code: "ACME" }),
      makeStore({ id: "b", name: "Bravo", code: "BRAVO" }),
    ];
    render(withRouter(<AdminStoresTable stores={stores} />));
    const rows = screen.getAllByTestId("admin-stores-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Acme")).toBeInTheDocument();
    expect(within(rows[0]).getByText("ACME")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Bravo")).toBeInTheDocument();
  });

  it("each row name is a Link to /app/admin/stores/:id", () => {
    render(
      withRouter(
        <AdminStoresTable
          stores={[makeStore({ id: "store-1" })]}
        />,
      ),
    );
    const link = screen.getByTestId("admin-stores-row-link");
    expect(link).toHaveAttribute("href", "/app/admin/stores/store-1");
  });

  it("renders an actions column only when an `actions` prop is provided", () => {
    render(
      withRouter(
        <AdminStoresTable
          stores={[makeStore()]}
          actions={(store) => (
            <button data-testid="row-action">act-{store.id}</button>
          )}
        />,
      ),
    );
    expect(screen.getByTestId("row-action")).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-stores-row-actions"),
    ).toBeInTheDocument();
  });

  it("status badge reflects is_active", () => {
    const { rerender } = render(
      withRouter(
        <AdminStoresTable stores={[makeStore({ is_active: true })]} />,
      ),
    );
    expect(screen.getByTestId("store-status-active")).toBeInTheDocument();

    rerender(
      withRouter(
        <AdminStoresTable stores={[makeStore({ is_active: false })]} />,
      ),
    );
    expect(screen.getByTestId("store-status-inactive")).toBeInTheDocument();
  });
});
