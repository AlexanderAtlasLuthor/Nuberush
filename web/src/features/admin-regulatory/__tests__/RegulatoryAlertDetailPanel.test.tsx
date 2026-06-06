// F2.26.6.D: tests for the alert detail panel + lifecycle action UI.
//
// Renders RegulatoryAlertDetailPanel directly, mocking the feature hooks so we
// can assert: detail states/fields, close, action visibility per status,
// terminal copy, required reason/note, exact mutation bodies, hold/ban
// consequence copy, mutation loading/error, success-clears-dialog, and that
// no decision-trail query is used. A final architecture guard greps sources.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { RegulatoryAlertDetailPanel } from "../components/RegulatoryAlertDetailPanel";
import * as hooks from "../hooks";
import type { ComplianceAlert } from "../types";

vi.mock("../hooks", () => ({
  useAdminRegulatoryAlert: vi.fn(),
  useAcknowledgeAdminRegulatoryAlert: vi.fn(),
  useDismissAdminRegulatoryAlert: vi.fn(),
  useResolveAdminRegulatoryAlert: vi.fn(),
}));

const ALERT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const PRODUCT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const NOTICE_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc";
const MATCH_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd";

function makeAlert(overrides: Partial<ComplianceAlert> = {}): ComplianceAlert {
  return {
    id: ALERT_ID,
    notice_id: NOTICE_ID,
    product_id: PRODUCT_ID,
    match_id: MATCH_ID,
    severity: "high",
    status: "open",
    recommended_action: "hold",
    resolution_note: null,
    resolved_by_user_id: null,
    resolved_at: null,
    created_at: "2026-05-12T08:00:00Z",
    updated_at: "2026-05-12T09:00:00Z",
    ...overrides,
  };
}

function asQueryResult(
  partial: Partial<UseQueryResult<ComplianceAlert>>,
): UseQueryResult<ComplianceAlert> {
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
  } as unknown as UseQueryResult<ComplianceAlert>;
}

function makeMutation(
  partial: Partial<UseMutationResult> = {},
): UseMutationResult & { mutate: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseMutationResult & { mutate: ReturnType<typeof vi.fn> };
}

function setDetail(partial: Partial<UseQueryResult<ComplianceAlert>>) {
  vi.mocked(hooks.useAdminRegulatoryAlert).mockReturnValue(
    asQueryResult(partial),
  );
}
function setAck(m: ReturnType<typeof makeMutation>) {
  vi.mocked(hooks.useAcknowledgeAdminRegulatoryAlert).mockReturnValue(
    m as never,
  );
}
function setDismiss(m: ReturnType<typeof makeMutation>) {
  vi.mocked(hooks.useDismissAdminRegulatoryAlert).mockReturnValue(m as never);
}
function setResolve(m: ReturnType<typeof makeMutation>) {
  vi.mocked(hooks.useResolveAdminRegulatoryAlert).mockReturnValue(m as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  setDetail({ isSuccess: true, data: makeAlert() });
  setAck(makeMutation());
  setDismiss(makeMutation());
  setResolve(makeMutation());
});

afterEach(() => {
  vi.clearAllMocks();
});

function renderPanel(onClose = vi.fn()) {
  return render(
    <RegulatoryAlertDetailPanel alertId={ALERT_ID} onClose={onClose} />,
  );
}

// --------------------------------------------------------------------- //
// Detail states
// --------------------------------------------------------------------- //

describe("RegulatoryAlertDetailPanel — states", () => {
  it("shows a loading state", () => {
    setDetail({ isLoading: true });
    renderPanel();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error state with the API message", () => {
    setDetail({
      isError: true,
      error: new ApiError({ status: 500, message: "kaboom" }),
    });
    renderPanel();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows a not-found state when data is missing", () => {
    setDetail({ isSuccess: true, data: undefined });
    renderPanel();
    expect(
      screen.getByTestId("regulatory-detail-missing"),
    ).toBeInTheDocument();
  });

  it("close button calls onClose", () => {
    const onClose = vi.fn();
    renderPanel(onClose);
    fireEvent.click(screen.getByTestId("regulatory-detail-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

// --------------------------------------------------------------------- //
// Detail fields
// --------------------------------------------------------------------- //

describe("RegulatoryAlertDetailPanel — fields", () => {
  it("renders all alert fields with badges", () => {
    setDetail({
      isSuccess: true,
      data: makeAlert({ severity: "critical", status: "open" }),
    });
    renderPanel();
    expect(screen.getByTestId("regulatory-detail-id")).toHaveTextContent(
      ALERT_ID,
    );
    expect(
      screen.getByTestId("regulatory-detail-product-id"),
    ).toHaveTextContent(PRODUCT_ID);
    expect(
      screen.getByTestId("regulatory-detail-notice-id"),
    ).toHaveTextContent(NOTICE_ID);
    expect(screen.getByTestId("regulatory-detail-match-id")).toHaveTextContent(
      MATCH_ID,
    );
    expect(
      within(screen.getByTestId("regulatory-detail-severity")).getByText(
        "Critical",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("regulatory-detail-status")).getByText("Open"),
    ).toBeInTheDocument();
    expect(
      within(
        screen.getByTestId("regulatory-detail-recommended-action"),
      ).getByText("Hold recommended"),
    ).toBeInTheDocument();
  });

  it("renders em-dash placeholders for null product/match/resolved fields", () => {
    setDetail({
      isSuccess: true,
      data: makeAlert({
        product_id: null,
        match_id: null,
        resolved_at: null,
        resolved_by_user_id: null,
        resolution_note: null,
      }),
    });
    renderPanel();
    expect(
      screen.getByTestId("regulatory-detail-product-id"),
    ).toHaveTextContent("—");
    expect(screen.getByTestId("regulatory-detail-match-id")).toHaveTextContent(
      "—",
    );
    expect(screen.getByTestId("regulatory-detail-resolved")).toHaveTextContent(
      "—",
    );
    expect(
      screen.getByTestId("regulatory-detail-resolved-by"),
    ).toHaveTextContent("—");
    expect(
      screen.getByTestId("regulatory-detail-resolution-note"),
    ).toHaveTextContent("—");
  });
});

// --------------------------------------------------------------------- //
// Action visibility per status
// --------------------------------------------------------------------- //

const ALL_ACTION_IDS = [
  "regulatory-action-acknowledge",
  "regulatory-action-dismiss",
  "regulatory-action-resolve-no_action",
  "regulatory-action-resolve-hold",
  "regulatory-action-resolve-ban",
];

describe("RegulatoryAlertDetailPanel — action visibility", () => {
  it("open alerts show all five lifecycle actions", () => {
    setDetail({ isSuccess: true, data: makeAlert({ status: "open" }) });
    renderPanel();
    for (const id of ALL_ACTION_IDS) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
    expect(
      screen.queryByTestId("regulatory-terminal-note"),
    ).not.toBeInTheDocument();
  });

  it("acknowledged alerts still show lifecycle actions", () => {
    setDetail({ isSuccess: true, data: makeAlert({ status: "acknowledged" }) });
    renderPanel();
    for (const id of ALL_ACTION_IDS) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
  });

  it("actioned alerts hide actions and show terminal copy", () => {
    setDetail({ isSuccess: true, data: makeAlert({ status: "actioned" }) });
    renderPanel();
    expect(
      screen.queryByTestId("regulatory-alert-actions"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("regulatory-terminal-note"),
    ).toHaveTextContent(/already been actioned/i);
  });

  it("dismissed alerts hide actions and show terminal copy", () => {
    setDetail({ isSuccess: true, data: makeAlert({ status: "dismissed" }) });
    renderPanel();
    expect(
      screen.queryByTestId("regulatory-alert-actions"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("regulatory-terminal-note"),
    ).toHaveTextContent(/already been dismissed/i);
  });
});

// --------------------------------------------------------------------- //
// Action bodies + required reason/note
// --------------------------------------------------------------------- //

function openAction(testId: string) {
  fireEvent.click(screen.getByTestId(testId));
}

describe("RegulatoryAlertDetailPanel — acknowledge", () => {
  it("requires a non-empty reason and submits { reason } trimmed", () => {
    const ack = makeMutation();
    setAck(ack);
    renderPanel();
    openAction("regulatory-action-acknowledge");

    const confirm = screen.getByTestId("regulatory-resolution-confirm");
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByTestId("regulatory-resolution-note"), {
      target: { value: "   " },
    });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByTestId("regulatory-resolution-note"), {
      target: { value: "  looks legit  " },
    });
    expect(confirm).not.toBeDisabled();
    fireEvent.click(confirm);

    expect(ack.mutate).toHaveBeenCalledWith({
      alertId: ALERT_ID,
      body: { reason: "looks legit" },
    });
  });
});

describe("RegulatoryAlertDetailPanel — dismiss", () => {
  it("submits { reason } via the dismiss hook", () => {
    const dismiss = makeMutation();
    setDismiss(dismiss);
    renderPanel();
    openAction("regulatory-action-dismiss");

    fireEvent.change(screen.getByTestId("regulatory-resolution-note"), {
      target: { value: "not our product" },
    });
    fireEvent.click(screen.getByTestId("regulatory-resolution-confirm"));

    expect(dismiss.mutate).toHaveBeenCalledWith({
      alertId: ALERT_ID,
      body: { reason: "not our product" },
    });
  });
});

describe("RegulatoryAlertDetailPanel — resolve", () => {
  it("no_action submits { action: 'no_action', resolution_note }", () => {
    const resolve = makeMutation();
    setResolve(resolve);
    renderPanel();
    openAction("regulatory-action-resolve-no_action");

    fireEvent.change(screen.getByTestId("regulatory-resolution-note"), {
      target: { value: "reviewed, fine" },
    });
    fireEvent.click(screen.getByTestId("regulatory-resolution-confirm"));

    expect(resolve.mutate).toHaveBeenCalledWith({
      alertId: ALERT_ID,
      body: { action: "no_action", resolution_note: "reviewed, fine" },
    });
  });

  it("hold shows the required consequence copy and submits a hold body", () => {
    const resolve = makeMutation();
    setResolve(resolve);
    renderPanel();
    openAction("regulatory-action-resolve-hold");

    expect(screen.getByTestId("regulatory-consequence")).toHaveTextContent(
      "This will mark the product as restricted and not allowed for sale through the audited compliance service.",
    );

    fireEvent.change(screen.getByTestId("regulatory-resolution-note"), {
      target: { value: "pending review" },
    });
    fireEvent.click(screen.getByTestId("regulatory-resolution-confirm"));

    expect(resolve.mutate).toHaveBeenCalledWith({
      alertId: ALERT_ID,
      body: { action: "hold", resolution_note: "pending review" },
    });
  });

  it("ban shows the required consequence copy and submits a ban body", () => {
    const resolve = makeMutation();
    setResolve(resolve);
    renderPanel();
    openAction("regulatory-action-resolve-ban");

    expect(screen.getByTestId("regulatory-consequence")).toHaveTextContent(
      "This will mark the product as banned and not allowed for sale. Existing inventory quarantine rules may apply.",
    );

    fireEvent.change(screen.getByTestId("regulatory-resolution-note"), {
      target: { value: "FDA enforcement" },
    });
    fireEvent.click(screen.getByTestId("regulatory-resolution-confirm"));

    expect(resolve.mutate).toHaveBeenCalledWith({
      alertId: ALERT_ID,
      body: { action: "ban", resolution_note: "FDA enforcement" },
    });
  });
});

// --------------------------------------------------------------------- //
// Mutation loading / error / success
// --------------------------------------------------------------------- //

describe("RegulatoryAlertDetailPanel — mutation feedback", () => {
  it("pending mutation disables confirm and shows a pending label", () => {
    setAck(makeMutation({ isPending: true }));
    renderPanel();
    openAction("regulatory-action-acknowledge");

    const confirm = screen.getByTestId("regulatory-resolution-confirm");
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveTextContent(/acknowledging…/i);
  });

  it("shows the mutation error message", () => {
    setAck(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 422, message: "reason required" }),
      }),
    );
    renderPanel();
    openAction("regulatory-action-acknowledge");
    expect(
      screen.getByTestId("regulatory-resolution-error"),
    ).toHaveTextContent("reason required");
  });

  it("clears/closes the dialog once the mutation succeeds", () => {
    const ack = makeMutation();
    setAck(ack);
    const { rerender } = renderPanel();
    openAction("regulatory-action-acknowledge");
    expect(
      screen.getByTestId("regulatory-resolution-dialog"),
    ).toBeInTheDocument();

    // Flip the hook to success and re-render: the panel should auto-close it.
    setAck(makeMutation({ isSuccess: true }));
    rerender(
      <RegulatoryAlertDetailPanel alertId={ALERT_ID} onClose={vi.fn()} />,
    );

    expect(
      screen.queryByTestId("regulatory-resolution-dialog"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// No decision-trail usage + architecture guard
// --------------------------------------------------------------------- //

describe("RegulatoryAlertDetailPanel — boundaries", () => {
  // The decision-trail hook is intentionally NOT mocked here; the grep guard
  // below proves none of the new components import or call it this subphase.
  it("new D sources avoid fetch / supabase / auth / store / raw query client / decisions", async () => {
    const fs = await import("node:fs");
    const files = [
      "../components/RegulatoryAlertDetailPanel.tsx",
      "../components/RegulatoryAlertActions.tsx",
      "../components/RegulatoryResolutionDialog.tsx",
    ];
    for (const rel of files) {
      const raw = fs.readFileSync(new URL(rel, import.meta.url), "utf8");
      const code = raw
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/\/\/[^\n]*/g, "");
      expect(code).not.toMatch(/\bfetch\s*\(/);
      expect(code.toLowerCase()).not.toContain("supabase");
      expect(code).not.toMatch(/useAuth|AuthContext|AuthProvider/);
      expect(code).not.toMatch(/useStoreContext|StoreContext|StoreProvider/);
      expect(code).not.toMatch(/useQueryClient/);
      expect(code).not.toMatch(/useAdminRegulatoryAlertDecisions/);
      expect(code).not.toMatch(/from\s+["'][^"']*\/(auth|store)\//);
    }
  });
});
