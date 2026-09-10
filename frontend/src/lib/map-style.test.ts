import type { StyleSpecification } from "maplibre-gl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearPatchedStyleCache, loadPatchedStyle, patchMapStyle } from "@/lib/map-style";
import { MAP, NEUTRAL } from "@/lib/theme";

/** A miniature style with one layer per patch rule, plus a layer no rule matches. */
function styleFixture(): StyleSpecification {
  return {
    version: 8,
    sources: { openmaptiles: { type: "vector", tiles: ["https://example.test/{z}/{x}/{y}.pbf"] } },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#fafaf8" } },
      { id: "park", type: "fill", source: "openmaptiles", paint: { "fill-color": "#d8e8cf" } },
      { id: "landcover_wood", type: "fill", source: "openmaptiles", paint: { "fill-color": "#c8dcbe", "fill-opacity": 0.4 } },
      { id: "landuse_residential", type: "fill", source: "openmaptiles", paint: { "fill-color": "#e0e0e0" } },
      { id: "water", type: "fill", source: "openmaptiles", paint: { "fill-color": "#a0c8f0" } },
      { id: "waterway", type: "line", source: "openmaptiles", paint: { "line-color": "#a0c8f0" } },
      {
        id: "building",
        type: "fill",
        source: "openmaptiles",
        paint: { "fill-color": "#d9d0c9", "fill-outline-color": "#c0b8b0" },
      },
      { id: "building_faint", type: "fill", source: "openmaptiles", paint: { "fill-color": "#d9d0c9", "fill-opacity": 0.2 } },
      { id: "highway_motorway_inner", type: "line", source: "openmaptiles", paint: { "line-color": "#fc8", "line-width": 2 } },
      { id: "highway_motorway_casing", type: "line", source: "openmaptiles", paint: { "line-color": "#e9ac77", "line-width": 3 } },
      { id: "highway_minor", type: "line", source: "openmaptiles", paint: { "line-color": "#cfcdca" } },
      { id: "highway_path", type: "line", source: "openmaptiles", paint: { "line-color": "#cba" } },
      { id: "railway", type: "line", source: "openmaptiles", paint: { "line-color": "#bbb" } },
      { id: "boundary_2", type: "line", source: "openmaptiles", paint: { "line-color": "#8b8b8b", "line-width": 1 } },
      {
        id: "label_city",
        type: "symbol",
        source: "openmaptiles",
        paint: { "text-color": "#333", "text-halo-color": "#eee", "text-halo-width": 1 },
      },
      { id: "highway-shield-non-us", type: "symbol", source: "openmaptiles" },
      { id: "poi_z14", type: "symbol", source: "openmaptiles", paint: { "text-color": "#666" } },
      { id: "custom_overlay", type: "fill", source: "openmaptiles", paint: { "fill-color": "#ff00ff" } },
    ],
  };
}

const paintOf = (style: StyleSpecification, id: string): Record<string, unknown> =>
  (style.layers.find((layer) => layer.id === id)?.paint ?? {}) as Record<string, unknown>;

describe("patchMapStyle", () => {
  it("recolours the background", () => {
    expect(paintOf(patchMapStyle(styleFixture()), "background")["background-color"]).toBe(MAP.background);
  });

  it("flattens land, landcover, landuse and park fills to the land colour", () => {
    const patched = patchMapStyle(styleFixture());
    for (const id of ["park", "landcover_wood", "landuse_residential"]) {
      expect(paintOf(patched, id)["fill-color"]).toBe(MAP.land);
    }
    expect(paintOf(patched, "landcover_wood")["fill-opacity"]).toBe(0.4);
  });

  it("recolours water fills and waterway lines", () => {
    const patched = patchMapStyle(styleFixture());
    expect(paintOf(patched, "water")["fill-color"]).toBe(MAP.water);
    expect(paintOf(patched, "waterway")["line-color"]).toBe(MAP.water);
  });

  it("draws buildings as land at no more than 0.6 opacity, with a quiet outline", () => {
    const patched = patchMapStyle(styleFixture());
    expect(paintOf(patched, "building")).toMatchObject({
      "fill-color": MAP.land,
      "fill-opacity": 0.6,
      "fill-outline-color": MAP.roadMinor,
    });
    expect(paintOf(patched, "building_faint")["fill-opacity"]).toBe(0.2);
  });

  it("paints major roads white and casings, minor roads, paths and rail in the minor tone", () => {
    const patched = patchMapStyle(styleFixture());
    expect(paintOf(patched, "highway_motorway_inner")["line-color"]).toBe(MAP.roadMajor);
    expect(paintOf(patched, "highway_motorway_casing")["line-color"]).toBe(MAP.roadMinor);
    for (const id of ["highway_minor", "highway_path", "railway"]) {
      expect(paintOf(patched, id)["line-color"]).toBe(MAP.roadMinor);
    }
  });

  it("keeps road widths untouched", () => {
    const patched = patchMapStyle(styleFixture());
    expect(paintOf(patched, "highway_motorway_inner")["line-width"]).toBe(2);
    expect(paintOf(patched, "highway_motorway_casing")["line-width"]).toBe(3);
  });

  it("hides administrative boundaries so only the PLZ zones draw borders", () => {
    expect(paintOf(patchMapStyle(styleFixture()), "boundary_2")["line-opacity"]).toBe(0);
  });

  it("gives labels the map label colour, a white halo and 0.9 opacity", () => {
    const patched = patchMapStyle(styleFixture());
    expect(paintOf(patched, "label_city")).toMatchObject({
      "text-color": MAP.label,
      "text-halo-color": "#FFFFFF",
      "text-opacity": 0.9,
      "text-halo-width": 1,
    });
    expect(paintOf(patched, "highway-shield-non-us")["text-color"]).toBe(MAP.label);
  });

  it("hides POI labels", () => {
    expect(paintOf(patchMapStyle(styleFixture()), "poi_z14")["text-opacity"]).toBe(0);
  });

  it("leaves unmatched layers alone", () => {
    expect(paintOf(patchMapStyle(styleFixture()), "custom_overlay")["fill-color"]).toBe("#ff00ff");
  });

  it("is pure: the input style and its nested paint objects are untouched", () => {
    const input = styleFixture();
    const patched = patchMapStyle(input);
    expect(input).toEqual(styleFixture());
    expect(patched).not.toBe(input);
    expect(patched.layers[0]).not.toBe(input.layers[0]);
  });

  it("keeps sources and the style version", () => {
    const patched = patchMapStyle(styleFixture());
    expect(patched.version).toBe(8);
    expect(patched.sources).toEqual(styleFixture().sources);
  });
});

describe("loadPatchedStyle", () => {
  beforeEach(() => {
    clearPatchedStyleCache();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const stubFetch = (impl: () => Promise<Response>) => {
    const fetchMock = vi.fn(impl);
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  };

  const okResponse = () =>
    Promise.resolve({ ok: true, status: 200, json: async () => styleFixture() } as Response);

  it("fetches the style and returns it patched", async () => {
    const fetchMock = stubFetch(okResponse);
    const style = await loadPatchedStyle("https://example.test/style.json");
    expect(fetchMock).toHaveBeenCalledWith("https://example.test/style.json");
    expect(paintOf(style, "background")["background-color"]).toBe(MAP.background);
  });

  it("memoises per URL", async () => {
    const fetchMock = stubFetch(okResponse);
    const first = await loadPatchedStyle("https://example.test/a.json");
    const second = await loadPatchedStyle("https://example.test/a.json");
    await loadPatchedStyle("https://example.test/b.json");
    expect(first).toBe(second);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects on a non-ok response and does not cache the failure", async () => {
    const fetchMock = stubFetch(() =>
      Promise.resolve({ ok: false, status: 503, json: async () => ({}) } as Response),
    );
    await expect(loadPatchedStyle("https://example.test/style.json")).rejects.toThrow("503");
    await expect(loadPatchedStyle("https://example.test/style.json")).rejects.toThrow("503");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects when the network fails", async () => {
    stubFetch(() => Promise.reject(new Error("offline")));
    await expect(loadPatchedStyle("https://example.test/style.json")).rejects.toThrow("offline");
  });
});
