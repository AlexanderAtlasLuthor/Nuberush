// F2.8.3: products list table.
//
// Read-only projection of the wire `Product` shape. No client-side
// derivations — `is_active` and `allowed_for_sale` are wire-truthy
// booleans rendered through their dedicated badge / inline badge,
// `compliance_status` is the wire enum rendered through
// `ProductComplianceBadge`. Row navigation is handled with a plain
// `Link` — no programmatic navigate, no row-level click handler that
// could fight the keyboard / right-click flow.

import { Link } from "react-router-dom";
import { Eye } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { Product } from "../types";

import { ProductComplianceBadge } from "./ProductComplianceBadge";
import { ProductStatusBadge } from "./ProductStatusBadge";

interface ProductsTableProps {
  products: Product[];
}

export function ProductsTable({ products }: ProductsTableProps) {
  return (
    <div className="rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Brand</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Compliance</TableHead>
            <TableHead>Allowed for sale</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-20 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {products.map((product) => (
            <TableRow key={product.id} data-testid="products-row">
              <TableCell className="font-medium">{product.name}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {product.brand ?? "—"}
              </TableCell>
              <TableCell className="text-sm">{product.category}</TableCell>
              <TableCell>
                <ProductComplianceBadge status={product.compliance_status} />
              </TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={cn(
                    "uppercase tracking-wide",
                    product.allowed_for_sale
                      ? "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100"
                      : "border-transparent bg-neutral-200 text-neutral-700 hover:bg-neutral-200",
                  )}
                  data-testid={
                    product.allowed_for_sale
                      ? "product-allowed-yes"
                      : "product-allowed-no"
                  }
                >
                  {product.allowed_for_sale ? "Allowed" : "Not allowed"}
                </Badge>
              </TableCell>
              <TableCell>
                <ProductStatusBadge isActive={product.is_active} />
              </TableCell>
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  asChild
                  data-testid="products-row-view"
                >
                  <Link to={`/app/store/products/${product.id}`}>
                    <Eye className="mr-1 h-4 w-4" aria-hidden="true" />
                    View
                  </Link>
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
