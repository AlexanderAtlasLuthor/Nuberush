// F2.24.C7: tests for ApproveApplicationPanel.
//
// Mocks the approve mutation hook so we exercise the panel's confirm /
// loading / success / error rendering without TanStack Query or the API
// layer. `@/api` stays real so ApiError + isApiError drive the 409
// branch authentically.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { ApproveApplicationPanel } from "../ApproveApplicationPanel";
import * as hooks from "../../hooks";
import type {
  StoreApplicationDetail,
  StoreApplicationReviewResponse,
} from "../../types";
import type { ApproveStoreApplicationParams } from "../../api";

vi.mock("../../hooks", () => ({
  useApproveStoreApplicationMutation: vi.fn(),
  useRejectStoreApplicationMutation: vi.fn(),
}));

const APP_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

function makeDetail(
  overrides: Partial<StoreApplicationDetail> = {},
): StoreApplicationDetail {
  return {
    id: APP_ID,
    business_name: "Acme Vapor Co",
    business_type: "Smoke shop",
    owner_full_name: "Ada Lovelace",
    owner_email: "ada@example.com",
    owner_phone: "555-0100",
    business_phone: null,
    address_line_1: "1 Main St",
    address_line_2: null,
    city: "Brooklyn",
    state: "NY",
    postal_code: "11201",
    country: "US",
    location_count: 1,
    estimated_weekly_orders: 50,
    hours_of_operation: null,
    website_url: null,
    social_url: null,
    notes: null,
    terms_accepted: true,
    terms_accepted_at: "2026-05-01T10:00:00Z",
    status: "pending_review",
    submitted_at: "2026-05-01T12:00:00Z",
    reviewed_at: null,
    reviewed_by_user_id: null,
    rejection_reason: null,
    provisioned_store_id: null,
    provisioned_owner_user_id: null,
    public_lookup_token: "tok",
    created_at: "2026-05-01T11:00:00Z",
    updated_at: "2026-05-01T12:00:00Z",
    audit_logs: [],
    ...overrides,
  };
}

interface MutationOptions {
  isPending?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  data?: StoreApplicationReviewResponse | null;
  error?: unknown;
}

function makeMutation(o: MutationOptions = {}) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    data: o.data ?? undefined,
    error: o.error ?? null,
  } as unknown as UseMutationResult<
    StoreApplicationReviewResponse,
    unknown,
    ApproveStoreApplicationParams
  > & { mutate: ReturnType<typeof vi.fn> };
}

function setApprove(mutation: ReturnType<typeof makeMutation>) {
  vi.mocked(hooks.useApproveStoreApplicationMutation).mockReturnValue(
    mutation as never,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  setApprove(makeMutation());
});

describe("ApproveApplicationPanel", () => {
  it("renders the approve action", () => {
    render(<ApproveApplicationPanel application={makeDetail()} />);
    expect(
      screen.getByTestId("approve-application-button"),
    ).toBeInTheDocument();
  });

  it("clicking approve fires the mutation exactly once with only the id", () => {
    const mutation = makeMutation();
    setApprove(mutation);
    render(<ApproveApplicationPanel application={makeDetail()} />);
    fireEvent.click(screen.getByTestId("approve-application-button"));
    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({ applicationId: APP_ID });
    // No role / store / user / Auth fields smuggled in.
    const arg = mutation.mutate.mock.calls[0][0];
    expect(Object.keys(arg)).toEqual(["applicationId"]);
  });

  it("disables the button and ignores extra clicks while pending", () => {
    const mutation = makeMutation({ isPending: true });
    setApprove(mutation);
    render(<ApproveApplicationPanel application={makeDetail()} />);
    const button = screen.getByTestId("approve-application-button");
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(mutation.mutate).not.toHaveBeenCalled();
  });

  it("on success shows a success message and provisioned ids", () => {
    setApprove(
      makeMutation({
        isSuccess: true,
        data: {
          id: APP_ID,
          status: "approved",
          reviewed_by_user_id: "admin-1",
          reviewed_at: "2026-05-02T00:00:00Z",
          provisioned_store_id: "store-123",
          provisioned_owner_user_id: "owner-456",
          rejection_reason: null,
          message: "Application approved.",
        },
      }),
    );
    render(<ApproveApplicationPanel application={makeDetail()} />);
    expect(
      screen.getByTestId("approve-application-success"),
    ).toHaveTextContent("Application approved.");
    expect(
      screen.getByTestId("approve-provisioned-store-id"),
    ).toHaveTextContent("store-123");
    expect(
      screen.getByTestId("approve-provisioned-owner-id"),
    ).toHaveTextContent("owner-456");
    // The active approve button is gone after success.
    expect(
      screen.queryByTestId("approve-application-button"),
    ).not.toBeInTheDocument();
  });

  it("on 409 shows the friendly conflict message", () => {
    setApprove(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 409, message: "conflict" }),
      }),
    );
    render(<ApproveApplicationPanel application={makeDetail()} />);
    expect(
      screen.getByTestId("approve-application-error"),
    ).toHaveTextContent(/no longer pending review/i);
  });

  it("on a generic error shows a safe message", () => {
    setApprove(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 500, message: "kaboom" }),
      }),
    );
    render(<ApproveApplicationPanel application={makeDetail()} />);
    const error = screen.getByTestId("approve-application-error");
    expect(error).toHaveTextContent(/something went wrong/i);
    // The raw server message is not leaked.
    expect(error).not.toHaveTextContent("kaboom");
  });
});
