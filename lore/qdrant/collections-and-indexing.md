# Qdrant — Collections and indexing

Stable 1.18.x (self-hosted or Qdrant Cloud). One HNSW graph per collection or named vector; segments are indexed lazily by the optimizer.

## Collection + vector params
- DO set `size` (fixed per index) and `distance`: `Cosine`, `Dot`, `Euclid`, `Manhattan`. Cosine = dot over vectors Qdrant auto-normalizes on upsert; match the metric your embedding model was trained on.
- DO name vectors when a point carries several (v0.10+); each gets its own size/distance and can override `hnsw_config`/`quantization_config`/`on_disk` (per-vector since v1.1.1).
- DO add sparse vectors (v1.7) for dense+sparse hybrid; their distance is always Dot — set `modifier: idf` (v1.10) for IDF term weighting.
- DO set `datatype: uint8` (v1.9) for pre-quantized int embeddings; float32 is default.
- DO batch upserts; never one point per request.

## Vector index (HNSW)
Defaults: `m` 16 (edges/node), `ef_construct` 100 (build breadth), `full_scan_threshold` 10000 KiB (below → brute force; 1KiB≈1×256d vec). Search `hnsw_ef`/`ef` defaults to `ef_construct`.
- DO raise `m` + `ef_construct` for recall (more RAM/build time); raise per-query `ef` to trade latency for recall.
- DO set `on_disk: true` (v1.2) to memmap vectors and/or the graph for large collections on NVMe.
- The optimizer builds HNSW per segment once unindexed data passes `indexing_threshold` (optimizers_config, default 20000 KiB); until then queries full-scan. Set it 0 to disable HNSW.
- DON'T revert `ef_construct` to force a rebuild — bumping it by 1 re-indexes; keep the new value.

## Payload indexes
- DO create payload indexes BEFORE bulk ingest: filterable HNSW only adds filter-aware edges (`payload_m`) when the index already exists.
- Types: `keyword`, `integer` (parameterized `lookup`/`range`, v1.8), `float`, `bool` (v1.4), `geo`, `datetime` (v1.8), `uuid` (v1.11), `text` (full-text: tokenizer word/whitespace/prefix/multilingual, stemmer, stopwords).
- DO set `is_tenant: true` (v1.11; keyword/uuid) to colocate a tenant's points on disk for multi-tenancy; `is_principal: true` for the dominant range field (e.g. timestamps).
- DO set payload index `on_disk: true` (v1.11) to save RAM; enable ACORN (v1.16) for highly selective filters to avoid HNSW recall collapse from over-filtering.
- DON'T leave high-selectivity filters unindexed — Qdrant Cloud blocks unindexed filtering by default (strict mode).

## Quantization
- DO scalar `int8` (4×; `quantile` e.g. 0.99, `always_ram`) as the safe default; binary (32×) for high-dim centered embeddings; product (`x4`–`x64`) only when RAM is the hard limit (slower, not SIMD-friendly).
- DO keep originals on disk + quantized in RAM (`on_disk: true` + `always_ram: true`) with `oversampling` + `rescore` at query time to restore precision.
- DON'T trust binary/PQ recall without rescore; DON'T pick PQ when you need speed.

See lore/qdrant/{search-and-quantization,filtering-and-payloads,performance}.md and lore/databases.md.

## Sources
qdrant.tech/documentation/concepts/{collections,indexing,optimizer} · guides/quantization · github.com/qdrant/qdrant/releases (1.18.2)
