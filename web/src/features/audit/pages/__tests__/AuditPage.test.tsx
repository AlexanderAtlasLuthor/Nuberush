// F2.16.6: tests for the refactored Store Audit page.
//
// Stub `@/auth` so the page reads a controlled `currentStoreId`
// from `useStoreContext`, and stub the audit hooks so we can
// simulate every query state without TanStack Query or the API.
// `AuditFilters` and `AuditFeed` are rendered for real — they are
// already covered by their own suites and exercising them here
// confirms the integration wiring.
//
// Coverage:
//   - Page header copy (new "Audit" title and unified description).
//   - No-store state.
//   - Default filters `{limit: 50, offset: 0}`.
//   - Loading / error / empty / data states surfaced via AuditFeed.
//   - Retry calls `query.refetch`.
//   - Filter changes feed back into the next `useStoreAuditQuery`
//     invocation.
//   - Three-source end-to-end rendering (inventory + order +
//     product_compliance events).
//   - Anti-fake guards: no BackendLimitationsCard, no
//     AvailableSurfacesCard, no "backend required" copy, no fake
//     rows.
//   - Source-level architecture guards (file-scan) carried over
//     from F2.10.4.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import AuditPage from "../AuditPage";
import * as auditHooks from "../../hooks";
import * as authModule from "@/auth";
import type { AuditEvent, AuditListResponse } from "../../types";
import type { StoreContextState } from "@/auth";

vi.mock("@/auth", async () => {
  const actual = await vi.importActual<typeof import("@/auth")>("@/auth");
  return {
    ...actual,
    useStoreContext: vi.fn(),
  };
});

vi.mock("../../hooks", () => ({
  useStoreAuditQuery: vi.fn(),
  // Legacy export still imported by the index barrel; keep the
  // identity mock available so anything reaching for `auditKeys`
  // doesn't blow up on a missing property.
  auditKeys: { all: ["audit"] as const },
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ACTOR_ID = "33333333-3333-3333-3333-333333333333";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return {
    refetch: vi.fn(),
    ...partial,
  } as unknown as UseQueryResult<TData>;
}

function makeStoreContext(
  overrides: Partial<StoreContextState> = {},
): StoreContextState {
  return {
    currentStoreId: STORE_ID,
    hasStoreContext: true,
    isStoreRequired: true,
    storeError: null,
    ...overrides,
  };
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
  vi.mocked(authModule.useStoreContext).mockReset();
  vi.mocked(authModule.useStoreContext).mockReturnValue(makeStoreContext());
  vi.mocked(auditHooks.useStoreAuditQuery).mockReset();
  vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
    asQueryResult<AuditListResponse>({
      isLoading: false,
      isFetching: false,
      isError: false,
      data: makeListResponse([]),
    }),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// A. Page shell
// --------------------------------------------------------------------- //

describe("AuditPage — page shell", () => {
  it("renders the 'Audit' title", () => {
    render(<AuditPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /^audit$/i }),
    ).toBeInTheDocument();
  });

  it("renders the unified feed description", () => {
    render(<AuditPage />);
    expect(
      screen.getByText(
        /unified inventory, order, and compliance activity/i,
      ),
    ).toBeInTheDocument();
  });

  it("does NOT render the legacy 'backend limitations' card", () => {
    render(<AuditPage />);
    expect(
      screen.queryByTestId("audit-backend-limitations-card"),
    ).toBeNull();
    expect(screen.queryByText(/backend limitations/i)).toBeNull();
    expect(
      screen.queryByText(/no global audit feed exists/i),
    ).toBeNull();
    expect(
      screen.queryByText(/unified store activity feed requires backend support/i),
    ).toBeNull();
  });

  it("does NOT render the legacy 'available audit surfaces' card", () => {
    render(<AuditPage />);
    expect(
      screen.queryByTestId("audit-available-surfaces-card"),
    ).toBeNull();
    expect(
      screen.queryByText(/available audit surfaces/i),
    ).toBeNull();
  });

  it("does NOT render the legacy StoreInventoryLogsPanel on the page", () => {
    render(<AuditPage />);
    expect(
      screen.queryByTestId("store-inventory-logs-panel"),
    ).toBeNull();
    expect(
      screen.queryByText(/store inventory logs/i),
    ).toBeNull();
  });

  it("does NOT render fake audit rows when items is []", () => {
    render(<AuditPage />);
    expect(screen.queryAllByTestId(/^audit-feed-row-/)).toHaveLength(0);
  });
});

// --------------------------------------------------------------------- //
// B. No-store state
// --------------------------------------------------------------------- //

describe("AuditPage — no-store state", () => {
  it("renders the 'Select a store' empty state when currentStoreId is null", () => {
    vi.mocked(authModule.useStoreContext).mockReturnValue(
      makeStoreContext({
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      }),
    );
    render(<AuditPage />);
    expect(screen.getByText("Select a store")).toBeInTheDocument();
    expect(
      screen.getByText("Choose a store to view its audit activity."),
    ).toBeInTheDocument();
  });

  it("does not render AuditFilters or AuditFeed when no store is selected", () => {
    vi.mocked(authModule.useStoreContext).mockReturnValue(
      makeStoreContext({ currentStoreId: null }),
    );
    render(<AuditPage />);
    expect(screen.queryByTestId("audit-filters")).toBeNull();
    expect(screen.queryByTestId("audit-feed")).toBeNull();
  });

  it("does not pass a real store id to useStoreAuditQuery when no store", () => {
    vi.mocked(authModule.useStoreContext).mockReturnValue(
      makeStoreContext({ currentStoreId: null }),
    );
    render(<AuditPage />);
    // The hook is invoked (React-hooks ordering stays stable), but
    // the first arg is the falsy storeId from context, never a
    // fake/hardcoded UUID.
    expect(auditHooks.useStoreAuditQuery).toHaveBeenCalled();
    const [storeIdArg] = vi.mocked(auditHooks.useStoreAuditQuery).mock
      .calls[0];
    expect(storeIdArg).toBeNull();
  });

  it("renders the no-store state for whitespace-only storeId", () => {
    vi.mocked(authModule.useStoreContext).mockReturnValue(
      makeStoreContext({ currentStoreId: "   " }),
    );
    render(<AuditPage />);
    expect(screen.getByText("Select a store")).toBeInTheDocument();
    expect(screen.queryByTestId("audit-feed")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// C. Loading / error / empty / data
// --------------------------------------------------------------------- //

describe("AuditPage — query states", () => {
  it("renders the loading state via AuditFeed", () => {
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: true,
        isFetching: true,
        isError: false,
        data: undefined,
      }),
    );
    render(<AuditPage />);
    expect(screen.getByText(/Loading audit events/i)).toBeInTheDocument();
  });

  it("renders the error state via AuditFeed", () => {
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: true,
        error: new Error("boom"),
        data: undefined,
      }),
    );
    render(<AuditPage />);
    expect(
      screen.getByText("Audit feed failed to load"),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("Retry calls query.refetch", () => {
    const refetch = vi.fn();
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: true,
        error: new Error("boom"),
        data: undefined,
        refetch,
      }),
    );
    render(<AuditPage />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state when items=[]", () => {
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        data: makeListResponse([]),
      }),
    );
    render(<AuditPage />);
    expect(screen.getByText("No audit events")).toBeInTheDocument();
  });

  it("renders data rows when items has events", () => {
    const event = makeAuditEvent();
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        data: makeListResponse([event]),
      }),
    );
    render(<AuditPage />);
    expect(
      screen.getByTestId(`audit-feed-row-${event.id}`),
    ).toBeInTheDocument();
    expect(screen.getByText(event.summary)).toBeInTheDocument();
  });

  it("forwards query.data.items to AuditFeed unchanged", () => {
    const events = [
      makeAuditEvent({ id: "e1" }),
      makeAuditEvent({ id: "e2", summary: "Second event" }),
      makeAuditEvent({ id: "e3", summary: "Third event" }),
    ];
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        data: makeListResponse(events),
      }),
    );
    render(<AuditPage />);
    expect(screen.getAllByTestId(/^audit-feed-row-/)).toHaveLength(3);
  });
});

// --------------------------------------------------------------------- //
// D. Query wiring + default filters
// --------------------------------------------------------------------- //

describe("AuditPage — query wiring", () => {
  it("calls useStoreAuditQuery with currentStoreId and default filters {limit:50, offset:0}", () => {
    render(<AuditPage />);
    expect(auditHooks.useStoreAuditQuery).toHaveBeenCalled();
    const [storeIdArg, filtersArg] = vi.mocked(auditHooks.useStoreAuditQuery)
      .mock.calls[0];
    expect(storeIdArg).toBe(STORE_ID);
    expect(filtersArg).toEqual({ limit: 50, offset: 0 });
  });

  it("re-invokes useStoreAuditQuery after a source filter change", () => {
    render(<AuditPage />);
    // First mount: default filters.
    const firstCallFilters = vi.mocked(auditHooks.useStoreAuditQuery).mock
      .calls[0][1];
    expect(firstCallFilters).toEqual({ limit: 50, offset: 0 });

    fireEvent.click(screen.getByTestId("audit-filter-source-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Inventory" }));

    // After the state update, the hook is invoked again with the
    // new filters snapshot. Take the latest invocation.
    const lastCall = vi.mocked(auditHooks.useStoreAuditQuery).mock.calls
      .at(-1);
    expect(lastCall?.[0]).toBe(STORE_ID);
    expect(lastCall?.[1]).toEqual({
      limit: 50,
      offset: 0,
      source: "inventory",
    });
  });

  it("re-invokes useStoreAuditQuery after an action filter change (and resets offset)", () => {
    render(<AuditPage />);
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "receipt" },
    });
    const lastCall = vi.mocked(auditHooks.useStoreAuditQuery).mock.calls
      .at(-1);
    expect(lastCall?.[1]).toEqual({
      limit: 50,
      offset: 0,
      action: "receipt",
    });
  });

  it("re-invokes useStoreAuditQuery after an actor_id filter change", () => {
    render(<AuditPage />);
    fireEvent.change(screen.getByTestId("audit-filter-actor-id"), {
      target: { value: ACTOR_ID },
    });
    const lastCall = vi.mocked(auditHooks.useStoreAuditQuery).mock.calls
      .at(-1);
    expect(lastCall?.[1]).toEqual({
      limit: 50,
      offset: 0,
      actor_id: ACTOR_ID,
    });
  });

  it("re-invokes useStoreAuditQuery after a date_from filter change", () => {
    render(<AuditPage />);
    fireEvent.change(screen.getByTestId("audit-filter-date-from"), {
      target: { value: "2026-01-01" },
    });
    const lastCall = vi.mocked(auditHooks.useStoreAuditQuery).mock.calls
      .at(-1);
    expect(lastCall?.[1]).toEqual({
      limit: 50,
      offset: 0,
      date_from: "2026-01-01",
    });
  });

  it("re-invokes useStoreAuditQuery after a date_to filter change", () => {
    render(<AuditPage />);
    fireEvent.change(screen.getByTestId("audit-filter-date-to"), {
      target: { value: "2026-02-01" },
    });
    const lastCall = vi.mocked(auditHooks.useStoreAuditQuery).mock.calls
      .at(-1);
    expect(lastCall?.[1]).toEqual({
      limit: 50,
      offset: 0,
      date_to: "2026-02-01",
    });
  });

  it("preserves limit and keeps offset at 0 across filter changes", () => {
    render(<AuditPage />);
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "sale" },
    });
    const lastCall = vi.mocked(auditHooks.useStoreAuditQuery).mock.calls
      .at(-1);
    expect(lastCall?.[1]?.limit).toBe(50);
    expect(lastCall?.[1]?.offset).toBe(0);
  });

  it("disables AuditFilters while the query is loading", () => {
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: true,
        isFetching: true,
        isError: false,
        data: undefined,
      }),
    );
    render(<AuditPage />);
    expect(screen.getByTestId("audit-filter-action")).toBeDisabled();
    expect(
      screen.getByTestId("audit-filter-source-trigger"),
    ).toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// E. Real three-source rendering
// --------------------------------------------------------------------- //

describe("AuditPage — unified three-source rendering", () => {
  it("renders inventory + order + product_compliance events with correct badges", () => {
    const events: AuditEvent[] = [
      makeAuditEvent({
        id: "e-inv",
        source: "inventory",
        action: "receipt",
        entity_type: "inventory_item",
        summary: "Inventory receipt: +10 units (after 10)",
      }),
      makeAuditEvent({
        id: "e-ord",
        source: "order",
        action: "order_canceled",
        entity_type: "order",
        summary: "Order order_canceled: pending → canceled",
      }),
      makeAuditEvent({
        id: "e-comp",
        source: "product_compliance",
        action: "compliance_changed",
        entity_type: "product",
        summary: "Compliance: allowed/true → restricted/false",
        actor_id: null,
      }),
    ];
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        data: makeListResponse(events, { total: 3 }),
      }),
    );
    render(<AuditPage />);

    // Each source produces a visible AuditEventBadge in its row.
    expect(
      screen.getByTestId("audit-event-badge-inventory"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("audit-event-badge-order"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("audit-event-badge-product_compliance"),
    ).toBeInTheDocument();

    // Humanized labels visible inside each row's Source cell. The
    // source select renders the same words as option labels, and
    // some rows have entity labels that share the word ("Order"),
    // so we scope each assertion to its source cell.
    expect(
      within(screen.getByTestId("audit-feed-source-e-inv")).getByText(
        "Inventory",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("audit-feed-source-e-ord")).getByText(
        "Order",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("audit-feed-source-e-comp")).getByText(
        "Compliance",
      ),
    ).toBeInTheDocument();

    // Summaries visible.
    expect(
      screen.getByText("Inventory receipt: +10 units (after 10)"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Order order_canceled: pending → canceled"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Compliance: allowed/true → restricted/false"),
    ).toBeInTheDocument();

    // Compliance row has null actor → "System".
    expect(
      screen.getByTestId("audit-feed-actor-e-comp"),
    ).toHaveTextContent("System");
  });
});

// --------------------------------------------------------------------- //
// F. Anti-fake / negative-surface guards
// --------------------------------------------------------------------- //

describe("AuditPage — anti-fake and negative-surface guards", () => {
  it("does not render backend-required primary copy", () => {
    render(<AuditPage />);
    expect(
      screen.queryByText(/backend required/i),
    ).toBeNull();
    expect(
      screen.queryByText(/unified audit not available/i),
    ).toBeNull();
    expect(
      screen.queryByText(/only inventory logs are available/i),
    ).toBeNull();
  });

  it("does not render unsupported global feeds", () => {
    render(<AuditPage />);
    expect(screen.queryByTestId(/global-audit-feed/i)).toBeNull();
    expect(screen.queryByTestId(/activity-feed/i)).toBeNull();
  });

  it("does not render role/permission gated copy", () => {
    render(<AuditPage />);
    expect(
      screen.queryByText(/you do not have permission/i),
    ).toBeNull();
    expect(
      screen.queryByText(/insufficient permissions/i),
    ).toBeNull();
  });

  it("does not render invented actor/store/severity fields", () => {
    const event = makeAuditEvent();
    vi.mocked(auditHooks.useStoreAuditQuery).mockReturnValue(
      asQueryResult<AuditListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        data: makeListResponse([event]),
      }),
    );
    const { container } = render(<AuditPage />);
    const text = container.textContent ?? "";
    for (const forbidden of [
      "actor_name",
      "actor_email",
      "store_name",
      "severity",
      "Severity",
    ]) {
      expect(text).not.toMatch(new RegExp(forbidden));
    }
  });
});

// --------------------------------------------------------------------- //
// G. Source-level architecture guards (file-scan)
// --------------------------------------------------------------------- //

describe("AuditPage — architecture", () => {
  it("does NOT import or reference useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AuditPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    // Strip block + line comments so rationale text does not produce
    // false positives.
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\bcanCreate\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bcanViewAudit\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bUSER_CREATION_MATRIX\b/);
    expect(code).not.toMatch(/\.role\s*===\s*["']/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT aggregate, sort, or merge logs in code", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AuditPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\.sort\s*\(/);
    expect(code).not.toMatch(/\.reverse\s*\(/);
    expect(code).not.toMatch(/\.concat\s*\(/);
    expect(code).not.toMatch(/\.reduce\s*\(/);
    expect(code).not.toMatch(/\.filter\s*\(/);
    expect(code).not.toMatch(/\baggregate\s*\(/);
  });

  it("does NOT call the API or query layer directly", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AuditPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // The page must consume `useStoreAuditQuery`, never the raw
    // `getStoreAudit` function or `apiRequest`.
    expect(code).not.toMatch(/\bgetStoreAudit\s*\(/);
    expect(code).not.toMatch(/\bapiRequest\b/);
  });

  it("router maps /app/store/audit to AuditPage and no longer references AuditPlaceholderPage", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "..",
      "..",
      "..",
      "app",
      "router.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    expect(source).toMatch(
      /import\s+AuditPage\s+from\s+["']@\/features\/audit\/pages\/AuditPage["']/,
    );
    expect(source).not.toMatch(/AuditPlaceholderPage/);
    expect(source).toMatch(
      /path:\s*["']audit["']\s*,\s*element:\s*<AuditPage\s*\/>/,
    );
  });
});
