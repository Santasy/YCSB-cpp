"""
The YCSB-cpp benchmark adapter: one pipeline, two ends.

    tools/run_all_workloads.py
        specs -> builds -> workloads -> runs -> cli     (BenchGrid plans/pools)
            |
            |  writes <output>/results/<structure>/<node size>/<run id>.csv
            v
        ycsb.schema.json — one merged time+memory schema for the whole tree
            |
            v
    tools/plot_all_workloads.py, python -m ycsb_bench.questions
        enrich -> dataset -> adapter -> curves -> tabs -> app, questions
                                                  (BenchGrid data/plots)

Shared vocabulary of the two ends, one implementation each:
:mod:`.naming` is the grammar of the tree (what the run end writes, what the
read end parses) and :mod:`.paths` is where everything lives — including the
output directory the run end writes and the result roots the read end scans.

The two ends stay separately importable on purpose: the runner needs only
BenchGrid's plan/pool side, the plot end its data/plots side (polars,
streamlit), and neither pulls in the other.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # tools/ycsb_bench/
TOOLS_DIR = _HERE.parent  # tools/

#: The editable BenchGrid checkout driving both ends of the pipeline.  BenchGrid
#: is a source checkout, not an installed package, so the package boundary is
#: where it goes on ``sys.path`` — every module below can then import it
#: directly, and only the modules that need it pay for it.
BENCHGRID_DIR = TOOLS_DIR / "BenchGrid"
if str(BENCHGRID_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHGRID_DIR))

from .cli import main  # noqa: E402 — the run end's entry point, needs the path above

__all__ = ["BENCHGRID_DIR", "TOOLS_DIR", "main"]
