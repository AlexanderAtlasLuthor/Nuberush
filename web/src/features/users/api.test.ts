// F2.9.1 + F2.15.4: API-layer unit tests for users.
//
// Strategy mirrors features/products/api.test.ts: stub `@/api` so every
// call to the users API resolves against a controlled `apiRequest`
// mock. We assert URL, HTTP method and body payload — exactly what the
// wire contract guarantees. No fetch, no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  adminSetUserPassword,
  assignUserStore,
  changeUserRole,
  createUser,
  deactivateUser,
  getUser,
  listUsers,
  reactivateUser,
  updateUser,
} from "./api";
import * as usersApi from "./api";
import type {
  CreateUserRequest,
  UserRead,
} from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "33333333-3333-3333-3333-333333333333";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// createUser
// --------------------------------------------------------------------- //

describe("createUser", () => {
  it("calls POST /auth/users with the request body verbatim", async () => {
    const body: CreateUserRequest = {
      full_name: "Jane Operator",
      email: "jane@example.com",
      password: "supersecret123",
      role: "staff",
      store_id: STORE_ID,
    };

    await createUser({ body });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe("/auth/users");
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual(body);
  });

  it("forwards every supported field in the body without dropping or renaming", async () => {
    const body: CreateUserRequest = {
      full_name: "Driver Dan",
      email: "dan@example.com",
      password: "anotherpw98765",
      role: "driver",
      store_id: STORE_ID,
      phone: "+15555550123",
    };

    await createUser({ body });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual(body);
    // Snake_case wire contract — no camelCase rewriting.
    const sent = options?.body as Record<string, unknown>;
    expect(Object.keys(sent).sort()).toEqual(
      ["email", "full_name", "password", "phone", "role", "store_id"].sort(),
    );
  });

  it("preserves an explicit null store_id (admin target signal)", async () => {
    const body: CreateUserRequest = {
      full_name: "Global Admin",
      email: "root@example.com",
      password: "supersecret123",
      role: "admin",
      store_id: null,
    };

    await createUser({ body });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    const sent = options?.body as { store_id: unknown };
    expect("store_id" in (options?.body as object)).toBe(true);
    expect(sent.store_id).toBeNull();
  });

  it("omits store_id when not provided (lets backend derive it)", async () => {
    const body: CreateUserRequest = {
      full_name: "Owner-derived",
      email: "owner-derived@example.com",
      password: "supersecret123",
      role: "staff",
    };

    await createUser({ body });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    const sent = options?.body as Record<string, unknown>;
    expect("store_id" in sent).toBe(false);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    const body: CreateUserRequest = {
      full_name: "Cancelable",
      email: "cancel@example.com",
      password: "supersecret123",
      role: "staff",
      store_id: STORE_ID,
    };

    await createUser({ body }, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("returns the UserRead response from apiRequest unchanged", async () => {
    const response: UserRead = {
      id: "11111111-1111-1111-1111-111111111111",
      full_name: "Jane Operator",
      email: "jane@example.com",
      role: "staff",
      store_id: STORE_ID,
      is_active: true,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);

    const result = await createUser({
      body: {
        full_name: "Jane Operator",
        email: "jane@example.com",
        password: "supersecret123",
        role: "staff",
        store_id: STORE_ID,
      },
    });

    expect(result).toEqual(response);
    expect(result).toBe(response);
  });

  it("propagates errors from apiRequest unchanged (no try/catch in feature layer)", async () => {
    const boom = new Error("boom");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);

    await expect(
      createUser({
        body: {
          full_name: "x",
          email: "x@example.com",
          password: "supersecret123",
          role: "staff",
          store_id: STORE_ID,
        },
      }),
    ).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("users api public surface", () => {
  it("exports the F2.15.4 surface (create + list + read + 6 mutations)", () => {
    const exported = Object.keys(usersApi).sort();
    expect(exported).toEqual(
      [
        "adminSetUserPassword",
        "assignUserStore",
        "changeUserRole",
        "createUser",
        "deactivateUser",
        "getUser",
        "listUsers",
        "reactivateUser",
        "updateUser",
      ].sort(),
    );
  });

  it("does not export functions for endpoints the backend has not implemented", () => {
    // The backend still does not surface these — adding them here
    // would either 404 at runtime or silently invent a contract.
    const forbidden = [
      "deleteUser",
      "listRoles",
      "getRoles",
      "listPermissions",
      "getPermissions",
      "listStores",
      "getStores",
      "inviteUser",
      "sendPasswordReset",
      "resetUserPassword",
    ];
    for (const name of forbidden) {
      expect(usersApi).not.toHaveProperty(name);
    }
  });
});

// --------------------------------------------------------------------- //
// F2.15.4 API surface — list / read / mutate
// --------------------------------------------------------------------- //

const USER_ID = "11111111-1111-1111-1111-111111111111";
const STORE_B = "44444444-4444-4444-4444-444444444444";

describe("listUsers", () => {
  it("calls GET /auth/users with no query string when filters are empty", async () => {
    await listUsers();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/auth/users");
    expect(options?.method ?? "GET").toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset", async () => {
    await listUsers({ limit: 25, offset: 50 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/auth/users?limit=25&offset=50");
  });

  it("serialises role", async () => {
    await listUsers({ role: "manager" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/auth/users?role=manager");
  });

  it("serialises is_active=true", async () => {
    await listUsers({ is_active: true });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/auth/users?is_active=true");
  });

  it("serialises is_active=false (an explicit false is meaningful)", async () => {
    await listUsers({ is_active: false });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/auth/users?is_active=false");
  });

  it("serialises store_id", async () => {
    await listUsers({ store_id: STORE_B });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users?store_id=${STORE_B}`);
  });

  it("serialises q", async () => {
    await listUsers({ q: "alice" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/auth/users?q=alice");
  });

  it("drops empty q (undefined-equivalent at the wire)", async () => {
    await listUsers({ q: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/auth/users");
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const ctrl = new AbortController();
    await listUsers({ limit: 1 }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });
});

describe("getUser", () => {
  it("calls GET /auth/users/{id}", async () => {
    await getUser({ userId: USER_ID });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users/${USER_ID}`);
    expect(options?.method ?? "GET").toBe("GET");
  });
});

describe("updateUser", () => {
  it("calls PATCH /auth/users/{id} with the body verbatim", async () => {
    await updateUser({
      userId: USER_ID,
      body: { full_name: "Renamed", phone: "+1-555-0100" },
    });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users/${USER_ID}`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({
      full_name: "Renamed",
      phone: "+1-555-0100",
    });
  });

  it("preserves an explicit null phone", async () => {
    await updateUser({ userId: USER_ID, body: { phone: null } });
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    const sent = options?.body as { phone: unknown };
    expect("phone" in (options?.body as object)).toBe(true);
    expect(sent.phone).toBeNull();
  });
});

describe("deactivateUser", () => {
  it("calls POST /auth/users/{id}/deactivate without a body", async () => {
    await deactivateUser({ userId: USER_ID });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users/${USER_ID}/deactivate`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeUndefined();
  });
});

describe("reactivateUser", () => {
  it("calls POST /auth/users/{id}/reactivate without a body", async () => {
    await reactivateUser({ userId: USER_ID });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users/${USER_ID}/reactivate`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeUndefined();
  });
});

describe("changeUserRole", () => {
  it("calls PATCH /auth/users/{id}/role with the body verbatim", async () => {
    await changeUserRole({
      userId: USER_ID,
      body: { role: "owner" },
    });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users/${USER_ID}/role`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({ role: "owner" });
  });
});

describe("assignUserStore", () => {
  it("calls PATCH /auth/users/{id}/store with a UUID body", async () => {
    await assignUserStore({
      userId: USER_ID,
      body: { store_id: STORE_B },
    });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users/${USER_ID}/store`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({ store_id: STORE_B });
  });

  it("preserves an explicit null store_id (admin target signal)", async () => {
    await assignUserStore({
      userId: USER_ID,
      body: { store_id: null },
    });
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    const sent = options?.body as { store_id: unknown };
    expect(sent.store_id).toBeNull();
  });
});

describe("adminSetUserPassword", () => {
  it("calls POST /auth/users/{id}/password with new_password only", async () => {
    await adminSetUserPassword({
      userId: USER_ID,
      body: { new_password: "fresh-secret-1234" },
    });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/auth/users/${USER_ID}/password`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({ new_password: "fresh-secret-1234" });
    // Defense in depth: nothing about the wire mentions a hash.
    const keys = Object.keys(options?.body as object);
    expect(keys).toEqual(["new_password"]);
    expect(keys).not.toContain("password_hash");
  });

  it("returns the UserRead (no password_hash on the type)", async () => {
    const response: UserRead = {
      id: USER_ID,
      full_name: "Whoever",
      email: "x@example.com",
      role: "staff",
      store_id: STORE_B,
      is_active: true,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);
    const result = await adminSetUserPassword({
      userId: USER_ID,
      body: { new_password: "fresh-secret-1234" },
    });
    expect(result).toEqual(response);
    // UserRead does not declare password_hash, so the runtime
    // response also does not carry it (the backend response_model is
    // UserRead by contract). A guard test against the type:
    expect(Object.keys(result)).not.toContain("password_hash");
  });
});
