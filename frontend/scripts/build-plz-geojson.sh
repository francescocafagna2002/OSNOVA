#!/usr/bin/env bash
# Rebuilds src/data/aargau-plz.json from swisstopo's open "Amtliches Ortschaftenverzeichnis"
# (PLZ polygons). Only needed when swisstopo publishes a new release; the output is committed.
#
# Requires: curl, unzip, node >= 18, network. mapshaper is fetched via npx.
# Usage (from frontend/): bash scripts/build-plz-geojson.sh [canton=AG]
set -euo pipefail

CANTON="${1:-AG}"
BASE="https://data.geo.admin.ch/ch.swisstopo-vd.ortschaftenverzeichnis_plz/ortschaftenverzeichnis_plz"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../src/data/aargau-plz.json"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -sSL -o "$TMP/shp.zip" "$BASE/ortschaftenverzeichnis_plz_2056.shp.zip"   # ~38 MB
curl -sSL -o "$TMP/csv.zip" "$BASE/ortschaftenverzeichnis_plz_4326.csv.zip"   # <1 MB
unzip -q "$TMP/shp.zip" -d "$TMP/shp"
unzip -q "$TMP/csv.zip" -d "$TMP/csv"

node "$HERE/plz-lookup.mjs" "$TMP/csv/AMTOVZ_CSV_WGS84/AMTOVZ_CSV_WGS84.csv" "$TMP/lookup.csv" "$CANTON"

npx -y mapshaper@0.7.61 "$TMP/shp/AMTOVZ_SHP_LV95/AMTOVZ_ZIP.shp" \
  -join "$TMP/lookup.csv" keys=ZIP_ID,ZIP_ID string-fields=ZIP_ID,plz fields=plz,name,gemeinde \
  -filter 'plz != null' \
  -dissolve plz copy-fields=name,gemeinde \
  -proj wgs84 \
  -simplify 8% keep-shapes \
  -o precision=0.0001 format=geojson id-field=plz "$OUT"

echo "wrote $OUT"
