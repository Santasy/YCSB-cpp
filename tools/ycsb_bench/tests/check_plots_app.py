"""
Streamlit smoke check of the YCSB-cpp plot viewer (headless ``AppTest``).

Runs ``tools/plot_all_workloads.py`` against the synthetic result tree built by
:mod:`check_analysis` — every tab rendered, no exception, the measure selector
present and opening on the default measure.  Run:

    .cache/plot-venv/bin/python tools/ycsb_bench/tests/check_plots_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tools/

TOOLS_DIR = Path(__file__).resolve().parents[2]
ROOT = TOOLS_DIR.parent
ENTRYPOINT = TOOLS_DIR / "plot_all_workloads.py"
TREE = ROOT / ".cache" / "ycsb_plot_check" / "results"

TAB_LABELS = [
    "Metrics",
    "Growth — best target size",
    "Growth — per target size",
    "Trade-off — time vs memory",
]


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")
    print(f"  ok  {message}")


def _by_label(widgets, label: str):
    """The first widget with *label* (AppTest widgets are unlabeled lists)."""
    for widget in widgets:
        if widget.label == label:
            return widget
    raise SystemExit(f"FAIL: no {label!r} widget in the app")


def main() -> None:
    from streamlit.testing.v1 import AppTest  # noqa: PLC0415 — streamlit is a leaf

    if not TREE.is_dir():
        raise SystemExit(f"missing {TREE}; run tools/ycsb_bench/tests/check_analysis.py first")
    os.environ["YCSB_BENCH_DATA_DIRS"] = str(TREE)

    at = AppTest.from_file(str(ENTRYPOINT), default_timeout=120)
    at.run()

    if at.exception:
        for exc in at.exception:
            print(exc.value)
        raise SystemExit("FAIL: the app raised")
    _check(not at.error, "no streamlit errors")
    _check(not at.exception, "no exception")

    labels = [tab.label for tab in at.tabs]
    _check(labels == TAB_LABELS, f"tabs rendered: {labels}")

    measures = [sb for sb in at.selectbox if sb.label == "Measure"]
    _check(bool(measures), f"measure selectors present ({len(measures)})")
    defaults = {sb.value for sb in measures}
    _check(
        defaults == {"run:total"},
        f"every measure selector opens on the default measure ({sorted(defaults)})",
    )
    options = {tuple(sb.options) for sb in measures}
    _check(
        options == {("load:total", "run:read", "run:total")},
        "measure options are the operation types plus load/total",
    )

    filters = {sb.label for sb in at.sidebar.selectbox}
    _check(
        {"workload", "struct_version", "node_size", "insert_order", "hash_algo"}
        <= filters,
        f"sidebar filters declared: {sorted(filters)}",
    )

    # A second run with other selections: another measure, a structure filter, a
    # metric that only a tree reports, and the slice colorings (min-max needs
    # matplotlib) — the paths ragged data has to survive.
    for sb in at.selectbox:
        if sb.label == "Measure":
            sb.select("load:total")
    _by_label(at.sidebar.selectbox, "struct_version").select("btree")
    _by_label(at.selectbox, "Metric").select("keys_per_leaf")
    for sb in at.selectbox:
        if sb.label == "Coloring":
            sb.select("Min-max gradient per slice")
    at.run()
    if at.exception:
        for exc in at.exception:
            print(exc.value)
        raise SystemExit("FAIL: the app raised on the second run")
    _check(not at.error and not at.exception, "second run clean (filters, measure, coloring)")
    _check(
        {sb.value for sb in at.selectbox if sb.label == "Measure"} == {"load:total"},
        "the measure selection sticks",
    )

    print("\nplots app check ok")


if __name__ == "__main__":
    main()
