import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { AboutDialog } from "@/components/header/about-dialog";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { renderWithProviders } from "@/test/render";

describe("AboutDialog", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("renders nothing while closed and the challenge copy when open", async () => {
    renderWithProviders(<AboutDialog />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    useUIStore.getState().setAboutOpen(true);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Predictions are probabilities, not facts/)).toBeInTheDocument();
  });
});
