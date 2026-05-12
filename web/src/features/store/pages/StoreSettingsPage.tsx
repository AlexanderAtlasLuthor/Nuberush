// F2.14.6: Store Settings page.
//
// Wires the store-profile feature into a real surface:
//
//   useStoreContext().currentStoreId
//     → useStoreQuery(currentStoreId)
//     → useUpdateStoreMutation(currentStoreId)
//     → <StoreSettingsForm onSubmit={handleSubmit} />
//
// Render branches (in order, first match wins):
//
//   1. !currentStoreId         → EmptyState ("No store selected…").
//                                We never call the API in this branch
//                                because `useStoreQuery(null)` is
//                                disabled by design.
//   2. storeQuery.isLoading    → LoadingState.
//   3. storeQuery.isError      → ErrorState with retry → query.refetch().
//   4. !storeQuery.data        → EmptyState (defensive; backend always
//                                returns a row in success).
//   5. happy path              → header + StoreSettingsForm bound to
//                                the mutation.
//
// Non-decisions (deliberately):
//   - No onCancel handler. Settings is a leaf page; there's no
//     conventional "cancel" destination wired into the navigation.
//     The form's local Cancel reset is enough; if a future redesign
//     introduces a parent flow, plumb a navigate-back callback then.
//   - No optimistic UI. The mutation invalidates the detail key on
//     success (F2.14.4) and the refetched data re-seeds the form via
//     the form's `useEffect` on `store.*`.
//   - No client-side permission gate. Manager / staff / driver get a
//     403 from the backend when they submit; the form surfaces the
//     server detail verbatim. Hiding the form for those roles is a
//     UX optimisation that belongs in a parent layout, not here.

import { Settings } from "lucide-react";

import { getApiErrorMessage } from "@/api";
import { useStoreContext } from "@/auth";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { useToast } from "@/hooks/use-toast";

import { StoreSettingsForm } from "../components/StoreSettingsForm";
import { useStoreQuery, useUpdateStoreMutation } from "../hooks";
import type { StoreUpdateRequest } from "../types";

function PageHeader() {
  return (
    <header className="space-y-2">
      <div className="flex items-center gap-2">
        <Settings
          className="h-5 w-5 text-muted-foreground"
          aria-hidden="true"
        />
        <h1 className="text-xl font-semibold">Store settings</h1>
      </div>
      <p className="text-sm text-muted-foreground">
        Manage the basic profile and timezone for this store.
      </p>
    </header>
  );
}

export default function StoreSettingsPage() {
  const { currentStoreId } = useStoreContext();
  const storeQuery = useStoreQuery(currentStoreId);

  // Hooks must be called unconditionally; guard the *call site* of the
  // mutation, not the hook construction. Passing "" when there's no
  // store id keeps the type happy and is harmless because submit can
  // only fire from the form, which only renders in the data branch.
  const updateMutation = useUpdateStoreMutation(currentStoreId ?? "");
  const { toast } = useToast();

  const handleSubmit = async (payload: StoreUpdateRequest) => {
    if (!currentStoreId) return;
    // The mutation hook owns error state — `mutation.error` flows back
    // into the form's `errorMessage` prop below. Catch the promise so
    // the rejection doesn't surface as an unhandled error; we don't
    // re-toast on failure because the inline form error is the
    // primary surface (and an error toast would double-message).
    try {
      await updateMutation.mutateAsync(payload);
      toast({ title: "Store settings updated." });
    } catch {
      // Intentionally empty: the form renders the failure via
      // `errorMessage`, no further side-effects required here.
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-3xl">
      <PageHeader />

      {!currentStoreId ? (
        <EmptyState
          icon={Settings}
          title="No store selected"
          message="No store selected for the current session."
        />
      ) : storeQuery.isLoading ? (
        <LoadingState message="Store settings are loading." />
      ) : storeQuery.isError ? (
        <ErrorState
          title="Store settings failed to load."
          message={getApiErrorMessage(storeQuery.error)}
          onRetry={() => storeQuery.refetch()}
        />
      ) : !storeQuery.data ? (
        <EmptyState
          icon={Settings}
          title="No store profile"
          message="No store profile returned for the current store."
        />
      ) : (
        <StoreSettingsForm
          store={storeQuery.data}
          isPending={updateMutation.isPending}
          errorMessage={
            updateMutation.error
              ? getApiErrorMessage(updateMutation.error)
              : null
          }
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}
