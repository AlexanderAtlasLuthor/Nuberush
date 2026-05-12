// F2.11-M2.3: tests for InventoryItemLogsPanel.
//
// Strategy mirrors features/audit/components/__tests__/StoreInventoryLogsPanel.test.tsx
// and features/orders/components/__tests__/OrderAuditLogsPanel.test.tsx —
// stub `../../hooks` so the panel renders the mocked `useInventoryItemLogs`
// result without touching TanStack Query, the api layer, or the network.
// Adds a pagination dimension because this panel pages over the fetched
// server batch (NOT a database total). The pagination is explicitly
// allowed by the M2.3 brief as honest in-memory paging — assertions
// must treat `total` as fetched-batch count only.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { InventoryItemLogsPanel } from "../InventoryItemLogsPanel";
import * as inventoryHooks from "../../hooks";
import type { InventoryLogEntry } from "../../types";

vi.mock("../../hooks", () => ({
  useInventoryItemLogs: vi.fn(),
}));

const ITEM_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "22222222-2222-2222-2222-222222222222";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const EM_DASH = "—";

// Mirrors the panel's documented constant. Exposed here so pagination
// assertions don't drift if the brief changes — but the test does NOT
// import the constant from the implementation; the brief specifies 20.
const PAGE_SIZE = 20;

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeLog(
  overrides: Partial<InventoryLogEntry> = {},
): InventoryLogEntry {
  return {
    id: "log-1",
    inventory_item_id: ITEM_ID,
    store_id: STORE_ID,
    variant_id: VARIANT_ID,
    performed_by_user_id: "user-1",
    movement_type: "receipt",
    quantity_delta: 10,
    quantity_after: 50,
    reason: "Inbound shipment",
    reference_type: "purchase_order",
    reference_id: "po-7",
    created_at: "2026-05-04T08:30:00Z",
    ...overrides,
  };
}

/**
 * Generate `n` logs with unique ids and unique reason strings so that
 * pagination tests can identify which page is currently rendered by
 * grepping for the per-row reason marker.
 */
function makeLogBatch(n: number): InventoryLogEntry[] {
  return Array.from({ length: n }, (_, i) =>
    makeLog({
      id: `log-${i + 1}`,
      reason: `entry-${i + 1}`,
    }),
  );
}

beforeEach(() => {
  vi.mocked(inventoryHooks.useInventoryItemLogs).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Loading branch
// --------------------------------------------------------------------- //

describe("InventoryItemLogsPanel — loading", () => {
  it("renders the loading state while the query is pending", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: true,
        isError: false,
        data: undefined,
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    expect(screen.getByText(/loading audit log/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByTestId("inventory-logs-page-meta")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Error branch
// --------------------------------------------------------------------- //

describe("InventoryItemLogsPanel — error", () => {
  it("renders the backend ApiError detail through getApiErrorMessage", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: true,
        error: new ApiError({
          status: 403,
          message: "You do not have access to this store.",
        }),
        data: undefined,
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    expect(
      screen.getByText(/audit log failed to load/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/you do not have access to this store\./i),
    ).toBeInTheDocument();
  });

  it("calls refetch from the hook when the Retry button is clicked", () => {
    const refetch = vi.fn();
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: true,
        error: new ApiError({ status: 500, message: "boom" }),
        data: undefined,
        refetch: refetch as never,
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

// --------------------------------------------------------------------- //
// Empty branch
// --------------------------------------------------------------------- //

describe("InventoryItemLogsPanel — empty", () => {
  it("renders the empty state when the response array is empty", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    expect(screen.getByText(/no audit entries/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /no stock movements have been recorded for this item yet/i,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByTestId("inventory-logs-page-meta")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Hook contract
// --------------------------------------------------------------------- //

describe("InventoryItemLogsPanel — hook contract", () => {
  it("calls useInventoryItemLogs with the provided itemId and { limit: 200 }", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    expect(inventoryHooks.useInventoryItemLogs).toHaveBeenCalledTimes(1);
    expect(inventoryHooks.useInventoryItemLogs).toHaveBeenCalledWith(
      ITEM_ID,
      { limit: 200 },
    );
  });
});

// --------------------------------------------------------------------- //
// Success branch — table shape
// --------------------------------------------------------------------- //

describe("InventoryItemLogsPanel — success", () => {
  it("renders the table headers in the documented column order", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog()],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    const headers = screen
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers).toEqual([
      "Movement",
      "Δ qty",
      "Qty after",
      "Reason",
      "Reference",
      "Performed by",
      "Created at",
    ]);
  });

  it("renders one row per log with all seven fields populated", () => {
    const log = makeLog();
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [log],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    // Skip header row at index 0; body rows follow.
    const allRows = screen.getAllByRole("row");
    expect(allRows.length).toBe(2);
    const bodyRow = allRows[1];

    expect(within(bodyRow).getByText("receipt")).toBeInTheDocument();
    // Δ qty is rendered via String(value) — positive numbers do NOT
    // get an explicit "+" prefix here. Different convention from
    // StoreInventoryLogsPanel; locked deliberately so a future drift
    // toward signed formatting fails this test loudly.
    expect(within(bodyRow).getByText("10")).toBeInTheDocument();
    expect(within(bodyRow).getByText("50")).toBeInTheDocument();
    expect(
      within(bodyRow).getByText("Inbound shipment"),
    ).toBeInTheDocument();
    expect(within(bodyRow).getByText("purchase_order")).toBeInTheDocument();
    expect(within(bodyRow).getByText("po-7")).toBeInTheDocument();
    expect(within(bodyRow).getByText("user-1")).toBeInTheDocument();
    expect(
      within(bodyRow).getByText("2026-05-04T08:30:00Z"),
    ).toBeInTheDocument();
  });

  it("renders positive quantity_delta verbatim (no explicit + sign)", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "pos", quantity_delta: 12 })],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    // Column 1 = Δ qty (after Movement at index 0).
    expect(cells[1]).toHaveTextContent("12");
    // No explicit plus sign.
    expect(cells[1].textContent).not.toMatch(/^\+/);
  });

  it("renders negative quantity_delta with leading minus", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "neg", quantity_delta: -3 })],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    expect(cells[1]).toHaveTextContent("-3");
  });

  it("renders em-dash when reason is null", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "no-reason", reason: null })],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    // Column 3 = Reason (after Movement, Δ qty, Qty after).
    expect(cells[3]).toHaveTextContent(EM_DASH);
  });

  it("renders em-dash when reference_type and reference_id are both null", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [
          makeLog({
            id: "no-ref",
            reference_type: null,
            reference_id: null,
          }),
        ],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    // Column 4 = Reference.
    expect(cells[4]).toHaveTextContent(EM_DASH);
  });

  it("renders em-dash when performed_by_user_id is null (system-initiated movement)", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "system", performed_by_user_id: null })],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    const bodyRow = screen.getAllByRole("row")[1];
    const cells = within(bodyRow).getAllByRole("cell");
    // Column 5 = Performed by.
    expect(cells[5]).toHaveTextContent(EM_DASH);
  });

  it("renders rows in the order returned by the hook (no client-side resort)", () => {
    // Backend orders DESC by created_at server-side
    // (services/inventory.list_inventory_logs_for_item). Feed an
    // out-of-order slice to confirm the panel renders exactly what
    // the hook returned.
    const a = makeLog({
      id: "row-a",
      reason: "first-by-time",
      created_at: "2026-05-01T00:00:00Z",
    });
    const b = makeLog({
      id: "row-b",
      reason: "second-by-time",
      created_at: "2026-05-02T00:00:00Z",
    });
    const c = makeLog({
      id: "row-c",
      reason: "third-by-time",
      created_at: "2026-05-03T00:00:00Z",
    });
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [c, a, b],
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    const bodyRows = screen.getAllByRole("row").slice(1);
    expect(bodyRows.length).toBe(3);
    // Reason column is unique per row in this fixture.
    expect(
      within(bodyRows[0]).getByText("third-by-time"),
    ).toBeInTheDocument();
    expect(
      within(bodyRows[1]).getByText("first-by-time"),
    ).toBeInTheDocument();
    expect(
      within(bodyRows[2]).getByText("second-by-time"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Pagination — fetched-batch only (NOT a DB total)
//
// The panel pages in-memory over the array returned by the hook. The
// `total` displayed is the length of the fetched batch, not a DB row
// count. Tests treat it that way explicitly so a future contributor
// reading them does not mistake the meta string for a backend total.
// --------------------------------------------------------------------- //

describe("InventoryItemLogsPanel — pagination", () => {
  it("renders 'Showing 1–20 of K' on the first page when more than 20 rows are fetched", () => {
    const total = 25;
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: makeLogBatch(total),
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    // Note: en-dash "–", not hyphen "-". Implementation uses U+2013.
    expect(
      screen.getByTestId("inventory-logs-page-meta"),
    ).toHaveTextContent(`Showing 1–${PAGE_SIZE} of ${total}`);
    expect(
      screen.getAllByRole("row").slice(1).length,
    ).toBe(PAGE_SIZE);
  });

  it("disables Previous on the first page and enables Next when more than 20 rows are fetched", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: makeLogBatch(25),
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    expect(screen.getByTestId("inventory-logs-prev")).toBeDisabled();
    expect(screen.getByTestId("inventory-logs-next")).not.toBeDisabled();
  });

  it("clicking Next moves to rows 21–N from the fetched batch", () => {
    const total = 25;
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: makeLogBatch(total),
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    fireEvent.click(screen.getByTestId("inventory-logs-next"));

    expect(
      screen.getByTestId("inventory-logs-page-meta"),
    ).toHaveTextContent(`Showing 21–${total} of ${total}`);
    // Page 2 has 5 entries (rows 21..25). Identify them by their unique
    // reason strings from makeLogBatch.
    const bodyRows = screen.getAllByRole("row").slice(1);
    expect(bodyRows.length).toBe(5);
    expect(
      within(bodyRows[0]).getByText("entry-21"),
    ).toBeInTheDocument();
    expect(
      within(bodyRows[4]).getByText("entry-25"),
    ).toBeInTheDocument();
  });

  it("Previous becomes enabled after Next, and Next disables on the final page", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: makeLogBatch(25),
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    fireEvent.click(screen.getByTestId("inventory-logs-next"));

    expect(screen.getByTestId("inventory-logs-prev")).not.toBeDisabled();
    expect(screen.getByTestId("inventory-logs-next")).toBeDisabled();
  });

  it("clicking Previous after Next returns to rows 1–20", () => {
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: makeLogBatch(25),
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    fireEvent.click(screen.getByTestId("inventory-logs-next"));
    fireEvent.click(screen.getByTestId("inventory-logs-prev"));

    expect(
      screen.getByTestId("inventory-logs-page-meta"),
    ).toHaveTextContent("Showing 1–20 of 25");
    expect(screen.getByTestId("inventory-logs-prev")).toBeDisabled();
    expect(screen.getByTestId("inventory-logs-next")).not.toBeDisabled();
  });

  it("disables both Previous and Next when fetched batch fits in a single page", () => {
    // 5 rows ≤ PAGE_SIZE → only one page exists.
    vi.mocked(inventoryHooks.useInventoryItemLogs).mockReturnValue(
      asQueryResult<InventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: makeLogBatch(5),
      }),
    );

    render(<InventoryItemLogsPanel inventoryItemId={ITEM_ID} />);

    expect(
      screen.getByTestId("inventory-logs-page-meta"),
    ).toHaveTextContent("Showing 1–5 of 5");
    expect(screen.getByTestId("inventory-logs-prev")).toBeDisabled();
    expect(screen.getByTestId("inventory-logs-next")).toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("InventoryItemLogsPanel — architecture", () => {
  it("does NOT import or reference useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "InventoryItemLogsPanel.tsx",
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

  it("does NOT include cross-resource audit derivation tokens", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "InventoryItemLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\bAuditEvent\b/);
    expect(code).not.toMatch(/\bGlobalAuditEvent\b/);
    expect(code).not.toMatch(/\bActivityFeedEvent\b/);
    expect(code).not.toMatch(/\bActivityFeed\b/);
    expect(code).not.toMatch(/\bAuditUnion\b/);
    expect(code).not.toMatch(/\bAuditFeedItem\b/);
  });

  it("does NOT recompute stock authority (no quantity_on_hand - quantity_reserved, no quantity_after derivation)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "InventoryItemLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // No "available" derivation from quantity fields.
    expect(code).not.toMatch(/quantity_on_hand\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_reserved\s*[-+*/]/);
    // No client-side recomputation of `quantity_after` from the wire
    // (e.g. summing prior deltas). The wire field is rendered as-is.
    expect(code).not.toMatch(/quantity_after\s*=/);
    expect(code).not.toMatch(/quantity_after\s*[-+*/]/);
  });

  it("does NOT sort, reverse, filter, reduce, or aggregate the logs array (slice is allowed for in-memory paging)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "InventoryItemLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // Forbidden — would mean reordering or aggregating backend-decided
    // truth on the client.
    expect(code).not.toMatch(/logs\s*\.\s*sort\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*reverse\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*filter\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*reduce\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*concat\s*\(/);
    expect(code).not.toMatch(/\baggregate\s*\(/);
  });
});
