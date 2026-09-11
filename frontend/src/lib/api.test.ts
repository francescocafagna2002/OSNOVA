import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBuildings } from "@/lib/api";
import { generateMockBuildings } from "@/lib/mock-data";
import { makeBuilding } from "@/test/fixtures";

describe("fetchBuildings", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the backend file when /data/buildings.json is served", async () => {
    const fixture = makeBuilding();
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => [fixture] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchBuildings()).resolves.toEqual([fixture]);
    expect(fetchMock).toHaveBeenCalledWith("/data/buildings.json", expect.objectContaining({ cache: "no-store" }));
  });

  it("falls back to mock buildings when the fetch throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("offline");
      }),
    );

    await expect(fetchBuildings()).resolves.toEqual(generateMockBuildings());
  });

  it("falls back to mock buildings on a non-OK response", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 404 })));

    await expect(fetchBuildings()).resolves.toEqual(generateMockBuildings());
  });
});
