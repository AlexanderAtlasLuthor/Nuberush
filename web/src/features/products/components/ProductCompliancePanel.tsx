// F2.8.4: compliance panel for the product detail page.
//
// Pure projection of `Product` fields already fetched by the parent
// page. NO independent data fetch — the parent's `useProductQuery`
// covers loading / error / empty for the underlying record, so this
// panel only renders when the product is in hand.
//
// Hard rules in force:
//   - No business logic. The wire enum / boolean / strings / ISO
//     timestamps are rendered verbatim.
//   - No combination across fields ("banned + allowed_for_sale" etc.)
//     — that rule lives server-side.
//   - No timestamp parsing / pretty-printing. F2.8.x stays raw-ISO;
//     formatting belongs to a future cross-cutting subphase.

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Product } from "../types";

import { ProductComplianceBadge } from "./ProductComplianceBadge";

const EM_DASH = "—";

function nullableText(value: string | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? EM_DASH
    : value;
}

interface ProductCompliancePanelProps {
  product: Product;
}

export function ProductCompliancePanel({
  product,
}: ProductCompliancePanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Compliance</CardTitle>
        <CardDescription>
          Server-managed compliance state. Edits go through the dedicated
          compliance endpoint and produce an audit row (ships in a later
          subphase).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
          <ComplianceField label="Compliance status">
            <ProductComplianceBadge status={product.compliance_status} />
          </ComplianceField>

          <ComplianceField label="Allowed for sale">
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
                  ? "product-compliance-allowed-yes"
                  : "product-compliance-allowed-no"
              }
            >
              {product.allowed_for_sale ? "Allowed" : "Not allowed"}
            </Badge>
          </ComplianceField>

          <ComplianceField label="Hold reason" wide>
            <span
              className="whitespace-pre-wrap"
              data-testid="product-compliance-hold-reason"
            >
              {nullableText(product.hold_reason)}
            </span>
          </ComplianceField>

          <ComplianceField label="Jurisdiction">
            <span data-testid="product-compliance-jurisdiction">
              {product.jurisdiction}
            </span>
          </ComplianceField>

          <ComplianceField label="Last compliance check">
            <span
              className="whitespace-nowrap"
              data-testid="product-compliance-last-check"
            >
              {nullableText(product.last_compliance_check)}
            </span>
          </ComplianceField>
        </div>
      </CardContent>
    </Card>
  );
}

function ComplianceField({
  label,
  wide,
  children,
}: {
  label: string;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={wide ? "md:col-span-2" : undefined}>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-1">{children}</div>
    </div>
  );
}
