// F2.14.6: tests for StoreSettingsPage.
//
// Strategy: mock the four collaborators (StoreContext, useStoreQuery,
// useUpdateStoreMutation, StoreSettingsForm, useToast, getApiErrorMessage)
// so we can drive the page through every render branch in isolation
// and assert the orchestration contract:
//
//   - what render branch fires per query state
//   - that the form receives the right props
//   - that submit forwards the payload to the mutation
//   - that success triggers the toast
//   - that mutation error is plumbed into the form's `errorMessage`
//   - that placeholder copy from F2.13 is gone
//
// We do NOT re-prove StoreSettingsForm behaviour here; that already
// has 32 dedicated tests in F2.14.5. The form mock here is a simple
// component that surfaces the props as DOM so we can read them.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";

import StoreSettingsPage from "../StoreSettingsPage";
import * as storeHooks from "../../hooks";
import * as authModule from "@/auth";
import * as apiModule from "@/api";
import * as toastModule from "@/hooks/use-toast";
import type {
  StoreProfile,
  StoreUpdateRequest,
} from "../../types";

// --------------------------------------------------------------------- //
// Mocks
// --------------------------------------------------------------------- //

// Mock the form so we can read the props it receives. The form's own
// behaviour is exhaustively covered in F2.14.5.
const submitButtonHandler = vi.fn();
vi.mock("../../components/StoreSettingsForm", () => ({
  StoreSettingsForm: (props: {
    store: StoreProfile;
    isPending?: boolean;
    errorMessage?: string | null;
    onSubmit: (payload: StoreUpdateRequest) => void | Promise<void>;
  }) => (
    <div data-testid="store-settings-form-mock">
      <span data-testid="form-store-name">{props.store.name}</span>
      <span data-testid="form-store-id">{props.store.id}</span>
      <span data-testid="form-is-pending">
        {props.isPending ? "true" : "false"}
      </span>
      <span data-testid="form-error-message">
        {props.errorMessage ?? ""}
      </span>
      <button
        type="button"
        data-testid="form-submit-trigger"
        onClick={() => {
          submitButtonHandler();
          void props.onSubmit({ name: "New Store" });
        }}
      >
        submit
      </button>
    </div>
  ),
}));

vi.mock("@/auth", () => ({
  useStoreContext: vi.fn(),
}));

vi.mock("../../hooks", () => ({
  useStoreQuery: vi.fn(),
  useUpdateStoreMutation: vi.fn(),
  storeKeys: {
    all: ["store"],
    detail: (id: string) => ["store", "detail", id],
  },
}));

vi.mock("@/api", () => ({
  getApiErrorMessage: vi.fn((err: unknown) =>
    err instanceof Error ? err.message : "Unknown error",
  ),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: vi.fn(),
}));

// --------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------- //

const STORE_ID = "22222222-2222-2222-2222-222222222222";

const STORE: StoreProfile = {
  id: STORE_ID,
  name: "Downtown Store",
  code: "DT-001",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

interface QueryOverrides {
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | null;
  data?: StoreProfile | undefined;
}

function makeQuery(o: QueryOverrides = {}): UseQueryResult<StoreProfile> {
  const refetch = vi.fn();
  return {
    isLoading: o.isLoading ?? false,
    isError: o.isError ?? false,
    isSuccess: !(o.isLoading || o.isError),
    error: o.error ?? null,
    data: o.data,
    refetch,
    isPending: o.isLoading ?? false,
    fetchStatus: o.isLoading ? "fetching" : "idle",
  } as unknown as UseQueryResult<StoreProfile>;
}

interface MutationOverrides {
  isPending?: boolean;
  isError?: boolean;
  error?: Error | null;
  mutateAsync?: ReturnType<typeof vi.fn>;
}

function makeMutation(
  o: MutationOverrides = {},
): UseMutationResult<StoreProfile, Error, StoreUpdateRequest> {
  return {
    isPending: o.isPending ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    mutate: vi.fn(),
    mutateAsync:
      o.mutateAsync ?? vi.fn().mockResolvedValue(STORE),
    reset: vi.fn(),
  } as unknown as UseMutationResult<StoreProfile, Error, StoreUpdateRequest>;
}

const toastSpy = vi.fn();

function setup(opts: {
  currentStoreId?: string | null;
  query?: UseQueryResult<StoreProfile>;
  mutation?: UseMutationResult<StoreProfile, Error, StoreUpdateRequest>;
} = {}) {
  vi.mocked(authModule.useStoreContext).mockReturnValue({
    currentStoreId: opts.currentStoreId === undefined ? STORE_ID : opts.currentStoreId,
    hasStoreContext: opts.currentStoreId !== null,
    isStoreRequired: true,
    storeError: null,
  });
  vi.mocked(storeHooks.useStoreQuery).mockReturnValue(
    opts.query ?? makeQuery({ data: STORE }),
  );
  vi.mocked(storeHooks.useUpdateStoreMutation).mockReturnValue(
    opts.mutation ?? makeMutation(),
  );
  vi.mocked(toastModule.useToast).mockReturnValue({
    toast: toastSpy,
    dismiss: vi.fn(),
    toasts: [],
  });
}

beforeEach(() => {
  vi.mocked(authModule.useStoreContext).mockReset();
  vi.mocked(storeHooks.useStoreQuery).mockReset();
  vi.mocked(storeHooks.useUpdateStoreMutation).mockReset();
  vi.mocked(toastModule.useToast).mockReset();
  vi.mocked(apiModule.getApiErrorMessage).mockReset();
  vi.mocked(apiModule.getApiErrorMessage).mockImplementation((err: unknown) =>
    err instanceof Error ? err.message : "Unknown error",
  );
  toastSpy.mockReset();
  submitButtonHandler.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Render branches
// --------------------------------------------------------------------- //

describe("StoreSettingsPage — loading", () => {
  it("renders the loading state when the query is loading", () => {
    setup({ query: makeQuery({ isLoading: true }) });

    render(<StoreSettingsPage />);

    expect(
      screen.getByText(/store settings are loading/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-settings-form-mock"),
    ).not.toBeInTheDocument();
  });
});

describe("StoreSettingsPage — query error", () => {
  it("renders the error state with the canonical title", () => {
    setup({
      query: makeQuery({
        isError: true,
        error: new Error("Network down"),
      }),
    });

    render(<StoreSettingsPage />);

    expect(
      screen.getByText(/store settings failed to load/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-settings-form-mock"),
    ).not.toBeInTheDocument();
  });

  it("retry button calls refetch on the store query", () => {
    const query = makeQuery({
      isError: true,
      error: new Error("boom"),
    });
    setup({ query });

    render(<StoreSettingsPage />);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(query.refetch).toHaveBeenCalledTimes(1);
  });
});

describe("StoreSettingsPage — empty states", () => {
  it("renders the no-store-selected state when currentStoreId is null", () => {
    setup({ currentStoreId: null });

    render(<StoreSettingsPage />);

    expect(
      screen.getByText(/no store selected for the current session/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-settings-form-mock"),
    ).not.toBeInTheDocument();
  });

  it("does not call the API when currentStoreId is null (relies on hook's enabled guard)", () => {
    setup({ currentStoreId: null });

    render(<StoreSettingsPage />);

    // The page still calls the hook (hooks must be unconditional), but
    // the hook's own `enabled` guard (covered in F2.14.4 tests) keeps
    // the queryFn from running. We only assert here that the page does
    // not bypass the hook with its own fetch.
    expect(storeHooks.useStoreQuery).toHaveBeenCalledWith(null);
  });

  it("renders the no-data state when query succeeds but data is undefined", () => {
    setup({ query: makeQuery({ data: undefined }) });

    render(<StoreSettingsPage />);

    expect(
      screen.getByText(/no store profile returned for the current store/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-settings-form-mock"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Data + form orchestration
// --------------------------------------------------------------------- //

describe("StoreSettingsPage — data branch", () => {
  it("renders the StoreSettingsForm when data exists", () => {
    setup();

    render(<StoreSettingsPage />);

    expect(
      screen.getByTestId("store-settings-form-mock"),
    ).toBeInTheDocument();
  });

  it("passes the store data to StoreSettingsForm", () => {
    setup();

    render(<StoreSettingsPage />);

    expect(screen.getByTestId("form-store-name")).toHaveTextContent(
      STORE.name,
    );
    expect(screen.getByTestId("form-store-id")).toHaveTextContent(
      STORE.id,
    );
  });

  it("forwards mutation.isPending as `isPending`", () => {
    setup({ mutation: makeMutation({ isPending: true }) });

    render(<StoreSettingsPage />);

    expect(screen.getByTestId("form-is-pending")).toHaveTextContent("true");
  });

  it("submit forwards the payload to mutation.mutateAsync", () => {
    const mutateAsync = vi.fn().mockResolvedValue(STORE);
    setup({ mutation: makeMutation({ mutateAsync }) });

    render(<StoreSettingsPage />);
    fireEvent.click(screen.getByTestId("form-submit-trigger"));

    expect(mutateAsync).toHaveBeenCalledWith({ name: "New Store" });
  });

  it("shows a success toast after a successful mutation", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(STORE);
    setup({ mutation: makeMutation({ mutateAsync }) });

    render(<StoreSettingsPage />);
    fireEvent.click(screen.getByTestId("form-submit-trigger"));

    await waitFor(() =>
      expect(toastSpy).toHaveBeenCalledWith({
        title: "Store settings updated.",
      }),
    );
  });

  it("does not show a success toast when the mutation rejects", async () => {
    const boom = new Error("Server exploded");
    const mutateAsync = vi.fn().mockRejectedValue(boom);
    setup({
      mutation: makeMutation({
        mutateAsync,
        isError: true,
        error: boom,
      }),
    });

    render(<StoreSettingsPage />);

    fireEvent.click(screen.getByTestId("form-submit-trigger"));
    // Wait a tick so the rejected promise settles.
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());

    expect(toastSpy).not.toHaveBeenCalled();
  });

  it("plumbs mutation.error through getApiErrorMessage into the form's errorMessage", () => {
    const boom = new Error("Server exploded");
    setup({ mutation: makeMutation({ isError: true, error: boom }) });

    render(<StoreSettingsPage />);

    expect(screen.getByTestId("form-error-message")).toHaveTextContent(
      "Server exploded",
    );
  });

  it("passes errorMessage=null when there is no mutation error", () => {
    setup();

    render(<StoreSettingsPage />);

    expect(screen.getByTestId("form-error-message")).toHaveTextContent("");
  });
});

// --------------------------------------------------------------------- //
// Placeholder copy is gone
// --------------------------------------------------------------------- //

describe("StoreSettingsPage — no placeholder copy", () => {
  it("does not render the F2.13 'Backend Required' status", () => {
    setup();

    render(<StoreSettingsPage />);

    expect(screen.queryByText(/backend required/i)).not.toBeInTheDocument();
  });

  it("does not render the F2.13 placeholder description", () => {
    setup();

    render(<StoreSettingsPage />);

    // Placeholder description was: "Store profile, preferences,
    // notification defaults, and operational settings will be
    // configured here once backend support exists."
    expect(
      screen.queryByText(/notification defaults/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /will be configured here once backend support exists/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders the new page header copy", () => {
    setup();

    render(<StoreSettingsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /store settings/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /manage the basic profile and timezone for this store/i,
      ),
    ).toBeInTheDocument();
  });
});
