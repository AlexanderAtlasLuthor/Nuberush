// F2.8.5: tests for the Update Compliance modal + its mounting from
// the ProductDetailHeader.
//
// Strategy: stub `../../hooks` so we can drive `useUpdateComplianceMutation`
// state per case. We render the header (which mounts the modal on
// click) so the open / submit / close flow is exercised end-to-end at
// the component level. Each test asserts one observable contract:
//   - opening the modal
//   - initial form values match the current product
//   - submit forwards the exact payload to `mutate`
//   - banned + allowed_for_sale=true is permitted by the UI and sent
//     verbatim (the backend owns the invariant; the UI does NOT)
//   - backend errors render inline
//   - modal auto-closes on success
//   - no permission / sellable / compliance derivation lives in the UI
//
// We render the header rather than the modal in isolation because that
// exercises the full open-from-button → submit → close lifecycle and
// proves the wiring, not just the modal in a vacuum.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { ProductDetailHeader } from "../ProductDetailHeader";
import * as productsHooks from "../../hooks";
import type { Product } from "../../types";
import type { UpdateProductComplianceParams } from "../../api";

vi.mock("../../hooks", () => ({
  useProductSellableQuery: vi.fn(),
  useUpdateComplianceMutation: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeProduct(overrides: Partial<Product> = {}): Product {
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
    ...overrides,
  };
}

interface MutationOverrides {
  isPending?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  error?: Error | null;
}

// Factory returning a UseMutationResult-shaped object with a fresh
// `mutate` spy per test. Only the fields the modal reads are populated.
function makeMutation(
  overrides: MutationOverrides = {},
): UseMutationResult<Product, Error, UpdateProductComplianceParams> & {
  mutate: ReturnType<typeof vi.fn>;
} {
  const mutate = vi.fn();
  return {
    mutate,
    isPending: overrides.isPending ?? false,
    isSuccess: overrides.isSuccess ?? false,
    isError: overrides.isError ?? false,
    error: overrides.error ?? null,
    reset: vi.fn(),
  } as unknown as UseMutationResult<
    Product,
    Error,
    UpdateProductComplianceParams
  > & {
    mutate: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(productsHooks.useProductSellableQuery).mockReturnValue({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: { product_id: PRODUCT_ID, sellable: true },
    error: null,
    // The badge only reads the four fields above; the rest of
    // UseQueryResult is unused.
  } as never);
  vi.mocked(productsHooks.useUpdateComplianceMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Open + initial values
// --------------------------------------------------------------------- //

describe("ProductDetailHeader → UpdateProductComplianceModal", () => {
  it("does not mount the modal until the Update compliance button is clicked", () => {
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      makeMutation(),
    );

    render(<ProductDetailHeader product={makeProduct()} />);

    // No dialog mounted, no mutation hook subscription.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(productsHooks.useUpdateComplianceMutation).not.toHaveBeenCalled();
  });

  it("opens the modal and seeds initial values from the current product", () => {
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      makeMutation(),
    );

    render(
      <ProductDetailHeader
        product={makeProduct({
          compliance_status: "restricted",
          allowed_for_sale: false,
        })}
      />,
    );

    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    // Dialog mounted; mutation hook now subscribed.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(productsHooks.useUpdateComplianceMutation).toHaveBeenCalledTimes(1);

    // compliance_status Select shows the current value.
    expect(screen.getByTestId("compliance-status-trigger")).toHaveTextContent(
      /restricted/i,
    );

    // allowed_for_sale checkbox is unchecked because the product is
    // currently allowed_for_sale=false.
    const checkbox = screen.getByTestId("compliance-allowed-checkbox");
    expect(checkbox).toHaveAttribute("aria-checked", "false");

    // reason starts blank.
    expect(screen.getByTestId("compliance-reason-input")).toHaveValue("");

    // Submit is disabled until reason is filled in.
    expect(screen.getByTestId("compliance-submit")).toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Submit
// --------------------------------------------------------------------- //

describe("UpdateProductComplianceModal — submit", () => {
  it("forwards the exact payload to useUpdateComplianceMutation.mutate", () => {
    const mutation = makeMutation();
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      mutation,
    );

    render(<ProductDetailHeader product={makeProduct()} />);
    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    fireEvent.change(screen.getByTestId("compliance-reason-input"), {
      target: { value: "  policy review  " },
    });
    fireEvent.click(screen.getByTestId("compliance-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: {
        // Initial product values surface unchanged when the user only
        // edits the reason — proving the form does no rewriting.
        compliance_status: "allowed",
        allowed_for_sale: true,
        // Reason is trimmed before send (UX guard, not business logic).
        reason: "policy review",
      },
    });
  });

  it("permits banned + allowed_for_sale=true through the UI and forwards verbatim", () => {
    // CRITICAL: this test pins the rule that the backend owns the
    // invariant. The UI MUST NOT short-circuit the submit, MUST NOT
    // auto-flip allowed_for_sale, MUST NOT disable the checkbox when
    // banned is selected.
    const mutation = makeMutation();
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      mutation,
    );

    render(
      <ProductDetailHeader
        product={makeProduct({
          compliance_status: "allowed",
          allowed_for_sale: true,
        })}
      />,
    );
    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    // Open the Select and pick "Banned".
    fireEvent.click(screen.getByTestId("compliance-status-trigger"));
    fireEvent.click(screen.getByRole("option", { name: /banned/i }));

    // The checkbox MUST stay checked — no UI flip.
    expect(
      screen.getByTestId("compliance-allowed-checkbox"),
    ).toHaveAttribute("aria-checked", "true");

    fireEvent.change(screen.getByTestId("compliance-reason-input"), {
      target: { value: "deliberate banned+allowed combo" },
    });
    fireEvent.click(screen.getByTestId("compliance-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: {
        compliance_status: "banned",
        allowed_for_sale: true,
        reason: "deliberate banned+allowed combo",
      },
    });
  });

  it("does not submit when reason is blank or whitespace-only", () => {
    const mutation = makeMutation();
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      mutation,
    );

    render(<ProductDetailHeader product={makeProduct()} />);
    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    // No reason entered → submit disabled.
    expect(screen.getByTestId("compliance-submit")).toBeDisabled();
    fireEvent.click(screen.getByTestId("compliance-submit"));
    expect(mutation.mutate).not.toHaveBeenCalled();

    // Whitespace-only → still disabled (trimmedReason.length === 0).
    fireEvent.change(screen.getByTestId("compliance-reason-input"), {
      target: { value: "   " },
    });
    expect(screen.getByTestId("compliance-submit")).toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Pending / error / success
// --------------------------------------------------------------------- //

describe("UpdateProductComplianceModal — async states", () => {
  it("disables the submit button while the mutation is pending", () => {
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(<ProductDetailHeader product={makeProduct()} />);
    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    fireEvent.change(screen.getByTestId("compliance-reason-input"), {
      target: { value: "anything" },
    });

    const submit = screen.getByTestId("compliance-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/updating/i);
  });

  it("surfaces backend errors inline without closing the modal", () => {
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "A banned product cannot be allowed_for_sale.",
        }),
      }),
    );

    render(<ProductDetailHeader product={makeProduct()} />);
    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    // Modal stays open and shows the error inline.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    const errorNode = screen.getByTestId("compliance-error");
    expect(errorNode).toHaveTextContent(
      /a banned product cannot be allowed_for_sale/i,
    );
  });

  it("auto-closes the modal on mutation success", async () => {
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );

    render(<ProductDetailHeader product={makeProduct()} />);
    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    // The modal sees `mutation.isSuccess === true` on first render and
    // calls `onOpenChange(false)`, which unmounts the dialog.
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});

// --------------------------------------------------------------------- //
// No permission / no derivation
// --------------------------------------------------------------------- //

describe("UpdateProductComplianceModal — thin-client guarantees", () => {
  it("renders the Update compliance button regardless of any role context", () => {
    // The button is unconditionally visible — there is NO useAuth /
    // role check / hasPermission gate. Backend authorisation surfaces
    // as a 4xx ApiError through the modal's inline error path.
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      makeMutation(),
    );

    render(<ProductDetailHeader product={makeProduct()} />);

    expect(
      screen.getByTestId("product-detail-update-compliance"),
    ).toBeInTheDocument();
  });

  it("does not pre-validate the banned/allowed combination on the client", () => {
    // Open with a banned product whose allowed_for_sale is true (an
    // impossible state on the wire today, but a useful smoke test for
    // "the form does not auto-correct"). The submit button must be
    // enabled as soon as a reason is entered, regardless of the
    // banned+allowed combination.
    vi.mocked(productsHooks.useUpdateComplianceMutation).mockReturnValue(
      makeMutation(),
    );

    const banned = makeProduct({
      compliance_status: "banned",
      allowed_for_sale: true,
    });

    render(<ProductDetailHeader product={banned} />);
    fireEvent.click(
      screen.getByTestId("product-detail-update-compliance"),
    );

    // Initial values reflect the banned + allowed combo verbatim.
    expect(screen.getByTestId("compliance-status-trigger")).toHaveTextContent(
      /banned/i,
    );
    expect(
      screen.getByTestId("compliance-allowed-checkbox"),
    ).toHaveAttribute("aria-checked", "true");

    // Once a reason is entered, submit is enabled — no client-side
    // gate based on the compliance + allowed combination.
    fireEvent.change(screen.getByTestId("compliance-reason-input"), {
      target: { value: "x" },
    });
    expect(screen.getByTestId("compliance-submit")).not.toBeDisabled();

    // Sanity: the dialog body never warns about the combination —
    // there is no client-side rule narrative in the UI.
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByText(/cannot be allowed/i)).not.toBeInTheDocument();
  });
});
