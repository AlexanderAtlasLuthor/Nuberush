// F2.26.4.D copy guardrail: Admin product approval copy.
//
// Locks the F2.26.4.B wording so a regression cannot re-introduce the
// "publishes this product to every store" phrasing. The mutation hooks
// are mocked so we render the real panel copy without TanStack Query or
// the api layer; this is a copy guardrail, not an approval-flow test.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AdminProductApprovalPanel } from "../AdminProductApprovalPanel";
import type { Product } from "../../types";

vi.mock("@/features/products/hooks", () => ({
  useApproveProductMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  }),
  useRejectProductMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  }),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_ID,
    name: "Mango Ice",
    brand: null,
    category: "vape",
    description: null,
    compliance_status: "allowed",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: null,
    approval_status: "pending",
    proposed_by_store_id: null,
    proposed_by_user_id: null,
    reviewed_by_user_id: null,
    reviewed_at: null,
    rejection_reason: null,
    created_at: "2026-05-27T00:00:00Z",
    updated_at: "2026-05-27T00:00:00Z",
    primary_image: null,
    ...overrides,
  } as Product;
}

describe("AdminProductApprovalPanel — copy guardrails (F2.26.4.D)", () => {
  it("frames approval as availability for sale, not publishing to every store", () => {
    render(<AdminProductApprovalPanel product={makeProduct()} />);

    expect(
      screen.getByText(/available for sale in all stores/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/publishes this product to every store/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/publish/i)).not.toBeInTheDocument();
  });
});
