// F2.9.2 + F2.15.4: query-key factory for the users module.
//
// Single source of truth for every key shape this feature mounts in
// the TanStack Query cache. Read hooks build keys via these helpers,
// never by hand. Mutation hooks invalidate via the same helpers, so a
// key shape change can never desync read vs. invalidate.
//
// Shape contract (matches features/products and features/inventory):
//
//   usersQueryKeys.all ──────────── ["users"]
//   usersQueryKeys.lists() ──────── ["users", "list"]
//   usersQueryKeys.list(filters) ── ["users", "list", filters]
//   usersQueryKeys.details() ────── ["users", "detail"]
//   usersQueryKeys.detail(userId) ─ ["users", "detail", userId]
//
// Filter objects are stored verbatim; TanStack Query's `hashKey`
// JSON-stringifies with sorted keys and drops `undefined`, so two
// callers passing logically-equivalent filters share one cache slot
// regardless of property order.

import type { UserListFilters } from "../types";

export const usersQueryKeys = {
  /** Root namespace. Useful for nuking the entire users cache. */
  all: ["users"] as const,

  // ----- list -------------------------------------------------------- //

  /** Prefix for every list query (any filter set). */
  lists: () => [...usersQueryKeys.all, "list"] as const,

  /** Concrete key for one list query. */
  list: (filters: UserListFilters = {}) =>
    [...usersQueryKeys.lists(), filters] as const,

  // ----- detail ------------------------------------------------------ //

  /** Prefix for every single-user detail query. */
  details: () => [...usersQueryKeys.all, "detail"] as const,

  /** Concrete key for one single-user detail query. */
  detail: (userId: string) =>
    [...usersQueryKeys.details(), userId] as const,
};
