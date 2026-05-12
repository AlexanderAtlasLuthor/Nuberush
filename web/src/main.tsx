import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { Providers } from "@/app/providers";
import { ErrorBoundary } from "@/app/error-boundary";
import { router } from "@/app/router";
import "./index.css";

// F2.1: production app entry.
//
// Mount order (outer → inner):
//   StrictMode      — surfaces unsafe lifecycles in dev (no prod cost)
//   ErrorBoundary   — catches uncaught render errors below this point
//   Providers       — TanStack Query, tooltips, toasters
//   RouterProvider  — react-router-dom v6 data router (see app/router.tsx)
//
// The legacy App.tsx (with its localStorage-driven RoleRouter and full
// page imports) remains on disk for visual reference during F2.x but is
// no longer mounted from main. Each role's pages will be moved into the
// new router as the corresponding F2 feature subphase ships.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <Providers>
        <RouterProvider router={router} />
      </Providers>
    </ErrorBoundary>
  </StrictMode>,
);
