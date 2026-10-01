"""
The BenchGrid imports the analysis layer needs, in one place.

``tools/BenchGrid`` is an editable checkout, not an installed package, so the
runner's bridge (:mod:`..benchgrid_bridge`) is imported first for its
``sys.path`` side effect.  Only the *streamlit-free* parts of the engine are
re-exported here; the viewer shell stays in :mod:`.app` so the headless CLI can
import the data layer without pulling streamlit in.
"""

from __future__ import annotations

# This one import must run *before* the BenchGrid ones below: importing the
# runner's bridge is what puts the editable tools/BenchGrid checkout on sys.path.
from .. import benchgrid_bridge  # noqa: I001
from benchgrid import Dataset, Matrix, read_schemas, scan_csv_lazy
from benchgrid.plots.adapter import PlotsAdapter, Tab
from benchgrid.plots.coloring import Coloring
from benchgrid.plots.context import TabContext
from benchgrid.plots.curves import CurvePlotSpec
from benchgrid.plots.pairs import PairPlotSpec
from benchgrid.schema import ScanSchema

__all__ = [
    "BENCHGRID_ROOT",
    "Coloring",
    "CurvePlotSpec",
    "Dataset",
    "Matrix",
    "PairPlotSpec",
    "PlotsAdapter",
    "ScanSchema",
    "Tab",
    "TabContext",
    "read_schemas",
    "scan_csv_lazy",
]

BENCHGRID_ROOT = benchgrid_bridge.BENCHGRID_ROOT
