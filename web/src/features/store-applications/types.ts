// F2.24.C6 — public store-application intake types.
//
// Mirrors the backend `StoreApplicationSubmitRequest`
// (app/schemas/store_applications.py) EXACTLY. snake_case wire contract,
// no camelCase rewriting — same convention as features/store, features/users.
//
// The request type lists ONLY the fields the public intake accepts. Every
// server-owned / privilege field (`status`, `role`, `store_id`, `user_id`,
// `auth_user_id`, `is_admin`, `reviewed_by_user_id`, `provisioned_*`,
// `public_lookup_token`, timestamps) is intentionally absent: the backend
// schema is `extra="forbid"`, so sending one is a 422, and the type makes
// it impossible to add one by construction.

export interface StoreApplicationSubmitRequest {
  // Required.
  business_name: string;
  business_type: string;
  owner_full_name: string;
  owner_email: string;
  owner_phone: string;
  business_phone: string;
  address_line_1: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  location_count: number;
  estimated_weekly_orders: number;
  hours_of_operation: string;
  terms_accepted: boolean;
  // Optional.
  address_line_2?: string;
  website_url?: string;
  social_url?: string;
  notes?: string;
}

export interface StoreApplicationSubmitResponse {
  id: string;
  status: string;
  message: string;
}
