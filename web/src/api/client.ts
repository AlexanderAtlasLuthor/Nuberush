// F2.2: centralized fetch-based API client.
//
// Single function (`apiRequest`) that every feature hook will go through.
// Keeps the surface tiny so swapping the transport later (axios, ky,
// HTTP/2 client) stays mechanical.
//
// Hard rules baked in:
//   - No React imports.
//   - No router imports.
//   - No TanStack Query imports.
//   - No redirect on 401. (F2.3 wires that into AuthProvider.)
//   - No automatic logout. (Same.)
//
// Behaviour:
//   - Path is appended to API_BASE_URL. Leading "/" optional.
//   - Authorization: Bearer <token> is auto-attached when
//     getAccessToken() returns a non-null value.
//   - Content-Type: application/json is auto-set when a non-FormData
//     body is provided (FormData lets the browser pick its own
//     multipart boundary).
//   - 2xx → JSON-parse and return; 204 / empty body → returns undefined.
//   - Non-2xx → throws ApiError preserving status, message and details.
//   - Network errors → throws ApiError with status 0.
//   - AbortError propagates as-is (TanStack Query expects this).

import { API_BASE_URL } from "./config";
import { ApiError } from "./errors";
import { getAccessToken } from "./session-token";

export type ApiMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface ApiRequestOptions {
  method?: ApiMethod;
  /** Object to JSON-serialize, or a FormData instance for uploads. */
  body?: unknown;
  /** Extra/override headers. Authorization is auto-attached if absent. */
  headers?: HeadersInit;
  /** Standard AbortController signal for cancellation. */
  signal?: AbortSignal;
}

function buildUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path; // absolute URL passthrough
  const prefix = path.startsWith("/") ? "" : "/";
  return `${API_BASE_URL}${prefix}${path}`;
}

function buildHeaders(
  body: unknown,
  custom: HeadersInit | undefined,
): Headers {
  const headers = new Headers(custom);

  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // Only set Content-Type when there's a JSON body to serialise.
  // FormData carries its own multipart boundary; the browser sets it.
  if (
    body !== undefined &&
    !(body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  // FastAPI returns JSON; tell the server we expect it.
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  return headers;
}

function serializeBody(body: unknown): BodyInit | undefined {
  if (body === undefined) return undefined;
  if (body instanceof FormData) return body;
  return JSON.stringify(body);
}

async function readErrorPayload(
  response: Response,
): Promise<{ message: string; details?: unknown; code?: string }> {
  const fallback = `Request failed with status ${response.status}`;
  let details: unknown;
  let message = fallback;
  let code: string | undefined;

  try {
    const text = await response.text();
    if (!text) return { message };
    const parsed: unknown = JSON.parse(text);
    if (parsed && typeof parsed === "object") {
      details = parsed;
      const obj = parsed as Record<string, unknown>;

      // FastAPI HTTPException(detail="...")
      if (typeof obj.detail === "string") {
        message = obj.detail;
      } else if (Array.isArray(obj.detail) && obj.detail.length > 0) {
        // Pydantic validation: take the first issue's message.
        const first = obj.detail[0] as { msg?: unknown };
        if (first && typeof first.msg === "string") message = first.msg;
      } else if (typeof obj.message === "string") {
        message = obj.message;
      }

      if (typeof obj.code === "string") code = obj.code;
    }
  } catch {
    // Body wasn't JSON (HTML 502 page, plain text, etc.). Use fallback.
  }

  return { message, details, code };
}

async function readSuccessPayload<TResponse>(
  response: Response,
): Promise<TResponse> {
  if (response.status === 204) return undefined as TResponse;

  const contentType = response.headers.get("Content-Type") ?? "";
  const text = await response.text();
  if (!text) return undefined as TResponse;

  if (!contentType.includes("application/json")) {
    // Non-JSON response (rare for FastAPI). Return the raw text so the
    // caller can decide what to do. Cast is intentional: callers that
    // request a JSON shape from a non-JSON endpoint will fail in their
    // own typings or runtime parsing.
    return text as unknown as TResponse;
  }

  try {
    return JSON.parse(text) as TResponse;
  } catch {
    throw new ApiError({
      status: response.status,
      message: "Failed to parse response JSON",
      details: { raw: text },
    });
  }
}

export async function apiRequest<TResponse = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  const { method = "GET", body, headers, signal } = options;

  const url = buildUrl(path);
  const finalHeaders = buildHeaders(body, headers);
  const finalBody = serializeBody(body);

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: finalHeaders,
      body: finalBody,
      signal,
    });
  } catch (err) {
    // Abort: let it propagate; TanStack Query handles cancellation.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    if (err instanceof Error && err.name === "AbortError") throw err;

    // Anything else is a network-level failure.
    throw new ApiError({
      status: 0,
      message: err instanceof Error ? err.message : "Network error",
    });
  }

  if (!response.ok) {
    const { message, details, code } = await readErrorPayload(response);
    throw new ApiError({ status: response.status, message, details, code });
  }

  return readSuccessPayload<TResponse>(response);
}
