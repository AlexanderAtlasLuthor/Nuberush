import { createBrowserRouter } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import AuthScreen from "@/pages/AuthScreen";
import AuthCallbackPage from "@/pages/AuthCallbackPage";
import SetPasswordPage from "@/pages/SetPasswordPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import StoreOnboardingPage from "@/features/store-onboarding/pages/StoreOnboardingPage";
import { ProtectedRoute, StoreGate } from "@/auth";
import DashboardHomePage from "@/features/dashboard/pages/DashboardHomePage";
import OrdersPage from "@/features/orders/pages/OrdersPage";
import CreateOrderPage from "@/features/orders/pages/CreateOrderPage";
import OrderDetailPage from "@/features/orders/pages/OrderDetailPage";
import InventoryPage from "@/features/inventory/pages/InventoryPage";
import AdminDashboardPage from "@/features/admin-dashboard/pages/AdminDashboardPage";
import AdminEarningsPage from "@/features/admin-earnings/pages/AdminEarningsPage";
import StoreEarningsPage from "@/features/store-earnings/pages/StoreEarningsPage";
import AdminOperationsPage from "@/features/admin-operations/pages/AdminOperationsPage";
import AdminProductsPage from "@/features/admin-products/pages/AdminProductsPage";
import AdminProductDetailPage from "@/features/admin-products/pages/AdminProductDetailPage";
import AdminCompliancePage from "@/features/admin-compliance/pages/AdminCompliancePage";
import AdminSettingsPage from "@/features/admin-settings/pages/AdminSettingsPage";
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
import AdminStoreApplicationsPage from "@/features/admin-store-applications/pages/AdminStoreApplicationsPage";
import AdminStoreApplicationDetailPage from "@/features/admin-store-applications/pages/AdminStoreApplicationDetailPage";
import HomePage from "@/features/public/pages/HomePage";
import ForStoresPage from "@/features/public/pages/ForStoresPage";
import HowItWorksPage from "@/features/public/pages/HowItWorksPage";
import FeaturesPage from "@/features/public/pages/FeaturesPage";
import ContactPage from "@/features/public/pages/ContactPage";
import RequestDemoPage from "@/features/public/pages/RequestDemoPage";
import SupportPage from "@/features/public/pages/SupportPage";
import ApplyPage from "@/features/store-applications/pages/ApplyPage";
import LegalHubPage from "@/features/public/legal/LegalHubPage";
import TermsPage from "@/features/public/legal/TermsPage";
import PrivacyPage from "@/features/public/legal/PrivacyPage";
import MerchantAgreementPage from "@/features/public/legal/MerchantAgreementPage";
import AcceptableUsePage from "@/features/public/legal/AcceptableUsePage";
import CookiesPage from "@/features/public/legal/CookiesPage";
import {
  AdminShell,
  AppIndexRedirect,
  LegacyInventoryRedirect,
  LegacyOrderRedirect,
  LegacyProductRedirect,
  PublicShell,
  StoreShell,
  StoreRedirect,
} from "./route-components";

export const appRoutes: RouteObject[] = [
  // F2.21.1: public website routes share the PublicShell layout. They
  // render identically for unauthenticated and authenticated visitors
  // per the F2.21 contract — no auth gate, no role/store context.
  {
    element: <PublicShell />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/for-stores", element: <ForStoresPage /> },
      { path: "/how-it-works", element: <HowItWorksPage /> },
      { path: "/features", element: <FeaturesPage /> },
      { path: "/contact", element: <ContactPage /> },
      { path: "/request-demo", element: <RequestDemoPage /> },
      // F2.24.C6: public merchant onboarding wizard. Public, no auth gate.
      { path: "/apply", element: <ApplyPage /> },
      { path: "/support", element: <SupportPage /> },
      { path: "/legal", element: <LegalHubPage /> },
      { path: "/legal/terms", element: <TermsPage /> },
      { path: "/legal/privacy", element: <PrivacyPage /> },
      {
        path: "/legal/merchant-agreement",
        element: <MerchantAgreementPage />,
      },
      { path: "/legal/acceptable-use", element: <AcceptableUsePage /> },
      { path: "/legal/cookies", element: <CookiesPage /> },
    ],
  },
  {
    path: "/login",
    element: <AuthScreen />,
  },
  // F2.25.4: public Supabase auth-link routes. Owners land here from the
  // password setup / recovery email; they are NOT behind ProtectedRoute.
  {
    path: "/auth/callback",
    element: <AuthCallbackPage />,
  },
  {
    path: "/auth/set-password",
    element: <SetPasswordPage />,
  },
  {
    path: "/auth/forgot-password",
    element: <ForgotPasswordPage />,
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
          // F2.24.C7: admin merchant-application review queue + detail.
          // Consumes the C3/C4 admin store-applications endpoints. The
          // public `/apply` intake (C6) is unrelated and lives under
          // PublicShell.
          {
            path: "applications",
            element: <AdminStoreApplicationsPage />,
          },
          {
            path: "applications/:applicationId",
            element: <AdminStoreApplicationDetailPage />,
          },
          // F2.15.7: real users management replaces the placeholder.
          // Same component handles both /app/store/users (store scope)
          // and /app/admin/users (global scope); the page reads
          // `useLocation()` to decide which UX hints to flip.
          { path: "users", element: <UsersPage /> },
          // F2.20.5: real admin products oversight + detail drill-down
          // replace the placeholder. The placeholder component remains
          // defined in route-components.tsx (unused) so the deletion
          // footprint is limited to the router; same convention used
          // in F2.15.7, F2.18.3, F2.18.4, F2.18.5, F2.19.5, F2.19.6.
          // Detail route is new in F2.20.0 — it did not exist as a
          // placeholder pre-F2.20.
          { path: "products", element: <AdminProductsPage /> },
          {
            path: "products/:productId",
            element: <AdminProductDetailPage />,
          },
          // F2.18.5: real admin global inventory and orders read-only
          // pages replace the placeholders. Placeholder components
          // remain defined in route-components.tsx (unused) so the
          // deletion footprint is limited to the router; same
          // convention used in F2.15.7, F2.18.3 and F2.18.4.
          { path: "inventory", element: <AdminInventoryPage /> },
          { path: "orders", element: <AdminOrdersPage /> },
          { path: "earnings", element: <AdminEarningsPage /> },
          // F2.18.4: real admin global audit feed replaces the
          // placeholder. The placeholder component remains defined in
          // route-components.tsx (unused) so the deletion footprint is
          // limited to the router; same convention used in F2.15.7
          // and F2.18.3.
          { path: "audit", element: <AdminAuditPage /> },
          // F2.20.6: real admin compliance oversight replaces the
          // placeholder. The placeholder component remains defined
          // in route-components.tsx (unused) so the deletion
          // footprint is limited to the router; same convention
          // used in F2.15.7, F2.18.3, F2.18.4, F2.18.5, F2.19.5,
          // F2.19.6, F2.20.5.
          { path: "compliance", element: <AdminCompliancePage /> },
          // F2.19.6: real admin operations alerts page replaces the
          // placeholder. The placeholder component remains defined in
          // route-components.tsx (unused) so the deletion footprint is
          // limited to the router; same convention used in F2.15.7,
          // F2.18.3, F2.18.4, F2.18.5, and F2.19.5.
          { path: "operations", element: <AdminOperationsPage /> },
          // Real admin settings page replaces the placeholder. The
          // placeholder component remains defined in
          // route-components.tsx (unused) so the deletion footprint
          // is limited to the router; same convention used in
          // F2.15.7, F2.18.3, F2.18.4, F2.18.5, F2.19.5, F2.19.6,
          // F2.20.5 and F2.20.6.
          { path: "settings", element: <AdminSettingsPage /> },
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
              { path: "onboarding", element: <StoreOnboardingPage /> },
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
              { path: "earnings", element: <StoreEarningsPage /> },
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
