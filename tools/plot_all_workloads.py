#!/usr/bin/env python3
"""
Streamlit entry point for the YCSB-cpp plot viewer.

The benchmark runner stays in ``tools/run_all_workloads.py``; this is its
plotting twin — the viewer shell is BenchGrid's, the declarations and tabs are
``ycsb_bench.analysis``:

    .cache/plot-venv/bin/streamlit run tools/plot_all_workloads.py

Reads the result trees of ``tools/run_all_workloads.py`` (override with
``YCSB_BENCH_DATA_DIRS=<root>[:<root>]``) and shows one measure per operation
type plus load/total, per workload, per structure version and target node size.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ycsb_bench.analysis.adapter import run_app  # noqa: E402

if __name__ == "__main__":
    run_app()
