"""
Project-side load normalization for the YCSB-cpp series frame.

This is the enrich hook handed to the generic plots engine (``adapter.enrich``)
and to :func:`.dataset.build_dataset`.  ``tools/run_all_workloads.py`` writes
one headerless CSV per (structure variant, workload, seed) whose rows carry the
run's *time* and *memory* measures merged in the same row, with the structure's
own metrics appended after them when the structure reports any (BTree/WTree do,
``std::map`` does not — hence the ragged schema).

Everything here is **project knowledge**: how a run is named (folder levels and
run-id suffixes) and which derived metrics the YCSB numbers imply.  The engine
owns the scan and every aggregation, never these maps.
"""

from __future__ import annotations

import operator
from functools import reduce

import polars as pl

#: Version recorded for a structure folder without a ``-version`` suffix.
DEFAULT_VERSION = "default"
#: Variant folder of a structure that has no node-size knob (std::map).
NO_NODE_SIZE = "default"
#: Node size reported for such a structure, so the variant axis stays numeric.
NO_NODE_BYTES = 0
#: Separator between the phase and the operation in a measure label.
MEASURE_SEP = ":"

#: Suffixes tools/run_all_workloads.py appends to a run id for the chosen
#: insert order / hash algorithm (see its --insert-orders / --hash-algos).
INSERT_ORDERS: tuple[str, ...] = ("ordered", "hashed")
HASH_ALGOS: tuple[str, ...] = ("fnv", "sha256")

#: Path keys every real series row has; rows without them (e.g. the schema
#: example CSV living next to the data) are dropped before any cast.
PATH_KEYS: tuple[str, ...] = ("struct_version", "node_size", "run_id", "seed")

#: Measurement columns cast to Int64 (counted, whole-byte values).
INT_METRICS: tuple[str, ...] = (
    "ops_count",
    "current_size",
    "maxrss_kb",
    "overhead",
    "height",
    "leaf_nodes",
    "internal_nodes",
)
#: Measurement columns cast to Float64.
FLOAT_METRICS: tuple[str, ...] = ("time_us",)

#: Row order of an enriched frame: structure variant, then the run identity, so
#: a matrix or an export lists the sweep in the order it was declared.
RUN_ORDER: tuple[str, ...] = (
    "struct_version",
    "target_node_bytes",
    "workload",
    "insert_order",
    "hash_algo",
    "seed",
    "measure",
)


def _ratio(num: pl.Expr, den: pl.Expr) -> pl.Expr:
    """``num / den``, null where *den* is missing or not positive (std reports none)."""
    return pl.when(den > 0).then(num / den)


def _strip_choices(source: pl.Expr, choices: tuple[str, ...]) -> pl.Expr:
    """*source* without one trailing ``-<choice>`` (the runner's run-id suffixes)."""
    return source.str.replace(rf"-({'|'.join(choices)})$", "")


def _suffix_value(source: pl.Expr, choices: tuple[str, ...], label: str) -> pl.Expr:
    """The trailing ``-<choice>`` token of *source*, else null."""
    expr = pl.lit(None, dtype=pl.Utf8)
    for choice in reversed(choices):
        expr = (
            pl.when(source.str.ends_with(f"-{choice}"))
            .then(pl.lit(choice))
            .otherwise(expr)
        )
    return expr.alias(label)


def _has_paths() -> pl.Expr:
    """Rows that came from a real series file (all path groups resolved)."""
    return reduce(operator.and_, (pl.col(key).is_not_null() for key in PATH_KEYS))


def _labels(df: pl.LazyFrame) -> pl.LazyFrame:
    """Split the folder/run-id names into dimensions and the measure label."""
    run_id = pl.col("run_id")
    without_hash = _strip_choices(run_id, HASH_ALGOS)
    return df.with_columns(
        # structure folder: "wtree-simple" → symbol "wtree", version "simple";
        # a bare "btree" → symbol "btree", version "default".
        pl.col("struct_version").str.split("-").list.first().alias("struct_symbol"),
        pl.when(pl.col("struct_version").str.contains("-"))
        .then(pl.col("struct_version").str.replace(r"^[^-]+-", ""))
        .otherwise(pl.lit(DEFAULT_VERSION))
        .alias("version"),
        # variant folder → numeric axis, with a structure without a knob at 0.
        pl.when(pl.col("node_size") == NO_NODE_SIZE)
        .then(pl.lit(NO_NODE_BYTES))
        .otherwise(pl.col("node_size").cast(pl.Int64))
        .alias("target_node_bytes"),
        # a measure is one (phase, operation) row: load:total, run:read, ...
        pl.concat_str(
            [pl.col("phase"), pl.col("operation")], separator=MEASURE_SEP
        ).alias("measure"),
        # run id → workload and its runner choices.
        _strip_choices(without_hash, INSERT_ORDERS).alias("workload"),
        _suffix_value(without_hash, INSERT_ORDERS, "insert_order"),
        _suffix_value(run_id, HASH_ALGOS, "hash_algo"),
        (pl.col("leaf_nodes") + pl.col("internal_nodes")).alias("node_count"),
    )


def _derived(df: pl.LazyFrame) -> pl.LazyFrame:
    """The metrics the views plot: per-key costs, throughput and footprint."""
    return df.with_columns(
        (pl.col("time_us") / 1000.0).alias("time_ms"),
        _ratio(pl.col("time_us"), pl.col("ops_count")).alias("us_per_op"),
        _ratio(pl.col("ops_count") * 1_000_000.0, pl.col("time_us")).alias(
            "ops_per_sec"
        ),
        _ratio(pl.col("overhead"), pl.col("current_size")).alias("overhead_per_key"),
        (pl.col("maxrss_kb") / 1024.0).alias("rss_mb"),
        # _ratio(pl.col("overhead"), pl.col("node_count")).alias("bytes_per_node"),
        # _ratio(pl.col("current_size"), pl.col("leaf_nodes")).alias("keys_per_leaf"),
    )


def enrich_series(frame: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
    """
    Normalize a scanned series frame into dimensions + measurements.

    Works on either an eager or a lazy frame and returns the same flavor, so the
    app keeps the single-pass lazy scan while a test or the headless CLI can
    hand in a frame.  Four passes over the (still lazy) plan: drop rows that
    carry no path metadata, cast the ragged strings, then derive the project
    dimensions and metrics, and finally order the rows by run identity so a
    matrix, a curve or an export comes out in a natural, reproducible order.
    """
    lazy = frame.lazy() if isinstance(frame, pl.DataFrame) else frame
    out = (
        lazy.filter(_has_paths())
        .with_columns(
            pl.col("seed").cast(pl.Int64),
            *[pl.col(name).cast(pl.Int64) for name in INT_METRICS],
            *[pl.col(name).cast(pl.Float64) for name in FLOAT_METRICS],
        )
        .pipe(_labels)
        .pipe(_derived)
        .sort(*RUN_ORDER)
    )
    return out if isinstance(frame, pl.LazyFrame) else out.collect()


__all__ = [
    "DEFAULT_VERSION",
    "FLOAT_METRICS",
    "HASH_ALGOS",
    "INSERT_ORDERS",
    "INT_METRICS",
    "MEASURE_SEP",
    "NO_NODE_BYTES",
    "NO_NODE_SIZE",
    "PATH_KEYS",
    "enrich_series",
]
