// F2.24.C6 — ApplyPage wizard flow tests.
//
// Mocks the feature api module (../api) so no network is touched, and
// renders the page inside a MemoryRouter only — NO AuthProvider / store
// context — proving the route needs no auth/session. The real @/api stays
// in place so ApiError / isApiError branch correctly.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ApiError } from "@/api";
import ApplyPage from "../ApplyPage";
import { submitStoreApplication } from "../../api";

vi.mock("../../api", () => ({
  submitStoreApplication: vi.fn(),
}));

const mockedSubmit = vi.mocked(submitStoreApplication);

beforeEach(() => {
  mockedSubmit.mockReset();
  mockedSubmit.mockResolvedValue({
    id: "11111111-1111-1111-1111-111111111111",
    status: "pending_review",
    message: "Application submitted for review.",
  });
});

function renderApply() {
  return render(
    <MemoryRouter>
      <ApplyPage />
    </MemoryRouter>,
  );
}

function setField(id: string, value: string) {
  fireEvent.change(screen.getByTestId(`apply-field-${id}`), {
    target: { value },
  });
}

function start() {
  fireEvent.click(screen.getByTestId("apply-start"));
}

function fillBusiness(over: Record<string, string> = {}) {
  const v: Record<string, string> = {
    business_name: "Acme Vapes",
    business_type: "vape_shop",
    business_phone: "+1 555 0199",
    address_line_1: "1 Test Way",
    city: "Miami",
    state: "FL",
    postal_code: "33101",
    ...over,
  };
  for (const [k, val] of Object.entries(v)) setField(k, val);
}

function fillOwner(over: Record<string, string> = {}) {
  const v: Record<string, string> = {
    owner_full_name: "Jane Owner",
    owner_email: "jane@example.com",
    owner_phone: "+1 555 0100",
    ...over,
  };
  for (const [k, val] of Object.entries(v)) setField(k, val);
}

function next() {
  fireEvent.click(screen.getByTestId("apply-next"));
}

/** Drive the wizard from welcome to the review step with valid data. */
function advanceToReview() {
  start();
  fillBusiness();
  next();
  fillOwner();
  next();
  setField("hours_of_operation", "Mon-Fri 9-5");
  next();
}

// --------------------------------------------------------------------- //

describe("ApplyPage wizard", () => {
  it("renders the welcome step with reviewed-application messaging", () => {
    renderApply();
    const welcome = within(screen.getByTestId("apply-welcome"));
    expect(
      welcome.getByText(/does not guarantee approval/i),
    ).toBeInTheDocument();
    expect(
      welcome.getByText(/reviewed before activation/i),
    ).toBeInTheDocument();
  });

  it("renders exactly one h1 (public single-heading contract)", () => {
    renderApply();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("advances through steps with valid data", () => {
    renderApply();
    start();
    expect(screen.getByTestId("apply-field-business_name")).toBeInTheDocument();
    fillBusiness();
    next();
    expect(screen.getByTestId("apply-field-owner_email")).toBeInTheDocument();
    fillOwner();
    next();
    expect(
      screen.getByTestId("apply-field-hours_of_operation"),
    ).toBeInTheDocument();
  });

  it("blocks progression when a required field is blank", () => {
    renderApply();
    start();
    // Leave business_name blank.
    fillBusiness({ business_name: "" });
    next();
    expect(screen.getByTestId("apply-error-business_name")).toBeInTheDocument();
    // Still on the business step.
    expect(screen.getByTestId("apply-field-business_name")).toBeInTheDocument();
    expect(
      screen.queryByTestId("apply-field-owner_email"),
    ).not.toBeInTheDocument();
  });

  it("shows an error for an invalid owner email", () => {
    renderApply();
    start();
    fillBusiness();
    next();
    fillOwner({ owner_email: "not-an-email" });
    next();
    expect(screen.getByTestId("apply-error-owner_email")).toBeInTheDocument();
    expect(screen.getByTestId("apply-field-owner_email")).toBeInTheDocument();
  });

  it("shows an error for location_count < 1", () => {
    renderApply();
    start();
    fillBusiness({ location_count: "0" });
    next();
    expect(
      screen.getByTestId("apply-error-location_count"),
    ).toBeInTheDocument();
  });

  it("shows an error for estimated_weekly_orders < 0", () => {
    renderApply();
    start();
    fillBusiness({ estimated_weekly_orders: "-1" });
    next();
    expect(
      screen.getByTestId("apply-error-estimated_weekly_orders"),
    ).toBeInTheDocument();
  });

  it("requires the terms checkbox before submitting", () => {
    renderApply();
    advanceToReview();
    // Submit without checking terms.
    fireEvent.click(screen.getByTestId("apply-submit"));
    expect(
      screen.getByTestId("apply-error-terms_accepted"),
    ).toBeInTheDocument();
    expect(mockedSubmit).not.toHaveBeenCalled();
  });

  it("submits the exact backend payload and shows the pending state", async () => {
    renderApply();
    advanceToReview();
    fireEvent.click(screen.getByTestId("apply-terms"));
    fireEvent.click(screen.getByTestId("apply-submit"));

    await screen.findByTestId("apply-submitted");

    expect(mockedSubmit).toHaveBeenCalledTimes(1);
    expect(mockedSubmit).toHaveBeenCalledWith({
      business_name: "Acme Vapes",
      business_type: "vape_shop",
      owner_full_name: "Jane Owner",
      owner_email: "jane@example.com",
      owner_phone: "+1 555 0100",
      business_phone: "+1 555 0199",
      address_line_1: "1 Test Way",
      city: "Miami",
      state: "FL",
      postal_code: "33101",
      country: "US",
      location_count: 1,
      estimated_weekly_orders: 0,
      hours_of_operation: "Mon-Fri 9-5",
      terms_accepted: true,
    });
  });

  it("never sends forbidden fields in the submitted payload", async () => {
    renderApply();
    advanceToReview();
    fireEvent.click(screen.getByTestId("apply-terms"));
    fireEvent.click(screen.getByTestId("apply-submit"));
    await screen.findByTestId("apply-submitted");

    const sent = mockedSubmit.mock.calls[0][0] as Record<string, unknown>;
    for (const forbidden of [
      "status",
      "role",
      "store_id",
      "user_id",
      "auth_user_id",
      "is_admin",
      "public_lookup_token",
      "reviewed_by_user_id",
      "provisioned_store_id",
      "provisioned_owner_user_id",
    ]) {
      expect(sent).not.toHaveProperty(forbidden);
    }
  });

  it("shows the pending-review submitted state on success", async () => {
    renderApply();
    advanceToReview();
    fireEvent.click(screen.getByTestId("apply-terms"));
    fireEvent.click(screen.getByTestId("apply-submit"));

    const submitted = await screen.findByTestId("apply-submitted");
    expect(submitted).toHaveTextContent(/application submitted/i);
    expect(submitted).toHaveTextContent(/pending review/i);
  });

  it("shows a friendly duplicate message on a 409", async () => {
    mockedSubmit.mockRejectedValueOnce(
      new ApiError({ status: 409, message: "conflict" }),
    );
    renderApply();
    advanceToReview();
    fireEvent.click(screen.getByTestId("apply-terms"));
    fireEvent.click(screen.getByTestId("apply-submit"));

    const err = await screen.findByTestId("apply-submit-error");
    expect(err).toHaveTextContent(/already active or under review/i);
    expect(screen.queryByTestId("apply-submitted")).not.toBeInTheDocument();
  });

  it("shows a friendly validation message on a 422", async () => {
    mockedSubmit.mockRejectedValueOnce(
      new ApiError({ status: 422, message: "unprocessable" }),
    );
    renderApply();
    advanceToReview();
    fireEvent.click(screen.getByTestId("apply-terms"));
    fireEvent.click(screen.getByTestId("apply-submit"));

    const err = await screen.findByTestId("apply-submit-error");
    expect(err).toHaveTextContent(/needs attention/i);
  });

  it("shows a generic message on an unexpected failure", async () => {
    mockedSubmit.mockRejectedValueOnce(new Error("network down"));
    renderApply();
    advanceToReview();
    fireEvent.click(screen.getByTestId("apply-terms"));
    fireEvent.click(screen.getByTestId("apply-submit"));

    const err = await screen.findByTestId("apply-submit-error");
    expect(err).toHaveTextContent(/couldn't submit your application/i);
  });

  it("renders without any auth/session context (public route)", () => {
    // No AuthProvider is mounted; rendering succeeds, proving the page
    // requires no auth/session and never redirects into /app.
    renderApply();
    expect(screen.getByTestId("apply-welcome")).toBeInTheDocument();
  });
});
