// F2.14.4: query-key factory for the store-profile module.
//
// Single source of truth for every key shape this feature mounts in
// the TanStack Query cache. Centralising keys means:
//
//   - The read hook builds keys via the same helper, never by hand.
//   - The mutation hook invalidates via the same helper, so a key
//     shape change can never desync read vs. invalidate.
//
// Shape contract:
//
//   storeKeys.all          ──── ["store"]
//   storeKeys.detail(id)   ──── ["store", "detail", id]
//
// F2.14 only exposes a single store at a time per session
// (`useStoreContext().currentStoreId`), so no list/filter keys are
// needed. If a /stores listing endpoint ever lands, extend with
// `lists()` / `list(filters)` then.

export const storeKeys = {
  /** Root namespace. Useful for nuking the entire store cache. */
  all: ["store"] as const,

  /** Concrete key for one store-profile detail query. */
  detail: (storeId: string) =>
    [...storeKeys.all, "detail", storeId] as const,
};
