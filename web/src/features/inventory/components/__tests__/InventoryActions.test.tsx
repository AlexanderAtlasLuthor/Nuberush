// F2.11-M2.2: tests for InventoryActions.
//
// InventoryActions is a pure DropdownMenu + modal-open dispatcher. Two
// test-doubling decisions:
//
//   1. Each child modal/panel is replaced by a tiny doppelgänger that
//      renders a marker testid + the item id when its `open` (or
//      always-mounted) state is truthy. That lets the test verify
//      "modal X opened" + "modal X received the right item" without
//      exercising the real modal's hooks.
//
//   2. `@/components/ui/dropdown-menu` is mocked to always render its
//      contents inline. Project precedent (layout-shell.test.tsx
//      lines 228–235) documents that Radix DropdownMenu cannot be
//      opened via `fireEvent` in jsdom because it listens to pointer
//      events that the testing harness does not synthesise. Mocking
//      the primitive lets us click the menu items directly and still
//      verify the wiring InventoryActions owns (trigger renders, item
//      → modal-open dispatch) — a real-Radix interaction test would
//      need `@testing-library/user-event`, which is intentionally not
//      a project dependency yet.

import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { InventoryActions } from "../InventoryActions";
import type { InventoryItem } from "../../types";

// --------------------------------------------------------------------- //
// Dropdown-menu mock — render menu inline so fireEvent.click works.
// --------------------------------------------------------------------- //

vi.mock("@/components/ui/dropdown-menu", () => {
  const Pass = ({ children }: { children?: ReactNode }) => <>{children}</>;
  const Wrap = ({
    children,
    ...rest
  }: { children?: ReactNode } & Record<string, unknown>) => (
    <div {...rest}>{children}</div>
  );
  return {
    DropdownMenu: Pass,
    DropdownMenuTrigger: Pass,
    DropdownMenuContent: Wrap,
    DropdownMenuLabel: Wrap,
    DropdownMenuSeparator: () => <hr />,
    DropdownMenuItem: ({
      children,
      onSelect,
      ...rest
    }: {
      children?: ReactNode;
      onSelect?: () => void;
    } & Record<string, unknown>) => (
      <button type="button" {...rest} onClick={() => onSelect?.()}>
        {children}
      </button>
    ),
  };
});

// --------------------------------------------------------------------- //
// Child component mocks — minimal test doubles.
// --------------------------------------------------------------------- //

vi.mock("../ReceiveStockModal", () => ({
  ReceiveStockModal: ({
    open,
    item,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    item: InventoryItem;
  }) =>
    open ? (
      <div data-testid="mock-receive-stock-modal" data-item-id={item.id}>
        receive
      </div>
    ) : null,
}));

vi.mock("../AdjustStockModal", () => ({
  AdjustStockModal: ({
    open,
    item,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    item: InventoryItem;
  }) =>
    open ? (
      <div data-testid="mock-adjust-stock-modal" data-item-id={item.id}>
        adjust
      </div>
    ) : null,
}));

vi.mock("../DamageStockModal", () => ({
  DamageStockModal: ({
    open,
    item,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    item: InventoryItem;
  }) =>
    open ? (
      <div data-testid="mock-damage-stock-modal" data-item-id={item.id}>
        damage
      </div>
    ) : null,
}));

vi.mock("../UpdateThresholdModal", () => ({
  UpdateThresholdModal: ({
    open,
    item,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    item: InventoryItem;
  }) =>
    open ? (
      <div data-testid="mock-update-threshold-modal" data-item-id={item.id}>
        threshold
      </div>
    ) : null,
}));

vi.mock("../UpdateStatusModal", () => ({
  UpdateStatusModal: ({
    open,
    item,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    item: InventoryItem;
  }) =>
    open ? (
      <div data-testid="mock-update-status-modal" data-item-id={item.id}>
        status
      </div>
    ) : null,
}));

vi.mock("../InventoryItemLogsPanel", () => ({
  InventoryItemLogsPanel: ({
    inventoryItemId,
  }: {
    inventoryItemId: string;
  }) => (
    <div
      data-testid="mock-inventory-item-logs-panel"
      data-item-id={inventoryItemId}
    >
      logs
    </div>
  ),
}));

// --------------------------------------------------------------------- //
// Fixtures
// --------------------------------------------------------------------- //

const ITEM_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "22222222-2222-2222-2222-222222222222";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const PRODUCT_ID = "44444444-4444-4444-4444-444444444444";

function makeItem(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    id: ITEM_ID,
    store_id: STORE_ID,
    variant_id: VARIANT_ID,
    quantity_on_hand: 50,
    quantity_reserved: 0,
    reorder_threshold: 10,
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

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Trigger
// --------------------------------------------------------------------- //

describe("InventoryActions — trigger", () => {
  it("renders the row action trigger with an accessible name keyed off the product name", () => {
    render(<InventoryActions item={makeItem()} />);

    const trigger = screen.getByRole("button", {
      name: /open actions for cosmic gummies/i,
    });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute(
      "data-testid",
      "inventory-row-actions-trigger",
    );
  });

  it("does not mount any child modal/panel before any action is invoked", () => {
    render(<InventoryActions item={makeItem()} />);

    expect(screen.queryByTestId("mock-receive-stock-modal")).toBeNull();
    expect(screen.queryByTestId("mock-adjust-stock-modal")).toBeNull();
    expect(screen.queryByTestId("mock-damage-stock-modal")).toBeNull();
    expect(screen.queryByTestId("mock-update-threshold-modal")).toBeNull();
    expect(screen.queryByTestId("mock-update-status-modal")).toBeNull();
    expect(
      screen.queryByTestId("mock-inventory-item-logs-panel"),
    ).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Menu items render
// --------------------------------------------------------------------- //

describe("InventoryActions — menu items", () => {
  it("renders all six documented action items", () => {
    render(<InventoryActions item={makeItem()} />);

    expect(screen.getByTestId("inventory-action-receive")).toBeInTheDocument();
    expect(screen.getByTestId("inventory-action-adjust")).toBeInTheDocument();
    expect(screen.getByTestId("inventory-action-damage")).toBeInTheDocument();
    expect(
      screen.getByTestId("inventory-action-threshold"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("inventory-action-status")).toBeInTheDocument();
    expect(screen.getByTestId("inventory-action-logs")).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Each menu item dispatches its corresponding child surface
// --------------------------------------------------------------------- //

describe("InventoryActions — action dispatch", () => {
  it.each([
    ["receive", "mock-receive-stock-modal"],
    ["adjust", "mock-adjust-stock-modal"],
    ["damage", "mock-damage-stock-modal"],
    ["threshold", "mock-update-threshold-modal"],
    ["status", "mock-update-status-modal"],
  ] as const)(
    "clicking the %s menu item opens the corresponding modal with the item prop",
    (action, modalTestId) => {
      render(<InventoryActions item={makeItem()} />);

      fireEvent.click(screen.getByTestId(`inventory-action-${action}`));

      const modal = screen.getByTestId(modalTestId);
      expect(modal).toBeInTheDocument();
      expect(modal).toHaveAttribute("data-item-id", ITEM_ID);
    },
  );

  it("clicking the logs menu item opens the logs Dialog and mounts the panel with the item id", () => {
    render(<InventoryActions item={makeItem()} />);

    fireEvent.click(screen.getByTestId("inventory-action-logs"));

    const panel = screen.getByTestId("mock-inventory-item-logs-panel");
    expect(panel).toBeInTheDocument();
    expect(panel).toHaveAttribute("data-item-id", ITEM_ID);
    // Dialog title also rendered.
    expect(screen.getByText(/^item logs$/i)).toBeInTheDocument();
  });

  it("only one modal mounts per click (six independent flags, not a state machine)", () => {
    render(<InventoryActions item={makeItem()} />);

    fireEvent.click(screen.getByTestId("inventory-action-receive"));

    expect(screen.getByTestId("mock-receive-stock-modal")).toBeInTheDocument();
    expect(screen.queryByTestId("mock-adjust-stock-modal")).toBeNull();
    expect(screen.queryByTestId("mock-damage-stock-modal")).toBeNull();
    expect(screen.queryByTestId("mock-update-threshold-modal")).toBeNull();
    expect(screen.queryByTestId("mock-update-status-modal")).toBeNull();
    expect(
      screen.queryByTestId("mock-inventory-item-logs-panel"),
    ).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("InventoryActions — architecture", () => {
  it("does NOT import or call any mutation hook directly (mutations live inside child modals)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "InventoryActions.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // Hooks barrel must not be imported here — InventoryActions
    // routes intent only; mutations live inside each modal.
    expect(code).not.toMatch(/from\s+["']\.\.\/hooks["']/);
    expect(code).not.toMatch(/\buseReceiveStockMutation\b/);
    expect(code).not.toMatch(/\buseAdjustStockMutation\b/);
    expect(code).not.toMatch(/\buseDamageStockMutation\b/);
    expect(code).not.toMatch(/\buseUpdateInventoryThresholdMutation\b/);
    expect(code).not.toMatch(/\buseUpdateInventoryStatusMutation\b/);
    expect(code).not.toMatch(/\buseInventoryItemLogs\b/);
    expect(code).not.toMatch(/\buseMutation\b/);
  });

  it("does NOT import useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "InventoryActions.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\.role\s*===/);
    expect(code).not.toMatch(/\bcanView\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bcanCreate\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT recompute stock authority or encode business logic", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "InventoryActions.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/quantity_on_hand\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_reserved\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_after\s*=/);
    // No conditional rendering keyed off status — every action is
    // shown unconditionally; the backend rejects invalid combinations.
    expect(code).not.toMatch(/item\.status\s*===/);
    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
  });
});
