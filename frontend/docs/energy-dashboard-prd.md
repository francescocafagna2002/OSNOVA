# AEW Energy Management Dashboard — Product Requirements (verbatim, 2026-09-10)

> Supplied by the product owner. The binding engineering interpretation is
> `docs/superpowers/specs/2026-09-10-energy-dashboard-design.md` at the repo root.

## 1. Project Overview

Design and build a modern enterprise energy-management dashboard inspired by the visual identity of AEW Energie AG. The product is a centralized control and monitoring interface for managing energy infrastructure across multiple buildings/sites.

The dashboard should allow users to: view all buildings/sites on a geographic map; identify buildings using unique IDs; filter and search buildings; monitor energy production and consumption; monitor solar/PV systems; monitor batteries and energy storage; monitor connected devices; identify errors, warnings and offline equipment; select a building and inspect its detailed energy data; navigate from regional overview → building → individual energy system/device.

The product should feel like a **professional Swiss energy infrastructure platform**, not a generic SaaS dashboard.

## 2. Design Direction

Brand inspiration: AEW Energie AG — Swiss, clean, precise, technical, trustworthy, infrastructure-oriented, sustainable, data-driven, minimal but highly functional. Do NOT simply copy the AEW website. The interface should communicate: "This is a professional control center for real energy infrastructure."

Avoid: excessive gradients, glassmorphism, excessive rounded cards, decorative illustrations, generic AI/SaaS aesthetics, excessive animations, neon colors, visually noisy charts.

## 3. Main User

Primary: energy / infrastructure operator monitoring many buildings and energy systems. Secondary: energy managers, facility managers, technical operators, operations teams, management. Must work for quick operational monitoring and detailed technical investigation.

## 4. Information Architecture

Region / PLZ → Buildings → Building detail → Energy systems → Individual devices.

We DO NOT have building addresses. Use Building ID, Site ID, PLZ / postal-code zone, geographic position, building status. Example: PLZ 5000 → Building BLD-001, BLD-002, BLD-003.

## 5. Main Dashboard

Header (logo, section title, user/settings); left navigation (Overview, Buildings, Devices, Energy, Alerts); main area with KPI cards, map and a buildings list.

## 6. Header

Left: AEW logo / brand. Center: current section title (e.g. Energy Management). Right: notifications, user profile, settings, optional system status indicator. Clean and compact.

## 7. Navigation

Overview (overall status), Buildings (list + map), Devices (all equipment), Energy (production, consumption, storage, flows), Alerts (warnings, errors, events), Settings. Active states in AEW Blue.

## 8. Geographic Map

Represents buildings geographically. NO addresses available: do not display or generate fake addresses. Display PLZ, Building ID, geographic location, status.

## 9. PLZ Zone Visualization

PLZ as geographic polygons. Selected PLZ highlighted with a subtle blue overlay that does not overpower buildings. Hover PLZ → PLZ information; click PLZ → filter buildings to this PLZ.

## 10. Building Markers

Marker states: Normal (blue), Efficient/healthy (green), Warning (orange/yellow), Critical (red), Offline (grey). Hover: ID, PLZ, energy status, consumption, production. Click: open Building Detail.

## 11. Building List

Each item: ID, PLZ, status, production, consumption; status indicator. Supports search, sorting, filtering, pagination or virtualization, status filtering, PLZ filtering.

## 12. Search

Global search by Building ID, PLZ, Device ID, Device name. Placeholder: "Search buildings, PLZ or devices...". Results update dynamically.

## 13. Filters

PLZ; building status (All/Normal/Warning/Critical/Offline); energy system (Solar/PV, Battery, HVAC, Meter, EV charging, Other); connectivity (Online/Offline/Warning). Combinable.

## 14. KPI Cards

Total Buildings; Energy Production (today); Energy Consumption (today); Self-consumption (%); Active Alerts (with critical count). Large numbers, small labels.

## 15. Energy Overview

High-level energy flow visualization: Solar → Energy system → Battery / Building → Consumption; metrics production, consumption, grid import/export, battery charge/discharge.

## 16. Charts

Production (line/area), consumption (line), production vs consumption (two series), battery state (line/area), energy distribution (donut/stacked bar). Time filters: Today, 24h, 7 days, 30 days, 12 months, Custom. Charts show units, time, legend, tooltip, current value, previous-period comparison where useful.

## 17–19. Building Detail

Header → summary (ID, PLZ, status, last update, connectivity) → energy KPIs (current load, today's production/consumption, self-consumption, grid import/export) → energy chart → systems → devices → alerts/events.

## 20. Systems

PV (status, current production, today's production), Battery (status, SoC, power), HVAC (status, consumption), EV Charging (active/total, load).

## 21–22. Devices

Table: Device, Type, Status, Current Value, Last Update. Device detail: ID, type, manufacturer, model, serial, status, connection, last update; measurements relevant to the type (voltage, current, power, energy, temperature, efficiency, SoC).

## 23. Alerts

Levels Critical / Warning / Info; list supports filter, sort, acknowledge, open related building/device.

## 24. System Status

Global indicator: Operational; counts of buildings, devices, online, offline, warnings, critical. Visible from the main dashboard.

## 25–28. Data Refresh and States

Show data freshness ("Last updated 16:42:31"), automatic/manual refresh, loading, stale ("Data delayed — last update 18 min ago"). Loading skeletons for every major component; empty states ("No buildings found — try changing your filters", "No alerts — all systems operating normally"); error states with retry.

## 29. Responsive

Desktop 1440–1920 primary. Tablet 768–1199: collapse navigation, reduce map/list split. Mobile 320–767: prioritise KPIs, alerts, search, list, map, charts; map must stay usable.

## 30–35. Design System

Primary `#0065A8`, dark blue `#003B5C`, secondary blue `#00558C`, light blue `#EAF4FA`, background `#F4F7F9`, white, primary text `#1D252C`, secondary text `#66727C`, border `#D9E1E6`. Status: success `#2E8B57`, warning `#F59E0B`, critical `#D64545`, offline `#8A959E`, solar `#F5B82E`, battery `#7A5AF8` (semantic only). Font Inter (alt. Helvetica Neue/Arial); hierarchy Display 48–56/600, H1 36–40/600, H2 28–32/600, H3 20–24/600, Body 14–16/400, Label 12–14/500, KPI 28–40/600–700; tabular numerals. Spacing 4/8 system. Radius 4/8/12, cards 8. Shadows sparingly. Consistent outline icons.

## 36–38. Interaction, Hover, Accessibility

Marker → detail; PLZ → filter; list row → map centers and highlights; building → systems → device → detail. Hover tooltips on markers, rows, KPIs, charts. WCAG 2.1 AA where practical: contrast, no colour-only status ("● Critical"), keyboard, focus, labels, chart summaries.

## 39–45. Architecture, Entities, Mock Data, Performance, Security, Audit

Data model Region → PLZ → Building → Systems/Devices/Measurements/Alerts. Entities Building (id, plz, lat, lng, status, lastUpdated, systems, devices), Device, Measurement, Alert. Mock: 100+ buildings, multiple PLZ, 500+ devices, all states, history, alerts; no fake addresses. Performance: 1,000+ buildings, 10,000+ devices; virtualisation, clustering, lazy loading, debounced search. Prepare for roles (Admin, Energy Manager, Operator, Viewer) and audit logging (future).

## 46–47. UX Principle and Priority

Answer within seconds: what is happening, where is the problem, which building, which device, energy situation, what needs attention. Visual priority: critical alerts > system status > energy KPIs > geography > building status > trends > device details > metadata.

## 48. MVP Scope

MUST: main dashboard, design system, header, navigation, KPI cards, PLZ zones, markers, list, search, filters, building detail, energy KPIs, charts, systems, devices, alerts, loading/empty/error states, responsive. SHOULD: device detail, advanced charts, alert acknowledgement, date range, clustering, freshness. FUTURE: permissions, automation, control, configuration, reports, export, AI, predictive maintenance.

## 49. Acceptance Criteria

1 buildings on map · 2 PLZ polygons · 3 IDs not addresses · 4 filter by PLZ · 5 search by ID · 6 filter by status · 7 critical identifiable · 8 open from map · 9 open from list · 10 detail KPIs · 11 systems and devices · 12 charts · 13 active alerts · 14 system operational status · 15 loading/error/empty · 16 responsive · 17 design system · 18 no fake addresses · 19 scalable to 1,000+/10,000+ · 20 reusable, data-driven components.

## 50. Overall Design Goal

AEW + Swiss precision + modern energy control center. CLEAN · TECHNICAL · PRECISE · TRUSTWORTHY · DATA-FIRST · SWISS · ENERGY · OPERATIONAL. The map + PLZ zones + building IDs are defining; drill down region → building → system → device.
