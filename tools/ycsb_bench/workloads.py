"""Workload discovery and data-structure compatibility filtering."""

import sys
from collections.abc import Sequence
from pathlib import Path

from .paths import ROOT

DATA_STRUCTURE_KINDS = frozenset({"ds", "datastructure"})


def adapter_kinds(path: Path) -> set[str]:
    kinds: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return kinds
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.strip() == "adapter.kinds":
            kinds.update(
                token.strip().lower() for token in value.split(",") if token.strip()
            )
    return kinds


def workload_path(value: str, workload_dir: Path) -> Path:
    path = Path(value).expanduser()
    candidates: list[Path]
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = [ROOT / path, workload_dir / path, Path.cwd() / path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError(f"workload file not found: {value}")


def discover_workloads(workload_dir: Path) -> list[Path]:
    if not workload_dir.is_dir():
        raise ValueError(f"workload directory not found: {workload_dir}")
    return sorted(
        (
            path.resolve()
            for path in workload_dir.iterdir()
            if path.is_file()
            and path.name.startswith("workload")
            and path.suffix != ".properties"
        ),
        key=lambda path: path.name,
    )


def select_workloads(
    values: Sequence[str] | None,
    workload_dir: Path,
    include_db_only: bool,
) -> list[Path]:
    if values is None:
        candidates = discover_workloads(workload_dir)
        explicit = False
    else:
        candidates = []
        for value in values:
            path = workload_path(value, workload_dir)
            if path not in candidates:
                candidates.append(path)
        explicit = True

    selected: list[Path] = []
    skipped: list[Path] = []
    for path in candidates:
        kinds = adapter_kinds(path)
        compatible = not kinds or bool(kinds.intersection(DATA_STRUCTURE_KINDS))
        if compatible or include_db_only:
            selected.append(path)
        else:
            skipped.append(path)

    if skipped:
        names = ", ".join(path.name for path in skipped)
        if explicit and not include_db_only:
            raise ValueError(
                f"selected workloads require a database adapter: {names}; "
                "choose data-structure-compatible workloads or use --include-db-only"
            )
        print(f"Skipping database-only workloads: {names}", file=sys.stderr)
    if not selected:
        raise ValueError("no data-structure-compatible workloads selected")
    return selected
