# Energy Fingerprints Frontend — Design Spec

**Date:** 2026-09-10
**Status:** Draft for review
**Source task:** [`frontend/docs/energy-fingerprints-task.md`](../../../frontend/docs/energy-fingerprints-task.md) (the "task doc"). This spec turns the task doc into concrete decisions and adapts it to one hard fact learned after it was written: **the data has no addresses and no coordinates.** Each customer is an anonymised ID with a postal code (PLZ) and a town name. Where this spec and the task doc disagree, this spec wins; every deviation is listed in §12.

## 1. Goal and scope

A single-screen Next.js demo that tells one story in under 30 seconds:

```
MAP (PLZ areas) → AREA → BUILDING (by ID) → ELECTRICITY → FINGERPRINT → PREDICTION → EXPLANATION
```

Deliverable is the task doc's §16 "Required" list, reinterpreted for PLZ-level geography, on mock data shaped like the future backend contract. Everything in the task doc's "Explicitly out of scope" list stays out. No authentication, no routes beyond `/`, no 3D, no building pins.

## 2. Decisions

Each decision names the option chosen and why. These are binding for implementers.

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| D1 | Basemap | MapLibre with the OpenFreeMap "positron" style, `https://tiles.openfreemap.org/styles/positron`, overridable via `NEXT_PUBLIC_MAP_STYLE_URL`. | Free, no API key, quiet light style (§17). Reachable at time of writing. Needs internet during the demo. |
| D2 | Geography | Buildings are **not** placed on the map. The map shows Aargau's PLZ areas as flat outlined polygons (pitch 0); only hover and selection change their look. | Data has only PLZ + ID. Outlined PLZ areas are honest about the data and give the map a real job: choosing an area. |
| D3 | PLZ boundaries | Real polygons from swisstopo's open "Amtliches Ortschaftenverzeichnis" (PLZ layer), clipped to canton AG, dissolved to one polygon per PLZ, simplified, WGS84, committed as `frontend/src/data/aargau-plz.json` (239 features, ~234 KB). Rebuilt by `frontend/scripts/build-plz-geojson.sh`. **Already done and verified** (5000 → Aarau). | User decision. One committed file, no runtime download. |
| D4 | Map colouring | No data colouring. Every PLZ area shares one light fill with thin borders; hovering tints the area; the highlighted area (selected area or the selected building's area) gets a strong outline. The hover tooltip still shows the building count. | User decision: keep the map quiet; choosing an area is the map's only job. |
| D5 | Area ↔ list ↔ building sync | Clicking a PLZ selects that area: the map highlights it and the list filters to it. Clicking a building card opens the detail sheet, highlights the building's PLZ on the map, and fits the map to that area; it does **not** change the area filter. Selecting an area clears any selected building. Clicking the map outside any PLZ clears the area filter. | Keeps the list stable while browsing buildings, keeps the map in sync with what is inspected. |
| D6 | Detail view | shadcn `Sheet` from the right, 640 px on desktop, full width on mobile, overlaying map and list. Title is the building ID; subtitle is "PLZ Town, AG". | One route, map stays visible behind the sheet. |
| D7 | Chart axis model | X axis is a numeric `value` axis in **minutes since the series start** (0..1440), ticks every 240 min labelled `00 04 08 12 16 20 24`. Series data is `[minute, kW]`. Events are converted to minute bands, clipped to `[0, 1440]`, and split when they cross midnight. | Deterministic, timezone-proof, unit-testable without ECharts. Meets §10's `00:00 → 24:00` axis. |
| D8 | Series window | Each building's `electricity` is one calendar day at 15-min resolution: 96 points from `2026-09-09T00:00+02:00` to `23:45`. | "Last 24 hours" and a `00→24` axis are both true only for a calendar-day window. Fixed date keeps mock data deterministic. |
| D9 | Mock determinism | Seeded PRNG (mulberry32, seed 42). Building 1 is a hand-authored demo building `AG-004711` in 5000 Aarau with PV 92 / Battery 48 / Heat pump 31 / EV 76, events EV 22:15→01:30 and PV 10:00→16:30. 120 buildings spread over ~20 Aargau PLZs; every PLZ used must exist in the GeoJSON (tested). | Demo flow and e2e tests depend on stable values. |
| D10 | Data layer | `fetchBuildings()` in `src/lib/api.ts` returns mock data behind a short artificial delay. `useBuildings()` wraps it in TanStack Query. Components never import mock data directly. | One-line swap to a real endpoint later. |
| D11 | State split | Zustand `ui-store` holds `selectedPlz`, `selectedBuildingId`, `isDetailOpen`, `viewMode`, `searchQuery`, `isAboutOpen`. TanStack Query holds building data. Derived values (filtered list, selected building, highlighted PLZ, counts per PLZ) are computed in hooks. Map hover state is local to the map component. | Repo convention. No duplicated state. |
| D12 | View mode | Desktop `map` mode: map 65% / list 35%. Desktop `list` mode: list full width. Mobile: the toggle shows exactly one of map or list. | Gives the toggle a job on desktop and delivers basic responsiveness without a second layout system. |
| D13 | Colours | Asset colours live once in TypeScript (`ASSETS[].color`) and are applied via inline style and to ECharts. Theme tokens live in `globals.css`. | ECharts cannot read CSS variables. |
| D14 | Test tooling | Vitest + jsdom + Testing Library (colocated `*.test.ts(x)`), Playwright (Chromium only) for the demo flow. `npm run check` = lint + typecheck + unit tests. | Repo has no test runner yet. |
| D15 | Typecheck | `npm run typecheck` = `next typegen && tsc --noEmit`. | `layout.tsx` uses Next 16's global `LayoutProps`, generated by `next typegen`. |
| D16 | Logo | Text wordmark ("AEW" tile + "Energy Fingerprints"). No logo file added. | No licensed asset in the repo; a team member can add `public/aew-logo.svg` later, the header has one slot for it. |
| D17 | Icons | PV `Sun`, Battery `BatteryCharging`, Heat pump `Flame`, EV `Car`, building `Building2` (all lucide). | Task doc emoji mapping. |
| D18 | Parallel work | Wave 0 (foundation) sequential on the integration branch. Wave 1 (header, map, list, detail, chart) as five agents in separate worktrees with disjoint file ownership. Wave 2 integrates, tests end to end, reviews, cleans up. | Parallel agents are safe only when the contract is frozen and nobody edits the same file. |
| D19 | Preview pages during Wave 1 | Each Wave 1 task adds a throwaway page `src/app/dev/<area>/page.tsx` for screenshots. Wave 2 deletes `src/app/dev/`. | Components are not on `/` until integration; agents still need a visual check. |
| D20 | Copy rule | Never state a prediction as fact. Use "likely / possible / unlikely" and "% likely". Enforced by a unit test on the describe function and by review. | Task doc §9. |

## 3. Architecture

Single route `/`. `page.tsx` stays a Server Component and renders one Client Component, `AppShell`, which lays out header, map, list, and sheet. Interactive pieces read the store and hooks directly; `AppShell` passes no data props, which keeps the five Wave 1 components independent.

```
page.tsx (server)
└── AppShell (client)
    ├── AppHeader ── AboutDialog
    ├── MapView (dynamic, ssr:false) ── PlzLayers, MapTooltip
    ├── BuildingList ── AreaHeader, BuildingCard ×N ── ProbabilityChip ×4
    └── BuildingDetailSheet
        ├── PredictionCards ── PredictionCard ×4 ── WhyPopover
        ├── ElectricityChart + ChartLegend
        ├── PredictionExplanation (static copy)
        └── TechnicalDetails (collapsible SHAP)
```

Data flow:

```
aargau-plz.json ──► PLZ_AREAS / PLZ_BY_CODE (lib/plz.ts)
fetchBuildings() ──► useBuildings() ──► useFilteredBuildings(selectedPlz, searchQuery) ──► BuildingList
                                   ├──► usePlzCounts() ──► MapView tooltip counts
                                   └──► useSelectedBuilding() ──► BuildingDetailSheet
useHighlightedPlz() = selectedBuilding?.postcode ?? selectedPlz ──► MapView highlight + fitBounds
```

## 4. File map and ownership

Ownership is binding in Wave 1: an agent may only create or edit files in its own rows.

| Path | Responsibility | Owner |
| --- | --- | --- |
| `frontend/package.json`, `vitest.config.ts`, `playwright.config.ts`, `src/test/setup.ts`, `src/test/render.tsx`, root `.gitignore` | Test tooling, scripts, ignore rules | W0 |
| `frontend/src/components/ui/{sheet,dialog,popover,collapsible,input,select,scroll-area,separator}.tsx` | shadcn components (generated, not hand-edited) | W0 |
| `frontend/src/data/aargau-plz.json`, `frontend/scripts/build-plz-geojson.sh`, `frontend/scripts/plz-lookup.mjs` | PLZ polygons and their build script | Done (committed with this spec) |
| `frontend/src/lib/types.ts` | Data contract | W0 |
| `frontend/src/lib/predictions.ts` | Thresholds, labels, asset metadata, marker-asset picker, copy helper | W0 |
| `frontend/src/lib/events.ts` | Event type metadata | W0 |
| `frontend/src/lib/plz.ts` | Typed PLZ areas, lookup, bbox, counts, GeoJSON with counts | W0 |
| `frontend/src/lib/random.ts` | Seeded PRNG | W0 |
| `frontend/src/lib/mock-data.ts` | Deterministic mock buildings, demo building | W0 |
| `frontend/src/lib/api.ts` | `fetchBuildings()` swap point | W0 |
| `frontend/src/hooks/use-buildings.ts` | Query hooks and derived selectors | W0 |
| `frontend/src/lib/search.ts` | Client-side filter | W0 |
| `frontend/src/stores/ui-store.ts` | UI state | W0 |
| `frontend/src/app/globals.css` | Theme tokens | W0 |
| `frontend/src/test/fixtures.ts` | `makeBuilding()` factory | W0 |
| `frontend/src/components/chart/electricity-chart.tsx` | Chart component (stub in W0, real in W1-chart) | W0 → W1-chart |
| `frontend/src/components/header/*` | Header, wordmark, area select, search, view toggle, about dialog | W1-header |
| `frontend/src/components/map/*` | Map, PLZ layers, tooltip, map constants | W1-map |
| `frontend/src/components/buildings/*` | List panel, area header, card, chip | W1-list |
| `frontend/src/components/detail/*` | Sheet, prediction cards, why popover, explanation, technical details | W1-detail |
| `frontend/src/lib/chart-option.ts`, `src/components/chart/*` | ECharts option builder, chart, legend | W1-chart |
| `frontend/src/app/dev/<area>/page.tsx` | Throwaway preview page per Wave 1 agent | W1-<area>, deleted by W2 |
| `frontend/src/components/app-shell.tsx`, `src/app/page.tsx` | Layout and integration | W2 |
| `frontend/e2e/demo-flow.spec.ts` | Playwright smoke of the demo flow (§11) | W2 |
| `frontend/README.md`, `frontend/docs/energy-fingerprints-task.md` (§16 checkboxes) | Docs | W2 |

## 5. Data contract

`src/lib/types.ts`. Adapts the task doc's §15: `address` and `location` are gone (the data has neither); `explanation` is added so §13 and §14 content also comes from data.

```ts
export const ASSET_KEYS = ["pv", "battery", "heatPump", "ev"] as const;
export type AssetKey = (typeof ASSET_KEYS)[number];

/** Probability per asset, 0–100. */
export type AssetPrediction = Record<AssetKey, number>;

export type ElectricityPoint = {
  timestamp: string; // ISO 8601 with offset
  powerKw: number;   // net power; negative = export to grid
};

export const EVENT_TYPES = ["ev_charging", "pv_generation", "high_consumption"] as const;
export type BuildingEventType = (typeof EVENT_TYPES)[number];

export type BuildingEvent = {
  type: BuildingEventType;
  start: string;       // ISO 8601
  end: string;         // ISO 8601, may be on the next day
  confidence?: number; // 0–1
};

export type ShapFeature = { feature: string; contribution: number }; // signed, roughly −1..1

export type AssetExplanation = {
  reasons: string[];   // plain-language evidence bullets for the "Why?" popover
  shap: ShapFeature[]; // signed contributions for the technical section
};

export type BuildingExplanation = {
  model: string;
  inputs: string[];
  additionalData: string[];
  method: string;            // "SHAP"
  methodDescription: string; // one line
  assets: Record<AssetKey, AssetExplanation>;
};

export type Building = {
  id: string;       // anonymised customer / meter id, e.g. "AG-004711"
  postcode: string; // PLZ, e.g. "5000"
  city: string;     // town name from the data, e.g. "Aarau"
  canton: string;   // "AG"
  predictions: AssetPrediction;
  electricity: ElectricityPoint[];
  events: BuildingEvent[];
  explanation: BuildingExplanation;
};
```

PLZ area data (`src/lib/plz.ts`), derived from the committed GeoJSON whose features carry `properties: { plz: string; name: string; gemeinde: string }` and `id = plz`:

```ts
export type PlzProperties = { plz: string; name: string; gemeinde: string };
export type PlzArea = PlzProperties & { bbox: [number, number, number, number] /* west, south, east, north */ };
export const PLZ_AREAS: readonly PlzArea[];
export const PLZ_BY_CODE: Record<string, PlzArea>;
export const AARGAU_BBOX: [number, number, number, number]; // union of all areas
export function getPlzArea(plz: string): PlzArea | undefined;
export function countBuildingsByPlz(buildings: Building[]): Record<string, number>;
/** The committed FeatureCollection with a numeric `count` property added to each feature. */
export function buildPlzGeoJson(counts: Record<string, number>): FeatureCollection<Polygon, PlzProperties & { count: number }>;
export function formatPlz(plz: string): string; // "5000 Aarau" (falls back to the code alone)
```

## 6. Domain logic (pure, tested)

### 6.1 `src/lib/predictions.ts`

```ts
export const PREDICTION_THRESHOLDS = { likely: 80, possible: 50 } as const;
export type PredictionLabel = "Likely" | "Possible" | "Unlikely";
export function getPredictionLabel(probability: number): PredictionLabel;
export function formatProbability(probability: number): string; // "76%"
export type AssetMeta = { key: AssetKey; label: string; shortLabel: string; icon: LucideIcon; color: string };
export const ASSETS: readonly AssetMeta[]; // fixed order: pv, battery, heatPump, ev
export const ASSET_BY_KEY: Record<AssetKey, AssetMeta>;
/** Asset keys labelled "Likely", highest first, at most `max` (default 2). */
export function getMarkerAssets(predictions: AssetPrediction, max?: number): AssetKey[];
/** "EV — 76% likely". Never states an asset as fact. */
export function describePrediction(assetKey: AssetKey, probability: number): string;
```

Labels: `>= 80` Likely, `>= 50` Possible, else Unlikely; inputs clamped to `[0, 100]`. Colours: PV `#d97706`, Battery `#16a34a`, Heat pump `#ea580c`, EV `#2563eb`.

### 6.2 `src/lib/events.ts`

`EVENT_META: Record<BuildingEventType, { label; color }>` — `ev_charging` "EV charging" (EV colour), `pv_generation` "Possible PV generation" (PV colour), `high_consumption` "High consumption" (`#64748b`). `EVENT_BAND_OPACITY = 0.14`.

### 6.3 `src/lib/search.ts`

`filterBuildings(buildings, query)`: normalise (lowercase, trim, NFD + strip combining marks, collapse whitespace); split the query into tokens; a building matches when every token is a substring of `"${id} ${postcode} ${city}"`. Empty query returns the input array unchanged.

### 6.4 `src/lib/chart-option.ts`

```ts
export const DAY_MINUTES = 1440;
export const TICK_MINUTES = 240;
export function minutesFromStart(iso: string, startMs: number): number;
export type EventBand = { type: BuildingEventType; label: string; color: string; startMin: number; endMin: number };
export function eventsToBands(events: BuildingEvent[], startMs: number): EventBand[]; // clip, split at midnight, drop empty
export function formatHourTick(minute: number): string; // 0 → "00", 240 → "04", 1440 → "24"
export function buildChartOption(electricity: ElectricityPoint[], events: BuildingEvent[]): EChartsOption;
```

`startMs` is the first point's timestamp. Bands render as `markArea` on the line series, `EVENT_META[type].color` at `EVENT_BAND_OPACITY`, label `insideTop`. Line 2 px navy, no symbols, no smoothing, `animation: false`. Y axis titled `kW`.

### 6.5 `src/lib/mock-data.ts`

```ts
export const MOCK_SEED = 42;
export const MOCK_BUILDING_COUNT = 120;
export const MOCK_DAY_START = "2026-09-09T00:00:00+02:00";
export const DEMO_BUILDING_ID = "AG-004711";
export const MOCK_PLZ_POOL: readonly { plz: string; weight: number }[]; // ~20 Aargau PLZs
export function generateMockBuildings(seed?: number, count?: number): Building[]; // [demo, ...random]
```

City names come from `PLZ_BY_CODE[plz].name`. Synthetic day curve: baseline 0.3–0.6 kW with noise; morning and evening bumps; heat-pump cycling when `heatPump >= 50`; midday PV dip (net may go negative) when `pv >= 50`; 7 kW EV plateau inside each EV window when `ev >= 50`; flattened evening peak when `battery >= 50`. Event windows are minutes from day start and may exceed 1440 (crossing midnight); the curve applies the plateau modulo the day and the event keeps its true end. Every building has 1–3 events. Explanations are template text conditioned on probabilities; the demo building's explanation is hand-authored to match the task doc's SHAP example.

## 7. UI state — `src/stores/ui-store.ts`

```ts
export type ViewMode = "map" | "list";
interface UIState {
  selectedPlz: string | null;        // area filter chosen on the map or via "Show all areas"
  selectedBuildingId: string | null;
  isDetailOpen: boolean;
  viewMode: ViewMode;
  searchQuery: string;
  isAboutOpen: boolean;
  selectPlz: (plz: string | null) => void;  // sets area, clears building, closes detail
  selectBuilding: (id: string) => void;     // sets id, opens detail, leaves area filter alone
  closeDetail: () => void;                  // closes detail, keeps selection highlight
  clearSelection: () => void;               // closes detail, clears building id
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setAboutOpen: (open: boolean) => void;
}
export const initialUIState; // state slice only, for tests
```

The old `selectedCustomerId` field is removed; nothing uses it.

## 8. Hooks — `src/hooks/use-buildings.ts`

```ts
export const buildingsQueryKey = ["buildings"] as const;
export function useBuildings(): UseQueryResult<Building[]>;
export function useFilteredBuildings(): { buildings: Building[]; total: number; isLoading: boolean; isError: boolean };
export function useSelectedBuilding(): Building | undefined;
export function usePlzCounts(): Record<string, number>;      // from all buildings, not filtered
export function useHighlightedPlz(): string | null;          // selectedBuilding?.postcode ?? selectedPlz
```

`useFilteredBuildings` applies the PLZ filter first, then the search query. `total` is the count after the PLZ filter but before search, so the header can say "12 buildings" for the area.

## 9. Components and interfaces

All Client Components. Only the sheet's children and the chart take data props; everything else reads hooks and the store.

| Component | File | Props | Behaviour |
| --- | --- | --- | --- |
| `AppHeader` | `components/header/app-header.tsx` | none | Wordmark, area `Select` (single option "Aargau (AG)"), search `Input` bound to `searchQuery` with placeholder "Search building ID, PLZ or town...", Map/List toggle (two buttons with `aria-pressed`), "About this project" button. |
| `AboutDialog` | `components/header/about-dialog.tsx` | none | shadcn `Dialog` bound to `isAboutOpen`; copy from the root README challenge section. |
| `MapView` | `components/map/map-view.tsx` | none | `react-map-gl/maplibre` `Map`, initial view fits `AARGAU_BBOX`, `NavigationControl`. Renders `PlzLayers` from `buildPlzGeoJson(usePlzCounts())` (counts feed the tooltip only). `interactiveLayerIds=["plz-fill"]`; on click with a feature → `selectPlz(plz)` (or `null` when the same PLZ is clicked again); click with no feature → `selectPlz(null)`; on mouse move → local `hoveredPlz` + cursor position for `MapTooltip`. When `useHighlightedPlz()` changes to a PLZ, `fitBounds(bbox, { padding: 48, duration: 900, maxZoom: 13 })`. Imports `maplibre-gl/dist/maplibre-gl.css`. |
| `PlzLayers` | `components/map/plz-layers.tsx` | `data`, `highlightedPlz`, `hoveredPlz` | `Source id="plz"` + four `Layer`s: `plz-fill` (uniform light fill), `plz-hover` (tint filtered to `hoveredPlz`), `plz-line` (thin borders), `plz-highlight` (thick primary-colour outline filtered to the highlighted PLZ). |
| `MapTooltip` | `components/map/map-tooltip.tsx` | `plz`, `count`, `x`, `y` | Absolutely positioned label "5000 Aarau · 12 buildings" near the cursor; hidden when `plz` is null. |
| `BuildingList` | `components/buildings/building-list.tsx` | none | `AreaHeader`, `ScrollArea` of `BuildingCard`s from `useFilteredBuildings`, empty and loading states, scrolls the selected card into view. |
| `AreaHeader` | `components/buildings/area-header.tsx` | none | "Buildings in 5000 Aarau" + "12 buildings" + "Show all areas" button when `selectedPlz` is set; otherwise "Buildings in Aargau" + "120 buildings". |
| `BuildingCard` | `components/buildings/building-card.tsx` | `building`, `selected`, `onSelect(id)` | Button-like card with `id="building-card-<id>"`, `aria-pressed`, `Building2` icon, ID bold, "PLZ Town" below, four `ProbabilityChip`s. |
| `ProbabilityChip` | `components/buildings/probability-chip.tsx` | `assetKey`, `probability` | Icon + percent in asset colour; `title` = `describePrediction(...)`. |
| `BuildingDetailSheet` | `components/detail/building-detail-sheet.tsx` | none | `Sheet` open when `isDetailOpen && selected`. Title "Building AG-004711", subtitle "5000 Aarau, AG". Sections in task-doc order. |
| `PredictionCards` / `PredictionCard` | `components/detail/prediction-cards.tsx`, `prediction-card.tsx` | `predictions`, `explanation` / `assetKey`, `probability`, `explanation` | Four cards, fixed order, each with icon, percent, label badge, and a `WhyPopover` trigger "Why?". |
| `WhyPopover` | `components/detail/why-popover.tsx` | `assetKey`, `probability`, `explanation: AssetExplanation` | Title "Why {label} is {likely/possible/unlikely}", reasons with check icons, top three positive SHAP features as bars. |
| `PredictionExplanation` | `components/detail/prediction-explanation.tsx` | none | Static "How is this calculated?" copy from task doc §12. |
| `TechnicalDetails` | `components/detail/technical-details.tsx` | `explanation`, `predictions` | `Collapsible` "Show technical details"; model, input, additional data, explainability line; per-asset signed feature list. |
| `ElectricityChart` | `components/chart/electricity-chart.tsx` | `electricity`, `events`, `className?` | `echarts-for-react` via `next/dynamic` (`ssr: false`); option from `buildChartOption`. Height 260 px. |
| `ChartLegend` | `components/chart/chart-legend.tsx` | `events` | Line swatch "Consumption" plus one swatch per distinct event type present. |
| `AppShell` | `components/app-shell.tsx` | none | Layout per D12; mounts sheet and about dialog once. |

## 10. Visual design

Tokens in `globals.css` (light only; the existing `.dark` block stays untouched):

- background `oklch(0.99 0.002 250)`, foreground (navy) `oklch(0.27 0.05 262)`
- primary (AEW-inspired blue) `oklch(0.50 0.17 252)`, primary-foreground white
- accent (green tint) `oklch(0.94 0.04 160)`, accent-foreground `oklch(0.35 0.09 160)`
- muted `oklch(0.96 0.01 250)`, muted-foreground `oklch(0.52 0.03 258)`, border `oklch(0.91 0.01 250)`, ring `oklch(0.60 0.15 252)`
- chart-1..4 = PV, Battery, Heat pump, EV colours

Map layer colours (hex, used in MapLibre paint): area fill `#dbeafe` at 0.35 opacity; hover fill `#1d4ed8` at 0.12; highlight outline `#1d4ed8` 2.5 px; borders `#94a3b8` 0.6 px.

Rules: white cards with `ring-1` borders, `rounded-xl`, lucide line icons, generous whitespace. Map and chart are the only strong visuals. No gradients, no animation beyond map fit and sheet slide.

## 11. Demo flow (manual QA and e2e)

1. Open the app: Aargau PLZ map, list says "Buildings in Aargau · 120 buildings".
2. Click the 5000 Aarau area on the map (or search "Aarau"): area highlights, list filters to Aarau.
3. Click **Building AG-004711**: map fits to 5000, card highlights, sheet opens with PV 92% Likely, Battery 48% Unlikely, Heat pump 31% Unlikely, EV 76% Possible.
4. Chart shows bands "EV charging" (22:15→24:00 and 00:00→01:30) and "Possible PV generation" (10:00→16:30).
5. Open "Why?" on EV: reasons and SHAP bars.
6. Expand "Show technical details".
7. Close the sheet; click "Show all areas".

The Playwright test drives steps 1, 2 (via search), 3–7 and asserts the four labels and both band labels. Map clicks are unit-tested with a mocked map.

## 12. Deviations from the task doc

- **No building markers, no addresses, no 3D** (§3, §5, §6, §7 wherever they mention addresses or pins). Replaced by outlined PLZ areas and ID-based cards (D2–D5).
- §15 contract loses `address` and `location`, gains `explanation`.
- §18 mobile stacking replaced by the Map/List toggle (D12).
- §4 logo is a wordmark (D16).
- §19 demo flow replaced by §11 above; "Bahnhofstrasse 12" becomes "Building AG-004711".
- Battery 48% is "Unlikely" under the §9 thresholds even though the task doc's sketch says "Maybe"; thresholds win.

## 13. Risks and assumptions to confirm

1. Demo venue has internet for basemap tiles. Fallback outside scope: serve a local style via `NEXT_PUBLIC_MAP_STYLE_URL`.
2. Real customer IDs may have a different format; the UI treats IDs as opaque strings.
3. A real PLZ in the customer data might not be in the Aargau GeoJSON (customers outside AG or PLZ changes). The UI shows such buildings in the list under "All areas" with the raw PLZ; the map simply has no polygon for them.
4. The base-nova shadcn components wrap `@base-ui/react`; prop names differ from Radix-era shadcn. Implementers read the generated file before using it.
5. Mobile is "usable, no horizontal scroll", not polished.

## 14. Parallelisation and hygiene

Branching: integration branch `feat/frontend-energy-map` (worktree `../OSNOVA-frontend-demo`). Wave 1 agents branch from it as `feat/ef-<area>` in their own worktrees, run `npm ci`, commit small, never touch files outside their ownership rows. Wave 2 merges the five branches (disjoint files, no conflicts expected), deletes `src/app/dev/`, deletes merged branches and worktrees, opens the PR to `main`.

Definition of done for any task: `npm run check` green in that task's worktree; no `console.log`; no unused exports or dependencies; no `any`; no `// TODO`; files only within ownership; commit messages in the repo's `type: summary` style with the Claude co-author trailer.
