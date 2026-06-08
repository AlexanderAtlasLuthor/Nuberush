// F2.27.8 + F2.27.9: tests for InventoryImportDialog.
//
// The dialog is a thin shell over the preview + confirm mutations. We
// mock both hooks (and useAuth) and assert the dialog's contract:
// selecting a file fires preview, the summary + per-row errors/warnings
// render, confirm is gated on blocking_error_count, confirm fires the
// mutation, the success/error banners render, and the admin-only
// "create missing products & variants" toggle behaves correctly.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ApiError } from "@/api";
import * as auth from "@/auth";
import { InventoryImportDialog } from "../InventoryImportDialog";
import * as hooks from "../../hooks";
import type {
  InventoryImportConfirmResponse,
  InventoryImportPreviewResponse,
  InventoryImportSummary,
} from "../../types";

vi.mock("../../hooks", () => ({
  useInventoryImportPreviewMutation: vi.fn(),
  useInventoryImportConfirmMutation: vi.fn(),
}));

vi.mock("@/auth", () => ({
  useAuth: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

interface FakeMutation {
  mutate: ReturnType<typeof vi.fn>;
  reset: ReturnType<typeof vi.fn>;
  isPending: boolean;
  isError: boolean;
  isSuccess: boolean;
  error: unknown;
  data: unknown;
}

function fakeMutation(overrides: Partial<FakeMutation> = {}): FakeMutation {
  return {
    mutate: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    error: null,
    data: undefined,
    ...overrides,
  };
}

function summary(
  overrides: Partial<InventoryImportSummary> = {},
): InventoryImportSummary {
  return {
    total_rows: 2,
    valid_rows: 2,
    rows_with_errors: 0,
    rows_with_warnings: 0,
    to_update: 1,
    to_create_inventory_item: 1,
    to_create_product_and_variant: 0,
    to_skip: 0,
    blocking_error_count: 0,
    ...overrides,
  };
}

function makePreview(
  overrides: Partial<InventoryImportPreviewResponse> = {},
): InventoryImportPreviewResponse {
  return {
    store_id: STORE_ID,
    summary: summary(),
    rows: [
      {
        row_number: 3,
        raw_sku: "100",
        normalized_sku: "100",
        item_name: "Widget",
        parsed_quantity: 5,
        matched_variant_id: "v1",
        matched_product_name: "Widget",
        current_on_hand: 2,
        quantity_reserved: 0,
        new_on_hand: 5,
        delta: 3,
        action: "update",
        errors: [],
        warnings: [],
      },
    ],
    ...overrides,
  };
}

function setHooks(preview: FakeMutation, confirm: FakeMutation) {
  vi.mocked(hooks.useInventoryImportPreviewMutation).mockReturnValue(
    preview as never,
  );
  vi.mocked(hooks.useInventoryImportConfirmMutation).mockReturnValue(
    confirm as never,
  );
}

function mockAuth(role: auth.UserRole = "manager") {
  vi.mocked(auth.useAuth).mockReturnValue({
    user: { id: "u1", role },
  } as ReturnType<typeof auth.useAuth>);
}

function renderDialog() {
  return render(
    <InventoryImportDialog open onOpenChange={vi.fn()} storeId={STORE_ID} />,
  );
}

function selectFile() {
  const input = screen.getByTestId(
    "inventory-import-file-input",
  ) as HTMLInputElement;
  const file = new File([new Uint8Array([1, 2, 3])], "inv.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

beforeEach(() => {
  vi.mocked(hooks.useInventoryImportPreviewMutation).mockReset();
  vi.mocked(hooks.useInventoryImportConfirmMutation).mockReset();
  vi.mocked(auth.useAuth).mockReset();
  mockAuth("manager");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("InventoryImportDialog", () => {
  it("renders the file upload control", () => {
    setHooks(fakeMutation(), fakeMutation());
    renderDialog();
    expect(
      screen.getByTestId("inventory-import-file-input"),
    ).toBeInTheDocument();
  });

  it("fires the preview mutation when a file is selected", () => {
    const preview = fakeMutation();
    setHooks(preview, fakeMutation());
    renderDialog();
    const file = selectFile();
    expect(preview.mutate).toHaveBeenCalledWith({
      storeId: STORE_ID,
      file,
      createMissing: false,
    });
  });

  it("renders the preview summary", () => {
    setHooks(fakeMutation({ data: makePreview() }), fakeMutation());
    renderDialog();
    expect(screen.getByTestId("import-summary")).toBeInTheDocument();
    expect(screen.getByTestId("summary-total-rows")).toHaveTextContent("2");
    expect(screen.getByTestId("summary-to-create")).toHaveTextContent("1");
  });

  it("renders per-row errors", () => {
    const data = makePreview({
      summary: summary({
        total_rows: 1,
        valid_rows: 0,
        rows_with_errors: 1,
        to_update: 0,
        to_create_inventory_item: 0,
        to_skip: 1,
        blocking_error_count: 1,
      }),
      rows: [
        {
          row_number: 4,
          raw_sku: "X",
          normalized_sku: "X",
          item_name: "Bad",
          parsed_quantity: null,
          matched_variant_id: null,
          matched_product_name: null,
          current_on_hand: null,
          quantity_reserved: null,
          new_on_hand: null,
          delta: null,
          action: "skip",
          errors: [{ code: "VARIANT_NOT_FOUND", message: "no variant" }],
          warnings: [],
        },
      ],
    });
    setHooks(fakeMutation({ data }), fakeMutation());
    renderDialog();
    expect(screen.getByText("VARIANT_NOT_FOUND")).toBeInTheDocument();
    expect(screen.getByTestId("import-blocking-warning")).toBeInTheDocument();
  });

  it("renders per-row warnings", () => {
    const data = makePreview({
      summary: summary({
        total_rows: 1,
        valid_rows: 1,
        rows_with_warnings: 1,
        to_update: 1,
        to_create_inventory_item: 0,
      }),
      rows: [
        {
          row_number: 5,
          raw_sku: "Y",
          normalized_sku: "Y",
          item_name: "Warn",
          parsed_quantity: 1,
          matched_variant_id: "v2",
          matched_product_name: "Warn",
          current_on_hand: 1,
          quantity_reserved: 0,
          new_on_hand: 1,
          delta: 0,
          action: "update",
          errors: [],
          warnings: [{ code: "SOME_WARNING", message: "heads up" }],
        },
      ],
    });
    setHooks(fakeMutation({ data }), fakeMutation());
    renderDialog();
    expect(screen.getByText("SOME_WARNING")).toBeInTheDocument();
  });

  it("disables confirm when blocking_error_count > 0", () => {
    const blocked = makePreview({
      summary: summary({ blocking_error_count: 2 }),
    });
    setHooks(fakeMutation({ data: blocked }), fakeMutation());
    renderDialog();
    selectFile();
    expect(screen.getByTestId("inventory-import-confirm")).toBeDisabled();
  });

  it("enables confirm when there are no blocking errors and fires confirm", () => {
    const preview = fakeMutation({ data: makePreview() });
    const confirm = fakeMutation();
    setHooks(preview, confirm);
    renderDialog();
    const file = selectFile();
    const confirmBtn = screen.getByTestId("inventory-import-confirm");
    expect(confirmBtn).toBeEnabled();
    fireEvent.click(confirmBtn);
    expect(confirm.mutate).toHaveBeenCalledWith({
      storeId: STORE_ID,
      file,
      createMissing: false,
    });
  });

  it("renders the success state", () => {
    const confirmData: InventoryImportConfirmResponse = {
      store_id: STORE_ID,
      updated_count: 3,
      created_inventory_item_count: 1,
      created_product_count: 0,
      created_variant_count: 0,
      skipped_count: 0,
      unchanged_count: 2,
      inventory_log_count: 3,
    };
    setHooks(
      fakeMutation({ data: makePreview() }),
      fakeMutation({ isSuccess: true, data: confirmData }),
    );
    renderDialog();
    expect(screen.getByTestId("import-confirm-success")).toHaveTextContent(
      /3 updated/i,
    );
  });

  it("renders the preview error state", () => {
    setHooks(
      fakeMutation({
        isError: true,
        error: new ApiError({ status: 422, message: "Bad headers" }),
      }),
      fakeMutation(),
    );
    renderDialog();
    expect(screen.getByTestId("import-preview-error")).toHaveTextContent(
      /bad headers/i,
    );
  });

  it("renders the confirm error state", () => {
    setHooks(
      fakeMutation({ data: makePreview() }),
      fakeMutation({
        isError: true,
        error: new ApiError({ status: 422, message: "Blocking errors" }),
      }),
    );
    renderDialog();
    expect(screen.getByTestId("import-confirm-error")).toHaveTextContent(
      /blocking errors/i,
    );
  });
});

describe("InventoryImportDialog - admin create-missing toggle (F2.27.9)", () => {
  it("hides the toggle for non-admin (manager)", () => {
    mockAuth("manager");
    setHooks(fakeMutation(), fakeMutation());
    renderDialog();
    expect(
      screen.queryByTestId("import-create-missing-toggle"),
    ).toBeNull();
  });

  it("shows the toggle for admin", () => {
    mockAuth("admin");
    setHooks(fakeMutation(), fakeMutation());
    renderDialog();
    expect(
      screen.getByTestId("import-create-missing-toggle"),
    ).toBeInTheDocument();
  });

  it("re-runs preview with createMissing when the toggle is turned on", () => {
    mockAuth("admin");
    const preview = fakeMutation();
    setHooks(preview, fakeMutation());
    renderDialog();
    const file = selectFile();
    expect(preview.mutate).toHaveBeenLastCalledWith({
      storeId: STORE_ID,
      file,
      createMissing: false,
    });
    fireEvent.click(screen.getByTestId("import-create-missing-toggle"));
    expect(preview.mutate).toHaveBeenLastCalledWith({
      storeId: STORE_ID,
      file,
      createMissing: true,
    });
  });

  it("renders create_product_and_variant rows as 'Create product'", () => {
    mockAuth("admin");
    const data = makePreview({
      summary: summary({
        to_update: 0,
        to_create_inventory_item: 0,
        to_create_product_and_variant: 1,
      }),
      rows: [
        {
          row_number: 3,
          raw_sku: "NEW",
          normalized_sku: "NEW",
          item_name: "Brand New",
          parsed_quantity: 4,
          matched_variant_id: null,
          matched_product_name: "Brand New",
          current_on_hand: 0,
          quantity_reserved: 0,
          new_on_hand: 4,
          delta: 4,
          action: "create_product_and_variant",
          errors: [],
          warnings: [],
        },
      ],
    });
    setHooks(fakeMutation({ data }), fakeMutation());
    renderDialog();
    expect(screen.getByText("Create product")).toBeInTheDocument();
    expect(
      screen.getByTestId("summary-to-create-product"),
    ).toHaveTextContent("1");
  });

  it("success banner reports created products and variants", () => {
    mockAuth("admin");
    const confirmData: InventoryImportConfirmResponse = {
      store_id: STORE_ID,
      updated_count: 0,
      created_inventory_item_count: 2,
      created_product_count: 2,
      created_variant_count: 2,
      skipped_count: 0,
      unchanged_count: 0,
      inventory_log_count: 2,
    };
    setHooks(
      fakeMutation({ data: makePreview() }),
      fakeMutation({ isSuccess: true, data: confirmData }),
    );
    renderDialog();
    expect(screen.getByTestId("import-confirm-success")).toHaveTextContent(
      /2 products/i,
    );
  });
});
