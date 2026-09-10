# AEW Energy Management Dashboard — UI Refinement Task (verbatim brief, 2026-09-10)

> Supplied by the product owner. Engineering interpretation: `docs/superpowers/specs/2026-09-10-ui-refinement-design.md` at the repo root.

## 1. Objective
We already have a working dashboard demo and an established layout/interaction structure. Do NOT redesign the product structure. Refine the existing UI and visual design so that it feels like a polished AEW Energie AG enterprise energy-management product, while preserving the current information architecture, layout, components and user flow. The demo already contains: full-screen geographic map; PLZ polygons; building markers; right-side building list; building cards; building detail side panel/drawer; energy-system probability cards; electricity profile chart; explanatory calculation section. Core rule: DO NOT change the existing structure. Improve visual language, typography, colors, spacing, borders, states, icons and overall polish.

## 2. Reference
Target direction: AEW Energie AG × Swiss utility × modern energy technology × technical precision. AEW positioning: reliable and climate-friendly supply, renewables, digitalisation, operational excellence. AEW's site uses Google Fonts and Font Awesome; a web-font/icon implementation is compatible.

## 3–4. Do not change / layout
Main screen: FULL SCREEN MAP + RIGHT BUILDING LIST (map ~65–70 %, list ~30–35 %). Building detail: MAP → dim/blur background → RIGHT-SIDE DETAIL DRAWER (not a page, modal, bottom sheet or new navigation flow). No traditional left sidebar.

## 5. Map
Quiet, technical, geographic. Palette: map background `#F5F6F4`, land `#F7F8F6`, roads `#FFFFFF`, secondary roads `#E3E5E4`, water `#DDE9ED`, labels `#1F2933`. Low contrast so energy/building information stays the focus.

## 6. PLZ Polygons
Keep, visible but subtle. Default fill `#EAF2FA` (40–60 %), border `#AFC2D8` (70–90 %). Hover `#D9E8F6`. Selected: AEW blue `#0065A8` with a subtle translucent fill. Not neon.

## 7. AEW Brand Colors
AEW blue `#0065A8` (selected states, primary actions, selected building, active controls, links, chart accents, map selection, focus). Dark blue `#003B5C` (headings, high-contrast text, active typography). Secondary blue `#00558C` (hover, darker interactive). Light blue `#EAF4FA` (selected backgrounds, information surfaces, KPI backgrounds, map states).

## 8. Neutrals
White `#FFFFFF`; page/map background `#F5F6F4`; soft surface `#F7F9FB`; light border `#D9E0E6`; medium border `#C7D0D8`; secondary text `#65727D`; primary text `#182638`; dark text `#102033`. No pure black.

## 9. Energy Colors (semantic only)
PV `#F59E0B` or softer `#EFA33A`; battery `#39A85A`; heat pump `#E85B2A`; EV `#2563EB`; success `#2E8B57`; warning `#F59E0B`; critical `#D64545`; offline `#8A959E`. AEW blue stays the dominant UI colour.

## 10–11. Typography
Preserve the editorial/serif character: Georgia or Source Serif 4 for building titles, section titles, large KPI values, headings, drawer headings. Inter (or Arial/Helvetica Neue) for buttons, filters, labels, metadata, timestamps, controls, tables, values. Scale: main title 32–36/500–600; section heading 22–26/600; building title 20–24/600; KPI number 30–38/600; body 14–16, lh 1.45–1.6; metadata 13–14; chart labels 12–14.

## 12–16. Building list, cards, pills
Card: building icon; "Building AG-021249"; "5070 Frick"; four pills (☀ 61 %, battery 45 %, heat pump 27 %, EV 92 %). No extra info. Card: white, 1 px `#D9E0E6`, radius 16 px, shadow `0 1px 3px rgba(20,40,60,0.06)`, almost flat. Hover: border `#AFC2D8`, background `#FBFDFF`, subtle shadow, pointer. Selected: border `#0065A8`, background `#F7FBFE`, optional `box-shadow: 0 0 0 1px #0065A8`; also highlighted on the map. Pills compact, light backgrounds, semantic icon colour, dark neutral text: PV bg `#FFF7E8` icon `#EFA33A`; battery bg `#EFF8F1` icon `#39A85A`; heat pump bg `#FFF2ED` icon `#E85B2A`; EV bg `#EFF4FF` icon `#2563EB`.

## 17–21. Detail drawer
Exact current structure: title, PLZ line, four system cards, "Electricity profile", chart, legend, "How is this calculated?". No tabs. Width ≈ 50–53 vw, max 880–920 px. Pure white, no glassmorphism/gradient. Overlay `rgba(20,35,50,0.12–0.20)` + `backdrop-filter: blur(4–8px)`; map stays visible. Header keeps "Building AG-021249 / 5070 Frick, AG"; close top right, minimal, unfilled, clear hover, AEW blue/navy interactive.

## 22–25. System cards, status, Why?
Four cards (PV / Solar, Battery, Heat pump, Electric vehicle) with icon, name, percentage, status, Why?. White, thin border, radius 16 px, no strong shadow; large serif percentage. Status: likely = AEW blue filled (`#0065A8` on white); unlikely = white with border `#C7D0D8`, text `#344454`; possible = very light blue/grey; understandable without colour. "Why?" = text link `#0065A8`, hover `#003B5C` underline; not a button.

## 26–29. Chart, legend, explanation
Title "Electricity profile — Last 24 hours"; same size/position/type. Main line navy `#18385A` 2–3 px; grid `#E1E6EA`; axis labels `#65727D`; PV area warm light orange 10–20 %; EV area light AEW blue 10–20 %; no saturated fills. Legend: Net power / EV charging / Possible PV generation, small markers, 13–14 px neutral text. Explanation card below chart: background `#F6F9FB`, radius 16 px, serif heading, body 14–16 px.

## 30–33. Icons, markers, controls, header
One outline family (Lucide), 18–22 px, no emoji: solar→sun, battery→battery, heat pump→flame, EV→car, building→building, close→x, zoom→plus/minus. Markers compact and status-aware with clustering (if present). Map controls minimal: white, thin border, small shadow, radius 8 px. Header: white, subtle bottom border, AEW blue logo, dark navy text, compact controls; no dark navigation.

## 34–38. Ratios, spacing, radius, animation, responsive
70 % map / 30 % list; drawer open ≈ 50/50 with map visible. 8 px grid (4–64). Radius: cards 16, pills 999, inputs 8–10, controls 8, drawer 0. Animation 150–250 ms ease-out for hover, drawer, selection, filters, tooltips; no bouncing/gradients/particles. Desktop 1440+ primary; tablet reduce proportions; mobile stack without changing product logic.

## 39–42. Data, performance, accessibility
No fake addresses: building ID, PLZ, coordinates only ("Building AG-021249 / 5070 Frick, AG"). Preserve the data model (PLZ → buildings → PV/battery/heat pump/EV; probabilities, measurements, alerts). Refinement must not slow map/list; clustering, virtualisation, debounced search, lazy loading, memoisation where appropriate. Keyboard, focus, contrast, labels, status text with colour ("● Online").

## 43–45. Must not / should / principle
Must not: redesign structure, add a left sidebar, move the list, replace the map, remove PLZ polygons or IDs, turn the drawer into a page, add unrelated dashboard grids or KPI sections, invent addresses, change flow, excessive animation, glassmorphism, dark mode, neon, generic SaaS look, replace chart or card concepts. Should: refine typography, colours, spacing, hierarchy, borders, shadows, icon consistency, hover/selected/loading states, chart and map styling; brand alignment; UX polish. Final feel: precise + calm + trustworthy + technical + modern + Swiss; structure and functionality essentially unchanged, significantly more polished and AEW-branded.
