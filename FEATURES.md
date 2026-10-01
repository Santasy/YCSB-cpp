# FEATURES.md — Project analysis, README-vs-reality, legacy code, TODO

Analysis snapshot: branch `dev/data-structures` @ `951f857`. Refreshed on `dev/data-structures`
for the items marked ✅ where code landed after that snapshot.

---

## 1. What the README claims vs. what actually exists

Legend: ✅ implemented · ⚠️ partially / misleading · ❌ not implemented

### Core runtime refactor claims (README "Differences from upstream master")

| Claim | Status | Evidence |
|-------|--------|----------|
| Entry moved to `core/ycsbc.cc` | ✅ | `core/ycsbc.cc:90` |
| Workload/client expanded (`core/core_workload.{h,cc}`, `core/client.h`), txn ops + failure counters | ✅ | `core/core_workload.h:29`, `client.h` |
| Pre-generated/replayed datasets (`core/dataset.{h,cc}`, `PrepareOpsForFile`) | ✅ | `core/dataset.cc`, `core_workload.cc` |
| `core/db_wrapper.h`, measurements, status reporting | ✅ | `core/db_wrapper.h`, `core/measurements.*` |
| Legacy `db/` dir removed, adapters under `adapters/<db>/` | ✅ | `core/db_factory.*`; DB adapters globbed in both builds from `adapters/data-bases/`; data-structure adapters from `adapters/data-structures/` |
| Redis rework, vendored `redis/hiredis/` removed | ✅ | no hiredis anywhere under `redis/` |
| RocksDB full adapter + `options.ini` | ✅ | `adapters/rocksdb/` |
| `workload_kv_*` suite + legacy names `workload[a-f]` | ✅ | `workloads/` |
| Benchmark scripts `scripts/run_all_benchmarks.sh`, `scripts/create_throughput_matrix.py`, `scripts/create_benchmark_graphs.py`, `scripts/merge_benchmark_csvs.py`, `scripts/build_btree_variants.sh`; **`run_deterministic_benchmark.sh` deleted** | ⚠️ | `run_deterministic_benchmark.sh` removed (never worked: no `workloadc_deterministic`, stale root props); all build/bench tooling consolidated under `scripts/` |
| Benchmark script **`run_leaves_benchmark.sh`** (README mention removed) | ✅ | Script never existed (not in git history); the README list entry is gone. |
| `PROPERTIES.md`, `utils/` refactor, `tests/test_fields.cc` | ✅ | present |

### Supported-database claims

README lists **LevelDB, RocksDB, LMDB, WiredTiger, SQLite, Redis, Leaves**. Reality in
`CMakeLists.txt` / `CMakePresets.json`:

| dbname | Build | State |
|--------|-------|-------|
| rocksdb / leveldb / lmdb / wiredtiger / sqlite / leaves | Makefile + CMake (`BIND_*`) | real adapters |
| redis | CMake only (`BIND_REDIS`) | real adapter, needs external server + `hiredis` |
| aerospike | CMake only (`BIND_AEROSPIKE`) | real adapter, needs external server + client lib |
| null | always (OBJECT lib) | no-op, used for overhead measurement |
| map | always (`ycsb_data_structs` OBJECT lib) | in-memory `std::map`, no persistence, see §5.4 |
| btree | CMake only (`BIND_BTREE`, opt-in) | in-memory `btree::btree_map` (cpp-btree submodule), see §2/§5.4 |

README's list therefore omits Aerospike, BTree, the null DB and the `map`/`btree` data-structure
adapters. The badger and dragonfly adapters were **deleted**.

---

## 2. Legacy code — inventory and why it is still here

### Root-level databases: REMOVED

`leaves/`, `leveldb/`, `rocksdb/`, `lmdb/`, `wiredtiger/`, `sqlite/`, `redis/`, `aerospike/`,
`null/` at repo root were **older-generation copies of the adapters**: root `leaves_db.cc`
(~263 lines) was an earlier API experiment (props `leaves.binary_key` / `leaves.batch_size`, no
`confluence`, no WAL, no txn API); `adapters/leaves/leaves_db.cc` (~430 lines) has `confluence`,
`merge_threshold`, `max_attached_age_ms`, `wal`, txn API. Root `leveldb_db.h` lacked
`BeginTransaction/CommitTransaction` and the `Load(table, Dataset&)` bulk path; `adapters/leveldb/`
has both. Same story for rocksdb, lmdb, wiredtiger, sqlite, redis, aerospike.

**They were never compiled** (both builds glob only `adapters/<db>/*.cc` and `core/*.cc`), and their
only live consumer was `run_deterministic_benchmark.sh`, which passed root-level
`${db}/${db}.properties`. Both the root copies and that script have been **deleted**. No CI existed
to catch divergence, so removal eliminates the trap.

### `tests/`

Single standalone file `tests/test_fields.cc`. Wired into CMake behind the `debug-test` preset →
`ycsb_tests` binary (`cmake --preset debug-test && cmake --build build-test --target ycsb_tests`);
manual fallback:
`g++ -std=c++20 -I. tests/test_fields.cc -o t && ./t`.

### `adapters/data-structures/cpp-btree/` (BTree work) — opt-in build

`adapters/data-structures/cpp-btree/` holds the tracked adapter
(`cppbtree_db.{h,cc}`, `.properties`, `README.md`) plus the `module-cpp-btree` submodule
(`.gitmodules` → GerHobbelt/cpp-btree, an Apache-2.0 header-only C++11 B-tree). The **adapter is
opt-in**: it is only added to `ycsb_data_structs` (dbname `btree`) when `BIND_BTREE` is ON,
mirroring `std::map`:
single owner/single thread, `btree.clear` on `Init`, real node footprint + height/leaf/internal-node
metrics in `GetStats`. The submodule must exist (`git submodule update --init`); only the tracked
adapter code is committed, the btree library itself is not.

---

## 3. Unimplemented / dead code (things that look implemented but are not)


2. **Dragonfly was config-only and has been deleted.** `adapters/dragonfly/` contained a single
   properties file that set `dbname=redis` + port 6380; there was no `dragonfly` registration in
   `db_factory`, so `-db dragonfly` failed. `scripts/run_all_benchmarks.sh` had a `redis|dragonfly` case and
   a `dragonfly` clean step, but the default `BENCHMARK_DATABASES` never listed it.
3. **`dedicated_writer` property** is passed by `scripts/run_all_benchmarks.sh` only for scenarios matching
   `*_dw`; no scenario in the default list matches, and no C++ code reads the property. Dead.
4. **`run_deterministic_benchmark.sh` was broken and has been deleted.** It used
   `WORKLOADS=("workloadc_deterministic")` (`:20`), a file that does not exist, and read root-level
   `${db}/${db}.properties` (see §2). Deterministic benchmarks are a planned TODO.md item.
5. **`workload_kv_concurrent_write` sets `leaves.heap_writeback_bytes`** — no code reads it; the
   only Leaf-tuning props implemented are `format`, `merge_threshold`, `max_attached_age_ms`, `wal`,
   `sync`, `mapsize`, `destroy`, `dbpath`.
6. **`medium_workload.properties` sets props no adapter reads**: `rocksdb.dir`, `leaves.dir`,
   `lmdb.env`. Real names: `rocksdb.dbname`/`rocksdb.*`, `leaves.dbpath`, `lmdb.dbpath`. Only
   `lmdb.nosync` there has an effect. Agents copying these names into new configs will silently no-op.
7. **`Run`-path DELETE is dead.** The `DB` interface and `Operation` enum have `Delete`, but the
   pre-generated `Dataset` `WorkItem::OpType` is only
   `{INSERT, UPDATE, READ, SCAN, READMODIFYWRITE}` — the hot loop (`client.h`) can never issue a
   Delete. Keep-or-drop is an interface decision (see §5).

---

## 4. Architectural notes that matter for the interface work

- **The two stacked layers are now split across two headers** (done, see §5.3):
  - *storage access* (`core/db_interfaces.h`, `DBInterface`): raw ordered
    `Get/Put/Erase/Range`, plus `Load(Dataset&)`, explicit txn callbacks and `GetStats`;
  - *YCSB row semantics* (`core/db_database.h`, `DB : DBInterface`): `Read/Scan/Update/Insert/Delete`
    over multi-field rows serialized by `utils/fields.h`
    (`Fields` = contiguous `[count:4][name_size:4][value_size:4][name][value]…` blob;
    `ReadonlyFields` = view over that blob, `Fields::update()` = merge/read-modify-write).
  - `RowStoreDB : DB` lifts a bare `DBInterface` (a data structure) onto the row API by inheriting
    `DB`'s default implementations and forwarding the raw primitives.
- **Adapters funnel the row model into each backend in ad-hoc ways**:
  - row-as-blob: leaves and (typically) leveldb/rocksdb/lmdb store the serialized
    `Fields` blob as the value;
  - RMW is done in-adaptee: `Update()` re-reads the row, merges, writes back (see
    `leaves_db.cc:308`);
  - `kSkip` status opts out of the client's RMW double-read (`Read(..., rmw=true)`),
    `DBWrapper` skips timing for it.
- **Ordering**: keys are produced by `BuildKeyName` (`core_workload.cc:268`) — zero-padded
  `user<decimal>` when `insertorder=ordered`, or SHA-256 hex / FNV hashed when `hashed`. All are
  byte-ordered ASCII, which is what `Scan` relies on (first key + `record_count` forward records).
- **Transactions are implicit**, not in the dataset: `client.h` wraps every `batch_size` ops in
  `BeginTransaction()/CommitTransaction()`; `batch_size` comes from props (`CoreWorkload::BATCH_SIZE_PROPERTY`).
- **Per-thread instances (storage engines) vs. one shared instance (data structures)**: `ycsbc.cc`
  creates one engine `DBWrapper` per client thread plus a fresh one for load; adapters that need a
  shared store use `static` members + `ref_cnt_` + mutex (leaves `storage_`); `core/db_interfaces.h`
  offers an opt-in `SharedBackend<Handle>` mixin for that pattern. **Data-structure adapters are the
  opposite**: `DBFactory::IsDataStructure()` makes the runtime create exactly one instance, reuse it
  across `-load` and `-run`, clamp `threadcount` to 1 and not assume thread-safety.
- **Bulk load** is part of the interface (`Load(table, Dataset&)`), with per-row fallback performed
  only by adapting `Dataset::Next()`; several backends implement dedicated fast paths
  (leaves single-cursor transaction, leveldb write-batch).

### Measured windows — what a "window" is

A **window** is one aggregated measurement period, emitted as exactly one
series-CSV row by `EmitSeriesRow`. Two shapes exist:

- **Run phase — one window per operation type**: `DBWrapper` times every DB
  call individually (ns) and feeds `Measurements::Report`, which aggregates
  per-type `count`/`latency_sum`/min/max atomics (`core/measurements.cc:43`).
  `GetOpWindows()` (`core/measurements.h:31`) emits one
  `OpWindow{op, count, total_ns}` per operation type with non-zero count, in
  **Operation enum order, not execution order**; `time_us = total_ns / 1000`
  is the sum of that op's individually measured latencies across all threads
  (`ycsbc.cc:296`). A trailing `total` window row is the **wall-clock**
  runtime of the whole run (`timer.Start()/End()` around all client threads,
  `ycsbc.cc:257`), not the sum of per-op latencies.
- **Load phase — one single window**: the whole load is one window with
  operation `total` (`ycsbc.h:84`); `time_us` = wall time of
  `load_db->Load()` only — dataset file generation runs outside the window
  (and is cached/reused, so it never re-occurs on repeat runs).

The pre-generated dataset's op order never influences window contents: a
window is a per-type (or whole-phase) aggregate, so the two different
`total`s (summed per-op latency vs wall-clock) deliberately diverge as
concurrency or batching overlaps work.

---

## 5. TODO

### 5.1 Current state

- The adapter dialect is split (done): `core/db_interfaces.h` (`DBInterface`, raw ordered KV +
  `Load` + txn callbacks + `GetStats`) is implemented by data structures; `core/db_database.h`
  (`DB : DBInterface`, row semantics: fields blob + filter + RMW-skip) is implemented by storage
  engines. `core/db.h` no longer exists.
- Only "databases" (KV stores, trees, network services) have adapters in the DB tree; the in-memory
  data-structure backends are **`std::map`** (`adapters/data-structures/stdlib/`, dbname `map`) and
  **cpp-btree** (`adapters/data-structures/cpp-btree/`, dbname `btree`) — see §5.4. `std::set` was
  dropped: every workload is key-value, so a value-less container has no YCSB row semantics to
  expose.
- The dataset pipeline (pre-generate → `Dataset::Next()` → `client.h` hot loop) is the only live
  execution path; the legacy `DoInsert/DoTransaction` virtuals in `CoreWorkload` are not called.
- Measurement/timing is layered (DBWrapper), independent of storage, and works unchanged.

### 5.2 Gaps vs. the README / docs that should be fixed or acknowledged

- Supported-DB list in README omits Aerospike / BTree / null; update or keep an explicit "not wired"
  note. (badger/dragonfly adapters were deleted.)
- `run_deterministic_benchmark.sh` (broken: nonexistent workload, stale root properties) has been
  deleted; deterministic datasets are DONE (see TODO.md).
- `medium_workload.properties` sets props no adapter reads (`rocksdb.dir`, `leaves.dir`, `lmdb.env`);
  real names `rocksdb.dbname`, `leaves.dbpath`, `lmdb.dbpath` (see §3.6).

### 5.3 Requirement: an adaptable interface for databases **and** data structures

Design a **storage-agnostic core** that both backend kinds can implement. **Implemented** as:

1. A minimal **ordered map contract** in `core/db_interfaces.h` (`class DBInterface`), the layer a
   plain backend implements:
   - point ops: `Get(table, key, value&)`, `Put(table, key, value)`, `Erase(table, key)`; the
     `Slice` key/value view lives in `utils/fields.h`;
   - ordered iteration: `Range(table, start, count, out&)` — required by `Scan`;
   - `Load(table, Dataset&)` with a **default per-op `Put` fallback** defined out-of-line in
     `core/db_interfaces.cc`; backends with a bulk path override it;
   - explicit transaction callbacks (`Begin/Commit/Rollback`) returning `kNotImplemented`, so
     batch-transaction wiring in `client.h` doesn't depend on backend whack-a-mole.
2. YCSB **row semantics** stay in a thin layer on top: `class DB : DBInterface` in
   `core/db_database.h` (fields blob, `filter()`, RMW-merge, the `kSkip` convention; raw primitives
   default to `kNotImplemented`). `RowStoreDB : DB` adapts a bare `DBInterface` up to the row API,
   so a data structure only ever stores `key -> std::string` and never understands `Fields`.
3. Loose ends:
   - `table`: still passed everywhere and still ignored/path-folded inconsistently by adapters
     (unchanged; the DS contract carries it through but `std::map` ignores it);
   - value-update semantics for flat stores: `DB`'s default `Update` = whole-row read-modify-write
     (Get → merge → Put), so DS adapters get RMW for free;
   - `Delete`: interface + counters exist but the dataset never emits one (unchanged);
   - shared-store lifetime for per-thread engine instances: opt-in `SharedBackend<Handle>` mixin in
     `core/db_interfaces.h` (not yet adopted by leaves/et al.); DS adapters sidestep it by being
     single-owner/single-thread instead;
   - dataset signature: ~~`CoreWorkload::GetPropertiesHash()` omits the field/thread/metadata
     props, so `Dataset` files can be silently reused with different data~~ **FIXED**: the hash now
     folds the full workload signature (proportions, distributions, scan params, insertorder,
     hashalgo, fieldcount/fieldlength, readallfields, writeallfields, recordcount, operationcount,
     threadcount, `seed`, …), and filenames carry a `v2-` version prefix.

### 5.4 Requirement: flexible implementations — `std::map` and cpp-btree

- **cpp-btree is built via `BIND_BTREE` (OFF by default)**: `adapters/data-structures/cpp-btree/`
  holds the tracked adapter
  (`cppbtree_db.{h,cc}`, `.properties`, `README.md`) plus the submoduled, header-only
  `module-cpp-btree` include. It implements exactly the same `DBInterface` contract as `std::map`
  (see below) with a `btree::btree_map<std::string,std::string>` member, `btree.clear` on `Init`,
  and richer `GetStats` (`overhead` = real `bytes_used()` footprint; `btree_height`,
  `btree_leaf_nodes`, `btree_internal_nodes` extras).
- New adapters are **props-driven, not hardcoded libs** (free from the CMake package/absolute-path
  dance of leaves); `std::set` is intentionally NOT planned (value-less container can't express
  YCSB rows):
  - `std::map` (`std_map_db.{h,cc}`) derives `DBInterface` and stores
    `key -> serialized string` in a plain **member** `std::map` (no statics, no mutex), giving
    ordered `lower_bound`/iteration for `Scan`; `map.clear=true` clears on `Init`; `Load` uses the
    inherited default per-op `Put` loop.
  - validated under both `insertorder=hashed` (sha256 hex keys) and the ordered/session workloads;
    `Scan` returns rows in byte order from `lower_bound`. `cppbtree_db` mirrors all of this and
    validates the same way (both were smoke-tested with `-load -run` on workloada).
  - runs as a **single owner, single thread**: the runtime creates one instance, `Init`s it once and
    reuses it for both `-load` and `-run`, clamping `threadcount` to 1 with a warning. Data therefore
    persists across the load/run split only within one process (no persistence) — the runner's
    separate load/run invocations are not yet wired for DS backends (`TODO`).
  - workloads needing engine-only features (transactions/concurrency) declare `adapter.kinds=db`;
    selecting `-db map`/`-db btree` for them fails fast before any dataset work.
  - a later custom structure (e.g. a proper btree or LSM-like container) implements the same core
    interface; the row-semantics layer, `DBWrapper` timing and dataset pipeline must not change.
- The new backends build under **C++20** in both build systems (`ycsb_data_structs` OBJECT library;
  the cpp-btree adapter is globbed at the top level of `adapters/data-structures/cpp-btree/` so the
  submodule's own test sources stay out).

### 5.5 Suggested step order (partially done)

1. `core/db_interfaces.h` (`DBInterface` ordered map contract + default bulk-load + explicit-txn
   stubs) — **done** (kept the `DBInterface` name rather than `core/storage.h`).
2. Split the `DB` row layer onto it (`core/db_database.h`; removed `core/db.h`) and migrate all

4.5 **Operation coverage gap**: 16 operation types are defined in `core/core_workload.h` but the client executor in `core/client.h` only implements INSERT, UPDATE, READ, SCAN and READMODIFYWRITE; DELETE, transaction ops and their `_FAILED` variants are missing.
   adapters; `RowStoreDB` bridges data structures to the row API; factory gained a data-structure
   registry + `IsDataStructure()` — **done**.
3. Implement `std::map` + cpp-btree adapters, validate correctness (compare vs `null`/`basic` for
   op throughput and `Scan` ordering), then run the existing scenario matrix with
   `BENCHMARK_DATABASES="map btree"`. — **done**: `map` and `btree` validated (deterministic hashed
   keys, ordered scans, single-threaded shared instance; btree also reports its node footprint);
   `std::set` dropped (no value column → no row semantics). Runner DS mode still one `-load -run`
   invocation per process.
4. Fix the §5.2 doc/script drifts and the dataset-hash gap while the interface churn is fresh. —
   **dataset-hash fixed** (§5.3); doc drifts remain (§5.2).