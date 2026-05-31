// F2.24.C7: TanStack Query cache keys for admin store applications.
//
// Centralised key factory so queries and mutations agree on the exact
// tuple shapes. Invalidation in mutations targets these keys; never
// hand-roll a key tuple at a call site.
//
// Shapes:
//   ["admin-store-applications"]                    → feature root
//   ["admin-store-applications","list", filters]    → one list page/filter
//   ["admin-store-applications","detail", id]       → one application

import type { StoreApplicationListFilters } from "../types";

export const adminStoreApplicationsKeys = {
  all: ["admin-store-applications"] as const,
  lists: () => [...adminStoreApplicationsKeys.all, "list"] as const,
  list: (filters: StoreApplicationListFilters = {}) =>
    [...adminStoreApplicationsKeys.lists(), filters] as const,
  details: () => [...adminStoreApplicationsKeys.all, "detail"] as const,
  detail: (applicationId: string) =>
    [...adminStoreApplicationsKeys.details(), applicationId] as const,
};
