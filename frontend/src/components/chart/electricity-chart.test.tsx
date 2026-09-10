import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ElectricityChart } from "@/components/chart/electricity-chart";
import { makeBuilding } from "@/test/fixtures";

vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: { series: Array<{ markArea: { data: unknown[] } }> } }) => (
    <div data-testid="echarts" data-bands={option.series[0].markArea.data.length} />
  ),
}));

describe("ElectricityChart", () => {
  it("renders the chart with bands and a legend for each event type present", () => {
    const building = makeBuilding();
    render(<ElectricityChart electricity={building.electricity} events={building.events} />);
    expect(screen.getByTestId("electricity-chart")).toHaveAttribute("data-events", "2");
    expect(screen.getByTestId("echarts")).toHaveAttribute("data-bands", "3");
    const legend = screen.getByRole("list", { name: "Chart legend" });
    expect(legend).toHaveTextContent("Net power");
    expect(legend).toHaveTextContent("EV charging");
    expect(legend).toHaveTextContent("Possible PV generation");
    expect(legend).not.toHaveTextContent("High consumption");
  });
});
