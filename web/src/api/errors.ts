// F2.2: typed error model for backend responses.
//
// Every non-2xx response from FastAPI is normalised to an `ApiError`
// before bubbling out of `apiRequest`. The class preserves the HTTP
// status, the parsed `detail` payload, and an optional code so feature
// hooks can branch on either `error.status` or `error.code`.
//
// Compatible with FastAPI's two error shapes:
//   - HTTPException → { "detail": "<string>" }
//   - Pydantic ValidationError → { "detail": [{ "loc": [...], "msg": "...", "type": "..." }] }
//
// Runtime helpers:
//   isApiError(e)         — type guard
//   getApiErrorMessage(e) — best-effort message extractor for any value

export interface ApiErrorInit {
  status: number;
  message: string;
  details?: unknown;
  code?: string;
}

export class ApiError extends Error {
  /** HTTP status code (0 for network/abort failures). */
  readonly status: number;
  /** Raw error payload from the backend, when available. */
  readonly details?: unknown;
  /** Application-level error code, if the backend supplied one. */
  readonly code?: string;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.details = init.details;
    this.code = init.code;

    // `extends Error` + ES target older than ES2015 can break instanceof.
    // Restoring the prototype keeps `e instanceof ApiError` reliable.
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function getApiErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return "Unknown error";
}
