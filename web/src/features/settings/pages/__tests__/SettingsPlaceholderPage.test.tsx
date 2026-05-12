import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import SettingsPlaceholderPage from "../SettingsPlaceholderPage";

describe("SettingsPlaceholderPage", () => {
  it("renders store-aware settings placeholder copy", () => {
    render(<SettingsPlaceholderPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /store settings/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/store profile, preferences, notification defaults/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Backend Required")).toBeInTheDocument();
    expect(screen.getByText("GET /stores/:storeId")).toBeInTheDocument();
    expect(
      screen.getByText("Store notification settings endpoint"),
    ).toBeInTheDocument();
  });

  it("states settings are not simulated in the frontend", () => {
    render(<SettingsPlaceholderPage />);

    expect(screen.getByText("No fake store settings")).toBeInTheDocument();
    expect(
      screen.getByText("No frontend-only policy changes"),
    ).toBeInTheDocument();
    expect(screen.getByText("No billing simulation")).toBeInTheDocument();
  });
});
