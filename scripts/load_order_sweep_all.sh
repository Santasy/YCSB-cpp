#!/bin/bash

# Load-order sweep across all WTree / cpp-btree variants for 10K, 100K and 1M
# insert records (load phase only), then concatenate every per-run CSV into a
# single annotated file.
#
# Runs scripts/load_order_sweep.sh once per record count, then builds:
#   storage/load_order_sweep/all_runs.csv
# with a header plus one line per run:
#   recordcount,tree,node_size,insert_order,phase,operation,ops_count,
#   current_size,time_us,maxrss_kb,overhead,height,leaf_nodes,internal_nodes
# (`height`,`leaf_nodes`,`internal_nodes` are wtree_* on wt rows and btree_*
# on bt rows; see their adapters).
#
# Env overrides: same as load_order_sweep.sh (LOAD_ORDER_SEED, ...).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
SWEEP_DIR="$ROOT_DIR/storage/load_order_sweep"

RECORD_COUNTS="${LOAD_ORDER_RECORD_COUNTS:-10000 100000 1000000}"

for rc in $RECORD_COUNTS; do
    "$ROOT_DIR/scripts/load_order_sweep.sh" "$rc"
done

# Name pattern: <tree>-<size>-<order>.csv ; tree is wt or bt.
OUT="$SWEEP_DIR/all_runs.csv"
{
    printf 'recordcount,tree,node_size,insert_order,phase,operation,ops_count,current_size,time_us,maxrss_kb,overhead,height,leaf_nodes,internal_nodes\n'
    for rc in $RECORD_COUNTS; do
        for f in "$SWEEP_DIR/$rc"/wt-*-*.csv "$SWEEP_DIR/$rc"/bt-*-*.csv; do
            [ -f "$f" ] || continue
            base="$(basename "$f" .csv)"          # e.g. wt-256-sha256
            tree="${base%%-*}"
            rest="${base#*-}"
            size="${rest%%-*}"
            order="${rest#*-}"
            awk -v rc="$rc" -v tree="$tree" -v size="$size" -v order="$order" \
                'NF { print rc "," tree "," size "," order "," $0 }' "$f"
        done
    done
} >"$OUT"

echo "Combined results: $OUT  ($(wc -l <"$OUT") lines)"
echo "Per-size folders: $SWEEP_DIR/{$RECORD_COUNTS}"