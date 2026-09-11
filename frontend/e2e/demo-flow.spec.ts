import { expect, test } from "@playwright/test";

test.describe("Energy Fingerprints demo flow (spec §11)", () => {
  test("map → area → building → predictions → fingerprint → explanation", async ({ page }) => {
    await page.goto("/");

    // 1. Shell, map and canton-wide list
    await expect(page.getByText("Energy Fingerprints")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Buildings in Aargau" })).toBeVisible();
    await expect(page.getByText("120 buildings")).toBeVisible();
    await expect(page.getByTestId("map-view")).toBeVisible();

    // 2. Narrow the list to Aarau via search (map clicks are covered by unit tests)
    await page.getByRole("searchbox", { name: "Search buildings" }).fill("AG-004711");
    const card = page.getByRole("button", { name: /Building AG-004711/ });
    await expect(card).toBeVisible();

    // 3. Select the demo building → sheet with four labelled predictions
    await card.click();
    // Named, because the "View insights" popover is a dialog too and can outlive its own close
    // transition long enough to make a bare `getByRole("dialog")` ambiguous below.
    const sheet = page.getByRole("dialog", { name: /Building AG-004711/ });
    await expect(sheet).toBeVisible();
    await expect(sheet.getByText("Building AG-004711")).toBeVisible();
    await expect(sheet.getByText("5000 Aarau, AG")).toBeVisible();
    await expect(sheet.getByTestId("prediction-card-pv")).toContainText("92%");
    await expect(sheet.getByTestId("prediction-card-pv")).toContainText("Likely");
    await expect(sheet.getByTestId("prediction-card-battery")).toContainText("48%");
    await expect(sheet.getByTestId("prediction-card-battery")).toContainText("Unlikely");
    await expect(sheet.getByTestId("prediction-card-heatPump")).toContainText("31%");
    await expect(sheet.getByTestId("prediction-card-heatPump")).toContainText("Unlikely");
    await expect(sheet.getByTestId("prediction-card-ev")).toContainText("76%");
    await expect(sheet.getByTestId("prediction-card-ev")).toContainText("Possible");
    // The dialog marks the rest of the page inert, so `card` drops out of the
    // accessibility tree while the sheet is open; query the DOM node directly.
    await expect(page.locator("#building-card-AG-004711")).toHaveAttribute("aria-pressed", "true");

    // 4. Fingerprint chart with both band labels rendered by ECharts (SVG renderer)
    const chart = sheet.getByTestId("electricity-chart");
    await expect(chart.locator("svg")).toBeVisible();
    await expect(chart.getByText("EV charging").first()).toBeVisible();
    await expect(chart.getByText("Possible PV generation").first()).toBeVisible();

    // 5. "View insights" popover for EV
    await sheet.getByRole("button", { name: "View insights for EV" }).click();
    await expect(page.getByText("Why EV is possible")).toBeVisible();
    await expect(page.getByText("Repeated high-power events")).toBeVisible();
    await page.keyboard.press("Escape");

    // 6. Technical details
    await sheet.getByRole("button", { name: /Show technical prediction details/ }).click();
    await expect(sheet.getByText("EV prediction: 76%")).toBeVisible();
    await expect(sheet.getByText("Very high power draw during the night")).toBeVisible();

    // 7. Close and return to the full list
    await sheet.getByRole("button", { name: /close/i }).click();
    await expect(sheet).toBeHidden();
    await page.getByRole("searchbox", { name: "Search buildings" }).fill("");
    await expect(page.getByText("120 buildings")).toBeVisible();
  });

  test("view toggle switches to a full-width list and back", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "List" }).click();
    await expect(page.getByTestId("map-view")).toBeHidden();
    await expect(page.getByTestId("list-panel")).toHaveAttribute("data-mode", "list");
    await page.getByRole("button", { name: "Map" }).click();
    await expect(page.getByTestId("map-view")).toBeVisible();
  });
});
