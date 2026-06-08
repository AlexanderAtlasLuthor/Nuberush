// Mutation-hook tests for the writable admin-settings surface (F2.27.10).
//
// Stub `../../api` so `patchAdminSettings` resolves under control; render the
// hook under a fresh QueryClient, mutate, and assert (a) the api was called
// with the payload verbatim and (b) the snapshot query is invalidated on
// success. No StoreContext, no store_id.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useUpdateAdminSettingsMutation } from "../useUpdateAdminSettingsMutation";
import { adminSettingsKeys } from "../queryKeys";
import * as adminSettingsApi from "../../api";
import type { AdminSettingsResponse } from "../../types";

vi.mock("../../api", () => ({
  patchAdminSettings: vi.fn(),
}));

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

const RESPONSE = {
  editable: {
    platform_name: "Acme",
    support_email: null,
    default_locale: "en-US",
    default_timezone: "America/New_York",
  },
} as unknown as AdminSettingsResponse;

beforeEach(() => {
  vi.mocked(adminSettingsApi.patchAdminSettings).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useUpdateAdminSettingsMutation", () => {
  it("calls patchAdminSettings with the payload and invalidates the snapshot", async () => {
    vi.mocked(adminSettingsApi.patchAdminSettings).mockResolvedValue(RESPONSE);
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateAdminSettingsMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ platform_name: "Acme" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(adminSettingsApi.patchAdminSettings).toHaveBeenCalledWith({
      platform_name: "Acme",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminSettingsKeys.snapshot(),
    });
  });

  it("surfaces an api error without invalidating", async () => {
    const boom = new Error("422 Unprocessable Entity");
    vi.mocked(adminSettingsApi.patchAdminSettings).mockRejectedValue(boom);
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateAdminSettingsMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ platform_name: "x" });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBe(boom);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
