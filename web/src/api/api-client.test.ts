// F2.2 / F2.22.2.G: focused unit tests for the API client foundation.
//
// Covers the error model and the Authorization-header behaviour of
// `apiRequest`. Since F2.22.2.G the Bearer token comes from the Supabase
// session (`@/lib/supabase`, mocked here), not a legacy in-memory holder.

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";
import { ApiError, getApiErrorMessage, isApiError } from "./errors";

const getSession = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: { getSession } },
}));

import { apiRequest } from "./client";

describe("ApiError", () => {
  it("preserves status, message, details and code", () => {
    const err = new ApiError({
      status: 422,
      message: "Insufficient stock.",
      details: { detail: "Insufficient stock." },
      code: "stock_insufficient",
    });
    expect(err.status).toBe(422);
    expect(err.message).toBe("Insufficient stock.");
    expect(err.details).toEqual({ detail: "Insufficient stock." });
    expect(err.code).toBe("stock_insufficient");
    expect(err.name).toBe("ApiError");
  });

  it("is an instance of Error and ApiError", () => {
    const err = new ApiError({ status: 500, message: "boom" });
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
  });

  it("does not require optional fields", () => {
    const err = new ApiError({ status: 0, message: "Network error" });
    expect(err.status).toBe(0);
    expect(err.details).toBeUndefined();
    expect(err.code).toBeUndefined();
  });
});

describe("isApiError", () => {
  it("returns true for an ApiError instance", () => {
    expect(
      isApiError(new ApiError({ status: 404, message: "not found" })),
    ).toBe(true);
  });

  it("returns false for a vanilla Error", () => {
    expect(isApiError(new Error("nope"))).toBe(false);
  });

  it("returns false for non-error values", () => {
    expect(isApiError("string")).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError(undefined)).toBe(false);
    expect(isApiError({ status: 500, message: "duck-typed" })).toBe(false);
  });
});

describe("getApiErrorMessage", () => {
  it("extracts message from ApiError", () => {
    expect(
      getApiErrorMessage(
        new ApiError({ status: 422, message: "Invalid transition." }),
      ),
    ).toBe("Invalid transition.");
  });

  it("extracts message from vanilla Error", () => {
    expect(getApiErrorMessage(new Error("x"))).toBe("x");
  });

  it("returns the input when given a string", () => {
    expect(getApiErrorMessage("plain string")).toBe("plain string");
  });

  it("falls back to 'Unknown error' for unknown values", () => {
    expect(getApiErrorMessage(undefined)).toBe("Unknown error");
    expect(getApiErrorMessage(null)).toBe("Unknown error");
    expect(getApiErrorMessage({ random: "object" })).toBe("Unknown error");
    expect(getApiErrorMessage(42)).toBe("Unknown error");
  });
});

describe("apiRequest Authorization header", () => {
  let fetchMock: Mock;

  function jsonResponse(): Response {
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn().mockResolvedValue(jsonResponse());
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the Supabase access token as a Bearer header", async () => {
    getSession.mockResolvedValue({
      data: { session: { access_token: "abc.def.ghi" } },
    });

    await apiRequest("/auth/me");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer abc.def.ghi");
  });

  it("sends no Authorization header when there is no session", async () => {
    getSession.mockResolvedValue({ data: { session: null } });

    await apiRequest("/auth/me");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
  });
});
