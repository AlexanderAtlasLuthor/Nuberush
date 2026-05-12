// F2.10.3: tests for StoreInventoryLogsPanel.
//
// Strategy mirrors features/orders/components/__tests__/OrderAuditLogsPanel
// and features/inventory/components/InventoryItemLogsPanel: stub
// `../../hooks` so the panel renders the mocked
// `useStoreInventoryLogsQuery` result without touching TanStack Query,
// the api layer, or the network. We assert each branch (no-store,
// loading, error, empty, success) and lock in the table column shape.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { StoreInventoryLogsPanel } from "../StoreInventoryLogsPanel";
import * as auditHooks from "../../hooks";
import type { StoreInventoryLogEntry } from "../../types";

vi.mock("../../hooks", () => ({
  useStoreInventoryLogsQuery: vi.fn(),
  // queryKeys re-export is imported by some other panels in the
  // module; provide a stub so the mock barrel is type-coherent.
  auditKeys: { all: ["audit"] as const },
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeLog(
  overrides: Partial<StoreInventoryLogEntry> = {},
): StoreInventoryLogEntry {
  return {
    id: "log-1",
    inventory_item_id: "item-1",
    store_id: STORE_ID,
    variant_id: "variant-1",
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

beforeEach(() => {
  vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// No-store-selected branch
// --------------------------------------------------------------------- //

describe("StoreInventoryLogsPanel — no store selected", () => {
  it.each([
    ["null", null],
    ["undefined", undefined],
    ["empty string", ""],
    ["whitespace only", "   "],
  ] as const)(
    "renders the no-store-selected state when storeId is %s",
    (_label, storeId) => {
      // Even when the hook is mocked to a "loading" shape, the panel
      // must show the no-store-selected branch first so it never
      // claims to be loading data it cannot fetch.
      vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
        asQueryResult<StoreInventoryLogEntry[]>({
          isLoading: true,
          isError: false,
          data: undefined,
          error: null,
        }),
      );

      render(<StoreInventoryLogsPanel storeId={storeId} />);

      expect(screen.getByText(/no store selected/i)).toBeInTheDocument();
      expect(
        screen.getByText(/select a store to view inventory logs/i),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/loading inventory logs/i),
      ).toBeNull();
      expect(
        screen.queryByTestId("store-inventory-logs-table-wrapper"),
      ).toBeNull();
    },
  );

  it("passes storeId and limit through to useStoreInventoryLogsQuery", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} limit={50} />);

    expect(auditHooks.useStoreInventoryLogsQuery).toHaveBeenCalledTimes(1);
    expect(auditHooks.useStoreInventoryLogsQuery).toHaveBeenCalledWith({
      storeId: STORE_ID,
      limit: 50,
    });
  });

  it("forwards a null storeId to the hook (the hook's enabled guard handles it)", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: undefined,
      }),
    );

    render(<StoreInventoryLogsPanel storeId={null} />);

    expect(auditHooks.useStoreInventoryLogsQuery).toHaveBeenCalledWith({
      storeId: null,
      limit: undefined,
    });
  });
});

// --------------------------------------------------------------------- //
// Loading branch
// --------------------------------------------------------------------- //

describe("StoreInventoryLogsPanel — loading", () => {
  it("renders the loading state while the query is pending", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: true,
        isError: false,
        data: undefined,
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByText(/loading inventory logs/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-inventory-logs-table-wrapper"),
    ).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Error branch
// --------------------------------------------------------------------- //

describe("StoreInventoryLogsPanel — error", () => {
  it("surfaces the backend ApiError detail through getApiErrorMessage", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: true,
        error: new ApiError({
          status: 403,
          message: "You do not have access to this store.",
        }),
        data: undefined,
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByText(/inventory logs failed to load/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/you do not have access to this store\./i),
    ).toBeInTheDocument();
  });

  it("does NOT show error when no store is selected (no-store branch wins)", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: true,
        error: new ApiError({ status: 500, message: "boom" }),
      }),
    );

    render(<StoreInventoryLogsPanel storeId={null} />);

    expect(screen.queryByText(/boom/i)).toBeNull();
    expect(screen.getByText(/no store selected/i)).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Empty branch
// --------------------------------------------------------------------- //

describe("StoreInventoryLogsPanel — empty", () => {
  it("renders the empty state when the response array is empty", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByText(/no inventory logs found for this store yet/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/no audit events/i)).toBeNull();
    expect(
      screen.queryByTestId("store-inventory-logs-table-wrapper"),
    ).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Success branch
// --------------------------------------------------------------------- //

describe("StoreInventoryLogsPanel — success", () => {
  it("renders the table headers in the documented column order", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog()],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    const headers = screen.getAllByRole("columnheader").map(
      (h) => h.textContent,
    );
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

  it("renders one row per log with all columns populated", () => {
    const log = makeLog();
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [log],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    const row = screen.getByTestId(`store-inventory-logs-row-${log.id}`);
    expect(within(row).getByText("receipt")).toBeInTheDocument();
    expect(
      within(row).getByTestId(`store-inventory-logs-delta-${log.id}`),
    ).toHaveTextContent("+10");
    expect(
      within(row).getByTestId(`store-inventory-logs-qty-after-${log.id}`),
    ).toHaveTextContent("50");
    expect(
      within(row).getByTestId(`store-inventory-logs-reason-${log.id}`),
    ).toHaveTextContent("Inbound shipment");
    expect(
      within(row).getByTestId(`store-inventory-logs-reference-${log.id}`),
    ).toHaveTextContent(/purchase_order\s+po-7/);
    expect(
      within(row).getByTestId(`store-inventory-logs-performer-${log.id}`),
    ).toHaveTextContent("user-1");
    expect(
      within(row).getByTestId(`store-inventory-logs-created-${log.id}`),
    ).toHaveTextContent("2026-05-04T08:30:00Z");
  });

  it("renders quantity_delta with explicit + sign when positive", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "pos", quantity_delta: 12 })],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByTestId("store-inventory-logs-delta-pos"),
    ).toHaveTextContent("+12");
  });

  it("renders quantity_delta with explicit - sign when negative", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "neg", quantity_delta: -3 })],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByTestId("store-inventory-logs-delta-neg"),
    ).toHaveTextContent("-3");
  });

  it("renders em-dash when reason is null", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "no-reason", reason: null })],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByTestId("store-inventory-logs-reason-no-reason"),
    ).toHaveTextContent("—");
  });

  it("renders em-dash when reference_type and reference_id are both null", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
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

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByTestId("store-inventory-logs-reference-no-ref"),
    ).toHaveTextContent("—");
  });

  it("renders 'System' when performed_by_user_id is null", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog({ id: "system", performed_by_user_id: null })],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.getByTestId("store-inventory-logs-performer-system"),
    ).toHaveTextContent("System");
  });

  it("renders rows in the order returned by the hook (no client-side resort)", () => {
    const a = makeLog({ id: "a", created_at: "2026-05-01T00:00:00Z" });
    const b = makeLog({ id: "b", created_at: "2026-05-02T00:00:00Z" });
    const c = makeLog({ id: "c", created_at: "2026-05-03T00:00:00Z" });
    // Backend already orders DESC by created_at; we render exactly
    // what the hook returns.
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [c, a, b],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    const rows = screen.getAllByTestId(/^store-inventory-logs-row-/);
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual([
      "store-inventory-logs-row-c",
      "store-inventory-logs-row-a",
      "store-inventory-logs-row-b",
    ]);
  });
});

// --------------------------------------------------------------------- //
// Negative-surface guards (no global feed language, no fake filters,
// no fake pagination, no count)
// --------------------------------------------------------------------- //

describe("StoreInventoryLogsPanel — does NOT render global / unsupported surfaces", () => {
  it("never renders global audit feed copy", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog()],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(screen.queryByText(/global audit/i)).toBeNull();
    expect(screen.queryByText(/audit events feed/i)).toBeNull();
    expect(screen.queryByText(/activity feed/i)).toBeNull();
    expect(screen.queryByText(/cross-resource/i)).toBeNull();
  });

  it("never renders unsupported filter UI", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog()],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(
      screen.queryByLabelText(/event type/i),
    ).toBeNull();
    expect(
      screen.queryByLabelText(/entity type/i),
    ).toBeNull();
    expect(screen.queryByLabelText(/^user$/i)).toBeNull();
    expect(screen.queryByLabelText(/from/i)).toBeNull();
    expect(screen.queryByLabelText(/to/i)).toBeNull();
  });

  it("never renders offset / total / count UI", () => {
    vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
      asQueryResult<StoreInventoryLogEntry[]>({
        isLoading: false,
        isError: false,
        data: [makeLog(), makeLog({ id: "log-2" })],
      }),
    );

    render(<StoreInventoryLogsPanel storeId={STORE_ID} />);

    expect(screen.queryByText(/showing\s+\d+(–|-)\d+\s+of\s+\d+/i)).toBeNull();
    expect(screen.queryByText(/total:\s*\d+/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /next/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /previous/i })).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("StoreInventoryLogsPanel — architecture", () => {
  it("does NOT import or reference useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "StoreInventoryLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    // Strip block + line comments so rationale text in the file
    // header doesn't trigger false positives.
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\buseStoreContext\b/);
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

  it("does NOT sort, merge, or aggregate logs in code", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "StoreInventoryLogsPanel.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // Catch any client-side mutation/reordering of the logs array.
    expect(code).not.toMatch(/logs\s*\.\s*sort\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*reverse\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*concat\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*reduce\s*\(/);
    expect(code).not.toMatch(/logs\s*\.\s*filter\s*\(/);
    expect(code).not.toMatch(/\baggregate\s*\(/);
  });
});
