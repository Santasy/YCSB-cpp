"""
Headless questions over a result tree of the run phase.

The same scan, schema, normalization and engine queries the plot viewer uses,
answered in the terminal: for one measure of one workload, a structure × target
node-size table per metric, written as CSV and printed as text.  Because a tree
holds several workloads (and their runs are not comparable across workloads),
the workload is always an explicit choice rather than something averaged away.

Run:

    .cache/plot-venv/bin/python -m ycsb_bench.questions --data-dir <root>
    .cache/plot-venv/bin/python -m ycsb_bench.questions \\
        --data-dir <root> --workload workload_kv_session --measure run:read
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .dataset import (
    ALL_METRICS,
    DEFAULT_MEASURE,
    MEASURE_KEY,
    NODE_BYTES,
    SOURCE,
    build_dataset,
    narrow,
)
from .enrich import MEASURE_SEP
from .paths import OUTPUT_DIR

#: Rows of the question table: one per structure variant.
ROW_KEY = "struct_version"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        action="append",
        default=None,
        help="result root(s) to scan (default: the configured roots)",
    )
    parser.add_argument(
        "--workload",
        default=None,
        help="workload to answer for (required when the tree holds several)",
    )
    parser.add_argument(
        "--measure",
        default=DEFAULT_MEASURE,
        help=f"measure to answer for (default: {DEFAULT_MEASURE})",
    )
    parser.add_argument(
        "--metric",
        action="append",
        default=None,
        help=f"metric(s) to tabulate (default: {', '.join(ALL_METRICS[:2])})",
    )
    parser.add_argument(
        "--agg",
        default="mean",
        help="aggregation over the repeated seeds (default: mean)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="where to write the CSV tables (default: the package output dir)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dataset = build_dataset(data_dirs=args.data_dir)
    if dataset.frame(SOURCE).is_empty():
        raise SystemExit(
            f"no series rows under {args.data_dir or 'the configured roots'}"
        )

    measures = sorted(v for v in dataset.distinct(SOURCE, MEASURE_KEY) if v is not None)
    workloads = sorted(v for v in dataset.distinct(SOURCE, "workload") if v is not None)
    if args.measure not in measures:
        raise SystemExit(
            f"measure {args.measure!r} not in data (available: {measures})"
        )
    if args.workload is None:
        if len(workloads) != 1:
            raise SystemExit(
                f"the tree holds {len(workloads)} workloads ({workloads}); "
                "pass --workload (runs are not comparable across workloads)"
            )
        workload = workloads[0]
    else:
        workload = args.workload
        if workload not in workloads:
            raise SystemExit(
                f"workload {workload!r} not in data (available: {workloads})"
            )

    metrics = args.metric or ALL_METRICS[:2]
    one = narrow(dataset, SOURCE, **{MEASURE_KEY: args.measure, "workload": workload})
    sizes = sorted(
        v for v in dataset.distinct(SOURCE, NODE_BYTES) if v is not None
    )
    seeds = len(dataset.distinct(SOURCE, "seed"))
    print(f"workload: {workload}   measure: {args.measure}   seeds: {seeds}")
    print(f"target node sizes: {sizes}   (0 = structure without a node-size knob)")

    args.output.mkdir(parents=True, exist_ok=True)
    stem = f"{args.measure.replace(MEASURE_SEP, '-')}_{workload}"
    for metric in metrics:
        matrix = one.matrix(SOURCE, ROW_KEY, NODE_BYTES, metric, args.agg, label=metric)
        path = args.output / f"{metric}_{stem}.csv"
        matrix.to_csv(path)
        print(f"\n{metric} ({args.agg}) — {ROW_KEY} x {NODE_BYTES} -> {path}")
        print(matrix.to_text())


__all__ = ["ROW_KEY", "main"]


if __name__ == "__main__":
    main()
