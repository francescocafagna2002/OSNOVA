# OSNOVA Backend

Python data processing for the **Energy Fingerprints** challenge — reading the
AEW smart-meter mounts and turning them into features, labels, and model output.

## Requirements

Python 3.10+. Dependencies are declared in [`pyproject.toml`](pyproject.toml)
(`polars`, `pandas`); `scripts/preview_data.py` itself uses only the standard
library, so it runs in a bare Renku session with no install step.

## Layout

```
backend/
  pyproject.toml       # project metadata and dependencies
  scripts/
    preview_data.py    # print header + first ten records of each CSV in a mount
  tests/
    test_preview_data.py
```

## Preview the data mount

Run from this directory — `scripts` is imported as a top-level package, so the
working directory has to be `backend/`:

```sh
python3 scripts/preview_data.py
```

It searches the current directory and its parents for an `aew-data` /
`aew_data` mount (including under `data/`), then recursively previews every
`.csv` and `.csv.gz`. Pass an explicit path if the mount lives elsewhere:

```sh
python3 scripts/preview_data.py /actual/path/to/aew-data
```

Keep previews in the Renku console. Never commit real customer records or
credentials, and write processing output to the organizer-provided `store`
mount rather than the read-only input mount.

## Tests

Synthetic-data tests, standard library only:

```sh
python3 -m unittest discover -s tests
```
