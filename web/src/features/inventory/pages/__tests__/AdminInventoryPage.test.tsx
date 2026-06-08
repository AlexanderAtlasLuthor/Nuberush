// F2.18.5: tests for the real Admin Inventory page.
//
// Stub the inventory hooks so we can drive every query state without
// TanStack Query or the API. Render through plain `render` — the
// admin page does NOT use react-router-dom hooks (no useParams, no
// useLocation), and does NOT use useStoreContext (verified by the
// architecture-guard test below).
//
// Coverage:
//   - Page header copy (admin-scoped, no "this store" language).
//   - Default filters {limit: 100, offset: 0}.
//   - Loading / error / empty / data states surfaced via the table.
//   - Retry calls query.refetch.
//   - Each AdminInventoryFilters field feeds back into the next
//     useAdminInventoryQuery invocation with the right snapshot.
//   - Empty/whitespace string filters are dropped.
//   - Pagination bounds + advance.
//   - Read-only enforcement: no mutation buttons rendered.
//   - Architecture guards: no useAuth / useStoreContext /
//     getInventoryList / useInventoryList / fetch / axios.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminInventoryPage from "../AdminInventoryPage";
import * as inventoryHooks from "../../hooks";
import * as storesHooks from "@/features/stores/hooks";
import type { StoreListResponse } from "@/features/stores/types";
import type {
  AdminInventoryFilters,
  InventoryItem,
  InventoryListResponse,
  ProductSummary,
  VariantSummary,
} from "../../types";

vi.mock("../../hooks", () => ({
  useAdminInventoryQuery: vi.fn(),
  useInventoryList: vi.fn(),
  useInventoryItem: vi.fn(),
  useInventoryItemLogs: vi.fn(),
  useReceiveStockMutation: vi.fn(),
  useAdjustStockMutation: vi.fn(),
  useDamageStockMutation: vi.fn(),
  useUpdateInventoryThresholdMutation: vi.fn(),
  useUpdateInventoryStatusMutation: vi.fn(),
  inventoryKeys: { all: ["inventory"] as const },
}));

// The page now hosts <AdminInventoryImport>, which calls
// useAdminStoresQuery to populate its store picker. Stub it so the page
// renders without a QueryClient. The launcher's own behaviour (picking a
// store, opening the dialog) is covered in AdminInventoryImport.test.tsx.
vi.mock("@/features/stores/hooks", () => ({
  useAdminStoresQuery: vi.fn(),
}));

const STORE_A_ID = "11111111-1111-1111-1111-111111111111";
const PRODUCT_ID = "22222222-2222-2222-2222-222222222222";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return {
    refetch: vi.fn(),
    ...partial,
  } as unknown as UseQueryResult<TData>;
}

function makeProduct(overrides: Partial<ProductSummary> = {}): ProductSummary {
  return {
    id: PRODUCT_ID,
    name: "Test Product",
    ...overrides,
  } as ProductSummary;
}

function makeVariant(overrides: Partial<VariantSummary> = {}): VariantSummary {
  return {
    id: VARIANT_ID,
    sku: "SKU-1",
    flavor: null,
    size_label: null,
    is_active: true,
    product: makeProduct(),
    ...overrides,
  };
}

function makeItem(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    id: "item-1",
    store_id: STORE_A_ID,
    variant_id: VARIANT_ID,
    quantity_on_hand: 12,
    quantity_reserved: 3,
    reorder_threshold: 5,
    status: "available",
    last_counted_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    variant: makeVariant(),
    ...overrides,
  };
}

function makeListResponse(
  items: InventoryItem[],
  overrides: Partial<InventoryListResponse> = {},
): InventoryListResponse {
  return {
    items,
    total: items.length,
    limit: 100,
    offset: 0,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReset();
  vi.mocked(storesHooks.useAdminStoresQuery).mockReturnValue(
    asQueryResult<StoreListResponse>({
      isLoading: false,
      isFetching: false,
      isError: false,
      isSuccess: true,
      data: { items: [], total: 0, limit: 100, offset: 0 },
    }),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Chrome
// --------------------------------------------------------------------- //

describe("AdminInventoryPage — chrome", () => {
  beforeEach(() => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
  });

  it("renders the page heading 'Inventory'", () => {
    render(<AdminInventoryPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Inventory" }),
    ).toBeInTheDocument();
  });

  it("renders the admin-scope description (no 'this store' language)", () => {
    render(<AdminInventoryPage />);
    expect(
      screen.getByText(
        /Stock levels across every store in the NubeRush platform\./,
      ),
    ).toBeInTheDocument();
  });

  it("calls useAdminInventoryQuery with default filters {limit: 100, offset: 0}", () => {
    render(<AdminInventoryPage />);
    const lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ limit: 100, offset: 0 });
  });

  it("renders the admin inventory import launcher (F2.27.9)", () => {
    render(<AdminInventoryPage />);
    expect(
      screen.getByTestId("admin-inventory-import"),
    ).toBeInTheDocument();
    // Nothing selected yet → import button is disabled.
    expect(
      screen.getByTestId("admin-inventory-import-open"),
    ).toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Query states
// --------------------------------------------------------------------- //

describe("AdminInventoryPage — query states", () => {
  it("renders the loading state", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: true,
        isFetching: true,
        isError: false,
        isSuccess: false,
      }),
    );
    render(<AdminInventoryPage />);
    expect(screen.getByText(/loading inventory/i)).toBeInTheDocument();
  });

  it("renders the error state and retry", () => {
    const refetch = vi.fn();
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: true,
        isSuccess: false,
        error: new Error("forbidden"),
        refetch: refetch as never,
      }),
    );
    render(<AdminInventoryPage />);
    expect(
      screen.getByText("Could not load inventory"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("renders the empty state when items is empty", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
    render(<AdminInventoryPage />);
    expect(screen.getByText("No inventory found")).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-inventory-pagination"),
    ).not.toBeInTheDocument();
  });

  it("renders rows when items is non-empty", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeItem({ id: "x" })], { total: 1 }),
      }),
    );
    render(<AdminInventoryPage />);
    expect(screen.getByTestId("admin-inventory-row")).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-inventory-row-product"),
    ).toHaveTextContent("Test Product");
    expect(
      screen.getByTestId("admin-inventory-row-sku"),
    ).toHaveTextContent("SKU-1");
  });

  it("renders the total count when there are items", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeItem()], { total: 137 }),
      }),
    );
    render(<AdminInventoryPage />);
    expect(screen.getByTestId("admin-inventory-total")).toHaveTextContent(
      "Total: 137",
    );
  });
});

// --------------------------------------------------------------------- //
// Filters
// --------------------------------------------------------------------- //

describe("AdminInventoryPage — filters", () => {
  beforeEach(() => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
  });

  it("typing store_id forwards the value", () => {
    render(<AdminInventoryPage />);
    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-store-id"),
      { target: { value: STORE_A_ID } },
    );
    const lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ store_id: STORE_A_ID });
  });

  it("whitespace-only store_id is dropped", () => {
    render(<AdminInventoryPage />);
    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-store-id"),
      { target: { value: "   " } },
    );
    const lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(
      (lastCall?.[0] as AdminInventoryFilters | undefined)?.store_id,
    ).toBeUndefined();
  });

  it("typing q forwards trimmed text", () => {
    render(<AdminInventoryPage />);
    fireEvent.change(screen.getByTestId("admin-inventory-filter-q"), {
      target: { value: "  beanies  " },
    });
    const lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ q: "beanies" });
  });

  it("clearing q drops the key", () => {
    render(<AdminInventoryPage />);
    fireEvent.change(screen.getByTestId("admin-inventory-filter-q"), {
      target: { value: "x" },
    });
    fireEvent.change(screen.getByTestId("admin-inventory-filter-q"), {
      target: { value: "" },
    });
    const lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(
      (lastCall?.[0] as AdminInventoryFilters | undefined)?.q,
    ).toBeUndefined();
  });

  it("typing product_id and variant_id forwards both", () => {
    render(<AdminInventoryPage />);
    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-product-id"),
      { target: { value: PRODUCT_ID } },
    );
    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-variant-id"),
      { target: { value: VARIANT_ID } },
    );
    const lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({
      product_id: PRODUCT_ID,
      variant_id: VARIANT_ID,
    });
  });

  it("checking Low stock only sets low_stock=true; unchecking drops the key", () => {
    render(<AdminInventoryPage />);
    fireEvent.click(
      screen.getByTestId("admin-inventory-filter-low-stock"),
    );
    let lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ low_stock: true });

    fireEvent.click(
      screen.getByTestId("admin-inventory-filter-low-stock"),
    );
    lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(
      (lastCall?.[0] as AdminInventoryFilters | undefined)?.low_stock,
    ).toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// Pagination
// --------------------------------------------------------------------- //

describe("AdminInventoryPage — pagination", () => {
  it("Previous disabled at first page; Next enabled when more rows", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeItem()], { total: 300, limit: 100, offset: 0 }),
      }),
    );
    render(<AdminInventoryPage />);
    expect(
      screen.getByTestId("admin-inventory-pagination-prev"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("admin-inventory-pagination-next"),
    ).not.toBeDisabled();
  });

  it("Next is disabled on the last page", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeItem()], { total: 100, limit: 100, offset: 0 }),
      }),
    );
    render(<AdminInventoryPage />);
    expect(
      screen.getByTestId("admin-inventory-pagination-next"),
    ).toBeDisabled();
  });

  it("clicking Next advances offset by limit", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeItem()], { total: 300, limit: 100, offset: 0 }),
      }),
    );
    render(<AdminInventoryPage />);
    fireEvent.click(
      screen.getByTestId("admin-inventory-pagination-next"),
    );
    const lastCall = vi
      .mocked(inventoryHooks.useAdminInventoryQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]?.offset).toBe(100);
  });
});

// --------------------------------------------------------------------- //
// Read-only enforcement
// --------------------------------------------------------------------- //

describe("AdminInventoryPage — read-only", () => {
  it("renders no mutation buttons", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeItem()], { total: 1 }),
      }),
    );
    render(<AdminInventoryPage />);
    // None of the store-scoped mutation labels should appear here.
    for (const label of [
      /receive/i,
      /adjust/i,
      /damage/i,
      /threshold/i,
      /update status/i,
      /reserve/i,
      /release/i,
    ]) {
      expect(screen.queryByRole("button", { name: label })).toBeNull();
    }
  });

  it("does not invoke any store-scoped inventory mutation hook", () => {
    vi.mocked(inventoryHooks.useAdminInventoryQuery).mockReturnValue(
      asQueryResult<InventoryListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
    render(<AdminInventoryPage />);
    expect(inventoryHooks.useReceiveStockMutation).not.toHaveBeenCalled();
    expect(inventoryHooks.useAdjustStockMutation).not.toHaveBeenCalled();
    expect(inventoryHooks.useDamageStockMutation).not.toHaveBeenCalled();
    expect(
      inventoryHooks.useUpdateInventoryThresholdMutation,
    ).not.toHaveBeenCalled();
    expect(
      inventoryHooks.useUpdateInventoryStatusMutation,
    ).not.toHaveBeenCalled();
    expect(inventoryHooks.useInventoryList).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminInventoryPage — architecture", () => {
  it("does NOT import useAuth / useStoreContext / store-scoped hooks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AdminInventoryPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\buseStoreContext\b/);
    expect(code).not.toMatch(/\buseInventoryList\b/);
    expect(code).not.toMatch(/\bgetInventoryList\b/);
    expect(code).not.toMatch(/\bgetAdminInventory\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\.role\s*===\s*["']/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
    expect(code).not.toMatch(/apiRequest/);
  });
});
