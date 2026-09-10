# AEW Energy Management Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Energy Fingerprints demo into the AEW Energy Management Dashboard: routed sections (Overview, Buildings, Building detail, Devices, Energy, Alerts, Settings), AEW design system, KPIs and system status, clustered status markers over PLZ zones, virtualised building list with combinable filters and search, building detail with energy KPIs, charts, systems, devices, alerts and predictions, on a 1,200-building / 7,000-device deterministic mock world.

**Architecture:** App Router route group with one client shell (sidebar + header). A seeded mock world behind `src/lib/api.ts`, wrapped by TanStack Query hooks; UI state in one Zustand store; all derived data in memoised hooks and pure functions under `src/lib`. Map = MapLibre GeoJSON layers with clustering; list = virtualised rows; charts = ECharts from pure option builders. Wave 0 freezes contracts and the shell; Wave 1 builds seven UI areas in parallel worktrees; Wave 2 composes pages, runs acceptance e2e, reviews and cleans up.

**Tech Stack:** Next.js 16.3 (App Router, Turbopack), React 19.2, TypeScript 5, Tailwind v4, shadcn base-nova (`@base-ui/react`), react-map-gl 8 + maplibre-gl 6, echarts 6 + echarts-for-react 3, TanStack Query 5, TanStack Table 9, **@tanstack/react-virtual (new)**, Zustand 5, lucide-react, Inter via next/font. Tests: Vitest + Testing Library, Playwright.

**Spec:** [`docs/superpowers/specs/2026-09-10-energy-dashboard-design.md`](../specs/2026-09-10-energy-dashboard-design.md) — binding. PRD: `frontend/docs/energy-dashboard-prd.md`.

**How this plan is written.** Wave 0 tasks freeze the contract: their exported signatures and their tests are given verbatim and must be implemented exactly. Wave 1 and Wave 2 tasks give the component contracts, behaviour, acceptance tests and visual rules, and leave internal structure to the implementer (use a mid-tier or better model). "Verbatim" means copy; "per spec §N" means read that section and follow it.

## Global Constraints

- All paths are relative to `frontend/` unless they start with `docs/`. Run every `npm` command from `frontend/`.
- Branch: `feat/energy-dashboard` (worktree `../OSNOVA-frontend-demo`). Wave 1 agents branch as `feat/ed-<area>` from the Wave 0 exit commit.
- Node ≥ 20. Never change versions of existing dependencies. The only new runtime dependency is `@tanstack/react-virtual` (Task 1). No other dependencies without a ledger ruling.
- Server Components by default; `"use client"` only where hooks, the store, browser APIs or client libraries are used. Pages under `src/app/(dashboard)/` are thin Server Components that render a client page component from `src/components/pages/` or the area's own directory.
- Server data → TanStack Query. Ephemeral UI state → Zustand `src/stores/ui-store.ts`. Derived data only in memoised hooks / pure functions. Components never import `src/lib/mock/*`; only `src/lib/api.ts` does.
- **No addresses anywhere** — not in types, mock data, copy, or tests. Buildings are `BLD-0001`-style IDs with a PLZ and coordinates inside that PLZ.
- Status is never colour alone: every status/severity rendering uses `StatusBadge`/`SeverityBadge` (dot + label) or an explicit text label.
- Design tokens per spec §12: primary `#0065A8`, dark `#003B5C`, hover `#00558C`, light `#EAF4FA`, background `#F4F7F9`, text `#1D252C` / `#66727C`, border `#D9E1E6`; status success `#2E8B57`, warning `#F59E0B`, critical `#D64545`, offline `#8A959E`, solar `#F5B82E`, battery `#7A5AF8`. Cards: `rounded-lg border bg-card`, no shadow. Font Inter. Tabular numerals for metrics (`tabular-nums`).
- Mock world: seed 42, now `2026-09-10T16:42:31+02:00`, 1,200 buildings, demo building `BLD-0001` in PLZ 5000 with fingerprint PV 92 / Battery 48 / Heat pump 31 / EV 76.
- Time ranges: `today | 24h | 7d | 30d | 12m`; steps 15 / 15 / 60 / 1440 / 43200 minutes.
- Wave 1 file ownership (spec §4) is binding; anything else is a "Request for Task 13" in the report.
- Definition of done per task: `npm run check` green with pristine output; no `console.log`, no `any`, no `// TODO`, no unused exports; commits `type: summary` ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; push after the final commit (`git push -u origin <branch>`).
- Before using a shadcn component, read its generated file in `src/components/ui/` (base-nova wraps `@base-ui/react`; prop names differ from Radix-era shadcn).
- Dev servers: Wave 1 agents use ports 3001–3007 (assigned per task); never 3000 in Wave 1.

---

## Orchestration runbook (controller)

| Wave | Tasks | Mode | Model guidance |
| --- | --- | --- | --- |
| 0 | 1 → 2 → 3 → 4 → 5 | Sequential on `feat/energy-dashboard`; task review after each | T1 sonnet; T2 opus (mock world judgment); T3 sonnet; T4 opus (shell/layout judgment); T5 sonnet |
| 1 | 6 map · 7 list+filters · 8 kpi/status/flow · 9 charts · 10 building detail · 11 alerts · 12 devices | **Parallel**, seven worktrees `../OSNOVA-ed-<area>` on `feat/ed-<area>`, `npm ci` each | T6 opus; T10 opus; others sonnet |
| 2 | 13 compose pages (+ merge) → 14 responsive/a11y/e2e/docs → 15 final review + cleanup + PR | Sequential on `feat/energy-dashboard` | T13 opus; T14 sonnet; T15 final reviewer opus |

Per-task loop, briefs, review packages, ledger, fix loops: exactly as in superpowers:subagent-driven-development (scripts under that skill's `scripts/`). Wave 1 reviews run per branch over `<wave0-exit>..feat/ed-<area>`. Preview pages: each Wave 1 task adds `src/app/(dashboard)/dev/<area>/page.tsx`; Task 13 deletes `src/app/(dashboard)/dev/`.

Pre-flight (human): none beyond approving the `npm install` in Task 1. Chromium for Playwright is already installed.

Cleanup (Task 15): delete `dev/` pages, `feat/ed-*` branches and worktrees (local + remote), the SDD workspace; confirm `git status` clean; open the PR `feat/energy-dashboard → main`.

---

## Wave 0 — Foundation (sequential)

### Task 1: Design system, fonts, tokens, shadcn additions, virtual list dependency

**Files:**
- Modify: `package.json`, `src/app/globals.css`, `src/app/layout.tsx`
- Create: `src/lib/design-tokens.ts`, `src/lib/design-tokens.test.ts`
- Create (generated): `src/components/ui/{skeleton,table,tabs,dropdown-menu,checkbox,tooltip}.tsx`

**Interfaces:**
- Produces: CSS variables per spec §12 on `:root`; `--font-sans` = Inter; `COLORS`, `STATUS_META`, `CONNECTIVITY_META`, `SEVERITY_META`, `SYSTEM_META`, `DEVICE_META`, `SYSTEM_STATUS_META` from `@/lib/design-tokens`; the six shadcn components.

- [ ] **Step 1: Install the dependency and shadcn components**

```bash
npm install @tanstack/react-virtual
npx shadcn@latest add skeleton table tabs dropdown-menu checkbox tooltip -y
```

Verify the six files exist; do not edit them. `@tanstack/react-virtual` is the only new runtime dependency allowed by the spec.

- [ ] **Step 2: Write the failing token test `src/lib/design-tokens.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import {
  COLORS,
  CONNECTIVITY_META,
  DEVICE_META,
  SEVERITY_META,
  STATUS_META,
  SYSTEM_META,
  SYSTEM_STATUS_META,
} from "@/lib/design-tokens";

describe("design tokens", () => {
  it("carries the PRD palette", () => {
    expect(COLORS.primary).toBe("#0065A8");
    expect(COLORS.primaryDark).toBe("#003B5C");
    expect(COLORS.background).toBe("#F4F7F9");
    expect(COLORS.border).toBe("#D9E1E6");
    expect(COLORS.critical).toBe("#D64545");
    expect(COLORS.solar).toBe("#F5B82E");
    expect(COLORS.battery).toBe("#7A5AF8");
  });

  it("maps every building status to a label, colour and icon", () => {
    expect(Object.keys(STATUS_META)).toEqual(["normal", "efficient", "warning", "critical", "offline"]);
    expect(STATUS_META.normal.color).toBe(COLORS.primary);
    expect(STATUS_META.efficient.color).toBe(COLORS.success);
    expect(STATUS_META.warning.color).toBe(COLORS.warning);
    expect(STATUS_META.critical.color).toBe(COLORS.critical);
    expect(STATUS_META.offline.color).toBe(COLORS.offline);
    for (const meta of Object.values(STATUS_META)) {
      expect(meta.label.length).toBeGreaterThan(0);
      expect(meta.icon).toBeTypeOf("object");
    }
  });

  it("maps severities, connectivity, systems, devices and system statuses", () => {
    expect(Object.keys(SEVERITY_META)).toEqual(["critical", "warning", "info"]);
    expect(Object.keys(CONNECTIVITY_META)).toEqual(["online", "warning", "offline"]);
    expect(Object.keys(SYSTEM_META)).toEqual(["pv", "battery", "hvac", "ev_charging", "meter", "other"]);
    expect(SYSTEM_META.pv.color).toBe(COLORS.solar);
    expect(SYSTEM_META.battery.color).toBe(COLORS.battery);
    expect(Object.keys(DEVICE_META)).toEqual(["pv_inverter", "battery", "meter", "hvac_controller", "ev_charger", "sensor"]);
    expect(Object.keys(SYSTEM_STATUS_META)).toEqual(["online", "charging", "discharging", "idle", "warning", "error", "offline"]);
  });
});
```

- [ ] **Step 3: Create `src/lib/design-tokens.ts`**

Export exactly:

```ts
export const COLORS = {
  primary: "#0065A8", primaryDark: "#003B5C", primaryHover: "#00558C", primaryLight: "#EAF4FA",
  background: "#F4F7F9", white: "#FFFFFF", text: "#1D252C", textSecondary: "#66727C", border: "#D9E1E6",
  success: "#2E8B57", warning: "#F59E0B", critical: "#D64545", offline: "#8A959E", solar: "#F5B82E", battery: "#7A5AF8",
} as const;
export type Meta = { label: string; color: string; icon: LucideIcon };
export const STATUS_META: Record<BuildingStatus, Meta>;            // normal→primary/Building2, efficient→success/Leaf, warning→warning/TriangleAlert, critical→critical/OctagonAlert, offline→offline/WifiOff
export const CONNECTIVITY_META: Record<Connectivity, Meta>;        // online→success/Wifi, warning→warning/Wifi, offline→offline/WifiOff
export const SEVERITY_META: Record<AlertSeverity, Meta>;           // critical→critical/OctagonAlert, warning→warning/TriangleAlert, info→primary/Info
export const SYSTEM_META: Record<SystemType, Meta>;                // pv→solar/Sun, battery→battery/BatteryCharging, hvac→primary/Fan, ev_charging→primaryDark/Car, meter→textSecondary/Gauge, other→textSecondary/Boxes
export const DEVICE_META: Record<DeviceType, Meta>;                // pv_inverter→solar/Zap, battery→battery/BatteryCharging, meter→textSecondary/Gauge, hvac_controller→primary/Fan, ev_charger→primaryDark/Car, sensor→textSecondary/Thermometer
export const SYSTEM_STATUS_META: Record<SystemStatus, Meta>;       // online→success, charging→battery, discharging→battery, idle→textSecondary, warning→warning, error→critical, offline→offline (icons: Circle for the neutral ones, else as above)
```

The status/system types come from `@/lib/types` **as it will be after Task 2**; to keep Task 1 self-contained, add the type aliases for `BuildingStatus`, `Connectivity`, `AlertSeverity`, `SystemType`, `DeviceType`, `SystemStatus` to `src/lib/types.ts` now (append; do not remove the existing fingerprint types yet — Task 2 rewrites the file).

- [ ] **Step 4: Theme tokens in `src/app/globals.css`**

Replace the `:root` block so the shadcn token names carry the PRD palette (hex is fine in Tailwind v4):

```css
:root {
  --background: #F4F7F9; --foreground: #1D252C;
  --card: #FFFFFF; --card-foreground: #1D252C;
  --popover: #FFFFFF; --popover-foreground: #1D252C;
  --primary: #0065A8; --primary-foreground: #FFFFFF;
  --secondary: #EAF4FA; --secondary-foreground: #003B5C;
  --muted: #EEF2F5; --muted-foreground: #66727C;
  --accent: #EAF4FA; --accent-foreground: #003B5C;
  --destructive: #D64545;
  --border: #D9E1E6; --input: #D9E1E6; --ring: #0065A8;
  --chart-1: #F5B82E; --chart-2: #7A5AF8; --chart-3: #0065A8; --chart-4: #2E8B57; --chart-5: #66727C;
  --radius: 0.5rem;
  --sidebar: #FFFFFF; --sidebar-foreground: #1D252C; --sidebar-primary: #0065A8; --sidebar-primary-foreground: #FFFFFF;
  --sidebar-accent: #EAF4FA; --sidebar-accent-foreground: #003B5C; --sidebar-border: #D9E1E6; --sidebar-ring: #0065A8;
  --status-success: #2E8B57; --status-warning: #F59E0B; --status-critical: #D64545; --status-offline: #8A959E;
  --energy-solar: #F5B82E; --energy-battery: #7A5AF8;
}
```

Add to `@theme inline`: `--color-status-success: var(--status-success)` (and warning/critical/offline, energy-solar, energy-battery) so `text-status-critical`, `bg-energy-solar` etc. exist. Add utilities in `@layer base`: `.text-kpi { @apply text-3xl font-semibold tabular-nums tracking-tight; }`, `.text-label { @apply text-xs font-medium text-muted-foreground; }`. Leave `.dark` as is.

- [ ] **Step 5: Inter in `src/app/layout.tsx`**

Replace Geist with `Inter` from `next/font/google` (`variable: "--font-sans"`, `subsets: ["latin"]`); keep Geist Mono for `--font-geist-mono`. Metadata title `AEW Energy Management`, description `Energy infrastructure monitoring for the Aargau region.` Keep `<Providers>` and `h-full overflow-hidden` body classes.

- [ ] **Step 6: Check and commit**

Run `npm run check` → green (the token test passes; existing tests still pass).

```bash
git add package.json package-lock.json src/app/globals.css src/app/layout.tsx src/lib/design-tokens.ts src/lib/design-tokens.test.ts src/lib/types.ts src/components/ui
git commit -m "feat(frontend): AEW design tokens, Inter, shadcn table/tabs/skeleton, react-virtual

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Data contract, geometry helpers, mock world, series and fingerprint generators

**Files:**
- Rewrite: `src/lib/types.ts` (spec §5 verbatim, plus `BuildingFilters`, `BuildingSort`)
- Create: `src/lib/geo.ts`, `src/lib/mock/world.ts`, `src/lib/mock/alerts.ts`, `src/lib/mock/series.ts`, `src/lib/mock/fingerprint.ts`, `src/lib/mock/index.ts`
- Move: `src/lib/mock-data.ts` → folded into `src/lib/mock/fingerprint.ts` (delete the old file and its test after migration)
- Test: `src/lib/geo.test.ts`, `src/lib/mock/world.test.ts`, `src/lib/mock/series.test.ts`, `src/lib/mock/fingerprint.test.ts`
- Keep: `src/lib/random.ts`, `src/lib/plz.ts` (add `PLZ_POLYGONS: Record<string, Polygon>` export used by geo sampling)

**Interfaces:**
- Consumes: `createRng` (`@/lib/random`), `PLZ_AREAS`, `PLZ_BY_CODE` (`@/lib/plz`), `aargau-plz.json`.
- Produces (must match exactly):

```ts
// geo.ts
export function pointInPolygon(point: [number, number], polygon: Polygon): boolean;          // ray casting, outer ring minus holes
export function randomPointInPolygon(rng: Rng, polygon: Polygon, bbox: Bbox, maxTries?: number): [number, number]; // [lng, lat]; falls back to bbox centre after maxTries (default 50)
// mock/index.ts
export const MOCK_SEED = 42; export const MOCK_NOW = "2026-09-10T16:42:31+02:00";
export type World = { buildings: Building[]; systems: EnergySystem[]; devices: Device[]; alerts: Alert[]; now: string };
export function getWorld(): World;                    // memoised generateWorld(MOCK_SEED)
export function generateWorld(seed: number): World;   // deterministic
export function getBuildingDetail(buildingId: string): BuildingDetail | undefined;
export function generateSeries(scope: "region" | string, range: TimeRange, seed?: number): EnergySeries;
export function generateFingerprint(buildingId: string, seed?: number): Fingerprint | undefined; // undefined for unknown ids
export const DEMO_BUILDING_ID = "BLD-0001";
```

- [ ] **Step 1: Rewrite `src/lib/types.ts`** from spec §5 (all types verbatim; keep `ASSET_KEYS`, `EVENT_TYPES`). Add:

```ts
export type BuildingFilters = { plz: string[]; statuses: BuildingStatus[]; systems: SystemType[]; connectivity: Connectivity[] };
export type BuildingSort = "id" | "severity" | "consumption" | "production";
```

Expect `npm run typecheck` to fail in the old demo components (`address`, `city`, `postcode` gone) — that is expected until Task 5 migrates them. For this task, run only the new tests plus `npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v components/` to confirm `src/lib` compiles; the full `npm run check` gate is Task 5's.

- [ ] **Step 2: Write the failing geo tests `src/lib/geo.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { pointInPolygon, randomPointInPolygon } from "@/lib/geo";
import { PLZ_BY_CODE, PLZ_POLYGONS } from "@/lib/plz";
import { createRng } from "@/lib/random";

const square = { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]] } as const;
const withHole = { type: "Polygon", coordinates: [square.coordinates[0], [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]] } as const;

describe("pointInPolygon", () => {
  it("detects inside, outside and holes", () => {
    expect(pointInPolygon([5, 5], square)).toBe(true);
    expect(pointInPolygon([11, 5], square)).toBe(false);
    expect(pointInPolygon([5, 5], withHole)).toBe(false);
    expect(pointInPolygon([2, 2], withHole)).toBe(true);
  });
});

describe("randomPointInPolygon", () => {
  it("returns deterministic points inside the real Aarau polygon", () => {
    const polygon = PLZ_POLYGONS["5000"];
    const bbox = PLZ_BY_CODE["5000"].bbox;
    const a = randomPointInPolygon(createRng(1), polygon, bbox);
    const b = randomPointInPolygon(createRng(1), polygon, bbox);
    expect(a).toEqual(b);
    for (let i = 0; i < 20; i++) {
      const p = randomPointInPolygon(createRng(i), polygon, bbox);
      expect(pointInPolygon(p, polygon)).toBe(true);
    }
  });
});
```

- [ ] **Step 3: Implement `src/lib/geo.ts` and add `PLZ_POLYGONS` to `src/lib/plz.ts`** (`Record<plz, Polygon>` built from the same collection). Run the geo tests → PASS.

- [ ] **Step 4: Write the failing world tests `src/lib/mock/world.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { pointInPolygon } from "@/lib/geo";
import { DEMO_BUILDING_ID, generateWorld, getBuildingDetail, getWorld, MOCK_NOW } from "@/lib/mock";
import { PLZ_BY_CODE, PLZ_POLYGONS } from "@/lib/plz";

const world = getWorld();

describe("mock world", () => {
  it("is deterministic and sized for the performance targets", () => {
    expect(generateWorld(42).buildings.map((b) => b.buildingId)).toEqual(world.buildings.map((b) => b.buildingId));
    expect(world.buildings.length).toBe(1200);
    expect(world.devices.length).toBeGreaterThanOrEqual(5000);
    expect(world.alerts.length).toBeGreaterThanOrEqual(150);
    expect(world.now).toBe(MOCK_NOW);
  });

  it("uses unique ids and no address-like fields", () => {
    expect(new Set(world.buildings.map((b) => b.buildingId)).size).toBe(1200);
    expect(new Set(world.devices.map((d) => d.deviceId)).size).toBe(world.devices.length);
    expect(new Set(world.alerts.map((a) => a.alertId)).size).toBe(world.alerts.length);
    for (const key of Object.keys(world.buildings[0])) expect(key).not.toMatch(/address|street|city/i);
    expect(world.buildings[0].buildingId).toBe(DEMO_BUILDING_ID);
    expect(world.buildings[0].plz).toBe("5000");
  });

  it("places every building inside its own PLZ polygon", () => {
    for (const b of world.buildings) {
      expect(PLZ_BY_CODE[b.plz], b.buildingId).toBeDefined();
      expect(pointInPolygon([b.longitude, b.latitude], PLZ_POLYGONS[b.plz]), b.buildingId).toBe(true);
    }
  });

  it("has a plausible status distribution and consistent derived fields", () => {
    const count = (s: string) => world.buildings.filter((b) => b.status === s).length / 1200;
    expect(count("normal")).toBeGreaterThan(0.45);
    expect(count("efficient")).toBeGreaterThan(0.1);
    expect(count("warning")).toBeGreaterThan(0.05);
    expect(count("critical")).toBeGreaterThan(0.02);
    expect(count("offline")).toBeGreaterThan(0.005);
    for (const b of world.buildings) {
      const detail = getBuildingDetail(b.buildingId)!;
      expect(detail.devices.length).toBe(b.deviceCount);
      expect(detail.systems.map((s) => s.type).sort()).toEqual([...b.systemTypes].sort());
      const active = detail.alerts.filter((a) => a.status === "active");
      expect(active.filter((a) => a.severity === "critical").length).toBe(b.alertCounts.critical);
      expect(active.filter((a) => a.severity === "warning").length).toBe(b.alertCounts.warning);
      expect(b.searchText).toContain(b.buildingId.toLowerCase());
      expect(b.searchText).toContain(b.plz);
      if (detail.devices[0]) expect(b.searchText).toContain(detail.devices[0].deviceId.toLowerCase());
      expect(b.energy.selfConsumptionPct).toBeGreaterThanOrEqual(0);
      expect(b.energy.selfConsumptionPct).toBeLessThanOrEqual(100);
      if (b.status === "offline") expect(b.connectivity).toBe("offline");
      if (b.status === "critical") expect(b.alertCounts.critical + detail.devices.filter((d) => d.status === "error" || d.status === "offline").length).toBeGreaterThan(0);
    }
  });

  it("gives every system a meter and type-appropriate device measurements", () => {
    for (const b of world.buildings.slice(0, 200)) {
      const detail = getBuildingDetail(b.buildingId)!;
      expect(detail.systems.some((s) => s.type === "meter")).toBe(true);
      for (const d of detail.devices) {
        expect(d.measurements.length).toBeGreaterThan(0);
        expect(d.currentValue.unit.length).toBeGreaterThan(0);
        if (d.type === "battery") expect(d.measurements.some((m) => m.key === "soc")).toBe(true);
        if (d.type === "pv_inverter") expect(d.measurements.some((m) => m.key === "power")).toBe(true);
      }
    }
    expect(getBuildingDetail("BLD-9999")).toBeUndefined();
  });
});
```

- [ ] **Step 5: Implement `src/lib/mock/world.ts` and `src/lib/mock/alerts.ts`** per spec §6 (PLZ pool weighting, systems/devices per building, manufacturers such as "Fronius", "SMA", "Huawei", "Landis+Gyr", "Siemens", "ABB", "Tesla"; models and serials generated; status derivation rules; `searchText`; alert templates and timestamps within 48 h of `MOCK_NOW`; `lastUpdated` rules). Keep each file under ~350 lines; extract `devices.ts` if needed (same directory, owned by this task). Run the world tests → PASS. If a distribution assertion misses, tune probabilities, not the assertion.

- [ ] **Step 6: Write the failing series tests `src/lib/mock/series.test.ts`**

```ts
import { describe, expect, it } from "vitest";

import { generateSeries, MOCK_NOW } from "@/lib/mock";

describe("generateSeries", () => {
  it.each([
    ["today", 15, 67],   // 00:00 → 16:30 inclusive at 15 min = 67 points
    ["24h", 15, 96],
    ["7d", 60, 168],
    ["30d", 1440, 30],
    ["12m", 43200, 12],
  ] as const)("range %s has step %s and %s points", (range, step, points) => {
    const s = generateSeries("region", range);
    expect(s.stepMinutes).toBe(step);
    expect(s.production.length).toBe(points);
    expect(s.consumption.length).toBe(points);
    expect(s.gridImport.length).toBe(points);
    expect(s.gridExport.length).toBe(points);
    expect(Date.parse(s.production[s.production.length - 1].timestamp)).toBeLessThanOrEqual(Date.parse(MOCK_NOW));
  });

  it("is deterministic per scope and range, non-negative, and has a battery series for battery buildings only", () => {
    expect(generateSeries("BLD-0001", "24h")).toEqual(generateSeries("BLD-0001", "24h"));
    expect(generateSeries("BLD-0001", "24h")).not.toEqual(generateSeries("BLD-0002", "24h"));
    for (const p of generateSeries("region", "7d").production) expect(p.value).toBeGreaterThanOrEqual(0);
    expect(generateSeries("region", "24h").batterySoc).toBeDefined();
    expect(generateSeries("BLD-0001", "24h").batterySoc).toBeUndefined(); // BLD-0001 has no battery (48% → none installed)
  });
});
```

- [ ] **Step 7: Implement `src/lib/mock/series.ts`** per spec §6 (`today` = from local midnight to `MOCK_NOW` rounded down to the step; `24h` = 96 points ending at `MOCK_NOW` rounded down; daily/monthly buckets end at the bucket containing now). Region SoC = fleet average. Run → PASS.

- [ ] **Step 8: Migrate the fingerprint generator** into `src/lib/mock/fingerprint.ts` (`generateFingerprint(buildingId)`; `BLD-0001` hand-authored as the old `AG-004711`; other buildings: predictions derived from their real systems — PV present → pv 75–98, battery present → 60–95, EV present → 60–95, HVAC → heatPump 55–95, absent → 3–40 — so predictions agree with the world). Port `src/lib/mock-data.test.ts` assertions to `src/lib/mock/fingerprint.test.ts` (demo values, events, plateau/dip, 96 points, deterministic). Delete `src/lib/mock-data.ts` and its test.

- [ ] **Step 9: Verify and commit**

Run `npx vitest run src/lib` → all lib tests green (component tests may fail until Task 5 — do not run them).

```bash
git add src/lib
git commit -m "feat(frontend): dashboard data contract, geometry helpers and seeded mock world

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: API swap point, hooks, store, filters, aggregation, freshness, formatting

**Files:**
- Rewrite: `src/lib/api.ts`, `src/stores/ui-store.ts`, `src/hooks/use-buildings.ts`
- Create: `src/hooks/use-devices.ts`, `src/hooks/use-alerts.ts`, `src/hooks/use-series.ts`, `src/hooks/use-fingerprint.ts`, `src/hooks/use-system-status.ts`, `src/hooks/use-now.ts`, `src/lib/filters.ts`, `src/lib/aggregate.ts`, `src/lib/freshness.ts`, `src/lib/format.ts`
- Delete: `src/lib/search.ts` (+ test; its normaliser moves into `filters.ts`)
- Test: `src/lib/filters.test.ts`, `src/lib/aggregate.test.ts`, `src/lib/freshness.test.ts`, `src/lib/format.test.ts`, `src/stores/ui-store.test.ts` (rewrite), `src/hooks/use-buildings.test.tsx` (rewrite), `src/test/fixtures.ts` (rewrite: `makeBuilding`, `makeDevice`, `makeAlert`, `makeSeries`, `makeFingerprint`)

**Interfaces (must match exactly):**

```ts
// api.ts — every function async with MOCK_LATENCY_MS = 120
export function fetchBuildings(): Promise<Building[]>;
export function fetchBuilding(buildingId: string): Promise<BuildingDetail>;     // rejects with Error("Building not found") for unknown ids
export function fetchDevices(): Promise<Device[]>;
export function fetchAlerts(): Promise<Alert[]>;
export function fetchSeries(scope: "region" | string, range: TimeRange): Promise<EnergySeries>;
export function fetchFingerprint(buildingId: string): Promise<Fingerprint>;      // rejects for unknown ids
export function fetchSystemStatus(): Promise<SystemStatusSummary>;
// filters.ts
export const DEFAULT_FILTERS: BuildingFilters;
export const STATUS_SEVERITY: Record<BuildingStatus, number>;                    // critical 0, warning 1, offline 2, normal 3, efficient 4
export function normalizeText(value: string): string;
export function applyBuildingFilters(buildings: Building[], filters: BuildingFilters, query: string): Building[];
export function sortBuildings(buildings: Building[], sort: BuildingSort): Building[];  // returns a new array
export function isFilterActive(filters: BuildingFilters): boolean;
export function plzOptions(buildings: Building[]): { plz: string; label: string; count: number }[];  // label via formatPlz, sorted by plz
// aggregate.ts
export function computeKpis(buildings: Building[], alerts: Alert[]): Kpis;
export function computeSystemStatus(buildings: Building[], devices: Device[], alerts: Alert[], now: string): SystemStatusSummary;
export function attentionList(buildings: Building[], n: number): Building[];
export function countByPlz(buildings: Building[]): Record<string, number>;
export function consumptionBySystemType(systems: EnergySystem[]): { type: SystemType; kwh: number }[];
// freshness.ts
export const STALE_AFTER_MINUTES = 15;
export function freshnessOf(lastUpdated: string, now: string, thresholdMinutes?: number): { ageMinutes: number; isDelayed: boolean; label: string };
// format.ts
export function formatKw(v: number): string;        // "24.6 kW"
export function formatKwh(v: number): string;       // "18.2 kWh", "1.3 MWh" (≥1000), "2.4 GWh" (≥1e6)
export function formatPercent(v: number): string;   // "74%"
export function formatTime(iso: string): string;    // "16:42"
export function formatTimeSeconds(iso: string): string; // "16:42:31"
export function formatDateTime(iso: string): string; // "10 Sep 2026, 16:42"
export function formatRelative(iso: string, now: string): string; // "just now", "10 minutes ago", "3 hours ago", "2 days ago"
export function formatNumber(v: number): string;    // "1,284"
// ui-store.ts — spec §8, plus `export const initialUIState`
// hooks — spec §9 names; useFilteredBuildings returns { buildings, total, isLoading, isError, refetch }
```

- [ ] **Step 1: Tests first.** Write `filters.test.ts` (AND across groups / OR within; search matches device id; empty query returns same reference; sort by severity puts critical first and is stable), `aggregate.test.ts` (KPIs sum production/consumption and count active alerts only; `incident` when any active critical; `degraded` when > 1 % devices offline; `operational` otherwise; attention order critical → warning → offline, ties by alert counts desc; distribution sums per type), `freshness.test.ts` (14 min → not delayed, 16 → delayed; label "Last updated 16:42:31" vs "Data delayed · 18 min ago"), `format.test.ts` (scaling and locale `en-CH`-style thousands separator `'`? — use `"1,284"` with `en-US` grouping as the spec example), `ui-store.test.ts` (initial state, `togglePlz` adds/removes, `clearFilters` resets filters and search, `selectBuilding(null)`), `use-buildings.test.tsx` (mock `@/lib/api`; filtered + total; attention list; refetch after error). Use the fixtures.

- [ ] **Step 2: Implement** each module until its test passes. `useFilteredBuildings` memoises `applyBuildingFilters` then `sortBuildings`; `useKpis`/`useSystemStatus` derive from `useBuildings` + `useAlerts` (+ `useDevices` for status) via `useMemo` — do not add a separate query for KPIs except `useSystemStatus`, which uses `fetchSystemStatus` (so the API shape matches a future backend). `useNow()` returns `MOCK_NOW` from a tiny module `src/lib/now.ts` re-exported by the hook (the only place a real clock would be wired).

- [ ] **Step 3: Verify and commit** — `npx vitest run src/lib src/stores src/hooks` green.

```bash
git add src/lib src/stores src/hooks src/test/fixtures.ts
git commit -m "feat(frontend): dashboard data layer, store, filters and aggregation

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Dashboard shell, routes, shared primitives, states kit, chart stubs

**Files:**
- Create: `src/app/(dashboard)/layout.tsx`, `src/app/(dashboard)/page.tsx`, `src/app/(dashboard)/buildings/page.tsx`, `src/app/(dashboard)/buildings/[buildingId]/page.tsx`, `src/app/(dashboard)/devices/page.tsx`, `src/app/(dashboard)/energy/page.tsx`, `src/app/(dashboard)/alerts/page.tsx`, `src/app/(dashboard)/settings/page.tsx` (all placeholders rendering `<PageHeader>` + an `EmptyState "Coming in this release"`)
- Delete: `src/app/page.tsx` (the route group's page replaces it)
- Create: `src/components/shell/{dashboard-shell,sidebar,header,global-search,notifications-button,system-status-pill,nav-items}.tsx`, `src/components/shell/dashboard-shell.test.tsx`
- Create: `src/components/primitives/{page-header,section-card,status-badge,severity-badge,system-type-icon,metric}.tsx`, `src/components/primitives/status-badge.test.tsx`
- Create: `src/components/states/{empty-state,error-state,data-freshness,skeletons}.tsx`, `src/components/states/states.test.tsx`
- Create (stubs, replaced by Task 9): `src/components/charts/{time-range-selector,energy-chart,battery-chart,distribution-donut,grid-chart}.tsx` with the final prop types and a `data-testid` placeholder each
- Modify: `src/lib/utils.ts` (add `cn` re-export unchanged; add nothing else)

**Interfaces:** spec §10 rows for `DashboardShell`, `Sidebar`, `Header`, `PageHeader`, `SectionCard`, `StatusBadge`, `SeverityBadge`, states kit, chart stubs. Additional:

```ts
// nav-items.ts
export const NAV_ITEMS: { href: string; label: string; icon: LucideIcon; match: (pathname: string) => boolean }[]; // Overview "/", Buildings "/buildings" (also matches /buildings/*), Devices, Energy, Alerts, Settings
export function sectionTitle(pathname: string): string;  // "Overview" | "Buildings" | "Building detail" | "Devices" | "Energy" | "Alerts" | "Settings"
// primitives
export function StatusBadge({ status, size? }: { status: BuildingStatus | Connectivity | DeviceStatus | SystemStatus; size?: "sm" | "md" }); // dot + label from the matching *_META; text always rendered
export function SeverityBadge({ severity }: { severity: AlertSeverity });
export function Metric({ label, value, unit?, hint? }: ...); // small label over tabular value
// states
export function EmptyState({ title, description?, action?: ReactNode, icon? });
export function ErrorState({ title?, message?, onRetry });       // button "Try again" calls onRetry
export function DataFreshness({ lastUpdated, onRefresh, isRefreshing? }); // uses freshnessOf(lastUpdated, useNow()); shows "Last updated 16:42:31" or "Data delayed · 18 min ago" with a warning tone; refresh button aria-label "Refresh data"
export function SkeletonCard(), SkeletonTable({ rows? }), SkeletonMap(), SkeletonChart()
```

Behaviour: sidebar 240 px with nav items (icon + label), active item `bg-accent text-accent-foreground` with a 2 px primary left bar; collapse button; at `md`..`lg` render the icon rail (64 px, labels as tooltips); below `md` hidden, `Header` shows a hamburger that opens a left `Sheet` with the nav. Header: section title (`sectionTitle(usePathname())`), `GlobalSearch` (Input with `aria-label="Search buildings, PLZ or devices"`, placeholder `Search buildings, PLZ or devices...`, 200 ms debounce into `setSearchQuery`), `NotificationsButton` (Bell with active-alert count badge, links to `/alerts`, `aria-label="Alerts, N active"`), `SystemStatusPill` (dot + "Operational"/"Degraded"/"Incident" from `useSystemStatus`; skeleton while loading), user menu placeholder (avatar initials "OP", `DropdownMenu` with "Profile", "Sign out" disabled items).

Tests: shell renders nav with six items and marks the active one by pathname (mock `next/navigation`); header title changes with pathname; search debounces into the store (fake timers); `StatusBadge` renders the label text for every status; `ErrorState` calls `onRetry`; `DataFreshness` shows delayed label when stale.

- [ ] **Step 1: Tests → implement → `npm run typecheck` may still fail on old demo components; run `npx vitest run src/components/shell src/components/primitives src/components/states` green.**
- [ ] **Step 2: Commit** `feat(frontend): dashboard shell, routes, primitives, states kit and chart stubs`.

---

### Task 5: Migrate the fingerprint UI and delete the demo shell

**Files:**
- Move + adapt: `src/components/detail/{prediction-card,prediction-cards,why-popover,prediction-explanation,technical-details}.tsx` → `src/components/predictions/`; `src/components/chart/electricity-chart.tsx` + `chart-legend.tsx` → `src/components/predictions/fingerprint-chart.tsx` + `fingerprint-legend.tsx`; `src/lib/chart-option.ts` → `src/lib/chart-options/fingerprint.ts`; tests move alongside and are updated to the `Fingerprint` type and `makeFingerprint()`.
- Create: `src/components/predictions/predictions-section.tsx` (`{ buildingId }`; uses `useFingerprint`; loading `SkeletonChart`, error `ErrorState`, content: cards → chart → explanation → technical details) + test.
- Delete: `src/components/app-shell.tsx` (+test), `src/components/header/*`, `src/components/buildings/*` (old list/card/chip/area-header), `src/components/detail/building-detail-sheet.tsx` (+test), `src/components/map/*` (old single-select map; Task 6 rewrites the directory from scratch), `e2e/demo-flow.spec.ts` (Task 14 writes the new suite; leave `e2e/.gitkeep`).
- Modify: `src/lib/predictions.ts` — keep `PREDICTION_THRESHOLDS`, `getPredictionLabel`, `formatProbability`, `ASSETS`, `ASSET_BY_KEY`, `describePrediction`, `formatContribution`; `src/lib/events.ts` unchanged.

- [ ] **Step 1: Perform the moves with `git mv`, fix imports, adapt props** (`PredictionCards` now takes `fingerprint.predictions` / `fingerprint.explanation`; `FingerprintChart` takes `electricity`, `events`).
- [ ] **Step 2: `npm run check` must be fully green** (this is the Wave 0 exit gate: lint, typecheck, all tests). `npm run build` green with routes `/`, `/buildings`, `/buildings/[buildingId]`, `/devices`, `/energy`, `/alerts`, `/settings`.
- [ ] **Step 3: Commit** `refactor(frontend): move fingerprint UI to predictions section; remove demo shell` and push.

**Wave 0 exit gate (controller):** Tasks 1–5 reviewed and complete; `npm run check` and `npm run build` green; `git status` clean. Record the exit commit; create the seven Wave 1 worktrees from it.

---

## Wave 1 — UI areas (parallel, one worktree per task)

Each task: branch `feat/ed-<area>` from the Wave 0 exit commit, `npm ci`, own only the listed files, add a preview page `src/app/(dashboard)/dev/<area>/page.tsx` (client; mounts the area's components with real hooks), verify in a browser on the assigned port, `npm run check`, commit, push. Anything outside ownership → "Requests for Task 13" in the report. All components are client components unless stated; all read data through hooks from Task 3 and primitives from Task 4.

### Task 6: Map — clustered status markers over PLZ zones (port 3001, model opus)

**Files:** `src/components/map/{buildings-map,buildings-map-lazy,plz-layers,building-layers,map-tooltip,map-legend,map-controls}.tsx`, `src/lib/map/{building-geojson,expressions}.ts`, tests `src/lib/map/*.test.ts`, `src/components/map/buildings-map.test.tsx`, preview `src/app/(dashboard)/dev/map/page.tsx`.

**Contract (spec §10 `BuildingsMap`):**
```ts
export type BuildingsMapProps = {
  buildings: Building[];
  selectedBuildingId: string | null;
  selectedPlz: string[];                       // highlighted/filtered PLZs
  onSelectBuilding: (buildingId: string) => void;   // marker click
  onOpenBuilding?: (buildingId: string) => void;    // marker double-click / tooltip "Open" / Enter on a focused marker
  onSelectPlz: (plz: string) => void;           // PLZ polygon click (toggle is the caller's job)
  fitTo?: "aargau" | "selection";               // default "aargau"; "selection" fits to selected building or selected PLZs
  isLoading?: boolean; className?: string;
};
export function BuildingsMap(props: BuildingsMapProps);
export const BuildingsMapLazy = dynamic(() => import("./buildings-map").then(m => m.BuildingsMap), { ssr: false, loading: SkeletonMap });
// lib/map/building-geojson.ts
export function buildingsToGeoJson(buildings: Building[]): FeatureCollection<Point, { buildingId; plz; status; production; consumption }>;
// lib/map/expressions.ts
export function statusColorExpression(): ExpressionSpecification;   // match on ["get","status"] → STATUS_META colours, fallback primary
export function plzInFilter(plz: string[]): ExpressionSpecification; // ["in", ["get","plz"], ["literal", plz]] or a never-matching filter when empty
export const CLUSTER_RADIUS = 40; export const CLUSTER_MAX_ZOOM = 13;
```
Behaviour: `Source id="buildings" type="geojson" cluster clusterRadius={40} clusterMaxZoom={13}`; layers `clusters` (circle, radius stepped by `point_count` 14/18/24, colour primary, white stroke), `cluster-count` (symbol, `text-field ["get","point_count_abbreviated"]`, white, `text-font ["Noto Sans Regular"]` if the style lacks it fall back to `["Open Sans Regular"]` — verify in the browser), `buildings-point` (circle radius 6, status colour, white 1.5 px stroke, filter `!has point_count`), `buildings-selected` (circle radius 10, stroke `#003B5C` 3 px, filter by selected id). PLZ layers as the demo's, but the highlight filter is `plzInFilter(selectedPlz)` and the hover fill is separate. Clicking a cluster calls `getClusterExpansionZoom` on the source and `easeTo`. Hover on a point shows `MapTooltip` (ID, PLZ · town, `StatusBadge`, consumption today, production today); hover on a PLZ shows "5000 Aarau · N buildings" (N from the buildings prop). `MapLegend`: five statuses as dot + label, bottom-left. `MapControls`: NavigationControl bottom-right + a "Reset view" button (aria-label). When `selectedBuildingId` changes → `flyTo` the building (zoom ≥ 14, 900 ms). Keep the demo's worker `setWorkerUrl` and the resize-latch initial fit. Keyboard: the map container is focusable with an `aria-label` "Map of buildings in Aargau"; a visually hidden list is not required.
Tests (mocked `react-map-gl/maplibre` as the demo did): geojson builder shape; expressions; click on a point feature calls `onSelectBuilding`; click on a PLZ feature calls `onSelectPlz`; cluster click calls the source's expansion zoom then `easeTo`; tooltip text for a hovered point; selected id change calls `flyTo`; legend lists five statuses.
Preview: 1,200 buildings from `useBuildings()`; clicking PLZs toggles a local array; readout of the selected id.

### Task 7: Building list, filter bar, sorting (port 3002, model sonnet)

**Files:** `src/components/buildings/{building-list,building-row,filter-bar,plz-filter,status-filter,system-filter,connectivity-filter,sort-select,result-count}.tsx`, tests, preview `dev/list/page.tsx`.

**Contract:** `BuildingList({ buildings, selectedBuildingId, onSelect, onOpen, sort, onSortChange, isLoading?, isError?, onRetry? })` — virtualised with `@tanstack/react-virtual` (`useVirtualizer`, row height 72 px estimate, overscan 8) inside a `ScrollArea`-like scroll container (`overflow-y-auto`, `role="list"`); rows `role="listitem"` containing a `<button aria-pressed>` that selects on click, opens on double-click, and an explicit `<Link href="/buildings/{id}" aria-label="Open BLD-0001">` chevron. Row content: ID (font-medium), PLZ + town (`formatPlz`), `StatusBadge`, `Metric` Production / Consumption (`formatKwh`), small system-type icons (`SystemTypeIcon` with `title`). Selected row scrolls into view (`scrollToIndex`). Loading → `SkeletonTable rows=8`; error → `ErrorState`; empty → `EmptyState "No buildings found" "Try changing your filters."` with a "Clear filters" action when filters are active.
`FilterBar()` reads/writes the store: `PlzFilter` (Popover: search input + checkbox list from `plzOptions(allBuildings)` showing "5000 Aarau (12)", "Clear"), `StatusFilter` (five toggle buttons with `aria-pressed`, each `StatusBadge`), `SystemFilter` (Popover checklist of six system types with icons), `ConnectivityFilter` (three toggles), `SortSelect` (Select: ID, Severity, Consumption, Production), `ResultCount` ("N of M buildings"), "Clear filters" button visible when `isFilterActive`. Chips row shows active filters as removable chips.
Tests: rows render ID/PLZ/status/metrics; select vs open callbacks; sort select writes store; PLZ popover toggles store `filters.plz`; status toggle; clear filters resets; virtualiser renders a window (with jsdom, mock `useVirtualizer` or set container size) — at least assert that not all 1,200 rows are in the DOM for a 1,200-building fixture.

### Task 8: KPI cards, system status panel, attention list, active alerts, energy flow diagram (port 3003, model sonnet)

**Files:** `src/components/kpi/{kpi-card,kpi-grid,energy-kpi-row}.tsx`, `src/components/status/{system-status-panel,attention-list,active-alerts}.tsx`, `src/components/energy/energy-flow-diagram.tsx`, tests, preview `dev/kpi/page.tsx`.

**Contract:** `KpiCard({ label, value, unit?, hint?, icon, tone?: "default"|"success"|"warning"|"critical" })` (label `text-label`, value `text-kpi`, hint small; tone tints the icon only); `KpiGrid()` = five cards from `useKpis()` (Total buildings; Production today; Consumption today; Self-consumption; Active alerts with hint "N critical", tone critical when > 0) with `SkeletonCard`×5 while loading and `ErrorState` on error; `EnergyKpiRow({ summary })` = six `Metric`s (PRD §19) in a `SectionCard "Energy"`; `SystemStatusPanel()` from `useSystemStatus()` + `useNow()`: big state pill (dot + Operational/Degraded/Incident), six counts (buildings, devices, online, offline, warnings, critical) in a 3×2 grid, `DataFreshness` at the bottom wired to `refetch`; `AttentionList({ n })` from `useAttentionList(n)`: rows ID · PLZ · `StatusBadge` · alert counts · link, empty state "Nothing needs attention"; `ActiveAlerts({ n })` from `useActiveAlerts(n)`: `SeverityBadge` · title · building link · `formatRelative`, footer link "All alerts →" to `/alerts`, empty state "No alerts — All systems are operating normally."; `EnergyFlowDiagram({ summary })`: inline SVG (viewBox 0 0 640 260) with nodes Solar, Energy system, Battery, Building, Grid; arrows with labels production kWh, battery ± kW / SoC, consumption kWh, grid import / export kWh; colours solar/battery/primary; `role="img"` with `aria-label` summarising the numbers; no animation.
Tests: KPI grid renders five values formatted; status panel states and counts; attention ordering from fixtures; active alerts shows severity labels and relative time; flow diagram aria-label contains production and consumption; empty states.

### Task 9: Charts kit (port 3004, model sonnet)

**Files:** replace the stubs `src/components/charts/{time-range-selector,energy-chart,battery-chart,distribution-donut,grid-chart}.tsx` (keep prop types and `data-testid`s), add `src/components/charts/chart-frame.tsx`, `src/lib/chart-options/{axis,energy,battery,distribution,grid}.ts` + tests, preview `dev/charts/page.tsx`.

**Contract:** `TimeRangeSelector({ value, onChange })` segmented buttons Today / 24h / 7 days / 30 days / 12 months with `aria-pressed`; `ChartFrame({ title, subtitle?, ariaLabel, summary, actions?, height?, children })` renders `SectionCard`, an `sr-only` summary paragraph and the chart; `EnergyChart({ series, range, height? })` — production (solar colour, area 0.15) vs consumption (primary line 2 px), axis per range (`axis.ts`: `timeAxisFormatter(range)` → "HH:mm" for today/24h, "EEE HH:mm" for 7d, "d MMM" for 30d, "MMM" for 12m; y unit `kW` for step ≤ 60, `kWh` otherwise), legend, axis-trigger tooltip "10 Sep 16:30 · Production 8.4 kW · Consumption 12.1 kW", `animation: false`, SVG renderer, current value badge (last point) in the header; `BatteryChart({ series })` SoC % area (battery colour), y 0–100; `DistributionDonut({ data })` donut by system type using `SYSTEM_META` colours, centre label total kWh, legend with percentages; `GridChart({ series, range })` import (primary) vs export (success) bars/lines. Loading state: `SkeletonChart` when `series` undefined; empty when all points zero → `EmptyState "No data for this range"`.
Option builders are pure and tested: point mapping, unit choice per range, formatter outputs, colours from tokens, `animation: false`.
Preview: region series for all ranges, `BLD-0001` battery (none) and a battery building, donut from `consumptionBySystemType(getWorld().systems)` via a hook `useSeries`/`useBuildings` (preview may import `@/lib/mock` — the only place allowed, and it is deleted in Task 13).

### Task 10: Building detail page (port 3005, model opus)

**Files:** `src/components/building-detail/{building-detail-page,building-summary,systems-grid,system-card,devices-table,building-alerts,breadcrumb}.tsx`, `src/app/(dashboard)/buildings/[buildingId]/page.tsx` (replace placeholder: Server Component reading `params.buildingId` and rendering `<BuildingDetailPage buildingId={...} />`), tests, preview not needed (the route is live; verify at `/buildings/BLD-0001` and `/buildings/BLD-9999`).

**Contract:** `BuildingDetailPage({ buildingId })` uses `useBuilding(buildingId)`, `useSeries(buildingId, timeRange)`, store `timeRange`; layout: `Breadcrumb` (Buildings › BLD-0001) → `PageHeader` title "Building BLD-0001" with `StatusBadge` and actions (`DataFreshness` wired to refetch) → `BuildingSummary({ building })` (ID, PLZ · town, status, connectivity `StatusBadge`, last updated `formatDateTime`, device count, systems as `SystemTypeIcon` chips) → `EnergyKpiRow({ summary })` (from Task 8 — import path `@/components/kpi/energy-kpi-row`; if the branch does not have it yet, create a local minimal `EnergyKpiRow` in this directory and note it for Task 13 to dedupe) → `SectionCard "Energy profile"` with `TimeRangeSelector` + `EnergyChart` (+ `BatteryChart` when `series.batterySoc`) → `SystemsGrid({ systems })` of `SystemCard` (icon, label, `StatusBadge`, 2–3 metrics) → `DevicesTable({ devices })` (TanStack Table; columns Device, Type, Status, Current value, Last update; sortable headers with `aria-sort`; sticky header; rows are plain, no links) → `BuildingAlerts({ alerts })` (active first, `SeverityBadge`, title, device id, relative time; empty "No alerts for this building") → `PredictionsSection({ buildingId })` from Task 5 in a `SectionCard "Asset predictions"`. States: loading skeletons per section; error → `ErrorState` with retry; unknown id → `EmptyState "Building not found"` with link back to Buildings.
Tests: renders summary/KPIs/systems/devices/alerts from a mocked `fetchBuilding`; sorting a devices column reorders rows; not-found state; time range change calls the series hook with the new range.

### Task 11: Alerts page (port 3006, model sonnet)

**Files:** `src/components/alerts/{alerts-page,alerts-table,severity-tabs,alert-status-filter}.tsx`, `src/app/(dashboard)/alerts/page.tsx` (replace placeholder), tests.

**Contract:** `AlertsPage()`: `PageHeader "Alerts"` with counts; `SeverityTabs` (shadcn `Tabs`: All (n) / Critical (n) / Warning (n) / Info (n)); `AlertStatusFilter` (toggles Active / Acknowledged / Resolved, default Active only); `AlertsTable({ alerts })` — TanStack Table, columns Severity (`SeverityBadge`), Alert (title + description muted), Building (`Link` to `/buildings/{id}`), Device (id or "—"), Time (`formatDateTime` + relative), Status; default sort time desc; sortable Severity/Time; pagination 50/page with "Showing 1–50 of N" and Prev/Next buttons. States: loading `SkeletonTable`, error with retry, empty "No alerts — All systems are operating normally."
Tests: tabs filter by severity and show counts; status filter; default newest first; building link href; pagination controls.

### Task 12: Devices page (port 3007, model sonnet)

**Files:** `src/components/devices/{devices-page,device-filters,all-devices-table}.tsx`, `src/app/(dashboard)/devices/page.tsx` (replace placeholder), tests.

**Contract:** `DevicesPage()` uses `useDevices()` + `useBuildings()` (for PLZ lookup): `PageHeader "Devices"` with total count; `DeviceFilters({ value, onChange })` local state `{ types: DeviceType[]; statuses: DeviceStatus[]; plz: string[]; query: string }` (type checklist popover, status toggles, PLZ popover reusing the same UX as the buildings PLZ filter but implemented locally, search input debounced 200 ms matching device id/name/building id); `AllDevicesTable({ devices })` — TanStack Table with columns Device (id + name), Type (`DEVICE_META` icon + label), Building (`Link` to detail), PLZ, Status (`StatusBadge`), Current value, Last update; sortable; pagination 50/page; row count "Showing 1–50 of N". States per the kit. Rows must render only the current page (7,000 devices must not be in the DOM).
Tests: filters narrow the table; pagination bounds; sort by status; building link; empty state.

**Wave 1 exit gate (controller):** seven branches reviewed; reports' "Requests for Task 13" collected.

---

## Wave 2 — Composition, acceptance, review (sequential)

### Task 13: Merge Wave 1, compose Overview / Buildings / Energy / Settings, remove previews (model opus)

**Files:** merges of `feat/ed-{map,list,kpi,charts,detail,alerts,devices}`; `src/components/pages/{overview-page,buildings-page,energy-page,settings-page}.tsx` + tests; `src/app/(dashboard)/page.tsx`, `buildings/page.tsx`, `energy/page.tsx`, `settings/page.tsx` (replace placeholders); delete `src/app/(dashboard)/dev/`; apply every "Request for Task 13" as its own commit.

**Behaviour (spec §11):**
- `OverviewPage`: grid `lg:grid-cols-12`: `KpiGrid` (12) · `SystemStatusPanel` (4) + `BuildingsMapLazy` (8, height 420, all buildings, `onSelectBuilding` → `router.push('/buildings/{id}')`, `onSelectPlz` → `setFilters({ plz:[plz] })` + `router.push('/buildings')`) · `AttentionList n=8` (6) + `ActiveAlerts n=5` (6) · `SectionCard "Energy — last 24 hours"` with `EnergyChart(useSeries("region","24h"))` (12).
- `BuildingsPage`: `PageHeader "Buildings"`; `FilterBar`; desktop `lg:grid-cols-[minmax(0,65fr)_minmax(0,35fr)]` with `BuildingsMapLazy` (`fitTo="selection"`, `selectedPlz = filters.plz`, `onSelectPlz` → `togglePlz`, `onSelectBuilding` → `selectBuilding`, `onOpenBuilding` → push) and `BuildingList` (`useFilteredBuildings`, `onSelect` → `selectBuilding`, `onOpen` → push); below `lg` a shadcn `Tabs` Map / List.
- `EnergyPage`: `EnergyKpiRow` for the region (sum of building summaries via a memo in the page), `EnergyFlowDiagram`, `TimeRangeSelector` + `EnergyChart`, `DistributionDonut` (`consumptionBySystemType` over all systems from `useBuildings` detail is too heavy → add `fetchSystemsSummary()` in `api.ts` returning `{ type, kwh }[]` computed from the world and a `useSystemsSummary()` hook; both owned by this task), `GridChart`.
- `SettingsPage`: About card (hackathon copy from the old about dialog) and a "Planned" list: device detail, alert acknowledgement, custom date range, roles, audit log, export.
- Sidebar/Header integration: `NotificationsButton` count from `useActiveAlerts`; `GlobalSearch` on non-Buildings pages navigates to `/buildings` on Enter.
Verification: `npm run check`, `npm run build` (routes list), browser walk of PRD §49 items 1–14 on port 3000 at 1440 px, 1024 px, 375 px. Commit per step; push.

### Task 14: Responsive and accessibility pass, acceptance e2e, docs (model sonnet)

**Files:** `e2e/acceptance.spec.ts`, `e2e/responsive.spec.ts`; targeted fixes only in files the browser walk shows broken (list them in the report); `README.md`; `docs/energy-dashboard-prd.md` unchanged.

E2E (Playwright, port 3000): (1) `/` shows KPI values, system status pill text, map container, attention list; (2) map has PLZ polygons — assert the `plz-fill` layer via `page.evaluate` on `window.__map` **is not allowed**; instead assert the legend and that a PLZ click through the Buildings page filter chip appears after `togglePlz` via the PLZ filter UI; (3) no address text: `page.getByText(/strasse|street|address/i)` count 0 on `/`, `/buildings`, `/buildings/BLD-0001`; (4) filter by PLZ 5000 → count chip and rows only PLZ 5000; (5) search "BLD-0001" → one row; (6) status filter Critical → every row shows "Critical"; (7) critical buildings visible at the top of the attention list; (8) open from list → `/buildings/BLD-…`; (9) marker open is unit-tested (canvas) — instead assert the map tooltip/legend present; (10) detail KPIs six metrics; (11) systems grid and devices table rows; (12) charts present with `aria-label` and time range buttons; (13) `/alerts` shows severity tabs with counts and rows; (14) system status pill in the header; (15) error state: intercept `**/nothing` not possible for mock — instead unit-covered; assert empty state via a search that matches nothing; (16) 375 px: no horizontal scroll (`document.documentElement.scrollWidth <= innerWidth`), hamburger opens nav, Buildings page shows Map/List tabs. Docs: README structure, scripts, data model, routes, how to swap the API, PLZ data provenance.

### Task 15: Final review, cleanup, PR (controller)

Whole-branch review (opus) over `merge-base main..HEAD` with the review package excluding lockfile/GeoJSON/generated UI; one fix wave; scoped re-review; cleanup checklist (dev pages gone, no `console.log`/`TODO`/`any`, unused exports sweep, `npm run check` + `build` + `test:e2e` green, branches/worktrees deleted local + remote, SDD workspace deleted); PR `feat/energy-dashboard → main` with summary, decisions, rulings, test plan.

---

## Self-review

**Spec coverage.** §2 D1–D18 → runbook + Tasks 1, 2, 4, 6, 7, 9, 13; §5 → Task 2; §6 → Task 2; §7 → Task 3 (+ chart options Task 9, fingerprint Task 5); §8/§9 → Task 3; §10 rows → Tasks 4, 6–12; §11 pages → Tasks 10, 11, 12, 13; §12 → Task 1; §13 → each task's tests + Task 14; §14/§15 documented; §16 → runbook + Task 15. PRD §49 items 1–20 → Task 14 e2e (1–16), Task 1 (17), Task 2 tests (18), Tasks 6/7/12 (19), architecture (20).

**Type consistency.** `BuildingsMapProps` (Task 6) consumed in Task 13; `BuildingList` props (Task 7) consumed in Task 13; `EnergyKpiRow` (Task 8) consumed in Tasks 10/13 with the fallback rule stated; chart stub prop types (Task 4) = real components (Task 9) consumed in Tasks 10/13; hooks (Task 3) consumed everywhere by the names in spec §9; `STATUS_META` etc. (Task 1) consumed by `StatusBadge` (Task 4) and map expressions (Task 6).

**Known judgment calls for the executing controller:** cluster-count glyph font name (Task 6 verifies in browser); `EnergyKpiRow` cross-branch dependency (Task 10 fallback → Task 13 dedupe); `fetchSystemsSummary` added in Task 13 (extends the API surface; record a ruling).
