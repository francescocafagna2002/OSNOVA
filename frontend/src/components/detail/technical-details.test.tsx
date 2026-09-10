import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { formatContribution, TechnicalDetails } from "@/components/detail/technical-details";
import { makeBuilding } from "@/test/fixtures";

describe("formatContribution", () => {
  it("prints a sign and two decimals", () => {
    expect(formatContribution(0.31)).toBe("+0.31");
    expect(formatContribution(-0.04)).toBe("−0.04");
    expect(formatContribution(0)).toBe("+0.00");
  });
});

describe("TechnicalDetails", () => {
  it("is collapsed by default and reveals model metadata and per-asset SHAP lists", async () => {
    const building = makeBuilding();
    render(<TechnicalDetails explanation={building.explanation} predictions={building.predictions} />);
    expect(screen.queryByText("Test model")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show technical details/ }));
    expect(await screen.findByText("Test model")).toBeInTheDocument();
    expect(screen.getByText("15-minute electricity measurements")).toBeInTheDocument();
    expect(screen.getByText(/SHAP shows which features/)).toBeInTheDocument();
    expect(screen.getByText("EV prediction: 76%")).toBeInTheDocument();
    expect(screen.getAllByText("+0.30")).toHaveLength(4);
    expect(screen.getAllByText("−0.04")).toHaveLength(4);
  });
});
