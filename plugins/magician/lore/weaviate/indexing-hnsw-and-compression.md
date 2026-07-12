# Weaviate — Indexing (HNSW) and Compression

Current: v1.38.x stable (active lines 1.36/1.37/1.38); self-hosted or Weaviate Cloud. Per-collection `vectorIndexType` + `vectorIndexConfig`; each named vector gets its own index + compression.

## Choose the index type
DO keep `hnsw` (default) for normal collections — fast ANN, higher build cost/RAM.
DO use `flat` (brute force) for small or many-tenant collections (one small index per tenant); exact, cheap, disk-friendly. PQ and SQ are NOT supported on flat (BQ and RQ are).
DO consider `dynamic` (v1.25, needs `ASYNC_INDEXING`): starts flat, auto-converts (one-way) to HNSW past `threshold` (default 10000).

## HNSW knobs (recall ↔ latency ↔ memory)
- `maxConnections` (M, default 32) and `efConstruction` (default 128): graph quality, set at BUILD time and IMMUTABLE. Higher = better recall, more RAM/slower build.
- `ef` (default -1 = dynamic): query-time search width, MUTABLE. When -1, bounded by `dynamicEfMin` 100 / `dynamicEfMax` 500 / `dynamicEfFactor` 8 (× limit). Pin a fixed `ef` (e.g. 64–256) once you tune; higher ef = higher recall, slower query.
- `distance` (default `cosine`; also `dot`, `l2-squared`, `hamming`, `manhattan`) — IMMUTABLE and MUST match how the embedding model was trained. cosine normalizes to unit length; use `dot` only on pre-normalized vectors.
- `vectorCacheMaxObjects` (default 1e12): RAM cap for decompressed vectors. `cleanupIntervalSeconds` 300: tombstone cleanup after deletes.

## Filtered search (pre-filter + over-filtering)
Weaviate pre-filters: inverted index builds an allow-list, HNSW walks only matching IDs. `filterStrategy` default `acorn` (v1.34) — multi-hop + seeded entrypoints, big win when the filter is tight and poorly correlated with the query; legacy `sweeping` still selectable. `flatSearchCutoff` (default 40000) auto-switches to brute force when the filtered set is small — cheaper and dodges HNSW recall collapse under heavy filtering.

## Compression / quantization
DEFAULT: none. `DEFAULT_QUANTIZATION` env (v1.33) sets a default for new collections. Once enabled, quantization CANNOT be disabled — decide before bulk load.
- RQ (recommended): 8-bit ≈4x, ~98–99% recall (HNSW GA v1.32, flat v1.35); 1-bit ≈32x, moderate recall (HNSW v1.33, flat v1.35). No codebook training.
- PQ: centroids (default/max 256), segments auto from dims (v1.23), `trainingLimit` 100000/shard. Prefer AutoPQ (trains at the limit, needs `ASYNC_INDEXING`). HNSW only.
- BQ: 1 bit/dim (~32x), NO training, flat AND hnsw — good for small sets and MUVERA/multi-vector.
- SQ: uint8 (~4x), HNSW only.
- `rescoreLimit`: fetch N candidates on compressed vectors, then rescore full-precision — restores precision lost to compression; raise if recall dips.

## ANN idioms
DO batch upserts (never one vector/request); build knobs (M, efConstruction, distance) are fixed at creation — recreate + reindex to change. DON'T ship an untuned index — sweep ef vs recall on a labeled set (performance.md). DON'T mismatch metric to model, or compress then blame recall without rescore.

Related: lore/weaviate/schema-and-vectorizers.md, lore/weaviate/query-and-hybrid-search.md, lore/weaviate/performance.md; lore/databases/{connection-pooling,resilience-and-observability}.md

## Sources
docs.weaviate.io: config-refs/indexing/vector-index · configuration/compression (rq/pq/bq/sq) · concepts/filtering · github.com/weaviate/weaviate/releases
