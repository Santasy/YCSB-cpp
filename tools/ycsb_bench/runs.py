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

from .naming import (
    LOGS_DIR,
    RESULTS_DIR,
    dataset_folder,
    run_name,
    structure_folder,
    variant_label,
)
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


def declared_count(workload: Path, key: str) -> int | None:
    """The value a workload file declares for *key*, so the dataset path can name it."""
    if not workload.is_file():
        return None
    for line in workload.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def make_targets(
    spec: TreeSpec,
    node_size: int | None,
    workloads: Sequence[Path],
    grid: Sequence[tuple[str | None, str | None, int]],
    output_dir: Path,
    dataset_dir: Path,
    recordcount: int | None = None,
    operationcount: int | None = None,
) -> list[RunTarget]:
    if spec.node_env is None:
        node_size = None
    targets: list[RunTarget] = []
    for workload in workloads:
        # The effective counts: the command line wins, else what the workload
        # declares, so the dataset folder says which dataset it holds.
        run_records = (
            recordcount
            if recordcount is not None
            else declared_count(workload, "recordcount")
        )
        run_ops = (
            operationcount
            if operationcount is not None
            else declared_count(workload, "operationcount")
        )
        for insert_order, hash_algo, seed in grid:
            name = run_name(workload.name, insert_order, hash_algo, seed)
            structure = structure_folder(spec.name)
            folder = variant_label(node_size)
            result = output_dir / RESULTS_DIR / structure / folder / f"{name}.csv"
            target_dataset = dataset_dir / dataset_folder(name, run_records, run_ops)
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
    dataset_only: bool = False,
) -> WorkPlan:
    # ``-datasets`` writes both dataset files and stops; ``-load -run`` would
    # also build the index and execute every operation, which is the measured
    # stage's job, not the preparation stage's.
    fixed = [
        *(("-datasets",) if dataset_only else ("-load", "-run")),
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


def dataset_pool(
    commands: Sequence[WorkCommand], workers: int | None, cpu_reserve: int
) -> CommandPool:
    """
    The dataset-generation pool: labelled apart, and wide open.

    Every target owns a dataset path that nothing else writes -- the path spells
    out workload, insert order, hash algo, seed and both counts -- so one
    generator per workload and seed is race free and the pool can take the whole
    worker budget instead of crawling one dataset at a time.

    ``workers`` is the ceiling for that budget, not a fixed count.  ``-datasets``
    only streams the files out, so a generator costs a few MB of RSS whatever the
    record count; lower it only when the workers compete for page cache on the
    dataset files themselves.
    """
    return CommandPool(
        name="datasets",
        commands=commands,
        threads=workers,
        cpu_reserve=cpu_reserve,
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
