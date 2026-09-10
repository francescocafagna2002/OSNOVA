import type { Feature, FeatureCollection, Polygon, Position } from "geojson";

import plzGeoJson from "@/data/aargau-plz.json";
import type { Building } from "@/lib/types";

export type PlzProperties = { plz: string; name: string; gemeinde: string };

/** west, south, east, north */
export type Bbox = [number, number, number, number];

export type PlzArea = PlzProperties & { bbox: Bbox };

type PlzFeature = Feature<Polygon, PlzProperties>;

const collection = plzGeoJson as unknown as FeatureCollection<Polygon, PlzProperties>;

function bboxOf(coordinates: Position[][]): Bbox {
  let west = Number.POSITIVE_INFINITY;
  let south = Number.POSITIVE_INFINITY;
  let east = Number.NEGATIVE_INFINITY;
  let north = Number.NEGATIVE_INFINITY;
  for (const ring of coordinates) {
    for (const [lng, lat] of ring) {
      if (lng < west) west = lng;
      if (lng > east) east = lng;
      if (lat < south) south = lat;
      if (lat > north) north = lat;
    }
  }
  return [west, south, east, north];
}

function unionBbox(boxes: Bbox[]): Bbox {
  return boxes.reduce<Bbox>(
    (acc, [w, s, e, n]) => [Math.min(acc[0], w), Math.min(acc[1], s), Math.max(acc[2], e), Math.max(acc[3], n)],
    [
      Number.POSITIVE_INFINITY,
      Number.POSITIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
    ],
  );
}

export const PLZ_AREAS: readonly PlzArea[] = collection.features.map((feature: PlzFeature) => ({
  ...feature.properties,
  bbox: bboxOf(feature.geometry.coordinates),
}));

export const PLZ_BY_CODE: Record<string, PlzArea> = Object.fromEntries(
  PLZ_AREAS.map((area) => [area.plz, area]),
);

export const AARGAU_BBOX: Bbox = unionBbox(PLZ_AREAS.map((area) => area.bbox));

export function getPlzArea(plz: string): PlzArea | undefined {
  return PLZ_BY_CODE[plz];
}

/** "5000 Aarau"; unknown codes render as the bare code. */
export function formatPlz(plz: string): string {
  const area = getPlzArea(plz);
  return area ? `${plz} ${area.name}` : plz;
}

export function countBuildingsByPlz(buildings: Building[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const building of buildings) {
    counts[building.postcode] = (counts[building.postcode] ?? 0) + 1;
  }
  return counts;
}

export type PlzCountProperties = PlzProperties & { count: number };

/** The committed polygons with a `count` per feature, ready for a MapLibre GeoJSON source. */
export function buildPlzGeoJson(counts: Record<string, number>): FeatureCollection<Polygon, PlzCountProperties> {
  return {
    type: "FeatureCollection",
    features: collection.features.map((feature) => ({
      ...feature,
      properties: { ...feature.properties, count: counts[feature.properties.plz] ?? 0 },
    })),
  };
}
