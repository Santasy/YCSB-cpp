"""
YCSB-cpp data assembly on the BenchGrid chain.

``build_dataset`` scans a result tree with the one shared schema
(:data:`.paths.SCHEMA_FILE`) through the Polars fast path, applies the project
normalization (:mod:`.enrich`) and wraps the frame in a
:class:`benchgrid.Dataset`.  Every query then reuses the generic engine
(``final_sample``, ``aggregate``, ``matrix``, ``filter``) — no
workload-specific query class is needed.

There is exactly one source: a YCSB run reports its time *and* memory measures
in the same row, so both live in one frame named ``ycsb``.  The *measure*
column (``load:total``, ``run:read``, ``run:total``, …) plays the role the
insert_only workloads give to their batch-phase ``step``, and
``current_size`` — the number of keys the run holds — is the progress column
growth curves are drawn against.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from benchgrid import Dataset, read_schemas, scan_csv_lazy
from benchgrid.schema import ScanSchema

from .enrich import enrich_series
from .paths import SCHEMA_FILE
from .paths import data_dirs as configured_data_dirs

#: The single series source (time and memory merged per row).
SOURCE = "ycsb"

#: Sidebar label of the source.
SOURCE_LABEL = "Time + memory (one merged series)"

#: The (phase, operation) row a view is about; the step/selector dimension.
MEASURE_KEY = "measure"
#: The measure a view opens on: the whole measured phase of the benchmark.
DEFAULT_MEASURE = "run:total"
#: Keys the run holds; also the growth axis of the curve views.
PROGRESS_KEY = "current_size"
#: The swept node-size variant, numeric (0 = structure without a node-size knob).
NODE_BYTES = "target_node_bytes"

#: Dimension keys that identify one measured row of one run (see :mod:`.enrich`).
#: ``measure`` is part of the identity because a run contributes one row per
#: (phase, operation) — so taking the maximum ``current_size`` per run is the
#: row itself, and a cumulative sampler stays comparable if one ever appears.
RUN_KEYS: tuple[str, ...] = (
    "struct_version",
    "node_size",
    "workload",
    "insert_order",
    "hash_algo",
    "seed",
    MEASURE_KEY,
)

#: Keys treated as measurements of the series source.
SERIES_METRICS: list[str] = [
    # raw, as the benchmark prints them
    "time_us",
    "maxrss_kb",
    "overhead",
    "ops_count",
    PROGRESS_KEY,
    "height",
    "leaf_nodes",
    "internal_nodes",
    "node_count",
    # derived (see enrich._derived)
    "time_ms",
    "us_per_op",
    "ops_per_sec",
    "overhead_per_key",
    "bytes_per_node",
    "keys_per_leaf",
    "rss_mb",
]

#: Curated metric subset exposed as the shared plot dropdown.
ALL_METRICS: list[str] = [
    "us_per_op",
    "ops_per_sec",
    "time_ms",
    "time_us",
    "overhead",
    "overhead_per_key",
    "bytes_per_node",
    "rss_mb",
    "height",
    "keys_per_leaf",
    "node_count",
    "ops_count",
]

#: Canonical source-ordered metric registry — the single declaration of which
#: keys are measurements.
SOURCE_METRICS: dict[str, list[str]] = {SOURCE: SERIES_METRICS}

#: metric → source; plots resolve their data frame from this.
METRIC_SOURCE: dict[str, str] = {
    metric: source
    for source, metrics in SOURCE_METRICS.items()
    for metric in metrics
}


def build_dataset(
    data_dirs: list[str] | None = None,
    schemas: dict[str, ScanSchema] | None = None,
) -> Dataset:
    """
    Scan *data_dirs* (default: :func:`.paths.data_dirs`) into an enriched
    :class:`benchgrid.Dataset`.

    The one schema drives the Polars ragged scan, the project normalization
    turns the run/folder names into dimensions and derived metrics, and the
    frame is wrapped with the canonical metric keys so ``Dataset.metrics`` /
    ``Dataset.dimensions`` behave.
    """
    schemas = schemas or read_schemas(SCHEMA_FILE)
    dirs = data_dirs or configured_data_dirs()
    parsed_dirs = []
    for d in dirs:
        path = Path(d)
        if path.name != "results":
            path = path / "results"
        parsed_dirs.append(path)
    return Dataset(
        frames={
            SOURCE: enrich_series(scan_csv_lazy(parsed_dirs, schemas[SOURCE]))
        },
        schemas=schemas,
        metric_keys={SOURCE: frozenset(SERIES_METRICS)},
    )


def narrow(dataset: Dataset, source: str = SOURCE, **fixed: Any) -> Dataset:
    """
    A copy of *dataset* with *source* restricted to rows matching *fixed*.

    The engine reduces a whole frame per query, so a question about one measure
    of one workload narrows the frame first and then queries it — the same
    filter the view applies, just headless.
    """
    frame = dataset.filter(source, **fixed)
    return Dataset(
        frames={source: frame},
        schemas={source: dataset.schemas[source]},
        metric_keys={source: dataset.metric_keys[source]},
    )


__all__ = [
    "ALL_METRICS",
    "DEFAULT_MEASURE",
    "MEASURE_KEY",
    "METRIC_SOURCE",
    "NODE_BYTES",
    "PROGRESS_KEY",
    "RUN_KEYS",
    "SERIES_METRICS",
    "SOURCE",
    "SOURCE_LABEL",
    "SOURCE_METRICS",
    "build_dataset",
    "narrow",
]
