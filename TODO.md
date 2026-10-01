# TODO.md — Open work (branch `dev/data-structures`)

Only **not-done** items live here. Completed roadmap entries (deterministic datasets/seeds, the
DBInterface/RowStoreDB split, the `std::map` and cpp-btree adapters, series-CSV output, map memory
- ``` - Operation enum/executor mismatch: 16 operation types are defined in core/core_workload.h but the client executor in core/client.h only implements INSERT, UPDATE, READ, SCAN and READMODIFYWRITE; DELETE, transaction ops and their _FAILED variants are missing.```
reporting) are recorded as done in FEATURES.md §5 and AGENTS.md. Refresh this file as items land.

---

## 1. Progressive per-batch measurements — DESIGNED, not implemented

Measure intermediate throughput/latency after batches of N operations. Each batch boundary would
emit **additional rows** for the operations in that batch — the fixed series schema below does not
change, batches just add more rows (workload A → ~20 read rows, ~10 update rows per run instead of
one row per op). All rows share the same columns; `time_us` is that window's wall-time, and memory
columns sample at the end of each window (see TODO §3 / FEATURES.md §5).

---

## 2. Output format — flip the default to `csv`

Series CSV + `--human` exist and work (`core/ycsbc.cc`, `core/measurements.{h,cc}`,
`core/db_database.h`, the DS adapters). The default is still `human` so
`run_all_benchmarks.sh`/`scripts/create_throughput_matrix.py` parsing keeps working.

- **Deferred work**: flip the default to `csv` in the same pass that updates
  `scripts/run_all_benchmarks.sh` (`extract_phase_throughput()`, `summarize_results()`, ~line 428/456) and
  `scripts/create_throughput_matrix.py` (`THROUGHPUT_RE`, ~line 93-96) to the series rows (keying off the
  `total`/per-op rows and the `schema.csv`). `scripts/merge_benchmark_csvs.py`/`scripts/create_benchmark_graphs.py`
  consume the wide *matrix* CSV and are unaffected.
- Series row schema (headerless): `phase,operation,ops_count,current_size,time_us,maxrss_kb,overhead[,extra_cols...]`.

---

## 3. Memory reporting — DB adapters still report zeros

`DB::GetStats(table) -> StoreStats` (`core/db_interfaces.h`) is implemented for the data-structure
adapters (`std::map` = per-entry estimate; `btree` = real `bytes_used()` + height/node extras). The
**storage-engine adapters** (rocksdb, leveldb, lmdb, wiredtiger, sqlite, leaves, redis, aerospike)
still use the default `StoreStats()` — a per-backend footprint measurement is boilerplate that
remains (until then their series rows carry `current_size=0, overhead=0`). Structure-specific extra
columns stay adapter-defined; names are written once into the container's `schema.csv`.

---

## Known gaps (carried from FEATURES.md §5.2 — not scheduled)

- `medium_workload.properties` sets props no adapter reads (`rocksdb.dir`, `leaves.dir`, `lmdb.env`);
  real names are `rocksdb.dbname`, `leaves.dbpath`, `lmdb.dbpath`.
en - Operation enum/executor mismatch: 16 operation types are defined in core/core_workload.h but the client executor in core/client.h only implements INSERT, UPDATE, READ, SCAN and READMODIFYWRITE; DELETE, transaction ops and their _FAILED variants are missing.```
- The benchmark runner's DS mode still needs one `-load -run` invocation per process (no persistence
  across invocations); wiring separate runner load/run phases for `map`/`btree` is still open.