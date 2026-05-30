// F2.20.6: tests for the real Admin Compliance oversight page.
//
// Stub `../../hooks` so we drive every query state without TanStack
// Query or the API. The page renders <Link> elements via the queue
// table; wrap the harness in MemoryRouter. The page itself does NOT
// use react-router-dom hooks (no useParams, no useLocation), and
// does NOT use useStoreContext / useAuth (verified by the
// architecture assertion at the bottom).
//
// Coverage:
//   - Loading state for the summary query.
//   - Loading state for the queue query.
//   - Summary error state.
//   - Queue error state.
//   - Empty queue state.
//   - KPI values render verbatim from backend summary.
//   - Queue rows render verbatim from backend queue response.
//   - Recent reviews render verbatim from backend summary.reviews.
//   - Filters: q / compliance_status / allowed_for_sale / is_active
//     mutate the next useAdminComplianceProductsQuery invocation.
//   - No category filter UI control exists.
//   - Empty/whitespace q is dropped.
//   - Changing any filter resets offset to 0.
//   - Reset restores DEFAULT_FILTERS.
//   - Pagination Prev disabled at offset 0; Next disabled at end;
//     advance + retreat update offset; range text formats correctly.
//   - Filters preserved across pagination.
//   - Drill-down link points to /app/admin/products/:productId.
//   - No client-side compliance summary / queue generation.
//   - No workflow / incident / task UI.
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

import AdminCompliancePage from "../AdminCompliancePage";
import * as adminComplianceHooks from "../../hooks";
import type {
  AdminComplianceProductsFilters,
  AdminComplianceProductsListResponse,
  AdminComplianceSummary,
  Product,
  ProductComplianceAuditLog,
} from "../../types";

vi.mock("../../hooks", () => ({
  useAdminComplianceSummaryQuery: vi.fn(),
  useAdminComplianceProductsQuery: vi.fn(),
  adminComplianceQueryKeys: { all: ["admin-compliance"] as const },
}));

// Stub the Radix Select primitives with a native <select> so JSDOM
// can drive them via fireEvent.change. Same pattern as the F2.20.5
// AdminProductsPage test — the trigger's data-testid lands on the
// native <select> so existing testid queries still work.
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
const AUDIT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const USER_A = "ffffffff-ffff-ffff-ffff-ffffffffffff";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
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
  } as unknown as UseQueryResult<TData>;
}

function makeSummary(
  overrides: Partial<AdminComplianceSummary> = {},
): AdminComplianceSummary {
  return {
    products: {
      total: 12,
      allowed: 7,
      restricted: 3,
      banned: 2,
      blocked: 5,
      allowed_for_sale: 8,
      not_allowed_for_sale: 4,
      inactive: 1,
    },
    reviews: { recent_count: 0, recent: [] },
    queue: { total: 5, banned: 2, restricted: 3, not_allowed_for_sale: 4 },
    ...overrides,
  };
}

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_A,
    name: "Restricted Vape",
    brand: "NubeBrand",
    category: "vape",
    description: null,
    compliance_status: "restricted",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: "2026-05-12T08:00:00Z",
    approval_status: "approved",
    proposed_by_store_id: null,
    proposed_by_user_id: null,
    reviewed_by_user_id: null,
    reviewed_at: null,
    rejection_reason: null,
    created_at: "2026-05-10T12:00:00Z",
    updated_at: "2026-05-12T08:00:00Z",
    ...overrides,
  };
}

function makeAudit(
  overrides: Partial<ProductComplianceAuditLog> = {},
): ProductComplianceAuditLog {
  return {
    id: AUDIT_A,
    product_id: PRODUCT_A,
    previous_compliance_status: "allowed",
    new_compliance_status: "restricted",
    previous_allowed_for_sale: true,
    new_allowed_for_sale: true,
    reason: "routine review",
    changed_by_user_id: USER_A,
    created_at: "2026-05-13T08:00:00Z",
    ...overrides,
  };
}

function makeQueueResponse(
  items: Product[],
  overrides: Partial<AdminComplianceProductsListResponse> = {},
): AdminComplianceProductsListResponse {
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
      <AdminCompliancePage />
    </MemoryRouter>,
  );
}

function lastQueueFilters(): AdminComplianceProductsFilters | undefined {
  const calls = vi.mocked(
    adminComplianceHooks.useAdminComplianceProductsQuery,
  ).mock.calls;
  if (calls.length === 0) return undefined;
  return calls[calls.length - 1][0] as
    | AdminComplianceProductsFilters
    | undefined;
}

beforeEach(() => {
  vi.mocked(
    adminComplianceHooks.useAdminComplianceSummaryQuery,
  ).mockReset();
  vi.mocked(
    adminComplianceHooks.useAdminComplianceProductsQuery,
  ).mockReset();

  vi.mocked(
    adminComplianceHooks.useAdminComplianceSummaryQuery,
  ).mockReturnValue(
    asQueryResult<AdminComplianceSummary>({
      isSuccess: true,
      data: makeSummary(),
    }),
  );
  vi.mocked(
    adminComplianceHooks.useAdminComplianceProductsQuery,
  ).mockReturnValue(
    asQueryResult<AdminComplianceProductsListResponse>({
      isSuccess: true,
      data: makeQueueResponse([]),
    }),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Loading / error / empty / success
// --------------------------------------------------------------------- //

describe("AdminCompliancePage — summary loading", () => {
  it("renders a loading state for the summary section", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceSummaryQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceSummary>({
        isPending: true,
        isLoading: true,
      }),
    );
    renderPage();
    // The first LoadingState in the document covers the summary
    // section while the queue is in its success branch (empty list →
    // EmptyState).
    expect(
      screen.getAllByRole("status").length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.queryByTestId("compliance-kpi-grid"),
    ).not.toBeInTheDocument();
  });
});

describe("AdminCompliancePage — queue loading", () => {
  it("renders a loading state for the queue section while summary is success", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isPending: true,
        isLoading: true,
      }),
    );
    renderPage();
    expect(screen.getByTestId("compliance-kpi-grid")).toBeInTheDocument();
    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.queryByTestId("compliance-queue-table"),
    ).not.toBeInTheDocument();
  });
});

describe("AdminCompliancePage — summary error", () => {
  it("renders an error state with retry when the summary query errors", () => {
    const refetch = vi.fn();
    vi.mocked(
      adminComplianceHooks.useAdminComplianceSummaryQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceSummary>({
        isError: true,
        error: new Error("forbidden summary"),
        refetch,
      }),
    );
    renderPage();
    expect(
      screen.getByText(/Could not load compliance summary/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/forbidden summary/i)).toBeInTheDocument();
    // Retry button (queue section may have its own retry too; the
    // first alert's retry is the summary's).
    const retryButtons = screen.getAllByRole("button", { name: /retry/i });
    fireEvent.click(retryButtons[0]);
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("AdminCompliancePage — queue error", () => {
  it("renders an error state with retry when the queue query errors", () => {
    const refetch = vi.fn();
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isError: true,
        error: new Error("queue failure"),
        refetch,
      }),
    );
    renderPage();
    expect(
      screen.getByText(/Could not load compliance queue/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/queue failure/i)).toBeInTheDocument();
    const retryButtons = screen.getAllByRole("button", { name: /retry/i });
    fireEvent.click(retryButtons[0]);
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("AdminCompliancePage — empty queue", () => {
  it("renders the empty queue state when the queue succeeds with no rows", () => {
    renderPage();
    expect(screen.getByText("Queue is empty")).toBeInTheDocument();
    expect(
      screen.queryByTestId("compliance-queue-table"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Success
// --------------------------------------------------------------------- //

describe("AdminCompliancePage — KPI grid", () => {
  it("renders backend summary KPI values verbatim", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceSummaryQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceSummary>({
        isSuccess: true,
        data: makeSummary({
          products: {
            total: 12,
            allowed: 7,
            restricted: 3,
            banned: 2,
            blocked: 5,
            allowed_for_sale: 8,
            not_allowed_for_sale: 4,
            inactive: 1,
          },
          queue: {
            total: 5,
            banned: 2,
            restricted: 3,
            not_allowed_for_sale: 4,
          },
          reviews: { recent_count: 3, recent: [] },
        }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("kpi-products-total-value"),
    ).toHaveTextContent("12");
    expect(
      screen.getByTestId("kpi-products-blocked-value"),
    ).toHaveTextContent("5");
    expect(
      screen.getByTestId("kpi-products-restricted-value"),
    ).toHaveTextContent("3");
    expect(
      screen.getByTestId("kpi-products-banned-value"),
    ).toHaveTextContent("2");
    expect(
      screen.getByTestId("kpi-products-not-allowed-for-sale-value"),
    ).toHaveTextContent("4");
    expect(
      screen.getByTestId("kpi-products-inactive-value"),
    ).toHaveTextContent("1");
    expect(screen.getByTestId("kpi-queue-total-value")).toHaveTextContent(
      "5",
    );
    expect(
      screen.getByTestId("kpi-reviews-recent-count-value"),
    ).toHaveTextContent("3");
  });
});

describe("AdminCompliancePage — queue rows", () => {
  it("renders one row per backend product with drill-down link", () => {
    const products = [
      makeProduct({
        id: PRODUCT_A,
        name: "Restricted Vape",
        compliance_status: "restricted",
      }),
      makeProduct({
        id: PRODUCT_B,
        name: "Banned Item",
        compliance_status: "banned",
        allowed_for_sale: false,
        hold_reason: "FDA notice",
      }),
    ];
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse(products, { total: 5 }),
      }),
    );
    renderPage();
    const rows = screen.getAllByTestId("compliance-queue-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("data-product-id", PRODUCT_A);
    expect(rows[1]).toHaveAttribute("data-product-id", PRODUCT_B);

    expect(
      within(rows[1]).getByTestId("compliance-queue-row-hold-reason"),
    ).toHaveTextContent("FDA notice");

    const links = screen.getAllByTestId("compliance-queue-row-drilldown");
    expect(links[0]).toHaveAttribute(
      "href",
      `/app/admin/products/${PRODUCT_A}`,
    );
    expect(links[1]).toHaveAttribute(
      "href",
      `/app/admin/products/${PRODUCT_B}`,
    );
  });

  it("renders the pagination range from backend totals", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse([makeProduct()], { total: 7 }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("compliance-pagination-range"),
    ).toHaveTextContent("Showing 1–1 of 7");
  });
});

describe("AdminCompliancePage — recent reviews", () => {
  it("renders recent review rows from backend summary", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceSummaryQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceSummary>({
        isSuccess: true,
        data: makeSummary({
          reviews: { recent_count: 2, recent: [makeAudit(), makeAudit({ id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" })] },
        }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("recent-compliance-reviews-count"),
    ).toHaveTextContent("2");
    expect(
      screen.getAllByTestId("recent-compliance-reviews-row"),
    ).toHaveLength(2);
  });

  it("renders an empty-reviews state when the backend tail is empty", () => {
    renderPage();
    expect(
      screen.getByTestId("recent-compliance-reviews-empty"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Filters
// --------------------------------------------------------------------- //

describe("AdminCompliancePage — filters", () => {
  it("default initial filters include limit 50 / offset 0", () => {
    renderPage();
    expect(lastQueueFilters()).toEqual({ limit: 50, offset: 0 });
  });

  it("does NOT render a category filter input (backend rejects it)", () => {
    renderPage();
    expect(
      screen.queryByTestId("compliance-filter-category"),
    ).not.toBeInTheDocument();
  });

  it("typing q forwards the trimmed value to the next query", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("compliance-filter-q"), {
      target: { value: "  mango  " },
    });
    expect(lastQueueFilters()).toEqual({
      limit: 50,
      offset: 0,
      q: "mango",
    });
  });

  it("clearing q drops the key", () => {
    renderPage();
    const input = screen.getByTestId("compliance-filter-q");
    fireEvent.change(input, { target: { value: "mango" } });
    fireEvent.change(input, { target: { value: "   " } });
    expect(lastQueueFilters()?.q).toBeUndefined();
  });

  it("selecting compliance_status forwards it", () => {
    renderPage();
    const trigger = screen.getByTestId(
      "compliance-filter-compliance-trigger",
    ) as HTMLSelectElement;
    fireEvent.change(trigger, { target: { value: "banned" } });
    expect(lastQueueFilters()?.compliance_status).toBe("banned");
  });

  it("selecting allowed_for_sale=false preserves the falsy boolean", () => {
    renderPage();
    const trigger = screen.getByTestId(
      "compliance-filter-allowed-for-sale-trigger",
    ) as HTMLSelectElement;
    fireEvent.change(trigger, { target: { value: "false" } });
    expect(lastQueueFilters()?.allowed_for_sale).toBe(false);
  });

  it("selecting is_active=false preserves the falsy boolean", () => {
    renderPage();
    const trigger = screen.getByTestId(
      "compliance-filter-is-active-trigger",
    ) as HTMLSelectElement;
    fireEvent.change(trigger, { target: { value: "false" } });
    expect(lastQueueFilters()?.is_active).toBe(false);
  });

  it("changing a filter resets offset to 0", () => {
    // Seed offset > 0 via pagination first.
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    fireEvent.click(screen.getByTestId("compliance-pagination-next"));
    expect(lastQueueFilters()?.offset).toBe(50);

    fireEvent.change(screen.getByTestId("compliance-filter-q"), {
      target: { value: "mango" },
    });
    expect(lastQueueFilters()?.offset).toBe(0);
  });

  it("Reset restores DEFAULT_FILTERS", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("compliance-filter-q"), {
      target: { value: "mango" },
    });
    expect(lastQueueFilters()?.q).toBe("mango");
    fireEvent.click(screen.getByTestId("compliance-filter-reset"));
    expect(lastQueueFilters()).toEqual({ limit: 50, offset: 0 });
  });
});

// --------------------------------------------------------------------- //
// Pagination
// --------------------------------------------------------------------- //

describe("AdminCompliancePage — pagination", () => {
  it("Previous disabled at offset 0", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("compliance-pagination-prev"),
    ).toBeDisabled();
  });

  it("Next disabled when offset + limit >= total", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse([makeProduct()], {
          total: 50,
          limit: 50,
          offset: 0,
        }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("compliance-pagination-next"),
    ).toBeDisabled();
  });

  it("Next advances offset; Previous retreats; filters preserved", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse([makeProduct()], { total: 200 }),
      }),
    );
    renderPage();
    fireEvent.change(screen.getByTestId("compliance-filter-q"), {
      target: { value: "mango" },
    });
    fireEvent.click(screen.getByTestId("compliance-pagination-next"));
    expect(lastQueueFilters()).toEqual({
      limit: 50,
      offset: 50,
      q: "mango",
    });
    fireEvent.click(screen.getByTestId("compliance-pagination-prev"));
    expect(lastQueueFilters()).toEqual({
      limit: 50,
      offset: 0,
      q: "mango",
    });
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminCompliancePage — architecture guard", () => {
  it("does not render workflow / incident / task buttons", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse([makeProduct()]),
      }),
    );
    renderPage();
    // No incident / task / assign / claim / SLA controls.
    for (const pattern of [
      /incident/i,
      /task/i,
      /assign/i,
      /claim/i,
      /SLA/i,
    ]) {
      expect(screen.queryByRole("button", { name: pattern })).not.toBeInTheDocument();
    }
  });

  it("does not render an inline compliance review/approve/reject mutation UI on the queue", () => {
    vi.mocked(
      adminComplianceHooks.useAdminComplianceProductsQuery,
    ).mockReturnValue(
      asQueryResult<AdminComplianceProductsListResponse>({
        isSuccess: true,
        data: makeQueueResponse([makeProduct()]),
      }),
    );
    renderPage();
    // Compliance changes flow through the canonical detail page; no
    // inline approve/reject button on the queue surface.
    for (const pattern of [/approve/i, /reject/i, /review now/i]) {
      expect(screen.queryByRole("button", { name: pattern })).not.toBeInTheDocument();
    }
  });

  it("renders without an AuthProvider or StoreProvider in the tree", () => {
    expect(() => renderPage()).not.toThrow();
  });
});
