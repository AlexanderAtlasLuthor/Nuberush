"""Pydantic v2 schemas for the Excel inventory import (F2.27.8).

These describe the wire contract for the two import endpoints:

  POST /stores/{store_id}/inventory/import/preview  -> InventoryImportPreviewResponse
  POST /stores/{store_id}/inventory/import/confirm  -> InventoryImportConfirmResponse

Row-level problems are reported as `InventoryImportRowIssue` entries in a
row's `errors` (blocking) or `warnings` (non-blocking) lists. File-level
problems never reach these schemas — the service raises
`InventoryImportValidationError` and the router maps it to an HTTP error.

The numeric diff fields on a preview row are nullable on purpose: a row
with a missing SKU, an unparseable quantity, or no matching variant has
no meaningful on-hand / delta to report.
"""

from uuid import UUID

from pydantic import BaseModel


class InventoryImportRowIssue(BaseModel):
    """A single error or warning attached to a preview row.

    `code` is a stable machine token (e.g. `MISSING_SKU`,
    `VARIANT_NOT_FOUND`); `message` is human-readable.
    """

    code: str
    message: str


# Backwards/forwards-friendly aliases. Errors and warnings share the same
# shape; the distinction is which list a row carries them in.
InventoryImportRowError = InventoryImportRowIssue
InventoryImportRowWarning = InventoryImportRowIssue


class InventoryImportPreviewRow(BaseModel):
    """One analyzed row, ready for the review UI.

    `action` is one of: `update`, `create_inventory_item`,
    `create_product_and_variant` (admin catalog import), or `skip`.
    A row with any `errors` is always `skip` (it cannot be applied).
    """

    row_number: int
    raw_sku: str | None
    normalized_sku: str
    item_name: str | None
    parsed_quantity: int | None
    matched_variant_id: UUID | None
    matched_product_name: str | None
    current_on_hand: int | None
    quantity_reserved: int | None
    new_on_hand: int | None
    delta: int | None
    action: str
    errors: list[InventoryImportRowIssue] = []
    warnings: list[InventoryImportRowIssue] = []


class InventoryImportSummary(BaseModel):
    """Aggregate counts across all rows. `blocking_error_count > 0`
    means confirm is refused."""

    total_rows: int
    valid_rows: int
    rows_with_errors: int
    rows_with_warnings: int
    to_update: int
    to_create_inventory_item: int
    # F2.27.9: rows that will create a new Product + ProductVariant
    # (admin catalog import). 0 when create-missing mode is off.
    to_create_product_and_variant: int = 0
    to_skip: int
    blocking_error_count: int


class InventoryImportPreviewResponse(BaseModel):
    """Response for the preview endpoint. No DB writes were performed."""

    store_id: UUID
    summary: InventoryImportSummary
    rows: list[InventoryImportPreviewRow]


class InventoryImportConfirmResponse(BaseModel):
    """Outcome of a successful, committed import."""

    store_id: UUID
    updated_count: int
    created_inventory_item_count: int
    # F2.27.9 catalog creation (admin import). Default 0 keeps the
    # F2.27.8 response shape valid for inventory-only imports.
    created_product_count: int = 0
    created_variant_count: int = 0
    skipped_count: int
    unchanged_count: int
    inventory_log_count: int
