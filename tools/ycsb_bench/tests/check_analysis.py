"""
Headless verification of the YCSB-cpp analysis layer (no streamlit).

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

from ycsb_bench.analysis import cli as analysis_cli  # noqa: E402
from ycsb_bench.analysis.bridge import read_schemas, scan_csv_lazy  # noqa: E402
from ycsb_bench.analysis.dataset import (  # noqa: E402
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
from ycsb_bench.analysis.enrich import enrich_series  # noqa: E402
from ycsb_bench.analysis.paths import SCHEMA_FILE, data_dirs  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]  # repo root
TREE = ROOT / ".cache" / "ycsb_plot_check" / "results"

#: (struct_version, node_size, run_id suffix) → extra structure fields per row.
TREE_LAYOUT = [
    ("btree", "256", ""),
    ("btree", "1024", ""),
    ("wtree-simple", "4096", ""),
    ("wtree-split", "4096", ""),
    ("std", "default", ""),
]


def _row(phase: str, operation: str, ops: int, size: int, us: float, rss: int, extra: list[int]) -> str:
    fields = [phase, operation, str(ops), str(size), f"{us:.0f}", str(rss), str(size * 8)]
    return ",".join([*fields, *(str(v) for v in extra)])


def _write_tree() -> None:
    if TREE.exists():
        shutil.rmtree(TREE)
    for struct_version, node_size, _ in TREE_LAYOUT:
        # std::map reports no tree metrics: its rows stop after the common fields.
        has_tree = struct_version != "std"
        for seed in (1, 2):
            run_id = f"workload_kv_session-ordered-fnv-seed-{seed}"
            path = TREE / struct_version / node_size / f"{run_id}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                _row("load", "total", 100, 100, 4808, 9600, [3, 4, 2] if has_tree else []),
                _row("run", "read", 44, 100, 26048, 9800, [3, 4, 2] if has_tree else []),
                _row("run", "total", 244, 100, 130000, 11000, [4, 6, 3] if has_tree else []),
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
        raw.height == 3 * 2 * 5 + 1,
        f"every series row scanned, the stray example CSV included ({raw.height})",
    )
    _check(
        raw.filter(pl.col("struct_version") == "std").get_column("height").null_count() == 6,
        "std::map rows carry no structure metrics",
    )

    frame = enrich_series(scan_csv_lazy(roots, schemas[SOURCE]))
    _check(isinstance(frame, pl.LazyFrame), "enrich keeps the single-pass lazy scan")
    frame = frame.collect()
    _check(frame.height == 30, f"rows without path metadata dropped ({frame.height})")
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
        frame.get_column("workload").unique().to_list() == ["workload_kv_session"]
        and frame.get_column("insert_order").unique().to_list() == ["ordered"]
        and frame.get_column("hash_algo").unique().to_list() == ["fnv"],
        "run id split into workload + runner choices",
    )
    _check(
        sorted(frame.get_column(NODE_BYTES).unique().to_list()) == [0, 256, 1024, 4096],
        "target_node_bytes is numeric, 0 for a structure without the knob",
    )
    read_row = frame.filter(pl.col("measure") == "run:read").row(0, named=True)
    _check(
        abs(read_row["us_per_op"] - 26048 / 44) < 1e-6
        and abs(read_row["ops_per_sec"] - 44 * 1e6 / 26048) < 1e-3
        and read_row["bytes_per_key"] == 8,
        "derived per-op / throughput / per-key metrics",
    )
    std_row = frame.filter(pl.col("struct_symbol") == "std").row(0, named=True)
    _check(
        std_row["height"] is None
        and std_row["keys_per_leaf"] is None
        and std_row["bytes_per_key"] == 8,
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
        dataset.frame(SOURCE).height == 30
        and build_dataset(roots).frame(SOURCE).equals(dataset.frame(SOURCE)),
        "the build is deterministic",
    )

    print("engine queries")
    final = dataset.final_sample(SOURCE, list(RUN_KEYS), PROGRESS_KEY)
    _check(
        final.height == 30,
        "the run identity includes the measure: final sample keeps every row",
    )
    totals = narrow(dataset, SOURCE, **{MEASURE_KEY: DEFAULT_MEASURE, "workload": "workload_kv_session"})
    _check(
        totals.frame(SOURCE).height == 10,
        f"narrowing to {DEFAULT_MEASURE} of one workload",
    )
    aggregated = totals.aggregate(SOURCE, [NODE_BYTES], "us_per_op", "mean")
    _check(aggregated.height == 4, "one aggregated row per target node size")
    matrix = totals.matrix(SOURCE, analysis_cli.ROW_KEY, NODE_BYTES, "us_per_op", "mean")
    _check(
        sorted(matrix.row_values()) == ["btree", "std", "wtree-simple", "wtree-split"],
        "matrix rows are the structure variants",
    )
    _check(
        sorted(matrix.col_values()) == [0, 256, 1024, 4096],
        "matrix columns are the target node sizes",
    )
    print("\n" + matrix.to_text())

    print("configuration")
    _check(data_dirs() == data_dirs(), "configured roots resolve")

    print("\nanalysis check ok")


if __name__ == "__main__":
    main()
