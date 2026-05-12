// F2.15.4: query-key factory unit tests for the users module.
//
// Pure unit tests on the key factory — no React, no QueryClient. We
// assert the shape of every key the brief calls out and the prefix
// relationships used by mutation invalidations.

import { describe, expect, it } from "vitest";

import { usersQueryKeys } from "../queryKeys";

const USER_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_ID = "22222222-2222-2222-2222-222222222222";

describe("usersQueryKeys", () => {
  it("anchors every key under the 'users' root", () => {
    expect(usersQueryKeys.all).toEqual(["users"]);
  });

  it("lists() returns the prefix shared by every list call", () => {
    expect(usersQueryKeys.lists()).toEqual(["users", "list"]);
  });

  it("list(filters) appends the filters object verbatim", () => {
    expect(
      usersQueryKeys.list({ limit: 25, role: "staff", is_active: false }),
    ).toEqual([
      "users",
      "list",
      { limit: 25, role: "staff", is_active: false },
    ]);
  });

  it("list() with no args defaults to an empty filters object", () => {
    expect(usersQueryKeys.list()).toEqual(["users", "list", {}]);
  });

  it("lists() is a prefix of list(filters)", () => {
    const prefix = usersQueryKeys.lists();
    const concrete = usersQueryKeys.list({ q: "alice" });
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("detail(userId) returns ['users','detail', id]", () => {
    expect(usersQueryKeys.detail(USER_ID)).toEqual([
      "users",
      "detail",
      USER_ID,
    ]);
  });

  it("details() is a prefix of detail(id)", () => {
    const prefix = usersQueryKeys.details();
    const concrete = usersQueryKeys.detail(USER_ID);
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("list and detail keys never collide (different root segments)", () => {
    expect(usersQueryKeys.list({ q: "x" })[1]).toBe("list");
    expect(usersQueryKeys.detail(USER_ID)[1]).toBe("detail");
    // Ensure no list key happens to equal a detail key.
    expect(usersQueryKeys.list({ q: USER_ID })).not.toEqual(
      usersQueryKeys.detail(USER_ID),
    );
  });

  it("two detail keys for different ids are distinct", () => {
    expect(usersQueryKeys.detail(USER_ID)).not.toEqual(
      usersQueryKeys.detail(OTHER_ID),
    );
  });
});
