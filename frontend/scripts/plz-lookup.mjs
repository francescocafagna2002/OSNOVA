// Build a one-row-per-ZIP_ID lookup for one canton from the swisstopo AMTOVZ CSV.
// Usage: node plz-lookup.mjs <AMTOVZ_CSV_WGS84.csv> <out.csv> [canton=AG]
import { readFileSync, writeFileSync } from "node:fs";

const [, , input, output, canton = "AG"] = process.argv;
const text = readFileSync(input, "utf8").replace(/^﻿/, "");
const [header, ...rows] = text.trim().split(/\r?\n/);
const cols = header.split(";");
const col = (name) => {
  const i = cols.indexOf(name);
  if (i < 0) throw new Error(`missing column ${name}`);
  return i;
};
const iZip = col("ZIP_ID"), iPlz = col("PLZ4"), iName = col("Ortschaftsname"), iGem = col("Gemeindename"), iKt = col("Kantonskürzel"), iShare = col("Adressenanteil"), iE = col("E"), iN = col("N");

// Primary row per ZIP_ID = the Gemeinde holding the largest address share (any canton),
// so a ZIP that only brushes the canton border is attributed to its real canton.
const best = new Map();
for (const line of rows) {
  const f = line.split(";");
  const share = parseFloat(f[iShare]);
  const rec = { zipId: f[iZip], plz: f[iPlz], name: f[iName], gemeinde: f[iGem], canton: f[iKt], share, lng: f[iE], lat: f[iN] };
  const prev = best.get(rec.zipId);
  if (!prev || share > prev.share) best.set(rec.zipId, rec);
}
const q = (s) => `"${String(s).replaceAll('"', '""')}"`;
const kept = [...best.values()].filter((r) => r.canton === canton);
const lines = ["ZIP_ID,plz,name,gemeinde,lng,lat", ...kept.map((r) => [r.zipId, r.plz, q(r.name), q(r.gemeinde), r.lng, r.lat].join(","))];
writeFileSync(output, lines.join("\n") + "\n");
console.log(`${kept.length} ZIP_IDs for canton ${canton}`);
