import { useEffect } from "react";
import { Navigate, Outlet, useParams } from "react-router-dom";
import { AdminLayout } from "@/layouts/AdminLayout";
import { StoreLayout } from "@/layouts/StoreLayout";
import { useAuth } from "@/auth";
import AdminPlaceholderPage from "@/features/admin/pages/AdminPlaceholderPage";

export function AdminShell() {
  return (
    <AdminLayout>
      <Outlet />
    </AdminLayout>
  );
}

export function StoreShell() {
  return (
    <StoreLayout>
      <Outlet />
    </StoreLayout>
  );
}

export function AppIndexRedirect() {
  const { user, logout } = useAuth();
  const isStoreUser =
    user?.role === "owner" ||
    user?.role === "manager" ||
    user?.role === "staff";
  const isUnsupportedRole =
    user !== null && user.role !== "admin" && !isStoreUser;

  useEffect(() => {
    if (isUnsupportedRole) {
      logout();
    }
  }, [isUnsupportedRole, logout]);

  if (user?.role === "admin") {
    return <Navigate to="/app/admin" replace />;
  }

  if (isStoreUser) {
    return <Navigate to="/app/store" replace />;
  }

  return <Navigate to="/login" replace />;
}

export function LegacyProductRedirect() {
  const { productId } = useParams<{ productId: string }>();
  return (
    <Navigate
      to={
        productId
          ? `/app/store/products/${productId}`
          : "/app/store/products"
      }
      replace
    />
  );
}

export function LegacyInventoryRedirect() {
  const { variantId } = useParams<{ variantId: string }>();
  return (
    <Navigate
      to={
        variantId
          ? `/app/store/inventory/${variantId}`
          : "/app/store/inventory"
      }
      replace
    />
  );
}

export function LegacyOrderRedirect() {
  const { orderId } = useParams<{ orderId: string }>();
  return (
    <Navigate
      to={orderId ? `/app/store/orders/${orderId}` : "/app/store/orders"}
      replace
    />
  );
}

export function StoreRedirect({ to }: { to: string }) {
  return <Navigate to={`/app/store/${to}`} replace />;
}

export function AdminDashboardPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Dashboard"
      description="Platform dashboard for NubeRush operators."
      requiredBackend={[
        "Admin dashboard KPI endpoints",
        "Store health summary endpoint",
        "Operations alerts endpoint",
        "Global compliance summary endpoint",
        "Global order/inventory summary endpoints",
      ]}
      nonGoals={[
        "No simulated KPIs",
        "No frontend aggregation across stores",
        "No fake global metrics",
      ]}
      futureCapabilities={[
        "Platform KPIs",
        "Store health",
        "Order volume",
        "Inventory alerts",
        "Compliance risk",
        "Operational incidents",
      ]}
    />
  );
}

export function AdminStoresPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Stores"
      description="Store management surface."
      requiredBackend={[
        "GET /stores",
        "POST /stores",
        "GET /stores/:storeId",
        "PATCH /stores/:storeId",
        "Store status/deactivation endpoint",
        "Store health summary endpoint",
      ]}
      nonGoals={[
        "No fake store list",
        "No hardcoded stores",
        "No frontend-generated store data",
      ]}
      futureCapabilities={[
        "List stores",
        "Create store",
        "View store status",
        "Update store profile",
        "Deactivate/reactivate store",
        "Store operational health",
      ]}
    />
  );
}

export function AdminStoreDetailPlaceholder() {
  const { storeId } = useParams<{ storeId: string }>();

  return (
    <AdminPlaceholderPage
      title="Admin Store Detail"
      description="Platform-level store detail page."
      routeContext={[
        `storeId route parameter: ${storeId ?? "unknown"}`,
        "Route context only; no store data is fetched or fabricated.",
      ]}
      requiredBackend={[
        "GET /stores/:storeId",
        "GET /stores/:storeId/users",
        "GET /stores/:storeId/inventory/summary",
        "GET /stores/:storeId/orders/summary",
        "GET /stores/:storeId/audit",
        "GET /stores/:storeId/compliance",
      ]}
      nonGoals={[
        "No fake store profile",
        "No fake store metrics",
        "No cross-store aggregation in frontend",
      ]}
      futureCapabilities={[
        "Store profile",
        "Store users",
        "Store inventory overview",
        "Store orders overview",
        "Store compliance status",
        "Store audit trail",
        "Store operations issues",
      ]}
    />
  );
}

export function AdminUsersPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Users"
      description="Global user oversight and user administration."
      requiredBackend={[
        "GET /auth/users",
        "PATCH /auth/users/:userId",
        "User deactivate endpoint",
        "User role update endpoint",
        "User store assignment endpoint",
        "Global user audit endpoint",
      ]}
      nonGoals={[
        "No fake user list",
        "No frontend role authority",
        "No frontend permission matrix as security",
      ]}
      futureCapabilities={[
        "List users",
        "Filter by role",
        "Filter by store",
        "Invite users",
        "Update roles",
        "Deactivate users",
        "Audit user activity",
      ]}
    />
  );
}

export function AdminProductsPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Global Products"
      description="Global products oversight across stores/catalog."
      requiredBackend={[
        "Global products query",
        "Cross-store product filters",
        "Global product compliance feed",
        "Product issue queue endpoint",
      ]}
      nonGoals={[
        "No client-side merging of store-scoped product lists",
        "No fake product data",
        "No frontend compliance authority",
      ]}
      futureCapabilities={[
        "Cross-store product search",
        "Product compliance status",
        "Product availability",
        "Restricted/banned/allowed visibility",
        "Product issue queue",
      ]}
    />
  );
}

export function AdminInventoryPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Global Inventory"
      description="Global inventory oversight."
      requiredBackend={[
        "Global inventory query",
        "Cross-store inventory filters",
        "Global low-stock summary endpoint",
        "Global inventory issue feed",
        "Store inventory summary endpoints",
      ]}
      nonGoals={[
        "No frontend aggregation of store inventory",
        "No fake stock totals",
        "No frontend stock truth",
      ]}
      futureCapabilities={[
        "Cross-store inventory search",
        "Low-stock risk overview",
        "Damaged stock visibility",
        "Inventory status monitoring",
        "Store-level inventory drilldown",
      ]}
    />
  );
}

export function AdminOrdersPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Global Orders"
      description="Global orders oversight."
      requiredBackend={[
        "Global orders query",
        "Cross-store order filters",
        "Global order status summary endpoint",
        "Problem orders endpoint",
        "Platform order audit endpoint",
      ]}
      nonGoals={[
        "No frontend aggregation of store orders",
        "No fake order volume",
        "No frontend order transition authority",
      ]}
      futureCapabilities={[
        "Cross-store order search",
        "Order status monitoring",
        "Delayed/problem orders",
        "Return/cancel visibility",
        "Platform-level order audit",
      ]}
    />
  );
}

export function AdminAuditPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Audit"
      description="Global audit feed."
      requiredBackend={[
        "Global audit feed",
        "Cross-resource audit query",
        "Cross-store audit filters",
        "User activity audit endpoint",
        "Compliance audit endpoint",
      ]}
      nonGoals={[
        "No merged audit feed built in frontend",
        "No fake audit events",
        "No client-side audit reconstruction",
      ]}
      futureCapabilities={[
        "Cross-store activity feed",
        "User activity",
        "Product changes",
        "Inventory events",
        "Order events",
        "Compliance events",
        "Filter by store/user/event type",
      ]}
    />
  );
}

export function AdminCompliancePlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Compliance"
      description="Global compliance oversight."
      requiredBackend={[
        "Global compliance feed",
        "Compliance risk queue endpoint",
        "Restricted/banned product query",
        "Store compliance summary endpoint",
        "Product compliance audit endpoint",
        "Admin compliance review endpoints",
      ]}
      nonGoals={[
        "No fake compliance queue",
        "No frontend compliance truth",
        "No client-side enforcement as authority",
      ]}
      futureCapabilities={[
        "Restricted products overview",
        "Banned products overview",
        "Compliance risk queue",
        "Store compliance issues",
        "Product compliance history",
        "Admin review workflow",
      ]}
    />
  );
}

export function AdminOperationsPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Operations"
      description="Platform operations command center."
      requiredBackend={[
        "Operations alerts endpoint",
        "Incident feed endpoint",
        "Store readiness summary endpoint",
        "Delayed orders endpoint",
        "Low-stock alert summary endpoint",
        "Compliance blockers endpoint",
        "System health endpoint",
      ]}
      nonGoals={[
        "No fake incidents",
        "No fake operational alerts",
        "No client-side operations scoring",
      ]}
      futureCapabilities={[
        "Operational incidents",
        "Store readiness",
        "Low-stock alerts",
        "Delayed orders",
        "Compliance blockers",
        "System health signals",
        "Daily operations queue",
      ]}
    />
  );
}

export function AdminSettingsPlaceholder() {
  return (
    <AdminPlaceholderPage
      title="Admin Settings"
      description="Platform settings for NubeRush operators."
      requiredBackend={[
        "Platform settings endpoint",
        "Billing/commission configuration endpoints",
        "Compliance policy endpoints",
        "Notification settings endpoint",
        "Admin preferences endpoint",
      ]}
      nonGoals={[
        "No fake platform settings",
        "No frontend-only policy changes",
        "No billing simulation",
      ]}
      futureCapabilities={[
        "Platform configuration",
        "Billing/commission settings",
        "Compliance policy settings",
        "Operational defaults",
        "Notification settings",
        "Admin user preferences",
      ]}
    />
  );
}
