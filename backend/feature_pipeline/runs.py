"""Continuous-block ("run") detection over an ordered building timeline.

Used for near-zero blocks, the four EV high-load thresholds and EV sessions.
A run never bridges a missing-timestamp gap: consecutive quarter-hours must be
exactly ``interval_minutes`` apart or a new run starts, per the brief
("не объединять блоки через missing timestamp gaps").

Requires the frame to already be sorted by ``(gp_nr, ts)``.
"""

from __future__ import annotations

import polars as pl


def add_run_columns(
    lf: pl.LazyFrame,
    cond_col: str,
    prefix: str,
    interval_minutes: int,
    group_col: str = "gp_nr",
    ts_col: str = "ts",
) -> pl.LazyFrame:
    """Add ``{prefix}_run_id`` and ``{prefix}_run_len`` columns.

    ``{prefix}_run_id`` is unique only within a group (paired with
    ``group_col`` it identifies one continuous block); ``{prefix}_run_len`` is
    the number of quarter-hours in that block, broadcast to every row of it so
    a later aggregation can filter "block starts of length >= N" without a
    second pass.
    """
    is_first = pl.int_range(pl.len()).over(group_col) == 0
    gap_ok = (pl.col(ts_col).diff().over(group_col) == pl.duration(minutes=interval_minutes)).fill_null(False)
    same_as_prev = (pl.col(cond_col) == pl.col(cond_col).shift(1).over(group_col)).fill_null(False)

    run_break = is_first | (~gap_ok) | (~same_as_prev)
    run_id_col = f"{prefix}_run_id"
    run_len_col = f"{prefix}_run_len"
    run_start_col = f"{prefix}_run_start"

    lf = lf.with_columns(run_break.alias(run_start_col))
    lf = lf.with_columns(pl.col(run_start_col).cum_sum().over(group_col).alias(run_id_col))
    lf = lf.with_columns(pl.len().over([group_col, run_id_col]).alias(run_len_col))
    return lf


def block_start_flag(prefix: str, cond_col: str, min_intervals: int) -> pl.Expr:
    """A row-level boolean: True exactly at the first quarter-hour of a

    qualifying (``cond_col`` true, long enough) block. Summing this per
    building over the whole timeline gives the block *count*.
    """
    return pl.col(cond_col) & pl.col(f"{prefix}_run_start") & (pl.col(f"{prefix}_run_len") >= min_intervals)
