# AEW Energy Management Dashboard — Design Spec

**Date:** 2026-09-10
**Status:** Draft for review
**Source PRD:** the "AEW Energy Management Dashboard — Technical Task / Product Requirements" (§1–§50) supplied by the product owner on 2026-09-10 (kept verbatim in `frontend/docs/energy-dashboard-prd.md`).
**Predecessor:** the Energy Fingerprints demo (tag `demo-v1-fingerprints`, PR #1, spec `2026-09-10-energy-fingerprints-frontend-design.md`). The dashboard **evolves** that codebase: its PLZ polygons, store/query architecture, chart machinery, test tooling and MapLibre worker fix are reused; its prediction UI becomes one section of the building detail page.

Where this spec and the PRD disagree, this spec wins; every deviation is listed in §14.

## 1. Goal and scope

A professional energy-infrastructure control centre for the Aargau region: region → PLZ → building → energy system → device. Desktop first, usable on tablet and phone. Mock data only, shaped so a real backend replaces it behind one file.

Scope for this plan = the PRD's **MUST HAVE** list (§48) in full: main dashboard, AEW-inspired design system, header, navigation, KPI cards, PLZ map zones, status building markers with clustering, building list, search, combinable filters, building detail (summary, energy KPIs, charts, systems, devices, alerts, predictions), alerts page, devices page, energy page, loading/empty/error states, responsive desktop/tablet/mobile.

Explicitly deferred (PRD SHOULD/FUTURE): device detail page, alert acknowledgement, custom date range, permissions, automation, device control, reports, export, AI recommendations. The data freshness indicator is included because it is cheap and the PRD's §25 wording is "must".

## 2. Decisions

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| D1 | Product relationship | Evolve the fingerprint demo in place on branch `feat/energy-dashboard` from tag `demo-v1-fingerprints`. The old single-screen shell, header, area header, view toggle, detail sheet and about dialog are removed; predictions, why-popover, technical details and the 24 h fingerprint chart are kept and mounted in the building detail page. | User decision; the demo remains restorable from the tag / PR #1. |
| D2 | Routing | Next App Router with a `(dashboard)` route group and one shared layout: `/` Overview, `/buildings`, `/buildings/[buildingId]`, `/devices`, `/energy`, `/alerts`, `/settings`. Pages are Server Components that render client page components. | PRD §7 navigation implies real sections; deep links to a building are essential for an operator tool. |
| D3 | Geography | Buildings carry `latitude`/`longitude` generated **inside their PLZ polygon** (rejection sampling with point-in-polygon). The UI shows ID, PLZ, status and position — never an address. | PRD §8/§40 include coordinates and forbid addresses. |
| D4 | Map rendering | One MapLibre GeoJSON source for buildings with `cluster: true`; circle layers for clusters, cluster counts (symbol layer using the basemap's glyphs), status-coloured points and a selected ring. PLZ polygons as in the demo, with multi-PLZ highlight. No DOM markers. | PRD §42–§43: thousands of markers, clustering, viewport rendering. GeoJSON layers are GPU-rendered and cheap. |
| D5 | Map component contract | `BuildingsMap` is prop-driven (buildings, selected building, selected PLZs, callbacks). It never reads the store. | Reused on Overview and Buildings pages with different behaviour; testable with a mocked map. |
| D6 | Scale of mock data | 1,200 buildings across all 239 Aargau PLZs (weighted to towns), ~7,000 devices (4–8 per building), ~180 alerts, deterministic seed 42, fixed "now" `2026-09-10T16:42:31+02:00`. Time series are generated on demand per (building, range) from a seeded generator, never stored up front. | PRD §41–§42 performance targets; on-demand series keep memory small and tests fast. |
| D7 | Fingerprint data | Kept as a separate lazily fetched `Fingerprint` (predictions, 24 h electricity, events, explanation) via `fetchFingerprint(buildingId)`; not embedded in `Building`. The demo building `AG-004711` becomes `BLD-0001` in PLZ 5000 with the same hand-authored values. | 1,200 × 96 points would bloat the building list payload; the detail page is the only consumer. |
| D8 | Status model | `BuildingStatus = normal · efficient · warning · critical · offline` (PRD §10 colours). `Connectivity = online · warning · offline`. Building status is derived in the generator from its systems/devices/alerts and stored on the building (the backend will do the same). Status is always shown as **dot + label**, never colour alone. | PRD §10, §38. |
| D9 | Lists at scale | Building list rows are virtualised with `@tanstack/react-virtual` (new runtime dependency, ~3 KB). The devices table uses TanStack Table with client-side pagination (50 rows/page) and sorting. | PRD §42 allows pagination or virtualisation; a 1,200-row card list needs virtualisation, a 7,000-row table paginates fine. |
| D10 | Filters and search | Filters live in the store as `{ plz[], statuses[], systems[], connectivity[] }` and combine with AND across groups, OR within a group. Search (header, 200 ms debounce) matches building ID, PLZ, and device IDs/names via a precomputed per-building search string. Pure functions in `src/lib/filters.ts`. | PRD §12–§13. |
| D11 | Charts | ECharts via `echarts-for-react` (SVG renderer). Pure option builders per chart in `src/lib/chart-options/`, tested without a DOM. Time ranges `today · 24h · 7d · 30d · 12m` (custom deferred). Every chart shows units, legend, tooltip with timestamp and value, and an `aria-label` summary. | PRD §16, §38. |
| D12 | Design system | PRD §30 palette as CSS variables; **Inter** via `next/font/google`; card radius 8 px; flat cards with 1 px `#D9E1E6` border and no shadow; shadows only on dropdowns/popovers/sheets; 4/8 px spacing scale; tabular numerals for metrics. Status and asset colours also exist once in TypeScript for MapLibre/ECharts. | PRD §30–§34. |
| D13 | Shell | Left sidebar 240 px (icon rail 64 px between 768 and 1199 px, hidden with a hamburger drawer below 768 px), header with section title, global search, notifications (active alert count), system status pill, user menu placeholder. | PRD §5–§7, §29. |
| D14 | States | Shared `states` kit: skeletons per component shape, `EmptyState`, `ErrorState` with retry (refetches the query), `DataFreshness` (last updated, manual refresh, "Data delayed" when older than 15 min against the mock now). | PRD §25–§28. |
| D15 | Data layer | `src/lib/api.ts` exposes `fetchBuildings`, `fetchBuilding`, `fetchDevices`, `fetchAlerts`, `fetchSeries`, `fetchFingerprint`, `fetchSystemStatus` over the mock world with a short artificial delay. Hooks in `src/hooks/` wrap them in TanStack Query. Components never import mock modules. | PRD §39. |
| D16 | Deferred features | Device rows are links to their building (no device detail page). Alerts have no acknowledge action. Settings is an "About" card plus a list of planned features. Custom date range is not offered. | User chose MUST HAVE only. |
| D17 | Accessibility | Status dot + text everywhere; keyboard-operable filters and lists; `focus-visible` rings; icon-only buttons carry `aria-label`; charts carry an `aria-label` and an `sr-only` summary sentence. | PRD §38. |
| D18 | Parallel work | Wave 0 (foundation, sequential): design system, contract + mock world, data layer + store, shell + states + chart stubs, migration of the fingerprint components. Wave 1 (parallel): map, list + filters, KPI/status/flow widgets, charts kit, building detail page, alerts page, devices page. Wave 2 (sequential): page composition (Overview, Buildings, Energy), responsive + accessibility + e2e + docs, final review, cleanup, PR. | Same discipline that worked for the demo: frozen contract first, disjoint ownership, integration last. |

## 3. Architecture

```
app/(dashboard)/layout.tsx (server) ── DashboardShell (client): Sidebar · Header · <main>
  /            OverviewPage        KpiGrid · SystemStatusPanel · DataFreshness · BuildingsMap · AttentionList · ActiveAlerts · EnergyChart
  /buildings   BuildingsPage       FilterBar · BuildingsMap (65%) · BuildingList (35%, virtualised) · mobile Map/List tabs
  /buildings/[id] BuildingDetailPage  BuildingSummary · EnergyKpiRow · EnergyChart+BatteryChart+TimeRangeSelector · SystemsGrid · DevicesTable · BuildingAlerts · PredictionsSection
  /devices     DevicesPage         DeviceFilters · DevicesTable (paginated)
  /energy      EnergyPage          EnergyKpiRow (region) · EnergyFlowDiagram · EnergyChart · DistributionDonut · GridChart
  /alerts      AlertsPage          SeverityTabs · StatusFilter · AlertsTable
  /settings    SettingsPage        AboutCard · PlannedFeatures
```

Data flow:

```
mock world (seeded) ──► api.ts ──► hooks (TanStack Query) ──► pages/components
                                     useBuildings, useBuilding(id), useDevices, useAlerts, useSeries(scope, range),
                                     useFingerprint(id), useSystemStatus, useKpis
ui-store (Zustand): filters, searchQuery, selectedBuildingId, timeRange, sidebarCollapsed, mobileNavOpen
derived (hooks, memoised): filtered buildings, counts per PLZ, attention list, alert counts
```

## 4. File map and ownership

"W0" = Wave 0 tasks (sequential); "W1-x" = Wave 1 agent x; "W2" = integration.

| Path | Responsibility | Owner |
| --- | --- | --- |
| `package.json` (dep `@tanstack/react-virtual`), `src/app/globals.css`, `src/app/layout.tsx` (Inter), `src/lib/design-tokens.ts` | Design system | W0 |
| `src/components/ui/{skeleton,table,tabs,dropdown-menu,checkbox,tooltip}.tsx` | shadcn additions (generated) | W0 |
| `src/lib/types.ts` (rewrite), `src/lib/geo.ts`, `src/lib/mock/{world,series,fingerprint,alerts}.ts`, `src/lib/mock/index.ts` | Contract and mock world | W0 |
| `src/lib/api.ts`, `src/hooks/*.ts`, `src/stores/ui-store.ts`, `src/lib/filters.ts`, `src/lib/aggregate.ts`, `src/lib/freshness.ts`, `src/lib/format.ts` | Data layer, state, pure logic | W0 |
| `src/app/(dashboard)/layout.tsx`, `src/app/(dashboard)/*/page.tsx` (placeholders), `src/components/shell/*`, `src/components/states/*`, `src/components/charts/*` (stubs) | Shell, states, chart stubs | W0 |
| `src/components/predictions/*` (moved from `detail/` + `chart/electricity-chart`), `src/lib/chart-options/fingerprint.ts` (moved from `chart-option.ts`) | Fingerprint migration; deletion of old shell/header/list/sheet | W0 |
| `src/components/map/*` | `BuildingsMap`, PLZ layers, building layers, tooltip, legend | W1-map |
| `src/components/buildings/*` | `BuildingList`, `BuildingRow`, `FilterBar`, `StatusBadge` consumers, sort | W1-list |
| `src/components/kpi/*`, `src/components/status/*`, `src/components/energy/energy-flow-diagram.tsx` | KPI cards, system status panel, energy flow | W1-kpi |
| `src/components/charts/*` (real), `src/lib/chart-options/{energy,battery,distribution,grid}.ts` | Charts kit + time range selector | W1-charts |
| `src/components/building-detail/*`, `src/app/(dashboard)/buildings/[buildingId]/page.tsx` | Building detail page | W1-detail |
| `src/components/alerts/*`, `src/app/(dashboard)/alerts/page.tsx` | Alerts page | W1-alerts |
| `src/components/devices/*`, `src/app/(dashboard)/devices/page.tsx` | Devices page | W1-devices |
| `src/app/(dashboard)/page.tsx`, `buildings/page.tsx`, `energy/page.tsx`, `settings/page.tsx`, `src/components/pages/*` | Page composition | W2 |
| `e2e/*.spec.ts`, `README.md`, `docs/energy-dashboard-prd.md` | Acceptance e2e, docs | W2 |

Shared primitives used by several Wave 1 tasks are Wave 0 deliverables: `StatusBadge`, `SeverityBadge`, `SystemTypeIcon`, `formatKw/kWh/percent/time`, the `states` kit, `PageHeader`, `SectionCard`.

## 5. Data contract (`src/lib/types.ts`)

```ts
export type BuildingStatus = "normal" | "efficient" | "warning" | "critical" | "offline";
export type Connectivity = "online" | "warning" | "offline";
export type SystemType = "pv" | "battery" | "hvac" | "ev_charging" | "meter" | "other";
export type SystemStatus = "online" | "charging" | "discharging" | "idle" | "warning" | "error" | "offline";
export type DeviceType = "pv_inverter" | "battery" | "meter" | "hvac_controller" | "ev_charger" | "sensor";
export type DeviceStatus = "online" | "charging" | "warning" | "error" | "offline";
export type AlertSeverity = "critical" | "warning" | "info";
export type AlertStatus = "active" | "acknowledged" | "resolved";
export type TimeRange = "today" | "24h" | "7d" | "30d" | "12m";

export type Metric = { key: string; label: string; value: number; unit: string };

export type EnergySummary = {
  currentLoadKw: number;
  productionTodayKwh: number;
  consumptionTodayKwh: number;
  selfConsumptionPct: number;   // 0–100
  gridImportKwh: number;
  gridExportKwh: number;
  batterySocPct?: number;        // present when a battery exists
};

export type EnergySystem = {
  systemId: string;              // "SYS-0001-PV"
  buildingId: string;
  type: SystemType;
  label: string;                 // "PV System", "Battery", "HVAC", "EV Charging", "Smart Meter"
  status: SystemStatus;
  metrics: Metric[];             // type-specific, e.g. currentProductionKw, todayProductionKwh, socPct, powerKw, activeChargers
  lastUpdated: string;
};

export type Device = {
  deviceId: string;              // "DEV-00001"
  buildingId: string;
  systemId: string;
  type: DeviceType;
  name: string;                  // "PV Inverter 1"
  manufacturer: string;
  model: string;
  serialNumber: string;
  status: DeviceStatus;
  lastUpdated: string;
  currentValue: Metric;          // what the table shows
  measurements: Metric[];        // voltage, current, power, energy, temperature, efficiency, soc — only the relevant ones
};

export type Building = {
  buildingId: string;            // "BLD-0001"
  plz: string;                   // "5000"
  latitude: number;
  longitude: number;
  status: BuildingStatus;
  connectivity: Connectivity;
  lastUpdated: string;
  systemTypes: SystemType[];     // for filtering and chips
  deviceCount: number;
  alertCounts: { critical: number; warning: number; info: number };
  energy: EnergySummary;
  searchText: string;            // lower-cased "BLD-0001 5000 DEV-00001 pv inverter 1 …"
};

export type BuildingDetail = Building & { systems: EnergySystem[]; devices: Device[]; alerts: Alert[] };

export type Alert = {
  alertId: string;               // "ALR-0001"
  buildingId: string;
  deviceId?: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  timestamp: string;
  status: AlertStatus;
};

export type SeriesPoint = { timestamp: string; value: number };
export type EnergySeries = {
  scope: "region" | string;      // "region" or a buildingId
  range: TimeRange;
  stepMinutes: number;           // 15 (today/24h), 60 (7d), 1440 (30d), 43200 (12m)
  production: SeriesPoint[];
  consumption: SeriesPoint[];
  gridImport: SeriesPoint[];
  gridExport: SeriesPoint[];
  batterySoc?: SeriesPoint[];
};

export type SystemStatusSummary = {
  state: "operational" | "degraded" | "incident";
  buildings: number; devices: number; devicesOnline: number; devicesOffline: number;
  warnings: number; critical: number;
  lastUpdated: string;
};

export type Kpis = {
  totalBuildings: number;
  productionTodayKwh: number;
  consumptionTodayKwh: number;
  selfConsumptionPct: number;
  activeAlerts: number;
  criticalAlerts: number;
};

// Fingerprint (kept from the demo)
export const ASSET_KEYS = ["pv", "battery", "heatPump", "ev"] as const;
export type AssetKey = (typeof ASSET_KEYS)[number];
export type AssetPrediction = Record<AssetKey, number>;
export type ElectricityPoint = { timestamp: string; powerKw: number };
export const EVENT_TYPES = ["ev_charging", "pv_generation", "high_consumption"] as const;
export type BuildingEventType = (typeof EVENT_TYPES)[number];
export type BuildingEvent = { type: BuildingEventType; start: string; end: string; confidence?: number };
export type ShapFeature = { feature: string; contribution: number };
export type AssetExplanation = { reasons: string[]; shap: ShapFeature[] };
export type BuildingExplanation = { model: string; inputs: string[]; additionalData: string[]; method: string; methodDescription: string; assets: Record<AssetKey, AssetExplanation> };
export type Fingerprint = { buildingId: string; predictions: AssetPrediction; electricity: ElectricityPoint[]; events: BuildingEvent[]; explanation: BuildingExplanation };
```

Filters:

```ts
export type BuildingFilters = { plz: string[]; statuses: BuildingStatus[]; systems: SystemType[]; connectivity: Connectivity[] };
export type BuildingSort = "id" | "severity" | "consumption" | "production";
```

## 6. Mock world (`src/lib/mock/`)

- `world.ts`: `generateWorld(seed = 42)` → `{ buildings: Building[]; systems: EnergySystem[]; devices: Device[]; alerts: Alert[]; now: string }`, memoised via `getWorld()`. Buildings: 1,200 IDs `BLD-0001…`; PLZ picked from a weighted pool of 40 town PLZs (80 %) and uniformly from the remaining 199 (20 %); position by rejection sampling inside the PLZ polygon (`geo.ts`: `randomPointInPolygon(rng, polygon)`, `pointInPolygon`). Each building gets a meter plus 0–3 systems (PV 55 %, battery 30 % and only with PV, HVAC 45 %, EV 25 %); each system gets 1–3 devices; device measurements depend on type. Status derivation: any `error`/`offline` device on a PV/meter or an active critical alert → `critical`; any `warning` device or active warning alert → `warning`; connectivity `offline` → `offline`; PV present and `selfConsumptionPct ≥ 70` → `efficient`; else `normal`. Target distribution ≈ 62 % normal, 22 % efficient, 10 % warning, 4 % critical, 2 % offline (assert ranges in tests). `lastUpdated` = now minus 0–20 min (offline: 30–180 min).
- `alerts.ts`: ~180 alerts (70 % active, 15 % acknowledged, 15 % resolved), titles from templates per device type ("PV inverter offline", "Battery temperature above normal range", "Meter communication lost", "EV charger fault", "HVAC consumption above expected"), timestamps within the last 48 h. Alert counts on buildings are consistent with the alert list (tested).
- `series.ts`: `generateSeries(scope, range, seedKey)` → `EnergySeries`. Day curve = the demo's synthesised shape scaled by building size; region = sum-like scaled curve with seed "region". Ranges: today (00:00 → now, 15 min), 24h (last 24 h, 15 min), 7d (hourly), 30d (daily), 12m (monthly). Values in kW for 15-min/hourly ranges and kWh per bucket for daily/monthly (unit exposed by the chart option builder).
- `fingerprint.ts`: the demo generator adapted to `Fingerprint`; `BLD-0001` keeps PV 92 / Battery 48 / Heat pump 31 / EV 76 and the EV 22:15→01:30 + PV 10:00→16:30 events.
- `index.ts`: re-exports and `MOCK_NOW`.

## 7. Pure logic

- `filters.ts`: `DEFAULT_FILTERS`, `applyBuildingFilters(buildings, filters, query)`, `sortBuildings(buildings, sort)`, `isFilterActive(filters)`, `plzOptions(buildings)` (PLZ → count, sorted), `STATUS_SEVERITY` order `critical > warning > offline > normal > efficient`.
- `aggregate.ts`: `computeKpis(buildings, alerts)`, `computeSystemStatus(buildings, devices, alerts, now)` (state: `incident` if critical > 0, `degraded` if warnings or offline devices > 1 % of devices, else `operational`), `attentionList(buildings, n)` (critical, then warning, then offline; by alert counts), `countByPlz`, `consumptionBySystemType(systems)`.
- `freshness.ts`: `freshnessOf(lastUpdated, now, thresholdMinutes = 15)` → `{ ageMinutes, isDelayed, label }`.
- `format.ts`: `formatKw`, `formatKwh` (auto-scales to MWh/GWh), `formatPercent`, `formatTime`, `formatDateTime`, `formatRelative(ts, now)` ("10 minutes ago").
- `design-tokens.ts`: `COLORS` (PRD §30), `STATUS_META: Record<BuildingStatus, { label; color; icon }>`, `SEVERITY_META`, `SYSTEM_META: Record<SystemType, { label; color; icon }>`, `DEVICE_META`, `CONNECTIVITY_META`.
- `chart-options/`: `energyOption(series, range)` (production vs consumption, area under production), `batteryOption(series)`, `distributionOption(bySystemType)`, `gridOption(series)`, `fingerprintOption(...)` (moved). Shared `axis.ts` for time axis formatting per range.

## 8. UI state (`ui-store.ts`)

```ts
interface UIState {
  filters: BuildingFilters; setFilters(patch: Partial<BuildingFilters>); togglePlz(plz); clearFilters();
  searchQuery: string; setSearchQuery(q);
  sort: BuildingSort; setSort(s);
  selectedBuildingId: string | null; selectBuilding(id | null);
  timeRange: TimeRange; setTimeRange(r);
  sidebarCollapsed: boolean; toggleSidebar();
  mobileNavOpen: boolean; setMobileNavOpen(open);
}
export const initialUIState;
```

## 9. Hooks (`src/hooks/`)

`useBuildings()`, `useBuilding(id)` (detail with systems, devices, alerts), `useDevices()`, `useAlerts()`, `useSeries(scope, range)`, `useFingerprint(id)`, `useSystemStatus()`, `useKpis()`; derived: `useFilteredBuildings()` → `{ buildings, total, isLoading, isError, refetch }`, `useAttentionList(n)`, `useActiveAlerts(n)`, `usePlzCounts()`. All queries `staleTime: Infinity`; `refetch` is what the refresh button and the error retry call. `useNow()` returns the mock now (single place to swap for a ticking clock).

## 10. Components and contracts

| Component | Props | Notes |
| --- | --- | --- |
| `DashboardShell` | `children` | Sidebar + Header + main; reads `sidebarCollapsed`, `mobileNavOpen`. |
| `Sidebar` | none | Nav items with icons, active state by pathname, collapse control. |
| `Header` | none | Section title from pathname, `GlobalSearch`, `NotificationsButton` (active alerts count → `/alerts`), `SystemStatusPill`, user menu placeholder. |
| `PageHeader` | `title, description?, actions?` | Consistent page top. |
| `SectionCard` | `title, actions?, children` | Flat card, 8 px radius. |
| `StatusBadge` | `status: BuildingStatus \| Connectivity \| DeviceStatus \| SystemStatus` | Dot + label; never colour alone. |
| `SeverityBadge` | `severity` | Same for alerts. |
| `Skeleton*`, `EmptyState`, `ErrorState`, `DataFreshness` | see D14 | |
| `KpiCard` | `label, value, unit?, hint?, icon, tone?` | Large tabular number, small label. |
| `KpiGrid` | none | 5 KPI cards from `useKpis`. |
| `SystemStatusPanel` | none | State pill + counts; from `useSystemStatus`. |
| `EnergyFlowDiagram` | `summary: EnergySummary` | SVG flow Solar → System → Battery/Building, Grid import/export, numbers. |
| `TimeRangeSelector` | `value, onChange` | Segmented control. |
| `EnergyChart` | `series, range, height?` | Production vs consumption. |
| `BatteryChart` | `series` | SoC area. |
| `DistributionDonut` | `data: { type, kwh }[]` | By system type. |
| `GridChart` | `series, range` | Import vs export. |
| `BuildingsMap` | `buildings, selectedBuildingId, selectedPlz: string[], onSelectBuilding(id), onOpenBuilding(id), onSelectPlz(plz), fitTo?: "aargau" \| "selection", className?` | D4/D5; hover tooltips; legend; cluster expansion on click; `flyTo` selected building. |
| `BuildingList` | `buildings, selectedBuildingId, onSelect(id), onOpen(id), sort, onSortChange` | Virtualised rows; row = ID, PLZ, `StatusBadge`, production, consumption, "Open" link. |
| `FilterBar` | none | PLZ multi-select (searchable popover with checkboxes), status chips, system multi-select, connectivity chips, "Clear filters", result count. Reads/writes store. |
| `AttentionList` | `n` | Top-n buildings needing attention with links. |
| `ActiveAlerts` | `n` | Latest active alerts with severity and building link. |
| `BuildingSummary` | `building` | ID, PLZ, status, connectivity, last updated + `DataFreshness`. |
| `EnergyKpiRow` | `summary` | Six metrics (PRD §19). |
| `SystemsGrid` | `systems` | One card per system with type icon, status, 2–3 metrics. |
| `DevicesTable` | `devices, pageSize?, showBuilding?` | TanStack Table: sortable columns Device, Type, Status, Current value, Last update (+ Building when `showBuilding`). |
| `BuildingAlerts` | `alerts` | Compact list with severity, title, relative time. |
| `PredictionsSection` | `buildingId` | Existing prediction cards, why popover, fingerprint chart, explanation, technical details; loading/empty/error. |
| `AlertsTable` | `alerts` | Sortable by time/severity; building + device links. |
| `DeviceFilters` | `value, onChange` | Type, status, PLZ, search. |

## 11. Pages and interactions (PRD §36–§37)

- **Overview**: KPI grid; system status + freshness; map of all buildings (marker click → open detail; PLZ click → sets `filters.plz=[plz]` and navigates to `/buildings`); attention list (top 8); active alerts (top 5, link to `/alerts`); region energy chart (24 h).
- **Buildings**: filter bar; map + list synced by `selectedBuildingId` (row click selects and flies the map to the building; marker click selects; "Open" or double-click opens detail; PLZ click toggles that PLZ in the filter); count "N of M buildings"; empty state when filters match nothing; mobile shows Map/List tabs.
- **Building detail**: breadcrumb (Buildings › BLD-0001); summary; KPI row; energy + battery charts with time range; systems; devices table; alerts; predictions section; "Not found" empty state for unknown IDs.
- **Devices**: filters + paginated table across all devices; row's building ID links to the detail page.
- **Energy**: region KPI row, flow diagram, energy chart with time range, distribution donut, grid chart.
- **Alerts**: severity tabs with counts, status filter, table sorted newest first, links.
- **Settings**: About card (hackathon copy) and planned features list.

## 12. Design system

CSS variables (light only): `--primary #0065A8`, `--primary-dark #003B5C`, `--primary-hover #00558C`, `--primary-light #EAF4FA`, `--background #F4F7F9`, `--card #FFFFFF`, `--foreground #1D252C`, `--muted-foreground #66727C`, `--border #D9E1E6`, status `--success #2E8B57`, `--warning #F59E0B`, `--critical #D64545`, `--offline #8A959E`, `--solar #F5B82E`, `--battery #7A5AF8`, `--radius 0.5rem`. Mapped into the existing shadcn token names (`--primary`, `--muted`, `--accent` = primary-light, `--destructive` = critical, `--ring` = primary). Typography per PRD §31 as utility classes (`text-kpi`, etc.). Cards: `rounded-lg border bg-card` with no shadow. Focus: `focus-visible:ring-2 ring-primary`.

Map colours: clusters `#0065A8` with white count; points by `STATUS_META` (normal `#0065A8`, efficient `#2E8B57`, warning `#F59E0B`, critical `#D64545`, offline `#8A959E`), white 1.5 px stroke; selected ring `#003B5C` 3 px; PLZ fill `#0065A8` at 0.06, selected PLZ fill 0.14 + 2 px outline; hover 0.10.

## 13. Testing and verification

`npm run check` (lint + typegen/tsc + Vitest) after every task; `npm run build` and `npm run test:e2e` in Wave 2. Unit coverage that must exist: geo (point-in-polygon), world invariants (counts, IDs unique, positions inside their PLZ, status distribution ranges, alert counts consistent, no address-like fields), series shape per range, filters (AND across groups, OR within, search on device IDs), aggregate (KPIs, system status states, attention ordering), freshness thresholds, format scaling, chart option builders, store transitions. Component tests per Wave 1 area with mocked api. E2E acceptance suite mirrors PRD §49 items 1–16: buildings visible on the map, PLZ polygons, IDs not addresses, filter by PLZ, search by ID, filter by status, critical buildings identifiable, open from map, open from list, detail KPIs, systems and devices, charts, alerts visible, system status visible, states rendered, responsive check at 375 px.

## 14. Deviations from the PRD

- Device detail page, alert acknowledgement, custom date range, permissions: deferred (D16).
- "Region" level is implicit (Aargau); no region selector.
- Building status `efficient` is derived from PV + self-consumption, a heuristic the backend can replace.
- KPI magnitudes reflect 1,200 mock buildings (tens of MWh/day), not the PRD's 18.4 GWh example.
- The PRD's "Devices" nav page lists devices without a detail drawer; clicking a row opens the building.
- Predictions section (from the hackathon demo) is added to the building detail; the PRD does not mention it.

## 15. Risks and assumptions

1. MapLibre cluster count labels need glyphs; the positron style provides them. If a style without glyphs is configured via `NEXT_PUBLIC_MAP_STYLE_URL`, counts fall back to circles sized by count only.
2. 1,200 buildings and 7,000 devices are generated at first access (~50 ms); acceptable. Real data would page.
3. Basemap tiles need internet.
4. `@tanstack/react-virtual` is the only new runtime dependency.

## 16. Hygiene

Same definition of done as the demo plan: `npm run check` green per task, no `console.log`, no `any`, no `// TODO`, no unused exports, ownership respected in Wave 1, commits `type: summary` with the Claude trailer, push after every task. Wave 2 deletes preview pages, Wave 1 branches and worktrees, and opens the PR to `main` from `feat/energy-dashboard`.
