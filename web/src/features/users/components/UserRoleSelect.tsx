// F2.9.3: reusable role select for the create-user flow.
//
// Visible options are intentionally narrowed to the four roles a backend
// caller can EVER successfully create:
//
//   owner | manager | staff | driver
//
// `admin` is omitted on purpose. This is NOT frontend authorization —
// the backend `USER_CREATION_MATRIX` rejects creating `admin` for every
// caller (including admin) in MVP, so showing it would only manufacture
// a guaranteed-403 path. The exclusion is "no universally invalid
// targets in the picker", same spirit as not letting users select a
// banned-and-allowed-for-sale combination they cannot save.
//
// What this component deliberately does NOT do:
//   - read `useAuth().user.role` to filter options. Backend gates the
//     fine-grained matrix server-side; the picker stays role-blind.
//   - implement an `allowedRoles` / `canCreate` / `hasPermission` helper.
//   - reach into the form state. It is a controlled primitive: parent
//     owns the value.

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { UserRole } from "../types";
import {
  VISIBLE_USER_ROLE_OPTIONS,
  type CreatableUserRole,
} from "./userRoleOptions";

// Re-export the picker's role type so existing `@/.../UserRoleSelect`
// import sites keep working. Type-only, so it does not re-trigger the
// Fast Refresh component-only rule.
export type { CreatableUserRole };

export interface UserRoleSelectProps {
  /**
   * Currently selected role, or empty string when nothing is picked
   * yet. Passing `""` shows the placeholder.
   */
  value: UserRole | "";
  /**
   * Called with the picked role. The component only ever emits values
   * from `VISIBLE_USER_ROLE_OPTIONS`, never `"admin"`.
   */
  onValueChange: (value: CreatableUserRole) => void;
  disabled?: boolean;
  id?: string;
  /** data-testid for the trigger element. */
  "data-testid"?: string;
}

export function UserRoleSelect({
  value,
  onValueChange,
  disabled,
  id,
  "data-testid": testId = "user-role-select-trigger",
}: UserRoleSelectProps) {
  return (
    <Select
      // Always pass a string to keep Radix in controlled mode end-to-
      // end; switching between undefined and a string would trip
      // React's "uncontrolled to controlled" warning. Empty string is a
      // valid value at the Root level (the constraint against empty
      // values applies to SelectItem, not Root) and surfaces the
      // placeholder because no item matches it.
      value={value}
      onValueChange={(v) => onValueChange(v as CreatableUserRole)}
      disabled={disabled}
    >
      <SelectTrigger id={id} data-testid={testId}>
        <SelectValue placeholder="Select a role" />
      </SelectTrigger>
      <SelectContent>
        {VISIBLE_USER_ROLE_OPTIONS.map((opt) => (
          <SelectItem
            key={opt.value}
            value={opt.value}
            data-testid={`user-role-option-${opt.value}`}
          >
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
