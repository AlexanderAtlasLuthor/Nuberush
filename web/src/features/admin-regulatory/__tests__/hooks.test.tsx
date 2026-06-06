// F2.26.6.B: hook + query-key tests for admin-regulatory.
//
// Pattern mirrors features/stores/hooks/__tests__/mutations.test.tsx: stub
// the feature's api module, render hooks under a fresh QueryClient, drive
// them, and assert (a) the api function was called with the variables
// verbatim and (b) the per-mutation invalidation contract. Query-key shape
// is asserted as pure unit tests. A final architecture guard greps the
// feature source for forbidden imports.

import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import {
  adminRegulatoryKeys,
  useAcknowledgeAdminRegulatoryAlert,
  useAdminRegulatoryAlert,
  useAdminRegulatoryAlertDecisions,
  useAdminRegulatoryAlerts,
  useDismissAdminRegulatoryAlert,
  useResolveAdminRegulatoryAlert,
} from "../hooks";
import * as regulatoryApi from "../api";
import type { ComplianceAlert } from "../types";

vi.mock("../api", () => ({
  getAdminRegulatoryAlerts: vi.fn(),
  getAdminRegulatoryAlert: vi.fn(),
  getAdminRegulatoryAlertDecisions: vi.fn(),
  acknowledgeAdminRegulatoryAlert: vi.fn(),
  dismissAdminRegulatoryAlert: vi.fn(),
  resolveAdminRegulatoryAlert: vi.fn(),
}));

const ALERT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

const SAMPLE_ALERT: ComplianceAlert = {
  id: ALERT_ID,
  notice_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
  product_id: null,
  match_id: null,
  severity: "high",
  status: "open",
  recommended_action: "hold",
  resolution_note: null,
  resolved_by_user_id: null,
  resolved_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

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

beforeEach(() => {
  vi.mocked(regulatoryApi.getAdminRegulatoryAlerts).mockReset();
  vi.mocked(regulatoryApi.getAdminRegulatoryAlert).mockReset();
  vi.mocked(regulatoryApi.getAdminRegulatoryAlertDecisions).mockReset();
  vi.mocked(regulatoryApi.acknowledgeAdminRegulatoryAlert).mockReset();
  vi.mocked(regulatoryApi.dismissAdminRegulatoryAlert).mockReset();
  vi.mocked(regulatoryApi.resolveAdminRegulatoryAlert).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Query keys
// --------------------------------------------------------------------- //

describe("adminRegulatoryKeys", () => {
  it("anchors every key under the 'admin-regulatory' root", () => {
    expect(adminRegulatoryKeys.all).toEqual(["admin-regulatory"]);
  });

  it("alerts(filters) appends 'alerts' + filters object verbatim", () => {
    expect(
      adminRegulatoryKeys.alerts({ status: "open", limit: 25 }),
    ).toEqual(["admin-regulatory", "alerts", { status: "open", limit: 25 }]);
  });

  it("alerts() defaults to an empty filters object (stable shape)", () => {
    expect(adminRegulatoryKeys.alerts()).toEqual([
      "admin-regulatory",
      "alerts",
      {},
    ]);
  });

  it("alert(alertId) includes the id under the 'alert' segment", () => {
    expect(adminRegulatoryKeys.alert(ALERT_ID)).toEqual([
      "admin-regulatory",
      "alert",
      ALERT_ID,
    ]);
  });

  it("decisions(alertId, params) extends the alert subtree with params", () => {
    expect(
      adminRegulatoryKeys.decisions(ALERT_ID, { limit: 10, offset: 0 }),
    ).toEqual([
      "admin-regulatory",
      "alert",
      ALERT_ID,
      "decisions",
      { limit: 10, offset: 0 },
    ]);
  });

  it("decisions() defaults params to an empty object", () => {
    expect(adminRegulatoryKeys.decisions(ALERT_ID)).toEqual([
      "admin-regulatory",
      "alert",
      ALERT_ID,
      "decisions",
      {},
    ]);
  });
});

// --------------------------------------------------------------------- //
// Read hooks
// --------------------------------------------------------------------- //

describe("useAdminRegulatoryAlerts", () => {
  it("calls getAdminRegulatoryAlerts with the filters and a signal", async () => {
    vi.mocked(regulatoryApi.getAdminRegulatoryAlerts).mockResolvedValue({
      items: [SAMPLE_ALERT],
      total: 1,
      limit: 25,
      offset: 0,
    });
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminRegulatoryAlerts({ status: "open" }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(regulatoryApi.getAdminRegulatoryAlerts).toHaveBeenCalledTimes(1);
    const [filters, signal] = vi.mocked(
      regulatoryApi.getAdminRegulatoryAlerts,
    ).mock.calls[0];
    expect(filters).toEqual({ status: "open" });
    expect(signal).toBeInstanceOf(AbortSignal);
  });
});

describe("useAdminRegulatoryAlert", () => {
  it("calls getAdminRegulatoryAlert when alertId is present", async () => {
    vi.mocked(regulatoryApi.getAdminRegulatoryAlert).mockResolvedValue(
      SAMPLE_ALERT,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminRegulatoryAlert(ALERT_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(regulatoryApi.getAdminRegulatoryAlert).toHaveBeenCalledWith(
      ALERT_ID,
      expect.any(AbortSignal),
    );
  });

  it("stays idle and never calls the api when alertId is missing", () => {
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminRegulatoryAlert(undefined),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(regulatoryApi.getAdminRegulatoryAlert).not.toHaveBeenCalled();
  });
});

describe("useAdminRegulatoryAlertDecisions", () => {
  it("calls getAdminRegulatoryAlertDecisions with id, params and signal", async () => {
    vi.mocked(
      regulatoryApi.getAdminRegulatoryAlertDecisions,
    ).mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminRegulatoryAlertDecisions(ALERT_ID, { limit: 10 }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(
      regulatoryApi.getAdminRegulatoryAlertDecisions,
    ).toHaveBeenCalledWith(ALERT_ID, { limit: 10 }, expect.any(AbortSignal));
  });

  it("stays idle when alertId is missing", () => {
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminRegulatoryAlertDecisions(null),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(
      regulatoryApi.getAdminRegulatoryAlertDecisions,
    ).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Mutation hooks
// --------------------------------------------------------------------- //

const EXPECTED_LISTS_KEY = ["admin-regulatory", "alerts"];
const EXPECTED_ALERT_KEY = ["admin-regulatory", "alert", ALERT_ID];
const EXPECTED_DECISIONS_KEY = [
  "admin-regulatory",
  "alert",
  ALERT_ID,
  "decisions",
];

function expectInvalidatesAlertSubtree(invalidateSpy: ReturnType<typeof vi.spyOn>) {
  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: EXPECTED_LISTS_KEY });
  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: EXPECTED_ALERT_KEY });
  expect(invalidateSpy).toHaveBeenCalledWith({
    queryKey: EXPECTED_DECISIONS_KEY,
  });
}

describe("useAcknowledgeAdminRegulatoryAlert", () => {
  it("calls the api and invalidates list, detail and decision trail", async () => {
    vi.mocked(regulatoryApi.acknowledgeAdminRegulatoryAlert).mockResolvedValue(
      { ...SAMPLE_ALERT, status: "acknowledged" },
    );
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => useAcknowledgeAdminRegulatoryAlert(),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({ alertId: ALERT_ID, body: { reason: "reviewing" } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      regulatoryApi.acknowledgeAdminRegulatoryAlert,
    ).toHaveBeenCalledWith(ALERT_ID, { reason: "reviewing" });
    expectInvalidatesAlertSubtree(invalidateSpy);
  });
});

describe("useDismissAdminRegulatoryAlert", () => {
  it("calls the api and invalidates the alert subtree", async () => {
    vi.mocked(regulatoryApi.dismissAdminRegulatoryAlert).mockResolvedValue({
      ...SAMPLE_ALERT,
      status: "dismissed",
    });
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDismissAdminRegulatoryAlert(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ alertId: ALERT_ID, body: { reason: "not ours" } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(regulatoryApi.dismissAdminRegulatoryAlert).toHaveBeenCalledWith(
      ALERT_ID,
      { reason: "not ours" },
    );
    expectInvalidatesAlertSubtree(invalidateSpy);
  });
});

describe("useResolveAdminRegulatoryAlert", () => {
  it("calls the api with the resolve body and invalidates the alert subtree", async () => {
    vi.mocked(regulatoryApi.resolveAdminRegulatoryAlert).mockResolvedValue({
      ...SAMPLE_ALERT,
      status: "actioned",
    });
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useResolveAdminRegulatoryAlert(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      alertId: ALERT_ID,
      body: { action: "hold", resolution_note: "pending review" },
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(regulatoryApi.resolveAdminRegulatoryAlert).toHaveBeenCalledWith(
      ALERT_ID,
      { action: "hold", resolution_note: "pending review" },
    );
    expectInvalidatesAlertSubtree(invalidateSpy);
  });
});

// --------------------------------------------------------------------- //
// Architecture guard — forbidden imports never leak into this feature
// --------------------------------------------------------------------- //

describe("admin-regulatory architecture guards", () => {
  // Strip comments so the guards inspect actual code, not the docstrings
  // (which deliberately spell out "No fetch()", "No Supabase", etc.).
  function stripComments(src: string): string {
    return src
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/[^\n]*/g, "");
  }

  const sources = ["../api.ts", "../hooks.ts", "../types.ts"].map((rel) =>
    stripComments(readFileSync(new URL(rel, import.meta.url), "utf8")),
  );

  it("never calls fetch() directly", () => {
    for (const src of sources) {
      expect(src).not.toMatch(/\bfetch\s*\(/);
    }
  });

  it("never imports the Supabase client", () => {
    for (const src of sources) {
      expect(src.toLowerCase()).not.toContain("supabase");
    }
  });

  it("never imports auth or store context", () => {
    for (const src of sources) {
      expect(src).not.toMatch(/useAuth|AuthContext|AuthProvider/);
      expect(src).not.toMatch(/useStoreContext|StoreContext|StoreProvider/);
      // No imports from auth/store context modules.
      expect(src).not.toMatch(/from\s+["'][^"']*\/(auth|store)\//);
    }
  });
});
