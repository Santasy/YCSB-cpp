# See TODO.md §3/§5.

**Operations coverage:** The YCSB operation enum (`core/core_workload.h`) defines 16 operation types (INSERT=0 … MAXOPTYPE=15). The client executor (`core/client.h`) currently handles only INSERT, UPDATE, READ, SCAN and READMODIFYWRITE; DELETE, transaction operations (BEGIN_TXN, COMMIT_TXN, ROLLBACK_TXN) and their `_FAILED` variants are not yet implemented in the client switch and will be treated as no-ops or cause adapter-specific behavior.

## Scratch / experiment outputs

Use the repo-local `.cache/` directory (create a subfolder per experiment,
e.g. `.cache/wtree/`) for scratch data, experiment outputs and temp artifacts.
**Do NOT use `/tmp`**: here it is tmpfs (RAM-backed, ~7.6 GB) and fills up —
1M-record dataset files are ~1 GB each, and truncated writes manifest as
"End of dataset" aborts. Put pre-generated `dataset_path` files on the real
disk under `.cache/` (or `storage/load_order_sweep/datasets` for the sweeps)
so they persist and are reused by the dataset cache.
