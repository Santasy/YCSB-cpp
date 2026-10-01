"""
The streamlit end of the read phase — run with ``streamlit run``:

    .cache/plot-venv/bin/streamlit run tools/plot_all_workloads.py
    .cache/plot-venv/bin/streamlit run -m ycsb_bench.app

Composition only: the shell (sidebar + one tab per project tab) is the generic
``benchgrid.plots.app.run``, the declarations are :mod:`.adapter` and the tab
list :mod:`.tabs`.  Point it at a result tree of the run phase with
``YCSB_BENCH_DATA_DIRS=<root>[:<root>]``.
"""

from .adapter import adapter
from .tabs import TABS


def run_app() -> None:
    """Entry point for ``streamlit run`` — delegates to the generic shell."""
    from benchgrid.plots.app import run  # noqa: PLC0415

    run(adapter, TABS)


if __name__ == "__main__":
    run_app()

__all__ = ["TABS", "adapter", "run_app"]
