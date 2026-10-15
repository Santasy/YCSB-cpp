"""
The streamlit end of the read phase — run with ``streamlit run``:

    .cache/plot-venv/bin/streamlit run tools/plot_all_workloads.py
    .cache/plot-venv/bin/streamlit run -m ycsb_bench.app

Composition only: the shell (sidebar + one tab per project tab) is the generic
``benchgrid.plots.app.run``, the declarations are :mod:`.adapter` and the tab
list :mod:`.tabs`.  Point it at a result tree of the run phase with
``YCSB_BENCH_DATA_DIRS=<root>[:<root>]``.
"""

import argparse
from collections.abc import Sequence

from benchgrid.plots.app import run

from .adapter import adapter, build_adapter
from .tabs import TABS
from .paths import DEFAULT_OUTPUT_DIR, DEFAULT_DATA_DIRS


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build data-structure binaries and run their workloads."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args(argv)


def run_app(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``streamlit run`` — delegates to the generic shell."""

    args = parse_args(argv)
    _adapter = build_adapter(dirs=[args.output_dir])

    run(_adapter, TABS)
    return 0


if __name__ == "__main__":
    run_app()

__all__ = ["TABS", "adapter", "run_app"]
