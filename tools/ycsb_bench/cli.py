"""Command line surface: flags, path resolution and pool orchestration."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .benchgrid_bridge import available_cpus, resolve_thread_count
from .builds import build_plan, build_pool
from .runs import dimensions, make_targets, run_plan, run_pool
from .specs import (
    DEFAULT_NODE_SIZES,
    TreeSpec,
    binary_path,
    root_path,
    tree_specs,
    variants_for,
    variant_label,
)
from .workloads import select_workloads

DEFAULT_SEEDS = tuple(range(1, 31))
CPU_RESERVE = 2


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def pool_workers(requested: int | None, command_count: int) -> int:
    return resolve_thread_count(
        requested, cpu_reserve=CPU_RESERVE, command_count=command_count
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build data-structure binaries and run their workloads."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument(
        "--ds",
        help="Select Data-structures (btree, wtree, std)",
        nargs="+",
        choices=("btree", "wtree", "std"),
        default=("btree", "wtree", "std"),
    )
    parser.add_argument(
        "--node-sizes",
        nargs="+",
        type=positive_int,
        default=list(DEFAULT_NODE_SIZES),
        help="Node-size variants for btree/wtree; ignored for std::map.",
    )
    parser.add_argument("--workloads", nargs="+")
    parser.add_argument("--workload-dir", default="workloads")
    parser.add_argument("--include-db-only", action="store_true")
    parser.add_argument(
        "--insert-orders",
        "--insert-order",
        nargs="+",
        choices=("ordered", "hashed"),
    )
    parser.add_argument(
        "--hash-algos",
        "--hash-algo",
        nargs="+",
        choices=("fnv", "sha256"),
    )
    parser.add_argument("--recordcount", type=positive_int)
    parser.add_argument("--operationcount", type=positive_int)
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        help="Seeds for each workload run; defaults to 1..30.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Run one seed; overrides --seeds for compatibility.",
    )
    parser.add_argument("--force-generate", action="store_true")
    parser.add_argument("--extra-properties", action="append", default=[])
    parser.add_argument("--result-format", choices=("csv", "human"), default="csv")
    parser.add_argument("--no-status", action="store_true")
    parser.add_argument("--output-dir", default=".cache/run_all_workloads")
    parser.add_argument("--dataset-dir")
    parser.add_argument("--binary-root", default=".")
    parser.add_argument(
        "--build-type", default=os.environ.get("CMAKE_BUILD_TYPE", "Release")
    )
    parser.add_argument(
        "--build-workers",
        type=positive_int,
        help="Build-pool workers; defaults to available CPUs minus two.",
    )
    parser.add_argument(
        "--build-jobs",
        type=positive_int,
        help="Compiler jobs per build; capped to keep two CPUs free.",
    )
    parser.add_argument(
        "--threads",
        type=positive_int,
        help="Run-pool workers; defaults to available CPUs minus two.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def unique(values: Sequence[int]) -> list[int]:
    result: list[int] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def resolve_extra_properties(values: Sequence[str]) -> list[Path]:
    result: list[Path] = []
    for value in values:
        path = root_path(value)
        if not path.is_file():
            raise ValueError(f"properties file not found: {path}")
        result.append(path)
    return result


def _prepare_directories(
    output_dir: Path,
    dataset_dir: Path,
    build_matrix: Sequence[tuple[TreeSpec, tuple[int | None, ...]]],
    workloads: Sequence[Path],
    grid: Sequence[tuple[str | None, str | None, int]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (output_dir / "build").mkdir(parents=True, exist_ok=True)
    for spec, variants in build_matrix:
        for node_size in variants:
            for target in make_targets(
                spec, node_size, workloads, grid, output_dir, dataset_dir
            ):
                target.result.parent.mkdir(parents=True, exist_ok=True)
                target.log.parent.mkdir(parents=True, exist_ok=True)
                target.dataset.mkdir(parents=True, exist_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        specs = tree_specs()
        selected_trees = [specs[name] for name in dict.fromkeys(args.ds)]
        node_sizes = unique(args.node_sizes)
        seed_values = (
            [args.seed]
            if args.seed is not None
            else (args.seeds if args.seeds is not None else DEFAULT_SEEDS)
        )
        seeds = unique(seed_values)
        output_dir = root_path(args.output_dir)
        dataset_dir = (
            root_path(args.dataset_dir) if args.dataset_dir else output_dir / "datasets"
        )
        binary_root = root_path(args.binary_root)
        workload_dir = root_path(args.workload_dir)
        extra_properties = resolve_extra_properties(args.extra_properties)
        workloads = (
            []
            if args.skip_run
            else select_workloads(
                args.workloads, workload_dir, args.include_db_only
            )
        )
        grid = dimensions(args.insert_orders, args.hash_algos, seeds)
        build_matrix = [
            (spec, variants_for(spec, node_sizes)) for spec in selected_trees
        ]
        build_count = sum(len(variants) for _, variants in build_matrix)
        build_workers = pool_workers(args.build_workers, build_count)
        max_build_jobs = max(1, available_cpus(CPU_RESERVE) // build_workers)
        build_jobs = (
            min(args.build_jobs, max_build_jobs)
            if args.build_jobs is not None
            else max_build_jobs
        )

        if not args.dry_run:
            _prepare_directories(
                output_dir, dataset_dir, build_matrix, workloads, grid
            )

        if not args.skip_build:
            build_commands = []
            for spec, variants in build_matrix:
                plan = build_plan(
                    spec,
                    variants,
                    output_dir,
                    binary_root,
                    args.build_type,
                    build_jobs,
                )
                build_commands.extend(plan.build_commands())
                if spec.node_env is None:
                    print(f"\n=== Build {spec.name} ===")
                else:
                    print(f"\n=== Build {spec.name}: {len(variants)} variant(s) ===")
            if build_commands:
                pool = build_pool(build_commands, build_workers, CPU_RESERVE)
                print(
                    f"\n=== Build pool: {len(build_commands)} command(s), "
                    f"{pool.resolved_threads()} worker(s) ==="
                )
                rc = pool.run(dry_run=args.dry_run, verbose=args.verbose)
                if rc != 0:
                    return rc

        if not args.skip_run:
            run_commands = []
            for spec, variants in build_matrix:
                for node_size in variants:
                    binary = binary_path(binary_root, spec, node_size)
                    if not args.dry_run and not binary.is_file():
                        raise FileNotFoundError(f"variant binary not found: {binary}")
                    targets = make_targets(
                        spec,
                        node_size,
                        workloads,
                        grid,
                        output_dir,
                        dataset_dir,
                    )
                    if not targets:
                        continue
                    plan = run_plan(
                        spec,
                        node_size,
                        targets,
                        binary_root,
                        args.recordcount,
                        args.operationcount,
                        args.force_generate,
                        args.result_format,
                        extra_properties,
                        not args.no_status,
                    )
                    run_commands.extend(plan.build_commands())
                    print(
                        f"\n=== Run {spec.name} ({variant_label(node_size)}): "
                        f"{len(targets)} workload command(s) ==="
                    )
            if run_commands:
                pool = run_pool(
                    run_commands, args.threads, cpu_reserve=CPU_RESERVE
                )
                print(
                    f"\n=== Run pool: {len(run_commands)} command(s), "
                    f"{pool.resolved_threads()} worker(s) ==="
                )
                rc = pool.run(dry_run=args.dry_run, verbose=args.verbose)
                if rc != 0:
                    return rc

        print("\nFinished.")
        return 0
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
