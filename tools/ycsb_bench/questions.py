"""
Headless questions over a result tree of the run phase.

The same scan, schema, normalization and engine queries the plot viewer uses,
answered in the terminal.  The question the sweep exists to answer is *what did
each workload cost, per operation type*: the aggregation the first tab draws as
heatmaps — the mean over the repeated seeds — for the metrics of interest
(:data:`QUESTION_METRICS`).

Every table has one row per workload × operation type × structure variant ×
target node size, the value being the mean over seeds of that metric, ordered by
workload and operation type (:data:`SORT_KEYS`).  Per metric the answer is written
twice over: once with every workload merged into it (``all_<metric>_<agg>.csv``)
and once per workload, so a plot of one workload needs no filtering and a sweep
comparison needs no concatenation.

``--max-node-bytes`` restricts the answer to the configurations up to that target
node size — the knob the sweep varies, so it is the one cut that makes the rest
of a sweep comparable.

Run:

    .cache/plot-venv/bin/python -m ycsb_bench.questions --data-dir <root>
    .cache/plot-venv/bin/python -m ycsb_bench.questions --agg median --output <dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
from benchgrid.data import Matrix

from .dataset import MEASURE_KEY, NODE_BYTES, SOURCE, build_dataset
from .naming import slug
from .paths import OUTPUT_DIR

#: Dimension of one answer: the workload, the operation type of the row, and the
#: configuration it was measured on.  Everything else in a run (the seeds) is
#: reduced away by the aggregation, like the heatmaps of the first tab.
WORKLOAD_KEY = "workload"
METRIC_KEY = "metric"
ROW_KEY = "struct_version"
#: Group keys of the answer, in the order they are written.
GROUP_KEYS: tuple[str, ...] = (
    WORKLOAD_KEY,
    METRIC_KEY,
    MEASURE_KEY,
    ROW_KEY,
    NODE_BYTES,
)
SORT_KEYS: tuple[str, ...] = (WORKLOAD_KEY, MEASURE_KEY)

#: The metrics the sweep is answered for, one CSV each.
QUESTION_METRICS: tuple[str, ...] = ("time_ms", "overhead_per_key")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        action="append",
        default=None,
        help="result root(s) to scan (default: the configured roots)",
    )
    parser.add_argument(
        "--metric",
        action="append",
        default=None,
        help=f"metric(s) to answer for, one CSV each (default: {', '.join(QUESTION_METRICS)})",
    )
    parser.add_argument(
        "--agg",
        default="mean",
        help="aggregation over the repeated seeds (default: mean)",
    )
    parser.add_argument(
        "--max-node-bytes",
        type=int,
        default=None,
        help="answer only for target node sizes <= this (default: no limit)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="where to write the CSV tables (default: the package output dir)",
    )
    return parser.parse_args()


def answer(
    dataset,
    metric: str,
    agg: str = "mean",
    max_node_bytes: int | None = None,
) -> pl.DataFrame:
    """
    *metric* as one long table over all workloads, aggregated over the seeds.

    Grouped by the answer's dimensions (:data:`GROUP_KEYS`) with the workload
    merged in, ordered by workload and operation type as the question asks, so
    two runs of the sweep write byte-identical tables.

    *max_node_bytes* keeps only the configurations up to that target node size.
    The cut is applied to the aggregated table because a group is one target
    size: dropping the groups above the limit is the same as never having
    measured them.
    """
    frame = dataset.aggregate(
        SOURCE, [key for key in GROUP_KEYS if key != METRIC_KEY], metric, agg
    )
    table = frame.select(
        pl.col(WORKLOAD_KEY),
        *(pl.col(key) for key in GROUP_KEYS if key not in (WORKLOAD_KEY, METRIC_KEY)),
        pl.col(metric),
    ).sort((*SORT_KEYS, metric), nulls_last=True)
    if max_node_bytes is not None:
        table = table.filter(pl.col(NODE_BYTES) <= max_node_bytes)
    return table


def write_tables(
    table: pl.DataFrame,
    metric: str,
    agg: str,
    output: Path,
    max_node_bytes: int | None = None,
) -> list[Path]:
    """
    Write *table* merged (``all_<metric>_<agg>.csv``) and split per workload.

    The merged table is the answer to the question; the per-workload files are
    the same rows without their siblings, named after the workload so they sort
    next to the merged one.  A *max_node_bytes* cut is part of the name
    (``_max<size>``) so two cuts of one sweep do not overwrite each other.
    Returns the paths written, merged first.
    """
    output.mkdir(parents=True, exist_ok=True)
    cut = f"_max{max_node_bytes}" if max_node_bytes is not None else ""
    merged = output / f"all_{metric}_{agg}{cut}.csv"
    table.write_csv(merged)
    written = [merged]
    for workload in table.get_column(WORKLOAD_KEY).unique().sort().to_list():
        path = output / f"{slug(workload)}_{metric}_{agg}{cut}.csv"
        table.filter(pl.col(WORKLOAD_KEY) == workload).write_csv(path)
        written.append(path)
    return written


def overview(table: pl.DataFrame, metric: str, agg: str = "mean") -> Matrix:
    """
    Workload x operation type, reduced to the console.

    Built from the answer itself, so the console cannot show a different
    aggregation, or a wider sweep, than the files it just wrote.
    """
    return Matrix.from_frame(
        table, WORKLOAD_KEY, MEASURE_KEY, metric, title=f"{metric} ({agg} over seeds)"
    )


def _header(dataset, max_node_bytes: int | None = None) -> str:
    seeds = len(dataset.distinct(SOURCE, "seed"))
    workloads = sorted(
        v for v in dataset.distinct(SOURCE, WORKLOAD_KEY) if v is not None
    )
    measures = sorted(v for v in dataset.distinct(SOURCE, MEASURE_KEY) if v is not None)
    sizes = sorted(v for v in dataset.distinct(SOURCE, NODE_BYTES) if v is not None)
    structures = sorted(v for v in dataset.distinct(SOURCE, ROW_KEY) if v is not None)
    lines = [
        f"seeds: {seeds} (aggregated by mean over the repeated runs)",
        f"workloads: {', '.join(workloads)}",
        f"measures (operation types): {', '.join(measures)}",
        f"structure variants: {', '.join(structures)}",
        f"target node sizes: {sizes}   (0 = structure without a node-size knob)",
        f"filter: target_node_bytes <= {max_node_bytes}"
        if max_node_bytes is not None
        else "filter: none (every target node size)",
        "rows: one per workload x operation type x structure variant x target node size",
        f"order: ASC {', ASC '.join(SORT_KEYS)}",
        "files per metric: all_<metric>_<agg>.csv merged, plus one per workload",
    ]
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    dataset = build_dataset(data_dirs=args.data_dir)
    if dataset.frame(SOURCE).is_empty():
        raise SystemExit(
            f"no series rows under {args.data_dir or 'the configured roots'}"
        )

    metrics = args.metric or list(QUESTION_METRICS)
    unknown = [metric for metric in metrics if metric not in dataset.metrics(SOURCE)]
    if unknown:
        raise SystemExit(
            f"metric(s) {unknown} not measured by this tree "
            f"(available: {dataset.metrics(SOURCE)})"
        )

    limit = args.max_node_bytes
    if limit is not None:
        sizes = sorted(
            v for v in dataset.distinct(SOURCE, NODE_BYTES) if v is not None
        )
        kept = [size for size in sizes if size <= limit]
        if not kept:
            raise SystemExit(
                f"--max-node-bytes {limit} excludes every target node size in the "
                f"tree (available: {sizes})"
            )
    print(_header(dataset, limit))
    for metric in metrics:
        table = answer(dataset, metric, args.agg, limit)
        merged, *per_workload = write_tables(
            table, metric, args.agg, args.output, limit
        )
        print(f"\n{metric} ({args.agg} over seeds) — {table.height} rows")
        print(f"  merged: {merged}")
        for path in per_workload:
            print(f"  one workload: {path}")
        print(overview(table, metric, args.agg).to_text())


__all__ = [
    "GROUP_KEYS",
    "METRIC_KEY",
    "QUESTION_METRICS",
    "ROW_KEY",
    "SORT_KEYS",
    "WORKLOAD_KEY",
    "answer",
    "main",
    "overview",
    "write_tables",
]


if __name__ == "__main__":
    main()
