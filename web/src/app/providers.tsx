import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { queryClient } from "@/lib/query-client";
import { AuthProvider, StoreProvider } from "@/auth";

// F2.1 / F2.3 / F2.4: top-level provider stack for the production app shell.
//
// Order (outermost → innermost):
//   QueryClientProvider — TanStack Query cache. Outermost so any provider
//                         or hook below it can use react-query.
//   AuthProvider        — session state. Sits inside the query client so
//                         a future query-based session bootstrap can use
//                         the same cache.
//   StoreProvider       — derives tenancy/store context from useAuth().
//                         MUST be inside AuthProvider (it reads the user
//                         via useAuth) and is intentionally above
//                         TooltipProvider so tooltipped UI in the shell
//                         can read store context too.
//   TooltipProvider     — Radix tooltip context.
//   children            — RouterProvider mounts here in main.tsx.
//   Toaster / Sonner    — global toast portals; placed after children
//                         so they render on top of the route tree.
export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <StoreProvider>
          <TooltipProvider>
            {children}
            <Toaster />
            <Sonner />
          </TooltipProvider>
        </StoreProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
