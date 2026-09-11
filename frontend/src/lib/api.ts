import { generateMockBuildings } from "@/lib/mock-data";
import type { Building } from "@/lib/types";

const MOCK_LATENCY_MS = 150;
/** Backend export copied to frontend/public/data/ (gitignored); absent = mock data. */
const DATA_URL = "/data/buildings.json";

/**
 * The only place that knows where buildings come from: the backend's buildings.json
 * when it is served, otherwise the deterministic mock set.
 */
export async function fetchBuildings(): Promise<Building[]> {
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (res.ok) return (await res.json()) as Building[];
  } catch {
    /* fall through to mocks */
  }
  await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));
  return generateMockBuildings();
}
