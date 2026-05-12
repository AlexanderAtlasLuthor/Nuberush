// F2.14.5: tests for StoreSettingsForm.
//
// The form is presentational — no hooks, no fetch, no toast — so the
// tests render it directly with controlled props and assert (a) the
// rendered surface, (b) the dirty/save gating logic, (c) the diff
// payload composition (only changed fields, trimmed), (d) the cancel
// reset behaviour, and (e) the validation messages, both local and
// external.

import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { StoreSettingsForm } from "../StoreSettingsForm";
import type { StoreProfile } from "../../types";

const STORE: StoreProfile = {
  id: "22222222-2222-2222-2222-222222222222",
  name: "Downtown Store",
  code: "DT-001",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function makeStore(overrides: Partial<StoreProfile> = {}): StoreProfile {
  return { ...STORE, ...overrides };
}

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Rendering
// --------------------------------------------------------------------- //

describe("StoreSettingsForm — rendering", () => {
  it("renders the store name from the server in the editable input", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    const nameInput = screen.getByTestId(
      "store-settings-name",
    ) as HTMLInputElement;
    expect(nameInput.value).toBe("Downtown Store");
  });

  it("renders the timezone from the server in the editable input", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    const tzInput = screen.getByTestId(
      "store-settings-timezone",
    ) as HTMLInputElement;
    expect(tzInput.value).toBe("America/New_York");
  });

  it("renders the read-only store code", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    const codeMeta = screen.getByTestId("store-settings-meta-code");
    expect(codeMeta).toHaveTextContent("DT-001");
  });

  it("renders an Active status badge when is_active=true", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    expect(
      screen.getByTestId("store-settings-status-active"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-settings-status-inactive"),
    ).not.toBeInTheDocument();
  });

  it("renders an Inactive status badge when is_active=false", () => {
    render(
      <StoreSettingsForm
        store={makeStore({ is_active: false })}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.getByTestId("store-settings-status-inactive"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-settings-status-active"),
    ).not.toBeInTheDocument();
  });

  it("renders metadata for id, created_at and updated_at", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    expect(screen.getByTestId("store-settings-meta-id")).toHaveTextContent(
      STORE.id,
    );
    expect(
      screen.getByTestId("store-settings-meta-created-at"),
    ).toHaveTextContent(STORE.created_at);
    expect(
      screen.getByTestId("store-settings-meta-updated-at"),
    ).toHaveTextContent(STORE.updated_at);
  });
});

// --------------------------------------------------------------------- //
// Dirty / Save gating
// --------------------------------------------------------------------- //

describe("StoreSettingsForm — dirty/save gating", () => {
  it("disables Save initially (no edits)", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    expect(screen.getByTestId("store-settings-submit")).toBeDisabled();
  });

  it("enables Save when the name changes", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "Renamed Store" },
    });

    expect(screen.getByTestId("store-settings-submit")).not.toBeDisabled();
  });

  it("enables Save when the timezone changes", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "America/Chicago" },
    });

    expect(screen.getByTestId("store-settings-submit")).not.toBeDisabled();
  });

  it("disables Save while pending=true", () => {
    render(
      <StoreSettingsForm store={STORE} onSubmit={vi.fn()} isPending />,
    );

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "Renamed Store" },
    });

    expect(screen.getByTestId("store-settings-submit")).toBeDisabled();
  });

  it("disables Save when the name is cleared", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "" },
    });

    expect(screen.getByTestId("store-settings-submit")).toBeDisabled();
  });

  it("disables Save when the timezone is cleared", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "" },
    });

    expect(screen.getByTestId("store-settings-submit")).toBeDisabled();
  });

  it("renders the Saving… label while pending", () => {
    render(
      <StoreSettingsForm store={STORE} onSubmit={vi.fn()} isPending />,
    );

    expect(screen.getByTestId("store-settings-submit")).toHaveTextContent(
      "Saving…",
    );
  });
});

// --------------------------------------------------------------------- //
// Submit payload composition
// --------------------------------------------------------------------- //

describe("StoreSettingsForm — submit payload", () => {
  it("submits a trimmed name", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "  Trimmed Name  " },
    });
    fireEvent.click(screen.getByTestId("store-settings-submit"));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({ name: "Trimmed Name" });
  });

  it("submits a trimmed timezone", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "  America/Chicago  " },
    });
    fireEvent.click(screen.getByTestId("store-settings-submit"));

    expect(onSubmit).toHaveBeenCalledWith({ timezone: "America/Chicago" });
  });

  it("submits only the changed name (timezone untouched)", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "Renamed" },
    });
    fireEvent.click(screen.getByTestId("store-settings-submit"));

    expect(onSubmit).toHaveBeenCalledWith({ name: "Renamed" });
  });

  it("submits only the changed timezone (name untouched)", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "America/Chicago" },
    });
    fireEvent.click(screen.getByTestId("store-settings-submit"));

    expect(onSubmit).toHaveBeenCalledWith({ timezone: "America/Chicago" });
  });

  it("submits both name and timezone when both changed", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "New Name" },
    });
    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "America/Chicago" },
    });
    fireEvent.click(screen.getByTestId("store-settings-submit"));

    expect(onSubmit).toHaveBeenCalledWith({
      name: "New Name",
      timezone: "America/Chicago",
    });
  });

  it("does not call onSubmit when there are no changes", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    // Form submit via the form element so the disabled button doesn't
    // gate the experiment — we want to assert the inner guard in
    // handleSubmit runs even if the submit somehow fires.
    const form = screen.getByTestId("store-settings-form");
    fireEvent.submit(form);

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not call onSubmit when the name is empty", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "   " },
    });

    const form = screen.getByTestId("store-settings-form");
    fireEvent.submit(form);

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      screen.getByTestId("store-settings-name-error"),
    ).toBeInTheDocument();
  });

  it("does not call onSubmit when the timezone is empty", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "   " },
    });

    const form = screen.getByTestId("store-settings-form");
    fireEvent.submit(form);

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      screen.getByTestId("store-settings-timezone-error"),
    ).toBeInTheDocument();
  });

  it("never includes read-only or out-of-scope fields in the payload", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "New Name" },
    });
    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "America/Chicago" },
    });
    fireEvent.click(screen.getByTestId("store-settings-submit"));

    const payload = onSubmit.mock.calls[0][0] as Record<string, unknown>;
    const allowedKeys = ["name", "timezone"];
    expect(Object.keys(payload).sort()).toEqual(allowedKeys.sort());

    const forbiddenKeys = [
      "id",
      "code",
      "is_active",
      "created_at",
      "updated_at",
      "contact_email",
      "contact_phone",
      "address",
      "business_hours",
      "preferences",
      "notification_defaults",
      "compliance_profile",
      "status",
      "slug",
    ];
    for (const key of forbiddenKeys) {
      expect(payload).not.toHaveProperty(key);
    }
  });
});

// --------------------------------------------------------------------- //
// Cancel
// --------------------------------------------------------------------- //

describe("StoreSettingsForm — cancel", () => {
  it("resets the inputs to the server values", () => {
    render(
      <StoreSettingsForm
        store={STORE}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "Renamed" },
    });
    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "America/Chicago" },
    });

    fireEvent.click(screen.getByTestId("store-settings-cancel"));

    const nameInput = screen.getByTestId(
      "store-settings-name",
    ) as HTMLInputElement;
    const tzInput = screen.getByTestId(
      "store-settings-timezone",
    ) as HTMLInputElement;
    expect(nameInput.value).toBe(STORE.name);
    expect(tzInput.value).toBe(STORE.timezone);
  });

  it("calls onCancel when provided", () => {
    const onCancel = vi.fn();
    render(
      <StoreSettingsForm
        store={STORE}
        onSubmit={vi.fn()}
        onCancel={onCancel}
      />,
    );

    fireEvent.click(screen.getByTestId("store-settings-cancel"));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("clears local validation errors on cancel", () => {
    render(
      <StoreSettingsForm
        store={STORE}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    // Trigger an error first.
    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "" },
    });
    fireEvent.submit(screen.getByTestId("store-settings-form"));
    expect(
      screen.getByTestId("store-settings-name-error"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("store-settings-cancel"));

    expect(
      screen.queryByTestId("store-settings-name-error"),
    ).not.toBeInTheDocument();
  });

  it("does not render the Cancel button when onCancel is not provided", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    expect(
      screen.queryByTestId("store-settings-cancel"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Errors
// --------------------------------------------------------------------- //

describe("StoreSettingsForm — errors", () => {
  it("shows a local error when the name is empty on submit", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "" },
    });
    fireEvent.submit(screen.getByTestId("store-settings-form"));

    expect(
      screen.getByTestId("store-settings-name-error"),
    ).toHaveTextContent(/required/i);
  });

  it("shows a local error when the timezone is empty on submit", () => {
    render(<StoreSettingsForm store={STORE} onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "" },
    });
    fireEvent.submit(screen.getByTestId("store-settings-form"));

    expect(
      screen.getByTestId("store-settings-timezone-error"),
    ).toHaveTextContent(/required/i);
  });

  it("shows a local error when name is over 150 characters", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    // The native maxLength attribute on the input would normally clip
    // user typing, but fireEvent.change bypasses that and lets us
    // assert the validation guard.
    fireEvent.change(screen.getByTestId("store-settings-name"), {
      target: { value: "x".repeat(151) },
    });
    fireEvent.submit(screen.getByTestId("store-settings-form"));

    expect(
      screen.getByTestId("store-settings-name-error"),
    ).toHaveTextContent(/150/);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows a local error when timezone is over 50 characters", () => {
    const onSubmit = vi.fn();
    render(<StoreSettingsForm store={STORE} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByTestId("store-settings-timezone"), {
      target: { value: "x".repeat(51) },
    });
    fireEvent.submit(screen.getByTestId("store-settings-form"));

    expect(
      screen.getByTestId("store-settings-timezone-error"),
    ).toHaveTextContent(/50/);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("renders an external errorMessage when provided", () => {
    render(
      <StoreSettingsForm
        store={STORE}
        onSubmit={vi.fn()}
        errorMessage="You do not have permission to access this resource"
      />,
    );

    expect(
      screen.getByTestId("store-settings-error"),
    ).toHaveTextContent(/permission/i);
  });

  it("does not render the external error block when errorMessage is null", () => {
    render(
      <StoreSettingsForm
        store={STORE}
        onSubmit={vi.fn()}
        errorMessage={null}
      />,
    );

    expect(
      screen.queryByTestId("store-settings-error"),
    ).not.toBeInTheDocument();
  });
});
