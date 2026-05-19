// F2.15.7: real users-management page (store + admin scopes).
//
// Mounted at TWO routes:
//   /app/store/users   →  scoped to the caller's store via useStoreContext.
//                         Listing, filters, and lifecycle actions all run
//                         against the caller's own store_id.
//   /app/admin/users   →  global admin scope. Filters expose store_id and
//                         the row actions menu surfaces admin-only items
//                         (assign store).
//
// One component, two scopes — the difference is decided by URL pathname
// via `useLocation`. The backend remains the authoritative gate: a
// non-admin who lands on /app/admin/users still gets 403 from
// `/auth/users` because the service-level matrix rejects them. The
// pathname check here is a UX hint, never authority.
//
// Architecture rules in force here (mirroring features/products and
// features/orders):
//   - No fetch, no mutations called directly. Hooks do the talking.
//   - useState only for filter state and modal-open booleans.
//   - No useAuth / role inspection. Backend matrices in
//     `app/core/permissions.py` are the single source of truth and
//     surface 401 / 403 / 422 / 404 for the UI to render.
//   - No fake users, no fake stores, no client-side authorization.

import { useState } from "react";
import { useLocation } from "react-router-dom";
import { Plus } from "lucide-react";

import { useStoreContext } from "@/auth";
import { Button } from "@/components/ui/button";

import { CreateUserModal } from "../components/CreateUserModal";
import { EditUserModal } from "../components/EditUserModal";
import { DeactivateUserDialog } from "../components/DeactivateUserDialog";
import { ChangeUserRoleModal } from "../components/ChangeUserRoleModal";
import { AssignUserStoreModal } from "../components/AssignUserStoreModal";
import { UserActionsMenu } from "../components/UserActionsMenu";
import { UsersFilters } from "../components/UsersFilters";
import { UsersTable } from "../components/UsersTable";
import { useUsersQuery } from "../hooks";
import type { UserListFilters, UserRead } from "../types";

const DEFAULT_LIMIT = 25;
const ADMIN_PATH_PREFIX = "/app/admin";

type ActiveModal = "edit" | "lifecycle" | "role" | "store" | null;

interface PageHeaderProps {
  title: string;
  description: string;
  onCreate: () => void;
}

function PageHeader({ title, description, onCreate }: PageHeaderProps) {
  return (
    <header className="flex items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <Button
        size="sm"
        onClick={onCreate}
        data-testid="users-create-button"
      >
        <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
        Create user
      </Button>
    </header>
  );
}

export default function UsersPage() {
  const location = useLocation();
  const { currentStoreId } = useStoreContext();

  // Detect the admin scope from the URL. The backend remains the
  // gate; this only flips UX hints (store filter visibility, admin
  // actions in the row menu, copy).
  const isAdminScope = location.pathname.startsWith(ADMIN_PATH_PREFIX);

  const [filters, setFilters] = useState<UserListFilters>({
    limit: DEFAULT_LIMIT,
    offset: 0,
  });
  const [openCreate, setOpenCreate] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserRead | null>(null);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);

  // Compose filters with the scope rule:
  //   store route  → force store_id = currentStoreId; ignore any
  //                  store_id the user typed (the store filter is
  //                  hidden, but defense-in-depth: the backend would
  //                  also reject cross-store filters with 403).
  //   admin route  → pass filters verbatim, including any store_id
  //                  the admin typed.
  // currentStoreId can be null (admin user, or unauthenticated). In
  // that case the effective store filter is undefined and the backend
  // applies its own scope rules from the JWT.
  const effectiveFilters: UserListFilters = isAdminScope
    ? filters
    : {
        ...filters,
        store_id: currentStoreId ?? undefined,
      };

  const query = useUsersQuery(effectiveFilters);

  const openModal = (modal: ActiveModal, user: UserRead) => {
    setSelectedUser(user);
    setActiveModal(modal);
  };

  const closeModal = () => {
    setActiveModal(null);
    // Keep `selectedUser` until the next open so success effects in
    // the closing modal can still reference the row that fired them.
  };

  const title = "Users";
  const description = isAdminScope
    ? "Manage users across the NubeRush platform."
    : "Manage team members who can operate this store.";

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl">
      <PageHeader
        title={title}
        description={description}
        onCreate={() => setOpenCreate(true)}
      />

      <UsersFilters
        filters={filters}
        onChange={setFilters}
        showStoreFilter={isAdminScope}
        disabled={query.isLoading}
      />

      <UsersTable
        users={query.data?.items ?? []}
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        onRetry={() => query.refetch()}
        emptyTitle="No users found"
        emptyDescription={
          isAdminScope
            ? "Try adjusting filters or create a new user."
            : "No users match the current filters for this store."
        }
        actions={(user) => (
          <UserActionsMenu
            user={user}
            onEdit={(u) => openModal("edit", u)}
            onDeactivateReactivate={(u) => openModal("lifecycle", u)}
            onChangeRole={(u) => openModal("role", u)}
            onAssignStore={(u) => openModal("store", u)}
            showAdminActions={isAdminScope}
          />
        )}
      />

      {openCreate ? (
        <CreateUserModal
          open={openCreate}
          onOpenChange={setOpenCreate}
          onCreated={() => {
            // Invalidations are handled by useCreateUserMutation? No —
            // F2.9.2 contract is "no invalidation". Trigger an explicit
            // refetch so the new row shows up in the list immediately.
            query.refetch();
          }}
        />
      ) : null}

      {activeModal === "edit" ? (
        <EditUserModal
          user={selectedUser}
          open={true}
          onOpenChange={(open) => (open ? null : closeModal())}
        />
      ) : null}

      {activeModal === "lifecycle" ? (
        <DeactivateUserDialog
          user={selectedUser}
          open={true}
          onOpenChange={(open) => (open ? null : closeModal())}
        />
      ) : null}

      {activeModal === "role" ? (
        <ChangeUserRoleModal
          user={selectedUser}
          open={true}
          onOpenChange={(open) => (open ? null : closeModal())}
        />
      ) : null}

      {activeModal === "store" ? (
        <AssignUserStoreModal
          user={selectedUser}
          open={true}
          onOpenChange={(open) => (open ? null : closeModal())}
        />
      ) : null}
    </div>
  );
}
