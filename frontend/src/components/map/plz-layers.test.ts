import { describe, expect, it } from "vitest";

import { plzFilter } from "@/components/map/plz-layers";

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
