"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Map, { NavigationControl, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";

import { MapTooltip } from "@/components/map/map-tooltip";
import { PLZ_FILL_LAYER_ID, PlzLayers } from "@/components/map/plz-layers";
import { useHighlightedPlz, usePlzCounts } from "@/hooks/use-buildings";
import { AARGAU_BBOX, buildPlzGeoJson, getPlzArea, type PlzCountProperties } from "@/lib/plz";
import { useUIStore } from "@/stores/ui-store";

export const MAP_STYLE_URL =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron";

const FIT_PADDING = 48;
const FIT_DURATION_MS = 900;
const FIT_MAX_ZOOM = 13;

type Hover = { plz: string; count: number; x: number; y: number } | null;

function plzFeatureAt(event: MapLayerMouseEvent): PlzCountProperties | undefined {
  return event.features?.[0]?.properties as PlzCountProperties | undefined;
}

export function MapView() {
  const mapRef = useRef<MapRef>(null);
  const counts = usePlzCounts();
  const highlightedPlz = useHighlightedPlz();
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const selectPlz = useUIStore((s) => s.selectPlz);
  const [hover, setHover] = useState<Hover>(null);

  const data = useMemo(() => buildPlzGeoJson(counts), [counts]);

  useEffect(() => {
    if (!highlightedPlz) return;
    const area = getPlzArea(highlightedPlz);
    if (!area) return;
    mapRef.current?.fitBounds(area.bbox, {
      padding: FIT_PADDING,
      duration: FIT_DURATION_MS,
      maxZoom: FIT_MAX_ZOOM,
    });
  }, [highlightedPlz]);

  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const feature = plzFeatureAt(event);
      if (!feature) {
        selectPlz(null);
        return;
      }
      selectPlz(feature.plz === selectedPlz ? null : feature.plz);
    },
    [selectPlz, selectedPlz],
  );

  const handleMouseMove = useCallback((event: MapLayerMouseEvent) => {
    const feature = plzFeatureAt(event);
    setHover(feature ? { plz: feature.plz, count: feature.count, x: event.point.x, y: event.point.y } : null);
  }, []);

  const clearHover = useCallback(() => setHover(null), []);

  return (
    <div className="relative h-full w-full" data-testid="map-view">
      <Map
        ref={mapRef}
        mapStyle={MAP_STYLE_URL}
        initialViewState={{ bounds: AARGAU_BBOX, fitBoundsOptions: { padding: 24 } }}
        interactiveLayerIds={[PLZ_FILL_LAYER_ID]}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={clearHover}
        cursor={hover ? "pointer" : "grab"}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="bottom-right" showCompass={false} />
        <PlzLayers data={data} highlightedPlz={highlightedPlz} hoveredPlz={hover?.plz ?? null} />
      </Map>
      <MapTooltip plz={hover?.plz ?? null} count={hover?.count ?? 0} x={hover?.x ?? 0} y={hover?.y ?? 0} />
    </div>
  );
}
