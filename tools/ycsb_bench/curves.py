"""
YCSB-cpp view *declarations* — the growth curves and the trade-off plot.

Every view opens with the engine's measure selector, so the specs declare
nothing about phases; the measure of interest is a tab-local choice.  What
stays project knowledge is the *identity* of a view — which keys make a curve,
a series or a point, and which one is the swept configuration — and that is
what these specs are.

The growth axis is ``current_size``: a YCSB run reports one row per
(phase, operation) for the record count it ran, so the curves show how a
structure's cost and footprint move as its population grows.
"""

from __future__ import annotations

from benchgrid.plots.curves import CurvePlotSpec
from benchgrid.plots.pairs import PairPlotSpec

from .dataset import MEASURE_KEY, NODE_BYTES, PROGRESS_KEY, SOURCE

#: Case A — one curve per (structure, version); each size is the best value of
#: the chosen metric over the target node size, and the point is labeled with
#: the target that achieved it.
GROWTH_BEST = CurvePlotSpec(
    source=SOURCE,
    metric="time_ms",
    curve_keys=["struct_symbol", "version"],
    select_best=NODE_BYTES,
    text_key=NODE_BYTES,
    log_y=True,
)

#: Case B — one curve per (structure, version, target node size).
GROWTH_PER_TARGET = CurvePlotSpec(
    source=SOURCE,
    metric="time_ms",
    curve_keys=["struct_symbol", "version", NODE_BYTES],
    text_key=NODE_BYTES,
    log_x=True,
    log_y=True,
)

#: Trade-off — one point per swept configuration (target node size × record
#: count), one series per (structure, version), each point labeled with its node
#: size.  The non-dominated lower-left region is the Pareto set (implicit: not
#: drawn).
TRADEOFF = PairPlotSpec(
    x_metric="overhead_per_key",
    y_metric="time_ms",
    point_keys=[PROGRESS_KEY, NODE_BYTES],
    color_keys=["struct_symbol", "version"],
    text_key=NODE_BYTES,
    log_x=True,
    log_y=True,
)

__all__ = ["GROWTH_BEST", "GROWTH_PER_TARGET", "MEASURE_KEY", "TRADEOFF"]
