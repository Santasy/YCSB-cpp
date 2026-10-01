#!/usr/bin/env python3
"""
Golden check for the dry-run matrix.

Runs the CLI in dry-run mode, normalizes machine-specific paths out of the
rendered commands, and compares the result with the committed fixture in
``fixtures/golden_dry_run.json``. Worker counts are not stored verbatim (they
depend on the host CPU count) but are checked against the CPU-budget formula
instead, and the SEED freeze grouping is checked against the plan tags.

Usage::

    python3 tools/ycsb_bench/tests/check_golden_dry_run.py            # check
    python3 tools/ycsb_bench/tests/check_golden_dry_run.py --update   # rewrite
"""

import json
import re
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parents[1]
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from ycsb_bench.builds import build_plan  # noqa: E402
from ycsb_bench.cli import CPU_RESERVE, pool_workers  # noqa: E402
from ycsb_bench.paths import root_path  # noqa: E402
from ycsb_bench.runs import dimensions, make_targets, run_plan  # noqa: E402
from ycsb_bench.specs import tree_specs  # noqa: E402
from ycsb_bench.workloads import select_workloads  # noqa: E402

FIXTURE = TESTS_DIR / "fixtures" / "golden_dry_run.json"

DRY_RUN_ARGS = [
    "--dry-run",
    "--ds", "btree", "wtree", "std",
    "--node-sizes", "256",
    "--seeds", "1", "2",
    "--workloads", "workload_kv_session",
    "--insert-orders", "ordered", "hashed",
    "--hash-algos", "fnv",
    "--recordcount", "10",
    "--operationcount", "10",
    "--no-status",
    "--output-dir", ".cache/golden/output",
    "--binary-root", ".cache/golden/binaries",
]

COMMAND_LINE = re.compile(r"^\[(?P<label>build|run)\]\s+(?P<id>\d+): (?P<cmd>.*)$")
POOL_LINE = re.compile(
    r"^=== (?P<kind>Build|Run) pool: (?P<count>\d+) command\(s\), "
    r"(?P<workers>\d+) worker\(s\) ===$"
)


def normalize(text: str) -> str:
    return text.replace(str(ROOT), "${ROOT}")


def render_dry_run() -> str:
    result = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "run_all_workloads.py"), *DRY_RUN_ARGS],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def parse(output: str) -> dict[str, object]:
    commands: dict[str, list[str]] = {"build": [], "run": []}
    pools: dict[str, dict[str, int]] = {}
    for raw_line in output.splitlines():
        line = normalize(raw_line)
        command_match = COMMAND_LINE.match(line)
        if command_match:
            commands[str(command_match["label"])].append(str(command_match["cmd"]))
            continue
        pool_match = POOL_LINE.match(line)
        if pool_match:
            kind = str(pool_match["kind"]).lower()
            pools[kind] = {
                "count": int(pool_match["count"]),
                "workers": int(pool_match["workers"]),
            }
    return {"commands": commands, "pools": pools}


def check_pool_budgets(pools: dict[str, dict[str, int]]) -> list[str]:
    failures: list[str] = []
    for kind, entry in pools.items():
        expected = pool_workers(None, entry["count"])
        if entry["workers"] != expected:
            failures.append(
                f"{kind} pool used {entry['workers']} workers, "
                f"expected {expected} (cpus - {CPU_RESERVE}, capped by count)"
            )
    return failures


def check_seed_freeze() -> list[str]:
    from benchgrid import freeze_groups

    specs = tree_specs()
    workloads = select_workloads(["workload_kv_session"], ROOT / "workloads", False)
    grid = dimensions(["ordered", "hashed"], ["fnv"], [1, 2])
    binary_root = root_path(".cache/golden/binaries")
    output_dir = ROOT / ".cache/golden/output"
    dataset_dir = output_dir / "datasets"
    commands = []
    for name in ("btree", "wtree", "std"):
        spec = specs[name]
        node_size = 256 if spec.node_env is not None else None
        targets = make_targets(
            spec, node_size, workloads, grid, output_dir, dataset_dir
        )
        commands.extend(
            run_plan(
                spec,
                node_size,
                targets,
                binary_root,
                10,
                10,
                False,
                "csv",
                [],
                False,
            ).build_commands()
        )
    seeds = [command.tags.get("SEED") for command in commands]
    if len(seeds) != 12:
        return [f"rendered {len(seeds)} run commands, expected 12"]
    if sorted(set(seeds)) != ["1", "2"]:
        return [f"SEED tags are {sorted(set(seeds))}, expected ['1', '2']"]
    groups = freeze_groups(commands, "SEED")
    keys = [key for key, _ in groups]
    if keys != ["1", "2"]:
        return [
            f"SEED freeze order is {keys}, expected ['1', '2'] "
            "(all seed=1 commands across trees before any seed=2)"
        ]
    sizes = [len(group) for _, group in groups]
    if sizes != [6, 6]:
        return [f"SEED group sizes are {sizes}, expected [6, 6]"]
    return []


def check_build_plan_cwd() -> list[str]:
    spec = tree_specs()["btree"]
    plan = build_plan(
        spec, (256,), ROOT / ".cache/golden/output", ROOT / ".cache/golden/binaries",
        "Release", 3,
    )
    commands = plan.build_commands()
    if len(commands) != 1:
        return [f"btree build plan rendered {len(commands)} commands, expected 1"]
    if commands[0].cwd is None or str(commands[0].cwd) != str(ROOT):
        return [f"build command cwd is {commands[0].cwd}, expected {ROOT}"]
    return []


def main(argv: list[str]) -> int:
    parsed = parse(render_dry_run())
    failures = check_pool_budgets(parsed["pools"])
    failures += check_seed_freeze()
    failures += check_build_plan_cwd()

    fixture = {
        "args": DRY_RUN_ARGS,
        "commands": parsed["commands"],
        "pool_counts": {kind: entry["count"] for kind, entry in parsed["pools"].items()},
        "seed_groups": ["1", "2"],
    }

    if "--update" in argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {FIXTURE}")
    else:
        if not FIXTURE.is_file():
            print(f"missing fixture: {FIXTURE}", file=sys.stderr)
            return 1
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for key in ("commands", "pool_counts", "seed_groups"):
            if expected.get(key) != fixture[key]:
                print(f"golden mismatch in '{key}':", file=sys.stderr)
                print(f"  expected: {json.dumps(expected.get(key))[:400]}", file=sys.stderr)
                print(f"  actual:   {json.dumps(fixture[key])[:400]}", file=sys.stderr)
                failures.append(f"golden mismatch in '{key}'")

    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)
    if failures:
        return 1
    print("golden dry run ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
