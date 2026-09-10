import type { Building } from "@/lib/types";

/** Lowercase, strip combining diacritics, collapse whitespace. */
export function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** Every whitespace-separated token must appear in "id postcode city". Empty query → input unchanged. */
export function filterBuildings(buildings: Building[], query: string): Building[] {
  const tokens = normalizeText(query).split(" ").filter(Boolean);
  if (tokens.length === 0) return buildings;
  return buildings.filter((building) => {
    const haystack = normalizeText(`${building.id} ${building.postcode} ${building.city}`);
    return tokens.every((token) => haystack.includes(token));
  });
}
