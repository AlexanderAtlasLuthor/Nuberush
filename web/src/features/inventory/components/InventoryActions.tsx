// F2.6.2 subfase 4: row-level actions for the inventory table.
//
// Both menu entries now open their respective dialog. The component
// owns one boolean per modal — flat flags rather than a union type
// because the two dialogs are independent UI surfaces, not a state
// machine. Mutations live inside each modal (F2.6.2 subfases 2 + 4);
// this file only routes "open this dialog now" intent.
//
// Hard rules in force:
//   - No mutations are called from this file.
//   - No fetch, no Zustand, no business logic.

import { useState } from "react";
import { MoreHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { ReceiveStockModal } from "./ReceiveStockModal";
import { AdjustStockModal } from "./AdjustStockModal";
import { DamageStockModal } from "./DamageStockModal";
import { UpdateThresholdModal } from "./UpdateThresholdModal";
import { UpdateStatusModal } from "./UpdateStatusModal";
import { InventoryItemLogsPanel } from "./InventoryItemLogsPanel";
import type { InventoryItem } from "../types";

interface InventoryActionsProps {
  item: InventoryItem;
}

export function InventoryActions({ item }: InventoryActionsProps) {
  const [openReceive, setOpenReceive] = useState(false);
  const [openAdjust, setOpenAdjust] = useState(false);
  const [openDamage, setOpenDamage] = useState(false);
  const [openThreshold, setOpenThreshold] = useState(false);
  const [openStatus, setOpenStatus] = useState(false);
  const [openLogs, setOpenLogs] = useState(false);

  const handleReceive = () => {
    setOpenReceive(true);
  };

  const handleAdjust = () => {
    setOpenAdjust(true);
  };

  const handleDamage = () => {
    setOpenDamage(true);
  };

  const handleThreshold = () => {
    setOpenThreshold(true);
  };

  const handleStatus = () => {
    setOpenStatus(true);
  };

  const handleLogs = () => {
    setOpenLogs(true);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            aria-label={`Open actions for ${item.variant.product.name}`}
            data-testid="inventory-row-actions-trigger"
          >
            <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuLabel>Stock movements</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={handleReceive}
            data-testid="inventory-action-receive"
          >
            Receive stock
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={handleAdjust}
            data-testid="inventory-action-adjust"
          >
            Adjust stock
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={handleDamage}
            data-testid="inventory-action-damage"
          >
            Record damage
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={handleThreshold}
            data-testid="inventory-action-threshold"
          >
            Set threshold
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={handleStatus}
            data-testid="inventory-action-status"
          >
            Update status
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={handleLogs}
            data-testid="inventory-action-logs"
          >
            View logs
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ReceiveStockModal
        open={openReceive}
        onOpenChange={setOpenReceive}
        item={item}
      />

      <AdjustStockModal
        open={openAdjust}
        onOpenChange={setOpenAdjust}
        item={item}
      />

      <DamageStockModal
        open={openDamage}
        onOpenChange={setOpenDamage}
        item={item}
      />

      <UpdateThresholdModal
        open={openThreshold}
        onOpenChange={setOpenThreshold}
        item={item}
      />

      <UpdateStatusModal
        open={openStatus}
        onOpenChange={setOpenStatus}
        item={item}
      />

      <Dialog open={openLogs} onOpenChange={setOpenLogs}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Item logs</DialogTitle>
            <DialogDescription>
              Append-only audit trail for{" "}
              <span className="font-medium">
                {item.variant.product.name}
              </span>{" "}
              <span className="font-mono text-xs">({item.variant.sku})</span>.
            </DialogDescription>
          </DialogHeader>
          {openLogs ? (
            <InventoryItemLogsPanel inventoryItemId={item.id} />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
