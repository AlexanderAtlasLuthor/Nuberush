// F2.3: barrel for the auth module.
//
// Feature code should import from `@/auth` rather than reaching into
// individual files; this keeps the public surface in one place and lets
// internals change without ripple edits.

export { AuthProvider, AuthContext } from "./AuthProvider";
export type { AuthContextValue } from "./AuthProvider";

export { useAuth } from "./useAuth";

export { ProtectedRoute } from "./ProtectedRoute";

export { StoreProvider, StoreContext } from "./StoreProvider";
export { useStoreContext } from "./useStoreContext";
export { StoreGate } from "./StoreGate";

export type { AuthUser, LoginCredentials, UserRole } from "./types";

export type {
  StoreContextState,
  CurrentStore,
} from "./store-context.types";
