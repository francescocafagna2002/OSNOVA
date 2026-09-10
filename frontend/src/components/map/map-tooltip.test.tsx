import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MapTooltip, TOOLTIP_FLIP_MARGIN } from "@/components/map/map-tooltip";

describe("MapTooltip", () => {
  it("renders nothing without a hovered PLZ", () => {
    render(<MapTooltip plz={null} count={0} x={10} y={10} containerWidth={800} />);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("sits to the right of the cursor when there is room", () => {
    render(<MapTooltip plz="5000" count={2} x={100} y={40} containerWidth={800} />);
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveAttribute("data-align", "right");
    expect(tip).toHaveStyle({ left: "112px", top: "52px" });
    expect(tip).toHaveTextContent("5000 Aarau · 2 buildings");
  });

  it("flips to the left of the cursor near the right edge so it never leaves the map", () => {
    const x = 800 - TOOLTIP_FLIP_MARGIN + 50;
    render(<MapTooltip plz="5000" count={1} x={x} y={40} containerWidth={800} />);
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveAttribute("data-align", "left");
    expect(tip).toHaveStyle({ right: `${800 - x + 12}px` });
  });

  it("falls back to right placement when the container width is unknown", () => {
    render(<MapTooltip plz="5000" count={1} x={790} y={40} />);
    expect(screen.getByRole("tooltip")).toHaveAttribute("data-align", "right");
  });
});
