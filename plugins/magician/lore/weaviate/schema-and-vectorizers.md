# Weaviate — Schema & Vectorizers

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

For HNSW knobs (maxConnections/ef/efConstruction) + PQ/BQ/SQ/RQ compression see lore/weaviate/indexing-hnsw-and-compression.md; for hybrid alpha/fusion + filter strategy see lore/weaviate/query-and-hybrid-search.md; tuning playbook lore/weaviate/performance.md.

## Sources
docs.weaviate.io/weaviate/config-refs/collections · /config-refs/indexing/vector-index · /config-refs/distances · /manage-collections/vector-config · /search/hybrid
