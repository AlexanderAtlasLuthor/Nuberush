// F2.8.6: ProductActionsBar wiring tests.
//
// We don't re-test the modal/dialog contracts here (they live in their
// own test files). We just prove that each button mounts the right
// modal — i.e. the wiring is correct and the modals are conditionally
// mounted (not rendered until clicked).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ProductActionsBar } from "../ProductActionsBar";
import * as productsHooks from "../../hooks";
import type { Product } from "../../types";

vi.mock("../../hooks", () => ({
  // ProductFormModal (edit mode)
  useUpdateProductMutation: vi.fn(),
  // ProductVariantFormModal (create mode)
  useCreateVariantMutation: vi.fn(),
  // DeactivateProductDialog
  useDeleteProductMutation: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeProduct(): Product {
  return {
    id: PRODUCT_ID,
    name: "Cosmic Gummies",
    brand: "Lunar Co.",
    category: "edibles",
    description: null,
    compliance_status: "allowed",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function idleMutation() {
  return {
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  };
}

beforeEach(() => {
  vi.mocked(productsHooks.useUpdateProductMutation).mockReturnValue(
    idleMutation() as never,
  );
  vi.mocked(productsHooks.useCreateVariantMutation).mockReturnValue(
    idleMutation() as never,
  );
  vi.mocked(productsHooks.useDeleteProductMutation).mockReturnValue(
    idleMutation() as never,
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProductActionsBar", () => {
  it("renders the three action buttons unconditionally (no permission gate)", () => {
    render(<ProductActionsBar product={makeProduct()} />);

    expect(screen.getByTestId("product-action-edit")).toBeInTheDocument();
    expect(
      screen.getByTestId("product-action-add-variant"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("product-action-deactivate"),
    ).toBeInTheDocument();
  });

  it("does not mount any modal until the operator clicks a button", () => {
    render(<ProductActionsBar product={makeProduct()} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    // Mutation hooks NOT subscribed yet.
    expect(productsHooks.useUpdateProductMutation).not.toHaveBeenCalled();
    expect(productsHooks.useCreateVariantMutation).not.toHaveBeenCalled();
    expect(productsHooks.useDeleteProductMutation).not.toHaveBeenCalled();
  });

  it("Edit product button opens the edit ProductFormModal", () => {
    render(<ProductActionsBar product={makeProduct()} />);

    fireEvent.click(screen.getByTestId("product-action-edit"));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByTestId("product-edit-submit")).toBeInTheDocument();
    expect(productsHooks.useUpdateProductMutation).toHaveBeenCalledTimes(1);
  });

  it("Add variant button opens the create ProductVariantFormModal", () => {
    render(<ProductActionsBar product={makeProduct()} />);

    fireEvent.click(screen.getByTestId("product-action-add-variant"));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByTestId("variant-create-submit")).toBeInTheDocument();
    expect(productsHooks.useCreateVariantMutation).toHaveBeenCalledTimes(1);
  });

  it("Deactivate button opens the DeactivateProductDialog", () => {
    render(<ProductActionsBar product={makeProduct()} />);

    fireEvent.click(screen.getByTestId("product-action-deactivate"));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByTestId("deactivate-product-submit"),
    ).toBeInTheDocument();
    expect(productsHooks.useDeleteProductMutation).toHaveBeenCalledTimes(1);
  });
});
