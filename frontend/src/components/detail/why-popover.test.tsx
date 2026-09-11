import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { topContributions, WhyPopover } from "@/components/detail/why-popover";
import { makeBuilding } from "@/test/fixtures";

describe("topContributions", () => {
  it("keeps only positive contributions, largest first, capped at three", () => {
    const shap = [
      { feature: "a", contribution: 0.1 },
      { feature: "b", contribution: -0.2 },
      { feature: "c", contribution: 0.4 },
      { feature: "d", contribution: 0.3 },
      { feature: "e", contribution: 0.2 },
    ];
    expect(topContributions(shap).map((s) => s.feature)).toEqual(["c", "d", "e"]);
  });
});

describe("WhyPopover", () => {
  it("opens with a probability-phrased title, reasons and SHAP bars", async () => {
    const building = makeBuilding();
    render(<WhyPopover assetKey="ev" probability={76} explanation={building.explanation.assets.ev} />);
    await userEvent.click(screen.getByRole("button", { name: "View insights for EV" }));
    expect(await screen.findByText("Why EV is possible")).toBeInTheDocument();
    expect(screen.getByText("Repeated high-power events")).toBeInTheDocument();
    expect(screen.getByText("High nighttime power peak")).toBeInTheDocument();
    expect(screen.getByText("+0.30")).toBeInTheDocument();
    expect(screen.queryByText("Counter feature")).not.toBeInTheDocument();
  });
});
