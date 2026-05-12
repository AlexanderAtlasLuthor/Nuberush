// F2.2: generic API types.
//
// These are the cross-cutting shapes the client itself uses. They are
// intentionally domain-agnostic — inventory, orders and product types
// belong to their own feature modules under `src/features/<domain>/types`
// and will arrive in later subphases.

/** Common pagination/filter inputs. Feature endpoints can extend this. */
export interface ApiListParams {
  limit?: number;
  offset?: number;
}

/** Server-side paginated envelope (when an endpoint chooses to use one). */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Optional success-envelope shape. Most FastAPI endpoints return the
 * payload directly; this type exists for endpoints that wrap responses
 * in `{ data: ... }`.
 */
export interface ApiSuccessResponse<T> {
  data: T;
}

/**
 * FastAPI's two error shapes, normalised into one type.
 *
 *   HTTPException(detail="...")
 *     →  { "detail": "..." }
 *
 *   Pydantic ValidationError
 *     →  { "detail": [{ "loc": [...], "msg": "...", "type": "..." }, ...] }
 */
export interface ApiValidationIssue {
  loc?: Array<string | number>;
  msg: string;
  type?: string;
}

export interface ApiErrorResponse {
  detail?: string | ApiValidationIssue[];
  code?: string;
  message?: string;
}
