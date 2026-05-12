// F2.9.3: CreateUserForm.
//
// Standalone form for POST /auth/users. Renders the field set the
// backend `CreateUserRequest` accepts (full_name, email, password,
// role, store_id, phone) and submits via `useCreateUserMutation`.
//
// Validation policy:
//   The form only does UX-level validation — non-empty trimmed
//   full_name, basic email shape, password length >= 8, role picked.
//   Everything else (role/store rules, email uniqueness, real password
//   policy, who-can-create-whom) is a BACKEND concern. The backend
//   returns 400 / 403 / 404 / 409 / 422 with a `detail` string and the
//   form surfaces that detail verbatim via `getApiErrorMessage`.
//
// Hard rules baked in (per F2.9.3 brief):
//   - No `useAuth`, no `currentUser.role` inspection.
//   - No client-side role/permission/creation matrix. The role picker
//     omits `admin` only because backend rejects admin-create for every
//     caller (see UserRoleSelect file header) — that's a "no
//     universally invalid targets" rule, not a per-role gate.
//   - No `store_id` requirement keyed off the caller's role.
//   - No options hidden based on the caller's role.
//   - Empty optional fields (store_id, phone) are OMITTED from the body
//     rather than sent as `null`. Both encodings are semantically
//     equivalent for the backend Pydantic schema (default=None) but
//     omitting matches the existing project convention in
//     features/products/components/ProductFormModal.tsx.
//
// Success / error UX:
//   - On `mutation.isSuccess`: show an inline success panel naming the
//     created user (full_name + email + role) and call optional
//     `onCreated(user)`. The form does NOT auto-reset; the parent
//     (e.g. CreateUserModal) is responsible for unmounting/closing,
//     which mount/unmount-resets the form on next open.
//   - On `mutation.isError`: render the backend `detail` string under
//     the form. Status-specific copy is intentionally avoided so the
//     server's message comes through unchanged (e.g. 403 "You cannot
//     create users in another store.", 409 "Email already registered.",
//     422 first-issue.msg).

import { useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { useCreateUserMutation } from "../hooks";
import type { CreateUserRequest, UserRead, UserRole } from "../types";
import { UserRoleSelect } from "./UserRoleSelect";

// Basic email shape check. The backend uses `EmailStr` (Pydantic
// EmailValidator) which is the authoritative gate; this is a UX-only
// guard so the user gets faster feedback than a 422 round-trip.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Mirrors the backend `Field(min_length=8, max_length=128)` constraint
// from app/schemas/auth.py::CreateUserRequest. The backend re-validates
// — this is just to spare a 422 round-trip.
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_LENGTH = 128;

export interface CreateUserFormProps {
  /** Called once with the created user when the mutation succeeds. */
  onCreated?: (user: UserRead) => void;
  /** Optional cancel handler. When omitted the cancel button is hidden. */
  onCancel?: () => void;
  className?: string;
}

export function CreateUserForm({
  onCreated,
  onCancel,
  className,
}: CreateUserFormProps) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole | "">("");
  const [storeId, setStoreId] = useState("");
  const [phone, setPhone] = useState("");

  const mutation = useCreateUserMutation();

  // Hand the created user up to the parent exactly once per success.
  // Using an effect rather than the per-call `onSuccess` keeps this
  // resilient to future callers that drive the mutation via mutateAsync.
  useEffect(() => {
    if (mutation.isSuccess && mutation.data) {
      onCreated?.(mutation.data);
    }
    // We intentionally exclude `onCreated` from the dep list to avoid
    // double-firing when a parent re-creates the callback on every
    // render. The mutation transition (idle → success) is the trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mutation.isSuccess, mutation.data]);

  const trimmedName = fullName.trim();
  const trimmedEmail = email.trim();
  const trimmedStoreId = storeId.trim();
  const trimmedPhone = phone.trim();

  const isEmailValid = EMAIL_PATTERN.test(trimmedEmail);
  const isPasswordValid =
    password.length >= PASSWORD_MIN_LENGTH &&
    password.length <= PASSWORD_MAX_LENGTH;
  const isFormValid =
    trimmedName.length > 0 &&
    isEmailValid &&
    isPasswordValid &&
    role !== "";

  const canSubmit = isFormValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // Narrow `role` to `UserRole` for the payload builder. canSubmit
    // already implies role !== "", but TS doesn't propagate narrowing
    // through derived const booleans, so do the narrowing explicitly.
    if (role === "") return;
    if (!canSubmit) return;

    const body: CreateUserRequest = {
      full_name: trimmedName,
      email: trimmedEmail,
      password,
      role,
    };
    if (trimmedStoreId.length > 0) {
      body.store_id = trimmedStoreId;
    }
    if (trimmedPhone.length > 0) {
      body.phone = trimmedPhone;
    }

    mutation.mutate({ body });
  };

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className={className}
      data-testid="create-user-form"
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="create-user-full-name">
            Full name <span className="text-destructive">*</span>
          </Label>
          <Input
            id="create-user-full-name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            disabled={mutation.isPending}
            required
            maxLength={150}
            autoComplete="name"
            data-testid="create-user-full-name"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="create-user-email">
            Email <span className="text-destructive">*</span>
          </Label>
          <Input
            id="create-user-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={mutation.isPending}
            required
            autoComplete="email"
            data-testid="create-user-email"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="create-user-password">
            Password <span className="text-destructive">*</span>
          </Label>
          <Input
            id="create-user-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={mutation.isPending}
            required
            minLength={PASSWORD_MIN_LENGTH}
            maxLength={PASSWORD_MAX_LENGTH}
            autoComplete="new-password"
            data-testid="create-user-password"
          />
          <p className="text-xs text-muted-foreground">
            Minimum {PASSWORD_MIN_LENGTH} characters. The backend
            re-validates the password policy.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="create-user-role">
            Role <span className="text-destructive">*</span>
          </Label>
          <UserRoleSelect
            id="create-user-role"
            value={role}
            onValueChange={(v) => setRole(v)}
            disabled={mutation.isPending}
            data-testid="create-user-role-trigger"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="create-user-store-id">Store ID</Label>
          <Input
            id="create-user-store-id"
            value={storeId}
            onChange={(e) => setStoreId(e.target.value)}
            disabled={mutation.isPending}
            placeholder="Optional UUID"
            data-testid="create-user-store-id"
          />
          <p className="text-xs text-muted-foreground">
            Optional. The backend decides whether a store ID is required
            for this role and caller; it returns an error if the value
            does not match the rule.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="create-user-phone">Phone</Label>
          <Input
            id="create-user-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            disabled={mutation.isPending}
            maxLength={30}
            autoComplete="tel"
            data-testid="create-user-phone"
          />
        </div>

        {mutation.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="create-user-error"
          >
            {getApiErrorMessage(mutation.error)}
          </p>
        ) : null}

        {mutation.isSuccess && mutation.data ? (
          <p
            role="status"
            aria-live="polite"
            className="text-sm text-emerald-700 dark:text-emerald-400"
            data-testid="create-user-success"
          >
            Created {mutation.data.full_name} ({mutation.data.email}) as{" "}
            {mutation.data.role}.
          </p>
        ) : null}

        <p className="text-xs text-muted-foreground">
          The backend enforces who may create which roles, store
          assignment and email uniqueness. Errors below this form come
          from the server unchanged.
        </p>
      </div>

      <div className="mt-6 flex items-center justify-end gap-2">
        {onCancel ? (
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={mutation.isPending}
            data-testid="create-user-cancel"
          >
            Cancel
          </Button>
        ) : null}
        <Button
          type="submit"
          disabled={!canSubmit}
          data-testid="create-user-submit"
        >
          {mutation.isPending ? "Creating…" : "Create user"}
        </Button>
      </div>
    </form>
  );
}
