# UI Refinement — AEW Visual Polish of the Energy Fingerprints Demo

**Date:** 2026-09-10 · **Status:** Draft for review
**Brief:** `frontend/docs/ui-refinement-brief.md` (verbatim). **Base:** tag `demo-v1-fingerprints` (PR #1). **Branch:** `feat/ui-refinement`, merged into `feat/frontend-energy-map` when done.

## 1. Scope

Visual refinement only. Structure, components, data model, copy and user flow stay as in the demo: full-screen PLZ map + right building list; selecting a building opens the right-side sheet over a dimmed, blurred map; four prediction cards, 24 h chart with bands, explanation, technical details. No markers (user decision: buildings have no coordinates). No new sections, routes, KPIs or navigation.

Out of scope: anything in the brief's §43 list; the parked dashboard plan.

## 2. Decisions

| # | Decision | Why |
| --- | --- | --- |
| R1 | Fonts: **Source Serif 4** (headings, building titles, large percentages, section titles) and **Inter** (everything else) via `next/font/google`, with Georgia / Arial fallbacks. `--font-serif` and `--font-sans` CSS variables; `--font-heading: var(--font-serif)`. | Brief §10–§11. |
| R2 | Palette per brief §7–§9 mapped onto the shadcn tokens: `--primary #0065A8`, `--primary-foreground #fff`, `--foreground #182638`, `--muted-foreground #65727D`, `--border #D9E0E6`, `--background #F5F6F4`, `--card #fff`, `--accent #EAF4FA`, `--accent-foreground #003B5C`, `--ring #0065A8`, `--radius 1rem` (cards 16 px; inputs/controls use explicit `rounded-lg` = 8 px, pills `rounded-full`). Extra tokens: `--surface-soft #F7F9FB`, `--border-medium #C7D0D8`, `--text-dark #102033`, `--navy #003B5C`, `--blue-hover #00558C`. | Brief §7–§8, §36. |
| R3 | Asset colours in TypeScript (`ASSETS[].color`) change to PV `#EFA33A`, Battery `#39A85A`, Heat pump `#E85B2A`, EV `#2563EB`, each with a `pillBackground`: `#FFF7E8`, `#EFF8F1`, `#FFF2ED`, `#EFF4FF`. `EVENT_META` follows: EV band uses AEW blue `#0065A8`, PV band `#EFA33A`, high consumption `#65727D`. | Brief §9, §16, §27. |
| R4 | Basemap: keep OpenFreeMap positron but **recolour it client-side**: fetch the style JSON once, patch paint colours by layer id/type (background `#F5F6F4`; land/landcover/landuse/park `#F7F8F6`; water `#DDE9ED`; major roads `#FFFFFF`; minor roads `#E3E5E4`; text `#1F2933` with halo white), memoise, pass the object as `mapStyle`. `NEXT_PUBLIC_MAP_STYLE_URL` still respected (patched the same way). | Brief §5 without hosting a custom style. |
| R5 | PLZ layers: fill `#EAF2FA` at 0.5, border `#AFC2D8` at 0.8 / 0.8 px; hover fill `#D9E8F6` at 0.6; highlighted: outline `#0065A8` 2 px + fill `#0065A8` at 0.10. Opacity transitions 200 ms via `*-opacity-transition`. Tooltip: white, 1 px `#D9E0E6`, radius 8 px, shadow `0 1px 3px rgba(20,40,60,.06)`, Inter 13 px. | Brief §6, §32. |
| R6 | Map controls (`NavigationControl`) restyled by CSS overrides on `.maplibregl-ctrl-group`: white, 1 px `#D9E0E6`, radius 8 px, shadow `0 1px 3px rgba(20,40,60,.08)`, 32 px buttons, AEW blue on hover. | Brief §32. |
| R7 | Header: white, 1 px bottom border, AEW blue logo tile with white "AEW", navy title, compact controls (height 56 px unchanged); search input radius 8 px; toggle buttons 8 px with active = light blue bg + navy text. | Brief §33. |
| R8 | Building cards: white, 1 px `#D9E0E6`, radius 16 px, shadow `0 1px 3px rgba(20,40,60,.06)`, padding 16 px; hover border `#AFC2D8`, bg `#FBFDFF`; selected border `#0065A8`, bg `#F7FBFE`, `shadow-[0_0_0_1px_#0065A8]`; title "Building AG-021249" in serif 17 px/600 navy; PLZ line 13 px secondary; building icon tile light blue. 200 ms ease-out transitions. List panel width 32 % (min 340 px, max 480 px); area header title serif 18 px. | Brief §12–§15, §34. |
| R9 | Pills: `rounded-full`, 12.5 px Inter medium, dark neutral text, per-asset light background and icon colour (R3), height 24 px, gap 6 px. | Brief §16. |
| R10 | Drawer: width `min(52vw, 900px)` on desktop (full width < 1024 px), radius 0, white; overlay `rgba(20,35,50,0.16)` + `backdrop-filter: blur(6px)` (edit `src/components/ui/sheet.tsx` overlay classes — this file is ours to keep); open/close 200 ms ease-out; header: serif title 24 px/600 navy, subtitle 14 px secondary; close = ghost icon button 32 px, hover light blue bg, navy icon, `aria-label="Close"` unchanged. | Brief §17–§21, §36–§37. |
| R11 | Prediction cards: white, 1 px `#D9E0E6`, radius 16 px, no shadow; icon 20 px in asset colour; name 13 px secondary; percentage serif 34 px/600 navy tabular; status pill: Likely = filled `#0065A8` white text; Possible = `#EAF4FA` bg, `#003B5C` text; Unlikely = white, 1 px `#C7D0D8`, `#344454` text — all carry the word. "Why?" = text link `#0065A8`, hover `#003B5C` underline, 13 px. | Brief §22–§25. |
| R12 | Chart: line `#18385A` 2.5 px; grid `#E1E6EA`; axis labels `#65727D` 12 px Inter; PV band `#EFA33A` at 0.14 with label in `#B8791A`; EV band `#0065A8` at 0.12 with label `#0065A8`; high-consumption band `#65727D` at 0.10; tooltip white with 1 px border; legend markers 10 px squares/line, 13 px neutral text. Section title "Electricity profile — Last 24 hours" serif 18 px. | Brief §26–§28. |
| R13 | Explanation card: `#F6F9FB` bg, radius 16 px, no border, serif heading 18 px, body 14.5 px/1.55. Technical details: same surface family, trigger as text link. | Brief §29. |
| R14 | Motion: 150–250 ms ease-out on card hover, drawer, PLZ hover, tooltip; nothing else. Focus: `focus-visible:ring-2 ring-[#0065A8] ring-offset-2`. | Brief §37, §42. |
| R15 | Preserve every test id, accessible name and copy string the tests and e2e rely on (`Building AG-…`, `Why EV?`, `Close`, `Show technical details`, chip titles, legend labels). | Refinement must not change behaviour. |

## 3. Ownership (parallel wave)

| Area | Files | Owner |
| --- | --- | --- |
| Tokens, fonts, asset colours, global CSS (incl. map control overrides) | `src/app/globals.css`, `src/app/layout.tsx`, `src/lib/predictions.ts`, `src/lib/events.ts`, `src/lib/theme.ts` (new: hex constants used by map/chart), tests | T1 (first) |
| Map | `src/components/map/*`, `src/lib/map-style.ts` (new, style patcher + test) | T2 |
| Header, list, cards, pills, shell proportions | `src/components/header/*`, `src/components/buildings/*`, `src/components/app-shell.tsx` | T3 |
| Drawer, prediction cards, why link, explanation, technical details, sheet overlay | `src/components/detail/*`, `src/components/ui/sheet.tsx`, `src/components/ui/badge.tsx` (only if a variant is needed) | T4 |
| Chart option and legend | `src/lib/chart-option.ts`, `src/components/chart/*` | T5 |
| Integration, visual QA, e2e, merge | everything | T6 |

## 4. Acceptance

Side by side with the demo at 1440 px: identical structure and behaviour; `npm run check`, `npm run build`, `npm run test:e2e` green; screenshots of map, list, drawer and chart reviewed against the brief's palette and typography; no emoji, one icon family, no colour-only status.
