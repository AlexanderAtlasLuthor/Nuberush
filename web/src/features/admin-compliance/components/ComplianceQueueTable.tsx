// F2.20.6: presentational table for the admin compliance queue.
//
// Pure presentational. The parent supplies the rows already filtered
// by `GET /admin/compliance/products`; this component only renders.
// No fetching, no client-side queue generation, no auth/store
// context. The drill-down link sends operators into the F2.20.5
// admin product detail page where the canonical compliance update
// modal lives (`PATCH /products/{product_id}/compliance`).

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

import { ProductComplianceBadge } from "@/features/products/components/ProductComplianceBadge";
import type { Product } from "../types";

const EM_DASH = "—";

export interface ComplianceQueueTableProps {
  products: Product[];
}

function formatTimestamp(iso: string | null): string {
  if (iso === null) return EM_DASH;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

export function ComplianceQueueTable({ products }: ComplianceQueueTableProps) {
  return (
    <div
      className="rounded-md border border-border"
      data-testid="compliance-queue-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead>Compliance status</TableHead>
            <TableHead>Allowed for sale</TableHead>
            <TableHead>Active</TableHead>
            <TableHead>Hold reason</TableHead>
            <TableHead>Last compliance check</TableHead>
            <TableHead>Updated at</TableHead>
            <TableHead className="text-right">Drill-down</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {products.map((product) => (
            <TableRow
              key={product.id}
              data-testid="compliance-queue-row"
              data-product-id={product.id}
            >
              <TableCell data-testid="compliance-queue-row-name">
                <span className="font-medium">{product.name}</span>
              </TableCell>
              <TableCell data-testid="compliance-queue-row-compliance">
                <ProductComplianceBadge
                  status={product.compliance_status}
                />
              </TableCell>
              <TableCell data-testid="compliance-queue-row-allowed-for-sale">
                <Badge
                  variant={product.allowed_for_sale ? "default" : "outline"}
                >
                  {product.allowed_for_sale ? "Yes" : "No"}
                </Badge>
              </TableCell>
              <TableCell data-testid="compliance-queue-row-is-active">
                <Badge variant={product.is_active ? "default" : "outline"}>
                  {product.is_active ? "Yes" : "No"}
                </Badge>
              </TableCell>
              <TableCell
                className="max-w-xs truncate"
                title={product.hold_reason ?? undefined}
                data-testid="compliance-queue-row-hold-reason"
              >
                {product.hold_reason ?? EM_DASH}
              </TableCell>
              <TableCell data-testid="compliance-queue-row-last-compliance-check">
                {formatTimestamp(product.last_compliance_check)}
              </TableCell>
              <TableCell data-testid="compliance-queue-row-updated-at">
                {formatTimestamp(product.updated_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link
                  to={`/app/admin/products/${encodeURIComponent(product.id)}`}
                  className="text-sm underline-offset-2 hover:underline"
                  data-testid="compliance-queue-row-drilldown"
                >
                  Review
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
