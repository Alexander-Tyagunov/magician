# Qdrant — deep dive

> On-demand companion to `lore/qdrant.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Collections and indexing](#collections-and-indexing) · [Filtering & Payloads](#filtering-and-payloads) · [Search & Quantization](#search-and-quantization) · [Performance](#performance)

## Collections and indexing <a id="collections-and-indexing"></a>

Stable 1.18.x (self-hosted or Qdrant Cloud). One HNSW graph per collection or named vector; segments are indexed lazily by the optimizer.

### Collection + vector params
- DO set `size` (fixed per index) and `distance`: `Cosine`, `Dot`, `Euclid`, `Manhattan`. Cosine = dot over vectors Qdrant auto-normalizes on upsert; match the metric your embedding model was trained on.
- DO name vectors when a point carries several (v0.10+); each gets its own size/distance and can override `hnsw_config`/`quantization_config`/`on_disk` (per-vector since v1.1.1).
- DO add sparse vectors (v1.7) for dense+sparse hybrid; their distance is always Dot — set `modifier: idf` (v1.10) for IDF term weighting.
- DO set `datatype: uint8` (v1.9) for pre-quantized int embeddings; float32 is default.
- DO batch upserts; never one point per request.

### Vector index (HNSW)
Defaults: `m` 16 (edges/node), `ef_construct` 100 (build breadth), `full_scan_threshold` 10000 KiB (below → brute force; 1KiB≈1×256d vec). Search `hnsw_ef`/`ef` defaults to `ef_construct`.
- DO raise `m` + `ef_construct` for recall (more RAM/build time); raise per-query `ef` to trade latency for recall.
- DO set `on_disk: true` (v1.2) to memmap vectors and/or the graph for large collections on NVMe.
- The optimizer builds HNSW per segment once unindexed data passes `indexing_threshold` (optimizers_config, default 20000 KiB); until then queries full-scan. Set it 0 to disable HNSW.
- DON'T revert `ef_construct` to force a rebuild — bumping it by 1 re-indexes; keep the new value.

### Payload indexes
- DO create payload indexes BEFORE bulk ingest: filterable HNSW only adds filter-aware edges (`payload_m`) when the index already exists.
- Types: `keyword`, `integer` (parameterized `lookup`/`range`, v1.8), `float`, `bool` (v1.4), `geo`, `datetime` (v1.8), `uuid` (v1.11), `text` (full-text: tokenizer word/whitespace/prefix/multilingual, stemmer, stopwords).
- DO set `is_tenant: true` (v1.11; keyword/uuid) to colocate a tenant's points on disk for multi-tenancy; `is_principal: true` for the dominant range field (e.g. timestamps).
- DO set payload index `on_disk: true` (v1.11) to save RAM; enable ACORN (v1.16) for highly selective filters to avoid HNSW recall collapse from over-filtering.
- DON'T leave high-selectivity filters unindexed — Qdrant Cloud blocks unindexed filtering by default (strict mode).

### Quantization
- DO scalar `int8` (4×; `quantile` e.g. 0.99, `always_ram`) as the safe default; binary (32×) for high-dim centered embeddings; product (`x4`–`x64`) only when RAM is the hard limit (slower, not SIMD-friendly).
- DO keep originals on disk + quantized in RAM (`on_disk: true` + `always_ram: true`) with `oversampling` + `rescore` at query time to restore precision.
- DON'T trust binary/PQ recall without rescore; DON'T pick PQ when you need speed.

See lore/deep/qdrant.md#{search-and-quantization,filtering-and-payloads,performance} and lore/databases.md.

### Sources
qdrant.tech/documentation/concepts/{collections,indexing,optimizer} · guides/quantization · github.com/qdrant/qdrant/releases (1.18.2)

## Filtering & Payloads <a id="filtering-and-payloads"></a>

Version: Qdrant 1.x; features gated below — verify your deployment's minor. Payload = arbitrary JSON on points; filtering restricts ANN search to points matching conditions.

### Filter clauses & conditions
- Three clauses: `must` (AND), `should` (OR), `must_not` (NOR). Nest recursively; a `Filter` inside `must` is a sub-group.
- Conditions on `key`: `match` (`value` exact; `any` = IN, v1.1; `except` = NOT IN, v1.2), `range` (`gt/gte/lt/lte` for int/float), datetime `range` (RFC 3339, v1.8, UTC), `geo_bounding_box`, `geo_radius` (meters), `geo_polygon` (v1.6), `values_count` (array len), `is_empty` (missing/null/`[]`), `is_null`, `has_id`, `has_vector` (v1.13).
- Full-text `match`: `text` (all words present, v0.10), `text_any` (any term, v1.16), `phrase` (ordered tokens, v1.15; needs `phrase_matching:true`). Without a text index these fall back to slow substring scan.
- Arrays: dot paths (`country.cities[].population`); wrap array-element logic in a `nested` (v1.2) so conditions match the SAME element. `has_id` isn't allowed in `nested` — use a sibling `must`.

### Payload indexes (the filtering lever)
- Filtering an UNINDEXED field forces a full scan. Create a payload index per field: `PUT /collections/{c}/index {field_name, field_schema}`.
- Schemas: `keyword`, `integer`, `float`, `bool` (v1.4), `geo`, `datetime` (v1.8), `uuid` (v1.11), `text`. Integer index is parameterized (v1.8): `lookup`/`range` flags — disable one to cut memory, but `range` on a `lookup`-only index is very slow.
- `text` index params: `tokenizer` (`word` default/`whitespace`/`prefix`/`multilingual`), `min_token_len`, `max_token_len`, `lowercase` (default true).
- `on_disk:true` (v1.11) keeps the index off-heap (cold-latency cost); `is_tenant:true` (`keyword`/`uuid`) co-locates tenant data for multitenancy; `is_principal:true` optimizes a dominant sort/filter field (e.g. timestamp).

### How filtering meets HNSW
- Qdrant estimates filter cardinality from the payload index to pick: weak filter → plain HNSW; very strict filter (below `full_scan_threshold`, default ~10000 KiB) → full scan (rescore if quantized); middle band → filterable HNSW (payload-aware graph edges).
- CRITICAL: those extra edges are built only if the payload index exists BEFORE ingestion. Indexing a field after load forces an HNSW rebuild (e.g. bump `ef_construct` by 1). Over-filtering can fragment the graph — ACORN (v1.16) explores 2nd-hop neighbors to recover recall; `enable_hnsw:false` (v1.17) skips edge-building for sparse-only filters.
- Filtering never replaces rescoring: with quantization, filters + refine keep recall — see lore/deep/qdrant.md#search-and-quantization.

### DON'T
- DON'T filter unindexed high-cardinality fields in the hot path.
- DON'T add the payload index after bulk upsert and expect filterable-HNSW speed without a rebuild.
- DON'T rely on substring/phrase match without a `text` index.
- DON'T over-index: each index costs memory/disk and slows writes — index only fields you filter on.

See lore/deep/qdrant.md#collections-and-indexing, lore/deep/qdrant.md#performance, lore/databases.md.

### Sources
qdrant.tech/documentation/concepts/{filtering,indexing,payload} · qdrant.tech/documentation/concepts/hybrid-queries

## Search & Quantization <a id="search-and-quantization"></a>

Current stable 1.x (self-hosted or Qdrant Cloud). ANN is approximate: recall ↔ latency ↔ memory — tune the index. Prefer the unified `query_points` API (v1.10+) over legacy `search`.

### Search knobs (per-request `params`)
- `hnsw_ef` is THE recall/latency dial — the HNSW candidate beam at query time. Raise it per query (e.g. 64→256) until recall plateaus. Higher = better recall, more CPU.
- `exact: true` forces brute-force full scan (100% recall, slow). Use ONLY to compute ground truth for measuring recall, never on prod hot paths.
- `indexed_only: true` skips segments still building their graph to bound tail latency.
- Build-time `m` (default 16) and `ef_construct` (default 100) cap achievable recall; `hnsw_ef` can't recover recall a too-low `m` left on the table. See lore/deep/qdrant.md#collections-and-indexing.

### Distance metric MUST match the model
Pick `Cosine`, `Dot`, `Euclid` (L2), or `Manhattan` (L1) to match how the embedding model was trained. Cosine normalizes internally; for `Dot` you must L2-normalize or scores are meaningless. Dims are fixed at collection creation — truncate (matryoshka) before ingest, not after.

### Quantization (`quantization_config`)
Applied at index time; originals retained for rescoring. Set per collection or per named vector.
- Scalar (`int8`): ~4x smaller, SIMD-fast, error usually <1%. `quantile` (e.g. 0.99) clips outliers; `always_ram: true` pins quantized vectors in RAM. Best default.
- Binary: 1-bit = 32x; `encoding` (v1.15) `two_bits`=16x, `one_and_half_bits`=24x. Fastest; suits high-dim, roughly centered distributions (~0.98 recall@100 reachable on 1536-dim vectors with rescore + oversampling). `query_encoding` (v1.15) enables asymmetric scoring (`scalar8bits`/`scalar4bits`).
- Product: `compression` `x4`..`x64` via k-means centroids. Highest compression but NOT SIMD-friendly (slower) and lossier — use only when RAM is the hard constraint.

### Rescore & oversampling (`params.quantization`)
- `rescore: true` re-ranks the quantized shortlist with full-precision vectors. Default ON for binary; OFF for scalar/product — enable there when recall matters.
- `oversampling` (v1.3, e.g. 2.0–3.0) fetches limit×factor via quantized distance, then rescores to `limit`. This is how binary/product recover precision — pair it WITH rescore.
- `ignore: true` bypasses quantized vectors for that query.
- Tier: quantized in RAM + `on_disk: true` originals is the sweet spot; if disk is slow, dropping rescore trades recall for latency.

### Filtering & recall (over-filtering)
A selective filter can strand the HNSW walk in a disconnected region and tank recall. Qdrant mitigates with filterable HNSW (extra payload-based edges via `payload_m`) and, for hard/combined filters, ACORN (v1.16) which explores second-hop neighbors. Create payload indexes BEFORE ingest so the edges exist; see lore/deep/qdrant.md#filtering-and-payloads.

### Hybrid & reranking
Combine dense + sparse (BM25/IDF) via `prefetch` sub-queries fused with `fusion: rrf` or `dbsf`, or rescore a dense prefetch with a reranker/late-interaction vector. Keep each prefetch `limit` modest.

Measure: compute ground truth with `exact: true`, then report recall@k while sweeping `hnsw_ef`/`oversampling`; load-test tail latency apart — see lore/deep/qdrant.md#performance and lore/deep/databases.md#resilience-and-observability.

### Sources
qdrant.tech/documentation/guides/quantization · /concepts/search · /concepts/indexing

## Performance <a id="performance"></a>

Version: current stable 1.18.x (self-hosted or Qdrant Cloud). HNSW vector index; scalar/product/binary + TurboQuant (1.18) quantization; per-collection optimizer/segment tuning. Verify param names/defaults against your release — they evolve.

The core tradeoff is recall ↔ latency ↔ memory. Levers below are ordered by typical payoff.

### Prioritized levers (biggest wins first)

1. Keep hot vectors in RAM, and size it. Estimate `vectors × dim × 4 bytes × 1.5` (the ×1.5 covers indexes, versions, temp segments). Rule of thumb: storing half your vectors in RAM roughly doubles search latency. If it won't fit, quantize before offloading to disk.
2. Quantize to shrink the working set. `scalar` int8 = 4x, SIMD-accelerated, ~1% error — the safe default; keep quantized vectors resident with `always_ram: true` and push originals `on_disk: true`. `binary` = up to 32x and much faster, but only for high-dim, centered embeddings; `product` up to 64x but slower (no SIMD); TurboQuant (1.18) defaults to `bits4` (8x). Restore precision with `rescore` + `oversampling` (e.g. 2.0). See lore/deep/qdrant.md#search-and-quantization.
3. Tune HNSW to the recall target. Defaults `m: 16`, `ef_construct: 100`; raise `m`/`ef_construct` for recall (more RAM, slower build), raise query-time `ef`/`hnsw_ef` for recall at latency cost. On-disk HNSW (`on_disk: true`, e.g. `m: 64, ef_construct: 512`) trades RAM for IOPS-bound latency; `inline_storage` (1.16) cuts disk IO at ~3-4x storage. See lore/deep/qdrant.md#collections-and-indexing.
4. Match segments to your goal via `default_segment_number` (0 = auto ≈ CPU cores). Latency: segments ≈ cores so one query fans across cores. Throughput: fewer (~2), larger segments handle more parallel requests.
5. Index the payload fields you filter on BEFORE ingest, so filterable-HNSW edges get built into the graph — otherwise you must rebuild HNSW. Over-restrictive filters fragment traversal (ACORN, 1.16, mitigates). See lore/deep/qdrant.md#filtering-and-payloads.
6. Threshold control: `indexing_threshold_kb` (default 10000; set 0 to skip indexing during bulk load, re-enable after) and `memmap_threshold` to memory-map large segments onto disk.

### Anti-patterns
- One-vector-per-request upserts — always batch; set `wait: false` for ingest throughput.
- Payload indexes created after loading data (forces a full HNSW rebuild).
- Distance metric mismatched to how the model was trained (normalize for cosine).
- All payload pinned in RAM — put non-filtered fields `on_disk`.
- Unbounded unindexed segments under heavy writes — use `indexed_only` / `prevent_unoptimized` (1.17) so queries skip slow full scans.
- Non-POSIX storage (WSL bind mounts → corruption); too-low open-file limit (OS error 24 — raise `ulimit -n`).

### How to measure
- Recall: run search with `exact: true` for ground truth, compare ANN results across `hnsw_ef` values.
- Quantization quality: compare `ignore: true` vs `false`.
- Disk-bound builds/search: measure IOPS (fio); watch the optimizer via `/collections/{name}/optimizations` + telemetry/metrics, and `update_queue` deferred-point count.
- Track p95/p99 latency alongside throughput; see lore/deep/databases.md#resilience-and-observability and lore/deep/databases.md#connection-pooling.

### Sources
qdrant.tech/documentation/ops-optimization/{optimize,optimizer} · guides/quantization · concepts/indexing · capacity-planning (v1.18)
