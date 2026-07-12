# Milvus — Search and Consistency
Version-adaptive: 2.5.x/2.6.x stable (2.6 latest); 3.0 beta (2026). Verify params at milvus.io/docs; SDK = pymilvus (MilvusClient).

## ANN search idioms
DO `load_collection`/load partitions into memory before search/query — unloaded errors; `release_collection` frees RAM.
DO put `metric_type` in `search_params` and MATCH the index's metric (COSINE/L2/IP; normalize for IP so IP==cosine). Mismatch silently wrecks ranking.
DO keep `limit` (topK) + `offset` < 16384 per request. For deep paging use a **search iterator**, not a big offset.
DON'T change dimension or metric after creation — recreate the collection.

## Per-index search knobs (recall↔latency)
The tunable is index-specific, passed in `params`:
- HNSW: **`ef`** — [1, int_max], default = `limit`, recommended [K, 10K]. Bigger ef = higher recall, slower. (M=30, efConstruction=360 fixed at build.)
- IVF_FLAT/SQ8/PQ: **`nprobe`** — [1, nlist], default 8 (low). Raise toward nlist for recall (nlist def 128).
- DISKANN: **`search_list`** — [1, int_max], default 100; set ≈ topK or slightly above.
DO prefer **AUTOINDEX** when unsure — Milvus derives index + params from the data (default on Zilliz Cloud). Measure recall vs a FLAT ground truth before trusting a knob.

## Range, grouping, filtered
- **Range search**: `radius` (outer) + `range_filter` (inner) define an annulus. Ordering flips by metric: L2/JACCARD/HAMMING → `range_filter <= dist < radius`; IP/COSINE → `radius < dist <= range_filter` (COSINE default, so radius < range_filter).
- **Grouping search**: `group_by_field` dedups by a scalar (one chunk/doc). `limit` counts GROUPS not rows; `group_size` = rows/group; `strict_group_size=True` fills exactly (slower on skewed data). Only FLAT, IVF_FLAT/SQ8, HNSW*, DISKANN, SPARSE_INVERTED_INDEX.
- **Filtered search**: standard = pre-filter then ANN within the subset. When an `expr` is complex/over-restrictive, latency spikes — switch to iterative via `search_params={"hints":"iterative_filter"}` (scalar-filters iterator output until topK). DON'T over-filter: a tiny surviving set starves HNSW traversal — index filtered scalars (inverted), verify recall.

## Hybrid (dense + sparse)
DO build one `AnnSearchRequest` per vector field (`data`, `anns_field`, `param`, `limit`, `expr`), pass `reqs` to `hybrid_search` with a ranker: **RRFRanker** (`k`, rank fusion, no field favored) or **WeightedRanker** (per-request weights). All vector fields indexed + loaded. BM25 sparse (2.5+) pairs with dense.

## Consistency levels
Four, via a **GuaranteeTs**: **Strong** (waits for newest ts — read-after-write, highest latency), **Bounded** (small staleness window — DEFAULT), **Session** (sees your session's writes), **Eventually** (skips check — fastest, no order guarantee).
DO set `consistency_level` at `create_collection` as the default, then OVERRIDE per search/query.
DO use Strong only when you must read just-written rows; Bounded/Eventually for recommender/search traffic.
DON'T assume Strong — default Bounded means fresh upserts may be briefly invisible until synced.

Cross-refs: lore/milvus/collections-and-index-types.md · lore/milvus/scaling-and-architecture.md · lore/milvus/performance.md · lore/databases/resilience-and-observability.md

## Sources
milvus.io/docs — consistency · single-vector-search · hnsw · ivf-flat · diskann · range-search · grouping-search · multi-vector-search · filtered-search · create-collection
