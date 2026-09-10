"use client";

import type { FeatureCollection, Polygon } from "geojson";
import type { ExpressionSpecification } from "maplibre-gl";
import { Layer, Source } from "react-map-gl/maplibre";

import type { PlzCountProperties } from "@/lib/plz";

const PLZ_SOURCE_ID = "plz";
export const PLZ_FILL_LAYER_ID = "plz-fill";

/** Spec §10: one quiet fill, thin borders, tint on hover, strong outline for the highlighted area. */
const MAP_COLORS = {
  fill: "#dbeafe",
  border: "#94a3b8",
  highlight: "#1d4ed8",
} as const;
const FILL_OPACITY = 0.35;
const HOVER_OPACITY = 0.12;
/** A value no PLZ has, so a null filter matches nothing. */
const NO_MATCH = "__none__";

export function plzFilter(plz: string | null): ExpressionSpecification {
  return ["==", ["get", "plz"], plz ?? NO_MATCH];
}

type PlzLayersProps = {
  data: FeatureCollection<Polygon, PlzCountProperties>;
  highlightedPlz: string | null;
  hoveredPlz: string | null;
};

export function PlzLayers({ data, highlightedPlz, hoveredPlz }: PlzLayersProps) {
  return (
    <Source id={PLZ_SOURCE_ID} type="geojson" data={data}>
      <Layer id={PLZ_FILL_LAYER_ID} type="fill" paint={{ "fill-color": MAP_COLORS.fill, "fill-opacity": FILL_OPACITY }} />
      <Layer
        id="plz-hover"
        type="fill"
        filter={plzFilter(hoveredPlz)}
        paint={{ "fill-color": MAP_COLORS.highlight, "fill-opacity": HOVER_OPACITY }}
      />
      <Layer id="plz-line" type="line" paint={{ "line-color": MAP_COLORS.border, "line-width": 0.6 }} />
      <Layer
        id="plz-highlight"
        type="line"
        filter={plzFilter(highlightedPlz)}
        paint={{ "line-color": MAP_COLORS.highlight, "line-width": 2.5 }}
      />
    </Source>
  );
}
