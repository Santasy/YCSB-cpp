# WTree Data-Structure Adapter

In-memory ordered key/value adapter backed by **WTree**
(`WTreeLib::map`, header-only, Apache-2.0). Registers
`RegisterDataStructure("wtree", NewWTreeDB)` so it is driven like
`std::map`/`btree`: a single instance, a single thread, shared across the
`-load` and `-run` phases of one process.

## Purpose

Compare `std::map` (red-black tree) and cpp-btree against a **W-Tree** (weight-
balanced tree with 512-byte nodes by default) under the same YCSB dataset
pipeline. The adapter is a plain `DBInterface` (core/db_interfaces.h) storing
`key -> value` in a member `WTreeLib::map<std::string, std::string>`; the row
layer (`RowStoreDB`) and benchmark harness are shared with the other
data-structure adapters.

## Usage

The adapter is opt-in: configure with `-DBIND_WTREE=ON` (default OFF) so the
`module-wtree` include path and the `wtree_db.cc` source are added to
`ycsb_data_structs`.

```bash
cmake --preset debug-ds && cmake --build build-dbg-ds
# or: cmake --preset all-bind-on -DBIND_WTREE=ON && cmake --build build

# Single combined load + run in one process (no persistence between processes)
./build/ycsb -load -run -db wtree -threads 1 \
  -P adapters/data-structures/wtree/wtree_db.properties \
  -P workloads/workloada -p recordcount=100000 -p operationcount=100000

# Structured results (tree metrics are extra columns in schema.csv)
./build/ycsb -load -run -db wtree -threads 1 \
  -P workloads/workloada -p recordcount=100000 -p operationcount=100000 \
  -p resultformat=csv -p output.file=.cache/wtree/time.csv
```

## Node-size sweep

`WTREE_TARGET_NODE_BYTES` (default 512, a CMake cache var) fixes the tree's
target node bytes at compile time, so each binary holds exactly one `map`
instantiation. Mirroring `build_btree_variants.sh`, sweep it per build with
`-DWTREE_TARGET_NODE_BYTES=256` etc. to compare node sizes across binaries.

## Metrics

`GetStats` walks the tree with the library's `WTreeProfiler` and reports the
node footprint as `overhead` plus per-structure columns in the series output /
`schema.csv`:

- `wtree_height` — number of levels in the tree
- `wtree_leaf_nodes`, `wtree_internal_nodes` — node counts

## Notes

- `wtree.clear=true` starts with an empty store on `Init` (mirrors
  `map.clear` / `btree.clear`).
- Not thread-safe: the runtime clamps `threadcount` to 1 for data-structure
  adapters.
- Requires `-DBIND_WTREE=ON` at configure time **and** the `module-wtree`
  submodule (`git submodule update --init`).
- The WTree adapter lives in its own `.properties` file; register the dbname
  as `wtree`.