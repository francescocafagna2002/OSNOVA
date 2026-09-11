import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BuildingDetailSheet } from "@/components/detail/building-detail-sheet";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/api", () => ({ fetchBuildings: async () => [makeBuilding({ id: "AG-004711" })] }));

describe("BuildingDetailSheet", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("stays closed with no selection", () => {
    renderWithProviders(<BuildingDetailSheet />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows the building, four labelled predictions, the chart and the explanation", async () => {
    useUIStore.getState().selectBuilding("AG-004711");
    renderWithProviders(<BuildingDetailSheet />);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Building AG-004711")).toBeInTheDocument();
    expect(screen.getByText("5000 Aarau, AG")).toBeInTheDocument();
    expect(screen.getByTestId("prediction-card-pv")).toHaveTextContent("92%");
    expect(screen.getByTestId("prediction-card-pv")).toHaveTextContent("Likely");
    expect(screen.getByTestId("prediction-card-battery")).toHaveTextContent("Unlikely");
    expect(screen.getByTestId("prediction-card-heatPump")).toHaveTextContent("Unlikely");
    expect(screen.getByTestId("prediction-card-ev")).toHaveTextContent("Possible");
    expect(screen.getByTestId("electricity-chart")).toHaveAttribute("data-events", "2");
    expect(screen.getByText("Electricity profile — Last 24 hours")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show technical prediction details/ })).toBeInTheDocument();
  });

  it("closes via the close control but keeps the selection", async () => {
    useUIStore.getState().selectBuilding("AG-004711");
    renderWithProviders(<BuildingDetailSheet />);
    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => expect(useUIStore.getState().isDetailOpen).toBe(false));
    expect(useUIStore.getState().selectedBuildingId).toBe("AG-004711");
  });
});
