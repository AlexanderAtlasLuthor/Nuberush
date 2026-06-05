// F2.26.4.C: human-readable display labels for inventory wire enums.
//
// Presentation only. These maps turn the raw snake_case enum tokens the
// backend sends (InventoryStatus, ComplianceStatus) into operator-facing
// copy for Store surfaces. The underlying wire values are NEVER altered —
// filters, payloads, and queries keep sending/receiving the raw tokens.
// Unknown values fall back to the raw token so a future backend addition
// renders verbatim rather than blank.

import type { ComplianceStatus, InventoryStatus } from "./types";

const INVENTORY_STATUS_LABEL: Record<InventoryStatus, string> = {
  available: "Available",
  reserved: "Reserved",
  sold: "Sold",
  flagged: "Flagged",
  quarantined: "Quarantined",
};

const COMPLIANCE_STATUS_LABEL: Record<ComplianceStatus, string> = {
  allowed: "Allowed",
  restricted: "Restricted",
  banned: "Banned",
};

export function inventoryStatusLabel(status: InventoryStatus): string {
  return INVENTORY_STATUS_LABEL[status] ?? status;
}

export function complianceStatusLabel(status: string): string {
  return (
    COMPLIANCE_STATUS_LABEL[status as ComplianceStatus] ?? status
  );
}
