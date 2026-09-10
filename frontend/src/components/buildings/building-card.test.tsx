import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BuildingCard } from "@/components/buildings/building-card";
import { makeBuilding } from "@/test/fixtures";

describe("BuildingCard", () => {
  it("shows the id, area and four chips in asset order with probability titles", () => {
    render(<BuildingCard building={makeBuilding()} selected={false} onSelect={() => {}} />);
    expect(screen.getByText("Building AG-000001")).toBeInTheDocument();
    expect(screen.getByText("5000 Aarau")).toBeInTheDocument();
    expect(screen.getByTitle("PV — 92% likely")).toHaveTextContent("92%");
    expect(screen.getByTitle("Battery — 48% unlikely")).toHaveTextContent("48%");
    expect(screen.getByTitle("Heat pump — 31% unlikely")).toHaveTextContent("31%");
    expect(screen.getByTitle("EV — 76% possible")).toHaveTextContent("76%");
    const chips = screen.getAllByTitle(/—/).map((el) => el.getAttribute("title"));
    expect(chips.map((t) => t?.split(" — ")[0])).toEqual(["PV", "Battery", "Heat pump", "EV"]);
  });

  it("exposes pressed state and calls onSelect with the id", async () => {
    const onSelect = vi.fn();
    render(<BuildingCard building={makeBuilding()} selected onSelect={onSelect} />);
    const button = screen.getByRole("button", { pressed: true });
    expect(button).toHaveAttribute("id", "building-card-AG-000001");
    await userEvent.click(button);
    expect(onSelect).toHaveBeenCalledWith("AG-000001");
  });
});
