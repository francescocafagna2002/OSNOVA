import { act, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearPatchedStyleCache } from "@/lib/map-style";
import { AARGAU_BBOX } from "@/lib/plz";
import { MAP } from "@/lib/theme";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

const mapMock = vi.hoisted(() => ({
  props: {} as Record<string, unknown>,
  fitBounds: vi.fn(),
}));

vi.mock("react-map-gl/maplibre", async () => {
  const React = await import("react");
  const MockMap = React.forwardRef<unknown, { children?: ReactNode }>(
    function MockMap(props, ref) {
      mapMock.props = props as Record<string, unknown>;
      React.useImperativeHandle(ref, () => ({ fitBounds: mapMock.fitBounds }));
      return <div data-testid="mock-map">{props.children}</div>;
    },
  );
  return {
    default: MockMap,
    NavigationControl: () => null,
    Source: ({ children }: { children?: ReactNode }) => <>{children}</>,
    Layer: () => null,
  };
});

vi.mock("@/lib/api", () => ({
  fetchBuildings: async () => [
    makeBuilding({ id: "AG-000001", postcode: "5000" }),
    makeBuilding({ id: "AG-000002", postcode: "5000" }),
    makeBuilding({ id: "AG-000003", postcode: "5400" }),
  ],
}));

import { MapView } from "@/components/map/map-view";

type Handler = (event: unknown) => void;
const feature = (plz: string, count: number) => ({ properties: { plz, name: "x", gemeinde: "x", count } });
const resize = () =>
  (mapMock.props.onResize as Handler)({ target: { fitBounds: mapMock.fitBounds } });
const clickWith = (features: unknown[]) =>
  act(() => (mapMock.props.onClick as Handler)({ features, point: { x: 10, y: 10 } }));

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

describe("MapView", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
    mapMock.fitBounds.mockClear();
    clearPatchedStyleCache();
    // Offline by default: the map must keep working on the unpatched style URL.
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("falls back to the style URL when the recolouring fetch fails", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(STYLE_URL));
    expect(mapMock.props.mapStyle).toBe(STYLE_URL);
  });

  it("passes the patched style object once it has loaded", async () => {
    const style = {
      version: 8,
      sources: {},
      layers: [{ id: "background", type: "background", paint: { "background-color": "#ffffff" } }],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => style } as Response)),
    );
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.mapStyle).not.toBe(STYLE_URL));
    const patched = mapMock.props.mapStyle as { layers: { paint: Record<string, string> }[] };
    expect(patched.layers[0].paint["background-color"]).toBe(MAP.background);
  });

  it("renders the map and no tooltip initially", () => {
    renderWithProviders(<MapView />);
    expect(screen.getByTestId("mock-map")).toBeInTheDocument();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("selects a PLZ on click, toggles it off on a second click, clears on empty click", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onClick).toBeTypeOf("function"));
    await clickWith([feature("5000", 2)]);
    expect(useUIStore.getState().selectedPlz).toBe("5000");
    await clickWith([feature("5000", 2)]);
    expect(useUIStore.getState().selectedPlz).toBeNull();
    useUIStore.getState().selectPlz("5400");
    await clickWith([]);
    expect(useUIStore.getState().selectedPlz).toBeNull();
  });

  it("shows a tooltip with the building count while hovering a PLZ", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onMouseMove).toBeTypeOf("function"));
    await act(() => (mapMock.props.onMouseMove as Handler)({ features: [feature("5000", 2)], point: { x: 40, y: 50 } }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("5000 Aarau · 2 buildings");
    await act(() => (mapMock.props.onMouseLeave as () => void)());
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("fits the whole canton on the first resize and never again", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onResize).toBeTypeOf("function"));
    act(() => resize());
    expect(mapMock.fitBounds).toHaveBeenCalledWith(AARGAU_BBOX, { padding: 24, duration: 0 });
    act(() => resize());
    expect(mapMock.fitBounds).toHaveBeenCalledTimes(1);
  });

  it("leaves a highlighted area framed when the first resize arrives", async () => {
    useUIStore.getState().selectPlz("5400");
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onResize).toBeTypeOf("function"));
    mapMock.fitBounds.mockClear();
    act(() => resize());
    expect(mapMock.fitBounds).not.toHaveBeenCalled();
  });

  it("does not refit a resize arriving after the initial-fit latch has expired (timeout)", () => {
    vi.useFakeTimers();
    renderWithProviders(<MapView />);
    expect(mapMock.props.onResize).toBeTypeOf("function");
    act(() => vi.advanceTimersByTime(1500));
    act(() => resize());
    expect(mapMock.fitBounds).not.toHaveBeenCalled();
  });

  it("does not refit once a user-originated move has disarmed the latch", () => {
    renderWithProviders(<MapView />);
    expect(mapMock.props.onMoveStart).toBeTypeOf("function");
    act(() =>
      (mapMock.props.onMoveStart as Handler)({ originalEvent: new MouseEvent("mousedown") }),
    );
    act(() => resize());
    expect(mapMock.fitBounds).not.toHaveBeenCalled();
  });

  it("fits the map to the highlighted PLZ", async () => {
    renderWithProviders(<MapView />);
    await waitFor(() => expect(mapMock.props.onClick).toBeTypeOf("function"));
    act(() => useUIStore.getState().selectBuilding("AG-000003"));
    await waitFor(() => expect(mapMock.fitBounds).toHaveBeenCalledTimes(1));
    const [bbox, options] = mapMock.fitBounds.mock.calls[0];
    expect(bbox[0]).toBeLessThan(bbox[2]);
    expect(options).toMatchObject({ padding: 48, maxZoom: 13 });
  });
});
