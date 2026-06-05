// F2.20.5: presentational table for the admin products oversight page.
//
// Pure presentational — the parent supplies the rows; this component
// only renders. No fetching, no client-side product/compliance
// derivation, no permission logic. Reuses the canonical
// ProductComplianceBadge so the compliance state styling is
// identical to the store-side products surface.
//
// Read-only here: there are no inline mutation actions. Each row
// links to /app/admin/products/{product.id} where the existing
// detail surface (ProductActionsBar, ProductCompliancePanel, etc.)
// handles compliance review and other admin actions.
//
// Columns deliberately match the wire contract: the F2.20.1 backend
// `Product` shape carries id, name, brand, category, compliance_status,
// allowed_for_sale, is_active, last_compliance_check, updated_at.

import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { ProductApprovalBadge } from "@/features/products/components/ProductApprovalBadge";
import { ProductComplianceBadge } from "@/features/products/components/ProductComplianceBadge";
import { ProductThumbnail } from "@/features/products/components/ProductThumbnail";
import type { Product } from "../types";

const EM_DASH = "—";

export interface AdminProductsTableProps {
  products: Product[];
}

function formatTimestamp(iso: string | null): string {
  if (iso === null) return EM_DASH;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

export function AdminProductsTable({ products }: AdminProductsTableProps) {
  return (
    <div
      className="rounded-md border border-border"
      data-testid="admin-products-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">Image</TableHead>
            <TableHead>Product</TableHead>
            <TableHead>Brand</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Approval</TableHead>
            <TableHead>Compliance</TableHead>
            <TableHead>Allowed for sale</TableHead>
            <TableHead>Active</TableHead>
            <TableHead>Last compliance check</TableHead>
            <TableHead>Updated at</TableHead>
            <TableHead className="text-right">Drill-down</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {products.map((product) => (
            <TableRow
              key={product.id}
              data-testid="admin-products-row"
              data-product-id={product.id}
            >
              <TableCell data-testid="admin-products-row-thumbnail">
                <ProductThumbnail
                  primaryImage={product.primary_image}
                  productName={product.name}
                  size="sm"
                />
              </TableCell>
              <TableCell data-testid="admin-products-row-name">
                <span className="font-medium">{product.name}</span>
              </TableCell>
              <TableCell data-testid="admin-products-row-brand">
                {product.brand ?? EM_DASH}
              </TableCell>
              <TableCell data-testid="admin-products-row-category">
                {product.category}
              </TableCell>
              <TableCell data-testid="admin-products-row-approval">
                <ProductApprovalBadge status={product.approval_status} />
              </TableCell>
              <TableCell data-testid="admin-products-row-compliance">
                <ProductComplianceBadge
                  status={product.compliance_status}
                />
              </TableCell>
              <TableCell data-testid="admin-products-row-allowed-for-sale">
                <Badge
                  variant={product.allowed_for_sale ? "default" : "outline"}
                >
                  {product.allowed_for_sale ? "Yes" : "No"}
                </Badge>
              </TableCell>
              <TableCell data-testid="admin-products-row-is-active">
                <Badge variant={product.is_active ? "default" : "outline"}>
                  {product.is_active ? "Yes" : "No"}
                </Badge>
              </TableCell>
              <TableCell data-testid="admin-products-row-last-compliance-check">
                {formatTimestamp(product.last_compliance_check)}
              </TableCell>
              <TableCell data-testid="admin-products-row-updated-at">
                {formatTimestamp(product.updated_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link
                  to={`/app/admin/products/${encodeURIComponent(product.id)}`}
                  className="text-sm underline-offset-2 hover:underline"
                  data-testid="admin-products-row-drilldown"
                >
                  Open
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
