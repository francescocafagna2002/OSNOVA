import { describe, expect, it } from "vitest";

import { createRng } from "@/lib/random";

describe("createRng", () => {
  it("is deterministic for a seed and uniform in [0, 1)", () => {
    const a = createRng(42);
    const b = createRng(42);
    const seqA = Array.from({ length: 5 }, () => a.next());
    const seqB = Array.from({ length: 5 }, () => b.next());
    expect(seqA).toEqual(seqB);
    for (const v of seqA) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it("int is inclusive on both ends and pick returns members", () => {
    const rng = createRng(7);
    const values = new Set(Array.from({ length: 200 }, () => rng.int(1, 3)));
    expect([...values].sort()).toEqual([1, 2, 3]);
    expect(["a", "b"]).toContain(rng.pick(["a", "b"]));
  });
});
