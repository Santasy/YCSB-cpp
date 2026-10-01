"""Data-structure variants: what to build, how to name it and where it lands."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .benchgrid_bridge import ROOT

DEFAULT_NODE_SIZES = (256, 512, 1024, 2048, 4096, 8192, 16384)


def root_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class TreeSpec:
    name: str
    prefix: str
    dbname: str
    properties: Path
    build_script: Path | None
    node_env: str | None
    build_dir_env: str
    collect_dir_env: str
    build_type_env: str


def tree_specs() -> dict[str, TreeSpec]:
    return {
        "btree": TreeSpec(
            name="btree",
            prefix="bt",
            dbname="btree",
            properties=ROOT
            / "adapters/data-structures/cpp-btree/cppbtree_db.properties",
            build_script=ROOT / "scripts/build_btree_variants.sh",
            node_env="BTREE_NODE_SIZES",
            build_dir_env="BTREE_BUILD_DIR",
            collect_dir_env="BTREE_COLLECT_DIR",
            build_type_env="BTREE_BUILD_TYPE",
        ),
        "wtree": TreeSpec(
            name="wtree",
            prefix="wt",
            dbname="wtree",
            properties=ROOT / "adapters/data-structures/wtree/wtree_db.properties",
            build_script=ROOT / "scripts/build_wtree_variants.sh",
            node_env="WTREE_NODE_SIZES",
            build_dir_env="WTREE_BUILD_DIR",
            collect_dir_env="WTREE_COLLECT_DIR",
            build_type_env="WTREE_BUILD_TYPE",
        ),
        "std": TreeSpec(
            name="std",
            prefix="std",
            dbname="map",
            properties=ROOT / "adapters/data-structures/stdlib/std_map.properties",
            build_script=None,
            node_env=None,
            build_dir_env="STD_BUILD_DIR",
            collect_dir_env="STD_COLLECT_DIR",
            build_type_env="STD_BUILD_TYPE",
        ),
    }


def binary_dir(binary_root: Path, spec: TreeSpec) -> Path:
    return binary_root / f"build-{spec.prefix}"


def binary_path(binary_root: Path, spec: TreeSpec, node_size: int | None) -> Path:
    if spec.node_env is None:
        node_size = None
    suffix = f"-{node_size}" if node_size is not None else ""
    return binary_dir(binary_root, spec) / f"ycsb-{spec.prefix}{suffix}"


def variants_for(spec: TreeSpec, node_sizes: Sequence[int]) -> tuple[int | None, ...]:
    if spec.node_env is None:
        return (None,)
    return tuple(node_sizes)


def variant_label(node_size: int | None) -> str:
    return str(node_size) if node_size is not None else "default"
