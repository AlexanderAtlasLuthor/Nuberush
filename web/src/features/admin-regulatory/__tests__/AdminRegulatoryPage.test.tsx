// F2.26.6.C: tests for the read-only Admin Regulatory alerts page.
//
// Pattern mirrors admin-operations/pages/tests/AdminOperationsPage.test.tsx:
// mock the feature hook, render the page, and assert each state branch, the
// filter→params wiring, KPI wording, badges, and pagination. A final
// architecture guard greps the new sources for forbidden imports.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";

import AdminRegulatoryPage from "../pages/AdminRegulatoryPage";
import * as hooks from "../hooks";
import type {
  ComplianceAlert,
  ComplianceAlertAggregate,
  ComplianceAlertFilters,
  ComplianceAlertListResponse,
} from "../types";

vi.mock("../hooks", () => ({
  useAdminRegulatoryAlerts: vi.fn(),
  useAdminRegulatoryAggregate: vi.fn(),
  useAdminRegulatoryAlert: vi.fn(),
  useAdminRegulatoryAlertDecisions: vi.fn(),
  useAcknowledgeAdminRegulatoryAlert: vi.fn(),
  useDismissAdminRegulatoryAlert: vi.fn(),
  useResolveAdminRegulatoryAlert: vi.fn(),
}));

/** Build a dense-by-enum aggregate, zero-filled then overlaid with counts. */
function makeAggregate(
  partial: {
    total?: number;
    by_status?: Partial<ComplianceAlertAggregate["by_status"]>;
    by_severity?: Partial<ComplianceAlertAggregate["by_severity"]>;
    by_recommended_action?: Partial<
      ComplianceAlertAggregate["by_recommended_action"]
    >;
  } = {},
): ComplianceAlertAggregate {
  return {
    total: partial.total ?? 0,
    by_status: {
      open: 0,
      acknowledged: 0,
      actioned: 0,
      dismissed: 0,
      ...partial.by_status,
    },
    by_severity: {
      low: 0,
      medium: 0,
      high: 0,
      critical: 0,
      ...partial.by_severity,
    },
    by_recommended_action: {
      none: 0,
      hold: 0,
      ban: 0,
      ...partial.by_recommended_action,
    },
  };
}

function asAggregateResult(
  partial: Partial<UseQueryResult<ComplianceAlertAggregate>>,
): UseQueryResult<ComplianceAlertAggregate> {
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
  } as unknown as UseQueryResult<ComplianceAlertAggregate>;
}

/** Filters last passed to the aggregate hook (parallels `lastFilters`). */
function lastAggregateFilters(): ComplianceAlertFilters | undefined {
  const calls = vi.mocked(hooks.useAdminRegulatoryAggregate).mock.calls;
  if (calls.length === 0) return undefined;
  return calls[calls.length - 1][0] as ComplianceAlertFilters | undefined;
}

function makeMutation(
  partial: Partial<UseMutationResult> = {},
): UseMutationResult {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseMutationResult;
}

/** Point the detail query hook at a given query-result shape. */
function setDetail(partial: Partial<UseQueryResult<ComplianceAlert>>) {
  const result = {
    refetch: vi.fn(),
    isPending: false,
    isLoading: false,
    isError: false,
    isSuccess: false,
    isFetching: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseQueryResult<ComplianceAlert>;
  vi.mocked(hooks.useAdminRegulatoryAlert).mockReturnValue(result);
}

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";
const NOTICE_ID = "22222222-2222-2222-2222-222222222222";

function asQueryResult(
  partial: Partial<UseQueryResult<ComplianceAlertListResponse>>,
): UseQueryResult<ComplianceAlertListResponse> {
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
  } as unknown as UseQueryResult<ComplianceAlertListResponse>;
}

let alertSeq = 0;
function makeAlert(overrides: Partial<ComplianceAlert> = {}): ComplianceAlert {
  alertSeq += 1;
  return {
    id: `alert-${alertSeq}`,
    notice_id: NOTICE_ID,
    product_id: PRODUCT_ID,
    match_id: null,
    severity: "high",
    status: "open",
    recommended_action: "hold",
    resolution_note: null,
    resolved_by_user_id: null,
    resolved_at: null,
    created_at: "2026-05-12T08:00:00Z",
    updated_at: "2026-05-12T08:00:00Z",
    ...overrides,
  };
}

function makeResponse(
  alerts: ComplianceAlert[],
  overrides: Partial<ComplianceAlertListResponse> = {},
): ComplianceAlertListResponse {
  return {
    items: alerts,
    total: alerts.length,
    limit: 25,
    offset: 0,
    ...overrides,
  };
}

function renderPage() {
  return render(<AdminRegulatoryPage />);
}

function lastFilters(): ComplianceAlertFilters | undefined {
  const calls = vi.mocked(hooks.useAdminRegulatoryAlerts).mock.calls;
  if (calls.length === 0) return undefined;
  return calls[calls.length - 1][0] as ComplianceAlertFilters | undefined;
}

beforeEach(() => {
  alertSeq = 0;
  vi.mocked(hooks.useAdminRegulatoryAlerts).mockReset();
  vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
    asQueryResult({ isSuccess: true, data: makeResponse([]) }),
  );
  // Aggregate hook: default to a successful zero-filled aggregate.
  vi.mocked(hooks.useAdminRegulatoryAggregate).mockReset();
  vi.mocked(hooks.useAdminRegulatoryAggregate).mockReturnValue(
    asAggregateResult({ isSuccess: true, data: makeAggregate() }),
  );
  // Detail + mutation hooks: only exercised when a Review opens the panel.
  vi.mocked(hooks.useAdminRegulatoryAlert).mockReset();
  setDetail({ isLoading: true });
  // Embedded decision trail (only mounts when the panel opens): empty list.
  vi.mocked(hooks.useAdminRegulatoryAlertDecisions).mockReturnValue({
    refetch: vi.fn(),
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: { items: [], total: 0, limit: 25, offset: 0 },
    error: null,
  } as never);
  vi.mocked(hooks.useAcknowledgeAdminRegulatoryAlert).mockReturnValue(
    makeMutation() as never,
  );
  vi.mocked(hooks.useDismissAdminRegulatoryAlert).mockReturnValue(
    makeMutation() as never,
  );
  vi.mocked(hooks.useResolveAdminRegulatoryAlert).mockReturnValue(
    makeMutation() as never,
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Header
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — header", () => {
  it("renders the title and description", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 1, name: /^regulatory alerts$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/review regulatory signals, product matches/i),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// State branches
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — loading state", () => {
  it("shows the loading state and no table", () => {
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({ isLoading: true, isPending: true }),
    );
    renderPage();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(
      screen.queryByTestId("regulatory-alerts-table"),
    ).not.toBeInTheDocument();
  });
});

describe("AdminRegulatoryPage — error state", () => {
  it("shows the error message and a retry button", () => {
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({ isError: true, error: new Error("boom") }),
    );
    renderPage();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/boom/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /retry/i }),
    ).toBeInTheDocument();
  });

  it("retry calls query.refetch", () => {
    const refetch = vi.fn();
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({ isError: true, error: new Error("oops"), refetch }),
    );
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("AdminRegulatoryPage — empty state", () => {
  it("shows filter-scoped empty copy (no global-compliance claim)", () => {
    renderPage(); // default mock = success with empty items
    expect(
      screen.getByText("No regulatory alerts match the current filters."),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("regulatory-alerts-table"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Success render
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — success render", () => {
  it("renders one table row and one mobile card per alert", () => {
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeAlert(), makeAlert()]),
      }),
    );
    renderPage();
    expect(screen.getAllByTestId("regulatory-alert-row")).toHaveLength(2);
    expect(screen.getAllByTestId("regulatory-alert-card")).toHaveLength(2);
  });

  it("renders product_id / notice_id and an em dash for a null product_id", () => {
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeAlert({ product_id: null })]),
      }),
    );
    renderPage();
    const row = screen.getByTestId("regulatory-alert-row");
    expect(
      within(row).getByTestId("regulatory-row-product-id"),
    ).toHaveTextContent("—");
    expect(
      within(row).getByTestId("regulatory-row-notice-id"),
    ).toHaveTextContent(NOTICE_ID);
  });

  it("renders an em dash for an unresolved alert's Resolved cell", () => {
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeAlert({ resolved_at: null })]),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("regulatory-row-resolved"),
    ).toHaveTextContent("—");
  });

  it("humanizes severity / status / recommended_action badges", () => {
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([
          makeAlert({
            severity: "critical",
            status: "acknowledged",
            recommended_action: "ban",
          }),
        ]),
      }),
    );
    renderPage();
    const row = screen.getByTestId("regulatory-alert-row");
    expect(within(row).getByText("Critical")).toBeInTheDocument();
    expect(within(row).getByText("Acknowledged")).toBeInTheDocument();
    expect(within(row).getByText("Ban recommended")).toBeInTheDocument();
    // Raw enum values must never be shown.
    expect(within(row).queryByText("critical")).not.toBeInTheDocument();
    expect(within(row).queryByText("ban")).not.toBeInTheDocument();
  });

  it("Review affordance is enabled and does not itself fire a mutation", () => {
    const alert = makeAlert();
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeResponse([alert]) }),
    );
    const ack = makeMutation();
    vi.mocked(hooks.useAcknowledgeAdminRegulatoryAlert).mockReturnValue(
      ack as never,
    );
    setDetail({ isSuccess: true, data: alert });

    renderPage();
    const reviewBtn = screen.getByTestId("regulatory-row-review");
    expect(reviewBtn).not.toBeDisabled();
    fireEvent.click(reviewBtn);
    // Opening the panel must not run any lifecycle mutation.
    expect(ack.mutate).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Detail panel open / close (page integration)
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — detail panel selection", () => {
  it("clicking Review opens the detail panel for that alert", () => {
    const alert = makeAlert();
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeResponse([alert]) }),
    );
    setDetail({ isSuccess: true, data: alert });

    renderPage();
    expect(
      screen.queryByTestId("regulatory-detail-panel"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("regulatory-row-review"));

    expect(screen.getByTestId("regulatory-detail-panel")).toBeInTheDocument();
    // The detail query was asked for the clicked alert id.
    expect(hooks.useAdminRegulatoryAlert).toHaveBeenCalledWith(alert.id);
  });

  it("Close hides the detail panel", () => {
    const alert = makeAlert();
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeResponse([alert]) }),
    );
    setDetail({ isSuccess: true, data: alert });

    renderPage();
    fireEvent.click(screen.getByTestId("regulatory-row-review"));
    expect(screen.getByTestId("regulatory-detail-panel")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("regulatory-detail-close"));
    expect(
      screen.queryByTestId("regulatory-detail-panel"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// KPI cards
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — KPI cards", () => {
  it("renders GLOBAL backend aggregate counts, not page-derived counts", () => {
    // The list page holds only 2 rows, but the global aggregate reports 87.
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeResponse([makeAlert(), makeAlert()], { total: 87 }),
      }),
    );
    vi.mocked(hooks.useAdminRegulatoryAggregate).mockReturnValue(
      asAggregateResult({
        isSuccess: true,
        data: makeAggregate({
          total: 87,
          by_status: { open: 40, dismissed: 12 },
          by_severity: { high: 9, critical: 6 },
          by_recommended_action: { hold: 7, ban: 4 },
        }),
      }),
    );
    renderPage();

    expect(screen.getByText("Total matching filters")).toBeInTheDocument();
    expect(
      screen.getByTestId("regulatory-kpi-total-value"),
    ).toHaveTextContent("87");
    // Open is the global count (40), NOT the 2 rows on this page.
    expect(screen.getByTestId("regulatory-kpi-open-value")).toHaveTextContent(
      "40",
    );
    // High + critical summed globally (9 + 6 = 15).
    expect(
      screen.getByTestId("regulatory-kpi-high-critical-value"),
    ).toHaveTextContent("15");
    // Hold + ban summed globally (7 + 4 = 11).
    expect(
      screen.getByTestId("regulatory-kpi-hold-ban-value"),
    ).toHaveTextContent("11");
  });

  it("never labels a KPI count '(this page)'", () => {
    renderPage();
    expect(screen.queryByText(/\(this page\)/i)).not.toBeInTheDocument();
  });

  it("shows a neutral placeholder while the aggregate loads", () => {
    vi.mocked(hooks.useAdminRegulatoryAggregate).mockReturnValue(
      asAggregateResult({ isLoading: true, isSuccess: false }),
    );
    renderPage();
    expect(
      screen.getByTestId("regulatory-kpi-total-value"),
    ).toHaveTextContent("—");
    expect(
      screen.getByTestId("regulatory-kpi-open-value"),
    ).toHaveTextContent("—");
  });

  it("renders zero counts as 0 (not a placeholder) when the aggregate is empty", () => {
    // Default beforeEach aggregate is a successful all-zero aggregate.
    renderPage();
    expect(
      screen.getByTestId("regulatory-kpi-total-value"),
    ).toHaveTextContent("0");
    expect(
      screen.getByTestId("regulatory-kpi-open-value"),
    ).toHaveTextContent("0");
  });

  it("drives the aggregate hook with the same filters as the list", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("regulatory-filter-status"), {
      target: { value: "open" },
    });
    expect(lastAggregateFilters()).toMatchObject({ status: "open" });
    expect(lastFilters()).toMatchObject({ status: "open" });
  });
});

// --------------------------------------------------------------------- //
// Filters → API params
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — filters", () => {
  it("selecting a status sets the param and resets offset to 0", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("regulatory-filter-status"), {
      target: { value: "open" },
    });
    expect(lastFilters()).toMatchObject({ status: "open", offset: 0 });
  });

  it("selecting 'all' status omits the param", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("regulatory-filter-status"), {
      target: { value: "open" },
    });
    fireEvent.change(screen.getByTestId("regulatory-filter-status"), {
      target: { value: "all" },
    });
    expect(lastFilters()?.status).toBeUndefined();
  });

  it("selecting a severity sets the param", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("regulatory-filter-severity"), {
      target: { value: "critical" },
    });
    expect(lastFilters()).toMatchObject({ severity: "critical", offset: 0 });
  });

  it("selecting a recommended_action sets the param", () => {
    renderPage();
    fireEvent.change(
      screen.getByTestId("regulatory-filter-recommended-action"),
      { target: { value: "ban" } },
    );
    expect(lastFilters()).toMatchObject({
      recommended_action: "ban",
      offset: 0,
    });
  });

  it("product_id is trimmed and set; whitespace-only is dropped", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("regulatory-filter-product-id"), {
      target: { value: `  ${PRODUCT_ID}  ` },
    });
    expect(lastFilters()).toMatchObject({ product_id: PRODUCT_ID, offset: 0 });

    fireEvent.change(screen.getByTestId("regulatory-filter-product-id"), {
      target: { value: "   " },
    });
    expect(lastFilters()?.product_id).toBeUndefined();
  });

  it("notice_id is trimmed and set; empty is dropped", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("regulatory-filter-notice-id"), {
      target: { value: NOTICE_ID },
    });
    expect(lastFilters()).toMatchObject({ notice_id: NOTICE_ID });

    fireEvent.change(screen.getByTestId("regulatory-filter-notice-id"), {
      target: { value: "" },
    });
    expect(lastFilters()?.notice_id).toBeUndefined();
  });

  it("changing a filter after paging resets offset to 0", () => {
    // 120 total over a page of 25 so Next is enabled.
    const items = Array.from({ length: 25 }, () => makeAlert());
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: { items, total: 120, limit: 25, offset: 0 },
      }),
    );
    renderPage();

    fireEvent.click(screen.getByTestId("regulatory-pagination-next"));
    expect(lastFilters()?.offset).toBe(25);

    fireEvent.change(screen.getByTestId("regulatory-filter-severity"), {
      target: { value: "high" },
    });
    expect(lastFilters()).toMatchObject({ severity: "high", offset: 0 });
  });
});

// --------------------------------------------------------------------- //
// Pagination
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — pagination", () => {
  function setup(total: number, itemsLength: number, offset = 0) {
    const items = Array.from({ length: itemsLength }, () => makeAlert());
    vi.mocked(hooks.useAdminRegulatoryAlerts).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: { items, total, limit: 25, offset },
      }),
    );
  }

  it("Previous is disabled at offset 0", () => {
    setup(120, 25);
    renderPage();
    expect(screen.getByTestId("regulatory-pagination-prev")).toBeDisabled();
  });

  it("Next advances offset by limit", () => {
    setup(120, 25);
    renderPage();
    fireEvent.click(screen.getByTestId("regulatory-pagination-next"));
    expect(lastFilters()?.offset).toBe(25);
  });

  it("Next is disabled when offset + limit >= total", () => {
    setup(25, 25);
    renderPage();
    expect(screen.getByTestId("regulatory-pagination-next")).toBeDisabled();
  });

  it("range text reads 'Showing X–Y of N'", () => {
    setup(120, 25);
    renderPage();
    expect(
      screen.getByTestId("regulatory-pagination-range"),
    ).toHaveTextContent("Showing 1–25 of 120");
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminRegulatoryPage — architecture", () => {
  it("new sources never import fetch / supabase / auth / store / mutations", async () => {
    const fs = await import("node:fs");
    const files = [
      "../pages/AdminRegulatoryPage.tsx",
      "../components/RegulatoryAlertsFilters.tsx",
      "../components/RegulatoryAlertsTable.tsx",
      "../components/RegulatoryAlertsMobileCards.tsx",
      "../components/RegulatoryKpiCards.tsx",
      "../components/RegulatoryAlertBadges.tsx",
    ];
    for (const rel of files) {
      const raw = fs.readFileSync(new URL(rel, import.meta.url), "utf8");
      const code = raw
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/\/\/[^\n]*/g, "");
      expect(code).not.toMatch(/\bfetch\s*\(/);
      expect(code.toLowerCase()).not.toContain("supabase");
      expect(code).not.toMatch(/useAuth|AuthContext|AuthProvider/);
      expect(code).not.toMatch(/useStoreContext|StoreContext|StoreProvider/);
      expect(code).not.toMatch(/\buseMutation\b/);
      expect(code).not.toMatch(/\buseQueryClient\b/);
      expect(code).not.toMatch(/from\s+["'][^"']*\/(auth|store)\//);
    }
  });
});
