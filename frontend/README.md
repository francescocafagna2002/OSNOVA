# OSNOVA Frontend

Web app for the **Energy Fingerprints** challenge — visualizing per-customer
asset probabilities, activity windows, and the evidence behind them.

## Stack

- **Next.js 16** (App Router, Turbopack) + **React 19** + **TypeScript**
- **Tailwind CSS v4** + **shadcn/ui**
- **ECharts** — time-series / fingerprint charts (`echarts`, `echarts-for-react`)
- **MapLibre GL** — postal-code maps (`maplibre-gl`, `react-map-gl`)
- **TanStack Query** — server state & data fetching
- **Zustand** — client UI state
- **TanStack Table** & **Motion** — installed, ready when needed

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
    map/                # MapLibre PLZ areas, tooltip
    buildings/          # list panel, area header, building cards, chips
    detail/              # detail sheet, prediction cards, why popover, SHAP details
    chart/               # ECharts 24h fingerprint + legend
    ui/                  # shadcn/ui (generated)
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

## Conventions

- Server Components by default; add `"use client"` only where interactivity or
  browser APIs are needed (charts, maps, stores).
- **Server data → TanStack Query.** **Ephemeral UI state → Zustand.** Don't mix.
- Add shadcn components with `npx shadcn@latest add <name>`.
