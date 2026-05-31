// F2.24.C7: tests for AdminStoreApplicationDetailPage.
//
// Stubs `../../hooks` (detail query + approve/reject mutations). The page
// is mounted at the parametrized route so useParams resolves the id.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";

import AdminStoreApplicationDetailPage from "../AdminStoreApplicationDetailPage";
import * as hooks from "../../hooks";
import type {
  StoreApplicationDetail,
  StoreApplicationReviewResponse,
} from "../../types";

vi.mock("../../hooks", () => ({
  useAdminStoreApplicationQuery: vi.fn(),
  useApproveStoreApplicationMutation: vi.fn(),
  useRejectStoreApplicationMutation: vi.fn(),
}));

// Mirror features/stores AdminStoreDetailPage.test: provide the route
// param via a partial mock of react-router-dom rather than mounting a
// full <Routes> tree.
let routeParams: Record<string, string> = {};

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useParams: () => routeParams,
  };
});

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
    business_phone: "555-0199",
    address_line_1: "1 Main St",
    address_line_2: "Suite 5",
    city: "Brooklyn",
    state: "NY",
    postal_code: "11201",
    country: "US",
    location_count: 3,
    estimated_weekly_orders: 150,
    hours_of_operation: "9-5 Mon-Fri",
    website_url: "https://acme.example",
    social_url: null,
    notes: "Priority applicant",
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

function asQuery(
  partial: Partial<UseQueryResult<StoreApplicationDetail>>,
): UseQueryResult<StoreApplicationDetail> {
  return partial as UseQueryResult<StoreApplicationDetail>;
}

function makeMutation() {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    data: undefined,
    error: null,
  } as unknown as UseMutationResult<
    StoreApplicationReviewResponse,
    unknown,
    never
  >;
}

function setQuery(partial: Partial<UseQueryResult<StoreApplicationDetail>>) {
  vi.mocked(hooks.useAdminStoreApplicationQuery).mockReturnValue(
    asQuery(partial),
  );
}

function renderDetail(id = APP_ID) {
  routeParams = { applicationId: id };
  return render(
    <MemoryRouter initialEntries={[`/app/admin/applications/${id}`]}>
      <AdminStoreApplicationDetailPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  routeParams = { applicationId: APP_ID };
  vi.mocked(hooks.useAdminStoreApplicationQuery).mockReset();
  vi.mocked(hooks.useApproveStoreApplicationMutation).mockReturnValue(
    makeMutation() as never,
  );
  vi.mocked(hooks.useRejectStoreApplicationMutation).mockReturnValue(
    makeMutation() as never,
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminStoreApplicationDetailPage — content", () => {
  beforeEach(() => {
    setQuery({ isLoading: false, isError: false, data: makeDetail() });
  });

  it("renders business information fields", () => {
    renderDetail();
    expect(screen.getByText("Acme Vapor Co")).toBeInTheDocument();
    expect(screen.getByText("Smoke shop")).toBeInTheDocument();
  });

  it("renders owner / contact fields", () => {
    renderDetail();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("11201")).toBeInTheDocument();
  });

  it("renders operations fields", () => {
    renderDetail();
    expect(screen.getByText("9-5 Mon-Fri")).toBeInTheDocument();
    expect(screen.getByText("Priority applicant")).toBeInTheDocument();
  });

  it("renders the status badge", () => {
    renderDetail();
    expect(
      screen.getByTestId("application-status-pending_review"),
    ).toBeInTheDocument();
  });

  it("renders audit logs when provided", () => {
    setQuery({
      isLoading: false,
      isError: false,
      data: makeDetail({
        audit_logs: [
          {
            id: "log-1",
            application_id: APP_ID,
            event_type: "application_submitted",
            actor_user_id: null,
            message: "Submitted via public apply form",
            payload: null,
            created_at: "2026-05-01T12:00:00Z",
          },
        ],
      }),
    });
    renderDetail();
    expect(
      screen.getByTestId("application-audit-logs"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("application_submitted"),
    ).toBeInTheDocument();
  });

  it("renders a back link to the applications queue", () => {
    renderDetail();
    expect(
      screen.getByTestId("application-detail-back-link"),
    ).toHaveAttribute("href", "/app/admin/applications");
  });
});

describe("AdminStoreApplicationDetailPage — error state", () => {
  it("renders the error state on a failed load", () => {
    setQuery({
      isLoading: false,
      isError: true,
      error: new Error("nope"),
      refetch: vi.fn() as never,
    });
    renderDetail();
    expect(
      screen.getByText("Could not load application"),
    ).toBeInTheDocument();
  });
});

describe("AdminStoreApplicationDetailPage — actions gating", () => {
  it("shows approve and reject actions for a pending application", () => {
    setQuery({
      isLoading: false,
      isError: false,
      data: makeDetail({ status: "pending_review" }),
    });
    renderDetail();
    expect(
      screen.getByTestId("approve-application-button"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("application-reject-button"),
    ).toBeInTheDocument();
  });

  it("hides approve and reject actions for an approved application", () => {
    setQuery({
      isLoading: false,
      isError: false,
      data: makeDetail({
        status: "approved",
        provisioned_store_id: "store-1",
        provisioned_owner_user_id: "owner-1",
        reviewed_at: "2026-05-02T00:00:00Z",
        reviewed_by_user_id: "admin-1",
      }),
    });
    renderDetail();
    expect(
      screen.queryByTestId("approve-application-button"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("application-reject-button"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("application-status-approved"),
    ).toBeInTheDocument();
  });

  it("hides actions and shows the reason for a rejected application", () => {
    setQuery({
      isLoading: false,
      isError: false,
      data: makeDetail({
        status: "rejected",
        rejection_reason: "Missing license documentation",
        reviewed_at: "2026-05-02T00:00:00Z",
        reviewed_by_user_id: "admin-1",
      }),
    });
    renderDetail();
    expect(
      screen.queryByTestId("approve-application-button"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("application-reject-button"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("application-status-rejected"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("application-rejection-reason"),
    ).toHaveTextContent("Missing license documentation");
  });
});
