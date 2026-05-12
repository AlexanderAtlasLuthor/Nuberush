// F2.4: StoreProvider — derives tenancy context from the authenticated
// session. MUST live below AuthProvider in the provider tree.
//
// What it does:
//   - Reads the current AuthUser via useAuth().
//   - Computes currentStoreId / hasStoreContext / isStoreRequired /
//     storeError from `user.role` + `user.store_id`.
//
// What it deliberately does NOT do:
//   - Call any API. /auth/me already carries store_id; there is no
//     /stores endpoint to enumerate, and per the F2.4 brief we don't
//     invent one.
//   - Cache to localStorage / sessionStorage. There is no user-driven
//     selection to persist (data model only allows one store per user).
//   - Decide permissions. Backend is authority on every store-scoped
//     call via resolve_store_scope / require_store_member. The frontend
//     only carries the ID for use as a query/path param.
//   - Expose setCurrentStoreId. Multi-store selection is not supported
//     by the backend yet. When it lands (admin store picker + /stores
//     listing endpoint), add the setter and the corresponding UX.
//
// Recompute trigger: useMemo on user.role + user.store_id only. No
// effects, no async work.

import { createContext, useMemo } from "react";
import type { ReactNode } from "react";
import { useAuth } from "./useAuth";
import type { StoreContextState } from "./store-context.types";

export const StoreContext = createContext<StoreContextState | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  const value = useMemo<StoreContextState>(() => {
    // Unauthenticated: ProtectedRoute will redirect away from /app
    // before this is observed. We still return a coherent "neutral"
    // state so the provider works under MemoryRouter / public routes.
    if (user === null) {
      return {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
        storeError: null,
      };
    }

    const isAdmin = user.role === "admin";
    const isStoreRequired = !isAdmin;
    const currentStoreId = user.store_id;
    const hasStoreContext = currentStoreId !== null;

    let storeError: string | null = null;
    if (isStoreRequired && !hasStoreContext) {
      // Backend invariant says non-admin users always have a store_id.
      // If we observe otherwise it's a data anomaly worth surfacing —
      // the user can't perform any store-scoped action without one.
      storeError =
        "Your account is not bound to a store. Contact your administrator to be assigned.";
    }

    return {
      currentStoreId,
      hasStoreContext,
      isStoreRequired,
      storeError,
    };
  }, [user]);

  return (
    <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
  );
}
