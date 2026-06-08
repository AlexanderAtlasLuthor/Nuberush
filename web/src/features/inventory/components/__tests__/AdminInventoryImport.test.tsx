// F2.27.9: tests for AdminInventoryImport — the admin entry point that
// lets a platform admin pick a target store and launch the QuickBooks
// inventory import against it.
//
// We mock useAdminStoresQuery (store list) and stub InventoryImportDialog
// to a prop recorder, so these tests assert ONLY the launcher's contract:
//   - the import button is gated on a store being selected;
//   - selecting a store and clicking Import opens the dialog wired to the
//     chosen storeId;
//   - store-query loading/error/empty states disable the picker.
// The dialog's own behaviour (preview/confirm, admin toggle) is covered
// by InventoryImportDialog.test.tsx.

import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import { AdminInventoryImport } from "../AdminInventoryImport";
import * as storesHooks from "@/features/stores/hooks";
import type { StoreListResponse, StoreProfile } from "@/features/stores/types";

vi.mock("@/features/stores/hooks", () => ({
  useAdminStoresQuery: vi.fn(),
}));

// Stub the dialog so we can read the storeId it is mounted with and the
// open state — without dragging in its preview/confirm internals. It
// renders nothing until `open`, mirroring how the real dialog is hidden.
vi.mock("../InventoryImportDialog", () => ({
  InventoryImportDialog: ({
    open,
    storeId,
    onOpenChange,
  }: {
    open: boolean;
    storeId: string;
    onOpenChange: (open: boolean) => void;
  }) =>
    open ? (
      <div data-testid="import-dialog-stub" data-store-id={storeId}>
        import dialog for {storeId}
        <button type="button" onClick={() => onOpenChange(false)}>
          close
        </button>
      </div>
    ) : null,
}));

const STORE_A: StoreProfile = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Vape Shop A",
  code: "A-001",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
} as StoreProfile;

const STORE_B: StoreProfile = {
  id: "22222222-2222-2222-2222-222222222222",
  name: "Vape Shop B",
  code: "B-002",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
} as StoreProfile;

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return { refetch: vi.fn(), ...partial } as unknown as UseQueryResult<TData>;
}

function mockStores(
  partial: Partial<UseQueryResult<StoreListResponse>>,
): void {
  vi.mocked(storesHooks.useAdminStoresQuery).mockReturnValue(
    asQueryResult<StoreListResponse>(partial),
  );
}

function mockStoreList(items: StoreProfile[]): void {
  mockStores({
    isLoading: false,
    isFetching: false,
    isError: false,
    isSuccess: true,
    data: { items, total: items.length, limit: 100, offset: 0 },
  });
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminInventoryImport", () => {
  it("disables the import button until a store is selected", () => {
    mockStoreList([STORE_A, STORE_B]);
    render(<AdminInventoryImport />);

    expect(screen.getByTestId("admin-inventory-import-open")).toBeDisabled();
    // The dialog is not mounted before a store is chosen.
    expect(screen.queryByTestId("import-dialog-stub")).not.toBeInTheDocument();
  });

  it("fetches one page of stores (limit 100) for the picker", () => {
    mockStoreList([STORE_A]);
    render(<AdminInventoryImport />);
    expect(storesHooks.useAdminStoresQuery).toHaveBeenCalledWith({ limit: 100 });
  });

  it("selecting a store enables Import and opens the dialog wired to that store", () => {
    mockStoreList([STORE_A, STORE_B]);
    render(<AdminInventoryImport />);

    // Open the Radix select and choose the second store.
    fireEvent.click(screen.getByTestId("admin-inventory-import-store-select"));
    fireEvent.click(
      screen.getByRole("option", { name: "Vape Shop B (B-002)" }),
    );

    const importButton = screen.getByTestId("admin-inventory-import-open");
    expect(importButton).not.toBeDisabled();
    // Selecting alone must not open the dialog.
    expect(screen.queryByTestId("import-dialog-stub")).not.toBeInTheDocument();

    fireEvent.click(importButton);

    const dialog = screen.getByTestId("import-dialog-stub");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("data-store-id", STORE_B.id);
  });

  it("shows a loading placeholder and disables the picker while stores load", () => {
    mockStores({
      isLoading: true,
      isFetching: true,
      isError: false,
      isSuccess: false,
    });
    render(<AdminInventoryImport />);

    expect(screen.getByText("Loading stores…")).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-inventory-import-store-select"),
    ).toBeDisabled();
    expect(screen.getByTestId("admin-inventory-import-open")).toBeDisabled();
  });

  it("shows an error placeholder and disables the picker when stores fail", () => {
    mockStores({
      isLoading: false,
      isFetching: false,
      isError: true,
      isSuccess: false,
      error: new Error("forbidden"),
    });
    render(<AdminInventoryImport />);

    expect(screen.getByText("Stores unavailable")).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-inventory-import-store-select"),
    ).toBeDisabled();
    expect(screen.getByTestId("admin-inventory-import-open")).toBeDisabled();
  });

  it("shows a no-stores placeholder when the list is empty", () => {
    mockStoreList([]);
    render(<AdminInventoryImport />);

    expect(screen.getByText("No stores")).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-inventory-import-store-select"),
    ).toBeDisabled();
  });
});
