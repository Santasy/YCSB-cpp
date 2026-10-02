"""
Headless verification of the YCSB-cpp read end (no streamlit).

Builds a small synthetic result tree under ``.cache/`` with the shapes the real
runner produces — 10-field BTree/WTree rows next to 7-field ``std::map`` rows, a
structure-version folder, a stray non-data CSV — then walks the whole chain:
schema → ragged scan → :func:`enrich_series` → :func:`build_dataset` → engine
queries (filter, final_sample, aggregate, matrix).  Run:

    .cache/plot-venv/bin/python tools/ycsb_bench/tests/check_analysis.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tools/

import ycsb_bench  # noqa: E402, F401 — puts the BenchGrid checkout on sys.path
from benchgrid import read_schemas, scan_csv_lazy  # noqa: E402
from ycsb_bench import questions as questions_cli  # noqa: E402
from ycsb_bench.adapter import BEST_DIRECTION, DIMS  # noqa: E402
from ycsb_bench.app import TABS  # noqa: E402
from ycsb_bench.curves import (  # noqa: E402
    GROWTH_BEST,
    GROWTH_PER_TARGET,
    TRADEOFF,
)
from ycsb_bench.dataset import (  # noqa: E402
    ALL_METRICS,
    DEFAULT_MEASURE,
    MEASURE_KEY,
    METRIC_SOURCE,
    NODE_BYTES,
    PROGRESS_KEY,
    RUN_KEYS,
    SERIES_METRICS,
    SOURCE,
    SOURCE_METRICS,
    build_dataset,
    narrow,
)
from ycsb_bench.enrich import enrich_series  # noqa: E402
from ycsb_bench.paths import SCHEMA_FILE, data_dirs  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]  # repo root
TREE = ROOT / ".cache" / "ycsb_plot_check" / "results"

#: What the viewer must show, mirrored by the streamlit check.
TAB_LABELS = [
    "Metrics",
    "Growth — best target size",
    "Growth — per target size",
    "Trade-off — time vs memory",
]

#: (struct_version, node_size) of the structure variants in the tree.
TREE_LAYOUT = [
    ("btree", "256"),
    ("btree", "1024"),
    ("wtree-simple", "4096"),
    ("wtree-split", "4096"),
    ("std", "default"),
]

#: (run id, factor) of the runs: a plain run, and one swept over the runner's
#: choices, each with a per-seed cost factor so the seed means are visible.
WORKLOAD_RUNS = [
    ("workload_kv_session-ordered-fnv", {1: 1, 2: 5}),
    ("workload_ordered_inserts", {1: 2, 2: 3}),
]
SEEDS = (1, 2)

#: The per-seed factors of the runs above, as (factor, count) pairs.
FACTORS = [(1, 1), (5, 1), (2, 1), (3, 1)]
SEED_FACTOR_MEAN = (1 + 5) / 2  # workload_kv_session
SEED_FACTOR_MEAN_2 = (2 + 3) / 2  # workload_ordered_inserts

#: Rows per run: (phase, operation, ops, size, us, rss_kb).
RUN_ROWS = [
    ("load", "total", 100, 100, 4808, 9600),
    ("run", "read", 44, 100, 26048, 9800),
    ("run", "total", 244, 100, 130000, 11000),
]


def _row(phase: str, operation: str, ops: int, size: int, us: float, rss: int, extra: list[int]) -> str:
    fields = [phase, operation, str(ops), str(size), f"{us:.0f}", str(rss), str(size * 8)]
    return ",".join([*fields, *(str(v) for v in extra)])


def _write_tree() -> None:
    if TREE.exists():
        shutil.rmtree(TREE)
    for struct_version, node_size in TREE_LAYOUT:
        # std::map reports no tree metrics: its rows stop after the common fields.
        has_tree = struct_version != "std"
        extra = [3, 4, 2] if has_tree else []
        for run_id, factors in WORKLOAD_RUNS:
            for seed, factor in factors.items():
                path = TREE / struct_version / node_size / f"{run_id}-seed-{seed}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                lines = [
                    _row(phase, operation, ops, size, us * factor, rss * factor, extra)
                    for phase, operation, ops, size, us, rss in RUN_ROWS
                ]
                path.write_text("\n".join(lines) + "\n")
    # A schema/example CSV next to the data must not become a data row.
    (TREE / "schema.csv").write_text(
        "phase,operation,ops_count,current_size,time_us,maxrss_kb,overhead\n"
    )


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")
    print(f"  ok  {message}")


def _row_key(keys: list[str]):
    """The sort order the question promises (nulls last, as the frame is written)."""
    return lambda row: tuple(  # noqa: E731
        (1, "") if row[key] is None else (0, row[key]) for key in keys
    )


def _expected_mean(metric: str) -> tuple[float, float]:
    """
    The mean over the seeds of the ``run:read`` row, per workload.

    The synthetic runs scale their cost per seed, so the seed mean of a cost is
    the raw value times the mean factor; ``overhead_per_key`` is a ratio
    (``overhead / current_size``) and therefore scale-invariant — every seed
    agrees and the mean is the value itself.
    """
    read_us = next(us for _, operation, _, _, us, _ in RUN_ROWS if operation == "read")
    if metric == "time_ms":
        return (read_us * SEED_FACTOR_MEAN / 1000, read_us * SEED_FACTOR_MEAN_2 / 1000)
    return (8.0, 8.0)


def _questions(dataset) -> None:
    """The headless question: seed means over both workloads, one table per metric."""
    print("questions")
    _check(
        questions_cli.QUESTION_METRICS == ("time_ms", "overhead_per_key"),
        f"the question answers {questions_cli.QUESTION_METRICS}",
    )
    for metric in questions_cli.QUESTION_METRICS:
        table = questions_cli.answer(dataset, metric, "mean")
        _check(
            table.columns
            == [questions_cli.WORKLOAD_KEY, MEASURE_KEY, questions_cli.ROW_KEY, NODE_BYTES, metric],
            f"{metric}: one column per answer dimension, then the value",
        )
        # Both workloads are merged into one answer, so the rows cover every
        # (workload, operation type, structure variant, target node size).
        _check(
            table.height == len(WORKLOAD_RUNS) * len(RUN_ROWS) * len(TREE_LAYOUT),
            f"{metric}: {table.height} rows — every workload, operation type and variant",
        )
        _check(
            sorted(table.get_column(questions_cli.WORKLOAD_KEY).unique().to_list())
            == ["workload_kv_session", "workload_ordered_inserts"],
            f"{metric}: both workloads in one table",
        )
        # Sorted by workload then operation type, and the order does not drift.
        keys = list(questions_cli.SORT_KEYS)
        _check(
            table.rows(named=True) == sorted(table.rows(named=True), key=_row_key(keys)),
            f"{metric}: sorted by {', '.join(keys)}",
        )
        _check(
            table.equals(questions_cli.answer(dataset, metric, "mean")),
            f"{metric}: the answer is deterministic",
        )
        # The value is the mean over the seeds: the synthetic runs scale their
        # cost per seed, so the mean of the factors must come out of the answer.
        read_row = table.filter(
            (pl.col(MEASURE_KEY) == "run:read")
            & (pl.col(questions_cli.ROW_KEY) == "btree")
            & (pl.col(NODE_BYTES) == 256)
        )
        means = dict(
            zip(
                read_row.get_column(questions_cli.WORKLOAD_KEY).to_list(),
                read_row.get_column(metric).to_list(),
                strict=True,
            )
        )
        expected = _expected_mean(metric)
        _check(
            all(
                abs(value - want) < 1e-6
                for value, want in zip(means.values(), expected, strict=True)
            ),
            f"{metric}: the rows are the mean over the seeds "
            f"({', '.join(f'{v:g}' for v in means.values())})",
        )
    # The target-size cut: only the configurations up to the limit answer.
    sizes = sorted(v for v in dataset.distinct(SOURCE, NODE_BYTES) if v is not None)
    whole = questions_cli.answer(dataset, "time_ms", "mean")
    variants = whole.select(questions_cli.ROW_KEY, NODE_BYTES).unique().rows()
    for limit in (0, 1024, max(sizes)):
        cut = questions_cli.answer(dataset, "time_ms", "mean", limit)
        kept = sorted(cut.select(questions_cli.ROW_KEY, NODE_BYTES).unique().rows())
        expected = sorted(variant for variant in variants if variant[1] <= limit)
        _check(
            kept == expected
            and cut.height == len(expected) * len(WORKLOAD_RUNS) * len(RUN_ROWS),
            f"--max-node-bytes {limit}: {cut.height} rows over "
            f"{len(kept)} structure variant(s) at or below the limit",
        )
    _check(
        questions_cli.answer(dataset, "time_ms", "mean", 1024).height
        < questions_cli.answer(dataset, "time_ms", "mean").height,
        "the cut is a strict reduction of the sweep",
    )

    # The files: one merged per metric, plus one per workload holding its rows.
    output = ROOT / ".cache" / "ycsb_plot_check" / "questions"
    if output.exists():
        shutil.rmtree(output)
    for metric in questions_cli.QUESTION_METRICS:
        table = questions_cli.answer(dataset, metric, "mean")
        merged, *split = questions_cli.write_tables(table, metric, "mean", output)
        workloads = sorted(
            v for v in dataset.distinct(SOURCE, questions_cli.WORKLOAD_KEY) if v is not None
        )
        _check(
            merged.name == f"all_{metric}_mean.csv"
            and [path.name for path in split]
            == [f"{workload}_{metric}_mean.csv" for workload in workloads],
            f"{metric}: files are all_{metric}_mean.csv plus one per workload",
        )
        _check(
            pl.read_csv(merged).equals(table),
            f"{metric}: the merged file is the answer",
        )
        for path, workload in zip(split, workloads, strict=True):
            _check(
                pl.read_csv(path).equals(
                    table.filter(pl.col(questions_cli.WORKLOAD_KEY) == workload)
                ),
                f"{metric}: {path.name} holds exactly its workload's rows",
            )
        # A cut of the same sweep is named apart, so it cannot overwrite the whole.
        cut_table = questions_cli.answer(dataset, metric, "mean", 1024)
        cut_merged, *cut_split = questions_cli.write_tables(
            cut_table, metric, "mean", output, 1024
        )
        _check(
            cut_merged.name == f"all_{metric}_mean_max1024.csv"
            and all("_max1024.csv" in path.name for path in cut_split)
            and pl.read_csv(cut_merged).equals(cut_table),
            f"{metric}: the cut is written beside the whole sweep",
        )
    shutil.rmtree(output)

    # A different aggregation answers the same shape with different numbers.
    means = questions_cli.answer(dataset, "time_ms", "mean")
    minima = questions_cli.answer(dataset, "time_ms", "min")
    _check(
        minima.shape == means.shape
        and minima.get_column("time_ms").ne(means.get_column("time_ms")).sum() > 0,
        "the seed aggregation is the only thing that differs between --agg choices",
    )


def _declarations() -> None:
    """The plot declarations: sidebar filters, cost direction, tabs, view specs."""
    print("declarations")
    _check(
        set(DIMS)
        == {"workload", "struct_version", "node_size", "insert_order", "hash_algo"},
        f"sidebar filters: {DIMS}",
    )
    _check(
        not BEST_DIRECTION,
        "every metric is a cost, so the viewer has no better-is-higher metric",
    )
    _check(
        [tab.label for tab in TABS] == TAB_LABELS,
        f"tabs declared: {[tab.label for tab in TABS]}",
    )
    _check(
        GROWTH_BEST.select_best == NODE_BYTES
        and GROWTH_PER_TARGET.select_best is None
        and TRADEOFF.x_metric == "overhead_per_key"
        and TRADEOFF.y_metric == "time_ms",
        "one growth view picks the best target size, the other draws every "
        "size, and the trade-off pairs time with overhead",
    )


def main() -> None:
    _write_tree()
    roots = [str(TREE)]

    print("schema")
    schemas = read_schemas(SCHEMA_FILE)
    _check(list(schemas) == [SOURCE], f"one source, {SOURCE}")
    _check(schemas[SOURCE].line_schema.ragged, "line schema is ragged")
    _check(
        dict(enumerate(schemas[SOURCE].line_schema.metrics.values()))[9] == "internal_nodes",
        "internal_nodes is the last positional field",
    )

    print("scan + enrich")
    raw = scan_csv_lazy(roots, schemas[SOURCE]).collect()
    _check(
        "__line__" not in raw.columns and "__fields__" not in raw.columns,
        "ragged scan leaves no helper columns",
    )
    _check(
        raw.height == len(RUN_ROWS) * len(TREE_LAYOUT) * 2 * len(WORKLOAD_RUNS) + 1,
        f"every series row scanned, the stray example CSV included ({raw.height})",
    )
    _check(
        raw.filter(pl.col("struct_version") == "std").get_column("height").null_count()
        == 2 * len(WORKLOAD_RUNS) * len(RUN_ROWS),
        "std::map rows carry no structure metrics",
    )

    frame = enrich_series(scan_csv_lazy(roots, schemas[SOURCE]))
    _check(isinstance(frame, pl.LazyFrame), "enrich keeps the single-pass lazy scan")
    frame = frame.collect()
    _check(
        frame.height == 2 * len(TREE_LAYOUT) * len(SEEDS) * len(RUN_ROWS),
        f"rows without path metadata dropped ({frame.height})",
    )
    _check(
        set(frame.get_column("struct_symbol").unique().to_list())
        == {"btree", "wtree", "std"},
        "struct_version split into struct_symbol",
    )
    simple = frame.filter(pl.col("struct_version") == "wtree-simple")
    _check(
        simple.get_column("struct_symbol").unique().to_list() == ["wtree"]
        and simple.get_column("version").unique().to_list() == ["simple"],
        "wtree-simple -> wtree + version simple",
    )
    _check(
        set(frame.get_column("measure").unique().to_list())
        == {"load:total", "run:read", "run:total"},
        "measure per operation type + load/total",
    )
    _check(
        sorted(frame.get_column("workload").unique().to_list())
        == ["workload_kv_session", "workload_ordered_inserts"],
        "both workloads of the tree are read",
    )
    _check(
        frame.filter(pl.col("workload") == "workload_kv_session")
        .get_column("insert_order")
        .unique()
        .to_list()
        == ["ordered"]
        and frame.filter(pl.col("workload") == "workload_kv_session")
        .get_column("hash_algo")
        .unique()
        .to_list()
        == ["fnv"]
        and frame.filter(pl.col("workload") == "workload_ordered_inserts")
        .get_column("insert_order")
        .null_count()
        == frame.filter(pl.col("workload") == "workload_ordered_inserts").height,
        "run id split into workload + runner choices (a plain run has neither)",
    )
    _check(
        sorted(frame.get_column(NODE_BYTES).unique().to_list()) == [0, 256, 1024, 4096],
        "target_node_bytes is numeric, 0 for a structure without the knob",
    )
    read_row = frame.filter(
        (pl.col("measure") == "run:read") & (pl.col("time_us") == 26048.0)
    ).row(0, named=True)
    _check(
        abs(read_row["us_per_op"] - 26048 / 44) < 1e-6
        and abs(read_row["ops_per_sec"] - 44 * 1e6 / 26048) < 1e-3
        and read_row["overhead_per_key"] == 8,
        "derived per-op / throughput / per-key metrics",
    )
    std_row = frame.filter(pl.col("struct_symbol") == "std").row(0, named=True)
    _check(
        std_row["height"] is None
        and std_row["keys_per_leaf"] is None
        and std_row["overhead_per_key"] == 8,
        "structure metrics are null, cost metrics still computed",
    )

    print("dataset")
    dataset = build_dataset(roots)
    _check(dataset.sources == [SOURCE], "single source")
    _check(
        set(dataset.metrics(SOURCE)) == set(SERIES_METRICS),
        "metric registry drives Dataset.metrics",
    )
    _check(
        set(METRIC_SOURCE) == {m for ms in SOURCE_METRICS.values() for m in ms}
        and set(ALL_METRICS) <= set(SERIES_METRICS),
        "declared metrics are measurements",
    )
    _check(
        {MEASURE_KEY, "workload", "struct_version", NODE_BYTES}
        <= set(dataset.dimensions(SOURCE)),
        "measure and run naming are dimensions",
    )
    _check(
        dataset.frame(SOURCE).height == 60
        and build_dataset(roots).frame(SOURCE).equals(dataset.frame(SOURCE)),
        "the build is deterministic",
    )

    print("engine queries")
    final = dataset.final_sample(SOURCE, list(RUN_KEYS), PROGRESS_KEY)
    _check(
        final.height == 60,
        "the run identity includes the measure: final sample keeps every row",
    )
    totals = narrow(dataset, SOURCE, **{MEASURE_KEY: DEFAULT_MEASURE, "workload": "workload_kv_session"})
    _check(
        totals.frame(SOURCE).height == 10,
        f"narrowing to {DEFAULT_MEASURE} of one workload",
    )
    aggregated = totals.aggregate(SOURCE, [NODE_BYTES], "us_per_op", "mean")
    _check(aggregated.height == 4, "one aggregated row per target node size")
    matrix = totals.matrix(SOURCE, questions_cli.ROW_KEY, NODE_BYTES, "us_per_op", "mean")
    _check(
        sorted(matrix.row_values()) == ["btree", "std", "wtree-simple", "wtree-split"],
        "matrix rows are the structure variants",
    )
    _check(
        sorted(matrix.col_values()) == [0, 256, 1024, 4096],
        "matrix columns are the target node sizes",
    )
    print("\n" + matrix.to_text())

    _declarations()
    _questions(dataset)

    print("configuration")
    _check(data_dirs() == data_dirs(), "configured roots resolve")

    print("\nread-end check ok")


if __name__ == "__main__":
    main()
