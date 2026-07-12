# Milvus — Performance

Version: 2.6.x current stable, 2.5.x prior, 3.0 beta; verify. Zilliz Cloud = managed. ANN tradeoff **recall ↔ latency ↔ memory**; index+params dominate. Defaults v2.x.

## Levers, in priority order

**1. Index + build params (biggest lever).** In-RAM HNSW = best latency/recall; `DISKANN` (NVMe, float only, L2/IP/COSINE) for sets > RAM; IVF trades recall for RAM. Matrix: lore/milvus/collections-and-index-types.md.
- HNSW `M` [2,2048] (more edges = better recall + RAM), `efConstruction` (higher = better graph, slower build) — rebuild-only.
- IVF `nlist` [1,65536] default **128**; rule of thumb `≈4×√n` per segment (n from `dataCoord.segment.maxSize`, default **1024 MB**).

**2. Search knobs (per-request; sweep these).** HNSW `ef` [top_k,∞]: higher = more recall, slower. IVF `nprobe` [1,nlist] default **8** (low — raise it). SCANN `reorder_k` (default top_k). DiskANN `search_list` default **16**. Quantized indexes: `refine`+`refine_k` (default 1) rescore raw to restore recall.

**3. Load & index state.** Search runs only on **loaded, indexed** collections; unindexed/growing or below-threshold segments brute-force (`rootCoord.minSegmentSizeToEnableIndex` default **1024** rows). Bulk-load → `create_index()` → `load_collection` before queries; `release` frees RAM.

**4. Consistency (staleness for latency).** Default **Bounded**. `Strong` lifts GuaranteeTs to newest ts → highest latency; `Eventually` skips the check → lowest; `Session` = read-your-writes per client. Detail: lore/milvus/search-and-consistency.md.

**5. Filtering.** Over-restrictive expr starves ANN candidates — recall collapses, latency spikes. Index hot scalars (INVERTED for `==`/`IN`, Trie for prefix), prune via a **partition key** — lore/milvus/search-and-consistency.md.

**6. Memory.** Quantize: IVF_SQ8 cuts ~70–75% vs FLOAT; PQ/RaBitQ go further at more recall cost; FP16/BF16/INT8 halve raw size. **mmap** (`queryNode.mmap.*` or `mmap.enabled` per collection/index) loads ~2–4× RAM — HNSW tolerates it, IVF degrades sharply; not on DiskANN/GPU or a loaded collection.

**7. Scale out.** Query-node **replicas** for read QPS/HA; shard for writes; resource groups per tenant — lore/milvus/scaling-and-architecture.md. GPU (CAGRA) wins on batch throughput, not light-load latency.

## Top anti-patterns
- Searching before load/index build → silent brute force (small/fresh collections feel slow); force `create_index()`.
- Defaults left on `nprobe`/`ef`, or `ef`/`search_list` < top_k.
- One-vector inserts (weak growing segments) — batch upsert then flush.
- Wrong `metric_type` vs the model (COSINE/L2/IP); normalize for IP.
- mmap on IVF then blaming latency; Strong reads everywhere; over-provisioning instead of quantizing.

## How to measure
Build a **FLAT** (exact) index for ground truth; track **recall@k** vs it while sweeping `ef`/`nprobe`/`refine_k` — never tune to latency alone. Benchmark QPS/**p99** at realistic `nq`/concurrency with **VectorDBBench**. Scrape Prometheus/Grafana for query latency, segment counts, load/compaction state, CPU (build intensive; query scales `nq`×`nprobe`). See lore/databases/resilience-and-observability.md; pool via lore/databases/connection-pooling.md.

## Sources
milvus.io/docs — performance_faq.md, index.md, disk_index.md, mmap.md, consistency.md · github.com/zilliztech/VectorDBBench
