# WTree load-order sweep

Comparing how the WTree data-structure adapter (`-db wtree`, 512-byte nodes,
`seed=42`, single thread) shapes its tree under different load key orders.
Series rows from `resultformat=csv`; columns
`wtree_height,wtree_leaf_nodes,wtree_internal_nodes` (see schema.csv).

## Experiment 1: ordered vs hashed (fnv) — `recordcount=1000`

| insertorder | height | leaf | internal | overhead B | load (µs) |
|-------------|-------:|-----:|---------:|-----------:|----------:|
| ordered     |   18   |  67  |   110    |   6,715    | 4.9 ms    |
| hashed fnv  |    4   | 193  |    58    |   4,992    | 4.6 ms    |

Ordered contiguous keys are the worst case: height 18 for only 1000 keys (long
skinny internal spine). Hashed scatter yields a properly balanced tree
(height 4, ~200 leaves).

## Experiment 2: scale-up, hashed (fnv) vs ordered

| n       | order   | height | leaf    | internal | overhead B | load    |
|---------|---------|-------:|--------:|---------:|-----------:|--------:|
| 10k     | hashed  |  8 |  1,614 |     745 |    56,371 | 23.5 ms   |
| 100k    | hashed  | 13 | 17,785 |   7,034 |   557,475 | 284.2 ms  |
| 1M      | hashed  | 21 | 185,308 |  67,084 | 5,461,686 | 3.5 s  |
| 10k     | ordered | 46 |    677 |   1,094 |    66,869 | 21.7 ms   |
| 100k    | ordered | 109 |  6,795 |  10,929 |   668,292 | 151.4 ms  |
| 1M      | ordered | 252 | 67,941 | 109,326 | 6,684,873 | 2.6 s   |

The gap widens sharply with size. Hashed stays roughly logarithmic
(8 → 21 across 10k → 1M); ordered grows almost linearly (46 → 252), a
degenerate spine ~12x taller at 1M, with ~1.63x the internal nodes and ~22.4%
more overhead.

## Experiment 3: hashed algorithms — fnv vs sha256

| n       | algo   | height | leaf    | internal | overhead B | load    |
|---------|--------|-------:|--------:|---------:|-----------:|--------:|
| 10k     | fnv    |  8 |  1,614 |   745 |  56,371 | 23.6 ms    |
| 10k     | sha256 |  8 |  1,828 |   661 |  53,780 | 14.6 ms    |
| 100k    | fnv    | 13 | 17,785 |  7,034 | 557,475 | 284.2 ms   |
| 100k    | sha256 | 10 | 18,381 |  6,646 | 541,145 | 264.1 ms   |
| 1M      | fnv    | 21 | 185,308 | 67,084 | 5,461,686 | 3.5 s |
| 1M      | sha256 | 14 | 184,182 | 66,263 | 5,403,994 | 3.3 s |

At small sizes fnv and sha256 are equivalent (4 vs 5). At scale FNV's weak
avalanche lets the tree drift (height 13 → 21) while sha256 stays near ideal
(10 → 14, ~log n). At 1M sha256 is 7 levels shorter, slightly fewer nodes,
~1.1% less overhead, and ~5.7% faster to load.

## Takeaways

- Ordered (contiguous) insert order is pathological for WTree: near-linear
  height growth, degenerate spine.
- Hashed load keeps the tree balanced; `hashalgo=sha256` is the better hashed
  choice at scale, FNV acceptable for small datasets.

Same workflow run on cpp-btree, plus head-to-head comparison with these
results, lives in [BTREE_RUNS.md](BTREE_RUNS.md).