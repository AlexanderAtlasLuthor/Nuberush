// F2.27.10: presentational form for the writable Admin Settings cluster.
//
// Edits ONLY the four backend-writable platform fields (`platform_name`,
// `support_email`, `default_locale`, `default_timezone`) and is otherwise
// permission-blind, network-blind and toast-blind — exactly like
// StoreSettingsForm, but with NO store coupling:
//
//   - No `store_id`, no `useStoreContext`, no `StoreProfile`, no tenancy.
//   - Network calls are owned by the page (which wires
//     `useUpdateAdminSettingsMutation` into `onSubmit` / `isPending` /
//     `errorMessage`). This file never imports a query, a fetch helper, or
//     the api layer.
//   - The payload includes only fields the user actually changed.
//
// Validation mirrors the backend `AdminSettingsUpdate` rules (trim,
// min/max length, email format). The backend re-validates and is the
// authority; this is a UX guard so a known-bad value never round-trips
// for a 422.

import { useEffect, useState, type FormEvent } from "react";

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

import type {
  AdminEditableSettings,
  AdminSettingsUpdateRequest,
} from "../types";

// Mirrors backend `AdminSettingsUpdate` Field bounds.
const PLATFORM_NAME_MAX_LENGTH = 150;
const SUPPORT_EMAIL_MAX_LENGTH = 255;
const LOCALE_MIN_LENGTH = 2;
const LOCALE_MAX_LENGTH = 10;
const TIMEZONE_MAX_LENGTH = 50;

// Lightweight email shape check — the backend (`EmailStr`) is authoritative.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface AdminSettingsFormProps {
  /** Server-fresh editable settings to seed the inputs from. */
  editable: AdminEditableSettings;
  /** When true: Save shows "Saving…" and is disabled. */
  isPending?: boolean;
  /** Pre-formatted error string from the page (e.g. via `getApiErrorMessage`). */
  errorMessage?: string | null;
  /**
   * Called with the diff payload (only fields that actually changed). The
   * page owns the network call; this form never touches the API directly.
   */
  onSubmit: (payload: AdminSettingsUpdateRequest) => void | Promise<void>;
  /** Optional cancel handler; resets inputs to server values when clicked. */
  onCancel?: () => void;
  className?: string;
}

interface LocalErrors {
  platform_name?: string;
  support_email?: string;
  default_locale?: string;
  default_timezone?: string;
}

function validate(
  platformName: string,
  supportEmail: string,
  defaultLocale: string,
  defaultTimezone: string,
): LocalErrors {
  const errors: LocalErrors = {};

  const name = platformName.trim();
  if (name.length === 0) {
    errors.platform_name = "Platform name is required.";
  } else if (name.length > PLATFORM_NAME_MAX_LENGTH) {
    errors.platform_name = `Platform name must be ${PLATFORM_NAME_MAX_LENGTH} characters or fewer.`;
  }

  const email = supportEmail.trim();
  if (email.length > 0) {
    if (email.length > SUPPORT_EMAIL_MAX_LENGTH) {
      errors.support_email = `Support email must be ${SUPPORT_EMAIL_MAX_LENGTH} characters or fewer.`;
    } else if (!EMAIL_RE.test(email)) {
      errors.support_email = "Enter a valid email address.";
    }
  }

  const locale = defaultLocale.trim();
  if (locale.length < LOCALE_MIN_LENGTH) {
    errors.default_locale = `Locale must be at least ${LOCALE_MIN_LENGTH} characters.`;
  } else if (locale.length > LOCALE_MAX_LENGTH) {
    errors.default_locale = `Locale must be ${LOCALE_MAX_LENGTH} characters or fewer.`;
  }

  const tz = defaultTimezone.trim();
  if (tz.length === 0) {
    errors.default_timezone = "Default timezone is required.";
  } else if (tz.length > TIMEZONE_MAX_LENGTH) {
    errors.default_timezone = `Timezone must be ${TIMEZONE_MAX_LENGTH} characters or fewer.`;
  }

  return errors;
}

export function AdminSettingsForm({
  editable,
  isPending = false,
  errorMessage = null,
  onSubmit,
  onCancel,
  className,
}: AdminSettingsFormProps) {
  const seedEmail = editable.support_email ?? "";
  const [nameInput, setNameInput] = useState(editable.platform_name);
  const [emailInput, setEmailInput] = useState(seedEmail);
  const [localeInput, setLocaleInput] = useState(editable.default_locale);
  const [timezoneInput, setTimezoneInput] = useState(
    editable.default_timezone,
  );
  const [localErrors, setLocalErrors] = useState<LocalErrors>({});

  // Re-seed when the parent receives a fresh snapshot (e.g. after a save
  // refetch) so the dirty signal returns to clean.
  useEffect(() => {
    setNameInput(editable.platform_name);
    setEmailInput(editable.support_email ?? "");
    setLocaleInput(editable.default_locale);
    setTimezoneInput(editable.default_timezone);
    setLocalErrors({});
  }, [
    editable.platform_name,
    editable.support_email,
    editable.default_locale,
    editable.default_timezone,
  ]);

  const trimmedName = nameInput.trim();
  const trimmedEmail = emailInput.trim();
  const trimmedLocale = localeInput.trim();
  const trimmedTimezone = timezoneInput.trim();

  // Current server value normalized for comparison (null → "").
  const serverEmail = editable.support_email ?? "";

  const isNameDirty = trimmedName !== editable.platform_name;
  const isEmailDirty = trimmedEmail !== serverEmail;
  const isLocaleDirty = trimmedLocale !== editable.default_locale;
  const isTimezoneDirty = trimmedTimezone !== editable.default_timezone;
  const isDirty =
    isNameDirty || isEmailDirty || isLocaleDirty || isTimezoneDirty;

  const liveErrors = validate(
    nameInput,
    emailInput,
    localeInput,
    timezoneInput,
  );
  const hasLiveErrors = Object.keys(liveErrors).length > 0;

  const canSubmit = isDirty && !hasLiveErrors && !isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const errors = validate(nameInput, emailInput, localeInput, timezoneInput);
    if (Object.keys(errors).length > 0) {
      setLocalErrors(errors);
      return;
    }
    if (!isDirty || isPending) {
      return;
    }

    const payload: AdminSettingsUpdateRequest = {};
    if (isNameDirty) {
      payload.platform_name = trimmedName;
    }
    if (isEmailDirty) {
      // Empty string clears the field; backend normalizes blank → null.
      payload.support_email = trimmedEmail;
    }
    if (isLocaleDirty) {
      payload.default_locale = trimmedLocale;
    }
    if (isTimezoneDirty) {
      payload.default_timezone = trimmedTimezone;
    }

    setLocalErrors({});
    void onSubmit(payload);
  };

  const handleCancel = () => {
    setNameInput(editable.platform_name);
    setEmailInput(editable.support_email ?? "");
    setLocaleInput(editable.default_locale);
    setTimezoneInput(editable.default_timezone);
    setLocalErrors({});
    onCancel?.();
  };

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className={className}
      data-testid="admin-settings-form"
    >
      <Card data-testid="settings-editable">
        <CardHeader>
          <CardTitle className="text-base">Editable platform settings</CardTitle>
          <CardDescription>
            These values are persisted and apply platform-wide. Other sections
            on this page are read-only.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="admin-settings-platform-name">
              Platform name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="admin-settings-platform-name"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              disabled={isPending}
              required
              maxLength={PLATFORM_NAME_MAX_LENGTH}
              data-testid="admin-settings-platform-name"
            />
            {localErrors.platform_name !== undefined ? (
              <p
                role="alert"
                className="text-sm text-destructive"
                data-testid="admin-settings-platform-name-error"
              >
                {localErrors.platform_name}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="admin-settings-support-email">Support email</Label>
            <Input
              id="admin-settings-support-email"
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              disabled={isPending}
              maxLength={SUPPORT_EMAIL_MAX_LENGTH}
              placeholder="support@example.com"
              data-testid="admin-settings-support-email"
            />
            {localErrors.support_email !== undefined ? (
              <p
                role="alert"
                className="text-sm text-destructive"
                data-testid="admin-settings-support-email-error"
              >
                {localErrors.support_email}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="admin-settings-default-locale">
              Default locale <span className="text-destructive">*</span>
            </Label>
            <Input
              id="admin-settings-default-locale"
              value={localeInput}
              onChange={(e) => setLocaleInput(e.target.value)}
              disabled={isPending}
              required
              maxLength={LOCALE_MAX_LENGTH}
              placeholder="en-US"
              data-testid="admin-settings-default-locale"
            />
            {localErrors.default_locale !== undefined ? (
              <p
                role="alert"
                className="text-sm text-destructive"
                data-testid="admin-settings-default-locale-error"
              >
                {localErrors.default_locale}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="admin-settings-default-timezone">
              Default timezone <span className="text-destructive">*</span>
            </Label>
            <Input
              id="admin-settings-default-timezone"
              value={timezoneInput}
              onChange={(e) => setTimezoneInput(e.target.value)}
              disabled={isPending}
              required
              maxLength={TIMEZONE_MAX_LENGTH}
              placeholder="America/New_York"
              data-testid="admin-settings-default-timezone"
            />
            {localErrors.default_timezone !== undefined ? (
              <p
                role="alert"
                className="text-sm text-destructive"
                data-testid="admin-settings-default-timezone-error"
              >
                {localErrors.default_timezone}
              </p>
            ) : null}
          </div>

          {errorMessage !== null && errorMessage !== undefined ? (
            <p
              role="alert"
              aria-live="polite"
              className="text-sm text-destructive"
              data-testid="admin-settings-form-error"
            >
              {errorMessage}
            </p>
          ) : null}

          <div className="flex items-center justify-end gap-2">
            {onCancel !== undefined ? (
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                disabled={isPending}
                data-testid="admin-settings-cancel"
              >
                Cancel
              </Button>
            ) : null}
            <Button
              type="submit"
              disabled={!canSubmit}
              data-testid="admin-settings-submit"
            >
              {isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </form>
  );
}
