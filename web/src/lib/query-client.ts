import { QueryClient } from "@tanstack/react-query";

// F2.1: shared TanStack Query client.
//
// Defaults are conservative for a production system:
//   retry: 1                        — one retry covers transient flakes
//                                     without compounding backend load
//   refetchOnWindowFocus: false     — prevents the noisy "every alt-tab
//                                     re-fetches everything" pattern
//   staleTime: 30s                  — data is treated as fresh for 30s
//                                     before background refetches kick in
//
// Override per-query as features require (e.g. inventory dashboards may
// want a shorter staleTime; static product catalogs may want longer).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: {
      retry: 0,
    },
  },
});
