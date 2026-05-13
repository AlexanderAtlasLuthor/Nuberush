// F2.20.5: tests for the real Admin Products oversight page.
//
// Stub `../../hooks` so we drive every query state without TanStack
// Query or the API. The page renders <Link> elements via the
// table; wrap the harness in MemoryRouter. The page itself does NOT
// use react-router-dom hooks (no useParams, no useLocation), and
// does NOT use useStoreContext / useAuth (verified by the
// architecture assertion at the bottom).
//
// Coverage:
//   - Loading / error / empty / success states.
//   - Backend rows render verbatim with the canonical Product fields.
//   - Table columns (Product, Brand, Category, Compliance, Allowed
//     for sale, Active, Last compliance check, Updated at, Drill-down).
//   - Filters: q / category / compliance_status / allowed_for_sale /
//     is_active mutate the next useAdminProductsQuery invocation.
//   - Empty/whitespace q and category are dropped.
//   - Changing any filter resets offset to 0.
//   - Reset restores DEFAULT_FILTERS.
//   - Pagination Prev disabled at offset 0; Next disabled at end;
//     advance + retreat update offset; range text formats correctly.
//   - Filters preserved across pagination.
//   - Drill-down link points to /app/admin/products/:productId.
//   - No mutation/action buttons on the list surface.
//   - Architecture guard: no fetch, auth, store context.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminProductsPage from "../AdminProductsPage";
import * as adminProductsHooks from "../../hooks";
import type {
  AdminProductsFilters,
  AdminProductsListResponse,
  Product,
} from "../../types";

vi.mock("../../hooks", () => ({
  useAdminProductsQuery: vi.fn(),
  adminProductsQueryKeys: { all: ["admin-products"] as const },
}));

// Real Radix Select uses ResizeObserver / scrollIntoView and pointer
// events that JSDOM does not implement out of the box. Re-mock the
// Select primitives to a plain native <select> + <option> tree so
// JSDOM can drive them via fireEvent.change. The trigger is rendered
// as a sibling <span> (NOT inside the <select>) so the data-testid
// query used by the filter assertions still finds it without
// triggering DOM-nesting warnings.
vi.mock("@/components/ui/select", () => {
  const Select = ({
    value,
    onValueChange,
    children,
    disabled,
  }: {
    value?: string;
    onValueChange?: (v: string) => void;
    children?: React.ReactNode;
    disabled?: boolean;
  }) => {
    // Walk children, harvest:
    //   - `options`:    every SelectItem → <option>
    //   - `triggerProps`: the SelectTrigger's id / data-testid so we
    //                     can pin them on the actual <select>. The
    //                     trigger node itself is dropped (we render
    //                     a native <select> in its place, so the
    //                     test's `getByTestId(...trigger-id)` lands
    //                     on the controllable <select> element).
    const options: React.ReactNode[] = [];
    let triggerProps: { id?: string; testId?: string } = {};

    const visit = (node: React.ReactNode): void => {
      if (node === null || node === undefined || node === false) return;
      if (Array.isArray(node)) {
        for (const child of node) visit(child);
        return;
      }
      if (typeof node !== "object") return;
      const element = node as React.ReactElement<{
        children?: React.ReactNode;
        value?: string;
        id?: string;
        ["data-testid"]?: string;
      }>;
      const type = element.type as { __mockKind?: string } | string;
      if (typeof type !== "string" && type.__mockKind === "item") {
        options.push(
          <option key={options.length} value={element.props.value}>
            {element.props.children}
          </option>,
        );
        return;
      }
      if (typeof type !== "string" && type.__mockKind === "content") {
        visit(element.props.children);
        return;
      }
      if (typeof type !== "string" && type.__mockKind === "trigger") {
        triggerProps = {
          id: element.props.id,
          testId: element.props["data-testid"],
        };
        return;
      }
      // Anything else (e.g. SelectValue) is dropped — it's chrome
      // that the native <select> renders for us.
    };
    visit(children);

    return (
      <select
        id={triggerProps.id}
        data-testid={triggerProps.testId}
        aria-label={triggerProps.id ?? "mock select"}
        value={value}
        disabled={disabled}
        onChange={(e) => onValueChange?.(e.target.value)}
      >
        {options}
      </select>
    );
  };
  const SelectTrigger = (_props: {
    children?: React.ReactNode;
    id?: string;
    "data-testid"?: string;
  }) => null;
  (SelectTrigger as unknown as { __mockKind: string }).__mockKind =
    "trigger";

  const SelectValue = ({ placeholder: _placeholder }: { placeholder?: string }) =>
    null;

  const SelectContent = ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  );
  (SelectContent as unknown as { __mockKind: string }).__mockKind =
    "content";

  const SelectItem = ({
    value,
    children,
  }: {
    value: string;
    children?: React.ReactNode;
  }) => <option value={value}>{children}</option>;
  (SelectItem as unknown as { __mockKind: string }).__mockKind = "item";

  return {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem,
  };
});

const PRODUCT_A = "11111111-1111-1111-1111-111111111111";
const PRODUCT_B = "22222222-2222-2222-2222-222222222222";
const PRODUCT_C = "33333333-3333-3333-3333-333333333333";

function asQueryResult(
  partial: Partial<UseQueryResult<AdminProductsListResponse>>,
): UseQueryResult<AdminProductsListResponse> {
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
  } as unknown as UseQueryResult<AdminProductsListResponse>;
}

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_A,
    name: "Mango Ice",
    brand: "NubeBrand",
    category: "vape",
    description: null,
    compliance_status: "allowed",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: "2026-05-12T08:00:00Z",
    created_at: "2026-05-10T12:00:00Z",
    updated_at: "2026-05-12T08:00:00Z",
    ...overrides,
  };
}

function makeResponse(
  items: Product[],
  overrides: Partial<AdminProductsListResponse> = {},
): AdminProductsListResponse {
  return {
    items,
    total: items.length,
    limit: 50,
    offset: 0,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminProductsPage />
    </MemoryRouter>,
  );
}

function lastFilters(): AdminProductsFilters | undefined {
  const calls = vi.mocked(adminProductsHooks.useAdminProductsQuery).mock
    .calls;
  if (calls.length === 0) return undefined;
  return calls[calls.length - 1][0] as AdminProductsFilters | undefined;
}

beforeEach(() => {
  vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReset();
  vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
    asQueryResult({ isSuccess: true, data: makeResponse([]) }),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Loading / error / empty / success
// --------------------------------------------------------------------- //

describe("AdminProductsPage — loading", () => {
  it("renders the loading state", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({ isPending: true, isLoading: true }),
    );
    renderPage();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-products-table"),
    ).not.toBeInTheDocument();
  });
});

describe("AdminProductsPage — error", () => {
  it("renders an error state with retry when the query errors", () => {
    const refetch = vi.fn();
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("Admin gate failed"),
        refetch,
      }),
    );
    renderPage();
    expect(
      screen.getByRole("alert"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Admin gate failed/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("AdminProductsPage — empty", () => {
  it("renders the empty state when the query succeeds with no rows", () => {
    renderPage();
    expect(screen.getByText("No products")).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-products-table"),
    ).not.toBeInTheDocument();
  });
});

describe("AdminProductsPage — success", () => {
  it("renders one row per product with backend data", () => {
    const products = [
      makeProduct({
        id: PRODUCT_A,
        name: "Mango Ice",
        brand: "NubeBrand",
        category: "vape",
        compliance_status: "allowed",
      }),
      makeProduct({
        id: PRODUCT_B,
        name: "Strawberry Burst",
        brand: null,
        category: "edibles",
        compliance_status: "restricted",
        allowed_for_sale: false,
      }),
      makeProduct({
        id: PRODUCT_C,
        name: "Banned Item",
        brand: "BanBrand",
        category: "vape",
        compliance_status: "banned",
        allowed_for_sale: false,
        is_active: false,
        last_compliance_check: null,
      }),
    ];
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse(products),
      }),
    );

    renderPage();
    const rows = screen.getAllByTestId("admin-products-row");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveAttribute("data-product-id", PRODUCT_A);
    expect(rows[1]).toHaveAttribute("data-product-id", PRODUCT_B);
    expect(rows[2]).toHaveAttribute("data-product-id", PRODUCT_C);

    expect(
      within(rows[0]).getByTestId("admin-products-row-name"),
    ).toHaveTextContent("Mango Ice");
    expect(
      within(rows[1]).getByTestId("admin-products-row-brand"),
    ).toHaveTextContent("—");
    expect(
      within(rows[2]).getByTestId("admin-products-row-last-compliance-check"),
    ).toHaveTextContent("—");
  });

  it("renders the total count and pagination range", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()], { total: 7 }),
      }),
    );
    renderPage();
    expect(screen.getByTestId("admin-products-total")).toHaveTextContent(
      "7 products",
    );
    expect(
      screen.getByTestId("admin-products-pagination-range"),
    ).toHaveTextContent("Showing 1–1 of 7");
  });

  it("drill-down link points to /app/admin/products/:productId", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct({ id: PRODUCT_A })]),
      }),
    );
    renderPage();
    const link = screen.getByTestId("admin-products-row-drilldown");
    expect(link).toHaveAttribute("href", `/app/admin/products/${PRODUCT_A}`);
  });
});

// --------------------------------------------------------------------- //
// Filters
// --------------------------------------------------------------------- //

describe("AdminProductsPage — filters", () => {
  it("default initial filters include limit 50 / offset 0", () => {
    renderPage();
    expect(lastFilters()).toEqual({ limit: 50, offset: 0 });
  });

  it("typing in q forwards the trimmed value to the next query", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("admin-products-filter-q"), {
      target: { value: "  mango  " },
    });
    expect(lastFilters()).toEqual({ limit: 50, offset: 0, q: "mango" });
  });

  it("clearing q drops the key (no q=\"\" smuggling)", () => {
    renderPage();
    const input = screen.getByTestId("admin-products-filter-q");
    fireEvent.change(input, { target: { value: "mango" } });
    fireEvent.change(input, { target: { value: "   " } });
    const filters = lastFilters();
    expect(filters).toBeDefined();
    expect(filters?.q).toBeUndefined();
  });

  it("typing in category forwards the trimmed value", () => {
    renderPage();
    fireEvent.change(
      screen.getByTestId("admin-products-filter-category"),
      { target: { value: "  vape  " } },
    );
    expect(lastFilters()?.category).toBe("vape");
  });

  it("clearing category drops the key", () => {
    renderPage();
    const input = screen.getByTestId("admin-products-filter-category");
    fireEvent.change(input, { target: { value: "vape" } });
    fireEvent.change(input, { target: { value: "" } });
    expect(lastFilters()?.category).toBeUndefined();
  });

  it("selecting compliance_status forwards it", () => {
    renderPage();
    const trigger = screen.getByTestId(
      "admin-products-filter-compliance-trigger",
    ) as HTMLSelectElement;
    fireEvent.change(trigger, { target: { value: "restricted" } });
    expect(lastFilters()?.compliance_status).toBe("restricted");
  });

  it("selecting 'all' for compliance_status drops the key", () => {
    renderPage();
    const trigger = screen.getByTestId(
      "admin-products-filter-compliance-trigger",
    ) as HTMLSelectElement;
    fireEvent.change(trigger, { target: { value: "restricted" } });
    fireEvent.change(trigger, { target: { value: "all" } });
    expect(lastFilters()?.compliance_status).toBeUndefined();
  });

  it("selecting allowed_for_sale=false preserves the falsy boolean", () => {
    renderPage();
    const trigger = screen.getByTestId(
      "admin-products-filter-allowed-for-sale-trigger",
    ) as HTMLSelectElement;
    fireEvent.change(trigger, { target: { value: "false" } });
    expect(lastFilters()?.allowed_for_sale).toBe(false);
  });

  it("selecting is_active=false preserves the falsy boolean", () => {
    renderPage();
    const trigger = screen.getByTestId(
      "admin-products-filter-is-active-trigger",
    ) as HTMLSelectElement;
    fireEvent.change(trigger, { target: { value: "false" } });
    expect(lastFilters()?.is_active).toBe(false);
  });

  it("changing any filter resets offset to 0", () => {
    // Seed offset > 0 via pagination first.
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    fireEvent.click(
      screen.getByTestId("admin-products-pagination-next"),
    );
    expect(lastFilters()?.offset).toBe(50);

    // Now change a filter — offset must reset to 0.
    fireEvent.change(screen.getByTestId("admin-products-filter-q"), {
      target: { value: "mango" },
    });
    expect(lastFilters()?.offset).toBe(0);
  });

  it("Reset restores DEFAULT_FILTERS", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("admin-products-filter-q"), {
      target: { value: "mango" },
    });
    expect(lastFilters()?.q).toBe("mango");
    fireEvent.click(screen.getByTestId("admin-products-filter-reset"));
    expect(lastFilters()).toEqual({ limit: 50, offset: 0 });
  });
});

// --------------------------------------------------------------------- //
// Pagination
// --------------------------------------------------------------------- //

describe("AdminProductsPage — pagination", () => {
  it("Previous is disabled at offset 0", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("admin-products-pagination-prev"),
    ).toBeDisabled();
  });

  it("Next is disabled when offset + limit >= total", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()], {
          total: 50,
          limit: 50,
          offset: 0,
        }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("admin-products-pagination-next"),
    ).toBeDisabled();
  });

  it("Next advances offset by limit", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    fireEvent.click(
      screen.getByTestId("admin-products-pagination-next"),
    );
    expect(lastFilters()?.offset).toBe(50);
  });

  it("Previous retreats offset by limit", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    fireEvent.click(
      screen.getByTestId("admin-products-pagination-next"),
    );
    fireEvent.click(
      screen.getByTestId("admin-products-pagination-next"),
    );
    expect(lastFilters()?.offset).toBe(100);
    fireEvent.click(
      screen.getByTestId("admin-products-pagination-prev"),
    );
    expect(lastFilters()?.offset).toBe(50);
  });

  it("preserves filter state across pagination", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    fireEvent.change(screen.getByTestId("admin-products-filter-q"), {
      target: { value: "mango" },
    });
    fireEvent.click(
      screen.getByTestId("admin-products-pagination-next"),
    );
    expect(lastFilters()).toEqual({
      limit: 50,
      offset: 50,
      q: "mango",
    });
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminProductsPage — architecture guard", () => {
  it("does not render mutation/action buttons on the list surface", () => {
    vi.mocked(adminProductsHooks.useAdminProductsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeProduct()]),
      }),
    );
    renderPage();
    // No edit / deactivate / approve / reject buttons should appear
    // on the list page (those live on the detail page only).
    expect(
      screen.queryByRole("button", { name: /edit/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /deactivate/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /approve/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /reject/i }),
    ).not.toBeInTheDocument();
  });

  it("renders without an AuthProvider or StoreProvider in the tree", () => {
    // MemoryRouter is the only context provided. If the page touched
    // useAuth / useStoreContext, the render would crash.
    expect(() => renderPage()).not.toThrow();
  });
});
