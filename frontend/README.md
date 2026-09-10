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
npm install      # first time only
npm run dev      # http://localhost:3000
```

Other scripts: `npm run build`, `npm run start`, `npm run lint`.

## Project structure

```
src/
  app/                 # App Router (layout, pages)
  components/
    providers.tsx      # client providers (TanStack Query + devtools)
    ui/                # shadcn/ui components
  lib/
    query-client.ts    # server/browser-safe QueryClient factory
    utils.ts           # cn() helper
  stores/
    ui-store.ts        # Zustand global UI state
```

## Conventions

- Server Components by default; add `"use client"` only where interactivity or
  browser APIs are needed (charts, maps, stores).
- **Server data → TanStack Query.** **Ephemeral UI state → Zustand.** Don't mix.
- Add shadcn components with `npx shadcn@latest add <name>`.
