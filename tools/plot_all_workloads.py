#!/usr/bin/env python3
"""Read end of the pipeline: the streamlit view over a result tree.

The run end stays in ``tools/run_all_workloads.py``; this is where its output
becomes plots — the viewer shell is BenchGrid's, the declarations and tabs are
``ycsb_bench``:

    .cache/plot-venv/bin/streamlit run tools/plot_all_workloads.py

Scans the result trees the run phase writes (override with
``YCSB_BENCH_DATA_DIRS=<root>[:<root>]``) and shows one measure per operation
type plus load/total, per workload, per structure version and target node size.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ycsb_bench.app import run_app  # noqa: E402

if __name__ == "__main__":
    run_app()
