#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

structure_names = {
    "btree": "btree",
    "wtree": "wtree",
    "std": "std::map",
}
structure_order = {"btree": 0, "wtree": 1, "std::map": 2}
seed_pattern = re.compile(r"^(?P<workload>.+)-seed-(?P<seed>[0-9]+)$")
prefix_pattern = re.compile(r"^(?P<prefix>bt|wt|std)-(?P<variant>[^.-]+)(?:-.*)?$")
prefix_names = {"bt": "btree", "wt": "wtree", "std": "std::map"}


def layout(path: Path) -> tuple[str, str, str, int | None] | None:
    seed_match = seed_pattern.fullmatch(path.stem)
    if seed_match:
        workload = seed_match.group("workload")
        seed: int | None = int(seed_match.group("seed"))
    else:
        seed = None
        workload = path.stem

    parts = path.parts
    for index, part in enumerate(parts):
        if part not in structure_names:
            continue
        variant = "default"
        if index + 1 < len(parts) - 1:
            variant = parts[index + 1]
        return structure_names[part], variant, workload, seed

    prefix_match = prefix_pattern.match(path.stem)
    if prefix_match is not None:
        return (
            prefix_names[prefix_match.group("prefix")],
            prefix_match.group("variant"),
            workload,
            seed,
        )
    return None


def schema_for(path: Path) -> list[str] | None:
    schema_path = path.parent / "schema.csv"
    if not schema_path.is_file():
        return None
    with schema_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.reader(stream):
            if row:
                return row
    return None


def numeric_value(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_value(value: float) -> str:
    if value == 0:
        return "0"
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def collect(input_dir: Path, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    groups: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    metric_fields: list[str] = []
    seen_metric_fields: set[str] = set()
    file_count = 0
    skipped = 0

    for path in sorted(input_dir.rglob("*.csv")):
        if path.name == "schema.csv" or path.resolve() == output_file:
            continue
        metadata = layout(path)
        if metadata is None:
            skipped += 1
            continue
        structure, variant, workload, seed = metadata
        header = schema_for(path)
        if header is None:
            skipped += 1
            continue
        if len(header) < 2 or header[0] != "phase" or header[1] != "operation":
            skipped += 1
            continue

        file_count += 1
        try:
            stream = path.open(newline="", encoding="utf-8")
        except OSError as error:
            print(f"warning: cannot read {path}: {error}", file=sys.stderr)
            skipped += 1
            file_count -= 1
            continue

        with stream:
            for row in csv.reader(stream):
                if not row or not any(value.strip() for value in row):
                    continue
                if len(row) < 2:
                    continue
                phase, operation = row[0], row[1]
                key = (structure, variant, workload, phase, operation)
                group = groups.setdefault(
                    key,
                    {"seeds": set(), "values": defaultdict(list)},
                )
                group["seeds"].add(seed)
                values = group["values"]
                for field, value in zip(header[2:], row[2:]):
                    if field not in seen_metric_fields:
                        seen_metric_fields.add(field)
                        metric_fields.append(field)
                    number = numeric_value(value)
                    if number is not None:
                        values[field].append(number)

    if file_count == 0:
        raise SystemExit(f"no seed result CSV files found under {input_dir}")

    fieldnames = [
        "structure",
        "variant",
        "workload",
        "phase",
        "operation",
        "seed_count",
        *metric_fields,
    ]

    with output_file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for (structure, variant, workload, phase, operation), group in sorted(
            groups.items(),
            key=lambda item: (
                structure_order.get(item[0][0], 99),
                int(item[0][1]) if item[0][1].isdigit() else 0,
                item[0][1],
                item[0][2],
                0 if item[0][3] == "load" else 1,
                item[0][3],
                item[0][4],
            ),
        ):
            row = {
                "structure": structure,
                "variant": variant,
                "workload": workload,
                "phase": phase,
                "operation": operation,
                "seed_count": len(group["seeds"]),
            }
            for field in metric_fields:
                values = group["values"].get(field, [])
                row[field] = format_value(sum(values) / len(values)) if values else ""
            writer.writerow(row)

    print(
        f"wrote {len(groups)} averaged rows from {file_count} files "
        f"to {output_file}"
    )
    if skipped:
        print(f"skipped {skipped} files", file=sys.stderr)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} INPUT_DIR OUTPUT_FILE", file=sys.stderr)
        return 2
    input_dir = Path(sys.argv[1]).expanduser().resolve()
    output_file = Path(sys.argv[2]).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"input directory not found: {input_dir}", file=sys.stderr)
        return 1
    collect(input_dir, output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
