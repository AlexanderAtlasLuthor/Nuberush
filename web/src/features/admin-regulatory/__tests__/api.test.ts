// F2.26.6.B: API-layer unit tests for admin-regulatory.
//
// Strategy mirrors features/audit/api.test.ts: stub `@/api` so every call
// resolves against a controlled `apiRequest` mock. We assert URL, HTTP
// method, query string, request body and AbortSignal forwarding — exactly
// what the wire contract guarantees. No fetch, no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  acknowledgeAdminRegulatoryAlert,
  dismissAdminRegulatoryAlert,
  getAdminRegulatoryAggregate,
  getAdminRegulatoryAlert,
  getAdminRegulatoryAlertDecisions,
  getAdminRegulatoryAlerts,
  resolveAdminRegulatoryAlert,
} from "../api";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const ALERT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const PRODUCT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const NOTICE_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc";
const ALERTS = "/admin/regulatory/alerts";
const AGGREGATE = "/admin/regulatory/aggregate";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// getAdminRegulatoryAlerts
// --------------------------------------------------------------------- //

describe("getAdminRegulatoryAlerts", () => {
  it("calls GET /admin/regulatory/alerts with no query when no filters", async () => {
    await getAdminRegulatoryAlerts();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(ALERTS);
    expect(path).not.toMatch(/\?/);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises status / severity / recommended_action / product_id / notice_id / limit / offset", async () => {
    await getAdminRegulatoryAlerts({
      limit: 25,
      offset: 50,
      status: "open",
      severity: "high",
      recommended_action: "hold",
      product_id: PRODUCT_ID,
      notice_id: NOTICE_ID,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `${ALERTS}?limit=25&offset=50&status=open&severity=high` +
        `&recommended_action=hold&product_id=${PRODUCT_ID}&notice_id=${NOTICE_ID}`,
    );
  });

  it("preserves an explicit offset=0 on the wire", async () => {
    await getAdminRegulatoryAlerts({ offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}?offset=0`);
  });

  it("omits undefined filters from the query string", async () => {
    await getAdminRegulatoryAlerts({ status: "acknowledged" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}?status=acknowledged`);
  });

  it("drops empty / whitespace-only product_id and notice_id filters", async () => {
    await getAdminRegulatoryAlerts({ product_id: "   ", notice_id: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(ALERTS);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminRegulatoryAlerts({ limit: 10 }, controller.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("propagates ApiError from apiRequest untouched", async () => {
    const boom = new Error("403 Forbidden");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(getAdminRegulatoryAlerts()).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// getAdminRegulatoryAggregate (F2.27.5)
// --------------------------------------------------------------------- //

describe("getAdminRegulatoryAggregate", () => {
  it("calls GET /admin/regulatory/aggregate with no query when no filters", async () => {
    await getAdminRegulatoryAggregate();

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(AGGREGATE);
    expect(path).not.toMatch(/\?/);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises the same filter dimensions as the list (no limit/offset)", async () => {
    await getAdminRegulatoryAggregate({
      // limit/offset are list-only and must NOT appear on the aggregate query.
      limit: 25,
      offset: 50,
      status: "open",
      severity: "high",
      recommended_action: "hold",
      product_id: PRODUCT_ID,
      notice_id: NOTICE_ID,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `${AGGREGATE}?status=open&severity=high&recommended_action=hold` +
        `&product_id=${PRODUCT_ID}&notice_id=${NOTICE_ID}`,
    );
    expect(path).not.toMatch(/limit=/);
    expect(path).not.toMatch(/offset=/);
  });

  it("drops empty / whitespace-only product_id and notice_id filters", async () => {
    await getAdminRegulatoryAggregate({ product_id: "  ", notice_id: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(AGGREGATE);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminRegulatoryAggregate({ status: "open" }, controller.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("propagates ApiError from apiRequest untouched", async () => {
    const boom = new Error("403 Forbidden");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(getAdminRegulatoryAggregate()).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// getAdminRegulatoryAlert
// --------------------------------------------------------------------- //

describe("getAdminRegulatoryAlert", () => {
  it("calls GET /admin/regulatory/alerts/{alert_id}", async () => {
    await getAdminRegulatoryAlert(ALERT_ID);

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/${ALERT_ID}`);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("URL-encodes the alertId path segment", async () => {
    await getAdminRegulatoryAlert("weird id");
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/weird%20id`);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminRegulatoryAlert(ALERT_ID, controller.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

// --------------------------------------------------------------------- //
// getAdminRegulatoryAlertDecisions
// --------------------------------------------------------------------- //

describe("getAdminRegulatoryAlertDecisions", () => {
  it("calls GET /admin/regulatory/alerts/{alert_id}/decisions with no query when no params", async () => {
    await getAdminRegulatoryAlertDecisions(ALERT_ID);

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/${ALERT_ID}/decisions`);
    expect(path).not.toMatch(/\?/);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset", async () => {
    await getAdminRegulatoryAlertDecisions(ALERT_ID, { limit: 25, offset: 10 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/${ALERT_ID}/decisions?limit=25&offset=10`);
  });

  it("preserves an explicit offset=0", async () => {
    await getAdminRegulatoryAlertDecisions(ALERT_ID, { offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/${ALERT_ID}/decisions?offset=0`);
  });

  it("URL-encodes the alertId path segment", async () => {
    await getAdminRegulatoryAlertDecisions("weird id");
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/weird%20id/decisions`);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminRegulatoryAlertDecisions(
      ALERT_ID,
      { limit: 5 },
      controller.signal,
    );
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

// --------------------------------------------------------------------- //
// Lifecycle mutations
// --------------------------------------------------------------------- //

describe("acknowledgeAdminRegulatoryAlert", () => {
  it("POSTs the reason body to /acknowledge", async () => {
    await acknowledgeAdminRegulatoryAlert(ALERT_ID, { reason: "reviewing" });

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/${ALERT_ID}/acknowledge`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({ reason: "reviewing" });
    expect(options?.signal).toBeUndefined();
  });
});

describe("dismissAdminRegulatoryAlert", () => {
  it("POSTs the reason body to /dismiss", async () => {
    await dismissAdminRegulatoryAlert(ALERT_ID, { reason: "not ours" });

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/${ALERT_ID}/dismiss`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({ reason: "not ours" });
  });
});

describe("resolveAdminRegulatoryAlert", () => {
  it("POSTs a no_action resolve body", async () => {
    await resolveAdminRegulatoryAlert(ALERT_ID, {
      action: "no_action",
      resolution_note: "fine",
    });

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`${ALERTS}/${ALERT_ID}/resolve`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({
      action: "no_action",
      resolution_note: "fine",
    });
  });

  it("POSTs a hold resolve body", async () => {
    await resolveAdminRegulatoryAlert(ALERT_ID, {
      action: "hold",
      resolution_note: "pending review",
    });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({
      action: "hold",
      resolution_note: "pending review",
    });
  });

  it("POSTs a ban resolve body", async () => {
    await resolveAdminRegulatoryAlert(ALERT_ID, {
      action: "ban",
      resolution_note: "FDA enforcement",
    });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({
      action: "ban",
      resolution_note: "FDA enforcement",
    });
  });
});
