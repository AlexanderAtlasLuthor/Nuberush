// F2.3 / F2.22.2.G: frontend mirror of the FastAPI auth contract.
//
// Sources of truth (do NOT diverge without updating both sides):
//   - backend/app/schemas/auth.py   (UserRead, CreateUserRequest)
//   - backend/app/db/models.py      (UserRole enum)
//
// Field names match the wire format exactly (snake_case from FastAPI).
// Don't camelCase here — that mapping belongs in feature hooks if/when
// it makes sense, not at the type-edge. Keeping the wire shape avoids
// silent drift the day a backend field is renamed.
//
// F2.22.2.G note: there is no `LoginResponse`/token type anymore — the
// access token lives in the Supabase session, not an app type.

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

/** Email + password submitted to `supabase.auth.signInWithPassword`. */
export interface LoginCredentials {
  email: string;
  password: string;
}
