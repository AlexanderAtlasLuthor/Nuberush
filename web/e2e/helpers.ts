// F2.27.3 — e2e env gate + shared login helper.
//
// The harness is env-gated so it can live in the repo before a staging stack
// exists. Specs ask this module which env vars they need; when any are
// missing, the spec skips with an explicit BLOCKED reason. When env IS
// present, specs run real browser assertions — there is no "pass because env
// is absent" path here.
import type { Page } from "@playwright/test";

export interface Creds {
  email: string;
  password: string;
}

function isSet(value: string | undefined): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

/** Names of the given env vars that are unset or blank. */
export function missingEnv(keys: string[]): string[] {
  return keys.filter((k) => !isSet(process.env[k]));
}

/** Human-readable BLOCKED reason for a skip, pointing at the runbook. */
export function blockedReason(missing: string[]): string {
  return (
    `BLOCKED: missing required env (${missing.join(", ")}). ` +
    `Configure against a deployed staging stack — see ` +
    `docs/f2.27-smoke-checklist.md.`
  );
}

/** Store smoke credentials (E2E_USER_*), or null if not fully provided. */
export function storeCreds(): Creds | null {
  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;
  if (!isSet(email) || !isSet(password)) return null;
  return { email, password };
}

/**
 * Admin smoke credentials. Prefers E2E_ADMIN_*; falls back to E2E_USER_* only
 * when the operator has documented those as valid for an admin account.
 */
export function adminCreds(): Creds | null {
  const email = process.env.E2E_ADMIN_EMAIL ?? process.env.E2E_USER_EMAIL;
  const password =
    process.env.E2E_ADMIN_PASSWORD ?? process.env.E2E_USER_PASSWORD;
  if (!isSet(email) || !isSet(password)) return null;
  return { email, password };
}

/** Missing-env list for specs that only need a reachable base URL. */
export function baseUrlGate(): string[] {
  return missingEnv(["E2E_BASE_URL"]);
}

/** Missing-env list for store specs (base URL + store credentials). */
export function storeGate(): string[] {
  const missing = missingEnv(["E2E_BASE_URL"]);
  if (!storeCreds()) {
    missing.push("E2E_USER_EMAIL + E2E_USER_PASSWORD");
  }
  return missing;
}

/** Missing-env list for admin specs (base URL + admin/user credentials). */
export function adminGate(): string[] {
  const missing = missingEnv(["E2E_BASE_URL"]);
  if (!adminCreds()) {
    missing.push(
      "E2E_ADMIN_EMAIL/E2E_USER_EMAIL + E2E_ADMIN_PASSWORD/E2E_USER_PASSWORD",
    );
  }
  return missing;
}

/**
 * Sign in through the real UI. The login form has no test IDs, so we use
 * stable accessible selectors: the email/password input types and the
 * "Sign In" button (which is type="button", not submit). Feature code is not
 * modified for the harness.
 */
export async function uiLogin(page: Page, creds: Creds): Promise<void> {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(creds.email);
  await page.locator('input[type="password"]').fill(creds.password);
  await page.getByRole("button", { name: /sign in/i }).click();
}
