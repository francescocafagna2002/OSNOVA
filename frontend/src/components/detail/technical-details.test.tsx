import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TechnicalDetails } from "@/components/detail/technical-details";
import { makeBuilding } from "@/test/fixtures";

describe("TechnicalDetails", () => {
  it("is collapsed by default and reveals model metadata and per-asset signal lists", async () => {
    const building = makeBuilding();
    render(<TechnicalDetails explanation={building.explanation} predictions={building.predictions} />);
    expect(screen.queryByText("Test model")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show technical prediction details/ }));
    expect(await screen.findByText("Test model")).toBeInTheDocument();
    expect(screen.getByText("15-minute electricity measurements")).toBeInTheDocument();
    expect(screen.getByText(/SHAP shows which features/)).toBeInTheDocument();
    expect(screen.getByText("EV prediction: 76%")).toBeInTheDocument();
    expect(screen.queryByText("+0.30")).not.toBeInTheDocument();
    expect(screen.queryByText("−0.04")).not.toBeInTheDocument();
  });

  it("reads PV, heat pump, battery, EV in that order with a plain-language summary each", async () => {
    const building = makeBuilding();
    render(<TechnicalDetails explanation={building.explanation} predictions={building.predictions} />);
    await userEvent.click(screen.getByRole("button", { name: /Show technical prediction details/ }));
    const headings = (await screen.findAllByText(/prediction: \d+%/)).map((el) => el.textContent);
    expect(headings).toEqual([
      "PV prediction: 92%",
      "Heat pump prediction: 31%",
      "Battery prediction: 48%",
      "EV prediction: 76%",
    ]);
    const pv = screen.getByTestId("technical-pv");
    expect(within(pv).getByText("Likely")).toBeInTheDocument();
    expect(within(pv).getByText(/solar panels on the roof are producing power/)).toBeInTheDocument();
    // Known model features get everyday wording, with the raw name kept underneath.
    expect(within(pv).getByText("Uses less electricity from the grid around midday")).toBeInTheDocument();
    expect(within(pv).getByText("Midday net-load dip")).toBeInTheDocument();
    // Unknown features fall back to their raw name.
    expect(within(pv).getByText("Secondary feature")).toBeInTheDocument();
  });
});
