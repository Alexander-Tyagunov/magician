# Milvus — Collections & Index Types

Version: docs track v3.0.x; 2.5 was the prior LTS. Distributed (segments, consistency levels); Zilliz Cloud = managed. Feature gates noted; confirm against your build.

## Collection & schema
- A collection = fields (columns) + entities (rows). Exactly one **primary key** (`INT64` or `VARCHAR`); set `auto_id=True` to let Milvus mint keys (then omit them on insert).
- Vector field types: `FLOAT_VECTOR`, `FLOAT16_VECTOR`/`BFLOAT16_VECTOR` (half-precision, ~½ memory), `INT8_VECTOR`, `BINARY_VECTOR`, `SPARSE_FLOAT_VECTOR`. `dim` is fixed per field. A collection may carry multiple vector fields (multi-vector).
- DO enable the **dynamic field** (`$meta`) for schemaless scalars, but declare + index hot filter fields explicitly — dynamic keys filter slower.
- DON'T search before you both **build an index** and **load** the collection into memory; unindexed/growing data is brute-forced.

## Segments (why indexing is lazy)
Inserts land in **growing** segments (in-memory, brute-force searched). On flush they seal; the vector index builds on **sealed** segments once they pass a size threshold. Fresh rows are searchable but slow until indexed — bulk-load before heavy query traffic.

## Picking an index (one index per vector field)
Match the **metric** to how the model was trained: `COSINE`, `L2`, `IP` (float); `JACCARD`/`HAMMING` (binary); `IP`/`BM25` (sparse). Normalize for COSINE.
- **FLAT** — exact, no params; small sets / ground-truth recall.
- **IVF_FLAT** (`nlist` 128 / `nprobe` 8) — cluster-and-probe baseline; **IVF_SQ8**/**IVF_PQ** (`m`,`nbits` 8) trade recall for memory; **SCANN** adds reorder.
- **HNSW** (`M` [2,2048], `efConstruction` / search `ef`≥topk) — default for low-latency in-memory recall; **HNSW_SQ/PQ/PRQ** quantize + `refine`/`refine_k` rescore to recover recall.
- **DISKANN** (Vamana; search `search_list` default 16) — NVMe-backed, float only, L2/IP/COSINE; sets too large for RAM.
- **GPU_CAGRA**, **GPU_IVF_FLAT/PQ**, **GPU_BRUTE_FORCE** — high-throughput batch; GPU may not beat CPU latency under light load.
- **Sparse**: `SPARSE_INVERTED_INDEX` (`inverted_index_algo` DAAT_MAXSCORE default; `drop_ratio_search`); powers BM25 full-text (`bm25_k1`,`bm25_b`).

## Partitions & multi-tenancy
- Explicit partitions: you place data; hard cap **1024**/collection. Searching a subset skips the rest.
- **Partition key**: mark a scalar field; Milvus hashes it mod `num_partitions` (default 16). Filter on it to prune — scales past the 1024 cap for per-tenant data. **Partition-key isolation** (HNSW only, single-value filter) builds a per-key index for tenant search.

See lore/milvus/search-and-consistency.md (consistency levels, filtering, hybrid), lore/milvus/scaling-and-architecture.md (nodes, shards, replicas), lore/milvus/performance.md, and lore/databases.md.

## Sources
milvus.io/docs — index.md, disk_index.md, gpu_index.md, manage-collections.md, use-partition-key.md, consistency.md
