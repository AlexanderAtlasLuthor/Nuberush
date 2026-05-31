// F2.24.C6 — wizard form state shape + validation, shared by the steps
// and the orchestrator. UI-only: the backend re-validates and is the
// authority (StoreApplicationSubmitRequest, extra="forbid"). This mirrors
// the backend Field bounds so a known-bad value never round-trips for 422.

import type { StoreApplicationSubmitRequest } from "../types";

export interface ApplicationFormValues {
  business_name: string;
  business_type: string;
  business_phone: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  website_url: string;
  social_url: string;
  location_count: string;
  estimated_weekly_orders: string;
  owner_full_name: string;
  owner_email: string;
  owner_phone: string;
  hours_of_operation: string;
  notes: string;
  terms_accepted: boolean;
}

export type StringFieldKey = Exclude<
  keyof ApplicationFormValues,
  "terms_accepted"
>;

export type ApplicationFormErrors = Partial<
  Record<keyof ApplicationFormValues, string>
>;

export type FieldChange = (key: StringFieldKey, value: string) => void;

export const INITIAL_VALUES: ApplicationFormValues = {
  business_name: "",
  business_type: "",
  business_phone: "",
  address_line_1: "",
  address_line_2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "US",
  website_url: "",
  social_url: "",
  location_count: "1",
  estimated_weekly_orders: "0",
  owner_full_name: "",
  owner_email: "",
  owner_phone: "",
  hours_of_operation: "",
  notes: "",
  terms_accepted: false,
};

// UX-only email check. The backend uses EmailStr; this just stops an
// obviously-malformed value from round-tripping for a 422.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function requireNonBlank(
  errors: ApplicationFormErrors,
  values: ApplicationFormValues,
  key: StringFieldKey,
  label: string,
): void {
  if (values[key].trim().length === 0) {
    errors[key] = `${label} is required.`;
  }
}

/**
 * Validate the fields belonging to one wizard step. `step` is the
 * 1-based content step: 1 = business, 2 = owner, 3 = operations,
 * 4 = review/terms. Returns a (possibly empty) error map.
 */
export function validateStep(
  step: number,
  values: ApplicationFormValues,
): ApplicationFormErrors {
  const errors: ApplicationFormErrors = {};

  if (step === 1) {
    requireNonBlank(errors, values, "business_name", "Business name");
    requireNonBlank(errors, values, "business_type", "Business type");
    requireNonBlank(errors, values, "business_phone", "Business phone");
    requireNonBlank(errors, values, "address_line_1", "Street address");
    requireNonBlank(errors, values, "city", "City");
    requireNonBlank(errors, values, "state", "State");
    requireNonBlank(errors, values, "postal_code", "Postal code");

    const country = values.country.trim();
    if (country.length === 0) {
      errors.country = "Country is required.";
    } else if (country.length !== 2) {
      errors.country = "Use the 2-letter country code (e.g. US).";
    }

    const locations = Number(values.location_count);
    if (
      values.location_count.trim() === "" ||
      !Number.isFinite(locations) ||
      !Number.isInteger(locations) ||
      locations < 1
    ) {
      errors.location_count = "Enter a number of locations (1 or more).";
    }

    const weekly = Number(values.estimated_weekly_orders);
    if (
      values.estimated_weekly_orders.trim() === "" ||
      !Number.isFinite(weekly) ||
      !Number.isInteger(weekly) ||
      weekly < 0
    ) {
      errors.estimated_weekly_orders =
        "Enter an estimate (0 or more).";
    }
  }

  if (step === 2) {
    requireNonBlank(errors, values, "owner_full_name", "Full name");
    if (values.owner_email.trim().length === 0) {
      errors.owner_email = "Email is required.";
    } else if (!EMAIL_RE.test(values.owner_email.trim())) {
      errors.owner_email = "Enter a valid email address.";
    }
    requireNonBlank(errors, values, "owner_phone", "Phone");
  }

  if (step === 3) {
    requireNonBlank(
      errors,
      values,
      "hours_of_operation",
      "Hours of operation",
    );
  }

  if (step === 4) {
    if (!values.terms_accepted) {
      errors.terms_accepted = "You must confirm before submitting.";
    }
  }

  return errors;
}

/**
 * Build the exact backend payload from the form values. Only the allowed
 * fields are ever placed on the object; optional empties are omitted.
 * No forbidden/server-owned field can appear by construction.
 */
export function toSubmitPayload(
  values: ApplicationFormValues,
): StoreApplicationSubmitRequest {
  const payload: StoreApplicationSubmitRequest = {
    business_name: values.business_name.trim(),
    business_type: values.business_type.trim(),
    owner_full_name: values.owner_full_name.trim(),
    owner_email: values.owner_email.trim(),
    owner_phone: values.owner_phone.trim(),
    business_phone: values.business_phone.trim(),
    address_line_1: values.address_line_1.trim(),
    city: values.city.trim(),
    state: values.state.trim(),
    postal_code: values.postal_code.trim(),
    country: values.country.trim().toUpperCase(),
    location_count: Number(values.location_count),
    estimated_weekly_orders: Number(values.estimated_weekly_orders),
    hours_of_operation: values.hours_of_operation.trim(),
    terms_accepted: values.terms_accepted,
  };

  const addressLine2 = values.address_line_2.trim();
  if (addressLine2) payload.address_line_2 = addressLine2;
  const websiteUrl = values.website_url.trim();
  if (websiteUrl) payload.website_url = websiteUrl;
  const socialUrl = values.social_url.trim();
  if (socialUrl) payload.social_url = socialUrl;
  const notes = values.notes.trim();
  if (notes) payload.notes = notes;

  return payload;
}
