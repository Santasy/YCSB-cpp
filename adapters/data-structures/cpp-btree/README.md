# BTree Data-Structure Adapter

In-memory ordered key/value adapter backed by Google's **cpp-btree**
(`btree::btree_map`, header-only, Apache-2.0). Registers
`RegisterDataStructure("btree", NewCppBTreeDB)` so it is driven like
`std::map`: a single instance, a single thread, shared across the `-load` and
`-run` phases of one process.

## Purpose

Compare `std::map` (red-black tree) against a cache-friendly B-tree
(packeted 256-byte nodes, fewer pointer dereferences) under the same YCSB
dataset pipeline. The adapter is a plain `DBInterface` (core/db_interfaces.h)
storing `key -> value` in a member `btree::btree_map<std::string, std::string>`;
the row layer (`RowStoreDB`) and benchmark harness are shared with the other
data-structure adapters.

## Usage

```bash
# Single combined load + run in one process (no persistence between processes)
./build/ycsb -load -run -db btree -threads 1 \
  -P adapters/data-structures/cpp-btree/cppbtree_db.properties \
  -P workloads/workloada -p recordcount=100000 -p operationcount=100000

# Structured results (tree metrics are extra columns in schema.csv)
./build/ycsb -load -run -db btree -threads 1 \
  -P workloads/workloada -p recordcount=100000 -p operationcount=100000 \
  -p resultformat=csv -p output.file=.cache/btree/time.csv
```

## Metrics

`GetStats` reports the real cpp-btree node footprint as `overhead` and adds
per-structure columns to the series output / `schema.csv`:

- `btree_height` — number of levels in the tree
- `btree_leaf_nodes`, `btree_internal_nodes` — node counts

## Notes

- `btree.clear=true` starts with an empty store on `Init` (mirrors
  `map.clear`).
- Not thread-safe: the runtime clamps `threadcount` to 1 for data-structure
  adapters.
- Requires the `module-cpp-btree` submodule (`git submodule update --init`).

## Performance Results

See `run_all_benchmarks.sh` / `create_throughput_matrix.py` for comparative
throughput. With 100,000 operations, expect faster range/scan and insertion
than `std::map` due to improved cache locality.