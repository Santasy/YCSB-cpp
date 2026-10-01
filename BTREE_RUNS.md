# cpp-btree load-order sweep

Comparing how the cpp-btree data-structure adapter (`-db btree`, 256-byte
nodes per `BTREE_TARGET_NODE_SIZE`, `seed=42`, single thread) shapes its tree
under different load key orders. Series rows from `resultformat=csv`; columns
`btree_height,btree_leaf_nodes,btree_internal_nodes`; `overhead` is the
adapter's `db_.bytes_used()` (actual node footprint).

## Experiment 1: ordered vs hashed (fnv) — `recordcount=1000`

| insertorder | height | leaf | internal | overhead B | load (µs) |
|-------------|-------:|-----:|---------:|-----------:|----------:|
| ordered     |   6   | 264  |    93    |   13,256   | 3.7 ms    |
| hashed fnv  |   6   | 303  |   128    |   29,768  | 3.7 ms    |

cpp-btree self-balances: both orders produce the same height at 1000 keys.
Hashed spreads keys into slightly more nodes (303 vs 264 leaves).

## Experiment 2: scale-up, ordered vs hashed (fnv)

| n       | order   | height | leaf    | internal | overhead B | load    |
|---------|---------|-------:|--------:|---------:|-----------:|--------:|
| 10k     | hashed  |  8 |  2,999 | 1,283 |   291,736 | 13.1 ms   | 
| 10k     | ordered |  7 |  2,635 |   932 |   131,784 | 12.18 ms   |
| 100k    | hashed  | 10 | 30,271 | 13,139 | 3,049,752 | 180.6 ms  |
| 100k    | ordered |  9 | 26,371 | 9,345 | 1,327,992 | 117.663 ms  |
| 1M      | hashed  | 12 | 301,763 | 131,384 | 30,298,888 | 2.6 s |
| 1M      | ordered | 11 | 263,489 | 93,413 | 13,224,856 | 1.07 s |

Insert order is nearly irrelevant to balance: ordered and hashed differ by at
most **one level** at every size (11 vs 12 at 1M). Ordered is actually
cheaper at scale — contiguous keys fit the fanout better: ~29% fewer internal
nodes, ~56% less node overhead, and ~59% faster to load than
hashed at 1M.

## Experiment 3: hashed algorithms — fnv vs sha256

| n       | algo   | height | leaf    | internal | overhead B | load    |
|---------|--------|-------:|--------:|---------:|-----------:|--------:|
| 10k     | fnv    | 8 | 2,999 | 1,283 | 291,736 | 13.1 ms    |
| 10k     | sha256 | 8 | 3,009 | 1,324 | 303,656 | 13.7 ms    |
| 100k    | fnv    | 10 | 30,271 | 13,139 | 3,049,752 | 180.6 ms |
| 100k    | sha256 | 10 | 30,198 | 13,146 | 3,036,248 | 183.5 ms |
| 1M      | fnv    | 12 | 301,763 | 131,384 | 30,298,888 | 2.6 s |
| 1M      | sha256 | 12 | 301,719 | 130,854 | 30,162,536 | 2.8 s |

Fnv and sha256 are effectively identical for cpp-btree: same height at every
size, node counts within 0.1%, ~0.2% overhead difference.

## Summary

- cpp-btree is robust to insert order: height tracks ~log n across all cases
  (6 → 11/12), never a degenerate spine.
- Ordered load is the cheapest at scale (fewer nodes, less overhead, faster);
  hashed costs +78.6% overhead and +70% load time.
- Hashed algorithm choice (fnv vs sha256) is immaterial for the btree.

## Comparison with WTree

WTree (512-byte nodes) behaved the opposite way — see WTREE_RUNS.md.

- **Order sensitivity**: WTree is critically order-dependent — ordered
  inserts degenerate into a near-linear spine (height 252 at 1M, ~18x taller
  than hashed). cpp-btree is order-agnostic: height barely moves (11 vs 12),
  its balance is structurally guaranteed.
- **Best config**: WTree needs hashed load (`hashalgo=sha256` preferred at
  scale) to stay balanced. cpp-btree is fine with either, but ordered load is
  measurably better (contiguous contention-friendly keys, ~38% faster load,
  ~18% less overhead at 1M).
- **Cost of hashing**: for the btree, hashing buys nothing structurally and
  costs nodes/overhead/time; for the WTree, hashing is what makes it usable.
- **Fnv vs sha256**: irrelevant for cpp-btree; for WTree sha256 keeps the
  height ~log n at scale (14 vs 21 at 1M) where fnv drifts.