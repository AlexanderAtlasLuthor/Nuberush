// F2.27.8: Excel inventory import dialog.
//
// Self-contained dialog driven by the two import mutations from F2.27.8.
// Flow: pick a `.xlsx` → Preview (read-only server diff) → review the
// summary + per-row table → Confirm (transactional apply). Owns only its
// own UI state (selected file, success banner); no fetch, no business
// rules — the backend is the authority for RBAC, tenancy and validation.
//
// Guards baked in:
//   - Confirm is disabled until a valid preview exists AND
//     summary.blocking_error_count === 0.
//   - Re-selecting a file clears the prior preview/confirm result so a
//     stale preview can never be confirmed against a different file.
//   - Confirm re-sends the SAME File; the backend re-validates from
//     scratch (a stale preview cannot smuggle bad rows through).

import { useEffect, useRef, useState, type ChangeEvent } from "react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  useInventoryImportConfirmMutation,
  useInventoryImportPreviewMutation,
} from "../hooks";
import type {
  InventoryImportIssue,
  InventoryImportPreviewResponse,
} from "../types";

interface InventoryImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  storeId: string;
}

const ACTION_LABEL: Record<string, string> = {
  update: "Update",
  create_inventory_item: "Create item",
  skip: "Skip",
};

function IssueList({ issues }: { issues: InventoryImportIssue[] }) {
  if (issues.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <ul className="space-y-0.5">
      {issues.map((issue, index) => (
        <li key={`${issue.code}-${index}`} className="text-xs">
          <span className="font-mono">{issue.code}</span>: {issue.message}
        </li>
      ))}
    </ul>
  );
}

function PreviewSummary({
  preview,
}: {
  preview: InventoryImportPreviewResponse;
}) {
  const s = preview.summary;
  const cells: Array<{ label: string; value: number; testid: string }> = [
    { label: "Total rows", value: s.total_rows, testid: "summary-total-rows" },
    { label: "Valid rows", value: s.valid_rows, testid: "summary-valid-rows" },
    {
      label: "Rows with errors",
      value: s.rows_with_errors,
      testid: "summary-rows-with-errors",
    },
    {
      label: "Rows with warnings",
      value: s.rows_with_warnings,
      testid: "summary-rows-with-warnings",
    },
    { label: "To update", value: s.to_update, testid: "summary-to-update" },
    {
      label: "To create",
      value: s.to_create_inventory_item,
      testid: "summary-to-create",
    },
    { label: "To skip", value: s.to_skip, testid: "summary-to-skip" },
    {
      label: "Blocking errors",
      value: s.blocking_error_count,
      testid: "summary-blocking-errors",
    },
  ];
  return (
    <div
      className="grid grid-cols-2 gap-2 sm:grid-cols-4"
      data-testid="import-summary"
    >
      {cells.map((c) => (
        <div key={c.testid} className="rounded-md border border-border p-2">
          <p className="text-xs text-muted-foreground">{c.label}</p>
          <p className="text-lg font-semibold tabular-nums" data-testid={c.testid}>
            {c.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function PreviewTable({
  preview,
}: {
  preview: InventoryImportPreviewResponse;
}) {
  return (
    <div className="max-h-72 overflow-auto rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Row</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead>Item</TableHead>
            <TableHead className="text-right">Current</TableHead>
            <TableHead className="text-right">New</TableHead>
            <TableHead className="text-right">Δ</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Errors</TableHead>
            <TableHead>Warnings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {preview.rows.map((row) => (
            <TableRow key={row.row_number} data-testid={`import-row-${row.row_number}`}>
              <TableCell className="tabular-nums">{row.row_number}</TableCell>
              <TableCell className="font-mono text-xs">
                {row.normalized_sku || "—"}
              </TableCell>
              <TableCell>{row.item_name ?? "—"}</TableCell>
              <TableCell className="text-right tabular-nums">
                {row.current_on_hand ?? "—"}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {row.new_on_hand ?? "—"}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {row.delta ?? "—"}
              </TableCell>
              <TableCell>
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  {ACTION_LABEL[row.action] ?? row.action}
                </span>
              </TableCell>
              <TableCell className="text-destructive">
                <IssueList issues={row.errors} />
              </TableCell>
              <TableCell className="text-amber-600">
                <IssueList issues={row.warnings} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function InventoryImportDialog({
  open,
  onOpenChange,
  storeId,
}: InventoryImportDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const preview = useInventoryImportPreviewMutation();
  const confirm = useInventoryImportConfirmMutation();
  const { reset: resetPreview } = preview;
  const { reset: resetConfirm } = confirm;

  // Reset everything on every (re)open so a relaunched dialog starts clean.
  useEffect(() => {
    if (open) {
      setFile(null);
      resetPreview();
      resetConfirm();
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [open, resetPreview, resetConfirm]);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    // A new file invalidates any prior preview/confirm result.
    resetPreview();
    resetConfirm();
    if (selected) {
      preview.mutate({ storeId, file: selected });
    }
  };

  const previewData = preview.data;
  const hasBlockingErrors =
    previewData !== undefined &&
    previewData.summary.blocking_error_count > 0;
  const canConfirm =
    file !== null &&
    previewData !== undefined &&
    !hasBlockingErrors &&
    !confirm.isPending &&
    !confirm.isSuccess;

  const handleConfirm = () => {
    if (!canConfirm || file === null) return;
    confirm.mutate({ storeId, file });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Import inventory</DialogTitle>
          <DialogDescription>
            Upload a QuickBooks POS export (<span className="font-mono">.xlsx</span>)
            to update on-hand quantities. Existing product variants are matched
            by SKU; nothing is written until you confirm.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="inventory-import-file">Excel file</Label>
            <input
              ref={fileInputRef}
              id="inventory-import-file"
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={handleFileChange}
              disabled={preview.isPending || confirm.isPending}
              data-testid="inventory-import-file-input"
              className="block w-full text-sm file:mr-4 file:rounded-md file:border file:border-border file:bg-muted file:px-3 file:py-1.5 file:text-sm"
            />
          </div>

          {preview.isPending ? (
            <p className="text-sm text-muted-foreground" data-testid="import-preview-loading">
              Analyzing file…
            </p>
          ) : null}

          {preview.isError ? (
            <p
              role="alert"
              aria-live="polite"
              className="text-sm text-destructive"
              data-testid="import-preview-error"
            >
              {getApiErrorMessage(preview.error)}
            </p>
          ) : null}

          {previewData ? (
            <>
              <PreviewSummary preview={previewData} />
              {hasBlockingErrors ? (
                <p
                  role="alert"
                  className="text-sm text-destructive"
                  data-testid="import-blocking-warning"
                >
                  This file has blocking errors. Fix them and re-upload before
                  importing.
                </p>
              ) : null}
              <PreviewTable preview={previewData} />
            </>
          ) : null}

          {confirm.isError ? (
            <p
              role="alert"
              aria-live="polite"
              className="text-sm text-destructive"
              data-testid="import-confirm-error"
            >
              {getApiErrorMessage(confirm.error)}
            </p>
          ) : null}

          {confirm.isSuccess ? (
            <p
              role="status"
              aria-live="polite"
              className="text-sm text-emerald-600"
              data-testid="import-confirm-success"
            >
              Import complete: {confirm.data.updated_count} updated,{" "}
              {confirm.data.created_inventory_item_count} created,{" "}
              {confirm.data.unchanged_count} unchanged,{" "}
              {confirm.data.skipped_count} skipped (
              {confirm.data.inventory_log_count} log entries).
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={preview.isPending || confirm.isPending}
          >
            {confirm.isSuccess ? "Close" : "Cancel"}
          </Button>
          <Button
            type="button"
            onClick={handleConfirm}
            disabled={!canConfirm}
            data-testid="inventory-import-confirm"
          >
            {confirm.isPending ? "Importing…" : "Confirm import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
