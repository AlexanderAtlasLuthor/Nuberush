// F2.8.6: Product create / edit modal.
//
// Two modes share a single component because the writable field set is
// almost identical:
//
//   CREATE — fields exposed:  name, brand, category, description,
//                             jurisdiction, compliance_status,
//                             allowed_for_sale.
//   EDIT   — fields exposed:  name, brand, category, description,
//                             jurisdiction, is_active.
//
// Why the asymmetry: the backend `ProductUpdate` schema deliberately
// omits compliance fields — the audit-write invariant requires that
// any compliance change go through `PATCH /products/{id}/compliance`,
// which is owned by `UpdateProductComplianceModal`. We DO NOT surface
// compliance edits here, never silently. `hold_reason` is also not
// exposed on either request shape (it's a server-managed display-only
// field on `ProductRead`); we omit it from the form rather than fake
// support for a field the wire doesn't accept.
//
// Hard rules (per F2.8.6 brief §3):
//   - No compliance derivation. Banned + allowed_for_sale=true is sent
//     verbatim in CREATE; the backend's 422 path is the canonical
//     signal. No client-side auto-flip.
//   - No business logic, no permission gating.
//   - Mirrors the F2.8.5 modal pattern (conditional mount by parent,
//     useEffect auto-close, inline error, no manual refetch).

import { useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import {
  useCreateProductMutation,
  useUpdateProductMutation,
} from "../hooks";
import type {
  Product,
  ProductComplianceStatus,
  ProductCreateRequest,
  ProductUpdateRequest,
} from "../types";

const COMPLIANCE_OPTIONS: ReadonlyArray<{
  value: ProductComplianceStatus;
  label: string;
}> = [
  { value: "allowed", label: "Allowed" },
  { value: "restricted", label: "Restricted" },
  { value: "banned", label: "Banned" },
];

const DEFAULT_JURISDICTION = "FL";

type ProductFormModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
} & (
  | { mode: "create"; product?: undefined }
  | { mode: "edit"; product: Product }
);

export function ProductFormModal(props: ProductFormModalProps) {
  return props.mode === "create" ? (
    <CreateProductModal
      open={props.open}
      onOpenChange={props.onOpenChange}
    />
  ) : (
    <EditProductModal
      open={props.open}
      onOpenChange={props.onOpenChange}
      product={props.product}
    />
  );
}

// --------------------------------------------------------------------- //
// Create
// --------------------------------------------------------------------- //

function CreateProductModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [jurisdiction, setJurisdiction] = useState(DEFAULT_JURISDICTION);
  const [complianceStatus, setComplianceStatus] = useState<
    ProductComplianceStatus
  >("allowed");
  const [allowedForSale, setAllowedForSale] = useState(true);

  const mutation = useCreateProductMutation();

  useEffect(() => {
    if (mutation.isSuccess && open) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, open, onOpenChange]);

  const trimmedName = name.trim();
  const trimmedCategory = category.trim();
  const isValid =
    trimmedName.length > 0 && trimmedCategory.length > 0;
  const canSubmit = isValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    const trimmedBrand = brand.trim();
    const trimmedDescription = description.trim();
    const trimmedJurisdiction = jurisdiction.trim();

    const body: ProductCreateRequest = {
      name: trimmedName,
      category: trimmedCategory,
      // Send the wire-truthy values verbatim. `undefined` for empty
      // optionals so the backend applies its own defaults; never coerce
      // empty strings into `null` for fields the backend types as `str`.
      brand: trimmedBrand.length > 0 ? trimmedBrand : undefined,
      description:
        trimmedDescription.length > 0 ? trimmedDescription : undefined,
      jurisdiction:
        trimmedJurisdiction.length > 0 ? trimmedJurisdiction : undefined,
      compliance_status: complianceStatus,
      allowed_for_sale: allowedForSale,
    };

    mutation.mutate({ body });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Create product</DialogTitle>
            <DialogDescription>
              The backend validates the combination and stores the product;
              the UI does not enforce business rules. Variants are created
              separately from the product detail page.
              {" "}
              If you are not an admin, the product is submitted as a
              pending proposal and a platform admin must approve it before
              it becomes visible to other stores or sellable.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <ProductFormFields
              name={name}
              onNameChange={setName}
              brand={brand}
              onBrandChange={setBrand}
              category={category}
              onCategoryChange={setCategory}
              description={description}
              onDescriptionChange={setDescription}
              jurisdiction={jurisdiction}
              onJurisdictionChange={setJurisdiction}
              disabled={mutation.isPending}
            />

            <div className="space-y-2">
              <Label htmlFor="product-create-compliance">
                Compliance status
              </Label>
              <Select
                value={complianceStatus}
                onValueChange={(value) =>
                  setComplianceStatus(value as ProductComplianceStatus)
                }
                disabled={mutation.isPending}
              >
                <SelectTrigger
                  id="product-create-compliance"
                  data-testid="product-create-compliance-trigger"
                >
                  <SelectValue placeholder="Select a compliance status" />
                </SelectTrigger>
                <SelectContent>
                  {COMPLIANCE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="product-create-allowed"
                checked={allowedForSale}
                disabled={mutation.isPending}
                onCheckedChange={(value) =>
                  setAllowedForSale(value === true)
                }
                data-testid="product-create-allowed-checkbox"
              />
              <Label
                htmlFor="product-create-allowed"
                className="text-sm cursor-pointer"
              >
                Allowed for sale
              </Label>
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="product-create-error"
              >
                {getApiErrorMessage(mutation.error)}
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              data-testid="product-create-submit"
            >
              {mutation.isPending ? "Creating…" : "Create product"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------- //
// Edit
// --------------------------------------------------------------------- //

function EditProductModal({
  open,
  onOpenChange,
  product,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: Product;
}) {
  const [name, setName] = useState(product.name);
  const [brand, setBrand] = useState(product.brand ?? "");
  const [category, setCategory] = useState(product.category);
  const [description, setDescription] = useState(product.description ?? "");
  const [jurisdiction, setJurisdiction] = useState(product.jurisdiction);
  const [isActive, setIsActive] = useState(product.is_active);

  const mutation = useUpdateProductMutation();

  useEffect(() => {
    if (mutation.isSuccess && open) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, open, onOpenChange]);

  const trimmedName = name.trim();
  const trimmedCategory = category.trim();
  const isValid = trimmedName.length > 0 && trimmedCategory.length > 0;
  const canSubmit = isValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    const trimmedBrand = brand.trim();
    const trimmedDescription = description.trim();
    const trimmedJurisdiction = jurisdiction.trim();

    const body: ProductUpdateRequest = {
      name: trimmedName,
      brand: trimmedBrand.length > 0 ? trimmedBrand : null,
      category: trimmedCategory,
      description:
        trimmedDescription.length > 0 ? trimmedDescription : null,
      jurisdiction:
        trimmedJurisdiction.length > 0 ? trimmedJurisdiction : undefined,
      is_active: isActive,
    };

    mutation.mutate({ productId: product.id, body });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Edit product</DialogTitle>
            <DialogDescription>
              Edit the non-compliance fields of{" "}
              <span className="font-medium">{product.name}</span>. Compliance
              changes go through the dedicated Update compliance dialog so
              the audit log fires server-side.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <ProductFormFields
              name={name}
              onNameChange={setName}
              brand={brand}
              onBrandChange={setBrand}
              category={category}
              onCategoryChange={setCategory}
              description={description}
              onDescriptionChange={setDescription}
              jurisdiction={jurisdiction}
              onJurisdictionChange={setJurisdiction}
              disabled={mutation.isPending}
            />

            <div className="flex items-center gap-2">
              <Checkbox
                id="product-edit-active"
                checked={isActive}
                disabled={mutation.isPending}
                onCheckedChange={(value) => setIsActive(value === true)}
                data-testid="product-edit-active-checkbox"
              />
              <Label
                htmlFor="product-edit-active"
                className="text-sm cursor-pointer"
              >
                Active
              </Label>
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="product-edit-error"
              >
                {getApiErrorMessage(mutation.error)}
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              data-testid="product-edit-submit"
            >
              {mutation.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------- //
// Shared text fields (kept here, not extracted to its own file, because
// it's an internal-only piece of these two modals)
// --------------------------------------------------------------------- //

interface ProductFormFieldsProps {
  name: string;
  onNameChange: (value: string) => void;
  brand: string;
  onBrandChange: (value: string) => void;
  category: string;
  onCategoryChange: (value: string) => void;
  description: string;
  onDescriptionChange: (value: string) => void;
  jurisdiction: string;
  onJurisdictionChange: (value: string) => void;
  disabled?: boolean;
}

function ProductFormFields({
  name,
  onNameChange,
  brand,
  onBrandChange,
  category,
  onCategoryChange,
  description,
  onDescriptionChange,
  jurisdiction,
  onJurisdictionChange,
  disabled,
}: ProductFormFieldsProps) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="product-name">
          Name <span className="text-destructive">*</span>
        </Label>
        <Input
          id="product-name"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          disabled={disabled}
          required
          maxLength={200}
          data-testid="product-form-name"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="product-brand">Brand</Label>
        <Input
          id="product-brand"
          value={brand}
          onChange={(e) => onBrandChange(e.target.value)}
          disabled={disabled}
          maxLength={120}
          data-testid="product-form-brand"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="product-category">
          Category <span className="text-destructive">*</span>
        </Label>
        <Input
          id="product-category"
          value={category}
          onChange={(e) => onCategoryChange(e.target.value)}
          disabled={disabled}
          required
          maxLength={100}
          data-testid="product-form-category"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="product-description">Description</Label>
        <Textarea
          id="product-description"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          disabled={disabled}
          rows={3}
          data-testid="product-form-description"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="product-jurisdiction">Jurisdiction</Label>
        <Input
          id="product-jurisdiction"
          value={jurisdiction}
          onChange={(e) => onJurisdictionChange(e.target.value)}
          disabled={disabled}
          maxLength={50}
          data-testid="product-form-jurisdiction"
        />
      </div>
    </>
  );
}
