// F2.11-M2.1: tests for InventoryPage.
//
// InventoryPage is a thin page shell over store context + the backend
// inventory list query. These tests validate render branches, query
// arguments, filter/pagination state, and row-action mounting only.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import * as auth from "@/auth";
import InventoryPage from "../InventoryPage";
import * as inventoryHooks from "../../hooks";
import type { InventoryItem, InventoryListResponse } from "../../types";

vi.mock("@/auth", () => ({
  useStoreContext: vi.fn(),
}));

vi.mock("../../hooks", () => ({
  useInventoryList: vi.fn(),
}));

vi.mock("../../components/InventoryActions", () => ({
  InventoryActions: ({ item }: { item: InventoryItem }) => (
    <button
      type="button"
      data-testid="mock-inventory-actions"
      data-item-id={item.id}
    >
      Actions for {item.variant.product.name}
    </button>
  ),
}));

const STORE_ID = "22222222-2222-2222-2222-222222222222";
const ITEM_ID = "11111111-1111-1111-1111-111111111111";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const PRODUCT_ID = "44444444-4444-4444-4444-444444444444";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeItem(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    id: ITEM_ID,
    store_id: STORE_ID,
    variant_id: VARIANT_ID,
    quantity_on_hand: 41,
    quantity_reserved: 7,
    reorder_threshold: 12,
    status: "available",
    last_counted_at: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    variant: {
      id: VARIANT_ID,
      sku: "GUM-MIX-10",
      flavor: null,
      size_label: null,
      is_active: true,
      product: {
        id: PRODUCT_ID,
        name: "Cosmic Gummies",
        brand: null,
        category: "edibles",
        compliance_status: "allowed",
        allowed_for_sale: true,
        is_active: true,
      },
    },
    ...overrides,
  };
}

function makeListResponse(
  overrides: Partial<InventoryListResponse> = {},
): InventoryListResponse {
  return {
    items: [],
    total: 0,
    limit: 20,
    offset: 0,
    ...overrides,
  };
}

function mockStore(currentStoreId: string | null = STORE_ID) {
  vi.mocked(auth.useStoreContext).mockReturnValue({
    currentStoreId,
  } as ReturnType<typeof auth.useStoreContext>);
}

function mockInventoryQuery(
  partial: Partial<UseQueryResult<InventoryListResponse>>,
) {
  vi.mocked(inventoryHooks.useInventoryList).mockReturnValue(
    asQueryResult<InventoryListResponse>(partial),
  );
}

beforeEach(() => {
  vi.mocked(auth.useStoreContext).mockReset();
  vi.mocked(inventoryHooks.useInventoryList).mockReset();
  mockStore();
  mockInventoryQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: makeListResponse(),
    error: null,
    refetch: vi.fn() as never,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("InventoryPage - store context", () => {
  it("renders the no-store empty state without table, filters, or pagination", () => {
    mockStore(null);
    mockInventoryQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    render(<InventoryPage />);

    expect(screen.getByText(/no store selected/i)).toBeInTheDocument();
    expect(
      screen.getByText(/inventory operates inside a store context/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByLabelText(/low stock only/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /previous/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /next/i })).toBeNull();
  });
});

describe("InventoryPage - render states", () => {
  it("renders loading state and disables the low-stock checkbox while loading", () => {
    mockInventoryQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    render(<InventoryPage />);

    expect(screen.getByRole("status")).toHaveTextContent(/loading inventory/i);
    expect(screen.getByLabelText(/low stock only/i)).toBeDisabled();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders backend ApiError detail and wires Retry to query.refetch", () => {
    const refetch = vi.fn();
    mockInventoryQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError({
        status: 500,
        message: "inventory backend exploded",
      }),
      refetch: refetch as never,
    });

    render(<InventoryPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      /inventory failed to load/i,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      /inventory backend exploded/i,
    );

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the normal empty state when the backend returns no items", () => {
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [], total: 0 }),
      error: null,
    });

    render(<InventoryPage />);

    expect(screen.getByText(/no inventory yet/i)).toBeInTheDocument();
    expect(
      screen.getByText(/this store has no inventory items yet/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders the low-stock empty copy after the low-stock filter is checked", () => {
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [], total: 0 }),
      error: null,
    });

    render(<InventoryPage />);
    fireEvent.click(screen.getByLabelText(/low stock only/i));

    expect(screen.getByText(/no low-stock items/i)).toBeInTheDocument();
    expect(
      screen.getByText(/no items are currently below their reorder threshold/i),
    ).toBeInTheDocument();
  });

  it("renders backend total, backend row fields verbatim, and one row action per item", () => {
    const first = makeItem();
    const second = makeItem({
      id: "55555555-5555-5555-5555-555555555555",
      variant_id: "66666666-6666-6666-6666-666666666666",
      quantity_on_hand: 3,
      quantity_reserved: 1,
      reorder_threshold: 9,
      status: "flagged",
      variant: {
        id: "66666666-6666-6666-6666-666666666666",
        sku: "VAPE-BERRY-1G",
        flavor: "Berry",
        size_label: "1g",
        is_active: true,
        product: {
          id: "77777777-7777-7777-7777-777777777777",
          name: "Nebula Vape",
          brand: "Cloud Co.",
          category: "vapes",
          compliance_status: "restricted",
          allowed_for_sale: true,
          is_active: true,
        },
      },
    });
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [first, second], total: 42 }),
      error: null,
    });

    render(<InventoryPage />);

    expect(screen.getByTestId("inventory-total")).toHaveTextContent("Total: 42");
    expect(screen.queryByRole("searchbox")).toBeNull();

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);

    expect(within(rows[0]).getByText("Cosmic Gummies")).toBeInTheDocument();
    expect(within(rows[0]).getByText("GUM-MIX-10")).toBeInTheDocument();
    expect(within(rows[0]).getByText("41")).toBeInTheDocument();
    expect(within(rows[0]).getByText("7")).toBeInTheDocument();
    expect(within(rows[0]).getByText("12")).toBeInTheDocument();
    expect(within(rows[0]).getByText("available")).toBeInTheDocument();

    expect(within(rows[1]).getByText("Nebula Vape")).toBeInTheDocument();
    expect(within(rows[1]).getByText("VAPE-BERRY-1G")).toBeInTheDocument();
    expect(within(rows[1]).getByText("3")).toBeInTheDocument();
    expect(within(rows[1]).getByText("1")).toBeInTheDocument();
    expect(within(rows[1]).getByText("9")).toBeInTheDocument();
    expect(within(rows[1]).getByText("flagged")).toBeInTheDocument();

    const actions = screen.getAllByTestId("mock-inventory-actions");
    expect(actions).toHaveLength(2);
    expect(actions[0]).toHaveAttribute("data-item-id", first.id);
    expect(actions[1]).toHaveAttribute("data-item-id", second.id);
  });
});

describe("InventoryPage - filters", () => {
  it("calls useInventoryList with the default backend-query params", () => {
    render(<InventoryPage />);

    expect(inventoryHooks.useInventoryList).toHaveBeenCalledWith({
      limit: 20,
      offset: 0,
      low_stock_only: false,
    });
  });

  it("sends low_stock_only=true when the low-stock checkbox is checked", () => {
    render(<InventoryPage />);

    fireEvent.click(screen.getByLabelText(/low stock only/i));

    expect(inventoryHooks.useInventoryList).toHaveBeenLastCalledWith({
      limit: 20,
      offset: 0,
      low_stock_only: true,
    });
  });

  it("resets offset to 0 when the low-stock filter changes", () => {
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [makeItem()], total: 45 }),
      error: null,
    });
    render(<InventoryPage />);

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(inventoryHooks.useInventoryList).toHaveBeenLastCalledWith({
      limit: 20,
      offset: 20,
      low_stock_only: false,
    });

    fireEvent.click(screen.getByLabelText(/low stock only/i));
    expect(inventoryHooks.useInventoryList).toHaveBeenLastCalledWith({
      limit: 20,
      offset: 0,
      low_stock_only: true,
    });
  });
});

describe("InventoryPage - pagination", () => {
  it("uses backend total to enable/disable Previous and Next while paging", () => {
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [makeItem()], total: 35 }),
      error: null,
    });
    render(<InventoryPage />);

    const previous = screen.getByRole("button", { name: /previous/i });
    const next = screen.getByRole("button", { name: /next/i });

    expect(previous).toBeDisabled();
    expect(next).not.toBeDisabled();

    fireEvent.click(next);
    expect(inventoryHooks.useInventoryList).toHaveBeenLastCalledWith({
      limit: 20,
      offset: 20,
      low_stock_only: false,
    });
    expect(previous).not.toBeDisabled();
    expect(next).toBeDisabled();

    fireEvent.click(previous);
    expect(inventoryHooks.useInventoryList).toHaveBeenLastCalledWith({
      limit: 20,
      offset: 0,
      low_stock_only: false,
    });
    expect(previous).toBeDisabled();
    expect(next).not.toBeDisabled();
  });
});

describe("InventoryPage - architecture", () => {
  it("does NOT import useAuth / currentUser / role checks / permission helpers / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "InventoryPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\buser\.role\b/);
    expect(code).not.toMatch(/\brole\s*===/);
    expect(code).not.toMatch(/\bcanView\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT recompute stock authority or make local low-stock decisions", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "InventoryPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/quantity_on_hand\s*-\s*quantity_reserved/);
    expect(code).not.toMatch(/quantity_reserved\s*[-+*/]/);
    expect(code).not.toMatch(/\bquantity_available\b/);
    expect(code).not.toMatch(/quantity_on_hand\s*<=\s*reorder_threshold/);
    expect(code).not.toMatch(/quantity_available\s*<=\s*reorder_threshold/);
  });

  it("does NOT sort, filter, reduce, or aggregate backend inventory rows client-side", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "InventoryPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/items\s*\.\s*sort\s*\(/);
    expect(code).not.toMatch(/items\s*\.\s*filter\s*\(/);
    expect(code).not.toMatch(/items\s*\.\s*reduce\s*\(/);
    expect(code).not.toMatch(/\baggregate\s*\(/);
  });
});
