"""
Streamlit composition for the YCSB-cpp plot viewer.

Composition only — the shell (sidebar + one tab per project tab) is the generic
``benchgrid.plots.app.run``; the adapter (:mod:`.adapter`) holds the workload's
declarations and :mod:`.tabs` holds the tab list.  Run either entry point:

    .cache/plot-venv/bin/streamlit run tools/plot_all_workloads.py
    .cache/plot-venv/bin/streamlit run tools/ycsb_bench/analysis/app.py

Point the viewer at a result tree with ``YCSB_BENCH_DATA_DIRS=<root>[:<root>]``.
"""

from __future__ import annotations

from .adapter import adapter, run_app

if __name__ == "__main__":
    run_app()

__all__ = ["adapter", "run_app"]
