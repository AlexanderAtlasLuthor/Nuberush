// F2.11-M2.6: tests for OrderAuditLogsPanel.
//
// Strategy mirrors features/audit/components/__tests__/StoreInventoryLogsPanel.test.tsx
// — stub `../../hooks` so the panel renders the mocked `useOrderAuditLogs`
// result without touching TanStack Query, the api layer, or the network.
// We assert each render branch (loading, error, empty, success) and
// lock the table column shape, the backend pass-through (rows render
// in hook-returned order with no client-side resort), and the
// nullable-field fallbacks.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { OrderAuditLogsPanel } from "../OrderAuditLogsPanel";
import * as ordersHooks from "../../hooks";
import type { OrderAuditLogRead } from "../../types";

vi.mock("../../hooks", () => ({
  useOrderAuditLogs: vi.fn(),
}));

const ORDER_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "22222222-2222-2222-2222-222222222222";
const EM_DASH = "—";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeLog(
  overrides: Partial<OrderAuditLogRead> = {},
): OrderAuditLogRead {
  return {
    id: "log-1",
    order_id: ORDER_ID,
    store_id: STORE_ID,
    performed_by_user_id: "user-1",
    previous_status: "pending",
    new_status: "accepted",
    action: "status_changed",
    reason: "manager approved",
    created_at: "2026-05-04T08:30:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(ordersHooks.useOrderAuditLogs).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Loading branch
// --------------------------------------------------------------------- //

describe("OrderAuditLogsPanel — loading", () => {
  it("renders the loading state while the query is pending", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: true,
        isError: false,
        data: undefined,
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    expect(screen.getByText(/loading audit log/i)).toBeInTheDocument();
    // Table not rendered while loading.
    expect(screen.queryByRole("table")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Error branch
// --------------------------------------------------------------------- //

describe("OrderAuditLogsPanel — error", () => {
  it("renders the backend ApiError detail through getApiErrorMessage", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: true,
        error: new ApiError({
          status: 403,
          message: "You do not have access to this store.",
        }),
        data: undefined,
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    expect(
      screen.getByText(/audit log failed to load/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/you do not have access to this store\./i),
    ).toBeInTheDocument();
  });

  it("calls refetch from the hook when the Retry button is clicked", () => {
    const refetch = vi.fn();
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: true,
        error: new ApiError({ status: 500, message: "boom" }),
        data: undefined,
        refetch: refetch as never,
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

// --------------------------------------------------------------------- //
// Empty branch
// --------------------------------------------------------------------- //

describe("OrderAuditLogsPanel — empty", () => {
  it("renders the empty state when the response array is empty", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    expect(screen.getByText(/no audit entries/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /no state transitions have been recorded for this order yet/i,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Hook contract
// --------------------------------------------------------------------- //

describe("OrderAuditLogsPanel — hook contract", () => {
  it("calls useOrderAuditLogs with the provided orderId", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    expect(ordersHooks.useOrderAuditLogs).toHaveBeenCalledTimes(1);
    expect(ordersHooks.useOrderAuditLogs).toHaveBeenCalledWith(ORDER_ID);
  });
});

// --------------------------------------------------------------------- //
// Success branch — table shape
// --------------------------------------------------------------------- //

describe("OrderAuditLogsPanel — success", () => {
  it("renders the table headers in the documented column order", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [makeLog()],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    const headers = screen
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers).toEqual([
      "Previous",
      "New",
      "Action",
      "Reason",
      "Performed by",
      "Created at",
    ]);
  });

  it("renders one row per log with all six fields populated", () => {
    const log = makeLog();
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [log],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    // Skip the header row (index 0); body rows follow.
    const allRows = screen.getAllByRole("row");
    expect(allRows.length).toBe(2);
    const bodyRow = allRows[1];

    expect(within(bodyRow).getByText("pending")).toBeInTheDocument();
    expect(within(bodyRow).getByText("accepted")).toBeInTheDocument();
    expect(within(bodyRow).getByText("status_changed")).toBeInTheDocument();
    expect(within(bodyRow).getByText("manager approved")).toBeInTheDocument();
    expect(within(bodyRow).getByText("user-1")).toBeInTheDocument();
    expect(
      within(bodyRow).getByText("2026-05-04T08:30:00Z"),
    ).toBeInTheDocument();
  });

  it("renders em-dash when previous_status is null (e.g. order_created row)", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [
          makeLog({
            id: "creation",
            previous_status: null,
            new_status: "pending",
            action: "order_created",
            reason: null,
          }),
        ],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    // Column 0 = Previous; null → em-dash.
    expect(cells[0]).toHaveTextContent(EM_DASH);
    // Column 1 = New; never null per the wire contract.
    expect(cells[1]).toHaveTextContent("pending");
  });

  it("renders em-dash when reason is null", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "no-reason", reason: null })],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    // Column 3 = Reason (after Previous, New, Action).
    expect(cells[3]).toHaveTextContent(EM_DASH);
  });

  it("renders em-dash when performed_by_user_id is null (system-initiated row)", () => {
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [
          makeLog({ id: "system", performed_by_user_id: null }),
        ],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    // Column 4 = Performed by.
    expect(cells[4]).toHaveTextContent(EM_DASH);
  });

  it("renders rows in the order returned by the hook (no client-side resort)", () => {
    // Backend orders ASC by created_at server-side
    // (services/orders.list_order_audit_logs). Feed an unsorted slice
    // to confirm the panel renders exactly what the hook returned.
    const a = makeLog({
      id: "row-a",
      action: "order_created",
      created_at: "2026-05-01T00:00:00Z",
    });
    const b = makeLog({
      id: "row-b",
      action: "status_changed",
      created_at: "2026-05-02T00:00:00Z",
    });
    const c = makeLog({
      id: "row-c",
      action: "order_canceled",
      created_at: "2026-05-03T00:00:00Z",
    });
    vi.mocked(ordersHooks.useOrderAuditLogs).mockReturnValue(
      asQueryResult<OrderAuditLogRead[]>({
        isLoading: false,
        isError: false,
        data: [c, a, b],
      }),
    );

    render(<OrderAuditLogsPanel orderId={ORDER_ID} />);

    const bodyRows = screen.getAllByRole("row").slice(1);
    expect(bodyRows.length).toBe(3);
    // Action column is index 2 — it's unique per row in this fixture
    // and uniquely identifies the source log.
    expect(
      within(bodyRows[0]).getByText("order_canceled"),
    ).toBeInTheDocument();
    expect(
      within(bodyRows[1]).getByText("order_created"),
    ).toBeInTheDocument();
    expect(
      within(bodyRows[2]).getByText("status_changed"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("OrderAuditLogsPanel — architecture", () => {
  it("does NOT import or reference useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "OrderAuditLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    // Strip block + line comments so rationale text in the file
    // header doesn't trigger false positives.
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\.role\s*===/);
    expect(code).not.toMatch(/\bcanView\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bcanCreate\b/);
    expect(code).not.toMatch(/\bcanViewAudit\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT include cross-resource audit derivation tokens or transition matrix", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "OrderAuditLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // No global / cross-resource audit shapes — those would imply
    // client-side merge of order + inventory + compliance audit rows.
    expect(code).not.toMatch(/\bAuditEvent\b/);
    expect(code).not.toMatch(/\bGlobalAuditEvent\b/);
    expect(code).not.toMatch(/\bActivityFeedEvent\b/);
    expect(code).not.toMatch(/\bActivityFeed\b/);
    expect(code).not.toMatch(/\bAuditUnion\b/);
    expect(code).not.toMatch(/\bAuditFeedItem\b/);

    // No transition matrix duplicated here — that's affordance work
    // for OrderActionsBar, not audit rendering.
    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/NEXT_FORWARD_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/CANCELABLE_STATUSES\s*=/);
    expect(code).not.toMatch(/RETURNABLE_STATUSES\s*=/);
  });

  it("does NOT sort, reverse, filter, reduce, or aggregate the logs array", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "OrderAuditLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // Catch any client-side mutation/reordering of the logs array.
    expect(code).not.toMatch(/logs\s*\.\s*sort\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*reverse\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*filter\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*reduce\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*concat\s*\(/);
    expect(code).not.toMatch(/\baggregate\s*\(/);
  });
});
