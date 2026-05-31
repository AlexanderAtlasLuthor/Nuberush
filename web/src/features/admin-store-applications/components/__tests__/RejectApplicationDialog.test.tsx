// F2.24.C7: tests for RejectApplicationDialog.
//
// Mocks the reject mutation hook; `@/api` stays real so ApiError +
// status-aware messaging drive the 409 / 422 / generic branches.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { RejectApplicationDialog } from "../RejectApplicationDialog";
import * as hooks from "../../hooks";
import type {
  StoreApplicationDetail,
  StoreApplicationReviewResponse,
} from "../../types";
import type { RejectStoreApplicationParams } from "../../api";

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
    RejectStoreApplicationParams
  > & { mutate: ReturnType<typeof vi.fn>; reset: ReturnType<typeof vi.fn> };
}

function setReject(mutation: ReturnType<typeof makeMutation>) {
  vi.mocked(hooks.useRejectStoreApplicationMutation).mockReturnValue(
    mutation as never,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  setReject(makeMutation());
});

describe("RejectApplicationDialog", () => {
  it("requires a non-blank reason before the confirm button enables", () => {
    render(
      <RejectApplicationDialog
        application={makeDetail()}
        open
        onOpenChange={vi.fn()}
      />,
    );
    const confirm = screen.getByTestId("reject-application-confirm");
    expect(confirm).toBeDisabled();

    // Whitespace-only is still blank.
    fireEvent.change(screen.getByTestId("reject-application-reason"), {
      target: { value: "   " },
    });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByTestId("reject-application-reason"), {
      target: { value: "Incomplete docs" },
    });
    expect(confirm).not.toBeDisabled();
  });

  it("submits ONLY rejection_reason (trimmed) and the application id", () => {
    const mutation = makeMutation();
    setReject(mutation);
    render(
      <RejectApplicationDialog
        application={makeDetail()}
        open
        onOpenChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("reject-application-reason"), {
      target: { value: "  Incomplete docs  " },
    });
    fireEvent.click(screen.getByTestId("reject-application-confirm"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      applicationId: APP_ID,
      body: { rejection_reason: "Incomplete docs" },
    });
    // No reviewer / store / user / role fields anywhere in the payload.
    const arg = mutation.mutate.mock.calls[0][0];
    expect(Object.keys(arg).sort()).toEqual(["applicationId", "body"]);
    expect(Object.keys(arg.body)).toEqual(["rejection_reason"]);
  });

  it("on 409 shows the friendly conflict message", () => {
    setReject(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 409, message: "conflict" }),
      }),
    );
    render(
      <RejectApplicationDialog
        application={makeDetail()}
        open
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("reject-application-error"),
    ).toHaveTextContent(/no longer pending review/i);
  });

  it("on 422 surfaces the validation message from the backend", () => {
    setReject(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "rejection_reason must not be empty",
        }),
      }),
    );
    render(
      <RejectApplicationDialog
        application={makeDetail()}
        open
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("reject-application-error"),
    ).toHaveTextContent("rejection_reason must not be empty");
  });

  it("on a generic error shows a safe message without leaking server text", () => {
    setReject(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 500, message: "kaboom" }),
      }),
    );
    render(
      <RejectApplicationDialog
        application={makeDetail()}
        open
        onOpenChange={vi.fn()}
      />,
    );
    const error = screen.getByTestId("reject-application-error");
    expect(error).toHaveTextContent(/something went wrong/i);
    expect(error).not.toHaveTextContent("kaboom");
  });
});
