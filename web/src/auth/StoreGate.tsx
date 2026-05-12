// F2.4: render-gate that blocks the app shell when the authenticated
// user is supposed to operate inside a store but has none.
//
// Position: sits BETWEEN ProtectedRoute and DashboardLayout in the
// /app route subtree. ProtectedRoute has already guaranteed that auth
// state is resolved and the user is signed in by the time we run, so
// we only need to inspect the derived store context.
//
// Behaviour:
//   isAuth loading → LoadingState (defensive — useAuth().isLoading
//                    should already be false here, but render the same
//                    "session-resolving" state if a race ever occurs)
//   storeError set → ErrorState with the spec's exact title
//                    "No store context available" and the human-readable
//                    detail from StoreProvider
//   otherwise      → <Outlet/> (admin in global scope, or non-admin
//                    with a valid store_id — both are allowed in)
//
// What this component intentionally does NOT do:
//   - redirect (would create a loop with ProtectedRoute and would also
//     hide a server-side data anomaly behind a quiet bounce)
//   - guess a default store (no enumeration endpoint, would fabricate
//     authority the frontend doesn't have)
//   - call the backend (no /stores endpoint to call)

import { Outlet } from "react-router-dom";
import { LoadingState } from "@/components/common/loading-state";
import { ErrorState } from "@/components/common/error-state";
import { useAuth } from "./useAuth";
import { useStoreContext } from "./useStoreContext";

export function StoreGate() {
  const { isLoading } = useAuth();
  const { isStoreRequired, hasStoreContext, storeError } = useStoreContext();

  if (isLoading) {
    return <LoadingState message="Restoring session…" />;
  }

  if (isStoreRequired && !hasStoreContext) {
    return (
      <ErrorState
        title="No store context available"
        message={
          storeError ??
          "Your account is not bound to a store. Contact your administrator."
        }
      />
    );
  }

  return <Outlet />;
}
