import { generateMockBuildings } from "@/lib/mock-data";
import type { Building } from "@/lib/types";

const MOCK_LATENCY_MS = 150;

/**
 * The only place that knows where buildings come from. Replace the body with a
 * real fetch when the backend exists; nothing else changes.
 */
export async function fetchBuildings(): Promise<Building[]> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));
  return generateMockBuildings();
}
