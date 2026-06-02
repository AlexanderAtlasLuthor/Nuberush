// F2.24.X5: role-picker data extracted from UserRoleSelect so the
// component file exports only components (Fast Refresh requirement).
//
// Visible options are intentionally narrowed to the four roles a backend
// caller can EVER successfully create: owner | manager | staff | driver.
// `admin` is omitted on purpose (the backend USER_CREATION_MATRIX rejects
// creating `admin` for every caller in MVP) — this is not frontend
// authorization, just "no universally invalid targets in the picker".

/**
 * Subset of `UserRole` the create-form picker exposes. Narrower than the
 * wire enum because `admin` is filtered out (see above).
 */
export type CreatableUserRole = "owner" | "manager" | "staff" | "driver";

interface RoleOption {
  readonly value: CreatableUserRole;
  readonly label: string;
}

export const VISIBLE_USER_ROLE_OPTIONS: ReadonlyArray<RoleOption> = [
  { value: "owner", label: "Owner" },
  { value: "manager", label: "Manager" },
  { value: "staff", label: "Staff" },
  { value: "driver", label: "Driver" },
];
