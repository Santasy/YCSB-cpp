#!/bin/bash

# Load-order sweep for a fixed record count across every WTree and cpp-btree
# node-size variant.
#
# For each variant binary (build-wt/ycsb-wt-<size>, build-bt/ycsb-bt-<size>)
# and each load key order (ordered / hashed-fnv / hashed-sha256) it runs the
# `-load` phase only, saving the series CSV row(s) to
#   storage/load_order_sweep/<recordcount>/<tree>-<nodesize>-<order>.csv
# Datasets are shared across all variants of the same (size, order) pair, so
# each unique dataset file is generated once and reused.
#
# Usage:
#   scripts/load_order_sweep.sh <recordcount> [operationcount]
#
# Env overrides:
#   LOAD_ORDER_SEED         RNG seed (default 12345)
#   LOAD_ORDER_NODE_SIZES   whitespace list of node sizes (default "256 512 1024 2048")
#   LOAD_ORDER_DATASET_DIR  where pre-generated datasets live (default <sweep>/datasets)
#   LOAD_ORDER_FORCE_GEN    1 -> force dataset regeneration

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
RC="${1:?usage: $0 <recordcount> [operationcount]}"
OC="${2:-$RC}"

SEED="${LOAD_ORDER_SEED:-12345}"
NODE_SIZES="${LOAD_ORDER_NODE_SIZES:-256 512 1024 2048}"
SWEEP_DIR="$ROOT_DIR/storage/load_order_sweep"
DATASET_DIR="${LOAD_ORDER_DATASET_DIR:-$SWEEP_DIR/datasets}"
OUT_DIR="$SWEEP_DIR/$RC"

mkdir -p "$OUT_DIR" "$DATASET_DIR"

# name|dbname|propsfile|insertorder|hashalgo
# `ordered` carries no hashalgo so its dataset hash matches a plain ordered
# workload (hashalgo is irrelevant when insertorder != hashed).
CASES=(
    "ordered|wtree|adapters/data-structures/wtree/wtree_db.properties|ordered|"
    "fnv|wtree|adapters/data-structures/wtree/wtree_db.properties|hashed|fnv"
    "sha256|wtree|adapters/data-structures/wtree/wtree_db.properties|hashed|sha256"
)

run_case() {
    local tree="$1" bin="$2" db="$3" props="$4" size="$5"
    local order_name="$6" insertorder="$7" hashalgo="$8"

    local out_csv="$OUT_DIR/${tree}-${size}-${order_name}.csv"
    local log="$OUT_DIR/${tree}-${size}-${order_name}.log"

    local args=(
        -load -db "$db" -threads 1 -P "$ROOT_DIR/$props"
        -p recordcount="$RC" -p operationcount="$OC"
        -p insertorder="$insertorder" -p seed="$SEED"
        -p dataset_path="$DATASET_DIR" -p resultformat=csv
        -p output.file="$out_csv"
        -p force_generate="${LOAD_ORDER_FORCE_GEN:-false}"
    )
    if [ -n "$hashalgo" ]; then
        args+=(-p hashalgo="$hashalgo")
    fi

    echo "[$tree-$size-$order_name] $bin -load -db $db recordcount=$RC"
    "$bin" "${args[@]}" >"$log" 2>&1
}

for t in "wt ycsb-wt wtree" "bt ycsb-bt btree"; do
    read -r tree pref db <<<"$t"
    for size in $NODE_SIZES; do
        bin="$ROOT_DIR/build-wt/ycsb-wt-${size}"
        [ "$tree" = "bt" ] && bin="$ROOT_DIR/build-bt/ycsb-bt-${size}"
        for c in "${CASES[@]}"; do
            IFS='|' read -r order_name _ props insertorder hashalgo <<<"$c"
            props_actual="$props"
            [ "$tree" = "bt" ] && props_actual="adapters/data-structures/cpp-btree/cppbtree_db.properties"
            run_case "$tree" "$bin" "$db" "$props_actual" "$size" \
                "$order_name" "$insertorder" "$hashalgo"
        done
    done
done

echo "Load-order sweep done for recordcount=$RC"
echo "Output: $OUT_DIR"