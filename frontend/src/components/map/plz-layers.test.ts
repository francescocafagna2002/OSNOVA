import { describe, expect, it } from "vitest";

import { plzFilter, plzHoverFilter } from "@/components/map/plz-layers";

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
