import type { StyleSpecification } from "maplibre-gl";

import { MAP, NEUTRAL } from "@/lib/theme";

/**
 * Client-side recolouring of a vector basemap style (spec R4).
 *
 * The demo keeps OpenFreeMap's positron tiles but repaints them into the AEW palette so the
 * map reads as a quiet technical backdrop. Rules match on `layer.type` plus substrings of a
 * lower-cased `layer.id`, so a style with different layer names degrades gracefully: anything
 * unmatched keeps its original paint.
 */

const HALO_COLOR = "#FFFFFF";
const LABEL_OPACITY = 0.9;
const BUILDING_MAX_OPACITY = 0.6;

const WATER_ID = /water|sea|ocean|river|lake|bay/;
const LAND_ID = /land|park|wood|grass|residential|farmland|forest|cemetery|sand|pitch/;
const BOUNDARY_ID = /boundary|admin/;
/** Casings and low-zoom "subtle" variants are outlines, not the road surface. */
const ROAD_CASING_ID = /casing|outline|subtle/;
const ROAD_MAJOR_ID = /motorway|trunk|primary|secondary|major/;
const ROAD_MINOR_ID = /road|highway|street|path|track|rail|transit|ferry|aeroway|runway|taxiway|pier|bridge|tunnel/;
const POI_ID = /(^|[-_])poi/;

/** A layer seen through a permissive lens: the spec's paint unions are per-layer-type. */
type LooseLayer = { id: string; type: string; paint?: Record<string, unknown> };

function paintOf(layer: LooseLayer): Record<string, unknown> {
  layer.paint ??= {};
  return layer.paint;
}

/** Keeps an already-fainter opacity, otherwise clamps to `max`. */
function clampOpacity(current: unknown, max: number): number {
  return typeof current === "number" && current < max ? current : max;
}

function patchFill(id: string, paint: Record<string, unknown>): void {
  if (WATER_ID.test(id)) {
    paint["fill-color"] = MAP.water;
    return;
  }
  if (id.includes("building")) {
    paint["fill-color"] = MAP.land;
    paint["fill-opacity"] = clampOpacity(paint["fill-opacity"], BUILDING_MAX_OPACITY);
    if ("fill-outline-color" in paint) paint["fill-outline-color"] = MAP.roadMinor;
    return;
  }
  if (LAND_ID.test(id)) paint["fill-color"] = MAP.land;
}

function patchLine(id: string, paint: Record<string, unknown>): void {
  if (WATER_ID.test(id)) {
    paint["line-color"] = MAP.water;
    return;
  }
  if (BOUNDARY_ID.test(id)) {
    // Administrative (municipal/cantonal) borders compete with the PLZ zones; the zones are the only borders we draw.
    paint["line-opacity"] = 0;
    return;
  }
  const isRoad = ROAD_MAJOR_ID.test(id) || ROAD_MINOR_ID.test(id);
  if (!isRoad) return;
  const isSurface = !ROAD_CASING_ID.test(id) && ROAD_MAJOR_ID.test(id);
  paint["line-color"] = isSurface ? MAP.roadMajor : MAP.roadMinor;
}

function patchSymbol(id: string, paint: Record<string, unknown>): void {
  if (POI_ID.test(id)) {
    paint["text-opacity"] = 0;
    return;
  }
  paint["text-color"] = MAP.label;
  paint["text-halo-color"] = HALO_COLOR;
  paint["text-opacity"] = LABEL_OPACITY;
}

function patchLayer(layer: LooseLayer): void {
  const id = layer.id.toLowerCase();
  switch (layer.type) {
    case "background":
      paintOf(layer)["background-color"] = MAP.background;
      return;
    case "fill":
      patchFill(id, paintOf(layer));
      return;
    case "line":
      patchLine(id, paintOf(layer));
      return;
    case "symbol":
      patchSymbol(id, paintOf(layer));
      return;
    default:
      return;
  }
}

/** Deep-copies `style` and repaints its layers into the AEW map palette. Pure. */
export function patchMapStyle(style: StyleSpecification): StyleSpecification {
  const patched = JSON.parse(JSON.stringify(style)) as StyleSpecification;
  for (const layer of patched.layers as unknown as LooseLayer[]) {
    patchLayer(layer);
  }
  return patched;
}

const styleCache = new Map<string, Promise<StyleSpecification>>();

async function fetchPatchedStyle(url: string): Promise<StyleSpecification> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Map style request failed with status ${response.status}`);
  return patchMapStyle((await response.json()) as StyleSpecification);
}

/** Fetches a style JSON once per URL and returns the patched object. Failures are not cached. */
export function loadPatchedStyle(url: string): Promise<StyleSpecification> {
  const cached = styleCache.get(url);
  if (cached) return cached;
  const pending = fetchPatchedStyle(url).catch((error: unknown) => {
    styleCache.delete(url);
    throw error;
  });
  styleCache.set(url, pending);
  return pending;
}

/** Test seam: drops the memoised styles so each case starts from a cold cache. */
export function clearPatchedStyleCache(): void {
  styleCache.clear();
}
