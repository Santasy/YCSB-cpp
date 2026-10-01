"""How each data-structure variant is compiled and collected."""

import shlex
from collections.abc import Sequence
from pathlib import Path

from benchgrid import ArgsJoinPolicy, CommandPool, WorkCommand, WorkPlan

from .paths import ROOT
from .specs import TreeSpec, binary_dir

ENV_PASSTHROUGH = 'for arg in "$@"; do export "$arg"; done; '


def assignment_value(value: str | Path) -> str:
    return shlex.quote(str(value))


def build_program(spec: TreeSpec) -> str:
    if spec.build_script is not None:
        inner = (
            ENV_PASSTHROUGH
            + f'exec {shlex.quote(str(spec.build_script))} > "$BUILD_LOG" 2>&1'
        )
    else:
        build_dir = spec.build_dir_env
        collect_dir = spec.collect_dir_env
        build_type = spec.build_type_env
        inner = (
            ENV_PASSTHROUGH
            + "{ "
            f'cmake -S . -B "${build_dir}" '
            f'-DCMAKE_BUILD_TYPE="${build_type}" '
            "-DBIND_BTREE=OFF -DBIND_WTREE=OFF "
            f'&& cmake --build "${build_dir}" --target ycsb -j"$BUILD_JOBS" '
            f'&& mkdir -p "${collect_dir}" '
            f'&& cp "${build_dir}/ycsb" "${collect_dir}/ycsb-{spec.prefix}" '
            f'&& rm -r "${build_dir}"'
            '; } > "$BUILD_LOG" 2>&1'
        )
    return f"bash -c {shlex.quote(inner)} --"


def build_plan(
    spec: TreeSpec,
    variants: Sequence[int | None],
    output_dir: Path,
    binary_root: Path,
    build_type: str,
    build_jobs: int,
) -> WorkPlan:
    records: list[dict[str, str]] = []
    if spec.node_env is None:
        build_dir = output_dir / "build" / spec.prefix
        log = output_dir / "logs" / f"build-{spec.prefix}.log"
        records.append(
            {
                spec.build_dir_env: assignment_value(build_dir),
                spec.collect_dir_env: assignment_value(binary_dir(binary_root, spec)),
                spec.build_type_env: assignment_value(build_type),
                "BUILD_JOBS": assignment_value(build_jobs),
                "BUILD_LOG": assignment_value(log),
            }
        )
    else:
        for node_size in variants:
            if node_size is None:
                continue
            build_dir = output_dir / "build" / spec.prefix / str(node_size)
            log = output_dir / "logs" / f"build-{spec.prefix}-{node_size}.log"
            records.append(
                {
                    spec.node_env: assignment_value(str(node_size)),
                    spec.build_dir_env: assignment_value(build_dir),
                    spec.collect_dir_env: assignment_value(
                        binary_dir(binary_root, spec)
                    ),
                    spec.build_type_env: assignment_value(build_type),
                    "BUILD_JOBS": assignment_value(build_jobs),
                    "BUILD_LOG": assignment_value(log),
                }
            )
    return WorkPlan(
        workdir=ROOT,
        program=build_program(spec),
        args_join=ArgsJoinPolicy.ASSIGNMENT,
        grid=records,
        parallel=True,
        single_core=False,
    )


def build_pool(
    commands: Sequence[WorkCommand], workers: int | None, cpu_reserve: int
) -> CommandPool:
    return CommandPool(
        name="build",
        commands=commands,
        threads=workers,
        cpu_reserve=cpu_reserve,
    )
