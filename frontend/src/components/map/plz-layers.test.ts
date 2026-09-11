import { describe, expect, it } from "vitest";

import { plzFillOpacity, plzFilter, plzHoverFilter } from "@/components/map/plz-layers";

describe("plzFilter", () => {
  it("matches exactly one PLZ", () => {
    expect(plzFilter("5000")).toEqual(["==", ["get", "plz"], "5000"]);
  });

  it("matches nothing for null", () => {
    const [, , sentinel] = plzFilter(null);
    expect(typeof sentinel).toBe("string");
    expect(sentinel).not.toMatch(/^\d{4}$/);
  });
});

describe("plzHoverFilter", () => {
  it("tints a hovered zone that is not highlighted", () => {
    expect(plzHoverFilter("5000", "5400")).toEqual(plzFilter("5000"));
    expect(plzHoverFilter("5000", null)).toEqual(plzFilter("5000"));
  });

  it("matches nothing when the hovered zone is the highlighted one", () => {
    expect(plzHoverFilter("5000", "5000")).toEqual(plzFilter(null));
  });

  it("matches nothing when nothing is hovered, highlight or not", () => {
    expect(plzHoverFilter(null, "5000")).toEqual(plzFilter(null));
    expect(plzHoverFilter(null, null)).toEqual(plzFilter(null));
  });
});

describe("plzFillOpacity", () => {
  it("keeps the resting opacity everywhere when nothing is hovered or highlighted", () => {
    expect(plzFillOpacity(null, null)).toBe(0.5);
  });

  it("fades the hovered and the highlighted zone, and nothing else", () => {
    expect(plzFillOpacity("5000", "5400")).toEqual(["match", ["get", "plz"], ["5000", "5400"], 0.3, 0.5]);
    expect(plzFillOpacity(null, "5400")).toEqual(["match", ["get", "plz"], ["5400"], 0.3, 0.5]);
  });

  it("lists a zone once when it is both hovered and highlighted", () => {
    expect(plzFillOpacity("5000", "5000")).toEqual(["match", ["get", "plz"], ["5000"], 0.3, 0.5]);
  });
});
