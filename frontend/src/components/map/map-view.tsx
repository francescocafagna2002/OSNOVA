"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { setWorkerUrl } from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Map, {
  NavigationControl,
  type MapEvent,
  type MapLayerMouseEvent,
  type MapRef,
  type ViewStateChangeEvent,
} from "react-map-gl/maplibre";

import { MapTooltip } from "@/components/map/map-tooltip";
import { PLZ_FILL_LAYER_ID, PlzLayers } from "@/components/map/plz-layers";
import { useHighlightedPlz, usePlzCounts } from "@/hooks/use-buildings";
import { AARGAU_BBOX, buildPlzGeoJson, getPlzArea, type PlzCountProperties } from "@/lib/plz";
import { useUIStore } from "@/stores/ui-store";

// MapLibre resolves its worker with `new URL("./maplibre-gl-worker.mjs", import.meta.url)`,
// which Turbopack rewrites to an empty URL; point it at the copy in `public/` instead.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

const MAP_STYLE_URL =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron";

const INITIAL_FIT_PADDING = 24;
const INITIAL_FIT_LATCH_MS = 1500;
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
  const cantonFittedRef = useRef(false);
  const fitLatchExpiredRef = useRef(false);

  const data = useMemo(() => buildPlzGeoJson(counts), [counts]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fitLatchExpiredRef.current = true;
    }, INITIAL_FIT_LATCH_MS);
    return () => window.clearTimeout(timer);
  }, []);

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

  /**
   * MapLibre reads the container size in its constructor, before the flex layout has
   * settled on first mount, and falls back to 400x300 — the `initialViewState` fit then
   * lands far too zoomed out. Its `load` event is not reliable here (never fires in this
   * setup), so refit on the first `resize`, which is exactly when the real size arrives
   * on a genuinely fresh mount.
   *
   * On a remount (e.g. toggling List -> Map) the container already has its final size
   * when the map is constructed, so MapLibre never fires that initial resize — the latch
   * would otherwise stay armed indefinitely and hijack the *next* real resize (window
   * resize, devtools, orientation change), snapping the user's pan/zoom back to the whole
   * canton. So the latch also expires on its own: either the first user-originated move
   * (`onMoveStart` carrying a DOM event) or a short timeout from mount, whichever comes
   * first. Only a resize that lands before both counts as the "initial" one.
   */
  const fitCantonOnce = useCallback(
    (event: MapEvent) => {
      if (cantonFittedRef.current || fitLatchExpiredRef.current) return;
      cantonFittedRef.current = true;
      if (highlightedPlz) return;
      event.target.fitBounds(AARGAU_BBOX, { padding: INITIAL_FIT_PADDING, duration: 0 });
    },
    [highlightedPlz],
  );

  const expireFitLatchOnUserMove = useCallback((event: ViewStateChangeEvent) => {
    if (event.originalEvent) {
      fitLatchExpiredRef.current = true;
    }
  }, []);

  return (
    <div className="relative h-full w-full" data-testid="map-view">
      <Map
        ref={mapRef}
        mapStyle={MAP_STYLE_URL}
        initialViewState={{ bounds: AARGAU_BBOX, fitBoundsOptions: { padding: INITIAL_FIT_PADDING } }}
        interactiveLayerIds={[PLZ_FILL_LAYER_ID]}
        onResize={fitCantonOnce}
        onMoveStart={expireFitLatchOnUserMove}
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
