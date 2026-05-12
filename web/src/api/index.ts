// F2.2: barrel export for the API client foundation.
//
// Feature modules should import from `@/api` (this file) and not reach
// directly into the submodules. That keeps the client's public surface
// in one place and lets us refactor internals without ripple changes.

export { API_BASE_URL } from "./config";

export {
  ApiError,
  isApiError,
  getApiErrorMessage,
  type ApiErrorInit,
} from "./errors";

export {
  getAccessToken,
  setAccessToken,
  clearAccessToken,
} from "./session-token";

export {
  apiRequest,
  type ApiMethod,
  type ApiRequestOptions,
} from "./client";

export type {
  ApiListParams,
  PaginatedResponse,
  ApiSuccessResponse,
  ApiValidationIssue,
  ApiErrorResponse,
} from "./types";
