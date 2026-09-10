# Data check 2026-09-10 (Renku, commit a6dc73e)

Measured by `osnova check-data --max-files 3` and `osnova weather` on the real mounts. No customer
records are in this file, only file names, column names and counts. Laptop sessions work from these facts.

## Facts the pipeline depends on

| question | answer | consequence |
| --- | --- | --- |
| Where is Table 1 | `/home/renku/work/store/cleaned_data/<year>/<German month> <year>/LG_AIM2Hackerdays_kWh_<export stamp>.csv`, 43 monthly files, 2023-01 to 2026-07 | `OSNOVA_DATA_DIR=/home/renku/work/store/cleaned_data`; year comes from the folder, the stamp in the name is the export date |
| Where are Tables 2-4 | `/home/renku/work/aew-data/test-blob/input_data/`: `HackDays2026 - GIGI.csv` (Table 2, `;`-separated CSV, not xlsx), `mpid_zähler_mapping.csv` (Table 3), `Zähler-GP.csv` (Table 4) | `OSNOVA_REGISTRY_DIR=/home/renku/work/aew-data/test-blob/input_data` |
| Table 1 header | `MP ID;OBIS-Code;Datum;PLZ;00:15;…;00:00;` (96 slot columns, trailing `;` = one empty column) | as assumed; `truncate_ragged_lines` handles the trailing separator |
| OBIS codes | `1-1:1.29.0*255` (import) and `1-1:2.29.0*255` (export), **equal row counts** (2,797,223 each in the sample) | every meter has an export row. `export_present` is not a PV feature; use export energy > 0 |
| Units | kWh per 15 min (median daily import sum 7.2 kWh, p10 1.2, p90 211; file name says `kWh`) | `ingest.unit_factor = 4.0` stays. No `config.renku.json` needed for units |
| Datum format | `dd.mm.yyyy` | as assumed |
| Rows per file | 1.31 M (April 2023, only 23 days: 01–23), 1.96 M (Aug 2023), 2.32 M (Dec 2023) | ≈ 28k → 37k meters per day across 2023: the meter population grows month by month. **April 2023 is incomplete.** |
| File size / time | ≈ 1.5 GB per file; check-data took 164 s for 3 files at a6dc73e (now single-pass) | ingest must stream (`sink_parquet`), never collect a file |
| DST cells | second run (f2682e6): on the four spring-forward days 2023-03-26, 2024-03-31, 2025-03-30, 2026-03-29 the cells `02:15, 02:30, 02:45, 03:00` are empty in ≈ 16.8k rows each (67,134 empty cells in total; per-slot counts differ by a few, so a handful of empty cells occur elsewhere too) | ingest marks those four cells on that day `quality = "dst"` and drops them; empty cells → null, never 0 |
| Join keys | second run: Table 2 `GP-Nr` has 25 nulls, lengths 5–15, not all digits, one value with inner whitespace; Table 4 `GPartner` is always 6 digits (76,718 unique GPs for 89,910 rows; 136 Zählpunkte carry two GPs). Normalising `.0`/leading zeros changed nothing | Table 2 cells do not always hold one clean 6-digit number. Third run adds a length histogram and a join on every 6-digit run extracted from the cell |
| PLZ in Table 1 | column present; 80 PLZ in the sampled files, all have weather | join lastgang → weather on PLZ works |
| Table 2 columns | `GP-Nr, PLZ, Ort, Kanton, WärmePumpe, " PV", "PV-Leistung in kWp ", Batterie/Speicher, Ladestation für Elektrofahrzeuge, Wärmepumpenboiler, Datum Unterschrift, geplanter Baustart, Übergabe, InBetrieb-Datum` | leading/trailing spaces in names, EV column is `Ladestation für Elektrofahrzeuge` (synth had `… für EV`): strip and match by substring |
| Table 2 size | 1,192 rows, 878 unique GP-Nr | several rows per customer (projects); registry stage must aggregate per GP |
| Asset flags (rows) | WärmePumpe 334, PV 755, Batterie/Speicher 713, Ladestation 192, Wärmepumpenboiler 10 | battery is unexpectedly common: check the flag values in the registry stage (`ja`/`nein`/other) |
| Join 3 → 4 → 2 | Table 3: 89,993 meters. Table 4: 89,910 rows. **Only 413 meters join to 337 of 878 GPs; 541 GPs have no meter.** | 62 % join loss. Cause unknown: key format (`.0`, leading zeros) or customers outside the meter population. The new `keys` and `joined_with_normalized_keys` sections of the report answer this on the next run |
| Meters per GP | 1: 291, 2: 35, 3: 9, 8: 1, 17: 1 | as designed: one meter = one entity, `meters_per_gp` recorded |
| Weather | 120 PLZ × 45 months (2023-01-01 00:00 → 2026-09-04 23:00 UTC), no hour gaps, no duplicates, both parts complete | `weather` stage wrote 120 parquet files, 32,229 local hours each (32,232 minus 3 fall-back duplicates). Verified on `plz=5000`: unique sorted local hours, 23 h on 2024-03-31, 24 h on 2024-10-27, summer radiation peaks at 13:00 local |

## Raw report

# data check

## data_dir

```json
"/tmp/osnova-check-ym4rd9gm"
```

## config

```json
{
  "import_obis": "1-1:1.29.0*255",
  "export_obis": "1-1:2.29.0*255",
  "unit_factor": 4.0,
  "csv_separator": ";",
  "date_format": "%d.%m.%Y"
}
```

## files

```json
{
  "count": 43,
  "per_year": {
    "2023": [
      "LG_AIM2Hackerdays_kWh_20260826_201441.csv",
      "LG_AIM2Hackerdays_kWh_20260828_151916.csv",
      "LG_AIM2Hackerdays_kWh_20260830_205227.csv",
      "LG_AIM2Hackerdays_kWh_20260825_152222.csv",
      "LG_AIM2Hackerdays_kWh_20260825_131305.csv",
      "LG_AIM2Hackerdays_kWh_20260828_124337.csv",
      "LG_AIM2Hackerdays_kWh_20260827_211912.csv",
      "LG_AIM2Hackerdays_kWh_20260827_144609.csv",
      "LG_AIM2Hackerdays_kWh_20260827_084034.csv",
      "LG_AIM2Hackerdays_kWh_20260830_162012.csv",
      "LG_AIM2Hackerdays_kWh_20260830_112533.csv",
      "LG_AIM2Hackerdays_kWh_20260829_055849.csv"
    ],
    "2024": [
      "LG_AIM2Hackerdays_kWh_20260812_070837.csv",
      "LG_AIM2Hackerdays_kWh_20260814_133937.csv",
      "LG_AIM2Hackerdays_kWh_20260822_063349.csv",
      "LG_AIM2Hackerdays_kWh_20260811_062000.csv",
      "LG_AIM2Hackerdays_kWh_20260807_062250.csv",
      "LG_AIM2Hackerdays_kWh_20260814_064940.csv",
      "LG_AIM2Hackerdays_kWh_20260813_095327.csv",
      "LG_AIM2Hackerdays_kWh_20260812_124247.csv",
      "LG_AIM2Hackerdays_kWh_20260811_114208.csv",
      "LG_AIM2Hackerdays_kWh_20260821_060854.csv",
      "LG_AIM2Hackerdays_kWh_20260820_084220.csv",
      "LG_AIM2Hackerdays_kWh_20260819_124455.csv"
    ],
    "2025": [
      "LG_AIM2Hackerdays_kWh_20260730_181422.csv",
      "LG_AIM2Hackerdays_kWh_20260801_174011.csv",
      "LG_AIM2Hackerdays_kWh_20260805_065742.csv",
      "LG_AIM2Hackerdays_kWh_20260730_061341.csv",
      "LG_AIM2Hackerdays_kWh_20260729_151030.csv",
      "LG_AIM2Hackerdays_kWh_20260801_063453.csv",
      "LG_AIM2Hackerdays_kWh_20260731_133938.csv",
      "LG_AIM2Hackerdays_kWh_20260731_065533.csv",
      "LG_AIM2Hackerdays_kWh_20260730_141924.csv",
      "LG_AIM2Hackerdays_kWh_20260804_115542.csv",
      "LG_AIM2Hackerdays_kWh_20260802_162640.csv",
      "LG_AIM2Hackerdays_kWh_20260802_085319.csv"
    ],
    "2026": [
      "LG_AIM2Hackerdays_kWh_20260728_140238.csv",
      "LG_AIM2Hackerdays_kWh_20260727_130937.csv",
      "LG_AIM2Hackerdays_kWh_20260727_065429.csv",
      "LG_AIM2Hackerdays_kWh_20260824_102023.csv",
      "LG_AIM2Hackerdays_kWh_20260729_062053.csv",
      "LG_AIM2Hackerdays_kWh_20260728_195653.csv",
      "LG_AIM2Hackerdays_kWh_20260728_063802.csv"
    ]
  },
  "sampled": [
    {
      "file": "/tmp/osnova-check-ym4rd9gm/consumption/2023/April 2023/LG_AIM2Hackerdays_kWh_20260826_201441.csv",
      "rows": 1313346,
      "n_slot_columns": 96,
      "non_slot_columns": [
        "MP ID",
        "OBIS-Code",
        "Datum",
        "PLZ",
        ""
      ],
      "date_min": "2023-04-01",
      "date_max": "2023-04-23"
    },
    {
      "file": "/tmp/osnova-check-ym4rd9gm/consumption/2023/August 2023/LG_AIM2Hackerdays_kWh_20260828_151916.csv",
      "rows": 1963044,
      "n_slot_columns": 96,
      "non_slot_columns": [
        "MP ID",
        "OBIS-Code",
        "Datum",
        "PLZ",
        ""
      ],
      "date_min": "2023-08-01",
      "date_max": "2023-08-31"
    },
    {
      "file": "/tmp/osnova-check-ym4rd9gm/consumption/2023/Dezember 2023/LG_AIM2Hackerdays_kWh_20260830_205227.csv",
      "rows": 2318056,
      "n_slot_columns": 96,
      "non_slot_columns": [
        "MP ID",
        "OBIS-Code",
        "Datum",
        "PLZ",
        ""
      ],
      "date_min": "2023-12-01",
      "date_max": "2023-12-31"
    }
  ]
}
```

## obis_counts

```json
{
  "1-1:1.29.0*255": 2797223,
  "1-1:2.29.0*255": 2797223
}
```

## unit_guess

```json
"kwh_per_15min"
```

## daily_sum_median

```json
7.205500000000001
```

## daily_sum_quantiles

```json
{
  "0.1": 1.2360000000000002,
  "0.5": 7.206,
  "0.9": 210.828
}
```

## daily_sum_rows

```json
6000
```

## dst_null_cells

```json
{
  "02:15": 0,
  "02:30": 0,
  "02:45": 0,
  "03:00": 0,
  "total": 0,
  "days_checked": [],
  "files_checked": []
}
```

## registry

```json
{
  "files": {
    "table2": "/tmp/osnova-check-ym4rd9gm/HackDays2026 - GIGI.csv",
    "table4": "/tmp/osnova-check-ym4rd9gm/Zähler-GP.csv",
    "table3": "/tmp/osnova-check-ym4rd9gm/mpid_zähler_mapping.csv"
  },
  "columns": {
    "table2": [
      "GP-Nr",
      "PLZ",
      "Ort",
      "Kanton",
      "WärmePumpe",
      " PV",
      "PV-Leistung in kWp ",
      "Batterie/Speicher",
      "Ladestation für Elektrofahrzeuge",
      "Wärmepumpenboiler",
      "Datum Unterschrift",
      "geplanter Baustart",
      "Übergabe",
      "InBetrieb-Datum"
    ],
    "table4": [
      "Zählpunktbezeichnung",
      "GPartner",
      "Anlage"
    ],
    "table3": [
      "MP ID",
      "Zählpunktbezeichnung"
    ]
  },
  "n_rows_table2": 1192,
  "n_rows_table4": 89910,
  "n_rows_table3": 89993,
  "n_gp": 878,
  "n_meters_table3": 89993,
  "n_meters_joined": 413,
  "n_gp_with_meter": 337,
  "n_gp_without_meter": 541,
  "meters_per_gp_hist": {
    "1": 291,
    "2": 35,
    "3": 9,
    "8": 1,
    "17": 1
  },
  "asset_counts": {
    "WärmePumpe": 334,
    " PV": 755,
    "Batterie/Speicher": 713,
    "Ladestation für Elektrofahrzeuge": 192,
    "Wärmepumpenboiler": 10,
    "geplanter Baustart": 2,
    "Übergabe": 8
  }
}
```

## weather

```json
{
  "dir": "/home/renku/work/store",
  "n_files": 5400,
  "columns": [
    "PLZ",
    "timestamp_utc",
    "temperature_2m",
    "cloud_cover",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "sunshine_duration",
    "relative_humidity_2m",
    "precipitation",
    "snowfall",
    "wind_speed_10m"
  ],
  "parts": {
    "weather_part_1": {
      "success_marker": true,
      "metadata": true,
      "n_plz_dirs": 60
    },
    "weather_part_2": {
      "success_marker": true,
      "metadata": true,
      "n_plz_dirs": 60
    }
  },
  "files_sample": [
    "weather_part_1/hourly/4302/2023-01.csv.gz",
    "weather_part_1/hourly/4302/2023-02.csv.gz",
    "weather_part_1/hourly/4302/2023-03.csv.gz"
  ],
  "rows_first_file": 744,
  "time_column": "timestamp_utc",
  "time_zone_hint": "utc",
  "continuity_plz": "4302",
  "continuity_files": 45,
  "time_min": "2023-01-01 00:00:00",
  "time_max": "2026-09-04 23:00:00",
  "hour_gaps": 0,
  "duplicate_hours": 0,
  "n_plz": 120,
  "files_per_plz_min": 45,
  "files_per_plz_max": 45,
  "plz_fewest_files": [
    "4302",
    "4303",
    "4304",
    "4310",
    "4312",
    "4313",
    "4314",
    "4315",
    "4316",
    "4317"
  ],
  "plz_in_table1": [
    "4302",
    "4303",
    "4310",
    "4313",
    "4322",
    "4325",
    "4333",
    "4468",
    "4469",
    "4665",
    "4805",
    "5000",
    "5001",
    "5044",
    "5046",
    "5054",
    "5070",
    "5072",
    "5074",
    "5075",
    "5076",
    "5078",
    "5105",
    "5106",
    "5112",
    "5113",
    "5225",
    "5235",
    "5237",
    "5244",
    "5272",
    "5304",
    "5305",
    "5313",
    "5316",
    "5324",
    "5330",
    "5332",
    "5334",
    "5425",
    "5426",
    "5443",
    "5452",
    "5454",
    "5462",
    "5464",
    "5467",
    "5504",
    "5505",
    "5506",
    "5507",
    "5522",
    "5600",
    "5604",
    "5605",
    "5607",
    "5608",
    "5615",
    "5617",
    "5618",
    "5619",
    "5620",
    "5622",
    "5623",
    "5625",
    "5630",
    "5706",
    "5707",
    "5726",
    "5727",
    "5728",
    "5733",
    "5735",
    "5736",
    "5737",
    "5745",
    "8953",
    "8962",
    "8964",
    "8967"
  ],
  "plz_with_weather": [
    "4302",
    "4303",
    "4304",
    "4310",
    "4312",
    "4313",
    "4314",
    "4315",
    "4316",
    "4317",
    "4322",
    "4323",
    "4324",
    "4325",
    "4332",
    "4333",
    "4334",
    "4422",
    "4468",
    "4469",
    "4665",
    "4805",
    "4813",
    "4814",
    "5000",
    "5001",
    "5026",
    "5027",
    "5028",
    "5044",
    "5046",
    "5054",
    "5070",
    "5072",
    "5073",
    "5074",
    "5075",
    "5076",
    "5077",
    "5078",
    "5079",
    "5105",
    "5106",
    "5107",
    "5108",
    "5112",
    "5113",
    "5213",
    "5223",
    "5225",
    "5235",
    "5236",
    "5237",
    "5244",
    "5272",
    "5301",
    "5304",
    "5305",
    "5306",
    "5312",
    "5313",
    "5314",
    "5315",
    "5316",
    "5322",
    "5324",
    "5325",
    "5330",
    "5332",
    "5334",
    "5425",
    "5426",
    "5443",
    "5445",
    "5452",
    "5454",
    "5462",
    "5464",
    "5467",
    "5504",
    "5505",
    "5506",
    "5507",
    "5522",
    "5600",
    "5604",
    "5605",
    "5607",
    "5608",
    "5614",
    "5615",
    "5616",
    "5617",
    "5618",
    "5619",
    "5620",
    "5621",
    "5622",
    "5623",
    "5625",
    "5630",
    "5643",
    "5705",
    "5706",
    "5707",
    "5724",
    "5725",
    "5726",
    "5727",
    "5728",
    "5733",
    "5735",
    "5736",
    "5737",
    "5745",
    "8918",
    "8953",
    "8962",
    "8964",
    "8967"
  ],
  "plz_missing": []
}
```


## weather stage

```text
plz=4302: 45 files -> 32229 hourly rows
plz=4303: 45 files -> 32229 hourly rows
plz=4304: 45 files -> 32229 hourly rows
...
plz=8967: 45 files -> 32229 hourly rows
wrote 120 PLZ to /home/renku/work/store/checkup_cleaned_20260910_232011_173889/osnova/weather
```
