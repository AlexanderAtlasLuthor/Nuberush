// F2.14.5: presentational form for Store Settings.
//
// Edits ONLY the two fields F2.14 made writable (`name`, `timezone`)
// and surfaces the rest of the StoreProfile as read-only metadata. The
// form is permission-blind, network-blind and toast-blind on purpose:
//
//   - Permission decisions live on the backend
//     (`require_owner_or_admin`); the page that mounts this form is
//     responsible for hiding it for unsupported roles if it wants UX
//     gating, but the backend is the authority.
//   - Network calls are owned by the page (which wires
//     `useUpdateStoreMutation` from F2.14.4 into `onSubmit` /
//     `isPending` / `errorMessage`). This file never imports a query
//     or a fetch helper.
//   - Toasts are owned by the page. The form just renders inline
//     errors and the `Saving…` state.
//
// Validation here mirrors the backend `StoreUpdate` rules
// (`Field(min_length=1, max_length=...)` + trim-on-validate). The
// backend re-validates and is authoritative; this is a UX guard so a
// known-bad value never round-trips for a 422.
//
// Hard rules baked in (per F2.14.5 brief):
//   - No `useStoreQuery`, no `useUpdateStoreMutation`, no fetch.
//   - No toast, no redirect.
//   - Payload only includes fields the user actually changed.
//   - Read-only / out-of-scope fields (`code`, `is_active`, `id`,
//     `created_at`, `updated_at`, address-style extras) are NEVER
//     placed on the payload, because `StoreUpdate.extra="forbid"`
//     server-side would 422 anything else and the contract is
//     identical here.

import { useEffect, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type { StoreProfile, StoreUpdateRequest } from "../types";

// Mirrors backend `StoreUpdate` Field bounds in
// app/schemas/stores.py (max_length=150 / max_length=50). Kept here as
// constants so the validation messages and the maxLength attributes
// share one source of truth.
const NAME_MAX_LENGTH = 150;
const TIMEZONE_MAX_LENGTH = 50;

export interface StoreSettingsFormProps {
  /** Server-fresh profile to seed inputs and metadata from. */
  store: StoreProfile;
  /** When true: Save shows "Saving…" and is disabled. */
  isPending?: boolean;
  /** Pre-formatted error string from the page (e.g. via `getApiErrorMessage`). */
  errorMessage?: string | null;
  /**
   * Called with the diff payload (only fields that actually changed).
   * The page is responsible for the network call; this form does not
   * touch the API directly.
   */
  onSubmit: (payload: StoreUpdateRequest) => void | Promise<void>;
  /**
   * Optional cancel handler. When provided, a Cancel button is rendered
   * and clicking it resets the inputs to the server values, clears
   * local validation errors, and invokes the callback.
   */
  onCancel?: () => void;
  className?: string;
}

interface LocalErrors {
  name?: string;
  timezone?: string;
}

function validate(name: string, timezone: string): LocalErrors {
  const errors: LocalErrors = {};
  const trimmedName = name.trim();
  const trimmedTimezone = timezone.trim();

  if (trimmedName.length === 0) {
    errors.name = "Store name is required.";
  } else if (trimmedName.length > NAME_MAX_LENGTH) {
    errors.name = `Store name must be ${NAME_MAX_LENGTH} characters or fewer.`;
  }

  if (trimmedTimezone.length === 0) {
    errors.timezone = "Timezone is required.";
  } else if (trimmedTimezone.length > TIMEZONE_MAX_LENGTH) {
    errors.timezone = `Timezone must be ${TIMEZONE_MAX_LENGTH} characters or fewer.`;
  }

  return errors;
}

export function StoreSettingsForm({
  store,
  isPending = false,
  errorMessage = null,
  onSubmit,
  onCancel,
  className,
}: StoreSettingsFormProps) {
  const [nameInput, setNameInput] = useState(store.name);
  const [timezoneInput, setTimezoneInput] = useState(store.timezone);
  const [localErrors, setLocalErrors] = useState<LocalErrors>({});

  // If the parent receives a fresh profile (e.g. after a successful
  // mutation refetch), re-seed the inputs so the dirty signal goes
  // back to clean. The local-errors slot resets too — anything that
  // was wrong against the OLD server state is no longer relevant.
  useEffect(() => {
    setNameInput(store.name);
    setTimezoneInput(store.timezone);
    setLocalErrors({});
  }, [store.id, store.name, store.timezone]);

  const trimmedName = nameInput.trim();
  const trimmedTimezone = timezoneInput.trim();

  const isNameDirty = trimmedName !== store.name;
  const isTimezoneDirty = trimmedTimezone !== store.timezone;
  const isDirty = isNameDirty || isTimezoneDirty;

  const liveErrors = validate(nameInput, timezoneInput);
  const hasLiveErrors =
    liveErrors.name !== undefined || liveErrors.timezone !== undefined;

  const canSubmit = isDirty && !hasLiveErrors && !isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const errors = validate(nameInput, timezoneInput);
    if (errors.name !== undefined || errors.timezone !== undefined) {
      setLocalErrors(errors);
      return;
    }

    if (!isDirty) {
      // Nothing to send. Mirrors how the backend treats an empty
      // PATCH (no-op) but avoids the round-trip entirely.
      return;
    }

    if (isPending) return;

    const payload: StoreUpdateRequest = {};
    if (isNameDirty) {
      payload.name = trimmedName;
    }
    if (isTimezoneDirty) {
      payload.timezone = trimmedTimezone;
    }

    setLocalErrors({});
    void onSubmit(payload);
  };

  const handleCancel = () => {
    setNameInput(store.name);
    setTimezoneInput(store.timezone);
    setLocalErrors({});
    onCancel?.();
  };

  const showNameError = localErrors.name ?? null;
  const showTimezoneError = localErrors.timezone ?? null;

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className={className}
      data-testid="store-settings-form"
    >
      <div className="space-y-6">
        {/* ---------------------------------------------------------- */}
        {/* Store profile (editable)                                   */}
        {/* ---------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Store profile</CardTitle>
            <CardDescription>
              Update the basic profile information for this store.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="store-settings-name">
                Store name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="store-settings-name"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                disabled={isPending}
                required
                maxLength={NAME_MAX_LENGTH}
                autoComplete="organization"
                data-testid="store-settings-name"
              />
              {showNameError !== null ? (
                <p
                  role="alert"
                  className="text-sm text-destructive"
                  data-testid="store-settings-name-error"
                >
                  {showNameError}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="store-settings-timezone">
                Operational timezone{" "}
                <span className="text-destructive">*</span>
              </Label>
              <Input
                id="store-settings-timezone"
                value={timezoneInput}
                onChange={(e) => setTimezoneInput(e.target.value)}
                disabled={isPending}
                required
                maxLength={TIMEZONE_MAX_LENGTH}
                placeholder="America/New_York"
                data-testid="store-settings-timezone"
              />
              {showTimezoneError !== null ? (
                <p
                  role="alert"
                  className="text-sm text-destructive"
                  data-testid="store-settings-timezone-error"
                >
                  {showTimezoneError}
                </p>
              ) : null}
            </div>
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------- */}
        {/* Store metadata (read-only)                                 */}
        {/* ---------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Store metadata</CardTitle>
            <CardDescription>
              Read-only identifiers and lifecycle timestamps. Edits to
              these fields are not allowed from Store Settings.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1" data-testid="store-settings-meta-id">
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Store ID
                </dt>
                <dd className="font-mono text-sm">{store.id}</dd>
              </div>
              <div
                className="space-y-1"
                data-testid="store-settings-meta-code"
              >
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Store code
                </dt>
                <dd className="font-mono text-sm">{store.code}</dd>
              </div>
              <div
                className="space-y-1"
                data-testid="store-settings-meta-status"
              >
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Status
                </dt>
                <dd className="text-sm">
                  {store.is_active ? (
                    <Badge
                      variant="secondary"
                      data-testid="store-settings-status-active"
                    >
                      Active
                    </Badge>
                  ) : (
                    <Badge
                      variant="destructive"
                      data-testid="store-settings-status-inactive"
                    >
                      Inactive
                    </Badge>
                  )}
                </dd>
              </div>
              <div
                className="space-y-1"
                data-testid="store-settings-meta-created-at"
              >
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Created at
                </dt>
                <dd className="font-mono text-sm">{store.created_at}</dd>
              </div>
              <div
                className="space-y-1"
                data-testid="store-settings-meta-updated-at"
              >
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Updated at
                </dt>
                <dd className="font-mono text-sm">{store.updated_at}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------- */}
        {/* External error (formatted by the page)                     */}
        {/* ---------------------------------------------------------- */}
        {errorMessage !== null && errorMessage !== undefined ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="store-settings-error"
          >
            {errorMessage}
          </p>
        ) : null}

        {/* ---------------------------------------------------------- */}
        {/* Actions                                                    */}
        {/* ---------------------------------------------------------- */}
        <div className="flex items-center justify-end gap-2">
          {onCancel !== undefined ? (
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={isPending}
              data-testid="store-settings-cancel"
            >
              Cancel
            </Button>
          ) : null}
          <Button
            type="submit"
            disabled={!canSubmit}
            data-testid="store-settings-submit"
          >
            {isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </form>
  );
}
