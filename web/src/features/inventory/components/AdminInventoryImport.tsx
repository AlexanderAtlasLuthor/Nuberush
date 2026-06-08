// F2.27.9: admin entry point for the QuickBooks inventory import.
//
// The platform-admin Inventory page (AdminInventoryPage, /app/admin/
// inventory) is store-agnostic: an admin's `store_id` is null, so the
// store-scoped import button on InventoryPage is unreachable for admins
// and there is no admin store picker. This launcher closes that gap.
//
// Flow: the admin picks a target store from a dropdown of ALL stores,
// then the existing InventoryImportDialog runs against that store. The
// dialog is reused untouched — it already accepts any `storeId` and
// reads `useAuth()` internally to surface the admin-only "Create missing
// products & variants" toggle (F2.27.9).
//
// RBAC stays backend-authoritative: import is require_manager_or_above
// and `create_missing` is admin-only. This component adds no client-side
// permission logic of its own.

import { useState } from "react";
import { Upload } from "lucide-react";

import { useAdminStoresQuery } from "@/features/stores/hooks";
import type { StoreProfile } from "@/features/stores/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { InventoryImportDialog } from "./InventoryImportDialog";

// One page of stores feeds the dropdown. 100 is the backend max for
// GET /stores; past that the list truncates. If the platform grows
// beyond 100 stores, switch to a searchable combobox (Command +
// Popover) or server-side `q` search rather than bumping this blindly.
const STORE_FETCH_LIMIT = 100;

function storeLabel(store: StoreProfile): string {
  return `${store.name} (${store.code})`;
}

export function AdminInventoryImport() {
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const storesQuery = useAdminStoresQuery({ limit: STORE_FETCH_LIMIT });
  const stores = storesQuery.data?.items ?? [];

  const isLoading = storesQuery.isLoading;
  const isError = storesQuery.isError;
  const isEmpty = !isLoading && !isError && stores.length === 0;
  const selectDisabled = isLoading || isError || isEmpty;

  const placeholder = isLoading
    ? "Loading stores…"
    : isError
      ? "Stores unavailable"
      : isEmpty
        ? "No stores"
        : "Select a store";

  return (
    <div
      className="flex flex-col items-start gap-2 sm:flex-row sm:items-end"
      data-testid="admin-inventory-import"
    >
      <div className="space-y-2">
        <Label htmlFor="admin-inventory-import-store">Import into store</Label>
        <Select
          // Controlled with "" (no store ID is ever empty) so the
          // component never flips uncontrolled→controlled; "" shows the
          // placeholder.
          value={selectedStoreId ?? ""}
          disabled={selectDisabled}
          onValueChange={(value) => setSelectedStoreId(value)}
        >
          <SelectTrigger
            id="admin-inventory-import-store"
            className="w-64"
            data-testid="admin-inventory-import-store-select"
          >
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {stores.map((store) => (
              <SelectItem key={store.id} value={store.id}>
                {storeLabel(store)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={selectedStoreId === null}
        onClick={() => setImportOpen(true)}
        data-testid="admin-inventory-import-open"
      >
        <Upload className="mr-2 h-4 w-4" />
        Import inventory
      </Button>

      {/*
        The dialog mounts once a store is chosen and is driven by
        `importOpen` (mirrors InventoryPage). `storeId` flows straight
        through, so the same dialog imports into whichever store the
        admin selected — and shows the admin-only create-missing toggle.
      */}
      {selectedStoreId !== null ? (
        <InventoryImportDialog
          open={importOpen}
          onOpenChange={setImportOpen}
          storeId={selectedStoreId}
        />
      ) : null}
    </div>
  );
}
