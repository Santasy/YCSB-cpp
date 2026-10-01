"""
Centralized folder/file configuration for the YCSB-cpp analysis.

Everything derives from this file's location, so the layer keeps working when
the repo moves.  The schema JSON is a shared artifact under ``tools/`` (reused
by the headless CLI in :mod:`.cli`), and the data roots are overridable with
``YCSB_BENCH_DATA_DIRS`` (os.pathsep-separated) so a sweep can be viewed
without editing code.
"""

from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # tools/ycsb_bench/analysis/
TOOLS_DIR = _HERE.parents[1]  # tools/
ROOT = TOOLS_DIR.parent  # repo root
BENCHGRID_DIR = TOOLS_DIR / "BenchGrid"

#: The shared scan schema: the folder/file layout of a YCSB result tree.
#: Expected layout:
#:   <root>/<struct_version>/<node_size>/<run_id>-seed-<seed>.csv
SCHEMA_FILE: Path = TOOLS_DIR / "ycsb.schema.json"

#: Environment override for the scanned roots (os.pathsep-separated).
DATA_DIRS_ENV = "YCSB_BENCH_DATA_DIRS"

#: Roots scanned by default: where tools/run_all_workloads.py writes results.
DATA_DIRS: list[str] = [
    # str(ROOT / ".cache" / "run_all_workloads" / "results")
    str(ROOT / "storage" / "logen")
]

#: Where the question CLI writes its CSV tables by default.
OUTPUT_DIR: Path = _HERE / "output"


def data_dirs() -> list[str]:
    """The result roots to scan: ``$YCSB_BENCH_DATA_DIRS`` or :data:`DATA_DIRS`."""
    raw = os.environ.get(DATA_DIRS_ENV, "")
    if raw.strip():
        parts = (piece.strip() for piece in raw.split(os.pathsep))
        return [part for part in parts if part]
    return list(DATA_DIRS)


__all__ = [
    "BENCHGRID_DIR",
    "DATA_DIRS",
    "DATA_DIRS_ENV",
    "OUTPUT_DIR",
    "ROOT",
    "SCHEMA_FILE",
    "TOOLS_DIR",
    "data_dirs",
]
