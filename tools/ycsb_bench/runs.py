"""Run matrix: workloads x insert orders x hash algorithms x seeds."""

import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from benchgrid import (
    ArgsJoinPolicy,
    CommandPool,
    IterationPolicy,
    WorkCommand,
    WorkPlan,
    WorkRecord,
)

from .naming import LOGS_DIR, RESULTS_DIR, run_name, structure_folder, variant_label
from .paths import ROOT
from .specs import TreeSpec, binary_path

FREEZE_KEY = "SEED"


@dataclass(frozen=True)
class RunTarget:
    workload: Path
    insert_order: str | None
    hash_algo: str | None
    seed: int
    result: Path
    dataset: Path
    log: Path


def dimensions(
    insert_orders: Sequence[str] | None,
    hash_algos: Sequence[str] | None,
    seeds: Sequence[int],
) -> list[tuple[str | None, str | None, int]]:
    orders: Sequence[str | None] = insert_orders or (None,)
    algos: Sequence[str | None] = hash_algos or (None,)
    return [
        (order, algo, seed)
        for order in orders
        for algo in algos
        for seed in seeds
    ]


def make_targets(
    spec: TreeSpec,
    node_size: int | None,
    workloads: Sequence[Path],
    grid: Sequence[tuple[str | None, str | None, int]],
    output_dir: Path,
    dataset_dir: Path,
) -> list[RunTarget]:
    if spec.node_env is None:
        node_size = None
    targets: list[RunTarget] = []
    for workload in workloads:
        for insert_order, hash_algo, seed in grid:
            name = run_name(workload.name, insert_order, hash_algo, seed)
            structure = structure_folder(spec.name)
            folder = variant_label(node_size)
            result = output_dir / RESULTS_DIR / structure / folder / f"{name}.csv"
            target_dataset = dataset_dir / structure / folder / name
            log = output_dir / LOGS_DIR / f"{structure}-{folder}-{name}.log"
            targets.append(
                RunTarget(
                    workload=workload,
                    insert_order=insert_order,
                    hash_algo=hash_algo,
                    seed=seed,
                    result=result,
                    dataset=target_dataset,
                    log=log,
                )
            )
    return targets


def _shell_join(parts: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def run_plan(
    spec: TreeSpec,
    node_size: int | None,
    targets: Sequence[RunTarget],
    binary_root: Path,
    recordcount: int | None,
    operationcount: int | None,
    force_generate: bool,
    result_format: str,
    extra_properties: Sequence[Path],
    status: bool,
) -> WorkPlan:
    fixed = [
        "-load",
        "-run",
        "-db",
        spec.dbname,
        "-threads",
        "1",
        "-P",
        str(spec.properties),
    ]
    records: list[WorkRecord] = []
    for target in targets:
        args = ["-P", str(target.workload)]
        for properties in extra_properties:
            args.extend(("-P", str(properties)))
        if target.insert_order is not None:
            args.extend(("-p", f"insertorder={target.insert_order}"))
        if target.hash_algo is not None:
            args.extend(("-p", f"hashalgo={target.hash_algo}"))
        if recordcount is not None:
            args.extend(("-p", f"recordcount={recordcount}"))
        if operationcount is not None:
            args.extend(("-p", f"operationcount={operationcount}"))
        args.extend(
            (
                "-p",
                f"seed={target.seed}",
                "-p",
                f"dataset_path={target.dataset}",
                "-p",
                f"force_generate={str(force_generate).lower()}",
                "-p",
                f"resultformat={result_format}",
                "-p",
                f"output.file={target.result}",
                "-p",
                "threadcount=1",
            )
        )
        if status:
            args.append("-s")
        suffix = _shell_join(args)
        suffix += f" > {shlex.quote(str(target.log))} 2>&1"
        records.append(WorkRecord({"ARGS": suffix}, {FREEZE_KEY: str(target.seed)}))

    return WorkPlan(
        workdir=ROOT,
        program=shlex.quote(str(binary_path(binary_root, spec, node_size))),
        args_join=ArgsJoinPolicy.POSITIONAL,
        fixed=tuple(shlex.quote(part) for part in fixed),
        grid=records,
        parallel=True,
        single_core=True,
        iteration=IterationPolicy.FREEZE_DIMENSION,
        freeze_key=FREEZE_KEY,
    )


def run_pool(
    commands: Sequence[WorkCommand], workers: int | None, cpu_reserve: int
) -> CommandPool:
    return CommandPool(
        name="run",
        commands=commands,
        threads=workers,
        cpu_reserve=cpu_reserve,
        iteration=IterationPolicy.FREEZE_DIMENSION,
        freeze_key=FREEZE_KEY,
    )
