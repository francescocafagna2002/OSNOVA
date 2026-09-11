"use client";

import type { FeatureCollection, Polygon } from "geojson";
import type { ExpressionSpecification } from "maplibre-gl";
import { Layer, Source } from "react-map-gl/maplibre";

import type { PlzCountProperties } from "@/lib/plz";
import { BRAND, MAP } from "@/lib/theme";

const PLZ_SOURCE_ID = "plz";
export const PLZ_FILL_LAYER_ID = "plz-fill";

/**
 * Spec R5: one quiet fill and thin borders at rest. A hovered or selected zone *loses* its fill
 * (so the streets and buildings underneath stay readable) and gets a bold AEW-blue outline instead.
 */
const FILL_OPACITY = 0.5;
/** Fill left on a hovered or selected zone: still clearly light blue, but thin enough to read the streets. */
const ACTIVE_FILL_OPACITY = 0.3;
const BORDER_OPACITY = 0.8;
const BORDER_WIDTH = 0.8;
/** Zones with buildings get a bolder outline so they read as the interactive ones. */
const ACTIVE_BORDER_WIDTH = 1.1;
const HOVER_WIDTH = 2.5;
const HIGHLIGHT_WIDTH = 2;
/** Spec R14: 150–250 ms ease-out on map states. */
const OPACITY_TRANSITION = { duration: 200 } as const;
/** A value no PLZ has, so a null filter matches nothing. */
const NO_MATCH = "__none__";

/** True for a zone that has at least one building; empty zones render grey and inert. */
export const HAS_BUILDINGS: ExpressionSpecification = [">", ["get", "count"], 0];

const FILL_COLOR: ExpressionSpecification = ["case", HAS_BUILDINGS, MAP.plzFill, MAP.plzEmptyFill];
const LINE_COLOR: ExpressionSpecification = ["case", HAS_BUILDINGS, MAP.plzBorder, MAP.plzEmptyBorder];
const LINE_WIDTH: ExpressionSpecification = ["case", HAS_BUILDINGS, ACTIVE_BORDER_WIDTH, BORDER_WIDTH];

export function plzFilter(plz: string | null): ExpressionSpecification {
  return ["==", ["get", "plz"], plz ?? NO_MATCH];
}

/** The highlight already outlines its zone; a second hover outline on top only thickens it. */
export function plzHoverFilter(hoveredPlz: string | null, highlightedPlz: string | null): ExpressionSpecification {
  return plzFilter(hoveredPlz === highlightedPlz ? null : hoveredPlz);
}

/** The base fill fades on the hovered and the highlighted zone so the basemap shows through. */
export function plzFillOpacity(
  hoveredPlz: string | null,
  highlightedPlz: string | null,
): number | ExpressionSpecification {
  // Deduplicated: MapLibre rejects a `match` whose labels repeat (hovering the selected zone).
  const active = [...new Set([hoveredPlz, highlightedPlz])].filter((plz): plz is string => plz !== null);
  if (active.length === 0) return FILL_OPACITY;
  return ["match", ["get", "plz"], active, ACTIVE_FILL_OPACITY, FILL_OPACITY];
}

type PlzLayersProps = {
  data: FeatureCollection<Polygon, PlzCountProperties>;
  highlightedPlz: string | null;
  hoveredPlz: string | null;
};

export function PlzLayers({ data, highlightedPlz, hoveredPlz }: PlzLayersProps) {
  return (
    <Source id={PLZ_SOURCE_ID} type="geojson" data={data}>
      <Layer
        id={PLZ_FILL_LAYER_ID}
        type="fill"
        paint={{
          "fill-color": FILL_COLOR,
          "fill-opacity": plzFillOpacity(hoveredPlz, highlightedPlz),
          "fill-opacity-transition": OPACITY_TRANSITION,
        }}
      />
      <Layer
        id="plz-line"
        type="line"
        paint={{ "line-color": LINE_COLOR, "line-opacity": BORDER_OPACITY, "line-width": LINE_WIDTH }}
      />
      <Layer
        id="plz-hover"
        type="line"
        filter={plzHoverFilter(hoveredPlz, highlightedPlz)}
        paint={{ "line-color": BRAND.blue, "line-width": HOVER_WIDTH }}
      />
      <Layer
        id="plz-highlight"
        type="line"
        filter={plzFilter(highlightedPlz)}
        paint={{ "line-color": BRAND.blue, "line-width": HIGHLIGHT_WIDTH }}
      />
    </Source>
  );
}
