"""
The grammar of a result tree — what the run end writes and the read end parses.

This is the seam between the two ends of the pipeline, so every piece of naming
knowledge lives here exactly once:

* **structure folders** ``<structure>`` or ``<structure>-<version>``
  (:func:`structure_folder` / :func:`split_structure_folder`),
* **variant folders** the node size, or ``default`` for a structure without that
  knob (:func:`variant_label` / :func:`node_size_bytes`),
* **run ids** ``<workload>[-<insert order>][-<hash algo>]-seed-<n>``
  (:func:`run_name` / :func:`split_run_name`),
* **measure labels** ``<phase>:<operation>`` (:func:`measure_label`),
* the subdirectories a run fills.

:mod:`.runs` builds names with these helpers and :mod:`.enrich` parses the same
grammar out of the scanned paths, so the two ends cannot drift; the round trip
is pinned by ``tools/ycsb_bench/tests/check_naming.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Subdirectories of the run phase's output directory.
RESULTS_DIR = "results"
LOGS_DIR = "logs"
DATASETS_DIR = "datasets"
BUILD_DIR = "build"

#: Separator between a structure and its version in a folder name.
STRUCTURE_SEP = "-"
#: Version recorded for a structure folder without a suffix.
DEFAULT_VERSION = "default"
#: Variant folder of a structure that has no node-size knob (std::map).
NO_NODE_SIZE_LABEL = "default"
#: Node size that variant stands for, so the read side keeps a numeric axis.
NO_NODE_BYTES = 0

#: Seed marker of a run id.
SEED_MARKER = "seed"
#: Insert orders tools/run_all_workloads.py sweeps.
INSERT_ORDERS: tuple[str, ...] = ("ordered", "hashed")
#: Hash algorithms it sweeps.
HASH_ALGOS: tuple[str, ...] = ("fnv", "sha256")

#: Separator between a phase and an operation in a measure label.
MEASURE_SEP = ":"


def slug(value: str) -> str:
    """*value* reduced to characters that are safe inside a folder or file name."""
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )


def structure_folder(struct: str, version: str | None = None) -> str:
    """The folder of a structure variant: ``wtree-simple``, or plain ``btree``."""
    if version in (None, "", DEFAULT_VERSION):
        return struct
    return f"{struct}{STRUCTURE_SEP}{version}"


def split_structure_folder(name: str) -> tuple[str, str]:
    """``(structure, version)`` of a structure folder; unversioned means default."""
    struct, separator, version = name.partition(STRUCTURE_SEP)
    if not separator or not version:
        return struct, DEFAULT_VERSION
    return struct, version


def variant_label(node_size: int | None) -> str:
    """The variant folder of a node size, or ``default`` when there is none."""
    return str(node_size) if node_size is not None else NO_NODE_SIZE_LABEL


def node_size_bytes(label: str) -> int:
    """The node size a variant folder stands for (0 = structure without the knob)."""
    if label == NO_NODE_SIZE_LABEL:
        return NO_NODE_BYTES
    return int(label)


def run_name(
    workload: str,
    insert_order: str | None = None,
    hash_algo: str | None = None,
    seed: int | None = None,
) -> str:
    """The run id (and result file stem) of one run of *workload*."""
    parts = [workload]
    if insert_order is not None:
        parts.append(insert_order)
    if hash_algo is not None:
        parts.append(hash_algo)
    if seed is not None:
        parts.append(f"{SEED_MARKER}-{seed}")
    return slug(STRUCTURE_SEP.join(parts))


@dataclass(frozen=True)
class RunName:
    """A parsed run id: the workload, the runner choices it was run with, the seed."""

    workload: str
    insert_order: str | None = None
    hash_algo: str | None = None
    seed: int | None = None


def _strip_suffix(value: str, choices: tuple[str, ...]) -> tuple[str, str | None]:
    """*value* with one trailing ``-<choice>`` removed, plus the choice found."""
    for choice in reversed(choices):
        suffix = f"{STRUCTURE_SEP}{choice}"
        if value.endswith(suffix):
            return value[: -len(suffix)], choice
    return value, None


def split_run_name(name: str) -> RunName:
    """The inverse of :func:`run_name`: a run id back into its parts."""
    workload, separator, tail = name.rpartition(f"{STRUCTURE_SEP}{SEED_MARKER}-")
    seed = int(tail) if separator and tail.isdigit() else None
    # :func:`run_name` appends the hash algorithm after the insert order, so
    # strip the suffixes in that order to invert it.
    without_hash, hash_algo = _strip_suffix(workload, HASH_ALGOS)
    base, insert_order = _strip_suffix(without_hash, INSERT_ORDERS)
    return RunName(base, insert_order, hash_algo, seed)


def measure_label(phase: str, operation: str) -> str:
    """The measure a result row stands for: ``run:total``, ``load:read``, …"""
    return f"{phase}{MEASURE_SEP}{operation}"


__all__ = [
    "BUILD_DIR",
    "DATASETS_DIR",
    "DEFAULT_VERSION",
    "HASH_ALGOS",
    "INSERT_ORDERS",
    "LOGS_DIR",
    "MEASURE_SEP",
    "NO_NODE_BYTES",
    "NO_NODE_SIZE_LABEL",
    "RESULTS_DIR",
    "SEED_MARKER",
    "STRUCTURE_SEP",
    "RunName",
    "measure_label",
    "node_size_bytes",
    "run_name",
    "slug",
    "split_run_name",
    "split_structure_folder",
    "structure_folder",
    "variant_label",
]
