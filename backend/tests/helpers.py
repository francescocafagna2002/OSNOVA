# tests/helpers.py
"""Shared helpers for tests on synthetic data."""

from __future__ import annotations


def pick(truth: dict, *, always_active: bool = True, **assets: bool) -> int:
    """First synth meter whose truth flags match `assets` (e.g. ev=True, pv=False).

    always_active=True prefers meters without a commissioning date, so injected assets
    are present over the whole series.
    """
    matches = []
    for mid, t in truth["meters"].items():
        if all(bool(t[k]) == v for k, v in assets.items()):
            matches.append((t["commissioned_on"] is not None, int(mid)))
    if not matches:
        raise LookupError(f"no synth meter with {assets}")
    matches.sort()
    if always_active and matches[0][0]:
        raise LookupError(f"no always-active synth meter with {assets}")
    return matches[0][1]
