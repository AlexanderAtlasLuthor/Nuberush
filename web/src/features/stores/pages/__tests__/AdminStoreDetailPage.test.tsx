// F2.18.3: tests for AdminStoreDetailPage.
//
// Mocks `../../hooks` to bypass TanStack Query and the API layer.
// Renders inside a MemoryRouter so `useParams()` resolves and the
// back-link can render.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import type {
  UseMutationResult,
  UseQueryResult,
} from "@tanstack/react-query";

import AdminStoreDetailPage from "../AdminStoreDetailPage";
import * as storesHooks from "../../hooks";
import type {
  DeactivateStoreParams,
  ReactivateStoreParams,
} from "../../api";
import type { StoreProfile } from "../../types";

// --------------------------------------------------------------------- //
// Hook mocks
// --------------------------------------------------------------------- //

vi.mock("../../hooks", () => ({
  useAdminStoresQuery: vi.fn(),
  useAdminStoreQuery: vi.fn(),
  useCreateStoreMutation: vi.fn(),
  useUpdateStoreMutation: vi.fn(),
  useDeactivateStoreMutation: vi.fn(),
  useReactivateStoreMutation: vi.fn(),
}));

// --------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------- //

const STORE_ID = "11111111-1111-1111-1111-111111111111";

function makeStore(overrides: Partial<StoreProfile> = {}): StoreProfile {
  return {
    id: STORE_ID,
    name: "Acme Cannabis Co",
    code: "ACME",
    is_active: true,
    timezone: "America/New_York",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    ...overrides,
  };
}

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeMutation<P>(
  o: { isPending?: boolean; isError?: boolean; error?: Error | null } = {},
) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    data: undefined,
  } as unknown as UseMutationResult<StoreProfile, Error, P> & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

function setupDefaultMutations() {
  vi.mocked(storesHooks.useDeactivateStoreMutation).mockReturnValue(
    makeMutation<DeactivateStoreParams>(),
  );
  vi.mocked(storesHooks.useReactivateStoreMutation).mockReturnValue(
    makeMutation<ReactivateStoreParams>(),
  );
}

function withRoute(
  node: ReactNode,
  path = `/app/admin/stores/${STORE_ID}`,
) {
  return (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/admin/stores/:storeId" element={node} />
        <Route
          path="/app/admin/stores"
          element={<div>stores list landing</div>}
        />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(storesHooks.useAdminStoreQuery).mockReset();
  setupDefaultMutations();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Chrome
// --------------------------------------------------------------------- //

describe("AdminStoreDetailPage — chrome", () => {
  it("renders the page heading and back link to /app/admin/stores", () => {
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: makeStore(),
      }),
    );
    render(withRoute(<AdminStoreDetailPage />));
    expect(
      screen.getByRole("heading", { level: 1, name: "Store detail" }),
    ).toBeInTheDocument();
    const back = screen.getByTestId("admin-store-detail-back-link");
    expect(back).toHaveAttribute("href", "/app/admin/stores");
  });
});

// --------------------------------------------------------------------- //
// Query states
// --------------------------------------------------------------------- //

describe("AdminStoreDetailPage — query states", () => {
  it("renders the loading state", () => {
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: true,
        isError: false,
        isSuccess: false,
      }),
    );
    render(withRoute(<AdminStoreDetailPage />));
    expect(screen.getByText(/loading store/i)).toBeInTheDocument();
  });

  it("renders the error state and retry", () => {
    const refetch = vi.fn();
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: true,
        isSuccess: false,
        error: new Error("not found"),
        refetch: refetch as never,
      }),
    );
    render(withRoute(<AdminStoreDetailPage />));
    expect(screen.getByText("Could not load store")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("renders the missing-id empty state when :storeId is empty", () => {
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: false,
        isSuccess: false,
      }),
    );
    // Route :storeId param empty — simulate via a route without the
    // matching id segment. MemoryRouter pointed at /app/admin/stores
    // would not match /app/admin/stores/:storeId, so we mount the
    // page directly without a route param.
    render(
      <MemoryRouter initialEntries={["/x"]}>
        <Routes>
          <Route path="/x" element={<AdminStoreDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Missing store id")).toBeInTheDocument();
  });

  it("renders the summary on happy path", () => {
    const store = makeStore({
      name: "Bravo",
      code: "BRAVO",
      timezone: "America/Chicago",
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-04-01T00:00:00Z",
    });
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: store,
      }),
    );
    render(withRoute(<AdminStoreDetailPage />));
    expect(screen.getByTestId("admin-store-summary-name")).toHaveTextContent(
      "Bravo",
    );
    expect(screen.getByTestId("admin-store-summary-code")).toHaveTextContent(
      "BRAVO",
    );
    expect(
      screen.getByTestId("admin-store-summary-timezone"),
    ).toHaveTextContent("America/Chicago");
    expect(
      screen.getByTestId("admin-store-summary-created"),
    ).toHaveTextContent("2026-03-01T00:00:00Z");
    expect(
      screen.getByTestId("admin-store-summary-updated"),
    ).toHaveTextContent("2026-04-01T00:00:00Z");
    expect(screen.getByTestId("store-status-active")).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Lifecycle action
// --------------------------------------------------------------------- //

describe("AdminStoreDetailPage — lifecycle", () => {
  it("active store shows a Deactivate store button", () => {
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: makeStore({ is_active: true }),
      }),
    );
    render(withRoute(<AdminStoreDetailPage />));
    expect(
      screen.getByTestId("admin-store-detail-lifecycle-button"),
    ).toHaveTextContent("Deactivate store");
  });

  it("inactive store shows a Reactivate store button", () => {
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: makeStore({ is_active: false }),
      }),
    );
    render(withRoute(<AdminStoreDetailPage />));
    expect(
      screen.getByTestId("admin-store-detail-lifecycle-button"),
    ).toHaveTextContent("Reactivate store");
  });

  it("clicking Deactivate store opens the lifecycle dialog and fires the mutation on confirm", () => {
    const mutateSpy = vi.fn();
    vi.mocked(storesHooks.useDeactivateStoreMutation).mockReturnValue(
      Object.assign(makeMutation<DeactivateStoreParams>(), {
        mutate: mutateSpy,
      }) as unknown as ReturnType<
        typeof storesHooks.useDeactivateStoreMutation
      >,
    );
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: makeStore({ id: STORE_ID, is_active: true }),
      }),
    );

    render(withRoute(<AdminStoreDetailPage />));
    fireEvent.click(
      screen.getByTestId("admin-store-detail-lifecycle-button"),
    );
    expect(
      screen.getByTestId("store-lifecycle-dialog"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("store-lifecycle-confirm"));
    expect(mutateSpy).toHaveBeenCalledWith({ storeId: STORE_ID });
  });

  it("clicking Reactivate store fires the reactivate mutation", () => {
    const mutateSpy = vi.fn();
    vi.mocked(storesHooks.useReactivateStoreMutation).mockReturnValue(
      Object.assign(makeMutation<ReactivateStoreParams>(), {
        mutate: mutateSpy,
      }) as unknown as ReturnType<
        typeof storesHooks.useReactivateStoreMutation
      >,
    );
    vi.mocked(storesHooks.useAdminStoreQuery).mockReturnValue(
      asQueryResult<StoreProfile>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: makeStore({ id: STORE_ID, is_active: false }),
      }),
    );

    render(withRoute(<AdminStoreDetailPage />));
    fireEvent.click(
      screen.getByTestId("admin-store-detail-lifecycle-button"),
    );
    fireEvent.click(screen.getByTestId("store-lifecycle-confirm"));
    expect(mutateSpy).toHaveBeenCalledWith({ storeId: STORE_ID });
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminStoreDetailPage — architecture", () => {
  it("does NOT import useAuth / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AdminStoreDetailPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\.role\s*===\s*["']/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });
});
