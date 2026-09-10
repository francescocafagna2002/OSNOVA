# UI Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Energy Fingerprints demo look like an AEW-built Swiss energy control centre — same structure, components, flow and data; refined typography (serif headings + Inter), AEW palette, subtle PLZ zones on a quiet recoloured basemap, premium flat cards and pills, a wider white drawer over a dimmed blurred map, a restrained navy chart.

**Architecture:** Token-first. Task 1 changes CSS variables, fonts and the TypeScript colour constants everyone reads; Tasks 2–5 restyle disjoint component areas in parallel worktrees; Task 6 merges, does visual QA in a browser, keeps tests and e2e green, and merges into `feat/frontend-energy-map`.

**Tech Stack:** unchanged (Next 16, Tailwind v4, shadcn base-nova, react-map-gl/maplibre, echarts). New: two Google fonts via `next/font/google` (no npm dependency).

**Spec:** [`docs/superpowers/specs/2026-09-10-ui-refinement-design.md`](../specs/2026-09-10-ui-refinement-design.md) — binding. Brief: `frontend/docs/ui-refinement-brief.md`.

## Global Constraints

- Paths relative to `frontend/`; run npm commands there. Base commit: tag `demo-v1-fingerprints` (39b4014) on branch `feat/ui-refinement`.
- **Do not change structure, behaviour, copy, test ids or accessible names.** All existing unit tests and the Playwright demo flow must pass without assertion changes (class-name assertions may be updated if a test asserted a colour class).
- No new npm dependencies. No emoji anywhere. One icon family (lucide). No dark mode, gradients, glassmorphism.
- Exact colours per spec §2 (R2–R13); 8 px spacing grid; radius cards 16 px / pills full / inputs+controls 8 px / drawer 0.
- Transitions 150–250 ms ease-out only where the spec lists them.
- Ownership per spec §3 is binding in the parallel wave; anything else is a "Request for Task 6".
- Definition of done per task: `npm run check` green, pristine output; no `console.log`, `any`, `// TODO`; commits `type: summary` with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; push after the final commit.
- Dev ports: T2 3001, T3 3002, T4 3003, T5 3004; T1 and T6 use 3000.

---

## Runbook

| Wave | Tasks | Mode | Model |
| --- | --- | --- | --- |
| 0 | 1 | on `feat/ui-refinement` | sonnet |
| 1 | 2, 3, 4, 5 | parallel worktrees `../OSNOVA-ur-<area>` on `feat/ur-<area>` from the Task 1 commit | T2 opus (basemap patching), T3–T5 sonnet |
| 2 | 6 | on `feat/ui-refinement`, then merge into `feat/frontend-energy-map` and push | opus; final review opus |

Each Wave 1 task verifies visually in a browser (screenshots at 1440 px; the app at `/` is live, no preview pages needed) and includes screenshot descriptions in its report.

---

## Task 1: Tokens, fonts, asset colours, global CSS

**Files:** `src/app/globals.css`, `src/app/layout.tsx`, `src/lib/theme.ts` (new), `src/lib/theme.test.ts` (new), `src/lib/predictions.ts`, `src/lib/events.ts`, `src/lib/predictions.test.ts` (only if a colour assertion exists).

- [ ] **Fonts.** In `layout.tsx` load `Source_Serif_4` (`variable: "--font-serif"`, `subsets: ["latin"]`, weights 500/600) and `Inter` (`variable: "--font-sans"`); keep `Geist_Mono` as `--font-geist-mono`; put all three variables on `<html>`. In `globals.css` `@theme inline`: `--font-sans: var(--font-sans), Inter, Arial, "Helvetica Neue", sans-serif; --font-serif: var(--font-serif), "Source Serif 4", Georgia, serif; --font-heading: var(--font-serif);`. Add base rule `h1,h2,h3,.font-heading { font-family: var(--font-serif); }` only via utilities (`font-serif`) — do not globally restyle `h*`; components opt in with `font-serif`.
- [ ] **Palette.** Replace `:root` with the mapping in spec R2 (hex values). Add `--surface-soft`, `--border-medium`, `--text-dark`, `--navy`, `--blue-hover`, and expose them in `@theme inline` as `--color-surface-soft`, `--color-border-medium`, `--color-text-dark`, `--color-navy`, `--color-blue-hover`. Set `--radius: 1rem`.
- [ ] **Map control overrides** in `globals.css` (`@layer components`): `.maplibregl-ctrl-group { background:#fff; border:1px solid #D9E0E6; border-radius:8px; box-shadow:0 1px 3px rgba(20,40,60,.08); overflow:hidden } .maplibregl-ctrl-group button { width:32px; height:32px } .maplibregl-ctrl-group button:hover { background:#EAF4FA } .maplibregl-ctrl-group button + button { border-top:1px solid #D9E0E6 }`.
- [ ] **`src/lib/theme.ts`** exports `BRAND = { blue:"#0065A8", navy:"#003B5C", blueHover:"#00558C", blueLight:"#EAF4FA" }`, `NEUTRAL = { pageBg:"#F5F6F4", surfaceSoft:"#F7F9FB", borderLight:"#D9E0E6", borderMedium:"#C7D0D8", textSecondary:"#65727D", textPrimary:"#182638", textDark:"#102033" }`, `MAP = { background:"#F5F6F4", land:"#F7F8F6", roadMajor:"#FFFFFF", roadMinor:"#E3E5E4", water:"#DDE9ED", label:"#1F2933", plzFill:"#EAF2FA", plzBorder:"#AFC2D8", plzHover:"#D9E8F6" }`, `CHART = { line:"#18385A", grid:"#E1E6EA", axis:"#65727D" }`. Test asserts a handful of values.
- [ ] **Asset colours.** `ASSETS` colours → PV `#EFA33A`, Battery `#39A85A`, Heat pump `#E85B2A`, EV `#2563EB`; add `pillBackground` per asset (`#FFF7E8`, `#EFF8F1`, `#FFF2ED`, `#EFF4FF`) to `AssetMeta`. `EVENT_META`: `ev_charging` colour `BRAND.blue`, `pv_generation` `#EFA33A`, `high_consumption` `#65727D`. Update any test that asserted the old hex values.
- [ ] `npm run check` green; commit `style(frontend): AEW palette, serif+Inter fonts, asset colours and map control styles`; push.

## Task 2: Map — quiet basemap, subtle PLZ zones, tooltip

**Files:** `src/lib/map-style.ts` (+test), `src/components/map/plz-layers.tsx` (+test), `src/components/map/map-tooltip.tsx`, `src/components/map/map-view.tsx` (+test).

- [ ] **Style patcher** `src/lib/map-style.ts`: `export function patchMapStyle(style: StyleSpecification): StyleSpecification` — deep-copies and recolours by rules on `layer.type` and `layer.id` (lower-cased): `background` → `background-color` MAP.background; `fill` layers whose id includes `land`, `park`, `wood`, `grass`, `residential`, `farmland`, `building` → `fill-color` MAP.land (buildings at 0.6 opacity, keep or lower); id includes `water` → MAP.water (fill or line); `line` layers with id including `motorway|trunk|primary|secondary` → `line-color` MAP.roadMajor; other road/street/path/rail lines → MAP.roadMinor; `symbol` layers → `text-color` MAP.label, `text-halo-color` `#FFFFFF`, and set `text-opacity` 0.9; boundary lines → `#C7D0D8`. Anything unmatched untouched. Pure and unit-tested with a small synthetic style. `export async function loadPatchedStyle(url: string): Promise<StyleSpecification>` fetches JSON and patches; memoise per URL.
- [ ] **`map-view.tsx`**: load the patched style in an effect (`useState<StyleSpecification | undefined>`), pass `mapStyle={style}`; while undefined render the map with `mapStyle={MAP_STYLE_URL}` fallback so nothing breaks offline of the patch (if fetch fails, log nothing; fall back to the URL). Keep `setWorkerUrl`, the resize latch, selection logic and the tests' mocked surface intact; in tests the fetch is mocked to reject (fallback path) plus one test where it resolves with a stub style and `mapStyle` becomes the patched object.
- [ ] **PLZ layers** per spec R5, using `MAP`/`BRAND` from `@/lib/theme`; add `"fill-opacity-transition": { duration: 200 }` on hover/highlight layers.
- [ ] **Tooltip** per R5 styling (white, border, radius 8, shadow, 13 px Inter, navy for the PLZ, secondary for the count).
- [ ] Verify at 1440 px: map reads light-neutral and low contrast; zones subtle; hover tint; selected outline AEW blue; controls white/8 px. `npm run check`; commit `style(frontend): quiet recoloured basemap and subtle PLZ zones`; push.

## Task 3: Header, building list, cards, pills, panel proportions

**Files:** `src/components/header/*`, `src/components/buildings/*`, `src/components/app-shell.tsx` (+ their tests where class assertions exist).

- [ ] **Header** (R7): `bg-white border-b border-border`; wordmark tile `bg-primary text-white rounded-lg` 32 px, title `font-serif text-[15px] text-navy`, subtitle 11 px secondary; search `rounded-lg border-border focus-visible:ring-2 focus-visible:ring-primary`; view toggle: container `rounded-lg border bg-white p-0.5`, active `bg-accent text-navy`; About button ghost, navy text on hover.
- [ ] **Panel** (R8): list aside `lg:w-[32%] lg:min-w-[340px] lg:max-w-[480px]`, `bg-[#F7F9FB]` panel background so white cards stand out; area header title `font-serif text-lg text-navy`, count 13 px secondary, "Show all areas" as outline 8 px control.
- [ ] **Cards** (R8): `rounded-2xl border border-border bg-white p-4 shadow-[0_1px_3px_rgba(20,40,60,0.06)] transition-[border-color,background-color,box-shadow] duration-200 ease-out hover:border-[#AFC2D8] hover:bg-[#FBFDFF]`; selected `border-primary bg-[#F7FBFE] shadow-[0_0_0_1px_#0065A8]`; icon tile `bg-accent text-navy rounded-lg size-9` with `Building2` 18 px; title `font-serif text-[17px] font-semibold text-navy`; PLZ line `text-[13px] text-muted-foreground`.
- [ ] **Pills** (R9): `ProbabilityChip` → `rounded-full h-6 px-2 text-[12.5px] font-medium text-[#182638]` with `style={{ backgroundColor: meta.pillBackground }}` and the icon in `meta.color`; keep `title` and `sr-only` label.
- [ ] Verify at 1440 px and 1024 px; `npm run check`; commit `style(frontend): AEW header, premium building cards and pills`; push.

## Task 4: Drawer, prediction cards, why link, explanation, technical details

**Files:** `src/components/detail/*`, `src/components/ui/sheet.tsx` (overlay + content classes only), `src/components/ui/badge.tsx` (add variants `likely`, `possible`, `unlikely` if needed).

- [ ] **Sheet** (R10): overlay classes → `bg-[rgba(20,35,50,0.16)] backdrop-blur-[6px]` with 200 ms ease-out enter/exit; content `data-[side=right]` width via the existing inline style → `width: "min(52vw, 900px)"` on ≥1024 px and `100vw` below (use a CSS class with a media query instead of inline if cleaner), `rounded-none`, `bg-white`, `shadow-[-8px_0_24px_rgba(20,40,60,0.08)]`; close button ghost 32 px, `hover:bg-accent text-navy`, `aria-label` unchanged.
- [ ] **Header**: title `font-serif text-2xl font-semibold text-navy`, description 14 px secondary; padding 24 px; sections spaced 32 px.
- [ ] **Prediction cards** (R11): `rounded-2xl border border-border bg-white p-4`; icon 20 px in asset colour; name 13 px secondary Inter; percentage `font-serif text-[34px] font-semibold text-navy tabular-nums leading-none`; status pill by label: Likely `bg-primary text-white`, Possible `bg-accent text-navy`, Unlikely `bg-white border border-[#C7D0D8] text-[#344454]` — all `rounded-full h-6 px-2.5 text-xs font-medium`; "Why?" `text-[13px] text-primary hover:text-navy hover:underline` (keep `aria-label="Why EV?"`).
- [ ] **Why popover**: white, border, radius 12 px, shadow `0 4px 16px rgba(20,40,60,.10)`; title serif 15 px navy; bars in asset colour on `#EEF2F5` track.
- [ ] **Explanation** (R13): `bg-[#F6F9FB] rounded-2xl p-5`; heading `font-serif text-lg text-navy`; body `text-[14.5px] leading-[1.55] text-[#182638]`. **Technical details**: trigger as text link (primary, hover navy underline); content surface `bg-[#F6F9FB] rounded-2xl p-4`; per-asset blocks white with border.
- [ ] Verify drawer at 1440 px (≈750 px wide), 1280 px, 768 px; `npm run check`; commit `style(frontend): wide white drawer over blurred map, refined prediction cards`; push.

## Task 5: Chart styling and legend

**Files:** `src/lib/chart-option.ts` (+test), `src/components/chart/*`.

- [ ] Option builder per R12: line `CHART.line` 2.5 px; grid `CHART.grid`; axis label colour `CHART.axis`, font 12 px Inter (`fontFamily: "Inter, Arial, sans-serif"`); y-axis name "kW" secondary; band opacity from `EVENT_BAND_OPACITY` (change to 0.14 in `events.ts` only if Task 1 did not — otherwise leave) with EV band label colour `BRAND.blue`, PV band label `#B8791A`, high consumption `#65727D`; tooltip `backgroundColor:"#fff", borderColor:"#D9E0E6", textStyle color "#182638"`; grid margins on the 8 px scale. Update tests that assert colours.
- [ ] Legend: 13 px `text-muted-foreground`, markers: 14×2 px line for Net power, 10 px rounded squares for bands using the band colours at 0.35; chart container `rounded-2xl border border-border bg-white p-4` with the title "Electricity profile — Last 24 hours" **kept in the drawer** (Task 4 owns it) — do not duplicate.
- [ ] Verify at 1440 px; `npm run check`; commit `style(frontend): restrained navy chart with subtle bands`; push.

## Task 6: Integrate, visual QA, tests, merge

- [ ] Merge `feat/ur-map`, `feat/ur-list`, `feat/ur-drawer`, `feat/ur-chart` into `feat/ui-refinement` (`--no-ff`); apply "Requests for Task 6" as separate commits.
- [ ] Cross-cutting consistency pass: spacing on the 8 px grid, one radius language, focus rings, hover timings, no leftover old hex values (`grep -rn "#1d4ed8\|#dbeafe\|#94a3b8\|#1e3a5f\|#d97706\|#16a34a\|#ea580c" src` → none).
- [ ] `npm run check`, `npm run build`, `npm run test:e2e` green. Browser screenshots at 1440 px: map, list with hover and selected card, drawer with chart, why popover, explanation; mobile 375 px sanity (no horizontal scroll).
- [ ] Final whole-branch review (opus) with the brief and spec; one fix wave; re-review.
- [ ] Delete `feat/ur-*` branches/worktrees (local + remote). Merge `feat/ui-refinement` into `feat/frontend-energy-map` (`--no-ff`), push; PR #1 updates automatically. Tag `demo-v2-aew-polish`.

## Self-review

Spec R1–R15 → T1 (R1–R3, R6 CSS, R14 tokens), T2 (R4–R5), T3 (R7–R9), T4 (R10–R11, R13), T5 (R12), T6 (R15, acceptance). Ownership disjoint: T1 owns theme/predictions/events/globals; T2 map + map-style; T3 header/buildings/app-shell; T4 detail + ui/sheet + ui/badge; T5 chart-option + chart components. Cross-task interface: `@/lib/theme` and `ASSETS[].pillBackground`/`color` (T1) consumed by T2–T5.
