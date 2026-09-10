"use client";

import type { FeatureCollection, Polygon } from "geojson";
import type { ExpressionSpecification } from "maplibre-gl";
import { Layer, Source } from "react-map-gl/maplibre";

import type { PlzCountProperties } from "@/lib/plz";
import { BRAND, MAP } from "@/lib/theme";

const PLZ_SOURCE_ID = "plz";
export const PLZ_FILL_LAYER_ID = "plz-fill";

/** Spec R5: one quiet fill, thin borders, a light tint on hover, AEW blue for the selection. */
const FILL_OPACITY = 0.5;
const BORDER_OPACITY = 0.8;
const BORDER_WIDTH = 0.8;
const HOVER_OPACITY = 0.6;
const HIGHLIGHT_FILL_OPACITY = 0.1;
const HIGHLIGHT_WIDTH = 2;
/** Spec R14: 150–250 ms ease-out on map states. */
const OPACITY_TRANSITION = { duration: 200 } as const;
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
      <Layer id={PLZ_FILL_LAYER_ID} type="fill" paint={{ "fill-color": MAP.plzFill, "fill-opacity": FILL_OPACITY }} />
      <Layer
        id="plz-hover"
        type="fill"
        filter={plzFilter(hoveredPlz)}
        paint={{
          "fill-color": MAP.plzHover,
          "fill-opacity": HOVER_OPACITY,
          "fill-opacity-transition": OPACITY_TRANSITION,
        }}
      />
      <Layer
        id="plz-highlight-fill"
        type="fill"
        filter={plzFilter(highlightedPlz)}
        paint={{
          "fill-color": BRAND.blue,
          "fill-opacity": HIGHLIGHT_FILL_OPACITY,
          "fill-opacity-transition": OPACITY_TRANSITION,
        }}
      />
      <Layer
        id="plz-line"
        type="line"
        paint={{ "line-color": MAP.plzBorder, "line-opacity": BORDER_OPACITY, "line-width": BORDER_WIDTH }}
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
