"""
YCSB-cpp plot adapter — the declarative contract for the generic engine.

The whole streamlit viewer and every chart sink is reused from BenchGrid; this
file is the workload's *declarations only* (metrics, axes, defaults), plus the
load hook that runs the project normalization from :mod:`.dataset`.

What the viewer *shows* is the workload's UI composition: the tab list lives in
:mod:`.tabs` (streamlit side) and the growth/trade-off specs in :mod:`.curves`.

Two shapes of data meet in one tree, which the declarations accommodate:

* the y axis is the swept node size, and :data:`.dataset.NO_NODE_BYTES` (0)
  holds the structures that have no such knob (std::map) so the axis stays
  numeric and the comparison is one heatmap;
* the step selector is a *measure* (per operation type, plus ``load:total`` and
  ``run:total``), not a batch phase, and opens on :data:`.dataset.DEFAULT_MEASURE`.
"""

from __future__ import annotations

from .bridge import PlotsAdapter
from .dataset import (
    ALL_METRICS,
    DEFAULT_MEASURE,
    MEASURE_KEY,
    METRIC_SOURCE,
    NODE_BYTES,
    PROGRESS_KEY,
    RUN_KEYS,
    SOURCE,
    SOURCE_LABEL,
    SOURCE_METRICS,
    build_dataset,
)
from .enrich import enrich_series
from .paths import SCHEMA_FILE, data_dirs

#: Sidebar filters: what a run is (workload, structure variant, run-id choices).
DIMS = ["workload", "struct_version", "node_size", "insert_order", "hash_algo"]

#: Every metric of a YCSB run is a cost: lower is better.
BEST_DIRECTION: dict[str, str] = {}


def build_adapter(dirs: list[str] | None = None) -> PlotsAdapter:
    """The adapter for the result roots *dirs* (default: :func:`.paths.data_dirs`)."""
    roots = list(dirs) if dirs else data_dirs()
    return PlotsAdapter(
        title="YCSB-cpp Benchmark Plot Viewer",
        schema_file=SCHEMA_FILE,
        data_dirs=roots,
        metrics=ALL_METRICS,
        metric_source=METRIC_SOURCE,
        source_metrics=SOURCE_METRICS,
        run_keys=list(RUN_KEYS),
        progress_key=PROGRESS_KEY,
        step_key=MEASURE_KEY,
        step_label="Measure",
        step_default=DEFAULT_MEASURE,
        dims=DIMS,
        x_keys=["struct_symbol", "version"],
        y_key=NODE_BYTES,
        color_group_extras=["struct_symbol"],
        best_direction=BEST_DIRECTION,
        default_panels=[
            {"metric": "time_ms", "chart_kind": "Heatmap"},
            {"metric": "overhead_per_key", "chart_kind": "Heatmap"},
        ],
        source_labels={SOURCE: SOURCE_LABEL},
        compare_label="Compare structure·version on x",
        enrich={SOURCE: enrich_series},
        load=lambda: build_dataset(roots),
        distinct_source=SOURCE,
    )


#: The viewer adapter (configured roots).
adapter = build_adapter()


def run_app() -> None:
    """Entry point for ``streamlit run`` — delegates to the generic shell."""
    from benchgrid.plots.app import run  # noqa: PLC0415

    from .tabs import TABS  # noqa: PLC0415

    run(adapter, TABS)


__all__ = ["BEST_DIRECTION", "DIMS", "adapter", "build_adapter", "run_app"]
