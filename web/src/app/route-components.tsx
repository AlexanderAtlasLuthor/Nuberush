import { useEffect } from "react";
import { Navigate, Outlet, useParams } from "react-router-dom";
import { AdminLayout } from "@/layouts/AdminLayout";
import { PublicLayout } from "@/layouts/PublicLayout";
import { StoreLayout } from "@/layouts/StoreLayout";
import { useAuth } from "@/auth";

// F2.21.1: PublicShell wraps every public-website route in PublicLayout.
// Renders identically for unauthenticated and authenticated visitors
// per F2.21 contract §4 — no auth check, no role/store context, no
// admin/store navigation.
export function PublicShell() {
  return (
    <PublicLayout>
      <Outlet />
    </PublicLayout>
  );
}

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
