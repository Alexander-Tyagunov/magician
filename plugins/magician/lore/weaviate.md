# Weaviate — core digest
Version: 1.38.x stable (self-hosted or Weaviate Cloud); features version-gated. Index: hnsw (default), flat (small/per-tenant), dynamic (auto flat→hnsw); params evolve.

DO match distance to the embedding model: cosine (default), dot, l2-squared, hamming, manhattan; normalize if needed (immutable).
DO tune HNSW (recall↔latency↔memory): efConstruction 128, maxConnections 32 (immutable); ef=-1 dynamic (dynamicEfMin 100/Max 500/Factor 8); raise ef for recall.
DO set schema up front; named vectors = multiple embeddings/object; vectorizer module (text2vec-*) or your own vectors.
DO batch imports — never one object per request.
DO quantize (RQ/PQ/BQ/SQ) + rescore for precision; DEFAULT_QUANTIZATION (1.33+) sets a collection default.
DO hybrid: alpha 1=vector, 0=keyword (BM25F); relativeScoreFusion default (1.24+), required for autocut.
DO use native multi-tenancy (tenants), not one collection/customer.

DON'T over-filter: excluding most candidates wrecks HNSW recall — add filterable indexes; flat suits tiny sets.
DON'T change dims or vectorizer after load — reindex.
DON'T ship defaults at scale: raise ef, size vectorCacheMaxObjects, choose quantization.

Deep dive when writing non-trivial Weaviate — read lore/weaviate/{schema-and-vectorizers,indexing-hnsw-and-compression,query-and-hybrid-search,performance}.md

## Sources
docs.weaviate.io/weaviate/config-refs/schema/vector-index · /search/hybrid · /config-refs/distances · /release-notes
