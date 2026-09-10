#!/usr/bin/env node
/**
 * Copies MapLibre's worker bundles into `public/maplibre/` so the app can point
 * `setWorkerUrl()` at a stable, static URL. MapLibre 6 loads its worker via
 * `new URL("./maplibre-gl-worker.mjs", import.meta.url)`, which Turbopack
 * rewrites to an empty URL — the worker then never starts and the map stays
 * blank. Runs from `predev` and `prebuild`; the output is generated, not committed.
 */
import { copyFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const FILES = ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"];

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const sourceDir = join(frontendDir, "node_modules", "maplibre-gl", "dist");
const targetDir = join(frontendDir, "public", "maplibre");

await mkdir(targetDir, { recursive: true });
await Promise.all(FILES.map((file) => copyFile(join(sourceDir, file), join(targetDir, file))));

process.stdout.write(`copied ${FILES.length} MapLibre worker files to public/maplibre/\n`);
