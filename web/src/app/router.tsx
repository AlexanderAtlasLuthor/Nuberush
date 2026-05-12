import { createBrowserRouter, Navigate } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import AuthScreen from "@/pages/AuthScreen";
import { ProtectedRoute, StoreGate } from "@/auth";
import DashboardHomePage from "@/features/dashboard/pages/DashboardHomePage";
import OrdersPage from "@/features/orders/pages/OrdersPage";
import CreateOrderPage from "@/features/orders/pages/CreateOrderPage";
import OrderDetailPage from "@/features/orders/pages/OrderDetailPage";
import InventoryPage from "@/features/inventory/pages/InventoryPage";
import AdminDashboardPage from "@/features/admin-dashboard/pages/AdminDashboardPage";
import AdminOperationsPage from "@/features/admin-operations/pages/AdminOperationsPage";
import AdminInventoryPage from "@/features/inventory/pages/AdminInventoryPage";
import AdminOrdersPage from "@/features/orders/pages/AdminOrdersPage";
import ProductsPage from "@/features/products/pages/ProductsPage";
import ProductDetailPage from "@/features/products/pages/ProductDetailPage";
import UsersPage from "@/features/users/pages/UsersPage";
import AuditPage from "@/features/audit/pages/AuditPage";
import AdminAuditPage from "@/features/audit/pages/AdminAuditPage";
import StoreSettingsPage from "@/features/store/pages/StoreSettingsPage";
import AdminStoresPage from "@/features/stores/pages/AdminStoresPage";
import AdminStoreDetailPage from "@/features/stores/pages/AdminStoreDetailPage";
import {
  AdminCompliancePlaceholder,
  AdminProductsPlaceholder,
  AdminSettingsPlaceholder,
  AdminShell,
  AppIndexRedirect,
  LegacyInventoryRedirect,
  LegacyOrderRedirect,
  LegacyProductRedirect,
  StoreShell,
  StoreRedirect,
} from "./route-components";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <Navigate to="/app" replace />,
  },
  {
    path: "/login",
    element: <AuthScreen />,
  },
  {
    path: "/app",
    element: <ProtectedRoute />,
    children: [
      { index: true, element: <AppIndexRedirect /> },
      { path: "products", element: <LegacyProductRedirect /> },
      { path: "products/:productId", element: <LegacyProductRedirect /> },
      { path: "inventory", element: <LegacyInventoryRedirect /> },
      { path: "inventory/:variantId", element: <LegacyInventoryRedirect /> },
      { path: "orders", element: <LegacyOrderRedirect /> },
      { path: "orders/new", element: <StoreRedirect to="orders/new" /> },
      { path: "orders/:orderId", element: <LegacyOrderRedirect /> },
      { path: "users", element: <StoreRedirect to="users" /> },
      { path: "audit", element: <StoreRedirect to="audit" /> },
      { path: "settings", element: <StoreRedirect to="settings" /> },
      {
        path: "admin",
        element: <AdminShell />,
        children: [
          // F2.19.5: real admin dashboard replaces the placeholder.
          // The placeholder component remains defined in
          // route-components.tsx (unused) so the deletion footprint is
          // limited to the router; same convention used in F2.15.7,
          // F2.18.3, F2.18.4, and F2.18.5.
          { index: true, element: <AdminDashboardPage /> },
          // F2.18.3: real admin stores list + detail replace the
          // placeholders. The placeholder components remain defined in
          // route-components.tsx (unused) so the deletion footprint is
          // limited to the router; same convention used in F2.15.7.
          { path: "stores", element: <AdminStoresPage /> },
          { path: "stores/:storeId", element: <AdminStoreDetailPage /> },
          // F2.15.7: real users management replaces the placeholder.
          // Same component handles both /app/store/users (store scope)
          // and /app/admin/users (global scope); the page reads
          // `useLocation()` to decide which UX hints to flip.
          { path: "users", element: <UsersPage /> },
          { path: "products", element: <AdminProductsPlaceholder /> },
          // F2.18.5: real admin global inventory and orders read-only
          // pages replace the placeholders. Placeholder components
          // remain defined in route-components.tsx (unused) so the
          // deletion footprint is limited to the router; same
          // convention used in F2.15.7, F2.18.3 and F2.18.4.
          { path: "inventory", element: <AdminInventoryPage /> },
          { path: "orders", element: <AdminOrdersPage /> },
          // F2.18.4: real admin global audit feed replaces the
          // placeholder. The placeholder component remains defined in
          // route-components.tsx (unused) so the deletion footprint is
          // limited to the router; same convention used in F2.15.7
          // and F2.18.3.
          { path: "audit", element: <AdminAuditPage /> },
          { path: "compliance", element: <AdminCompliancePlaceholder /> },
          // F2.19.6: real admin operations alerts page replaces the
          // placeholder. The placeholder component remains defined in
          // route-components.tsx (unused) so the deletion footprint is
          // limited to the router; same convention used in F2.15.7,
          // F2.18.3, F2.18.4, F2.18.5, and F2.19.5.
          { path: "operations", element: <AdminOperationsPage /> },
          { path: "settings", element: <AdminSettingsPlaceholder /> },
        ],
      },
      {
        path: "store",
        element: <StoreGate />,
        children: [
          {
            element: <StoreShell />,
            children: [
              { index: true, element: <DashboardHomePage /> },
              { path: "products", element: <ProductsPage /> },
              {
                path: "products/:productId",
                element: <ProductDetailPage />,
              },
              { path: "inventory", element: <InventoryPage /> },
              { path: "inventory/:variantId", element: <InventoryPage /> },
              { path: "orders", element: <OrdersPage /> },
              { path: "orders/new", element: <CreateOrderPage /> },
              { path: "orders/:orderId", element: <OrderDetailPage /> },
              { path: "users", element: <UsersPage /> },
              { path: "audit", element: <AuditPage /> },
              { path: "settings", element: <StoreSettingsPage /> },
            ],
          },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(appRoutes);
