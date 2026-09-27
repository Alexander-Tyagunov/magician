# Weaviate — deep dive

> On-demand companion to `lore/weaviate.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Schema & Vectorizers](#schema-and-vectorizers) · [Indexing (HNSW) and Compression](#indexing-hnsw-and-compression) · [Query & Hybrid Search](#query-and-hybrid-search) · [Performance Playbook](#performance)

## Schema & Vectorizers <a id="schema-and-vectorizers"></a>

Version: Weaviate DB v1.38 stable (Jun 2026); supported window v1.36–1.38 (latest-3-minors). Self-hosted (Docker/k8s) or Weaviate Cloud. Clients: Python v4.16+, JS/TS v3.8+. Schema = "collections" (formerly "classes").

DO define collections explicitly up front — `vectorizer`, `vectorIndexType`, `properties`, `distance` are set at create time and `vectorizer` / `vectorIndexType` / `efConstruction` / `maxConnections` / `distance` are IMMUTABLE; changing them means drop + recreate + reindex.
DO match `distance` to how the embedding model was trained: `cosine` (default) / `dot` / `l2-squared` / `hamming` / `manhattan`. With `cosine`, Weaviate normalizes vectors to length 1 at read time and computes dot internally; with raw `dot`, unnormalized vectors give magnitude-dependent (unbounded) scores — normalize if your model expects it.
DO use NAMED VECTORS (a list under `vectorConfig`) when one object carries multiple embeddings (title vs body, image vs text) — each named vector gets its own vectorizer, index, distance, and quantizer. Add more later via `config.add_vector()` (v1.31), but it does NOT backfill existing objects.
DO pick the index type by scale: `hnsw` (default) for large/high-QPS; `flat` for small or per-tenant collections (brute force, pair with BQ); `dynamic` starts flat then auto-upgrades to HNSW past a threshold (needs async indexing enabled); `hfresh` (newer) supports only cosine/l2-squared, no dot.
DO set `vectorizer: none` and supply vectors yourself when you embed out-of-band; otherwise a `text2vec-*` module (openai / cohere / transformers / huggingface / ollama / jinaai) vectorizes on import AND query — keep the module identical for both.
DO control what gets embedded: per-property `skip` / `vectorizePropertyName` and collection-level `vectorizeCollectionName`; the concatenation order of vectorized text properties changes the resulting vector.
DO configure BM25 + tokenization for keyword/hybrid retrieval: `invertedIndexConfig.bm25` (`b`=0.75, `k1`=1.2, mutable), property `tokenization` (`word` default / `lowercase` / `whitespace` / `field`), `indexSearchable=true` for BM25, `indexFilterable`/`indexRangeFilters` for structured filters.
DO enable multi-tenancy for per-customer isolation: `multiTenancyConfig.enabled` (immutable) with `autoTenantCreation` (v1.25) / `autoTenantActivation` (v1.25.2); each tenant is its own shard.

DON'T expect edits to vectorizer / index type / efConstruction / maxConnections / distance — recreate the collection instead.
DON'T rely on multi-vector embeddings (ColBERT/ColPali, v1.29) outside HNSW named vectors — unsupported on flat/dynamic.
DON'T assume adding a property or a named vector re-embeds existing objects; backfill explicitly.
DON'T mismatch the metric to the model (e.g. L2 on cosine-trained embeddings) — recall silently degrades.

For HNSW knobs (maxConnections/ef/efConstruction) + PQ/BQ/SQ/RQ compression see lore/deep/weaviate.md#indexing-hnsw-and-compression; for hybrid alpha/fusion + filter strategy see lore/deep/weaviate.md#query-and-hybrid-search; tuning playbook lore/deep/weaviate.md#performance.

### Sources
docs.weaviate.io/weaviate/config-refs/collections · /config-refs/indexing/vector-index · /config-refs/distances · /manage-collections/vector-config · /search/hybrid

## Indexing (HNSW) and Compression <a id="indexing-hnsw-and-compression"></a>

Current: v1.38.x stable (active lines 1.36/1.37/1.38); self-hosted or Weaviate Cloud. Per-collection `vectorIndexType` + `vectorIndexConfig`; each named vector gets its own index + compression.

### Choose the index type
DO keep `hnsw` (default) for normal collections — fast ANN, higher build cost/RAM.
DO use `flat` (brute force) for small or many-tenant collections (one small index per tenant); exact, cheap, disk-friendly. PQ and SQ are NOT supported on flat (BQ and RQ are).
DO consider `dynamic` (v1.25, needs `ASYNC_INDEXING`): starts flat, auto-converts (one-way) to HNSW past `threshold` (default 10000).

### HNSW knobs (recall ↔ latency ↔ memory)
- `maxConnections` (M, default 32) and `efConstruction` (default 128): graph quality, set at BUILD time and IMMUTABLE. Higher = better recall, more RAM/slower build.
- `ef` (default -1 = dynamic): query-time search width, MUTABLE. When -1, bounded by `dynamicEfMin` 100 / `dynamicEfMax` 500 / `dynamicEfFactor` 8 (× limit). Pin a fixed `ef` (e.g. 64–256) once you tune; higher ef = higher recall, slower query.
- `distance` (default `cosine`; also `dot`, `l2-squared`, `hamming`, `manhattan`) — IMMUTABLE and MUST match how the embedding model was trained. cosine normalizes to unit length; use `dot` only on pre-normalized vectors.
- `vectorCacheMaxObjects` (default 1e12): RAM cap for decompressed vectors. `cleanupIntervalSeconds` 300: tombstone cleanup after deletes.

### Filtered search (pre-filter + over-filtering)
Weaviate pre-filters: inverted index builds an allow-list, HNSW walks only matching IDs. `filterStrategy` default `acorn` (v1.34) — multi-hop + seeded entrypoints, big win when the filter is tight and poorly correlated with the query; legacy `sweeping` still selectable. `flatSearchCutoff` (default 40000) auto-switches to brute force when the filtered set is small — cheaper and dodges HNSW recall collapse under heavy filtering.

### Compression / quantization
DEFAULT: none. `DEFAULT_QUANTIZATION` env (v1.33) sets a default for new collections. Once enabled, quantization CANNOT be disabled — decide before bulk load.
- RQ (recommended): 8-bit ≈4x, ~98–99% recall (HNSW GA v1.32, flat v1.35); 1-bit ≈32x, moderate recall (HNSW v1.33, flat v1.35). No codebook training.
- PQ: centroids (default/max 256), segments auto from dims (v1.23), `trainingLimit` 100000/shard. Prefer AutoPQ (trains at the limit, needs `ASYNC_INDEXING`). HNSW only.
- BQ: 1 bit/dim (~32x), NO training, flat AND hnsw — good for small sets and MUVERA/multi-vector.
- SQ: uint8 (~4x), HNSW only.
- `rescoreLimit`: fetch N candidates on compressed vectors, then rescore full-precision — restores precision lost to compression; raise if recall dips.

### ANN idioms
DO batch upserts (never one vector/request); build knobs (M, efConstruction, distance) are fixed at creation — recreate + reindex to change. DON'T ship an untuned index — sweep ef vs recall on a labeled set (lore/deep/weaviate.md#performance). DON'T mismatch metric to model, or compress then blame recall without rescore.

Related: lore/deep/weaviate.md#schema-and-vectorizers, lore/deep/weaviate.md#query-and-hybrid-search, lore/deep/weaviate.md#performance; lore/deep/databases.md#{connection-pooling,resilience-and-observability}

### Sources
docs.weaviate.io: config-refs/indexing/vector-index · configuration/compression (rq/pq/bq/sq) · concepts/filtering · github.com/weaviate/weaviate/releases

## Query & Hybrid Search <a id="query-and-hybrid-search"></a>

Version: Weaviate DB v1.38 stable (Jun 2026); clients Python v4.16+, JS/TS v3.8+. Vector (`nearVector`/`nearText`), keyword (`bm25`), and `hybrid` all accept `filters`, `limit`/`offset`, `groupBy`, and `targetVector`/`target_vector` (REQUIRED on named-vector collections).

DO tune recall↔latency at QUERY time via HNSW `ef` (per-query, overrides collection `ef`; `-1` = dynamic from limit): a wider beam raises recall AND latency. See lore/deep/weaviate.md#indexing-hnsw-and-compression.
DO bound similarity with EITHER `distance` OR `certainty` (mutually exclusive); `certainty` (0–1) is meaningful only for `cosine`. In hybrid, cap the vector leg with `maxVectorDistance`.
DO run `hybrid(query=, alpha=)`: `alpha` default 0.75 (1.0 = pure vector, 0.0 = pure BM25, 0.5 = even). Fusion `relativeScoreFusion` is default since v1.24 (normalize then add scores) vs `rankedFusion` (sum of 1/rank). Prefer relative-score; it is REQUIRED for autocut.
DO scope the keyword leg with `queryProperties`/`properties` + caret boosts (`["title^2","body"]`); this affects BM25 ONLY, not the vector leg. Pass your own `vector=` to override the embedded query.
DO tighten BM25 with the search operator (v1.31): `Or` + `minimum_match`/`minimumOrTokensMatch` (default `Or`), or `And` (all tokens within one property). BM25F scores `word`-tokenized text; use `trigram` tokenization for typo tolerance, else `lowercase`/`whitespace`/`field`. Stopwords are filtered at query time (v1.37, no reindex).
DO PRE-FILTER: pass `filters=` — Weaviate builds an inverted-index allow-list (uint64 ids) THEN walks HNSW, so filtered recall ≈ unfiltered (no brute-force scan). Needs `indexFilterable` (roaring bitmaps, default) / `indexRangeFilters` (int/number/date) / `indexSearchable` for BM25. Use `containsAny`/`containsAll`/`Not`, `by_ref` for cross-refs (slower).
DO leave `filterStrategy: acorn` (default v1.34): multi-hop traversal + extra matching entrypoints — much faster for RESTRICTIVE, low-correlation filters; `sweeping` is the older linear scan. Very selective filters (~<15% of data) auto-fall back to brute force over the matched subset.
DO two-stage retrieve→rerank: configure a reranker module, then `rerank(prop=, query=)` reorders the top `limit` hits with a heavier cross-encoder — keep `limit` small (cost is per-candidate). `autocut`/`auto_limit` trims to score cliffs; `return_metadata(score, explain_score)` / `explainScore` breaks out bm25/vector/hybrid contributions.

DON'T post-filter in app code — you lose recall guarantees and waste retrieved candidates; always push predicates via `filters=`.
DON'T pair `autocut` with `rankedFusion` (ranks have no score gaps to cut on) — use `relativeScoreFusion`.
DON'T omit `targetVector` on named-vector collections, or query raw `dot` on un-normalized vectors (unbounded, wrong ordering).
DON'T deep-paginate with a large `offset` (re-scans from 0) — narrow with filters + small `limit`, or cursor over ids.
DON'T set query `ef` too low to save latency — recall drops silently; measure recall per query set.

Tuning playbook: lore/deep/weaviate.md#performance. Schema/vectorizer/metric setup: lore/deep/weaviate.md#schema-and-vectorizers. Timeouts/retries/observability: lore/deep/databases.md#resilience-and-observability.

### Sources
docs.weaviate.io/weaviate/search/{hybrid,bm25,filters,rerank} · /weaviate/concepts/filtering · /weaviate/api/graphql/search-operators

## Performance Playbook <a id="performance"></a>

Version: Weaviate DB v1.38 stable (Jun 2026), supported v1.36–1.38; self-hosted or Weaviate Cloud. HNSW is default (flat/dynamic alternatives). ANN is approximate: every lever trades recall ↔ latency ↔ memory. Set a recall@k target first, then tune.

### Prioritized levers (highest leverage first)

1. DIMENSIONS — biggest memory lever. RAM ≈ 2 × (n_vectors × dims × 4B); the 2× covers Go GC + HNSW links (each `maxConnections` link ≈ 8–10B). 1M×1536-dim ≈ 12GB. Prefer a smaller model or matryoshka/truncated dims over more hardware.
2. QUANTIZATION (per (named) vector; undoing needs recreate). RQ recommended: 8-bit ≈ 4× smaller at 98–99% recall (v1.32); 1-bit ≈ 32× at moderate recall (v1.33). BQ ≈ 32× (coarse); PQ slightly beats 1-bit recall but encodes slower. Compressed vectors search first, then `rescoreLimit` candidates re-score on full vectors — raise it to buy recall at a latency cost. `DEFAULT_QUANTIZATION` (v1.33) sets a fleet default; flat rejects PQ/SQ.
3. HNSW query knob `ef` (mutable): raises recall AND latency. Default `-1` = dynamic (`dynamicEfMin` 100, `dynamicEfMax` 500, `dynamicEfFactor` 8). Start ~64; >512 gives diminishing recall. Use static `ef` for predictable tail latency.
4. HNSW build knobs (IMMUTABLE): `efConstruction` 128, `maxConnections` 32. Higher = better recall + more RAM/slower build. Cutting `maxConnections` saves RAM but hurts recall — offset by raising `efConstruction`/`ef`. Wrong here = drop + reindex.
5. THROUGHPUT: a single insert/search is single-threaded; concurrency + batching use all cores. Shard (even on one node) + add CPU for QPS/import speed. Replicas add read QPS + HA.

### Top anti-patterns

- One vector per request. BATCH upserts — the client parallelizes them; single inserts waste cores.
- Post-filtering / fetch-then-drop. Weaviate PRE-filters via a roaring-bitmap allow-list (no brute force); build `indexFilterable` (default) and `indexRangeFilters` (int/number/date, new props only). Over-filtering rarely tanks recall (graph links still followed); filters under `flatSearchCutoff` (default 40000 ≈ 15%) auto-fall back to brute force. Keep `filterStrategy: acorn` (default v1.34) for low-correlation restrictive filters; else `sweeping`.
- Undersized RAM → OOM during import (imports out-allocate GC). Set `LIMIT_RESOURCES=true` or `GOMEMLIMIT` (~80–90%); enable `ASYNC_INDEXING=true` for background builds.
- `vectorCacheMaxObjects` below dataset size (default 1e12): a full cache drops wholesale and disk lookups are orders slower — keep it above live count during import.
- Mismatched distance metric — silent recall loss (see schema-and-vectorizers).

### How to measure

- Recall@k vs an exact baseline (flat index or `flatSearchCutoff: 0`) on a fixed query set; raise `ef` to target, then read the latency cost.
- Track p50/p95/p99 latency + QPS under concurrency, not one query. Watch heap, import rate, cache drops via `PROMETHEUS_MONITORING_ENABLED` metrics + spans (lore/deep/databases.md#resilience-and-observability).
- Siblings: lore/deep/weaviate.md#indexing-hnsw-and-compression, lore/deep/weaviate.md#query-and-hybrid-search, lore/deep/weaviate.md#schema-and-vectorizers; pooling: lore/deep/databases.md#connection-pooling.

### Sources
docs.weaviate.io/weaviate/concepts/resources · /config-refs/indexing/vector-index · /weaviate/configuration/compression/rq-compression · /weaviate/concepts/filtering · /deploy/configuration/env-vars
