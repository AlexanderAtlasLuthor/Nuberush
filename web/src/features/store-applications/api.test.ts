// F2.24.C6 — API-layer unit tests for public store-application intake.
// Mirrors features/store/api.test.ts: stub `@/api` and assert the URL,
// method and verbatim snake_case body. No fetch, no React, no Supabase.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import { submitStoreApplication } from "./api";
import * as applicationsApi from "./api";
import type {
  StoreApplicationSubmitRequest,
  StoreApplicationSubmitResponse,
} from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const PAYLOAD: StoreApplicationSubmitRequest = {
  business_name: "Acme Vapes",
  business_type: "vape_shop",
  owner_full_name: "Jane Owner",
  owner_email: "jane@example.com",
  owner_phone: "+1 555 0100",
  business_phone: "+1 555 0199",
  address_line_1: "1 Test Way",
  city: "Miami",
  state: "FL",
  postal_code: "33101",
  country: "US",
  location_count: 2,
  estimated_weekly_orders: 150,
  hours_of_operation: "Mon-Fri 9-5",
  terms_accepted: true,
};

const RESPONSE: StoreApplicationSubmitResponse = {
  id: "11111111-1111-1111-1111-111111111111",
  status: "pending_review",
  message: "Application submitted for review.",
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

describe("submitStoreApplication", () => {
  it("POSTs /public/store-applications with the payload verbatim", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(RESPONSE as never);

    const result = await submitStoreApplication(PAYLOAD);

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/public/store-applications");
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual(PAYLOAD);
    expect(result).toEqual(RESPONSE);
  });

  it("never sends forbidden / server-owned fields", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(RESPONSE as never);

    await submitStoreApplication(PAYLOAD);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    const sent = options?.body as Record<string, unknown>;
    for (const forbidden of [
      "status",
      "role",
      "store_id",
      "user_id",
      "auth_user_id",
      "is_admin",
      "reviewed_by_user_id",
      "provisioned_store_id",
      "provisioned_owner_user_id",
      "public_lookup_token",
      "created_at",
      "updated_at",
    ]) {
      expect(sent).not.toHaveProperty(forbidden);
    }
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    vi.mocked(apiRequest).mockResolvedValueOnce(RESPONSE as never);

    await submitStoreApplication(PAYLOAD, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("propagates errors from apiRequest unchanged", async () => {
    const boom = new Error("boom");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);

    await expect(submitStoreApplication(PAYLOAD)).rejects.toBe(boom);
  });
});

describe("store-applications api public surface", () => {
  it("exports only submitStoreApplication", () => {
    expect(Object.keys(applicationsApi).sort()).toEqual([
      "submitStoreApplication",
    ]);
  });
});
