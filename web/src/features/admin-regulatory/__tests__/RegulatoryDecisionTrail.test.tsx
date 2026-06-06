// F2.26.6.E: tests for the decision trail (regulatory decision audit history).
//
// Renders RegulatoryDecisionTrail directly, mocking the decisions query hook.
// Covers loading/error/retry/empty/success, humanized action labels (no raw
// enum), actor/reason/created_at, before→after status (incl. placeholders),
// and safe metadata rendering for null / simple / nested / oversized shapes.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { RegulatoryDecisionTrail } from "../components/RegulatoryDecisionTrail";
import * as hooks from "../hooks";
import type {
  RegulatoryDecisionAuditLog,
  RegulatoryDecisionAuditLogListResponse,
} from "../types";

vi.mock("../hooks", () => ({
  useAdminRegulatoryAlertDecisions: vi.fn(),
}));

const ALERT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const ACTOR_ID = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee";

let seq = 0;
function makeDecision(
  overrides: Partial<RegulatoryDecisionAuditLog> = {},
): RegulatoryDecisionAuditLog {
  seq += 1;
  return {
    id: `decision-${seq}`,
    alert_id: ALERT_ID,
    notice_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
    product_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    actor_user_id: ACTOR_ID,
    action: "alert_acknowledged",
    before: { status: "open" },
    after: { status: "acknowledged" },
    metadata: null,
    reason: "looks legit",
    created_at: "2026-05-12T08:00:00Z",
    ...overrides,
  };
}

function asQueryResult(
  partial: Partial<UseQueryResult<RegulatoryDecisionAuditLogListResponse>>,
): UseQueryResult<RegulatoryDecisionAuditLogListResponse> {
  return {
    refetch: vi.fn(),
    isPending: false,
    isLoading: false,
    isError: false,
    isSuccess: false,
    isFetching: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseQueryResult<RegulatoryDecisionAuditLogListResponse>;
}

function setTrail(
  partial: Partial<UseQueryResult<RegulatoryDecisionAuditLogListResponse>>,
) {
  vi.mocked(hooks.useAdminRegulatoryAlertDecisions).mockReturnValue(
    asQueryResult(partial),
  );
}

function setItems(items: RegulatoryDecisionAuditLog[]) {
  setTrail({
    isSuccess: true,
    data: { items, total: items.length, limit: 25, offset: 0 },
  });
}

beforeEach(() => {
  seq = 0;
  vi.clearAllMocks();
  setItems([]);
});

afterEach(() => {
  vi.clearAllMocks();
});

function renderTrail() {
  return render(<RegulatoryDecisionTrail alertId={ALERT_ID} />);
}

// --------------------------------------------------------------------- //
// States
// --------------------------------------------------------------------- //

describe("RegulatoryDecisionTrail — states", () => {
  it("queries the decisions hook with the alert id", () => {
    renderTrail();
    expect(hooks.useAdminRegulatoryAlertDecisions).toHaveBeenCalledWith(
      ALERT_ID,
      expect.objectContaining({ limit: 25, offset: 0 }),
    );
  });

  it("shows a loading state", () => {
    setTrail({ isLoading: true });
    renderTrail();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error state and retry calls refetch", () => {
    const refetch = vi.fn();
    setTrail({
      isError: true,
      error: new ApiError({ status: 500, message: "boom" }),
      refetch,
    });
    renderTrail();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("shows the exact empty-state copy", () => {
    setItems([]);
    renderTrail();
    expect(
      screen.getByText(
        "No decisions have been recorded for this alert yet.",
      ),
    ).toBeInTheDocument();
  });

  it("renders one row per decision on success", () => {
    setItems([makeDecision(), makeDecision()]);
    renderTrail();
    expect(screen.getAllByTestId("regulatory-decision-row")).toHaveLength(2);
  });
});

// --------------------------------------------------------------------- //
// Field rendering
// --------------------------------------------------------------------- //

describe("RegulatoryDecisionTrail — fields", () => {
  it("humanizes every action label and never shows the raw enum", () => {
    setItems([
      makeDecision({ action: "alert_acknowledged" }),
      makeDecision({ action: "alert_dismissed" }),
      makeDecision({ action: "alert_resolved_no_action" }),
      makeDecision({ action: "alert_resolved_hold" }),
      makeDecision({ action: "alert_resolved_ban" }),
    ]);
    renderTrail();
    const labels = screen
      .getAllByTestId("regulatory-decision-action")
      .map((el) => el.textContent);
    expect(labels).toEqual([
      "Alert acknowledged",
      "Alert dismissed",
      "Resolved with no action",
      "Resolved with hold",
      "Resolved with ban",
    ]);
    // No raw enum value leaks into the trail.
    const trail = screen.getByTestId("regulatory-decision-trail");
    expect(trail.textContent).not.toMatch(/alert_acknowledged|alert_resolved_/);
  });

  it("shows actor_user_id, reason and a formatted created_at", () => {
    setItems([
      makeDecision({
        actor_user_id: ACTOR_ID,
        reason: "documented reason",
        created_at: "2026-05-12T08:00:00Z",
      }),
    ]);
    renderTrail();
    const row = screen.getByTestId("regulatory-decision-row");
    expect(
      within(row).getByTestId("regulatory-decision-actor"),
    ).toHaveTextContent(ACTOR_ID);
    expect(
      within(row).getByTestId("regulatory-decision-reason"),
    ).toHaveTextContent("documented reason");
    expect(
      within(row).getByTestId("regulatory-decision-created"),
    ).toHaveTextContent("2026-05-12");
  });

  it("renders before→after status from the snapshot, humanized", () => {
    setItems([
      makeDecision({
        before: { status: "open" },
        after: { status: "actioned" },
      }),
    ]);
    renderTrail();
    const row = screen.getByTestId("regulatory-decision-row");
    expect(
      within(within(row).getByTestId("regulatory-decision-before")).getByText(
        "Open",
      ),
    ).toBeInTheDocument();
    expect(
      within(within(row).getByTestId("regulatory-decision-after")).getByText(
        "Actioned",
      ),
    ).toBeInTheDocument();
  });

  it("shows a placeholder when before/after status is missing or unknown", () => {
    setItems([
      makeDecision({ before: null, after: { foo: "bar" } }),
    ]);
    renderTrail();
    const row = screen.getByTestId("regulatory-decision-row");
    expect(
      within(row).getByTestId("regulatory-decision-before"),
    ).toHaveTextContent("—");
    expect(
      within(row).getByTestId("regulatory-decision-after"),
    ).toHaveTextContent("—");
  });
});

// --------------------------------------------------------------------- //
// Metadata
// --------------------------------------------------------------------- //

describe("RegulatoryDecisionTrail — metadata", () => {
  it("shows a placeholder when metadata is null", () => {
    setItems([makeDecision({ metadata: null })]);
    renderTrail();
    expect(
      screen.getByTestId("regulatory-decision-metadata"),
    ).toHaveTextContent("No additional metadata.");
  });

  it("shows a placeholder when metadata is an empty object", () => {
    setItems([makeDecision({ metadata: {} })]);
    renderTrail();
    expect(
      screen.getByTestId("regulatory-decision-metadata"),
    ).toHaveTextContent("No additional metadata.");
  });

  it("renders a compact key/value summary for simple metadata", () => {
    setItems([
      makeDecision({
        metadata: { resolution_action: "hold", product_id: null },
      }),
    ]);
    renderTrail();
    const meta = screen.getByTestId("regulatory-decision-metadata");
    expect(meta).toHaveTextContent("resolution_action:");
    expect(meta).toHaveTextContent("hold");
    expect(meta).toHaveTextContent("product_id:");
    // null value renders the em-dash placeholder, not "null".
    expect(meta).toHaveTextContent("—");
  });

  it("renders nested metadata safely (no [object Object], no crash)", () => {
    setItems([
      makeDecision({ metadata: { nested: { a: 1, b: 2 } } }),
    ]);
    renderTrail();
    const meta = screen.getByTestId("regulatory-decision-metadata");
    expect(meta.textContent).not.toContain("[object Object]");
    expect(meta).toHaveTextContent('{"a":1,"b":2}');
  });

  it("collapses oversized metadata values to a generic label", () => {
    const big = { items: Array.from({ length: 50 }, (_, i) => `v${i}`) };
    setItems([makeDecision({ metadata: { big } })]);
    renderTrail();
    const meta = screen.getByTestId("regulatory-decision-metadata");
    expect(meta.textContent).not.toContain("[object Object]");
    expect(meta).toHaveTextContent("Additional metadata recorded");
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("RegulatoryDecisionTrail — boundaries", () => {
  it("source avoids fetch / supabase / auth / store / raw query client / mutations", async () => {
    const fs = await import("node:fs");
    // Vitest runs from web/, so read the source via a cwd-relative path.
    const raw = fs.readFileSync(
      "src/features/admin-regulatory/components/RegulatoryDecisionTrail.tsx",
      "utf8",
    );
    const code = raw
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/[^\n]*/g, "");
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code.toLowerCase()).not.toContain("supabase");
    expect(code).not.toMatch(/useAuth|AuthContext|AuthProvider/);
    expect(code).not.toMatch(/useStoreContext|StoreContext|StoreProvider/);
    expect(code).not.toMatch(/useQueryClient|useMutation/);
    expect(code).not.toMatch(/from\s+["'][^"']*\/(auth|store)\//);
  });
});
