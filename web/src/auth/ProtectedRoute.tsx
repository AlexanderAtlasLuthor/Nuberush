// F2.3: route-level auth guard.
//
// Behaviour matrix:
//   isLoading           → render LoadingState (do NOT redirect — we
//                         don't know yet whether the user is logged in)
//   !isAuthenticated    → Navigate to /login (replace history; pass
//                         the current location in router state so the
//                         AuthScreen can return the user there post-
//                         login)
//   authenticated       → render <Outlet/> (the matched child route)
//
// What this component intentionally does NOT do:
//   - role/permission gating. Backend is authority. If a user is
//     allowed to be logged in, they reach the shell; the API will
//     return 401/403 for any data they shouldn't see, and feature
//     hooks surface that. UI-level role visibility (showing/hiding
//     menu items) is a later subphase concern.

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { LoadingState } from "@/components/common/loading-state";
import { useAuth } from "./useAuth";

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingState message="Restoring session…" />;
  }

  if (!isAuthenticated) {
    return (
      <Navigate to="/login" replace state={{ from: location }} />
    );
  }

  return <Outlet />;
}
