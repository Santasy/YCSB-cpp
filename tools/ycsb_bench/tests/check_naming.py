"""
The run end and the read end must agree on the grammar of a result tree.

``ycsb_bench.naming`` is that grammar, and this check walks every shape the run
phase can produce — workloads x insert orders x hash algorithms x seeds, per
structure variant — round tripping each name through the scalar helpers
(:func:`~ycsb_bench.naming.run_name` → :func:`~ycsb_bench.naming.split_run_name`,
:func:`~ycsb_bench.naming.structure_folder` →
:func:`~ycsb_bench.naming.split_structure_folder`,
:func:`~ycsb_bench.naming.variant_label` →
:func:`~ycsb_bench.naming.node_size_bytes`) and through the two places the
*names* are consumed: the schema's file pattern and the vectorized parsing in
:func:`~ycsb_bench.enrich.enrich_series`.  Run:

    .cache/plot-venv/bin/python tools/ycsb_bench/tests/check_naming.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tools/

from ycsb_bench.naming import (  # noqa: E402
    DEFAULT_VERSION,
    HASH_ALGOS,
    INSERT_ORDERS,
    NO_NODE_BYTES,
    SEED_MARKER,
    measure_label,
    node_size_bytes,
    run_name,
    split_run_name,
    split_structure_folder,
    structure_folder,
    variant_label,
)
from ycsb_bench.paths import SCHEMA_FILE  # noqa: E402
from ycsb_bench.runs import make_targets  # noqa: E402
from ycsb_bench.specs import tree_specs  # noqa: E402

WORKLOADS = ("workload_kv_session", "workload_ordered_inserts")
SEEDS = (1, 7, 30)
STRUCTURES = (("btree", None), ("btree", "small"), ("wtree", "simple"),
              ("wtree", "split"), ("std", None))
NODE_SIZES = (256, 16384, None)


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")
    print(f"  ok  {message}")


def _schema_file_pattern() -> re.Pattern[str]:
    """The compiled ``<run_id>-seed-<n>.csv`` pattern of the shared schema."""
    pattern = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    text = pattern["ycsb"]["file_pattern"]["pattern"]
    return re.compile(text)


def _combos() -> list[tuple[str, str | None, str | None, int]]:
    """Every (workload, insert order, hash algorithm, seed) the runner can sweep."""
    return [
        (workload, order, algo, seed)
        for workload in WORKLOADS
        for order in (None, *INSERT_ORDERS)
        for algo in (None, *HASH_ALGOS)
        for seed in SEEDS
    ]


def _enriched_names() -> list[dict[str, object]]:
    """What the vectorized read end makes of one row per run id."""
    combos = [
        (workload, order, algo, seed)
        for workload in WORKLOADS
        for order in (None, *INSERT_ORDERS)
        for algo in (None, *HASH_ALGOS)
        for seed in SEEDS
    ]
    # The frame the scanner hands to the enrich hook: the path/run-id groups
    # plus one row of measurements (all trees report time and memory).
    row_count = len(combos)
    frame = pl.DataFrame(
        {
            "phase": ["load"] * row_count,
            "operation": ["total"] * row_count,
            "struct_version": [structure_folder("btree")] * row_count,
            "node_size": [variant_label(256)] * row_count,
            "run_id": [run_name(w, o, a, s).rsplit(f"-{SEED_MARKER}-", 1)[0]
                       for w, o, a, s in combos],
            "seed": [seed for _, _, _, seed in combos],
            "time_us": [1.0] * row_count,
            "ops_count": [1] * row_count,
            "current_size": [1] * row_count,
            "maxrss_kb": [1] * row_count,
            "overhead": [1] * row_count,
            "leaf_nodes": [1] * row_count,
            "internal_nodes": [1] * row_count,
            "height": [1] * row_count,
        }
    )
    from ycsb_bench.enrich import enrich_series  # noqa: PLC0415 — the hook under test

    return enrich_series(frame).select("workload", "insert_order", "hash_algo").to_dicts()


def _scalar_grammar() -> None:
    """Every name the run end can build parses back into the parts it came from."""
    print("scalar grammar")
    combos = [
        (workload, order, algo, seed)
        for workload in WORKLOADS
        for order in (None, *INSERT_ORDERS)
        for algo in (None, *HASH_ALGOS)
        for seed in SEEDS
    ]
    for workload, order, algo, seed in combos:
        name = run_name(workload, order, algo, seed)
        parsed = split_run_name(name)
        if (parsed.workload, parsed.insert_order, parsed.hash_algo, parsed.seed) != (
            workload,
            order,
            algo,
            seed,
        ):
            raise SystemExit(
                f"FAIL: {name!r} parsed back as {parsed}, expected "
                f"workload={workload!r} order={order!r} algo={algo!r} seed={seed}"
            )
    _check(True, f"run ids round trip ({len(combos)} combinations)")

    for struct, version in STRUCTURES:
        folder = structure_folder(struct, version)
        _check(
            split_structure_folder(folder) == (struct, version or DEFAULT_VERSION),
            f"{folder} → {split_structure_folder(folder)}",
        )
    for node_size in NODE_SIZES:
        label = variant_label(node_size)
        _check(
            node_size_bytes(label) == (node_size or NO_NODE_BYTES),
            f"variant {label} → {node_size_bytes(label)} bytes",
        )
    _check(
        measure_label("run", "total") == "run:total",
        "measure label is phase:operation",
    )


def _schema_agreement() -> re.Pattern[str]:
    """The shared schema must accept the file names the run end writes."""
    print("schema agreement")
    pattern = _schema_file_pattern()
    names = [
        run_name(workload, order, algo, seed)
        for workload in WORKLOADS
        for order in (None, "ordered")
        for algo in (None, "fnv")
        for seed in SEEDS
    ]
    matched = [name for name in names if pattern.match(f"{name}.csv")]
    _check(
        len(matched) == len(names),
        f"the schema file pattern matches every run id ({len(matched)}/{len(names)})",
    )
    groups = pattern.match(f"{run_name('workload_kv_session', None, None, 3)}.csv")
    _check(
        groups is not None
        and groups["run_id"] == "workload_kv_session"
        and groups["seed"] == "3",
        "the schema splits the run id from the seed",
    )
    return pattern


def _read_end_agreement() -> None:
    """The vectorized enrich hook must read back what the run end wrote."""
    print("read end agreement")
    expected = sorted(
        (workload, order or "", algo or "")
        for workload, order, algo, _ in _combos()
    )
    enriched = sorted(
        (row["workload"], row["insert_order"] or "", row["hash_algo"] or "")
        for row in _enriched_names()
    )
    if enriched != expected:
        raise SystemExit(
            f"FAIL: the enrich hook does not agree with the run end\n"
            f"  missing: {sorted(set(expected) - set(enriched))}\n"
            f"  unexpected: {sorted(set(enriched) - set(expected))}"
        )
    _check(True, f"the enrich hook reads back all {len(expected)} run ids")


def _run_end_agreement(pattern: re.Pattern[str]) -> None:
    """Every target the runner plans must be named the way the reader expects."""
    print("run end agreement")
    workload_paths = [Path(workload) for workload in WORKLOADS]
    grid = [
        (order, algo, seed)
        for order in (None, "ordered")
        for algo in (None, "fnv")
        for seed in SEEDS
    ]
    for name, spec in tree_specs().items():
        # Structures with a node-size knob get one variant per node size; one
        # without it (std::map) has exactly one, and every request collapses
        # onto it — exactly as the runner does.
        node_sizes = NODE_SIZES if spec.node_env is not None else (None,)
        for node_size in node_sizes:
            targets = make_targets(
                spec,
                node_size,
                workload_paths,
                grid,
                Path("/out"),
                Path("/out/datasets"),
            )
            for target in targets:
                _check_target(spec, node_size, target, pattern)
            _check(
                True,
                f"{name}/{variant_label(node_size)}: {len(targets)} target(s) well named",
            )


def _check_target(
    spec: object, node_size: int | None, target: object, pattern: re.Pattern[str]
) -> None:
    """One planned target: structure folder, variant folder, run id, schema match."""
    result = target.result  # type: ignore[attr-defined]
    parsed = split_run_name(result.stem)
    if parsed.workload not in WORKLOADS or parsed.seed not in SEEDS:
        raise SystemExit(f"FAIL: {result.name!r} does not parse back")
    if result.parent.name != variant_label(node_size):
        raise SystemExit(f"FAIL: {result} is not in a variant folder")
    if result.parent.parent.name != structure_folder(spec.name):  # type: ignore[attr-defined]
        raise SystemExit(f"FAIL: {result} is not under a structure folder")
    if not pattern.match(result.name):
        raise SystemExit(f"FAIL: {result.name} misses the schema")


def main() -> None:
    _scalar_grammar()
    pattern = _schema_agreement()
    _read_end_agreement()
    _run_end_agreement(pattern)
    print("\nnaming check ok")


if __name__ == "__main__":
    main()
