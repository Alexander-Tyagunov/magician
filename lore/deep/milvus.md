# Milvus — deep dive

> On-demand companion to `lore/milvus.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Collections & Index Types](#collections-and-index-types) · [Search and Consistency](#search-and-consistency) · [Scaling & Architecture](#scaling-and-architecture) · [Performance](#performance)

## Collections & Index Types <a id="collections-and-index-types"></a>

Version: docs track v3.0.x; 2.5 was the prior LTS. Distributed (segments, consistency levels); Zilliz Cloud = managed. Feature gates noted; confirm against your build.

### Collection & schema
- A collection = fields (columns) + entities (rows). Exactly one **primary key** (`INT64` or `VARCHAR`); set `auto_id=True` to let Milvus mint keys (then omit them on insert).
- Vector field types: `FLOAT_VECTOR`, `FLOAT16_VECTOR`/`BFLOAT16_VECTOR` (half-precision, ~½ memory), `INT8_VECTOR`, `BINARY_VECTOR`, `SPARSE_FLOAT_VECTOR`. `dim` is fixed per field. A collection may carry multiple vector fields (multi-vector).
- DO enable the **dynamic field** (`$meta`) for schemaless scalars, but declare + index hot filter fields explicitly — dynamic keys filter slower.
- DON'T search before you both **build an index** and **load** the collection into memory; unindexed/growing data is brute-forced.

### Segments (why indexing is lazy)
Inserts land in **growing** segments (in-memory, brute-force searched). On flush they seal; the vector index builds on **sealed** segments once they pass a size threshold. Fresh rows are searchable but slow until indexed — bulk-load before heavy query traffic.

### Picking an index (one index per vector field)
Match the **metric** to how the model was trained: `COSINE`, `L2`, `IP` (float); `JACCARD`/`HAMMING` (binary); `IP`/`BM25` (sparse). Normalize for COSINE.
- **FLAT** — exact, no params; small sets / ground-truth recall.
- **IVF_FLAT** (`nlist` 128 / `nprobe` 8) — cluster-and-probe baseline; **IVF_SQ8**/**IVF_PQ** (`m`,`nbits` 8) trade recall for memory; **SCANN** adds reorder.
- **HNSW** (`M` [2,2048], `efConstruction` / search `ef`≥topk) — default for low-latency in-memory recall; **HNSW_SQ/PQ/PRQ** quantize + `refine`/`refine_k` rescore to recover recall.
- **DISKANN** (Vamana; search `search_list` default 16) — NVMe-backed, float only, L2/IP/COSINE; sets too large for RAM.
- **GPU_CAGRA**, **GPU_IVF_FLAT/PQ**, **GPU_BRUTE_FORCE** — high-throughput batch; GPU may not beat CPU latency under light load.
- **Sparse**: `SPARSE_INVERTED_INDEX` (`inverted_index_algo` DAAT_MAXSCORE default; `drop_ratio_search`); powers BM25 full-text (`bm25_k1`,`bm25_b`).

### Partitions & multi-tenancy
- Explicit partitions: you place data; hard cap **1024**/collection. Searching a subset skips the rest.
- **Partition key**: mark a scalar field; Milvus hashes it mod `num_partitions` (default 16). Filter on it to prune — scales past the 1024 cap for per-tenant data. **Partition-key isolation** (HNSW only, single-value filter) builds a per-key index for tenant search.

See lore/deep/milvus.md#search-and-consistency (consistency levels, filtering, hybrid), lore/deep/milvus.md#scaling-and-architecture (nodes, shards, replicas), lore/deep/milvus.md#performance, and lore/databases.md.

### Sources
milvus.io/docs — index.md, disk_index.md, gpu_index.md, manage-collections.md, use-partition-key.md, consistency.md

## Search and Consistency <a id="search-and-consistency"></a>

Version-adaptive: 2.5.x/2.6.x stable (2.6 latest); 3.0 beta (2026). Verify params at milvus.io/docs; SDK = pymilvus (MilvusClient).

### ANN search idioms
DO `load_collection`/load partitions into memory before search/query — unloaded errors; `release_collection` frees RAM.
DO put `metric_type` in `search_params` and MATCH the index's metric (COSINE/L2/IP; normalize for IP so IP==cosine). Mismatch silently wrecks ranking.
DO keep `limit` (topK) + `offset` < 16384 per request. For deep paging use a **search iterator**, not a big offset.
DON'T change dimension or metric after creation — recreate the collection.

### Per-index search knobs (recall↔latency)
The tunable is index-specific, passed in `params`:
- HNSW: **`ef`** — [1, int_max], default = `limit`, recommended [K, 10K]. Bigger ef = higher recall, slower. (M=30, efConstruction=360 fixed at build.)
- IVF_FLAT/SQ8/PQ: **`nprobe`** — [1, nlist], default 8 (low). Raise toward nlist for recall (nlist def 128).
- DISKANN: **`search_list`** — [1, int_max], default 100; set ≈ topK or slightly above.
DO prefer **AUTOINDEX** when unsure — Milvus derives index + params from the data (default on Zilliz Cloud). Measure recall vs a FLAT ground truth before trusting a knob.

### Range, grouping, filtered
- **Range search**: `radius` (outer) + `range_filter` (inner) define an annulus. Ordering flips by metric: L2/JACCARD/HAMMING → `range_filter <= dist < radius`; IP/COSINE → `radius < dist <= range_filter` (COSINE default, so radius < range_filter).
- **Grouping search**: `group_by_field` dedups by a scalar (one chunk/doc). `limit` counts GROUPS not rows; `group_size` = rows/group; `strict_group_size=True` fills exactly (slower on skewed data). Only FLAT, IVF_FLAT/SQ8, HNSW*, DISKANN, SPARSE_INVERTED_INDEX.
- **Filtered search**: standard = pre-filter then ANN within the subset. When an `expr` is complex/over-restrictive, latency spikes — switch to iterative via `search_params={"hints":"iterative_filter"}` (scalar-filters iterator output until topK). DON'T over-filter: a tiny surviving set starves HNSW traversal — index filtered scalars (inverted), verify recall.

### Hybrid (dense + sparse)
DO build one `AnnSearchRequest` per vector field (`data`, `anns_field`, `param`, `limit`, `expr`), pass `reqs` to `hybrid_search` with a ranker: **RRFRanker** (`k`, rank fusion, no field favored) or **WeightedRanker** (per-request weights). All vector fields indexed + loaded. BM25 sparse (2.5+) pairs with dense.

### Consistency levels
Four, via a **GuaranteeTs**: **Strong** (waits for newest ts — read-after-write, highest latency), **Bounded** (small staleness window — DEFAULT), **Session** (sees your session's writes), **Eventually** (skips check — fastest, no order guarantee).
DO set `consistency_level` at `create_collection` as the default, then OVERRIDE per search/query.
DO use Strong only when you must read just-written rows; Bounded/Eventually for recommender/search traffic.
DON'T assume Strong — default Bounded means fresh upserts may be briefly invisible until synced.

Cross-refs: lore/deep/milvus.md#collections-and-index-types · lore/deep/milvus.md#scaling-and-architecture · lore/deep/milvus.md#performance · lore/deep/databases.md#resilience-and-observability

### Sources
milvus.io/docs — consistency · single-vector-search · hnsw · ivf-flat · diskann · range-search · grouping-search · multi-vector-search · filtered-search · create-collection

## Scaling & Architecture <a id="scaling-and-architecture"></a>

Version: 2.5.x LTS / 2.6.x latest; docs track v3.0.x — confirm your build. Cloud-native, storage/compute **disaggregated** → compute scales independently. 2.6 splits stream vs batch across node types + adds **Woodpecker** (zero-disk WAL on object storage).

### Deployment modes — pick by scale
- **Milvus Lite** — `pip install pymilvus`, `MilvusClient("./x.db")`; embedded, prototyping/edge, a few M vectors. Same API, portable to Standalone.
- **Standalone** — all components in one Docker image; single machine, ~100M vectors. Full features but not HA.
- **Distributed** — Kubernetes; isolated ingest vs. query nodes, redundancy, 100M→tens of B. Production/HA. Resource groups here only.
- **Zilliz Cloud** — fully managed (serverless/dedicated); billed in compute units.

### Four layers (Distributed)
- **Access layer** — stateless **proxies**; validate, fan out, MPP-aggregate. Front with an LB. Scale for connection load.
- **Coordinator** — one active "brain": DDL/DCL, TSO/timestamp oracle, query routing, binds WAL to streaming nodes, dispatches compaction/index builds. **Cannot** be replica-scaled by node count — HA is active-standby.
- **Worker nodes** (stateless, scalable): **Streaming node** = shard mini-brain, serves *growing* data via WAL, seals it; **Query node** loads *sealed* data, serves search/query; **Data node** = compaction + index building (older builds had a separate index node).
- **Storage**: **etcd** (metadata/checkpoints), **object storage** (MinIO/S3 — indexes, snapshots), **WAL** (Kafka/Pulsar/Woodpecker).

### Shards & replicas
- **Shards** = DML channels, fixed at create (`shards_num`); parallelize *writes*. Over-sharding wastes resources — a few is usually enough.
- **In-memory replicas** load the same sealed segments onto multiple query nodes → higher QPS and instant failover (reroute, no reload). Set `replica_number` at load; a replica group holds one shard replica per shard (streaming + historical; shard leader serves growing). Search runs once ≥1 replica is up; costs RAM × replicas.

### Resource groups (Distributed only, declarative v2.4.1+)
Physically isolate query nodes per tenant. `__default_resource_group` holds all nodes at start (undeletable). Config `requests`/`limits`/`transfer_from`/`transfer_to`; Milvus keeps `requests.nodeNum < size < limits.nodeNum`. Match #groups to #replicas to isolate each.

### Scaling levers
Query nodes → read/QPS + replicas; data/index nodes → ingest & build speed; streaming nodes → writes; proxies → connections. Scale **out**, not up. Scale **in gradually** (one node at a time, verify) or use HPA.

### Compaction
Auto-merges small sealed segments, purges deletes/TTL-expired data. **Clustering compaction**: pick a scalar `clustering_key`; Milvus co-locates entities by key range and builds PartitionStats so filtered searches **prune** whole segments (big QPS wins on selective filters). Needs `dataCoord.compaction.clustering.enable` + `queryNode.enableSegmentPrune`. Best on >1M-row collections.

See lore/deep/milvus.md#collections-and-index-types (segments, partitions), lore/deep/milvus.md#search-and-consistency (consistency ↔ streaming/sealed), lore/deep/milvus.md#performance, lore/deep/databases.md#{connection-pooling,resilience-and-observability}.

### Sources
milvus.io/docs — architecture_overview · replica · resource_group · scaleout · install-overview · clustering-compaction · zilliz.com/cloud

## Performance <a id="performance"></a>

Version: 2.6.x current stable, 2.5.x prior, 3.0 beta; verify. Zilliz Cloud = managed. ANN tradeoff **recall ↔ latency ↔ memory**; index+params dominate. Defaults v2.x.

### Levers, in priority order

**1. Index + build params (biggest lever).** In-RAM HNSW = best latency/recall; `DISKANN` (NVMe, float only, L2/IP/COSINE) for sets > RAM; IVF trades recall for RAM. Matrix: lore/deep/milvus.md#collections-and-index-types.
- HNSW `M` [2,2048] (more edges = better recall + RAM), `efConstruction` (higher = better graph, slower build) — rebuild-only.
- IVF `nlist` [1,65536] default **128**; rule of thumb `≈4×√n` per segment (n from `dataCoord.segment.maxSize`, default **1024 MB**).

**2. Search knobs (per-request; sweep these).** HNSW `ef` [top_k,∞]: higher = more recall, slower. IVF `nprobe` [1,nlist] default **8** (low — raise it). SCANN `reorder_k` (default top_k). DiskANN `search_list` default **16**. Quantized indexes: `refine`+`refine_k` (default 1) rescore raw to restore recall.

**3. Load & index state.** Search runs only on **loaded, indexed** collections; unindexed/growing or below-threshold segments brute-force (`rootCoord.minSegmentSizeToEnableIndex` default **1024** rows). Bulk-load → `create_index()` → `load_collection` before queries; `release` frees RAM.

**4. Consistency (staleness for latency).** Default **Bounded**. `Strong` lifts GuaranteeTs to newest ts → highest latency; `Eventually` skips the check → lowest; `Session` = read-your-writes per client. Detail: lore/deep/milvus.md#search-and-consistency.

**5. Filtering.** Over-restrictive expr starves ANN candidates — recall collapses, latency spikes. Index hot scalars (INVERTED for `==`/`IN`, Trie for prefix), prune via a **partition key** — lore/deep/milvus.md#search-and-consistency.

**6. Memory.** Quantize: IVF_SQ8 cuts ~70–75% vs FLOAT; PQ/RaBitQ go further at more recall cost; FP16/BF16/INT8 halve raw size. **mmap** (`queryNode.mmap.*` or `mmap.enabled` per collection/index) loads ~2–4× RAM — HNSW tolerates it, IVF degrades sharply; not on DiskANN/GPU or a loaded collection.

**7. Scale out.** Query-node **replicas** for read QPS/HA; shard for writes; resource groups per tenant — lore/deep/milvus.md#scaling-and-architecture. GPU (CAGRA) wins on batch throughput, not light-load latency.

### Top anti-patterns
- Searching before load/index build → silent brute force (small/fresh collections feel slow); force `create_index()`.
- Defaults left on `nprobe`/`ef`, or `ef`/`search_list` < top_k.
- One-vector inserts (weak growing segments) — batch upsert then flush.
- Wrong `metric_type` vs the model (COSINE/L2/IP); normalize for IP.
- mmap on IVF then blaming latency; Strong reads everywhere; over-provisioning instead of quantizing.

### How to measure
Build a **FLAT** (exact) index for ground truth; track **recall@k** vs it while sweeping `ef`/`nprobe`/`refine_k` — never tune to latency alone. Benchmark QPS/**p99** at realistic `nq`/concurrency with **VectorDBBench**. Scrape Prometheus/Grafana for query latency, segment counts, load/compaction state, CPU (build intensive; query scales `nq`×`nprobe`). See lore/deep/databases.md#resilience-and-observability; pool via lore/deep/databases.md#connection-pooling.

### Sources
milvus.io/docs — performance_faq.md, index.md, disk_index.md, mmap.md, consistency.md · github.com/zilliztech/VectorDBBench
