# Frontend Technical Task — Energy Fingerprints Demo

> Hackathon demo spec for the AEW **Energy Fingerprints** challenge frontend.
> Adapted to this repo's stack — see [`frontend/README.md`](../README.md).

## 1. Goal

Build a single-page web application for the AEW Energy Fingerprints hackathon.

The app visualizes buildings in a geographic area and, for each building, shows
AI/ML predictions about which energy assets are likely present, based on
electricity consumption data.

This is a **demo/prototype**, not a production system. Keep the UI simple,
clean, and easy to understand — the whole concept should be understandable in
under 30 seconds.

**Core story the UX must tell:**

```
MAP → BUILDING → ELECTRICITY DATA → FINGERPRINT → PREDICTION → EXPLANATION
```

Not: *Dashboard → 50 charts → complicated analytics.*

## 2. Tech stack (already decided in this repo)

| Concern | Choice |
| --- | --- |
| Framework | Next.js 16 (App Router, Turbopack), React 19, TypeScript |
| Styling / components | Tailwind CSS v4 + shadcn/ui |
| Map | **MapLibre GL** via `react-map-gl` |
| Charts (24h electricity graph) | **ECharts** via `echarts-for-react` |
| Server state / mock-to-API data | TanStack Query |
| Client UI state (selection, view mode, filters) | Zustand (`src/stores/ui-store.ts`) |
| Icons | `lucide-react` |

Follow existing conventions in [`frontend/README.md`](../README.md): Server
Components by default, `"use client"` only where interactivity/browser APIs
are needed (map, charts, stores). Server data → TanStack Query. Ephemeral UI
state → Zustand. Add shadcn components with `npx shadcn@latest add <name>`.

## 3. Main UX concept

One main page/screen:

```
┌──────────────────────────────────────────────────────────────┐
│ AEW logo     Aargau ▼    Search...             Map | List    │
├───────────────────────────────────┬──────────────────────────┤
│                                    │                          │
│                                    │   BUILDINGS IN AREA      │
│           3D MAP                  │                          │
│      🏠   🏠   🏠                  │   Building 1             │
│    🏠    🏠    🏠                  │   Building 2             │
│       🏠    🏠                     │   Building 3             │
│                                    │   Building 4             │
│                                    │   Building 5             │
└───────────────────────────────────┴──────────────────────────┘
```

The user can:

- See buildings on the map.
- Search/filter buildings.
- Switch between Map View and List View.
- Click a building on the map or in the list.
- Open a building detail view (modal / large side panel).
- See predictions for PV, battery, heat pump, and EV.
- See the building's electricity consumption for the last 24 hours.
- See highlighted regions on the graph representing detected energy patterns.
- See a simple explanation of how the prediction was generated.
- Optionally expand technical details (SHAP).

## 4. Header

Minimal header, single row:

- **Left:** AEW logo / branding.
- **Center-left:** Area selector, e.g. `Aargau (AG) ▾`. Default area for the
  prototype is Aargau; the selector can be a static dropdown (single option
  is fine for MVP).
- **Center:** Search input, placeholder `Search address, city or building...`.
  Can be mocked (client-side filter over the mock dataset) if there's no
  backend search.
- **Right:** View toggle `[ Map ] [ List ]`, plus an `About this project` link
  (opens a simple modal/panel with a short description of the challenge —
  reuse the copy from the repo root [`README.md`](../../README.md)).

## 5. Map view

Main view is a map of Aargau, rendered with **MapLibre GL** (`react-map-gl`,
already installed).

**Buildings do not need real 3D building models.** Use generic/stylized
3D-looking building markers (e.g. small extruded shapes, or 2D pin/icon
markers styled to look like little building blocks). The priority is
identifying/selecting buildings, not photorealism.

### Visual states based on predictions

Buildings can carry a small visual indicator based on their strongest/most
notable predicted asset(s):

- **PV detected** → small solar-panel highlight/tint on the marker.
- **EV detected** → EV icon near the building.
- **Heat pump detected** → heat-pump icon.
- **Battery detected** → battery icon.

**Do not overload the map with icons.** Show at most one or two indicator
icons per marker (e.g. the top prediction, or only predictions above the
"Likely" threshold — see §9). The map's main job is building
identification/selection, not displaying all four probabilities at once
(that's what the list card and detail panel are for).

### Map interaction

- Clicking a building marker highlights the same building in the list panel
  (scroll into view + visual highlight state).
- Clicking a building in the list highlights the marker on the map and pans
  the map toward it.
- Either interaction opens the building detail panel.

```
Click building
      ↓
Map zooms toward building
      ↓
Building becomes highlighted (map + list)
      ↓
Detail panel opens
```

## 6. Building list (List panel)

On desktop, shown as a right-side panel next to the map (roughly `MAP 65% /
LIST 35%` width split — see §11).

Header: `Buildings in this area` + a count, e.g. `124 buildings`.

Each building card shows:

- Building/street address (bold).
- City / postcode.
- Four probability chips with icon + percentage: ☀ PV, 🔋 Battery,
  🔥 Heat pump, 🚗 EV.

```
┌───────────────────────────────┐
│ 🏠  Bahnhofstrasse 12         │
│     5000 Aarau                │
│                               │
│ ☀ 92%   🔋 48%   🔥 31%  🚗 76%│
└───────────────────────────────┘
```

Selecting a card highlights it (border/background) and syncs the map
selection.

## 7. Building detail panel

Opens as a **modal or large side panel** (prefer this over a separate route/
page — keeps the app to a single screen for the demo). Triggered by selecting
a building from the map or the list.

```
┌──────────────────────────────────────────────┐
│ ✕                                              │
│ Bahnhofstrasse 12                              │
│ 5000 Aarau, AG                                 │
│                                                 │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐            │
│ │ ☀ PV │ │🔋 Bat.│ │🔥 HP  │ │🚗 EV │            │
│ │ 92%  │ │ 48%  │ │ 31%  │ │ 76%  │            │
│ │Likely│ │Maybe  │ │Unlikely│Likely│            │
│ └──────┘ └──────┘ └──────┘ └──────┘            │
│                                                 │
│ Electricity profile — Last 24 hours            │
│              GRAPH                             │
│ ─── Consumption   ███ EV charging               │
│ ███ PV generation                              │
│                                                 │
│ About this prediction                          │
│ ...                                             │
│                                                 │
│ Show technical details ▾                       │
└──────────────────────────────────────────────┘
```

Contains, top to bottom:

1. Close control (`✕`).
2. Address + city/canton.
3. Four asset prediction cards (§8).
4. 24h electricity graph with highlighted event zones (§10–§11).
5. "About this prediction" explanation (§12).
6. Expandable "Show technical details" section with SHAP-style explanation
   (§13).
7. Optional per-asset "Why?" interaction (§14).

## 8. Asset prediction cards

Exactly **four** primary predictions, always shown in this order: **PV,
Battery, Heat Pump, EV**.

Each card shows: icon, percentage, and a human-readable label (see §9).

```
☀️ PV / Solar        92%   Likely
🔋 Battery           48%   Uncertain / Possible
🔥 Heat Pump         31%   Unlikely
🚗 Electric Vehicle  76%   Likely
```

Backend will eventually supply these probabilities (0–1 or 0–100). For now,
use mock data per building (§15).

## 9. Probability → label mapping

Use simple, human-readable labels, **configurable via constants** (not
hardcoded per component):

| Range | Label |
| --- | --- |
| 80–100% | Likely |
| 50–79% | Possible |
| 0–49% | Unlikely |

Implement as a small pure function/config (e.g.
`src/lib/predictions.ts::getPredictionLabel(probability: number)`), not
inline conditionals scattered across components — the thresholds must be easy
to tune during the hackathon.

**Copy rule:** never state predictions as fact. Always phrase as a
probability, e.g. `EV — 76% likely`, never `This house has an EV`.

## 10. Electricity graph (24h)

The most important visualization in the detail panel. Render with **ECharts**
(`echarts-for-react`, already installed).

- X-axis: time of day, `00:00 → 24:00` (tick marks roughly every 4h:
  `00 04 08 12 16 20 24`).
- Y-axis: power in kW.
- Line series: electricity consumption curve, built from the building's
  `electricity` time series (15-minute or hourly points — see §15 data
  contract).
- Keep the chart visually simple: one primary line, muted grid, minimal
  chrome. This chart and the map are the visual focus of the app — don't
  compete with them via other charts elsewhere.

## 11. Energy fingerprint highlighting

Key feature: the graph must render **highlighted background zones**
corresponding to detected events, drawn as ECharts `markArea` bands under the
consumption line, each with a small label.

Examples:

- **EV charging:** band from `22:15 → 01:30`, label `EV charging`.
- **PV generation:** band from `10:00 → 16:30`, label `Possible PV
  generation`.
- **Other high consumption** (optional): band from `18:00 → 20:00`.

```
        EV
         ↓
       ┌─────────┐
       │         │
───────╲_________╱──────────
       │         │
       └─────────┘
       22:00    02:00
```

Bands must stay **subtle** (low-opacity fill, e.g. 10–15% alpha, distinct
color per event `type`) so the consumption curve stays the primary, readable
element. Zones are driven entirely by the building's `events` array (§15) —
the frontend only renders what it's given, it does not compute events.

## 12. "About this prediction" (plain-language explanation)

Below the graph, a short, non-technical paragraph explaining how predictions
work in general terms. Example copy:

> **How is this calculated?**
> The prediction is based on electricity meter measurements recorded every 15
> minutes. The model looks for recurring patterns in the building's
> electricity consumption and compares them with patterns associated with
> known energy assets such as PV systems, EVs, heat pumps and batteries.

This copy can be static for the MVP (not per-building), followed by a `Show
technical details ▾` toggle.

## 13. Technical details / SHAP (expandable)

Clicking `Show technical details` expands a section with:

- **Model:** short description (e.g. "Machine Learning classification
  model").
- **Input:** "15-minute electricity measurements".
- **Additional data:** e.g. "Weather / temperature (if available)".
- **Explainability:** "SHAP" + one-line description: *"SHAP shows which
  features contributed most to the prediction."*
- A small per-asset SHAP-style feature list with signed contributions, e.g.:

```
EV prediction: 76%

+ High nighttime power peak       +0.31
+ Repeated 7 kW events            +0.24
+ Event duration                  +0.15
- Daytime consumption pattern     -0.04
```

**Do not invent real model internals.** All of this content — model name,
inputs, SHAP values — comes from mock data structured to match what the
backend/ML team will eventually provide. The UI's job is to *support*
displaying this content, not to fabricate specific model claims.

## 14. "Why this prediction?" (optional, recommended)

Per asset card, an optional `Why?` link/button that opens a small
popover/panel:

```
Why EV is likely

✓ Repeated high-power events
✓ Mostly during nighttime
✓ Similar duration across multiple days

SHAP contribution
████████████  High
████████      Medium
██            Low
```

Optional for MVP, but strongly recommended for the demo — explainability is
one of the strongest parts of the concept.

## 15. Mock data contract

Structure mock data to match the shape the backend will eventually send, so
swapping mock data for a real API later is a data-layer change only (behind
TanStack Query), not a component rewrite.

```ts
// src/lib/types.ts
export type AssetPrediction = {
  pv: number;        // 0–100
  battery: number;   // 0–100
  heatPump: number;  // 0–100
  ev: number;        // 0–100
};

export type ElectricityPoint = {
  timestamp: string; // ISO 8601
  powerKw: number;
};

export type BuildingEvent = {
  type: "ev_charging" | "pv_generation" | "high_consumption";
  start: string;  // ISO 8601
  end: string;    // ISO 8601
  confidence?: number; // 0–1
};

export type Building = {
  id: string;
  address: string;
  city: string;
  postcode: string;
  canton: string;
  location: {
    lat: number;
    lng: number;
  };
  predictions: AssetPrediction;
  electricity: ElectricityPoint[];
  events: BuildingEvent[];
};
```

This is an example contract — adapt field names if the actual backend
contract differs, but keep the same shape (flat prediction object, time
series array, typed event list) so the graph/prediction components don't need
to change when real data arrives.

Mock dataset: generate ~100–150 `Building` records around Aarau/Aargau
coordinates, with randomized but plausible predictions, a synthetic 24h
`electricity` curve per building, and 1–3 `events` per building. Put this in
e.g. `src/lib/mock-data.ts`, served through a TanStack Query hook (e.g.
`useBuildings()`) so it's a one-line swap to a real fetch later.

## 16. MVP scope

### Required

- [ ] Single web page/app shell (header, map, list).
- [ ] Aargau map (MapLibre GL) with generic building markers.
- [ ] Building list panel, synced with the map.
- [ ] Map ↔ list selection sync (click either → highlight both).
- [ ] Building detail modal/panel.
- [ ] Four predictions (PV, Battery, Heat Pump, EV) with percentages and
      Likely/Possible/Unlikely labels.
- [ ] Last-24h electricity graph (ECharts).
- [ ] Highlighted event zones on the graph.
- [ ] "About this prediction" static explanation.
- [ ] Expandable technical details / SHAP section.
- [ ] Mock data matching the contract in §15.

### Explicitly out of scope

Do not build: authentication, user profiles, complex settings, device
control, real-time device control, multiple dashboards, complex analytics,
billing, notifications, a mobile app, an admin panel, or complex/realistic 3D
building models.

## 17. Visual style

Aim for **Swiss energy-tech / modern utility SaaS**:

- Clean white/light background.
- Dark navy typography.
- AEW-inspired blue/green accents.
- Subtle shadows, rounded cards, simple line icons (`lucide-react`).
- Generous whitespace, clear typography.

Avoid: neon/cyberpunk styling, excessive gradients, too many colors, oversized
cards, too many charts, complex animations. The map and the electricity
fingerprint graph are the visual focus — everything else should stay quiet.

## 18. Responsive behavior

Desktop is the primary target for the hackathon demo.

- Desktop layout: map ~65% width / list ~35% width, side by side.
- Selecting a building opens the detail panel as an overlay on top of the
  map+list (or replacing the list panel) — don't navigate to a new route.
- Mobile: basic responsiveness only (no horizontal scroll, panels stack), not
  a priority for MVP.

## 19. Demo flow (for reference / manual QA)

1. Open the app — see the Aargau map with buildings.
2. Show the building list.
3. Click **Bahnhofstrasse 12**.
4. Map pans/zooms toward the building; it highlights on map + list.
5. Detail panel opens showing PV 92% Likely, Battery 48% Possible, Heat pump
   31% Unlikely, EV 76% Likely.
6. Show the 24h electricity fingerprint, pointing at the highlighted zones
   ("here the model detects a probable EV charging event", "here's the
   daytime pattern associated with PV generation").
7. Open **Why this prediction?** and show the evidence/SHAP explanation.
8. Close the panel, return to the map.

Use this flow as the basis for a manual smoke test once each MVP box in §16
is implemented.
