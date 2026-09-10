# Energy Fingerprints Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the single-screen Energy Fingerprints demo: Aargau PLZ area map, ID-based building list, detail sheet with four predictions, 24h ECharts fingerprint with event bands, plain-language and SHAP explanations, on deterministic mock data.

**Architecture:** One route. A client `AppShell` lays out header, map, list, and sheet; every interactive piece reads a Zustand UI store and TanStack Query hooks directly, so the five UI areas are independent. Pure domain logic (labels, search, chart option, PLZ lookup, mock generator) lives in `src/lib` and is unit-tested. Wave 0 freezes the contract; Wave 1 builds the five UI areas in parallel worktrees; Wave 2 integrates, runs the e2e demo flow, reviews, and cleans up.

**Tech Stack:** Next.js 16.3 (App Router, Turbopack), React 19.2, TypeScript 5, Tailwind v4, shadcn base-nova (`@base-ui/react`), `react-map-gl` 8 (`/maplibre`) + `maplibre-gl` 6, `echarts` 6 + `echarts-for-react` 3, TanStack Query 5, Zustand 5, lucide-react. Tests: Vitest + jsdom + Testing Library, Playwright.

**Spec:** [`docs/superpowers/specs/2026-09-10-energy-fingerprints-frontend-design.md`](../specs/2026-09-10-energy-fingerprints-frontend-design.md). Read it first; it is the binding authority. The task doc it adapts is `frontend/docs/energy-fingerprints-task.md`.

## Global Constraints

- All paths below are relative to `frontend/` unless they start with `docs/` or are the root `.gitignore`.
- Run every `npm` command from `frontend/`.
- Node ≥ 20. Never change versions of existing dependencies. Add no runtime dependencies; only the dev dependencies named in Task 1.
- Server Components by default; add `"use client"` only to files that use hooks, browser APIs, the store, or third-party client libraries.
- Server data → TanStack Query. Ephemeral UI state → Zustand `src/stores/ui-store.ts`. Never store derived data.
- Prediction thresholds: `likely: 80`, `possible: 50` (inclusive lower bounds). Asset order everywhere: PV, Battery, Heat pump, EV. Asset colours: PV `#d97706`, Battery `#16a34a`, Heat pump `#ea580c`, EV `#2563eb`.
- Copy rule: never state a prediction as fact. Use "likely / possible / unlikely" and "% likely".
- Basemap: `process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron"`.
- Mock data: seed 42, 120 buildings, day `2026-09-09T00:00:00+02:00`, 96 points at 15 min, demo building `AG-004711` in `5000` Aarau with PV 92 / Battery 48 / Heat pump 31 / EV 76.
- Chart x axis: minutes since series start, 0..1440, ticks every 240, labels `00 04 08 12 16 20 24`.
- Wave 1 file ownership (spec §4) is binding: never create or edit a file outside your task's `Files` list. Shared files (`package.json`, `globals.css`, `page.tsx`, `ui-store.ts`, `types.ts`) are Wave 0 / Wave 2 only.
- After each task's final commit, push: `git push -u origin HEAD`.
- Definition of done for every task: `npm run check` green (lint + typecheck + unit tests); no `console.log`; no `any`; no `// TODO`; no unused exports; commits in `type: summary` style ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Before using any shadcn component, read its generated file in `src/components/ui/` — the base-nova style wraps `@base-ui/react`, and prop names differ from older shadcn (e.g. `Select` takes `items`, `onOpenChange(open, details)`).

---

## Orchestration runbook (for the controller session)

**Branches and worktrees.** Integration branch: `feat/frontend-energy-map`, checked out at `../OSNOVA-frontend-demo` (a sibling of the main checkout). Wave 0 and Wave 2 run there. Wave 1 agents get their own worktree each (`Agent` tool with `isolation: "worktree"`, or `git worktree add ../OSNOVA-ef-<area> -b feat/ef-<area> feat/frontend-energy-map`), run `npm ci` in `frontend/`, and commit on their branch. Worktrees have no `node_modules`; `npm ci` takes 1–2 minutes each.

**Waves.**

| Wave | Tasks | Mode | Model guidance |
| --- | --- | --- | --- |
| 0 | 1 → 2 → 3 → 4 | Sequential on the integration branch, one implementer per task, task review after each | Task 1 sonnet (tooling judgment); Tasks 2–4 sonnet (code is fully specified but touches many files) |
| 1 | 5, 6, 7, 8, 9 | **Parallel**, five implementers dispatched in one message, each in its own worktree and branch | Task 6 (map) opus; Tasks 5, 7, 8, 9 sonnet |
| 2 | 10 → 11 → 12 | Sequential on the integration branch | Task 10 opus (integration and merge judgment); Task 11 sonnet; Task 12 = SDD final review on opus |

**Per-task loop.** Follow superpowers:subagent-driven-development exactly: brief file → implementer → report → review package → task reviewer → fix loop (max 5) → ledger. For Wave 1, run the five implementers concurrently, then review each branch separately (`review-package` over `feat/frontend-energy-map..feat/ef-<area>`), then hand all five branch names to Task 10.

**Dispatch brief must contain**, besides the task text: the spec path; the Global Constraints above; the branch/worktree to use; "run `npm ci` first"; "verify with `npm run check` before reporting"; the report path. Wave 1 briefs add: "you own only the files in your task; if you believe you need a change elsewhere, write it in your report as a request for Task 10 instead of making it".

**Pre-flight (human, once).** Approve the dev-dependency install in Task 1. Run `npx playwright install chromium` in `frontend/` before Wave 2 (browser download). Confirm the demo machine has internet for basemap tiles.

**Cleanup at the end (Task 12).** Delete `src/app/dev/`; delete `feat/ef-*` branches and their worktrees; delete the plan's `.superpowers/sdd/<plan>/` workspace; confirm `git status` clean on the integration branch; open the PR to `main`.

---

## Wave 0 — Foundation (sequential, integration branch)

### Task 1: Test tooling, scripts, shadcn components, ignore rules

**Files:**
- Modify: `package.json` (scripts + devDependencies)
- Create: `vitest.config.ts`, `playwright.config.ts`, `src/test/setup.ts`, `src/test/render.tsx`, `src/lib/utils.test.ts`, `e2e/.gitkeep`
- Create (generated): `src/components/ui/{sheet,dialog,popover,collapsible,input,select,scroll-area,separator}.tsx`
- Modify: root `.gitignore`

**Interfaces:**
- Produces: `npm run typecheck`, `npm run test`, `npm run test:e2e`, `npm run check`; `renderWithProviders(ui)` from `@/test/render`; jsdom polyfills for `ResizeObserver`, `matchMedia`, `scrollIntoView`.

- [ ] **Step 1: Install dev dependencies**

```bash
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @playwright/test
```

- [ ] **Step 2: Add scripts to `package.json`**

Replace the `scripts` block with:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "eslint",
  "typecheck": "next typegen && tsc --noEmit",
  "test": "vitest run",
  "test:watch": "vitest",
  "test:e2e": "playwright test",
  "check": "npm run lint && npm run typecheck && npm run test"
}
```

- [ ] **Step 3: Create `vitest.config.ts`**

```ts
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
```

- [ ] **Step 4: Create `src/test/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!("ResizeObserver" in globalThis)) {
  Object.defineProperty(globalThis, "ResizeObserver", {
    value: ResizeObserverStub,
    writable: true,
  });
}

if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}
```

- [ ] **Step 5: Create `src/test/render.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
}

/** Renders `ui` inside a fresh QueryClientProvider. Returns the client for cache seeding. */
export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const client = createTestQueryClient();
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return { client, ...render(ui, { wrapper: Wrapper, ...options }) };
}
```

- [ ] **Step 6: Write the sanity test `src/lib/utils.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("merges conditional class names", () => {
    expect(cn("a", false && "b", "c")).toBe("a c");
  });
});
```

- [ ] **Step 7: Create `playwright.config.ts` and `e2e/.gitkeep`**

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
```

`e2e/.gitkeep` is an empty file.

- [ ] **Step 8: Add the shadcn components**

```bash
npx shadcn@latest add sheet dialog popover collapsible input select scroll-area separator -y
```

Verify the eight files exist in `src/components/ui/`. Do not edit them. If the CLI rewrote `src/app/globals.css`, review the diff and keep only additions it made for these components (there should be none).

- [ ] **Step 9: Append to the root `.gitignore`**

```gitignore

# ─── Agent scratch and worktrees ─────────────────────────────────────────────
.claude/worktrees/
.superpowers/

# ─── Playwright ──────────────────────────────────────────────────────────────
frontend/test-results/
frontend/playwright-report/
```

- [ ] **Step 10: Run the full check**

Run: `npm run check`
Expected: lint clean, `next typegen` + `tsc` clean, `1 passed` from Vitest.

- [ ] **Step 11: Commit**

```bash
git add package.json package-lock.json vitest.config.ts playwright.config.ts src/test src/lib/utils.test.ts e2e/.gitkeep src/components/ui ../.gitignore
git commit -m "chore(frontend): add vitest, playwright, check script and shadcn components

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Data contract, prediction logic, event metadata, PLZ areas

**Files:**
- Create: `src/lib/types.ts`, `src/lib/predictions.ts`, `src/lib/events.ts`, `src/lib/plz.ts`
- Test: `src/lib/predictions.test.ts`, `src/lib/plz.test.ts`
- Uses (already committed): `src/data/aargau-plz.json`

**Interfaces:**
- Consumes: nothing.
- Produces: every type in spec §5; `PREDICTION_THRESHOLDS`, `getPredictionLabel`, `formatProbability`, `ASSETS`, `ASSET_BY_KEY`, `getMarkerAssets`, `describePrediction`; `EVENT_META`, `EVENT_BAND_OPACITY`; `PLZ_AREAS`, `PLZ_BY_CODE`, `AARGAU_BBOX`, `getPlzArea`, `countBuildingsByPlz`, `buildPlzGeoJson`, `formatPlz`.

- [ ] **Step 1: Create `src/lib/types.ts`**

Copy the contract from spec §5 verbatim (the `ASSET_KEYS` … `Building` block).

- [ ] **Step 2: Write the failing tests `src/lib/predictions.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import {
  ASSETS,
  describePrediction,
  formatProbability,
  getMarkerAssets,
  getPredictionLabel,
} from "@/lib/predictions";

describe("getPredictionLabel", () => {
  it.each([
    [100, "Likely"],
    [80, "Likely"],
    [79.9, "Possible"],
    [50, "Possible"],
    [49, "Unlikely"],
    [0, "Unlikely"],
  ])("maps %s to %s", (probability, label) => {
    expect(getPredictionLabel(probability)).toBe(label);
  });

  it("clamps out-of-range and NaN input", () => {
    expect(getPredictionLabel(150)).toBe("Likely");
    expect(getPredictionLabel(-5)).toBe("Unlikely");
    expect(getPredictionLabel(Number.NaN)).toBe("Unlikely");
  });
});

describe("formatProbability", () => {
  it("rounds and appends a percent sign", () => {
    expect(formatProbability(76.4)).toBe("76%");
    expect(formatProbability(120)).toBe("100%");
  });
});

describe("ASSETS", () => {
  it("keeps the fixed order PV, Battery, Heat pump, EV", () => {
    expect(ASSETS.map((a) => a.key)).toEqual(["pv", "battery", "heatPump", "ev"]);
  });
});

describe("getMarkerAssets", () => {
  it("returns only Likely assets, highest first, capped at two", () => {
    expect(getMarkerAssets({ pv: 92, battery: 85, heatPump: 31, ev: 96 })).toEqual(["ev", "pv"]);
  });

  it("returns an empty list when nothing is Likely", () => {
    expect(getMarkerAssets({ pv: 79, battery: 10, heatPump: 50, ev: 0 })).toEqual([]);
  });
});

describe("describePrediction", () => {
  it("phrases predictions as probabilities, never as facts", () => {
    const text = describePrediction("ev", 76);
    expect(text).toBe("EV — 76% possible");
    expect(text.toLowerCase()).not.toContain("has");
  });
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npx vitest run src/lib/predictions.test.ts`
Expected: FAIL, cannot resolve `@/lib/predictions`.

- [ ] **Step 4: Create `src/lib/predictions.ts`**

```ts
import { BatteryCharging, Car, Flame, Sun, type LucideIcon } from "lucide-react";

import type { AssetKey, AssetPrediction } from "@/lib/types";

/** Tune during the hackathon; every label in the UI derives from these. Inclusive lower bounds. */
export const PREDICTION_THRESHOLDS = { likely: 80, possible: 50 } as const;

export type PredictionLabel = "Likely" | "Possible" | "Unlikely";

function clampProbability(probability: number): number {
  if (Number.isNaN(probability)) return 0;
  return Math.min(100, Math.max(0, probability));
}

export function getPredictionLabel(probability: number): PredictionLabel {
  const p = clampProbability(probability);
  if (p >= PREDICTION_THRESHOLDS.likely) return "Likely";
  if (p >= PREDICTION_THRESHOLDS.possible) return "Possible";
  return "Unlikely";
}

export function formatProbability(probability: number): string {
  return `${Math.round(clampProbability(probability))}%`;
}

export type AssetMeta = {
  key: AssetKey;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  color: string;
};

/** Fixed display order: PV, Battery, Heat pump, EV. */
export const ASSETS: readonly AssetMeta[] = [
  { key: "pv", label: "PV / Solar", shortLabel: "PV", icon: Sun, color: "#d97706" },
  { key: "battery", label: "Battery", shortLabel: "Battery", icon: BatteryCharging, color: "#16a34a" },
  { key: "heatPump", label: "Heat pump", shortLabel: "Heat pump", icon: Flame, color: "#ea580c" },
  { key: "ev", label: "Electric vehicle", shortLabel: "EV", icon: Car, color: "#2563eb" },
];

export const ASSET_BY_KEY = Object.fromEntries(ASSETS.map((asset) => [asset.key, asset])) as Record<
  AssetKey,
  AssetMeta
>;

/** Asset keys labelled "Likely", highest probability first, at most `max`. */
export function getMarkerAssets(predictions: AssetPrediction, max = 2): AssetKey[] {
  return ASSETS.map((asset) => asset.key)
    .filter((key) => getPredictionLabel(predictions[key]) === "Likely")
    .sort((a, b) => predictions[b] - predictions[a])
    .slice(0, max);
}

/** "EV — 76% possible". Phrases the prediction as a probability, never as a fact. */
export function describePrediction(assetKey: AssetKey, probability: number): string {
  const label = getPredictionLabel(probability).toLowerCase();
  return `${ASSET_BY_KEY[assetKey].shortLabel} — ${formatProbability(probability)} ${label}`;
}
```

- [ ] **Step 5: Create `src/lib/events.ts`**

```ts
import { ASSET_BY_KEY } from "@/lib/predictions";
import type { BuildingEventType } from "@/lib/types";

export type EventMeta = { label: string; color: string };

export const EVENT_META: Record<BuildingEventType, EventMeta> = {
  ev_charging: { label: "EV charging", color: ASSET_BY_KEY.ev.color },
  pv_generation: { label: "Possible PV generation", color: ASSET_BY_KEY.pv.color },
  high_consumption: { label: "High consumption", color: "#64748b" },
};

/** Fill alpha for chart bands; keeps the consumption line the primary element. */
export const EVENT_BAND_OPACITY = 0.14;
```

- [ ] **Step 6: Run the prediction tests to verify they pass**

Run: `npx vitest run src/lib/predictions.test.ts`
Expected: PASS (all cases).

- [ ] **Step 7: Write the failing tests `src/lib/plz.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import {
  AARGAU_BBOX,
  buildPlzGeoJson,
  countBuildingsByPlz,
  formatPlz,
  getPlzArea,
  PLZ_AREAS,
  PLZ_BY_CODE,
} from "@/lib/plz";
import type { Building } from "@/lib/types";

describe("PLZ areas", () => {
  it("loads every Aargau PLZ polygon with a name and a bbox", () => {
    expect(PLZ_AREAS.length).toBe(239);
    const aarau = getPlzArea("5000");
    expect(aarau?.name).toBe("Aarau");
    expect(aarau?.gemeinde).toBe("Aarau");
    expect(aarau?.bbox[0]).toBeLessThan(aarau!.bbox[2]);
    expect(aarau?.bbox[1]).toBeLessThan(aarau!.bbox[3]);
    expect(PLZ_BY_CODE["5400"].name).toBe("Baden");
  });

  it("returns undefined for unknown codes", () => {
    expect(getPlzArea("9999")).toBeUndefined();
  });

  it("exposes a canton-wide bbox in lng/lat order", () => {
    const [west, south, east, north] = AARGAU_BBOX;
    expect(west).toBeGreaterThan(7.5);
    expect(east).toBeLessThan(8.6);
    expect(south).toBeGreaterThan(47.0);
    expect(north).toBeLessThan(47.7);
  });

  it("formats a code with its town name and falls back to the code", () => {
    expect(formatPlz("5000")).toBe("5000 Aarau");
    expect(formatPlz("9999")).toBe("9999");
  });
});

describe("countBuildingsByPlz / buildPlzGeoJson", () => {
  const stub = (id: string, postcode: string) => ({ id, postcode }) as Building;

  it("counts buildings per postcode", () => {
    expect(countBuildingsByPlz([stub("a", "5000"), stub("b", "5000"), stub("c", "5400")])).toEqual({
      "5000": 2,
      "5400": 1,
    });
  });

  it("adds a numeric count to every feature, zero when absent", () => {
    const geo = buildPlzGeoJson({ "5000": 2 });
    const aarau = geo.features.find((f) => f.properties.plz === "5000");
    const baden = geo.features.find((f) => f.properties.plz === "5400");
    expect(aarau?.properties.count).toBe(2);
    expect(baden?.properties.count).toBe(0);
    expect(geo.features.length).toBe(239);
  });
});
```

- [ ] **Step 8: Run the PLZ tests to verify they fail**

Run: `npx vitest run src/lib/plz.test.ts`
Expected: FAIL, cannot resolve `@/lib/plz`.

- [ ] **Step 9: Create `src/lib/plz.ts`**

```ts
import type { Feature, FeatureCollection, Polygon, Position } from "geojson";

import plzGeoJson from "@/data/aargau-plz.json";
import type { Building } from "@/lib/types";

export type PlzProperties = { plz: string; name: string; gemeinde: string };

/** west, south, east, north */
export type Bbox = [number, number, number, number];

export type PlzArea = PlzProperties & { bbox: Bbox };

type PlzFeature = Feature<Polygon, PlzProperties>;

const collection = plzGeoJson as unknown as FeatureCollection<Polygon, PlzProperties>;

function bboxOf(coordinates: Position[][]): Bbox {
  let west = Number.POSITIVE_INFINITY;
  let south = Number.POSITIVE_INFINITY;
  let east = Number.NEGATIVE_INFINITY;
  let north = Number.NEGATIVE_INFINITY;
  for (const ring of coordinates) {
    for (const [lng, lat] of ring) {
      if (lng < west) west = lng;
      if (lng > east) east = lng;
      if (lat < south) south = lat;
      if (lat > north) north = lat;
    }
  }
  return [west, south, east, north];
}

function unionBbox(boxes: Bbox[]): Bbox {
  return boxes.reduce<Bbox>(
    (acc, [w, s, e, n]) => [Math.min(acc[0], w), Math.min(acc[1], s), Math.max(acc[2], e), Math.max(acc[3], n)],
    [
      Number.POSITIVE_INFINITY,
      Number.POSITIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
    ],
  );
}

export const PLZ_AREAS: readonly PlzArea[] = collection.features.map((feature: PlzFeature) => ({
  ...feature.properties,
  bbox: bboxOf(feature.geometry.coordinates),
}));

export const PLZ_BY_CODE: Record<string, PlzArea> = Object.fromEntries(
  PLZ_AREAS.map((area) => [area.plz, area]),
);

export const AARGAU_BBOX: Bbox = unionBbox(PLZ_AREAS.map((area) => area.bbox));

export function getPlzArea(plz: string): PlzArea | undefined {
  return PLZ_BY_CODE[plz];
}

/** "5000 Aarau"; unknown codes render as the bare code. */
export function formatPlz(plz: string): string {
  const area = getPlzArea(plz);
  return area ? `${plz} ${area.name}` : plz;
}

export function countBuildingsByPlz(buildings: Building[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const building of buildings) {
    counts[building.postcode] = (counts[building.postcode] ?? 0) + 1;
  }
  return counts;
}

export type PlzCountProperties = PlzProperties & { count: number };

/** The committed polygons with a `count` per feature, ready for a MapLibre GeoJSON source. */
export function buildPlzGeoJson(counts: Record<string, number>): FeatureCollection<Polygon, PlzCountProperties> {
  return {
    type: "FeatureCollection",
    features: collection.features.map((feature) => ({
      ...feature,
      properties: { ...feature.properties, count: counts[feature.properties.plz] ?? 0 },
    })),
  };
}
```

If `import type … from "geojson"` fails to resolve, run `npm install -D @types/geojson` and note it in the report.

- [ ] **Step 10: Run the PLZ tests to verify they pass**

Run: `npx vitest run src/lib/plz.test.ts`
Expected: PASS.

- [ ] **Step 11: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/lib/types.ts src/lib/predictions.ts src/lib/predictions.test.ts src/lib/events.ts src/lib/plz.ts src/lib/plz.test.ts
git commit -m "feat(frontend): add data contract, prediction labels and PLZ area lookup

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: UI store, search filter, theme tokens

**Files:**
- Modify: `src/stores/ui-store.ts` (full rewrite), `src/app/globals.css` (`:root` block only)
- Create: `src/lib/search.ts`
- Test: `src/stores/ui-store.test.ts`, `src/lib/search.test.ts`

**Interfaces:**
- Consumes: `Building` from Task 2.
- Produces: `useUIStore`, `initialUIState`, `ViewMode` (spec §7); `filterBuildings`, `normalizeText`.

- [ ] **Step 1: Write the failing store tests `src/stores/ui-store.test.ts`**

```ts
import { beforeEach, describe, expect, it } from "vitest";

import { initialUIState, useUIStore } from "@/stores/ui-store";

describe("ui-store", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("starts with nothing selected, map view, empty search", () => {
    const s = useUIStore.getState();
    expect(s.selectedPlz).toBeNull();
    expect(s.selectedBuildingId).toBeNull();
    expect(s.isDetailOpen).toBe(false);
    expect(s.viewMode).toBe("map");
    expect(s.searchQuery).toBe("");
    expect(s.isAboutOpen).toBe(false);
  });

  it("selectBuilding sets the id and opens the detail without touching the area", () => {
    useUIStore.getState().selectPlz("5000");
    useUIStore.getState().selectBuilding("AG-004711");
    const s = useUIStore.getState();
    expect(s.selectedBuildingId).toBe("AG-004711");
    expect(s.isDetailOpen).toBe(true);
    expect(s.selectedPlz).toBe("5000");
  });

  it("selectPlz clears the building and closes the detail", () => {
    useUIStore.getState().selectBuilding("AG-004711");
    useUIStore.getState().selectPlz("5400");
    const s = useUIStore.getState();
    expect(s.selectedPlz).toBe("5400");
    expect(s.selectedBuildingId).toBeNull();
    expect(s.isDetailOpen).toBe(false);
  });

  it("closeDetail keeps the selection highlighted", () => {
    useUIStore.getState().selectBuilding("AG-004711");
    useUIStore.getState().closeDetail();
    const s = useUIStore.getState();
    expect(s.isDetailOpen).toBe(false);
    expect(s.selectedBuildingId).toBe("AG-004711");
  });

  it("clearSelection drops the building and closes the detail", () => {
    useUIStore.getState().selectBuilding("AG-004711");
    useUIStore.getState().clearSelection();
    const s = useUIStore.getState();
    expect(s.isDetailOpen).toBe(false);
    expect(s.selectedBuildingId).toBeNull();
  });

  it("setters update view mode, search and about", () => {
    useUIStore.getState().setViewMode("list");
    useUIStore.getState().setSearchQuery("aarau");
    useUIStore.getState().setAboutOpen(true);
    const s = useUIStore.getState();
    expect(s.viewMode).toBe("list");
    expect(s.searchQuery).toBe("aarau");
    expect(s.isAboutOpen).toBe(true);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/stores/ui-store.test.ts`
Expected: FAIL (`initialUIState` not exported, `selectPlz` undefined).

- [ ] **Step 3: Rewrite `src/stores/ui-store.ts`**

```ts
import { create } from "zustand";

export type ViewMode = "map" | "list";

/**
 * Ephemeral UI state only. Building data lives in TanStack Query; derived values
 * (filtered list, selected building, highlighted PLZ) live in hooks, never here.
 */
interface UIStateSlice {
  /** Area filter chosen on the map or cleared via "Show all areas". */
  selectedPlz: string | null;
  selectedBuildingId: string | null;
  isDetailOpen: boolean;
  viewMode: ViewMode;
  searchQuery: string;
  isAboutOpen: boolean;
}

interface UIActions {
  /** Sets the area filter, clears any selected building, closes the detail. */
  selectPlz: (plz: string | null) => void;
  /** Selects a building and opens the detail; leaves the area filter alone. */
  selectBuilding: (id: string) => void;
  /** Closes the detail but keeps the building highlighted. */
  closeDetail: () => void;
  clearSelection: () => void;
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setAboutOpen: (open: boolean) => void;
}

export type UIState = UIStateSlice & UIActions;

export const initialUIState: UIStateSlice = {
  selectedPlz: null,
  selectedBuildingId: null,
  isDetailOpen: false,
  viewMode: "map",
  searchQuery: "",
  isAboutOpen: false,
};

export const useUIStore = create<UIState>((set) => ({
  ...initialUIState,
  selectPlz: (plz) => set({ selectedPlz: plz, selectedBuildingId: null, isDetailOpen: false }),
  selectBuilding: (id) => set({ selectedBuildingId: id, isDetailOpen: true }),
  closeDetail: () => set({ isDetailOpen: false }),
  clearSelection: () => set({ selectedBuildingId: null, isDetailOpen: false }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setAboutOpen: (open) => set({ isAboutOpen: open }),
}));
```

- [ ] **Step 4: Run the store tests to verify they pass**

Run: `npx vitest run src/stores/ui-store.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing search tests `src/lib/search.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { filterBuildings, normalizeText } from "@/lib/search";
import type { Building } from "@/lib/types";

const stub = (id: string, postcode: string, city: string) => ({ id, postcode, city }) as Building;

const buildings = [
  stub("AG-004711", "5000", "Aarau"),
  stub("AG-000002", "5400", "Baden"),
  stub("AG-000003", "8967", "Widen"),
  stub("AG-000004", "5610", "Wohlen AG"),
];

describe("normalizeText", () => {
  it("lowercases, strips diacritics and collapses whitespace", () => {
    expect(normalizeText("  Zürcher   Straße ")).toBe("zurcher straße");
    expect(normalizeText("Möhlin")).toBe("mohlin");
  });
});

describe("filterBuildings", () => {
  it("returns the same array for an empty query", () => {
    expect(filterBuildings(buildings, "   ")).toBe(buildings);
  });

  it("matches by id, postcode or town, case-insensitively", () => {
    expect(filterBuildings(buildings, "ag-004711").map((b) => b.id)).toEqual(["AG-004711"]);
    expect(filterBuildings(buildings, "54").map((b) => b.id)).toEqual(["AG-000002"]);
    expect(filterBuildings(buildings, "WOHLEN").map((b) => b.id)).toEqual(["AG-000004"]);
  });

  it("requires every token to match", () => {
    expect(filterBuildings(buildings, "5000 baden")).toEqual([]);
    expect(filterBuildings(buildings, "5000 aarau").map((b) => b.id)).toEqual(["AG-004711"]);
  });
});
```

- [ ] **Step 6: Run to verify failure, then create `src/lib/search.ts`**

Run: `npx vitest run src/lib/search.test.ts` → FAIL (module missing).

```ts
import type { Building } from "@/lib/types";

/** Lowercase, strip combining diacritics, collapse whitespace. */
export function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** Every whitespace-separated token must appear in "id postcode city". Empty query → input unchanged. */
export function filterBuildings(buildings: Building[], query: string): Building[] {
  const tokens = normalizeText(query).split(" ").filter(Boolean);
  if (tokens.length === 0) return buildings;
  return buildings.filter((building) => {
    const haystack = normalizeText(`${building.id} ${building.postcode} ${building.city}`);
    return tokens.every((token) => haystack.includes(token));
  });
}
```

Run: `npx vitest run src/lib/search.test.ts` → PASS.

- [ ] **Step 7: Replace the `:root` block in `src/app/globals.css`**

Keep everything else (imports, `@theme inline`, `.dark`, `@layer base`) unchanged. Replace only the `:root { … }` block with:

```css
:root {
  --background: oklch(0.99 0.002 250);
  --foreground: oklch(0.27 0.05 262);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.27 0.05 262);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.27 0.05 262);
  --primary: oklch(0.5 0.17 252);
  --primary-foreground: oklch(0.99 0 0);
  --secondary: oklch(0.96 0.01 250);
  --secondary-foreground: oklch(0.27 0.05 262);
  --muted: oklch(0.96 0.01 250);
  --muted-foreground: oklch(0.52 0.03 258);
  --accent: oklch(0.94 0.04 160);
  --accent-foreground: oklch(0.35 0.09 160);
  --destructive: oklch(0.577 0.245 27.325);
  --border: oklch(0.91 0.01 250);
  --input: oklch(0.91 0.01 250);
  --ring: oklch(0.6 0.15 252);
  --chart-1: #d97706;
  --chart-2: #16a34a;
  --chart-3: #ea580c;
  --chart-4: #2563eb;
  --chart-5: oklch(0.52 0.03 258);
  --radius: 0.625rem;
  --sidebar: oklch(0.985 0.003 250);
  --sidebar-foreground: oklch(0.27 0.05 262);
  --sidebar-primary: oklch(0.5 0.17 252);
  --sidebar-primary-foreground: oklch(0.99 0 0);
  --sidebar-accent: oklch(0.96 0.01 250);
  --sidebar-accent-foreground: oklch(0.27 0.05 262);
  --sidebar-border: oklch(0.91 0.01 250);
  --sidebar-ring: oklch(0.6 0.15 252);
}
```

- [ ] **Step 8: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/stores/ui-store.ts src/stores/ui-store.test.ts src/lib/search.ts src/lib/search.test.ts src/app/globals.css
git commit -m "feat(frontend): add UI store, search filter and theme tokens

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Seeded mock data, API swap point, query hooks, fixtures, chart stub

**Files:**
- Create: `src/lib/random.ts`, `src/lib/mock-data.ts`, `src/lib/api.ts`, `src/hooks/use-buildings.ts`, `src/test/fixtures.ts`, `src/components/chart/electricity-chart.tsx`
- Test: `src/lib/random.test.ts`, `src/lib/mock-data.test.ts`, `src/hooks/use-buildings.test.tsx`

**Interfaces:**
- Consumes: Task 2 types, `PLZ_BY_CODE`, `ASSET_KEYS`; Task 3 `useUIStore`, `filterBuildings`.
- Produces: `createRng(seed)`; `generateMockBuildings`, `DEMO_BUILDING_ID`, `MOCK_PLZ_POOL`, `MOCK_DAY_START`; `fetchBuildings`; `useBuildings`, `useFilteredBuildings`, `useSelectedBuilding`, `usePlzCounts`, `useHighlightedPlz`; `makeBuilding(overrides)`; `ElectricityChart` props `{ electricity, events, className? }` (stub; Task 9 replaces the body, not the signature).

- [ ] **Step 1: Write the failing PRNG test `src/lib/random.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { createRng } from "@/lib/random";

describe("createRng", () => {
  it("is deterministic for a seed and uniform in [0, 1)", () => {
    const a = createRng(42);
    const b = createRng(42);
    const seqA = Array.from({ length: 5 }, () => a.next());
    const seqB = Array.from({ length: 5 }, () => b.next());
    expect(seqA).toEqual(seqB);
    for (const v of seqA) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it("int is inclusive on both ends and pick returns members", () => {
    const rng = createRng(7);
    const values = new Set(Array.from({ length: 200 }, () => rng.int(1, 3)));
    expect([...values].sort()).toEqual([1, 2, 3]);
    expect(["a", "b"]).toContain(rng.pick(["a", "b"]));
  });
});
```

- [ ] **Step 2: Create `src/lib/random.ts`**

```ts
export type Rng = {
  /** Uniform in [0, 1). */
  next: () => number;
  between: (min: number, max: number) => number;
  /** Integer in [min, max], inclusive. */
  int: (min: number, max: number) => number;
  pick: <T>(items: readonly T[]) => T;
  chance: (probability: number) => boolean;
};

/** mulberry32 — small, fast, deterministic. Good enough for mock data. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function createRng(seed: number): Rng {
  const next = mulberry32(seed);
  return {
    next,
    between: (min, max) => min + (max - min) * next(),
    int: (min, max) => Math.floor(min + (max - min + 1) * next()),
    pick: (items) => items[Math.floor(next() * items.length)],
    chance: (probability) => next() < probability,
  };
}
```

Run: `npx vitest run src/lib/random.test.ts` → PASS.

- [ ] **Step 3: Write the failing mock-data tests `src/lib/mock-data.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import {
  DEMO_BUILDING_ID,
  generateMockBuildings,
  MOCK_BUILDING_COUNT,
  MOCK_PLZ_POOL,
} from "@/lib/mock-data";
import { getPlzArea } from "@/lib/plz";
import { ASSET_KEYS } from "@/lib/types";

describe("generateMockBuildings", () => {
  const buildings = generateMockBuildings();

  it("is deterministic and has the configured size with unique ids", () => {
    expect(buildings).toEqual(generateMockBuildings());
    expect(buildings.length).toBe(MOCK_BUILDING_COUNT);
    expect(new Set(buildings.map((b) => b.id)).size).toBe(MOCK_BUILDING_COUNT);
  });

  it("puts the hand-authored demo building first", () => {
    const demo = buildings[0];
    expect(demo.id).toBe(DEMO_BUILDING_ID);
    expect(demo.postcode).toBe("5000");
    expect(demo.city).toBe("Aarau");
    expect(demo.canton).toBe("AG");
    expect(demo.predictions).toEqual({ pv: 92, battery: 48, heatPump: 31, ev: 76 });
    expect(demo.events).toEqual([
      { type: "ev_charging", start: "2026-09-09T22:15:00+02:00", end: "2026-09-10T01:30:00+02:00", confidence: 0.9 },
      { type: "pv_generation", start: "2026-09-09T10:00:00+02:00", end: "2026-09-09T16:30:00+02:00", confidence: 0.85 },
    ]);
    expect(demo.explanation.assets.ev.shap.map((s) => s.contribution)).toEqual([0.31, 0.24, 0.15, -0.04]);
  });

  it("gives the demo building an EV plateau at night and a PV dip at midday", () => {
    const demo = buildings[0];
    const at = (hhmm: string) => demo.electricity.find((p) => p.timestamp.includes(`T${hhmm}:00+02:00`))!.powerKw;
    expect(at("22:30")).toBeGreaterThan(6.5);
    expect(at("00:45")).toBeGreaterThan(6.5);
    expect(at("13:00")).toBeLessThan(0);
    expect(at("04:00")).toBeLessThan(2);
  });

  it("uses only Aargau PLZs that exist in the polygon data", () => {
    for (const { plz } of MOCK_PLZ_POOL) expect(getPlzArea(plz), plz).toBeDefined();
    for (const b of buildings) {
      expect(getPlzArea(b.postcode), b.id).toBeDefined();
      expect(b.city).toBe(getPlzArea(b.postcode)!.name);
    }
  });

  it("gives every building a full day, 1–3 events and probabilities in range", () => {
    for (const b of buildings) {
      expect(b.electricity.length).toBe(96);
      expect(b.electricity[0].timestamp).toBe("2026-09-09T00:00:00+02:00");
      expect(b.events.length).toBeGreaterThanOrEqual(1);
      expect(b.events.length).toBeLessThanOrEqual(3);
      for (const e of b.events) expect(Date.parse(e.end)).toBeGreaterThan(Date.parse(e.start));
      for (const key of ASSET_KEYS) {
        expect(b.predictions[key]).toBeGreaterThanOrEqual(0);
        expect(b.predictions[key]).toBeLessThanOrEqual(100);
        expect(b.explanation.assets[key].reasons.length).toBeGreaterThan(0);
        expect(b.explanation.assets[key].shap.length).toBe(4);
      }
    }
  });
});
```

- [ ] **Step 4: Run to verify failure**

Run: `npx vitest run src/lib/mock-data.test.ts` → FAIL (module missing).

- [ ] **Step 5: Create `src/lib/mock-data.ts`**

```ts
import { getPlzArea } from "@/lib/plz";
import { createRng, type Rng } from "@/lib/random";
import {
  ASSET_KEYS,
  type AssetExplanation,
  type AssetKey,
  type AssetPrediction,
  type Building,
  type BuildingEvent,
  type BuildingExplanation,
  type ElectricityPoint,
} from "@/lib/types";

export const MOCK_SEED = 42;
export const MOCK_BUILDING_COUNT = 120;
/** Local midnight in Europe/Zurich (CEST). Timestamps are emitted with this offset. */
export const MOCK_DAY_START = "2026-09-09T00:00:00+02:00";
export const DEMO_BUILDING_ID = "AG-004711";

const TZ_OFFSET_MINUTES = 120;
const STEP_MINUTES = 15;
const POINTS_PER_DAY = 96;
const DAY_MINUTES = 1440;
const EV_PLATEAU_KW = 7;
const DAY_START_MS = Date.parse(MOCK_DAY_START);

/** Aargau postal codes used for mock buildings; every code must exist in src/data/aargau-plz.json. */
export const MOCK_PLZ_POOL: readonly { plz: string; weight: number }[] = [
  { plz: "5000", weight: 8 },
  { plz: "5400", weight: 6 },
  { plz: "5200", weight: 4 },
  { plz: "5600", weight: 4 },
  { plz: "4800", weight: 4 },
  { plz: "4310", weight: 3 },
  { plz: "5610", weight: 3 },
  { plz: "4663", weight: 2 },
  { plz: "4313", weight: 2 },
  { plz: "5070", weight: 2 },
  { plz: "5630", weight: 2 },
  { plz: "5330", weight: 2 },
  { plz: "5734", weight: 2 },
  { plz: "5034", weight: 2 },
  { plz: "5033", weight: 2 },
  { plz: "8957", weight: 2 },
  { plz: "5430", weight: 3 },
  { plz: "4665", weight: 2 },
  { plz: "5507", weight: 1 },
  { plz: "5620", weight: 2 },
];

/** Minutes from day start; `end` may exceed DAY_MINUTES when an event crosses midnight. */
type Window = { start: number; end: number };
type EventWindows = { ev: Window[]; pv?: Window; high?: Window };

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** ISO 8601 with the fixed +02:00 offset, e.g. minute 1335 → "2026-09-09T22:15:00+02:00". */
function isoAtMinute(minute: number): string {
  const local = new Date(DAY_START_MS + (minute + TZ_OFFSET_MINUTES) * 60_000);
  return `${local.toISOString().slice(0, 19)}+02:00`;
}

function pickPlz(rng: Rng): string {
  const total = MOCK_PLZ_POOL.reduce((sum, entry) => sum + entry.weight, 0);
  let roll = rng.between(0, total);
  for (const entry of MOCK_PLZ_POOL) {
    roll -= entry.weight;
    if (roll <= 0) return entry.plz;
  }
  return MOCK_PLZ_POOL[MOCK_PLZ_POOL.length - 1].plz;
}

function pickPredictions(rng: Rng): AssetPrediction {
  const pv = rng.int(5, 98);
  const battery = pv >= 70 ? rng.int(30, 90) : rng.int(3, 45);
  const heatPump = rng.int(5, 95);
  const ev = rng.int(5, 95);
  return { pv, battery, heatPump, ev };
}

function pickWindows(rng: Rng, predictions: AssetPrediction): EventWindows {
  const windows: EventWindows = { ev: [] };
  if (predictions.ev >= 50) {
    const start = rng.int(84, 92) * STEP_MINUTES; // 21:00 – 23:00
    const duration = rng.int(8, 14) * STEP_MINUTES; // 2h – 3.5h, may cross midnight
    windows.ev.push({ start, end: start + duration });
  }
  if (predictions.pv >= 50) {
    windows.pv = { start: 600 + rng.int(-3, 3) * STEP_MINUTES, end: 990 + rng.int(-3, 3) * STEP_MINUTES };
  }
  if ((windows.ev.length === 0 && !windows.pv) || rng.chance(0.3)) {
    windows.high = { start: 1080, end: 1200 };
  }
  return windows;
}

function inWindow(minute: number, window: Window): boolean {
  if (minute >= window.start && minute < window.end) return true;
  // A window crossing midnight also covers the first minutes of this synthetic day.
  return window.end > DAY_MINUTES && minute < window.end - DAY_MINUTES;
}

function bell(x: number, center: number, width: number): number {
  return Math.exp(-((x - center) ** 2) / (2 * width * width));
}

export function synthesizeElectricity(rng: Rng, predictions: AssetPrediction, windows: EventWindows): ElectricityPoint[] {
  const points: ElectricityPoint[] = [];
  for (let i = 0; i < POINTS_PER_DAY; i++) {
    const minute = i * STEP_MINUTES;
    const hour = minute / 60;
    let kw = 0.35 + rng.between(0, 0.15);
    kw += 0.8 * bell(hour, 7.5, 1);
    kw += 1.2 * bell(hour, 19, 1.5);
    if (predictions.heatPump >= 50) {
      const cycling = i % 4 < 2 ? 1.4 : 0.2;
      const daypart = hour < 9 || hour > 17 ? 1 : 0.5;
      kw += cycling * daypart;
    }
    if (predictions.pv >= 50 && windows.pv) {
      const peak = 2.5 + 3 * (predictions.pv / 100);
      const t = (minute - windows.pv.start) / (windows.pv.end - windows.pv.start);
      if (t > 0 && t < 1) kw -= peak * Math.sin(Math.PI * t);
    }
    if (predictions.battery >= 50) {
      kw -= 0.6 * bell(hour, 19, 1.5);
      kw += 0.4 * bell(hour, 13, 1.5);
    }
    if (windows.ev.some((window) => inWindow(minute, window))) {
      kw += EV_PLATEAU_KW + rng.between(-0.2, 0.2);
    }
    points.push({ timestamp: isoAtMinute(minute), powerKw: round2(kw) });
  }
  return points;
}

function windowsToEvents(windows: EventWindows, confidences: { ev: number; pv: number; high: number }): BuildingEvent[] {
  const events: BuildingEvent[] = windows.ev.map((window) => ({
    type: "ev_charging",
    start: isoAtMinute(window.start),
    end: isoAtMinute(window.end),
    confidence: confidences.ev,
  }));
  if (windows.pv) {
    events.push({ type: "pv_generation", start: isoAtMinute(windows.pv.start), end: isoAtMinute(windows.pv.end), confidence: confidences.pv });
  }
  if (windows.high) {
    events.push({ type: "high_consumption", start: isoAtMinute(windows.high.start), end: isoAtMinute(windows.high.end), confidence: confidences.high });
  }
  return events.slice(0, 3);
}

const REASONS: Record<AssetKey, { likely: string[]; unlikely: string[] }> = {
  pv: {
    likely: ["Recurring midday reduction in net consumption", "Reduction scales with expected sunshine hours", "Pattern repeats across consecutive days"],
    unlikely: ["No consistent midday reduction in net load", "Daytime consumption follows a typical household shape"],
  },
  battery: {
    likely: ["Evening peak is flatter than similar households", "Midday surplus is absorbed rather than exported", "Charge and discharge cycles follow the PV pattern"],
    unlikely: ["Evening peak shape matches households without storage", "Midday surplus is exported rather than stored"],
  },
  heatPump: {
    likely: ["Regular on/off cycling of a 1–2 kW load", "Higher baseline in morning and evening hours", "Consumption rises when outdoor temperature drops"],
    unlikely: ["No regular cycling load detected", "Baseline consumption is stable across the day"],
  },
  ev: {
    likely: ["Repeated high-power events", "Mostly during nighttime", "Similar duration across multiple days"],
    unlikely: ["No repeated high-power plateaus", "Nighttime consumption stays near baseline"],
  },
};

const SHAP_FEATURES: Record<AssetKey, [string, string, string, string]> = {
  pv: ["Midday net-load dip", "Clear-sky day correlation", "Seasonal amplitude", "Nighttime baseline"],
  battery: ["Evening peak flattening", "Midday absorption", "Cycle regularity", "Export events"],
  heatPump: ["Cycling frequency", "Temperature sensitivity", "Morning baseline", "Summer consumption"],
  ev: ["High nighttime power peak", "Repeated 7 kW events", "Event duration", "Daytime consumption pattern"],
};

const MODEL_META = {
  model: "Machine learning classification model",
  inputs: ["15-minute electricity measurements"],
  additionalData: ["Weather / temperature (if available)"],
  method: "SHAP",
  methodDescription: "SHAP shows which features contributed most to the prediction.",
} as const;

function generateAssetExplanation(rng: Rng, key: AssetKey, probability: number): AssetExplanation {
  const p = probability / 100;
  const likely = p >= 0.5;
  const strength = likely ? p : 1 - p;
  const shap = SHAP_FEATURES[key].map((feature, index) => {
    const magnitude = strength * (0.35 - index * 0.08) + rng.between(-0.03, 0.03);
    const supportsAsset = index < 3; // three features for, one against
    const sign = (supportsAsset ? 1 : -1) * (likely ? 1 : -1);
    return { feature, contribution: round2(sign * Math.abs(magnitude)) };
  });
  return { reasons: likely ? REASONS[key].likely : REASONS[key].unlikely, shap };
}

function generateExplanation(rng: Rng, predictions: AssetPrediction): BuildingExplanation {
  const assets = Object.fromEntries(
    ASSET_KEYS.map((key) => [key, generateAssetExplanation(rng, key, predictions[key])]),
  ) as Record<AssetKey, AssetExplanation>;
  return { ...MODEL_META, inputs: [...MODEL_META.inputs], additionalData: [...MODEL_META.additionalData], assets };
}

/** Hand-authored so the demo matches the task doc's SHAP example exactly. */
const DEMO_EXPLANATION: BuildingExplanation = {
  ...MODEL_META,
  inputs: [...MODEL_META.inputs],
  additionalData: [...MODEL_META.additionalData],
  assets: {
    pv: {
      reasons: REASONS.pv.likely,
      shap: [
        { feature: "Midday net-load dip", contribution: 0.38 },
        { feature: "Clear-sky day correlation", contribution: 0.22 },
        { feature: "Seasonal amplitude", contribution: 0.12 },
        { feature: "Nighttime baseline", contribution: -0.02 },
      ],
    },
    battery: {
      reasons: REASONS.battery.unlikely,
      shap: [
        { feature: "Evening peak flattening", contribution: 0.09 },
        { feature: "Midday absorption", contribution: 0.06 },
        { feature: "Cycle regularity", contribution: -0.05 },
        { feature: "Export events", contribution: -0.11 },
      ],
    },
    heatPump: {
      reasons: REASONS.heatPump.unlikely,
      shap: [
        { feature: "Cycling frequency", contribution: -0.21 },
        { feature: "Temperature sensitivity", contribution: -0.12 },
        { feature: "Morning baseline", contribution: 0.05 },
        { feature: "Summer consumption", contribution: -0.03 },
      ],
    },
    ev: {
      reasons: REASONS.ev.likely,
      shap: [
        { feature: "High nighttime power peak", contribution: 0.31 },
        { feature: "Repeated 7 kW events", contribution: 0.24 },
        { feature: "Event duration", contribution: 0.15 },
        { feature: "Daytime consumption pattern", contribution: -0.04 },
      ],
    },
  },
};

function buildDemoBuilding(rng: Rng): Building {
  const predictions: AssetPrediction = { pv: 92, battery: 48, heatPump: 31, ev: 76 };
  const windows: EventWindows = { ev: [{ start: 1335, end: DAY_MINUTES + 90 }], pv: { start: 600, end: 990 } };
  return {
    id: DEMO_BUILDING_ID,
    postcode: "5000",
    city: getPlzArea("5000")?.name ?? "Aarau",
    canton: "AG",
    predictions,
    electricity: synthesizeElectricity(rng, predictions, windows),
    events: windowsToEvents(windows, { ev: 0.9, pv: 0.85, high: 0.6 }),
    explanation: DEMO_EXPLANATION,
  };
}

/** Deterministic: same seed and count always yield the same buildings. Demo building first. */
export function generateMockBuildings(seed = MOCK_SEED, count = MOCK_BUILDING_COUNT): Building[] {
  const rng = createRng(seed);
  const buildings: Building[] = [buildDemoBuilding(rng)];
  const usedIds = new Set(buildings.map((b) => b.id));
  while (buildings.length < count) {
    const id = `AG-${String(rng.int(1, 999_999)).padStart(6, "0")}`;
    if (usedIds.has(id)) continue;
    usedIds.add(id);
    const postcode = pickPlz(rng);
    const predictions = pickPredictions(rng);
    const windows = pickWindows(rng, predictions);
    buildings.push({
      id,
      postcode,
      city: getPlzArea(postcode)?.name ?? postcode,
      canton: "AG",
      predictions,
      electricity: synthesizeElectricity(rng, predictions, windows),
      events: windowsToEvents(windows, {
        ev: round2(rng.between(0.7, 0.95)),
        pv: round2(rng.between(0.6, 0.9)),
        high: round2(rng.between(0.5, 0.8)),
      }),
      explanation: generateExplanation(rng, predictions),
    });
  }
  return buildings;
}
```

- [ ] **Step 6: Run the mock-data tests**

Run: `npx vitest run src/lib/mock-data.test.ts`
Expected: PASS. If the "EV plateau / PV dip" assertions fail by a small margin, the curve constants are wrong, not the test — check `inWindow` and the PV `sin` term before touching thresholds.

- [ ] **Step 7: Create `src/lib/api.ts` and `src/test/fixtures.ts`**

```ts
// src/lib/api.ts
import { generateMockBuildings } from "@/lib/mock-data";
import type { Building } from "@/lib/types";

const MOCK_LATENCY_MS = 150;

/**
 * The only place that knows where buildings come from. Replace the body with a
 * real fetch when the backend exists; nothing else changes.
 */
export async function fetchBuildings(): Promise<Building[]> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));
  return generateMockBuildings();
}
```

```ts
// src/test/fixtures.ts
import type { AssetExplanation, Building } from "@/lib/types";

const explanation = (reason: string, feature: string): AssetExplanation => ({
  reasons: [reason],
  shap: [
    { feature, contribution: 0.3 },
    { feature: "Secondary feature", contribution: 0.1 },
    { feature: "Tertiary feature", contribution: 0.05 },
    { feature: "Counter feature", contribution: -0.04 },
  ],
});

/** A realistic building for component tests; override any field. */
export function makeBuilding(overrides: Partial<Building> = {}): Building {
  return {
    id: "AG-000001",
    postcode: "5000",
    city: "Aarau",
    canton: "AG",
    predictions: { pv: 92, battery: 48, heatPump: 31, ev: 76 },
    electricity: [
      { timestamp: "2026-09-09T00:00:00+02:00", powerKw: 0.4 },
      { timestamp: "2026-09-09T00:15:00+02:00", powerKw: 0.5 },
      { timestamp: "2026-09-09T00:30:00+02:00", powerKw: 7.2 },
    ],
    events: [
      { type: "ev_charging", start: "2026-09-09T22:15:00+02:00", end: "2026-09-10T01:30:00+02:00", confidence: 0.9 },
      { type: "pv_generation", start: "2026-09-09T10:00:00+02:00", end: "2026-09-09T16:30:00+02:00", confidence: 0.85 },
    ],
    explanation: {
      model: "Test model",
      inputs: ["15-minute electricity measurements"],
      additionalData: ["Weather / temperature (if available)"],
      method: "SHAP",
      methodDescription: "SHAP shows which features contributed most to the prediction.",
      assets: {
        pv: explanation("Recurring midday reduction in net consumption", "Midday net-load dip"),
        battery: explanation("Midday surplus is exported rather than stored", "Evening peak flattening"),
        heatPump: explanation("No regular cycling load detected", "Cycling frequency"),
        ev: explanation("Repeated high-power events", "High nighttime power peak"),
      },
    },
    ...overrides,
  };
}
```

- [ ] **Step 8: Write the failing hook tests `src/hooks/use-buildings.test.tsx`**

```tsx
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QueryClientProvider } from "@tanstack/react-query";

import { useFilteredBuildings, useHighlightedPlz, usePlzCounts, useSelectedBuilding } from "@/hooks/use-buildings";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { createTestQueryClient } from "@/test/render";

const fixtures = [
  makeBuilding({ id: "AG-000001", postcode: "5000", city: "Aarau" }),
  makeBuilding({ id: "AG-000002", postcode: "5000", city: "Aarau" }),
  makeBuilding({ id: "AG-000003", postcode: "5400", city: "Baden" }),
];

vi.mock("@/lib/api", () => ({ fetchBuildings: async () => fixtures }));

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

describe("use-buildings hooks", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("filters by selected PLZ first, then by search, and reports the area total", async () => {
    useUIStore.getState().selectPlz("5000");
    useUIStore.getState().setSearchQuery("000002");
    const { result } = renderHook(() => useFilteredBuildings(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.buildings.map((b) => b.id)).toEqual(["AG-000002"]);
    expect(result.current.total).toBe(2);
  });

  it("returns all buildings when no area is selected", async () => {
    const { result } = renderHook(() => useFilteredBuildings(), { wrapper });
    await waitFor(() => expect(result.current.buildings.length).toBe(3));
    expect(result.current.total).toBe(3);
  });

  it("resolves the selected building and its PLZ as the highlight", async () => {
    useUIStore.getState().selectPlz("5000");
    useUIStore.getState().selectBuilding("AG-000003");
    const selected = renderHook(() => useSelectedBuilding(), { wrapper });
    await waitFor(() => expect(selected.result.current?.id).toBe("AG-000003"));
    const highlighted = renderHook(() => useHighlightedPlz(), { wrapper });
    await waitFor(() => expect(highlighted.result.current).toBe("5400"));
  });

  it("falls back to the selected area when no building is selected", () => {
    useUIStore.getState().selectPlz("5000");
    const { result } = renderHook(() => useHighlightedPlz(), { wrapper });
    expect(result.current).toBe("5000");
  });

  it("counts buildings per PLZ over the whole dataset", async () => {
    useUIStore.getState().selectPlz("5400");
    const { result } = renderHook(() => usePlzCounts(), { wrapper });
    await waitFor(() => expect(result.current).toEqual({ "5000": 2, "5400": 1 }));
  });
});
```

- [ ] **Step 9: Run to verify failure, then create `src/hooks/use-buildings.ts`**

Run: `npx vitest run src/hooks` → FAIL (module missing).

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { fetchBuildings } from "@/lib/api";
import { countBuildingsByPlz } from "@/lib/plz";
import { filterBuildings } from "@/lib/search";
import type { Building } from "@/lib/types";
import { useUIStore } from "@/stores/ui-store";

export const buildingsQueryKey = ["buildings"] as const;

const EMPTY: Building[] = [];

export function useBuildings() {
  return useQuery({ queryKey: buildingsQueryKey, queryFn: fetchBuildings, staleTime: Infinity });
}

/** PLZ filter first, then search. `total` is the area count before search. */
export function useFilteredBuildings() {
  const { data, isLoading, isError } = useBuildings();
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const searchQuery = useUIStore((s) => s.searchQuery);
  const inArea = useMemo(() => {
    const all = data ?? EMPTY;
    return selectedPlz ? all.filter((b) => b.postcode === selectedPlz) : all;
  }, [data, selectedPlz]);
  const buildings = useMemo(() => filterBuildings(inArea, searchQuery), [inArea, searchQuery]);
  return { buildings, total: inArea.length, isLoading, isError };
}

export function useSelectedBuilding(): Building | undefined {
  const { data } = useBuildings();
  const id = useUIStore((s) => s.selectedBuildingId);
  return useMemo(() => (id ? data?.find((b) => b.id === id) : undefined), [data, id]);
}

/** Counts over the whole dataset, independent of filters; feeds the map tooltip. */
export function usePlzCounts(): Record<string, number> {
  const { data } = useBuildings();
  return useMemo(() => countBuildingsByPlz(data ?? EMPTY), [data]);
}

/** The PLZ the map should outline: the selected building's, else the selected area. */
export function useHighlightedPlz(): string | null {
  const selected = useSelectedBuilding();
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  return selected?.postcode ?? selectedPlz;
}
```

Run: `npx vitest run src/hooks` → PASS.

- [ ] **Step 10: Create the chart stub `src/components/chart/electricity-chart.tsx`**

```tsx
"use client";

import type { BuildingEvent, ElectricityPoint } from "@/lib/types";

export type ElectricityChartProps = {
  electricity: ElectricityPoint[];
  events: BuildingEvent[];
  className?: string;
};

/**
 * Placeholder that fixes the chart's public interface so the detail panel can be
 * built in parallel. The chart task replaces the body, not the props.
 */
export function ElectricityChart({ electricity, events, className }: ElectricityChartProps) {
  return (
    <div
      data-testid="electricity-chart"
      data-points={electricity.length}
      data-events={events.length}
      className={className}
      style={{ height: 260 }}
    />
  );
}
```

- [ ] **Step 11: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/lib/random.ts src/lib/random.test.ts src/lib/mock-data.ts src/lib/mock-data.test.ts src/lib/api.ts src/hooks/use-buildings.ts src/hooks/use-buildings.test.tsx src/test/fixtures.ts src/components/chart/electricity-chart.tsx
git commit -m "feat(frontend): add seeded mock buildings, data hooks and chart stub

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

**Wave 0 exit gate (controller):** all four tasks reviewed and complete on `feat/frontend-energy-map`; `npm run check` green; `git status` clean. Only then create the five Wave 1 worktrees from this commit.

---

## Wave 1 — UI areas (parallel, one worktree and branch per task)

Each Wave 1 task starts from the Wave 0 exit commit on its own branch `feat/ef-<area>`, runs `npm ci`, and owns only its listed files. Each adds a throwaway preview page under `src/app/dev/<area>/page.tsx` so the implementer can open `http://localhost:3000/dev/<area>` and screenshot it (use the Playwright or browser tools if available; otherwise `npm run dev` and describe what you saw in the report). Wave 2 deletes `src/app/dev/`.

### Task 5: Header — wordmark, area select, search, view toggle, about dialog

**Files:**
- Create: `src/components/header/wordmark.tsx`, `src/components/header/area-select.tsx`, `src/components/header/view-toggle.tsx`, `src/components/header/about-dialog.tsx`, `src/components/header/app-header.tsx`, `src/app/dev/header/page.tsx`
- Test: `src/components/header/app-header.test.tsx`, `src/components/header/about-dialog.test.tsx`

**Interfaces:**
- Consumes: `useUIStore` (`searchQuery`, `setSearchQuery`, `viewMode`, `setViewMode`, `isAboutOpen`, `setAboutOpen`), `ViewMode`; shadcn `Button`, `Input`, `Select*`, `Dialog*`.
- Produces: `<AppHeader />` and `<AboutDialog />`, both prop-less; Task 10 mounts them.

- [ ] **Step 1: Read the generated shadcn files you will use**

Open `src/components/ui/select.tsx` and `src/components/ui/dialog.tsx`. Note that `Select` takes `items` (array of `{ label, value }`) so `SelectValue` can render the label, and that `Dialog`'s `onOpenChange` receives `(open, eventDetails)`.

- [ ] **Step 2: Write the failing header test `src/components/header/app-header.test.tsx`**

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { AppHeader } from "@/components/header/app-header";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { renderWithProviders } from "@/test/render";

describe("AppHeader", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("shows the wordmark, area and search placeholder", () => {
    renderWithProviders(<AppHeader />);
    expect(screen.getByText("Energy Fingerprints")).toBeInTheDocument();
    expect(screen.getByText("Aargau (AG)")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search building ID, PLZ or town...")).toBeInTheDocument();
  });

  it("writes the search query to the store", async () => {
    renderWithProviders(<AppHeader />);
    await userEvent.type(screen.getByRole("searchbox", { name: "Search buildings" }), "aarau");
    expect(useUIStore.getState().searchQuery).toBe("aarau");
  });

  it("toggles the view mode with pressed state", async () => {
    renderWithProviders(<AppHeader />);
    const list = screen.getByRole("button", { name: "List" });
    const map = screen.getByRole("button", { name: "Map" });
    expect(map).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(list);
    expect(useUIStore.getState().viewMode).toBe("list");
    expect(list).toHaveAttribute("aria-pressed", "true");
    expect(map).toHaveAttribute("aria-pressed", "false");
  });

  it("opens the about dialog flag", async () => {
    renderWithProviders(<AppHeader />);
    await userEvent.click(screen.getByRole("button", { name: "About this project" }));
    expect(useUIStore.getState().isAboutOpen).toBe(true);
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `npx vitest run src/components/header` → FAIL (modules missing).

- [ ] **Step 4: Create `src/components/header/wordmark.tsx`**

```tsx
/**
 * Text wordmark. If the team obtains the official AEW logo, drop it in
 * `public/aew-logo.svg` and replace the "AEW" tile with an <Image>.
 */
export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <div
        aria-hidden
        className="grid size-8 place-items-center rounded-md bg-primary text-[11px] font-bold tracking-wide text-primary-foreground"
      >
        AEW
      </div>
      <div className="leading-tight">
        <div className="text-sm font-semibold">Energy Fingerprints</div>
        <div className="text-[11px] text-muted-foreground">Energy Data Hackdays 2026</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create `src/components/header/area-select.tsx`**

```tsx
"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/** Static for the prototype: Aargau is the only area with data. */
export const AREAS = [{ value: "AG", label: "Aargau (AG)" }] as const;

export function AreaSelect() {
  return (
    <Select value="AG" items={AREAS}>
      <SelectTrigger aria-label="Area" className="w-40">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {AREAS.map((area) => (
          <SelectItem key={area.value} value={area.value}>
            {area.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

If the generated `Select` does not accept `items` (check `src/components/ui/select.tsx` and the `@base-ui/react/select` types), pass `items={Object.fromEntries(AREAS.map((a) => [a.value, a.label]))}` instead; record which form you used in the report.

- [ ] **Step 6: Create `src/components/header/view-toggle.tsx`**

```tsx
"use client";

import { List as ListIcon, Map as MapIcon, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ViewMode } from "@/stores/ui-store";

const OPTIONS: { value: ViewMode; label: string; icon: LucideIcon }[] = [
  { value: "map", label: "Map", icon: MapIcon },
  { value: "list", label: "List", icon: ListIcon },
];

export function ViewToggle({ value, onChange }: { value: ViewMode; onChange: (mode: ViewMode) => void }) {
  return (
    <div role="group" aria-label="View" className="flex rounded-lg border bg-muted p-0.5">
      {OPTIONS.map(({ value: mode, label, icon: Icon }) => {
        const active = value === mode;
        return (
          <Button
            key={mode}
            size="sm"
            variant="ghost"
            aria-pressed={active}
            onClick={() => onChange(mode)}
            className={cn("h-7 px-2.5", active && "bg-background text-foreground shadow-sm hover:bg-background")}
          >
            <Icon />
            {label}
          </Button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 7: Create `src/components/header/about-dialog.tsx`**

```tsx
"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useUIStore } from "@/stores/ui-store";

/** Copy adapted from the repository README ("Challenge" section). */
const ABOUT_PARAGRAPHS = [
  "One smart meter records a household's aggregated electricity signal, but many devices contribute to it. The Energy Fingerprints challenge at Energy Data Hackdays 2026 asks which assets — electric vehicles, heat pumps, rooftop PV and batteries — can be recognised from anonymised 15-minute measurements.",
  "This demo shows, per postal-code area and per anonymised building, how likely each asset is, when it appears to be active, and the evidence behind that estimate. Predictions are probabilities, not facts.",
  "Data: four years of 15-minute smart-meter readings for about 90,000 anonymised customers with postal codes, plus known asset labels for around 1,000 of them. The demo runs on generated mock data shaped like the real contract.",
];

export function AboutDialog() {
  const isAboutOpen = useUIStore((s) => s.isAboutOpen);
  const setAboutOpen = useUIStore((s) => s.setAboutOpen);
  return (
    <Dialog open={isAboutOpen} onOpenChange={(open) => setAboutOpen(open)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>About this project</DialogTitle>
          <DialogDescription>AEW Energy Fingerprints — Energy Data Hackdays 2026</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm leading-relaxed text-foreground/90">
          {ABOUT_PARAGRAPHS.map((paragraph) => (
            <p key={paragraph.slice(0, 24)}>{paragraph}</p>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 8: Create `src/components/header/app-header.tsx`**

```tsx
"use client";

import { Info, Search } from "lucide-react";

import { AreaSelect } from "@/components/header/area-select";
import { ViewToggle } from "@/components/header/view-toggle";
import { Wordmark } from "@/components/header/wordmark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUIStore } from "@/stores/ui-store";

export function AppHeader() {
  const searchQuery = useUIStore((s) => s.searchQuery);
  const setSearchQuery = useUIStore((s) => s.setSearchQuery);
  const viewMode = useUIStore((s) => s.viewMode);
  const setViewMode = useUIStore((s) => s.setViewMode);
  const setAboutOpen = useUIStore((s) => s.setAboutOpen);

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-background px-4">
      <Wordmark />
      <div className="hidden md:block">
        <AreaSelect />
      </div>
      <div className="relative mx-auto w-full max-w-md">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="Search buildings"
          placeholder="Search building ID, PLZ or town..."
          className="pl-8"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
        />
      </div>
      <ViewToggle value={viewMode} onChange={setViewMode} />
      <Button variant="ghost" size="sm" className="hidden sm:inline-flex" onClick={() => setAboutOpen(true)}>
        <Info />
        About this project
      </Button>
    </header>
  );
}
```

- [ ] **Step 9: Write the about-dialog test `src/components/header/about-dialog.test.tsx`**

```tsx
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
```

- [ ] **Step 10: Run the header tests**

Run: `npx vitest run src/components/header` → PASS. If `getByRole("searchbox")` fails, the `Input` dropped `type`; check the generated `input.tsx` passes `type` through.

- [ ] **Step 11: Create the preview page `src/app/dev/header/page.tsx`**

```tsx
"use client";

import { AboutDialog } from "@/components/header/about-dialog";
import { AppHeader } from "@/components/header/app-header";
import { useUIStore } from "@/stores/ui-store";

/** Throwaway preview for the header task; deleted at integration. */
export default function HeaderPreviewPage() {
  const state = useUIStore();
  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <AboutDialog />
      <pre className="p-4 text-xs text-muted-foreground">
        {JSON.stringify({ viewMode: state.viewMode, searchQuery: state.searchQuery, isAboutOpen: state.isAboutOpen }, null, 2)}
      </pre>
    </div>
  );
}
```

Run `npm run dev`, open `http://localhost:3000/dev/header`, confirm: wordmark, select shows "Aargau (AG)", typing updates the readout, toggle switches, About opens a dialog with a close control.

- [ ] **Step 12: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/components/header src/app/dev/header
git commit -m "feat(frontend): add app header with search, view toggle and about dialog

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Map — Aargau PLZ areas with hover, click-to-select, highlight and fit

**Files:**
- Create: `src/components/map/plz-layers.tsx`, `src/components/map/map-tooltip.tsx`, `src/components/map/map-view.tsx`, `src/app/dev/map/page.tsx`
- Test: `src/components/map/plz-layers.test.ts`, `src/components/map/map-view.test.tsx`

**Interfaces:**
- Consumes: `usePlzCounts`, `useHighlightedPlz` (Task 4); `AARGAU_BBOX`, `buildPlzGeoJson`, `getPlzArea`, `formatPlz`, `PlzCountProperties` (Task 2); `useUIStore` (`selectedPlz`, `selectPlz`).
- Produces: `<MapView />` (prop-less, client-only — Task 10 loads it with `next/dynamic` and `ssr: false`); `MAP_STYLE_URL`.

- [ ] **Step 1: Write the failing filter test `src/components/map/plz-layers.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { plzFilter } from "@/components/map/plz-layers";

describe("plzFilter", () => {
  it("matches exactly one PLZ", () => {
    expect(plzFilter("5000")).toEqual(["==", ["get", "plz"], "5000"]);
  });

  it("matches nothing for null", () => {
    const [, , sentinel] = plzFilter(null);
    expect(typeof sentinel).toBe("string");
    expect(sentinel).not.toMatch(/^\d{4}$/);
  });
});
```

- [ ] **Step 2: Create `src/components/map/plz-layers.tsx`**

```tsx
"use client";

import type { FeatureCollection, Polygon } from "geojson";
import type { ExpressionSpecification } from "maplibre-gl";
import { Layer, Source } from "react-map-gl/maplibre";

import type { PlzCountProperties } from "@/lib/plz";

export const PLZ_SOURCE_ID = "plz";
export const PLZ_FILL_LAYER_ID = "plz-fill";

/** Spec §10: one quiet fill, thin borders, tint on hover, strong outline for the highlighted area. */
export const MAP_COLORS = {
  fill: "#dbeafe",
  border: "#94a3b8",
  highlight: "#1d4ed8",
} as const;
const FILL_OPACITY = 0.35;
const HOVER_OPACITY = 0.12;
/** A value no PLZ has, so a null filter matches nothing. */
const NO_MATCH = "__none__";

export function plzFilter(plz: string | null): ExpressionSpecification {
  return ["==", ["get", "plz"], plz ?? NO_MATCH];
}

type PlzLayersProps = {
  data: FeatureCollection<Polygon, PlzCountProperties>;
  highlightedPlz: string | null;
  hoveredPlz: string | null;
};

export function PlzLayers({ data, highlightedPlz, hoveredPlz }: PlzLayersProps) {
  return (
    <Source id={PLZ_SOURCE_ID} type="geojson" data={data}>
      <Layer id={PLZ_FILL_LAYER_ID} type="fill" paint={{ "fill-color": MAP_COLORS.fill, "fill-opacity": FILL_OPACITY }} />
      <Layer
        id="plz-hover"
        type="fill"
        filter={plzFilter(hoveredPlz)}
        paint={{ "fill-color": MAP_COLORS.highlight, "fill-opacity": HOVER_OPACITY }}
      />
      <Layer id="plz-line" type="line" paint={{ "line-color": MAP_COLORS.border, "line-width": 0.6 }} />
      <Layer
        id="plz-highlight"
        type="line"
        filter={plzFilter(highlightedPlz)}
        paint={{ "line-color": MAP_COLORS.highlight, "line-width": 2.5 }}
      />
    </Source>
  );
}
```

Run: `npx vitest run src/components/map/plz-layers.test.ts` → PASS.

- [ ] **Step 3: Create `src/components/map/map-tooltip.tsx`**

```tsx
import { formatPlz } from "@/lib/plz";

type MapTooltipProps = { plz: string | null; count: number; x: number; y: number };

/** Cursor-following label; hidden when no PLZ is hovered. */
export function MapTooltip({ plz, count, x, y }: MapTooltipProps) {
  if (!plz) return null;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-10 rounded-md border bg-background/95 px-2 py-1 text-xs shadow-sm"
      style={{ left: x + 12, top: y + 12 }}
    >
      {formatPlz(plz)} · {count} {count === 1 ? "building" : "buildings"}
    </div>
  );
}
```

- [ ] **Step 4: Write the failing map test `src/components/map/map-view.test.tsx`**

```tsx
import { act, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

const mapMock = vi.hoisted(() => ({
  props: {} as Record<string, unknown>,
  fitBounds: vi.fn(),
}));

vi.mock("react-map-gl/maplibre", async () => {
  const React = await import("react");
  const MockMap = React.forwardRef<unknown, Record<string, unknown> & { children?: ReactNode }>(
    function MockMap(props, ref) {
      mapMock.props = props;
      React.useImperativeHandle(ref, () => ({ fitBounds: mapMock.fitBounds }));
      return <div data-testid="mock-map">{props.children}</div>;
    },
  );
  return {
    default: MockMap,
    NavigationControl: () => null,
    Source: ({ children }: { children?: ReactNode }) => <>{children}</>,
    Layer: () => null,
  };
});

vi.mock("@/lib/api", () => ({
  fetchBuildings: async () => [
    makeBuilding({ id: "AG-000001", postcode: "5000" }),
    makeBuilding({ id: "AG-000002", postcode: "5000" }),
    makeBuilding({ id: "AG-000003", postcode: "5400" }),
  ],
}));

import { MapView } from "@/components/map/map-view";

type Handler = (event: unknown) => void;
const feature = (plz: string, count: number) => ({ properties: { plz, name: "x", gemeinde: "x", count } });
const clickWith = (features: unknown[]) =>
  act(() => (mapMock.props.onClick as Handler)({ features, point: { x: 10, y: 10 } }));

describe("MapView", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
    mapMock.fitBounds.mockClear();
  });

  it("renders the map and no tooltip initially", () => {
    renderWithProviders(<MapView />);
    expect(screen.getByTestId("mock-map")).toBeInTheDocument();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("selects a PLZ on click, toggles it off on a second click, clears on empty click", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onClick).toBeTypeOf("function"));
    await clickWith([feature("5000", 2)]);
    expect(useUIStore.getState().selectedPlz).toBe("5000");
    await clickWith([feature("5000", 2)]);
    expect(useUIStore.getState().selectedPlz).toBeNull();
    useUIStore.getState().selectPlz("5400");
    await clickWith([]);
    expect(useUIStore.getState().selectedPlz).toBeNull();
  });

  it("shows a tooltip with the building count while hovering a PLZ", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onMouseMove).toBeTypeOf("function"));
    await act(() => (mapMock.props.onMouseMove as Handler)({ features: [feature("5000", 2)], point: { x: 40, y: 50 } }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("5000 Aarau · 2 buildings");
    await act(() => (mapMock.props.onMouseLeave as () => void)());
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("fits the map to the highlighted PLZ", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onClick).toBeTypeOf("function"));
    act(() => useUIStore.getState().selectBuilding("AG-000003"));
    await waitFor(() => expect(mapMock.fitBounds).toHaveBeenCalledTimes(1));
    const [bbox, options] = mapMock.fitBounds.mock.calls[0];
    expect(bbox[0]).toBeLessThan(bbox[2]);
    expect(options).toMatchObject({ padding: 48, maxZoom: 13 });
  });
});
```

- [ ] **Step 5: Run to verify failure**

Run: `npx vitest run src/components/map/map-view.test.tsx` → FAIL (module missing).

- [ ] **Step 6: Create `src/components/map/map-view.tsx`**

```tsx
"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Map, { NavigationControl, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";

import { MapTooltip } from "@/components/map/map-tooltip";
import { PLZ_FILL_LAYER_ID, PlzLayers } from "@/components/map/plz-layers";
import { useHighlightedPlz, usePlzCounts } from "@/hooks/use-buildings";
import { AARGAU_BBOX, buildPlzGeoJson, getPlzArea, type PlzCountProperties } from "@/lib/plz";
import { useUIStore } from "@/stores/ui-store";

export const MAP_STYLE_URL =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron";

const FIT_PADDING = 48;
const FIT_DURATION_MS = 900;
const FIT_MAX_ZOOM = 13;

type Hover = { plz: string; count: number; x: number; y: number } | null;

function plzFeatureAt(event: MapLayerMouseEvent): PlzCountProperties | undefined {
  return event.features?.[0]?.properties as PlzCountProperties | undefined;
}

export function MapView() {
  const mapRef = useRef<MapRef>(null);
  const counts = usePlzCounts();
  const highlightedPlz = useHighlightedPlz();
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const selectPlz = useUIStore((s) => s.selectPlz);
  const [hover, setHover] = useState<Hover>(null);

  const data = useMemo(() => buildPlzGeoJson(counts), [counts]);

  useEffect(() => {
    if (!highlightedPlz) return;
    const area = getPlzArea(highlightedPlz);
    if (!area) return;
    mapRef.current?.fitBounds(area.bbox, {
      padding: FIT_PADDING,
      duration: FIT_DURATION_MS,
      maxZoom: FIT_MAX_ZOOM,
    });
  }, [highlightedPlz]);

  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const feature = plzFeatureAt(event);
      if (!feature) {
        selectPlz(null);
        return;
      }
      selectPlz(feature.plz === selectedPlz ? null : feature.plz);
    },
    [selectPlz, selectedPlz],
  );

  const handleMouseMove = useCallback((event: MapLayerMouseEvent) => {
    const feature = plzFeatureAt(event);
    setHover(feature ? { plz: feature.plz, count: feature.count, x: event.point.x, y: event.point.y } : null);
  }, []);

  const clearHover = useCallback(() => setHover(null), []);

  return (
    <div className="relative h-full w-full" data-testid="map-view">
      <Map
        ref={mapRef}
        mapStyle={MAP_STYLE_URL}
        initialViewState={{ bounds: AARGAU_BBOX, fitBoundsOptions: { padding: 24 } }}
        interactiveLayerIds={[PLZ_FILL_LAYER_ID]}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={clearHover}
        cursor={hover ? "pointer" : "grab"}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="bottom-right" showCompass={false} />
        <PlzLayers data={data} highlightedPlz={highlightedPlz} hoveredPlz={hover?.plz ?? null} />
      </Map>
      <MapTooltip plz={hover?.plz ?? null} count={hover?.count ?? 0} x={hover?.x ?? 0} y={hover?.y ?? 0} />
    </div>
  );
}
```

- [ ] **Step 7: Run the map tests**

Run: `npx vitest run src/components/map` → PASS. If the CSS import breaks jsdom, `vitest.config.ts` already sets `css: false`; do not add a manual mock.

- [ ] **Step 8: Create the preview page `src/app/dev/map/page.tsx`**

```tsx
"use client";

import dynamic from "next/dynamic";

import { useUIStore } from "@/stores/ui-store";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false });

/** Throwaway preview for the map task; deleted at integration. */
export default function MapPreviewPage() {
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const selectBuilding = useUIStore((s) => s.selectBuilding);
  return (
    <div className="flex h-dvh flex-col">
      <div className="flex items-center gap-3 border-b px-4 py-2 text-sm">
        <span>selectedPlz: {selectedPlz ?? "none"}</span>
        <button className="rounded border px-2 py-1" onClick={() => selectBuilding("AG-004711")}>
          Select demo building
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <MapView />
      </div>
    </div>
  );
}
```

Run `npm run dev`, open `http://localhost:3000/dev/map`. Confirm: Aargau fills the view with quiet light-blue areas and thin borders; hovering shows the tooltip and a light tint; clicking outlines the area and updates the readout; clicking the same area again clears it; "Select demo building" zooms to 5000 Aarau with a thick outline. Screenshot for the report.

- [ ] **Step 9: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/components/map src/app/dev/map
git commit -m "feat(frontend): add Aargau PLZ area map with hover, select and fit

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Building list — area header, cards, probability chips

**Files:**
- Create: `src/components/buildings/probability-chip.tsx`, `src/components/buildings/building-card.tsx`, `src/components/buildings/area-header.tsx`, `src/components/buildings/building-list.tsx`, `src/app/dev/list/page.tsx`
- Test: `src/components/buildings/building-card.test.tsx`, `src/components/buildings/building-list.test.tsx`

**Interfaces:**
- Consumes: `useFilteredBuildings` (Task 4); `ASSETS`, `ASSET_BY_KEY`, `describePrediction`, `formatProbability` (Task 2); `formatPlz` (Task 2); `useUIStore` (`selectedPlz`, `selectPlz`, `selectedBuildingId`, `selectBuilding`, `searchQuery`); shadcn `Button`, `ScrollArea`.
- Produces: `<BuildingList />` (prop-less); `<BuildingCard building selected onSelect />`; `<ProbabilityChip assetKey probability />`. Cards carry `id="building-card-<id>"` and `aria-pressed`.

- [ ] **Step 1: Write the failing card test `src/components/buildings/building-card.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run to verify failure, then create the chip and card**

Run: `npx vitest run src/components/buildings/building-card.test.tsx` → FAIL.

```tsx
// src/components/buildings/probability-chip.tsx
import { ASSET_BY_KEY, describePrediction, formatProbability } from "@/lib/predictions";
import type { AssetKey } from "@/lib/types";

export function ProbabilityChip({ assetKey, probability }: { assetKey: AssetKey; probability: number }) {
  const { icon: Icon, color, shortLabel } = ASSET_BY_KEY[assetKey];
  return (
    <span
      title={describePrediction(assetKey, probability)}
      className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium tabular-nums"
      style={{ color }}
    >
      <Icon className="size-3.5" aria-hidden />
      <span className="sr-only">{shortLabel}</span>
      {formatProbability(probability)}
    </span>
  );
}
```

```tsx
// src/components/buildings/building-card.tsx
"use client";

import { Building2 } from "lucide-react";

import { ProbabilityChip } from "@/components/buildings/probability-chip";
import { ASSETS } from "@/lib/predictions";
import type { Building } from "@/lib/types";
import { cn } from "@/lib/utils";

type BuildingCardProps = { building: Building; selected: boolean; onSelect: (id: string) => void };

export function BuildingCard({ building, selected, onSelect }: BuildingCardProps) {
  return (
    <button
      type="button"
      id={`building-card-${building.id}`}
      aria-pressed={selected}
      onClick={() => onSelect(building.id)}
      className={cn(
        "w-full rounded-xl bg-card p-3 text-left ring-1 ring-foreground/10 transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        selected && "bg-primary/5 ring-2 ring-primary hover:bg-primary/5",
      )}
    >
      <div className="flex items-start gap-2.5">
        <div className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
          <Building2 className="size-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">Building {building.id}</div>
          <div className="text-xs text-muted-foreground">
            {building.postcode} {building.city}
          </div>
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {ASSETS.map((asset) => (
          <ProbabilityChip key={asset.key} assetKey={asset.key} probability={building.predictions[asset.key]} />
        ))}
      </div>
    </button>
  );
}
```

Run: `npx vitest run src/components/buildings/building-card.test.tsx` → PASS.

- [ ] **Step 3: Write the failing list test `src/components/buildings/building-list.test.tsx`**

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BuildingList } from "@/components/buildings/building-list";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

vi.mock("@/lib/api", () => ({
  fetchBuildings: async () => [
    makeBuilding({ id: "AG-000001", postcode: "5000", city: "Aarau" }),
    makeBuilding({ id: "AG-000002", postcode: "5000", city: "Aarau" }),
    makeBuilding({ id: "AG-000003", postcode: "5400", city: "Baden" }),
  ],
}));

describe("BuildingList", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("lists all buildings with the canton header", async () => {
    renderWithProviders(<BuildingList />);
    expect(await screen.findByText("Building AG-000001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buildings in Aargau" })).toBeInTheDocument();
    expect(screen.getByText("3 buildings")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show all areas/ })).not.toBeInTheDocument();
  });

  it("filters to the selected area and offers to show all", async () => {
    useUIStore.getState().selectPlz("5400");
    renderWithProviders(<BuildingList />);
    expect(await screen.findByText("Building AG-000003")).toBeInTheDocument();
    expect(screen.queryByText("Building AG-000001")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buildings in 5400 Baden" })).toBeInTheDocument();
    expect(screen.getByText("1 building")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show all areas/ }));
    expect(useUIStore.getState().selectedPlz).toBeNull();
    expect(await screen.findByText("Building AG-000001")).toBeInTheDocument();
  });

  it("selects a building on click and scrolls the selected card into view", async () => {
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView");
    renderWithProviders(<BuildingList />);
    await userEvent.click(await screen.findByText("Building AG-000002"));
    const state = useUIStore.getState();
    expect(state.selectedBuildingId).toBe("AG-000002");
    expect(state.isDetailOpen).toBe(true);
    await waitFor(() => expect(screen.getByRole("button", { pressed: true })).toHaveAttribute("id", "building-card-AG-000002"));
    expect(scrollSpy).toHaveBeenCalled();
  });

  it("shows an empty state for a search with no matches", async () => {
    useUIStore.getState().setSearchQuery("zzz");
    renderWithProviders(<BuildingList />);
    expect(await screen.findByText("No buildings match “zzz”.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run to verify failure, then create the header and list**

Run: `npx vitest run src/components/buildings/building-list.test.tsx` → FAIL.

```tsx
// src/components/buildings/area-header.tsx
"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useFilteredBuildings } from "@/hooks/use-buildings";
import { formatPlz } from "@/lib/plz";
import { useUIStore } from "@/stores/ui-store";

export function AreaHeader() {
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const selectPlz = useUIStore((s) => s.selectPlz);
  const { total, isLoading } = useFilteredBuildings();
  const title = selectedPlz ? `Buildings in ${formatPlz(selectedPlz)}` : "Buildings in Aargau";
  const count = `${total} ${total === 1 ? "building" : "buildings"}`;
  return (
    <div className="flex items-start justify-between gap-2 border-b px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="text-xs text-muted-foreground">{isLoading ? "Loading…" : count}</p>
      </div>
      {selectedPlz && (
        <Button variant="outline" size="xs" onClick={() => selectPlz(null)}>
          <X />
          Show all areas
        </Button>
      )}
    </div>
  );
}
```

```tsx
// src/components/buildings/building-list.tsx
"use client";

import { useEffect } from "react";

import { AreaHeader } from "@/components/buildings/area-header";
import { BuildingCard } from "@/components/buildings/building-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useFilteredBuildings } from "@/hooks/use-buildings";
import { useUIStore } from "@/stores/ui-store";

export function BuildingList() {
  const { buildings, isLoading, isError } = useFilteredBuildings();
  const selectedBuildingId = useUIStore((s) => s.selectedBuildingId);
  const selectBuilding = useUIStore((s) => s.selectBuilding);
  const searchQuery = useUIStore((s) => s.searchQuery);

  useEffect(() => {
    if (!selectedBuildingId) return;
    document
      .getElementById(`building-card-${selectedBuildingId}`)
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedBuildingId]);

  const empty = !isLoading && !isError && buildings.length === 0;

  return (
    <section aria-label="Buildings" className="flex h-full min-h-0 flex-col">
      <AreaHeader />
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-2 p-3">
          {isLoading && <p className="p-4 text-sm text-muted-foreground">Loading buildings…</p>}
          {isError && <p className="p-4 text-sm text-destructive">Could not load buildings.</p>}
          {empty && (
            <p className="p-4 text-sm text-muted-foreground">
              {searchQuery ? `No buildings match “${searchQuery}”.` : "No buildings in this area."}
            </p>
          )}
          {buildings.map((building) => (
            <BuildingCard
              key={building.id}
              building={building}
              selected={building.id === selectedBuildingId}
              onSelect={selectBuilding}
            />
          ))}
        </div>
      </ScrollArea>
    </section>
  );
}
```

Run: `npx vitest run src/components/buildings` → PASS. If `ScrollArea` throws in jsdom, check `src/test/setup.ts` provides `ResizeObserver` (Task 1) before adding any mock.

- [ ] **Step 5: Create the preview page `src/app/dev/list/page.tsx`**

```tsx
"use client";

import { BuildingList } from "@/components/buildings/building-list";
import { useUIStore } from "@/stores/ui-store";

/** Throwaway preview for the list task; deleted at integration. */
export default function ListPreviewPage() {
  const state = useUIStore();
  return (
    <div className="flex h-dvh">
      <div className="flex-1 space-y-2 p-4 text-sm">
        <button className="rounded border px-2 py-1" onClick={() => state.selectPlz("5000")}>Select 5000</button>
        <button className="ml-2 rounded border px-2 py-1" onClick={() => state.setSearchQuery("baden")}>Search baden</button>
        <pre className="text-xs text-muted-foreground">
          {JSON.stringify({ selectedPlz: state.selectedPlz, selectedBuildingId: state.selectedBuildingId, isDetailOpen: state.isDetailOpen }, null, 2)}
        </pre>
      </div>
      <aside className="w-[400px] border-l">
        <BuildingList />
      </aside>
    </div>
  );
}
```

Run `npm run dev`, open `http://localhost:3000/dev/list`. Confirm: 120 cards scroll; "Select 5000" filters and shows "Show all areas"; clicking a card highlights it and the readout shows `isDetailOpen: true`.

- [ ] **Step 6: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/components/buildings src/app/dev/list
git commit -m "feat(frontend): add building list with area header and probability chips

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Detail sheet — prediction cards, why popover, explanation, technical details

**Files:**
- Create: `src/components/detail/prediction-card.tsx`, `src/components/detail/prediction-cards.tsx`, `src/components/detail/why-popover.tsx`, `src/components/detail/prediction-explanation.tsx`, `src/components/detail/technical-details.tsx`, `src/components/detail/building-detail-sheet.tsx`, `src/app/dev/detail/page.tsx`
- Test: `src/components/detail/why-popover.test.tsx`, `src/components/detail/technical-details.test.tsx`, `src/components/detail/building-detail-sheet.test.tsx`

**Interfaces:**
- Consumes: `useSelectedBuilding` (Task 4); `ElectricityChart` stub props `{ electricity, events, className? }` (Task 4 — do not modify that file); `ASSETS`, `ASSET_BY_KEY`, `getPredictionLabel`, `formatProbability` (Task 2); `useUIStore` (`isDetailOpen`, `closeDetail`); shadcn `Sheet*`, `Popover*`, `Collapsible*`, `Badge`, `buttonVariants`.
- Produces: `<BuildingDetailSheet />` (prop-less); `topContributions(shap, max?)`; `formatContribution(value)`.

- [ ] **Step 1: Read `src/components/ui/sheet.tsx`, `popover.tsx`, `collapsible.tsx`**

Note: `SheetContent` takes `side`; `PopoverTrigger` renders a `<button>` and accepts `className`; `CollapsibleTrigger` gets `data-panel-open` when open.

- [ ] **Step 2: Write the failing popover test `src/components/detail/why-popover.test.tsx`**

```tsx
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
    await userEvent.click(screen.getByRole("button", { name: "Why EV?" }));
    expect(await screen.findByText("Why EV is possible")).toBeInTheDocument();
    expect(screen.getByText("Repeated high-power events")).toBeInTheDocument();
    expect(screen.getByText("High nighttime power peak")).toBeInTheDocument();
    expect(screen.getByText("+0.30")).toBeInTheDocument();
    expect(screen.queryByText("Counter feature")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run to verify failure, then create `src/components/detail/why-popover.tsx`**

Run: `npx vitest run src/components/detail/why-popover.test.tsx` → FAIL.

```tsx
"use client";

import { Check } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ASSET_BY_KEY, getPredictionLabel } from "@/lib/predictions";
import type { AssetExplanation, AssetKey, ShapFeature } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_BARS = 3;

/** Positive contributions only, largest first, at most `max`. */
export function topContributions(shap: ShapFeature[], max = MAX_BARS): ShapFeature[] {
  return shap
    .filter((item) => item.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, max);
}

type WhyPopoverProps = { assetKey: AssetKey; probability: number; explanation: AssetExplanation };

export function WhyPopover({ assetKey, probability, explanation }: WhyPopoverProps) {
  const meta = ASSET_BY_KEY[assetKey];
  const label = getPredictionLabel(probability).toLowerCase();
  const bars = topContributions(explanation.shap);
  const maxContribution = Math.max(0.01, ...bars.map((bar) => bar.contribution));

  return (
    <Popover>
      <PopoverTrigger
        aria-label={`Why ${meta.shortLabel}?`}
        className={cn(buttonVariants({ variant: "link", size: "xs" }), "h-auto px-0")}
      >
        Why?
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72">
        <div className="text-sm font-semibold">
          Why {meta.shortLabel} is {label}
        </div>
        <ul className="mt-2 space-y-1.5 text-sm">
          {explanation.reasons.map((reason) => (
            <li key={reason} className="flex gap-2">
              <Check className="mt-0.5 size-4 shrink-0 text-accent-foreground" aria-hidden />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
        {bars.length > 0 && (
          <div className="mt-3">
            <div className="text-xs font-medium text-muted-foreground">SHAP contribution</div>
            <ul className="mt-1.5 space-y-1.5">
              {bars.map((bar) => (
                <li key={bar.feature} className="text-xs">
                  <div className="flex justify-between gap-2">
                    <span>{bar.feature}</span>
                    <span className="tabular-nums">+{bar.contribution.toFixed(2)}</span>
                  </div>
                  <div className="mt-0.5 h-1.5 rounded-full bg-muted">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.round((bar.contribution / maxContribution) * 100)}%`,
                        backgroundColor: meta.color,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
```

Run: `npx vitest run src/components/detail/why-popover.test.tsx` → PASS.

- [ ] **Step 4: Create the prediction cards**

```tsx
// src/components/detail/prediction-card.tsx
"use client";

import { WhyPopover } from "@/components/detail/why-popover";
import { Badge } from "@/components/ui/badge";
import { ASSET_BY_KEY, formatProbability, getPredictionLabel, type PredictionLabel } from "@/lib/predictions";
import type { AssetExplanation, AssetKey } from "@/lib/types";

const LABEL_VARIANT: Record<PredictionLabel, "default" | "secondary" | "outline"> = {
  Likely: "default",
  Possible: "secondary",
  Unlikely: "outline",
};

type PredictionCardProps = { assetKey: AssetKey; probability: number; explanation: AssetExplanation };

export function PredictionCard({ assetKey, probability, explanation }: PredictionCardProps) {
  const meta = ASSET_BY_KEY[assetKey];
  const Icon = meta.icon;
  const label = getPredictionLabel(probability);
  return (
    <div
      data-testid={`prediction-card-${assetKey}`}
      className="flex flex-col gap-2 rounded-xl bg-card p-3 ring-1 ring-foreground/10"
    >
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon className="size-4" style={{ color: meta.color }} aria-hidden />
        {meta.label}
      </div>
      <div className="text-2xl font-semibold tabular-nums">{formatProbability(probability)}</div>
      <div className="flex items-center justify-between gap-2">
        <Badge variant={LABEL_VARIANT[label]}>{label}</Badge>
        <WhyPopover assetKey={assetKey} probability={probability} explanation={explanation} />
      </div>
    </div>
  );
}
```

```tsx
// src/components/detail/prediction-cards.tsx
import { PredictionCard } from "@/components/detail/prediction-card";
import { ASSETS } from "@/lib/predictions";
import type { AssetPrediction, BuildingExplanation } from "@/lib/types";

type PredictionCardsProps = { predictions: AssetPrediction; explanation: BuildingExplanation };

/** Exactly four cards, always PV, Battery, Heat pump, EV. */
export function PredictionCards({ predictions, explanation }: PredictionCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {ASSETS.map((asset) => (
        <PredictionCard
          key={asset.key}
          assetKey={asset.key}
          probability={predictions[asset.key]}
          explanation={explanation.assets[asset.key]}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Create `src/components/detail/prediction-explanation.tsx`**

```tsx
/** Static for the MVP (task doc §12); the sentence on the model is generic on purpose. */
export function PredictionExplanation() {
  return (
    <section className="rounded-xl bg-muted/50 p-4 text-sm leading-relaxed">
      <h3 className="mb-1 font-semibold">How is this calculated?</h3>
      <p className="text-foreground/90">
        The prediction is based on electricity meter measurements recorded every 15 minutes. The model looks for
        recurring patterns in the building&apos;s electricity consumption and compares them with patterns
        associated with known energy assets such as PV systems, EVs, heat pumps and batteries. Every result is a
        probability, not a confirmed installation.
      </p>
    </section>
  );
}
```

- [ ] **Step 6: Write the failing technical-details test, then the component**

```tsx
// src/components/detail/technical-details.test.tsx
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
```

Run: `npx vitest run src/components/detail/technical-details.test.tsx` → FAIL.

```tsx
// src/components/detail/technical-details.tsx
"use client";

import { ChevronDown } from "lucide-react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ASSETS, formatProbability } from "@/lib/predictions";
import type { AssetPrediction, BuildingExplanation } from "@/lib/types";
import { cn } from "@/lib/utils";

/** "+0.31" / "−0.04" (typographic minus). */
export function formatContribution(value: number): string {
  return `${value < 0 ? "−" : "+"}${Math.abs(value).toFixed(2)}`;
}

type TechnicalDetailsProps = { explanation: BuildingExplanation; predictions: AssetPrediction };

export function TechnicalDetails({ explanation, predictions }: TechnicalDetailsProps) {
  return (
    <Collapsible>
      <CollapsibleTrigger className="group flex items-center gap-1 text-sm font-medium text-primary hover:underline">
        Show technical details
        <ChevronDown className="size-4 transition-transform group-data-[panel-open]:rotate-180" aria-hidden />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-3 space-y-4 text-sm">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-muted-foreground">Model</dt>
          <dd>{explanation.model}</dd>
          <dt className="text-muted-foreground">Input</dt>
          <dd>{explanation.inputs.join(", ")}</dd>
          <dt className="text-muted-foreground">Additional data</dt>
          <dd>{explanation.additionalData.join(", ") || "None"}</dd>
          <dt className="text-muted-foreground">Explainability</dt>
          <dd>
            {explanation.method} — {explanation.methodDescription}
          </dd>
        </dl>
        <div className="grid gap-3 sm:grid-cols-2">
          {ASSETS.map((asset) => (
            <div key={asset.key} className="rounded-lg bg-muted/50 p-3">
              <div className="mb-1.5 text-xs font-semibold">
                {asset.shortLabel} prediction: {formatProbability(predictions[asset.key])}
              </div>
              <ul className="space-y-0.5 font-mono text-xs">
                {explanation.assets[asset.key].shap.map((item) => (
                  <li key={item.feature} className="flex justify-between gap-2">
                    <span>{item.feature}</span>
                    <span className={cn("tabular-nums", item.contribution < 0 ? "text-destructive" : "text-accent-foreground")}>
                      {formatContribution(item.contribution)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
```

Run: `npx vitest run src/components/detail/technical-details.test.tsx` → PASS.

- [ ] **Step 7: Write the failing sheet test `src/components/detail/building-detail-sheet.test.tsx`**

```tsx
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
    expect(screen.getByText("How is this calculated?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show technical details/ })).toBeInTheDocument();
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
```

- [ ] **Step 8: Run to verify failure, then create `src/components/detail/building-detail-sheet.tsx`**

Run: `npx vitest run src/components/detail/building-detail-sheet.test.tsx` → FAIL.

```tsx
"use client";

import { ElectricityChart } from "@/components/chart/electricity-chart";
import { PredictionCards } from "@/components/detail/prediction-cards";
import { PredictionExplanation } from "@/components/detail/prediction-explanation";
import { TechnicalDetails } from "@/components/detail/technical-details";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useSelectedBuilding } from "@/hooks/use-buildings";
import { useUIStore } from "@/stores/ui-store";

/** Desktop width per spec D6; the inline style beats the generated `sm:max-w-sm`. */
const SHEET_STYLE = { width: "min(100vw, 640px)", maxWidth: "none" } as const;

export function BuildingDetailSheet() {
  const building = useSelectedBuilding();
  const isDetailOpen = useUIStore((s) => s.isDetailOpen);
  const closeDetail = useUIStore((s) => s.closeDetail);
  const open = isDetailOpen && building !== undefined;

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) closeDetail();
      }}
    >
      <SheetContent side="right" className="overflow-y-auto" style={SHEET_STYLE}>
        {building && (
          <>
            <SheetHeader>
              <SheetTitle>Building {building.id}</SheetTitle>
              <SheetDescription>
                {building.postcode} {building.city}, {building.canton}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-6 px-4 pb-6">
              <PredictionCards predictions={building.predictions} explanation={building.explanation} />
              <section>
                <h3 className="mb-2 text-sm font-semibold">Electricity profile — Last 24 hours</h3>
                <ElectricityChart electricity={building.electricity} events={building.events} />
              </section>
              <PredictionExplanation />
              <TechnicalDetails explanation={building.explanation} predictions={building.predictions} />
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
```

Run: `npx vitest run src/components/detail` → PASS. If the close button has a different accessible name, read `sheet.tsx` (it renders `<span className="sr-only">Close</span>`) and adjust only the test query, not the component.

- [ ] **Step 9: Create the preview page `src/app/dev/detail/page.tsx`**

```tsx
"use client";

import { BuildingDetailSheet } from "@/components/detail/building-detail-sheet";
import { useUIStore } from "@/stores/ui-store";

/** Throwaway preview for the detail task; deleted at integration. */
export default function DetailPreviewPage() {
  const selectBuilding = useUIStore((s) => s.selectBuilding);
  return (
    <div className="p-6">
      <button className="rounded border px-3 py-1.5 text-sm" onClick={() => selectBuilding("AG-004711")}>
        Open demo building
      </button>
      <BuildingDetailSheet />
    </div>
  );
}
```

Run `npm run dev`, open `http://localhost:3000/dev/detail`, click the button. Confirm: sheet slides in at 640 px; four cards in order with 92 / 48 / 31 / 76 and Likely / Unlikely / Unlikely / Possible; "Why?" opens a popover with three bars; the chart area is an empty 260 px box (stub, expected); technical details expand. Escape and the ✕ close it.

- [ ] **Step 10: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/components/detail src/app/dev/detail
git commit -m "feat(frontend): add building detail sheet with predictions and explanations

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Electricity chart — ECharts option builder, event bands, legend

**Files:**
- Create: `src/lib/chart-option.ts`, `src/components/chart/chart-legend.tsx`, `src/app/dev/chart/page.tsx`
- Modify: `src/components/chart/electricity-chart.tsx` (replace the stub body; keep the exported name, props type and the `data-testid`/`data-points`/`data-events` attributes)
- Test: `src/lib/chart-option.test.ts`, `src/components/chart/electricity-chart.test.tsx`

**Interfaces:**
- Consumes: `EVENT_META`, `EVENT_BAND_OPACITY` (Task 2); `ElectricityPoint`, `BuildingEvent`.
- Produces: `buildChartOption`, `eventsToBands`, `minutesFromStart`, `formatHourTick`, `formatClock`, `hexToRgba`, `LINE_COLOR`, `DAY_MINUTES`, `TICK_MINUTES`; `<ElectricityChart electricity events className? />` now renders the real chart **and** its `ChartLegend` beneath it (so Task 8 needs no change).

- [ ] **Step 1: Write the failing option tests `src/lib/chart-option.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import {
  buildChartOption,
  DAY_MINUTES,
  eventsToBands,
  formatClock,
  formatHourTick,
  hexToRgba,
  minutesFromStart,
  TICK_MINUTES,
} from "@/lib/chart-option";
import { makeBuilding } from "@/test/fixtures";

const startMs = Date.parse("2026-09-09T00:00:00+02:00");

describe("time helpers", () => {
  it("converts timestamps to minutes from the series start", () => {
    expect(minutesFromStart("2026-09-09T22:15:00+02:00", startMs)).toBe(1335);
    expect(minutesFromStart("2026-09-10T01:30:00+02:00", startMs)).toBe(1530);
  });

  it("formats ticks as two-digit hours and clock times as HH:MM", () => {
    expect(formatHourTick(0)).toBe("00");
    expect(formatHourTick(240)).toBe("04");
    expect(formatHourTick(1440)).toBe("24");
    expect(formatClock(1335)).toBe("22:15");
    expect(formatClock(5)).toBe("00:05");
  });

  it("converts hex to rgba", () => {
    expect(hexToRgba("#2563eb", 0.14)).toBe("rgba(37, 99, 235, 0.14)");
  });
});

describe("eventsToBands", () => {
  it("splits an event crossing midnight into a tail band and a head band", () => {
    const bands = eventsToBands(
      [{ type: "ev_charging", start: "2026-09-09T22:15:00+02:00", end: "2026-09-10T01:30:00+02:00" }],
      startMs,
    );
    expect(bands.map((b) => [b.startMin, b.endMin])).toEqual([
      [1335, 1440],
      [0, 90],
    ]);
    expect(bands.every((b) => b.label === "EV charging")).toBe(true);
  });

  it("clips bands to the day and drops events entirely outside it", () => {
    const bands = eventsToBands(
      [
        { type: "pv_generation", start: "2026-09-08T23:00:00+02:00", end: "2026-09-09T00:30:00+02:00" },
        { type: "high_consumption", start: "2026-09-11T10:00:00+02:00", end: "2026-09-11T12:00:00+02:00" },
      ],
      startMs,
    );
    expect(bands.map((b) => [b.type, b.startMin, b.endMin])).toEqual([
      ["pv_generation", 0, 30],
      ["pv_generation", 1380, 1440],
    ]);
  });
});

describe("buildChartOption", () => {
  const building = makeBuilding();
  const option = buildChartOption(building.electricity, building.events);

  it("uses a 0..1440 value axis with 4-hour ticks and no animation", () => {
    const xAxis = option.xAxis as { min: number; max: number; interval: number };
    expect(xAxis.min).toBe(0);
    expect(xAxis.max).toBe(DAY_MINUTES);
    expect(xAxis.interval).toBe(TICK_MINUTES);
    expect(option.animation).toBe(false);
  });

  it("plots [minute, kW] pairs and one markArea per band", () => {
    const [series] = option.series as Array<{ data: [number, number][]; markArea: { data: unknown[] } }>;
    expect(series.data).toEqual([
      [0, 0.4],
      [15, 0.5],
      [30, 7.2],
    ]);
    expect(series.markArea.data).toHaveLength(3); // EV tail + EV head + PV
  });

  it("handles an empty series", () => {
    const empty = buildChartOption([], []);
    const [series] = empty.series as Array<{ data: unknown[] }>;
    expect(series.data).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify failure, then create `src/lib/chart-option.ts`**

Run: `npx vitest run src/lib/chart-option.test.ts` → FAIL.

```ts
import type { EChartsOption } from "echarts";

import { EVENT_BAND_OPACITY, EVENT_META } from "@/lib/events";
import type { BuildingEvent, BuildingEventType, ElectricityPoint } from "@/lib/types";

export const DAY_MINUTES = 1440;
export const TICK_MINUTES = 240;
export const LINE_COLOR = "#1e3a5f";
const GRID_COLOR = "#e2e8f0";
const AXIS_TEXT_COLOR = "#64748b";

export function minutesFromStart(iso: string, startMs: number): number {
  return (Date.parse(iso) - startMs) / 60_000;
}

/** 0 → "00", 240 → "04", 1440 → "24". */
export function formatHourTick(minute: number): string {
  return String(Math.round(minute / 60)).padStart(2, "0");
}

/** 1335 → "22:15". */
export function formatClock(minute: number): string {
  const whole = Math.round(minute);
  const hh = String(Math.floor(whole / 60)).padStart(2, "0");
  const mm = String(whole % 60).padStart(2, "0");
  return `${hh}:${mm}`;
}

export function hexToRgba(hex: string, alpha: number): string {
  const value = Number.parseInt(hex.slice(1), 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export type EventBand = {
  type: BuildingEventType;
  label: string;
  color: string;
  startMin: number;
  endMin: number;
};

/**
 * Converts events to minute bands inside [0, DAY_MINUTES]. A band that runs past
 * the day end keeps its in-day part and folds the overflow to the start of the
 * day (the previous night's tail); a band that starts before the day folds
 * symmetrically. Empty bands are dropped.
 */
export function eventsToBands(events: BuildingEvent[], startMs: number): EventBand[] {
  const bands: EventBand[] = [];
  for (const event of events) {
    const meta = EVENT_META[event.type];
    const start = minutesFromStart(event.start, startMs);
    const end = minutesFromStart(event.end, startMs);
    const segments: [number, number][] = [[Math.max(0, start), Math.min(DAY_MINUTES, end)]];
    if (end > DAY_MINUTES) segments.push([0, Math.min(DAY_MINUTES, end - DAY_MINUTES)]);
    if (start < 0) segments.push([Math.max(0, start + DAY_MINUTES), DAY_MINUTES]);
    for (const [segmentStart, segmentEnd] of segments) {
      if (segmentEnd > segmentStart) {
        bands.push({ type: event.type, label: meta.label, color: meta.color, startMin: segmentStart, endMin: segmentEnd });
      }
    }
  }
  return bands;
}

type AxisTooltipParam = { value: [number, number] };

function tooltipFormatter(params: unknown): string {
  const list = (Array.isArray(params) ? params : [params]) as AxisTooltipParam[];
  const first = list[0];
  if (!first) return "";
  const [minute, kw] = first.value;
  return `${formatClock(minute)} · ${kw.toFixed(2)} kW`;
}

export function buildChartOption(electricity: ElectricityPoint[], events: BuildingEvent[]): EChartsOption {
  const startMs = electricity.length > 0 ? Date.parse(electricity[0].timestamp) : 0;
  const data = electricity.map((point): [number, number] => [minutesFromStart(point.timestamp, startMs), point.powerKw]);
  const bands = electricity.length > 0 ? eventsToBands(events, startMs) : [];

  return {
    animation: false,
    grid: { left: 48, right: 16, top: 28, bottom: 28 },
    tooltip: { trigger: "axis", formatter: tooltipFormatter },
    xAxis: {
      type: "value",
      min: 0,
      max: DAY_MINUTES,
      interval: TICK_MINUTES,
      axisLabel: { formatter: (value: number) => formatHourTick(value), color: AXIS_TEXT_COLOR },
      axisLine: { lineStyle: { color: GRID_COLOR } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      name: "kW",
      nameTextStyle: { color: AXIS_TEXT_COLOR, align: "right" },
      axisLabel: { color: AXIS_TEXT_COLOR },
      splitLine: { lineStyle: { color: GRID_COLOR } },
    },
    series: [
      {
        name: "Net power",
        type: "line",
        data,
        showSymbol: false,
        smooth: false,
        lineStyle: { width: 2, color: LINE_COLOR },
        itemStyle: { color: LINE_COLOR },
        markArea: {
          silent: true,
          data: bands.map((band) => [
            {
              name: band.label,
              xAxis: band.startMin,
              itemStyle: { color: hexToRgba(band.color, EVENT_BAND_OPACITY) },
              label: { show: true, position: "insideTop", color: band.color, fontSize: 11, fontWeight: 500 },
            },
            { xAxis: band.endMin },
          ]),
        },
      },
    ],
  };
}
```

Run: `npx vitest run src/lib/chart-option.test.ts` → PASS.

- [ ] **Step 3: Create `src/components/chart/chart-legend.tsx`**

```tsx
import { hexToRgba, LINE_COLOR } from "@/lib/chart-option";
import { EVENT_META } from "@/lib/events";
import type { BuildingEvent, BuildingEventType } from "@/lib/types";

export function ChartLegend({ events }: { events: BuildingEvent[] }) {
  const types = Array.from(new Set<BuildingEventType>(events.map((event) => event.type)));
  return (
    <ul aria-label="Chart legend" className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="inline-block h-0.5 w-4 rounded" style={{ backgroundColor: LINE_COLOR }} />
        Net power
      </li>
      {types.map((type) => (
        <li key={type} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block size-3 rounded-sm"
            style={{ backgroundColor: hexToRgba(EVENT_META[type].color, 0.35) }}
          />
          {EVENT_META[type].label}
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 4: Write the failing chart component test `src/components/chart/electricity-chart.test.tsx`**

```tsx
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
```

- [ ] **Step 5: Run to verify failure, then replace the stub `src/components/chart/electricity-chart.tsx`**

Run: `npx vitest run src/components/chart` → FAIL (no `echarts` testid).

```tsx
"use client";

import ReactECharts from "echarts-for-react";
import { useMemo } from "react";

import { ChartLegend } from "@/components/chart/chart-legend";
import { buildChartOption } from "@/lib/chart-option";
import type { BuildingEvent, ElectricityPoint } from "@/lib/types";
import { cn } from "@/lib/utils";

const CHART_HEIGHT = 260;

export type ElectricityChartProps = {
  electricity: ElectricityPoint[];
  events: BuildingEvent[];
  className?: string;
};

/**
 * 24h net-power line with event bands (task doc §10–§11). Only ever mounted
 * inside the client-side detail sheet, so no dynamic import is needed.
 */
export function ElectricityChart({ electricity, events, className }: ElectricityChartProps) {
  const option = useMemo(() => buildChartOption(electricity, events), [electricity, events]);
  return (
    <div
      data-testid="electricity-chart"
      data-points={electricity.length}
      data-events={events.length}
      className={cn("space-y-2", className)}
    >
      <ReactECharts option={option} notMerge style={{ height: CHART_HEIGHT, width: "100%" }} opts={{ renderer: "svg" }} />
      <ChartLegend events={events} />
    </div>
  );
}
```

Run: `npx vitest run src/components/chart` → PASS.

- [ ] **Step 6: Create the preview page `src/app/dev/chart/page.tsx`**

```tsx
"use client";

import { ElectricityChart } from "@/components/chart/electricity-chart";
import { generateMockBuildings } from "@/lib/mock-data";

const [demo, ...others] = generateMockBuildings();

/** Throwaway preview for the chart task; deleted at integration. */
export default function ChartPreviewPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <section>
        <h2 className="mb-2 text-sm font-semibold">Demo building {demo.id}</h2>
        <ElectricityChart electricity={demo.electricity} events={demo.events} />
      </section>
      {others.slice(0, 3).map((building) => (
        <section key={building.id}>
          <h2 className="mb-2 text-sm font-semibold">{building.id}</h2>
          <ElectricityChart electricity={building.electricity} events={building.events} />
        </section>
      ))}
    </div>
  );
}
```

Run `npm run dev`, open `http://localhost:3000/dev/chart`. Confirm on the demo chart: ticks `00 04 08 12 16 20 24`; a navy line with a 7 kW plateau from 22:15 to 24:00 and from 00:00 to 01:30; a negative dip around midday; two blue "EV charging" bands and one amber "Possible PV generation" band, all subtle; the tooltip reads like `22:30 · 7.85 kW`. Screenshot for the report.

- [ ] **Step 7: Full check and commit**

Run: `npm run check` — expected green.

```bash
git add src/lib/chart-option.ts src/lib/chart-option.test.ts src/components/chart src/app/dev/chart
git commit -m "feat(frontend): add 24h electricity chart with event bands and legend

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

**Wave 1 exit gate (controller):** each of the five branches reviewed with the SDD task review; each reports `npm run check` green and a preview screenshot or description. Collect any "request for Task 10" notes from the reports and hand them to Task 10.

---

## Wave 2 — Integration, end-to-end, review, cleanup (sequential, integration branch)

### Task 10: Merge Wave 1, build the app shell, remove scaffolding

**Files:**
- Merge: branches `feat/ef-header`, `feat/ef-map`, `feat/ef-list`, `feat/ef-detail`, `feat/ef-chart` into `feat/frontend-energy-map`
- Create: `src/components/app-shell.tsx`
- Modify: `src/app/page.tsx` (replace scaffold), `src/app/layout.tsx` (body classes only)
- Delete: `src/app/dev/` (all preview pages)
- Test: `src/components/app-shell.test.tsx`

**Interfaces:**
- Consumes: `<AppHeader />`, `<AboutDialog />` (Task 5); `<MapView />` (Task 6); `<BuildingList />` (Task 7); `<BuildingDetailSheet />` (Task 8); `useUIStore` (`viewMode`).
- Produces: the working `/` route.

- [ ] **Step 1: Merge the five branches**

From `frontend/` in the integration worktree:

```bash
git merge --no-ff feat/ef-header -m "merge: header (Task 5)"
git merge --no-ff feat/ef-map -m "merge: map (Task 6)"
git merge --no-ff feat/ef-list -m "merge: building list (Task 7)"
git merge --no-ff feat/ef-detail -m "merge: detail sheet (Task 8)"
git merge --no-ff feat/ef-chart -m "merge: electricity chart (Task 9)"
npm ci
npm run check
```

Expected: no conflicts (file ownership is disjoint; the only file two tasks touch is `electricity-chart.tsx`, owned by Task 9 alone after Wave 0). If a conflict appears, stop and report it — do not resolve by picking a side blindly. Apply any "request for Task 10" notes from the Wave 1 reports here, each as its own commit.

- [ ] **Step 2: Write the failing shell test `src/components/app-shell.test.tsx`**

```tsx
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

vi.mock("next/dynamic", () => ({
  default: () => {
    function MapPlaceholder() {
      return <div data-testid="map-view" />;
    }
    return MapPlaceholder;
  },
}));

vi.mock("@/lib/api", () => ({ fetchBuildings: async () => [makeBuilding()] }));

describe("AppShell", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("shows header, map and list in map mode", async () => {
    renderWithProviders(<AppShell />);
    expect(screen.getByText("Energy Fingerprints")).toBeInTheDocument();
    expect(screen.getByTestId("map-view")).toBeInTheDocument();
    expect(await screen.findByText("Building AG-000001")).toBeInTheDocument();
    expect(screen.getByTestId("list-panel")).toHaveAttribute("data-mode", "map");
  });

  it("hides the map and widens the list in list mode", async () => {
    useUIStore.getState().setViewMode("list");
    renderWithProviders(<AppShell />);
    expect(screen.queryByTestId("map-view")).not.toBeInTheDocument();
    expect(screen.getByTestId("list-panel")).toHaveAttribute("data-mode", "list");
  });
});
```

- [ ] **Step 3: Run to verify failure, then create `src/components/app-shell.tsx`**

Run: `npx vitest run src/components/app-shell.test.tsx` → FAIL.

```tsx
"use client";

import dynamic from "next/dynamic";

import { BuildingList } from "@/components/buildings/building-list";
import { BuildingDetailSheet } from "@/components/detail/building-detail-sheet";
import { AboutDialog } from "@/components/header/about-dialog";
import { AppHeader } from "@/components/header/app-header";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";

/** MapLibre touches `window` at import time; load it on the client only (spec D2). */
const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-muted" aria-label="Loading map" />,
});

/**
 * Layout per spec D12: desktop map mode = map 65 / list 35; desktop list mode = list
 * full width; mobile shows exactly one of the two.
 */
export function AppShell() {
  const viewMode = useUIStore((s) => s.viewMode);
  const showMap = viewMode === "map";

  return (
    <div className="flex h-dvh flex-col">
      <AppHeader />
      <div className="flex min-h-0 flex-1">
        {showMap && (
          <div className="relative min-h-0 flex-1 lg:basis-[65%]">
            <MapView />
          </div>
        )}
        <aside
          data-testid="list-panel"
          data-mode={viewMode}
          className={cn(
            "min-h-0 bg-background",
            showMap ? "hidden border-l lg:flex lg:w-[35%] lg:max-w-md lg:flex-col" : "flex flex-1 flex-col",
          )}
        >
          <BuildingList />
        </aside>
      </div>
      <BuildingDetailSheet />
      <AboutDialog />
    </div>
  );
}
```

Run: `npx vitest run src/components/app-shell.test.tsx` → PASS.

- [ ] **Step 4: Replace `src/app/page.tsx` and trim `src/app/layout.tsx`**

`src/app/page.tsx` becomes:

```tsx
import { AppShell } from "@/components/app-shell";

export default function Home() {
  return <AppShell />;
}
```

In `src/app/layout.tsx`, change the `<body>` class from `min-h-full flex flex-col` to `h-full overflow-hidden` so the shell owns scrolling. Leave everything else as is.

- [ ] **Step 5: Delete the preview pages**

```bash
git rm -r src/app/dev
```

Confirm nothing imports from `@/app/dev` (`grep -r "app/dev" src` returns nothing).

- [ ] **Step 6: Full check, production build, and browser smoke**

```bash
npm run check
npm run build
```

Expected: both green; the build lists only `/` (plus `_not-found`). Then `npm run dev`, open `http://localhost:3000` and walk spec §11 steps 1–7 by hand (or with the browser tools). Verify on a narrow viewport (375 px) that the toggle switches between map and list with no horizontal scroll.

- [ ] **Step 7: Commit**

```bash
git add src/components/app-shell.tsx src/components/app-shell.test.tsx src/app/page.tsx src/app/layout.tsx
git commit -m "feat(frontend): integrate map, list, detail and header into the app shell

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(The `git rm -r src/app/dev` from Step 5 is staged already; include it in this commit.)

---

### Task 11: Playwright demo flow and documentation

**Files:**
- Create: `e2e/demo-flow.spec.ts`
- Delete: `e2e/.gitkeep`
- Modify: `frontend/README.md` (structure + scripts), `frontend/docs/energy-fingerprints-task.md` (§16 checkboxes and a short "Adaptation" note at the top)

**Interfaces:**
- Consumes: the integrated `/` route; demo building `AG-004711`; texts from Tasks 5–9.

- [ ] **Step 1: Ensure Chromium is installed**

Run: `npx playwright install chromium` (pre-flight; skip if already done).

- [ ] **Step 2: Write `e2e/demo-flow.spec.ts`**

```ts
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
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByText("Building AG-004711")).toBeVisible();
    await expect(sheet.getByText("5000 Aarau, AG")).toBeVisible();
    await expect(sheet.getByTestId("prediction-card-pv")).toContainText(["92%", "Likely"]);
    await expect(sheet.getByTestId("prediction-card-battery")).toContainText(["48%", "Unlikely"]);
    await expect(sheet.getByTestId("prediction-card-heatPump")).toContainText(["31%", "Unlikely"]);
    await expect(sheet.getByTestId("prediction-card-ev")).toContainText(["76%", "Possible"]);
    await expect(card).toHaveAttribute("aria-pressed", "true");

    // 4. Fingerprint chart with both band labels rendered by ECharts (SVG renderer)
    const chart = sheet.getByTestId("electricity-chart");
    await expect(chart.locator("svg")).toBeVisible();
    await expect(chart.getByText("EV charging").first()).toBeVisible();
    await expect(chart.getByText("Possible PV generation").first()).toBeVisible();

    // 5. Why? popover for EV
    await sheet.getByRole("button", { name: "Why EV?" }).click();
    await expect(page.getByText("Why EV is possible")).toBeVisible();
    await expect(page.getByText("Repeated high-power events")).toBeVisible();
    await page.keyboard.press("Escape");

    // 6. Technical details
    await sheet.getByRole("button", { name: /Show technical details/ }).click();
    await expect(sheet.getByText("EV prediction: 76%")).toBeVisible();
    await expect(sheet.getByText("+0.31")).toBeVisible();

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
```

- [ ] **Step 3: Run the e2e test**

Run: `npm run test:e2e`
Expected: 2 passed. If the band labels are not found, check that `ElectricityChart` passes `opts={{ renderer: "svg" }}` (Task 9) — the canvas renderer has no text nodes. If Escape does not close the popover, replace the `Escape` press with a click on the sheet title.

- [ ] **Step 4: Update `frontend/README.md`**

Replace the "Project structure" block and the "Getting started" scripts line with:

````markdown
## Getting started

```bash
npm install            # first time only
npm run dev            # http://localhost:3000
npm run check          # lint + typecheck + unit tests
npm run test:e2e       # Playwright demo flow (needs `npx playwright install chromium` once)
```

## Project structure

```
src/
  app/                 # App Router: layout, single page
  components/
    app-shell.tsx      # header + map + list + detail layout, view mode
    header/            # wordmark, area select, search, view toggle, about dialog
    map/               # MapLibre PLZ areas, tooltip
    buildings/         # list panel, area header, building cards, chips
    detail/            # detail sheet, prediction cards, why popover, SHAP details
    chart/             # ECharts 24h fingerprint + legend
    ui/                # shadcn/ui (generated)
  data/aargau-plz.json # PLZ polygons (swisstopo, built by scripts/build-plz-geojson.sh)
  hooks/               # TanStack Query hooks and derived selectors
  lib/                 # pure domain logic: types, predictions, search, chart option, mock data, PLZ
  stores/ui-store.ts   # Zustand UI state
  test/                # Vitest setup, render helper, fixtures
e2e/                   # Playwright demo flow
docs/                  # task doc
```

## Data

The UI runs on deterministic mock data (`src/lib/mock-data.ts`, seed 42) shaped like the
future backend contract (`src/lib/types.ts`). `src/lib/api.ts` is the single swap point for a
real endpoint. Buildings are anonymised IDs with a postal code; the map shows PLZ areas, not
addresses. Basemap tiles come from OpenFreeMap (internet required); override with
`NEXT_PUBLIC_MAP_STYLE_URL`.
````

Keep the "Stack" and "Conventions" sections.

- [ ] **Step 5: Update the task doc**

At the top of `frontend/docs/energy-fingerprints-task.md`, after the blockquote, add:

```markdown
> **Adaptation (2026-09-10):** the data has no addresses or coordinates — only anonymised
> building IDs with a postal code and town. The map therefore shows outlined PLZ areas
> instead of building markers, and buildings are listed by ID. Binding
> decisions live in `docs/superpowers/specs/2026-09-10-energy-fingerprints-frontend-design.md`.
```

Tick every box in §16 "Required" that is now implemented (all of them), and change the two address-based items to read "Aargau PLZ map (MapLibre GL) with area selection" and "Building list panel (by ID), synced with the map".

- [ ] **Step 6: Full check and commit**

```bash
npm run check
git rm e2e/.gitkeep
git add e2e/demo-flow.spec.ts README.md docs/energy-fingerprints-task.md
git commit -m "test(frontend): add Playwright demo flow; update docs for PLZ-based design

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Final review, simplification pass, cleanup, PR

This task is executed by the controller with the SDD final-review procedure, not by a single implementer.

- [ ] **Step 1: Whole-branch review**

Run `scripts/review-package PLAN_FILE $(git merge-base main HEAD) HEAD` and dispatch the final reviewer (most capable model) with the package, the spec, and the ledger's deferred/parked lines. Also run the `/code-review` skill on the branch diff and the `/simplify` skill on the changed code; treat their output as additional findings. One fix dispatch for the complete findings list, one scoped re-review.

- [ ] **Step 2: Cleanup checklist (verify each, fix in the fix dispatch if not)**

- `src/app/dev/` does not exist.
- `grep -rn "console.log" src e2e` returns nothing.
- `grep -rn "TODO\|FIXME" src e2e` returns nothing.
- `grep -rn ": any\|as any" src` returns nothing.
- `npx knip` is not installed; instead confirm every exported symbol in `src/lib` and `src/hooks` is imported somewhere (`grep -rn "<name>" src`), and remove dead ones. `selectedCustomerId` must not exist anywhere.
- `package.json` has no dependency added beyond Task 1's dev dependencies (and `@types/geojson` if Task 2 needed it).
- `npm run check`, `npm run build`, `npm run test:e2e` all green on the integration branch.
- The Next agent-rules block in `AGENTS.md` is unchanged.

- [ ] **Step 3: Delete Wave 1 branches and worktrees**

```bash
for area in header map list detail chart; do
  git worktree remove --force ../OSNOVA-ef-$area 2>/dev/null || true
  git branch -D feat/ef-$area
done
git worktree prune
```

(If the harness created the worktrees under `.claude/worktrees/`, remove those paths instead.)

- [ ] **Step 4: Finish the branch**

Use superpowers:finishing-a-development-branch. Expected outcome: a PR from `feat/frontend-energy-map` to `main` with the spec and plan linked in the description, the e2e run summarised, and the "Rulings I made" list from the ledger.

---

## Self-review (done while writing)

**Spec coverage.** §5 contract → Task 2. §6.1–6.3 → Tasks 2, 3. §6.4 → Task 9. §6.5 → Task 4. §7 → Task 3. §8 → Task 4. §9 header → 5, map → 6, list → 7, detail → 8, chart → 9, shell → 10. §10 tokens → Task 3; map colours → Task 6. §11 demo flow → Task 11 (steps 2 via search; map click via Task 6 unit test). §12/§13 are documentation → Task 11. §14 hygiene → runbook + Task 12. Task doc §16 "Required" items all map to Tasks 5–10.

**Type consistency.** `selectBuilding(id)` (Task 3) used by Tasks 6, 7, 8 dev pages and list; `selectPlz(plz | null)` used by Tasks 6, 7; `useFilteredBuildings()` returns `{ buildings, total, isLoading, isError }` (Task 4) consumed in Task 7; `usePlzCounts`, `useHighlightedPlz` (Task 4) consumed in Task 6; `PlzCountProperties` (Task 2) consumed in Task 6; `ElectricityChart` props identical in Tasks 4, 8, 9; `describePrediction` output format "EV — 76% possible" asserted in Tasks 2 and 7; label variants `Likely | Possible | Unlikely` in Tasks 2, 8, 11.

**Known judgment calls left to the executing controller.** (a) Base-nova `Select` `items` shape (Task 5 gives both forms). (b) The sheet close-button accessible name (Task 8 Step 8 note). (c) Whether `@types/geojson` is needed (Task 2 Step 9 note). Record each as a ledger ruling.
