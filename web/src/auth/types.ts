// F2.3: frontend mirror of the FastAPI auth contract.
//
// Sources of truth (do NOT diverge without updating both sides):
//   - backend/app/schemas/auth.py   (LoginRequest, TokenResponse, UserRead)
//   - backend/app/db/models.py      (UserRole enum)
//
// Field names match the wire format exactly (snake_case from FastAPI).
// Don't camelCase here — that mapping belongs in feature hooks if/when
// it makes sense, not at the type-edge. Keeping the wire shape avoids
// silent drift the day a backend field is renamed.

/** Roles the backend may return on /auth/me. Source: app.db.models.UserRole. */
export type UserRole = "owner" | "manager" | "staff" | "driver" | "admin";

/** UserRead from backend/app/schemas/auth.py. */
export interface AuthUser {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  store_id: string | null;
  is_active: boolean;
}

/** Body accepted by POST /auth/login (LoginRequest). */
export interface LoginCredentials {
  email: string;
  password: string;
}

/** TokenResponse from POST /auth/login. token_type is always "bearer". */
export interface LoginResponse {
  access_token: string;
  token_type: string;
}

/**
 * In-app session aggregate. Note: the current backend does NOT issue a
 * refresh token — `access_token` is the only credential. When the
 * backend grows refresh/cookie support, extend this type rather than
 * inventing new ones.
 */
export interface AuthSession {
  user: AuthUser;
  accessToken: string;
}
