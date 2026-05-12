// F2.8.6: Product Variant create / edit modal.
//
// Two modes share a single component because the writable field set is
// identical between `VariantCreateRequest` and `VariantUpdateRequest`
// (modulo `product_id`, which is immutable on edit and injected by the
// hook on create).
//
// Hard rules (per F2.8.6 brief §4):
//   - Money fields (`price`, `cost`) stay STRINGS through the entire
//     flow. We never `Number()`, `parseFloat()`, or otherwise coerce
//     them — the backend takes Decimal-as-string and we preserve
//     precision verbatim. Empty cost → undefined (CREATE) / null (EDIT).
//   - No stock logic, no sellability logic, no inventory side-effect
//     reasoning. The variant lives independently of inventory rows.
//   - Create-mode hook (useCreateVariantMutation) injects `product_id`
//     into the body internally; the form NEVER asks for it.
//
// Mirrors the F2.8.5 modal pattern (conditional mount by parent,
// useEffect auto-close, inline error, no manual refetch).

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
  useCreateVariantMutation,
  useUpdateVariantMutation,
} from "../hooks";
import type {
  ProductVariant,
  VariantCreateRequest,
  VariantUpdateRequest,
} from "../types";

type ProductVariantFormModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
} & (
  | { mode: "create"; productId: string; variant?: undefined }
  | { mode: "edit"; productId: string; variant: ProductVariant }
);

export function ProductVariantFormModal(
  props: ProductVariantFormModalProps,
) {
  return props.mode === "create" ? (
    <CreateVariantModal
      open={props.open}
      onOpenChange={props.onOpenChange}
      productId={props.productId}
    />
  ) : (
    <EditVariantModal
      open={props.open}
      onOpenChange={props.onOpenChange}
      variant={props.variant}
    />
  );
}

// --------------------------------------------------------------------- //
// Create
// --------------------------------------------------------------------- //

function CreateVariantModal({
  open,
  onOpenChange,
  productId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  productId: string;
}) {
  const [sku, setSku] = useState("");
  const [barcode, setBarcode] = useState("");
  const [flavor, setFlavor] = useState("");
  const [sizeLabel, setSizeLabel] = useState("");
  const [unitCount, setUnitCount] = useState("");
  const [puffCount, setPuffCount] = useState("");
  const [thcStrength, setThcStrength] = useState("");
  const [price, setPrice] = useState("");
  const [cost, setCost] = useState("");
  const [isActive, setIsActive] = useState(true);

  const mutation = useCreateVariantMutation();

  useEffect(() => {
    if (mutation.isSuccess && open) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, open, onOpenChange]);

  const trimmedSku = sku.trim();
  const trimmedPrice = price.trim();
  const isValid = trimmedSku.length > 0 && trimmedPrice.length > 0;
  const canSubmit = isValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    // Body matches the hook's expected `Omit<VariantCreateRequest,
    // "product_id">` shape; the hook injects product_id internally.
    const body: Omit<VariantCreateRequest, "product_id"> = {
      sku: trimmedSku,
      price: trimmedPrice,
      ...optionalString("barcode", barcode),
      ...optionalString("flavor", flavor),
      ...optionalString("size_label", sizeLabel),
      ...optionalString("thc_strength", thcStrength),
      ...optionalInt("unit_count", unitCount),
      ...optionalInt("puff_count", puffCount),
      ...optionalString("cost", cost),
      is_active: isActive,
    };

    mutation.mutate({ productId, body });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Add variant</DialogTitle>
            <DialogDescription>
              Create a new SKU-level variant for this product. Money values
              are sent as strings to preserve Decimal precision; the
              backend validates the numeric format.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <VariantFormFields
              sku={sku}
              onSkuChange={setSku}
              barcode={barcode}
              onBarcodeChange={setBarcode}
              flavor={flavor}
              onFlavorChange={setFlavor}
              sizeLabel={sizeLabel}
              onSizeLabelChange={setSizeLabel}
              unitCount={unitCount}
              onUnitCountChange={setUnitCount}
              puffCount={puffCount}
              onPuffCountChange={setPuffCount}
              thcStrength={thcStrength}
              onThcStrengthChange={setThcStrength}
              price={price}
              onPriceChange={setPrice}
              cost={cost}
              onCostChange={setCost}
              isActive={isActive}
              onIsActiveChange={setIsActive}
              priceRequired
              disabled={mutation.isPending}
            />

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="variant-create-error"
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
              data-testid="variant-create-submit"
            >
              {mutation.isPending ? "Adding…" : "Add variant"}
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

function EditVariantModal({
  open,
  onOpenChange,
  variant,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  variant: ProductVariant;
}) {
  const [sku, setSku] = useState(variant.sku);
  const [barcode, setBarcode] = useState(variant.barcode ?? "");
  const [flavor, setFlavor] = useState(variant.flavor ?? "");
  const [sizeLabel, setSizeLabel] = useState(variant.size_label ?? "");
  const [unitCount, setUnitCount] = useState(
    variant.unit_count !== null ? String(variant.unit_count) : "",
  );
  const [puffCount, setPuffCount] = useState(
    variant.puff_count !== null ? String(variant.puff_count) : "",
  );
  const [thcStrength, setThcStrength] = useState(variant.thc_strength ?? "");
  // Money: keep the wire string verbatim. Never coerce to a number;
  // never re-format. The user edits the same string the backend sent.
  const [price, setPrice] = useState(variant.price);
  const [cost, setCost] = useState(variant.cost ?? "");
  const [isActive, setIsActive] = useState(variant.is_active);

  const mutation = useUpdateVariantMutation();

  useEffect(() => {
    if (mutation.isSuccess && open) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, open, onOpenChange]);

  const trimmedSku = sku.trim();
  const trimmedPrice = price.trim();
  // SKU and price stay required UX-side because the backend will reject
  // empty values; price empties to "" would fail the Pydantic Decimal
  // parse before reaching the column constraint.
  const isValid = trimmedSku.length > 0 && trimmedPrice.length > 0;
  const canSubmit = isValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    // EDIT body uses null for empty optional fields so the operator can
    // explicitly clear a value. The CREATE body used `undefined` because
    // the backend applies defaults on absent optional fields.
    const trimmedCost = cost.trim();

    const body: VariantUpdateRequest = {
      sku: trimmedSku,
      barcode: nullableString(barcode),
      flavor: nullableString(flavor),
      size_label: nullableString(sizeLabel),
      thc_strength: nullableString(thcStrength),
      unit_count: nullableInt(unitCount),
      puff_count: nullableInt(puffCount),
      price: trimmedPrice,
      cost: trimmedCost.length > 0 ? trimmedCost : null,
      is_active: isActive,
    };

    mutation.mutate({ variantId: variant.id, body });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Edit variant</DialogTitle>
            <DialogDescription>
              Edit fields of variant{" "}
              <span className="font-mono text-xs">{variant.sku}</span>. The
              parent product is immutable. Money values are sent as strings
              to preserve Decimal precision.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <VariantFormFields
              sku={sku}
              onSkuChange={setSku}
              barcode={barcode}
              onBarcodeChange={setBarcode}
              flavor={flavor}
              onFlavorChange={setFlavor}
              sizeLabel={sizeLabel}
              onSizeLabelChange={setSizeLabel}
              unitCount={unitCount}
              onUnitCountChange={setUnitCount}
              puffCount={puffCount}
              onPuffCountChange={setPuffCount}
              thcStrength={thcStrength}
              onThcStrengthChange={setThcStrength}
              price={price}
              onPriceChange={setPrice}
              cost={cost}
              onCostChange={setCost}
              isActive={isActive}
              onIsActiveChange={setIsActive}
              priceRequired
              disabled={mutation.isPending}
            />

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="variant-edit-error"
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
              data-testid="variant-edit-submit"
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
// Shared field cluster
// --------------------------------------------------------------------- //

interface VariantFormFieldsProps {
  sku: string;
  onSkuChange: (value: string) => void;
  barcode: string;
  onBarcodeChange: (value: string) => void;
  flavor: string;
  onFlavorChange: (value: string) => void;
  sizeLabel: string;
  onSizeLabelChange: (value: string) => void;
  unitCount: string;
  onUnitCountChange: (value: string) => void;
  puffCount: string;
  onPuffCountChange: (value: string) => void;
  thcStrength: string;
  onThcStrengthChange: (value: string) => void;
  price: string;
  onPriceChange: (value: string) => void;
  cost: string;
  onCostChange: (value: string) => void;
  isActive: boolean;
  onIsActiveChange: (value: boolean) => void;
  priceRequired: boolean;
  disabled?: boolean;
}

function VariantFormFields(props: VariantFormFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="variant-sku">
            SKU <span className="text-destructive">*</span>
          </Label>
          <Input
            id="variant-sku"
            value={props.sku}
            onChange={(e) => props.onSkuChange(e.target.value)}
            disabled={props.disabled}
            required
            maxLength={100}
            data-testid="variant-form-sku"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="variant-barcode">Barcode</Label>
          <Input
            id="variant-barcode"
            value={props.barcode}
            onChange={(e) => props.onBarcodeChange(e.target.value)}
            disabled={props.disabled}
            maxLength={100}
            data-testid="variant-form-barcode"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="variant-flavor">Flavor</Label>
          <Input
            id="variant-flavor"
            value={props.flavor}
            onChange={(e) => props.onFlavorChange(e.target.value)}
            disabled={props.disabled}
            maxLength={100}
            data-testid="variant-form-flavor"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="variant-size-label">Size label</Label>
          <Input
            id="variant-size-label"
            value={props.sizeLabel}
            onChange={(e) => props.onSizeLabelChange(e.target.value)}
            disabled={props.disabled}
            maxLength={50}
            data-testid="variant-form-size-label"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="variant-unit-count">Unit count</Label>
          <Input
            id="variant-unit-count"
            type="number"
            inputMode="numeric"
            min={1}
            value={props.unitCount}
            onChange={(e) => props.onUnitCountChange(e.target.value)}
            disabled={props.disabled}
            data-testid="variant-form-unit-count"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="variant-puff-count">Puff count</Label>
          <Input
            id="variant-puff-count"
            type="number"
            inputMode="numeric"
            min={1}
            value={props.puffCount}
            onChange={(e) => props.onPuffCountChange(e.target.value)}
            disabled={props.disabled}
            data-testid="variant-form-puff-count"
          />
        </div>

        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="variant-thc">THC strength</Label>
          <Input
            id="variant-thc"
            value={props.thcStrength}
            onChange={(e) => props.onThcStrengthChange(e.target.value)}
            disabled={props.disabled}
            maxLength={50}
            data-testid="variant-form-thc"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="variant-price">
            Price{" "}
            {props.priceRequired ? (
              <span className="text-destructive">*</span>
            ) : null}
          </Label>
          <Input
            id="variant-price"
            inputMode="decimal"
            value={props.price}
            onChange={(e) => props.onPriceChange(e.target.value)}
            disabled={props.disabled}
            required={props.priceRequired}
            placeholder="0.00"
            data-testid="variant-form-price"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="variant-cost">Cost</Label>
          <Input
            id="variant-cost"
            inputMode="decimal"
            value={props.cost}
            onChange={(e) => props.onCostChange(e.target.value)}
            disabled={props.disabled}
            placeholder="0.00"
            data-testid="variant-form-cost"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="variant-active"
          checked={props.isActive}
          disabled={props.disabled}
          onCheckedChange={(value) => props.onIsActiveChange(value === true)}
          data-testid="variant-form-active-checkbox"
        />
        <Label htmlFor="variant-active" className="text-sm cursor-pointer">
          Active
        </Label>
      </div>
    </>
  );
}

// --------------------------------------------------------------------- //
// Helpers — emit only the keys the operator actually filled in
// --------------------------------------------------------------------- //

function optionalString<K extends string>(
  key: K,
  value: string,
): { [P in K]?: string } {
  const trimmed = value.trim();
  return trimmed.length > 0 ? ({ [key]: trimmed } as { [P in K]?: string }) : ({} as { [P in K]?: string });
}

function optionalInt<K extends string>(
  key: K,
  value: string,
): { [P in K]?: number } {
  const trimmed = value.trim();
  if (trimmed.length === 0) return {} as { [P in K]?: number };
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed)
    ? ({ [key]: parsed } as { [P in K]?: number })
    : ({} as { [P in K]?: number });
}

function nullableString(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function nullableInt(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) return null;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
}
