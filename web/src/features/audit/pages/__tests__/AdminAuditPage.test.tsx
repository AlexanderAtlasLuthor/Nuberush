// F2.18.4: tests for the real Admin Audit page.
//
// Stub the audit hooks so we can drive every query state without
// TanStack Query or the API. Render through a plain `render` — the
// admin page does NOT use react-router-dom hooks (no useParams, no
// useLocation), so a router wrapper is not required. This is part of
// the contract: admin audit must not require store context.
//
// Coverage:
//   - Page header copy (admin-scoped, no "this store" language).
//   - Default filters {limit: 50, offset: 0}.
//   - Loading / error / empty / data states surfaced via AuditFeed.
//   - Retry calls query.refetch.
//   - Each AdminAuditFilters field feeds back into the next
//     useAdminAuditQuery invocation with the right snapshot.
//   - Empty/whitespace string filters are dropped.
//   - Pagination Previous/Next disabled at bounds; Next advances
//     offset by limit.
//   - Architecture guards: source does not import useAuth /
//     currentUser / useStoreContext / getStoreAudit / fetch / axios.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminAuditPage from "../AdminAuditPage";
import * as auditHooks from "../../hooks";
import type {
  AdminAuditFilters,
  AuditEvent,
  AuditListResponse,
} from "../../types";

vi.mock("../../hooks", () => ({
  useAdminAuditQuery: vi.fn(),
  useStoreAuditQuery: vi.fn(),
  useStoreInventoryLogsQuery: vi.fn(),
  auditKeys: { all: ["audit"] as const },
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ACTOR_ID = "22222222-2222-2222-2222-222222222222";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return {
    refetch: vi.fn(),
    ...partial,
  } as unknown as UseQueryResult<TData>;
}

function makeAuditEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: "evt-1",
    source: "inventory",
    store_id: STORE_ID,
    actor_id: ACTOR_ID,
    action: "receipt",
    entity_type: "inventory_item",
    entity_id: "item-1",
    summary: "Inventory receipt: +10 units (after 10)",
    metadata: { quantity_delta: 10, quantity_after: 10 },
    created_at: "2026-05-04T08:30:00Z",
    ...overrides,
  };
}

function makeListResponse(
  items: AuditEvent[],
  overrides: Partial<AuditListResponse> = {},
): AuditListResponse {
  return {
    items,
    total: items.length,
    limit: 50,
    offset: 0,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(auditHooks.useAdminAuditQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Chrome
// --------------------------------------------------------------------- //

describe("AdminAuditPage — chrome", () => {
  beforeEach(() => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
  });

  it("renders the page heading 'Audit'", () => {
    render(<AdminAuditPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Audit" }),
    ).toBeInTheDocument();
  });

  it("renders the admin-scope description (no 'this store' language)", () => {
    render(<AdminAuditPage />);
    expect(
      screen.getByText(
        /Review unified inventory, order, and compliance activity across the NubeRush platform\./,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/this store/i)).not.toBeInTheDocument();
  });

  it("calls useAdminAuditQuery with default filters {limit: 50, offset: 0}", () => {
    render(<AdminAuditPage />);
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ limit: 50, offset: 0 });
  });
});

// --------------------------------------------------------------------- //
// Query states
// --------------------------------------------------------------------- //

describe("AdminAuditPage — query states", () => {
  it("renders the loading state", () => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: true,
        isFetching: true,
        isError: false,
        isSuccess: false,
        data: undefined,
      }),
    );
    render(<AdminAuditPage />);
    expect(screen.getByText(/loading audit events/i)).toBeInTheDocument();
  });

  it("renders the error state and retry button", () => {
    const refetch = vi.fn();
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: true,
        isSuccess: false,
        data: undefined,
        error: new Error("forbidden"),
        refetch: refetch as never,
      }),
    );
    render(<AdminAuditPage />);
    expect(
      screen.getByText("Audit feed failed to load"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("renders the empty state when items is empty", () => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
    render(<AdminAuditPage />);
    expect(screen.getByText("No audit events")).toBeInTheDocument();
    expect(
      screen.getByText(
        "No platform activity recorded for the selected filters.",
      ),
    ).toBeInTheDocument();
    // Pagination bar should not render when there are no items.
    expect(
      screen.queryByTestId("admin-audit-pagination"),
    ).not.toBeInTheDocument();
  });

  it("renders rows when items is non-empty", () => {
    const event = makeAuditEvent();
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([event], { total: 1 }),
      }),
    );
    render(<AdminAuditPage />);
    expect(
      screen.getByTestId(`audit-feed-row-${event.id}`),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(`audit-feed-summary-${event.id}`),
    ).toHaveTextContent("Inventory receipt: +10 units (after 10)");
  });

  it("renders the admin-scoped card title 'Platform activity'", () => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeAuditEvent()], { total: 1 }),
      }),
    );
    render(<AdminAuditPage />);
    expect(screen.getByText("Platform activity")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Inventory, order, and compliance events across every store.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the total count when there are items", () => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeAuditEvent()], { total: 137 }),
      }),
    );
    render(<AdminAuditPage />);
    expect(screen.getByTestId("admin-audit-total")).toHaveTextContent(
      "Total: 137",
    );
  });
});

// --------------------------------------------------------------------- //
// Filters
// --------------------------------------------------------------------- //

describe("AdminAuditPage — filters", () => {
  beforeEach(() => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
  });

  it("typing in store_id forwards the value to useAdminAuditQuery", () => {
    render(<AdminAuditPage />);
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-store-id"),
      { target: { value: STORE_ID } },
    );
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ store_id: STORE_ID });
  });

  it("clearing store_id drops the key from the next snapshot", () => {
    render(<AdminAuditPage />);
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-store-id"),
      { target: { value: STORE_ID } },
    );
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-store-id"),
      { target: { value: "" } },
    );
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect((lastCall?.[0] as AdminAuditFilters | undefined)?.store_id)
      .toBeUndefined();
  });

  it("whitespace-only store_id is dropped (treated as empty)", () => {
    render(<AdminAuditPage />);
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-store-id"),
      { target: { value: "   " } },
    );
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect((lastCall?.[0] as AdminAuditFilters | undefined)?.store_id)
      .toBeUndefined();
  });

  it("typing in action forwards trimmed text", () => {
    render(<AdminAuditPage />);
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-action"),
      { target: { value: "  receipt  " } },
    );
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ action: "receipt" });
  });

  it("typing in actor_id forwards the value", () => {
    render(<AdminAuditPage />);
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-actor-id"),
      { target: { value: ACTOR_ID } },
    );
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ actor_id: ACTOR_ID });
  });

  it("typing in date_from / date_to forwards the values", () => {
    render(<AdminAuditPage />);
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-date-to"),
      { target: { value: "2026-12-31" } },
    );
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({
      date_from: "2026-01-01",
      date_to: "2026-12-31",
    });
  });

  it("clearing action drops the key", () => {
    render(<AdminAuditPage />);
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-action"),
      { target: { value: "receipt" } },
    );
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-action"),
      { target: { value: "   " } },
    );
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect((lastCall?.[0] as AdminAuditFilters | undefined)?.action)
      .toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// Pagination
// --------------------------------------------------------------------- //

describe("AdminAuditPage — pagination", () => {
  it("Previous is disabled on the first page; Next enabled when more rows", () => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeAuditEvent()], {
          total: 200,
          limit: 50,
          offset: 0,
        }),
      }),
    );
    render(<AdminAuditPage />);
    expect(
      screen.getByTestId("admin-audit-pagination-prev"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("admin-audit-pagination-next"),
    ).not.toBeDisabled();
  });

  it("Next is disabled on the last page", () => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeAuditEvent()], {
          total: 50,
          limit: 50,
          offset: 0,
        }),
      }),
    );
    render(<AdminAuditPage />);
    expect(
      screen.getByTestId("admin-audit-pagination-next"),
    ).toBeDisabled();
  });

  it("clicking Next advances offset by limit", () => {
    vi.mocked(auditHooks.useAdminAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeAuditEvent()], {
          total: 200,
          limit: 50,
          offset: 0,
        }),
      }),
    );
    render(<AdminAuditPage />);
    fireEvent.click(screen.getByTestId("admin-audit-pagination-next"));
    const lastCall = vi
      .mocked(auditHooks.useAdminAuditQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]?.offset).toBe(50);
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminAuditPage — architecture", () => {
  it("does NOT import useAuth / currentUser / useStoreContext / getStoreAudit / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AdminAuditPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\buseStoreContext\b/);
    expect(code).not.toMatch(/\buseStoreAuditQuery\b/);
    expect(code).not.toMatch(/\bgetStoreAudit\b/);
    expect(code).not.toMatch(/\bgetAdminAudit\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\.role\s*===\s*["']/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
    expect(code).not.toMatch(/apiRequest/);
  });
});
