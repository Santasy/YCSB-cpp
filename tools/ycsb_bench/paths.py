"""
Where things live — the one place both ends of the pipeline resolve paths from.

The run end writes under an output directory (:data:`DEFAULT_OUTPUT_DIR`, the
``--output-dir`` of ``tools/run_all_workloads.py``) and the read end scans the
result roots inside it (:data:`DEFAULT_DATA_DIRS`, overridable with
``$YCSB_BENCH_DATA_DIRS``), so a fresh run shows up in the plot viewer with no
extra flags.  Relative paths from the command line are resolved against the
repository root (:func:`root_path`).
"""

from __future__ import annotations

import os
from pathlib import Path

from . import BENCHGRID_DIR

_HERE = Path(__file__).resolve().parent  # tools/ycsb_bench/
TOOLS_DIR = _HERE.parent  # tools/
ROOT = TOOLS_DIR.parent  # repo root

#: The shared scan schema: the folder/file layout of a YCSB result tree.
#: Expected layout:
#:   <root>/<struct_version>/<node_size>/<run_id>-seed-<seed>.csv
SCHEMA_FILE: Path = TOOLS_DIR / "ycsb.schema.json"

#: Environment override for the scanned roots (os.pathsep-separated).
DATA_DIRS_ENV = "YCSB_BENCH_DATA_DIRS"

#: Where a run writes by default (run phase) — results, logs, build, datasets.
DEFAULT_OUTPUT_DIR: Path = ROOT / "storage"

#: Roots scanned by default (read phase): the run phase's result tree.
DEFAULT_DATA_DIRS: list[str] = [str(DEFAULT_OUTPUT_DIR / "results")]

#: Where the questions CLI writes its CSV tables by default.
OUTPUT_DIR: Path = _HERE / "output"


def root_path(value: str | Path) -> Path:
    """*value* as an absolute path, relative paths resolved against the repo root."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def data_dirs() -> list[str]:
    """The result roots to scan: ``$YCSB_BENCH_DATA_DIRS`` or :data:`DEFAULT_DATA_DIRS`."""
    raw = os.environ.get(DATA_DIRS_ENV, "")
    if raw.strip():
        parts = (piece.strip() for piece in raw.split(os.pathsep))
        return [part for part in parts if part]
    return list(DEFAULT_DATA_DIRS)


__all__ = [
    "BENCHGRID_DIR",
    "DATA_DIRS_ENV",
    "DEFAULT_DATA_DIRS",
    "DEFAULT_OUTPUT_DIR",
    "OUTPUT_DIR",
    "ROOT",
    "SCHEMA_FILE",
    "TOOLS_DIR",
    "data_dirs",
    "root_path",
]
