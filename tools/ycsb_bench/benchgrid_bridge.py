"""Single place where the editable BenchGrid submodule is put on ``sys.path``."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCHGRID_ROOT = ROOT / "tools" / "BenchGrid"

if str(BENCHGRID_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCHGRID_ROOT))

try:
    from benchgrid import (
        ArgsJoinPolicy,
        CommandPool,
        IterationPolicy,
        WorkCommand,
        WorkPlan,
        WorkRecord,
        available_cpus,
        merge_plans,
        resolve_thread_count,
    )
except ImportError as exc:
    raise SystemExit(f"Cannot import BenchGrid from {BENCHGRID_ROOT}: {exc}") from exc

__all__ = [
    "BENCHGRID_ROOT",
    "ROOT",
    "ArgsJoinPolicy",
    "CommandPool",
    "IterationPolicy",
    "WorkCommand",
    "WorkPlan",
    "WorkRecord",
    "available_cpus",
    "merge_plans",
    "resolve_thread_count",
]
