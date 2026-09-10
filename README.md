# OSNOVA

A project for AEW's **Energy Fingerprints** challenge at **Energy Data Hackdays 2026**.

## Challenge

One smart meter records a household's aggregated electricity signal, but many devices contribute to it. The goal is to identify electric vehicles (EVs), heat pumps, rooftop photovoltaic (PV) systems, batteries, and other distinctive devices from anonymized 15-minute measurements.

The challenge focuses on three questions:

1. **Asset presence:** Which assets does a household have?
2. **Activity windows:** When are those assets charging, producing electricity, heating, cycling, or discharging?
3. **Change over time:** How do their fingerprints vary across seasons, locations, new installations, and multiple years?

A useful result should show not only a prediction, but also the evidence behind it.

## Data

### Input Data

The challenge provides:

- **Smart-meter measurements:** four years of 15-minute data for **90,000 anonymized customers**.
- **Location metadata:** customer postal codes.
- **Asset labels:** known assets for around **1,000 customers**, provided in Excel.

The measurements represent net household load, so device consumption and local generation can overlap in the same signal. Optional enrichment sources include open data such as **MeteoSwiss weather data**.

Challenge datasets are not included in this repository.

### Planned Outputs

- Per-customer probabilities for the presence of each asset type.
- Estimated activity windows for detected assets.
- Inspectable evidence, such as repeated charging plateaus, temperature-dependent consumption, or recurring sunny-midday reductions in net load.
- Summaries of seasonal patterns and changes over time, including potential new installations.

Output formats and storage locations will be documented alongside the implementation.

## Proposed Approach

The challenge outlines two starting points:

1. **Device-driven pattern matching:** research published device profiles, turn characteristics such as power, duration, plateau shape, and start/stop behavior into templates, and search household time series for repeated matches.
2. **Label-driven learning:** use the labeled customers to compare households with and without an asset, identify distinguishing features, and train a classifier.

Weather data can provide additional context for heating demand and solar-related patterns.

## Success Criteria

- **Accurate:** reliable asset probabilities and activity windows.
- **Robust:** handles seasonal and location differences, missing data, and overlapping loads.
- **Explainable:** provides inspectable evidence rather than only a label.
- **Scalable:** works across multi-year data and large customer populations.
- **Innovative:** explores useful combinations of signal processing and machine learning.

## Getting Started

### Preview data in Renku

From the repository directory in the Renku session, run:

```sh
python3 scripts/preview_data.py
```

The script looks for the nearby `aew-data` or `aew_data` mount, including under
`data/`, and recursively prints each CSV's filename, header, and first ten data
records. It supports `.csv` and `.csv.gz`, uses only the Python standard library,
and reads a small prefix rather than loading whole files. It does not change any
files or require the SAS URL in code. Excel and other non-CSV files are skipped.

If the mount is elsewhere, pass its actual path (or the path to one CSV):

```sh
python3 scripts/preview_data.py /actual/path/to/aew-data
```

Keep data previews in the Renku console; do not commit real customer records or
credentials. Save future processing outputs in the organizer-provided `store`
mount, not the read-only input mount.

Run the synthetic-data tests locally with `python3 -m unittest discover -s tests`.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the contributor code of conduct and contribution terms.

## Group Members

| Name | GitHub |
| --- | --- |
| Danylo Serhieiev | [@happybald](https://github.com/happybald) |
| Jenia | [@j-isler](https://github.com/j-isler) |
| StevenDok. | [@SteveDok22](https://github.com/SteveDok22) |
| pablittto | [@PahanLL](https://github.com/PahanLL) |
| Yuniia S | [@yunuasharovenko-boop](https://github.com/yunuasharovenko-boop) |
| BigBoyJohnny | [@TsNikolay](https://github.com/TsNikolay) |

## License

This project is licensed under the Apache License 2.0 — see [LICENSE.md](LICENSE.md) for details.
