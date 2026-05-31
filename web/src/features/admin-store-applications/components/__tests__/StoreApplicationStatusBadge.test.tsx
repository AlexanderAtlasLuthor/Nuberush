// F2.24.C7: tests for StoreApplicationStatusBadge.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { StoreApplicationStatusBadge } from "../StoreApplicationStatusBadge";
import type { StoreApplicationStatus } from "../../types";

const CASES: ReadonlyArray<[StoreApplicationStatus, string]> = [
  ["draft", "Draft"],
  ["submitted", "Submitted"],
  ["pending_review", "Pending review"],
  ["approved", "Approved"],
  ["rejected", "Rejected"],
];

describe("StoreApplicationStatusBadge", () => {
  it.each(CASES)("renders a readable label for %s", (status, label) => {
    render(<StoreApplicationStatusBadge status={status} />);
    const badge = screen.getByTestId(`application-status-${status}`);
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(label);
  });
});
