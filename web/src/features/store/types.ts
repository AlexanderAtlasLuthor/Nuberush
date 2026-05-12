// F2.14.4: store-profile wire types.
//
// 1:1 mirror of the FastAPI stores contract (F2.14.1 / F2.14.3). Field
// names and casing match the JSON over the wire exactly (snake_case).
// Do NOT camelCase here; if a UI layer ever needs camelCase, that
// mapping belongs at the page boundary, not in this feature module.
//
// Sources of truth (do not diverge without updating both sides):
//   - backend/app/schemas/stores.py    StoreRead, StoreUpdate
//   - backend/app/db/models.py         Store
//   - backend/app/api/routes/stores.py GET/PATCH /stores/{store_id}
//
// Type-design decisions (mirror the products / users / inventory feature
// modules):
//   - Datetime fields are strings from the wire (ISO-8601).
//   - UUIDs are strings.
//   - Read shape mirrors `StoreRead` exactly — the 7 declared fields,
//     nothing more.
//   - Update shape mirrors `StoreUpdate` exactly — only `name` and
//     `timezone`. The backend uses `extra="forbid"`, so any extra key
//     here would cause a 422 round-trip; we mirror that by NOT listing
//     code / is_active / id / created_at / updated_at as updatable.
//   - No business logic, no derived flags, no permission calculations.
//     Backend is authoritative for every rule.

export interface StoreProfile {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface StoreUpdateRequest {
  name?: string;
  timezone?: string;
}
