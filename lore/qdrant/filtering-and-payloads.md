# Qdrant — Filtering & Payloads

Version: Qdrant 1.x; features gated below — verify your deployment's minor. Payload = arbitrary JSON on points; filtering restricts ANN search to points matching conditions.

## Filter clauses & conditions
- Three clauses: `must` (AND), `should` (OR), `must_not` (NOR). Nest recursively; a `Filter` inside `must` is a sub-group.
- Conditions on `key`: `match` (`value` exact; `any` = IN, v1.1; `except` = NOT IN, v1.2), `range` (`gt/gte/lt/lte` for int/float), datetime `range` (RFC 3339, v1.8, UTC), `geo_bounding_box`, `geo_radius` (meters), `geo_polygon` (v1.6), `values_count` (array len), `is_empty` (missing/null/`[]`), `is_null`, `has_id`, `has_vector` (v1.13).
- Full-text `match`: `text` (all words present, v0.10), `text_any` (any term, v1.16), `phrase` (ordered tokens, v1.15; needs `phrase_matching:true`). Without a text index these fall back to slow substring scan.
- Arrays: dot paths (`country.cities[].population`); wrap array-element logic in a `nested` (v1.2) so conditions match the SAME element. `has_id` isn't allowed in `nested` — use a sibling `must`.

## Payload indexes (the filtering lever)
- Filtering an UNINDEXED field forces a full scan. Create a payload index per field: `PUT /collections/{c}/index {field_name, field_schema}`.
- Schemas: `keyword`, `integer`, `float`, `bool` (v1.4), `geo`, `datetime` (v1.8), `uuid` (v1.11), `text`. Integer index is parameterized (v1.8): `lookup`/`range` flags — disable one to cut memory, but `range` on a `lookup`-only index is very slow.
- `text` index params: `tokenizer` (`word` default/`whitespace`/`prefix`/`multilingual`), `min_token_len`, `max_token_len`, `lowercase` (default true).
- `on_disk:true` (v1.11) keeps the index off-heap (cold-latency cost); `is_tenant:true` (`keyword`/`uuid`) co-locates tenant data for multitenancy; `is_principal:true` optimizes a dominant sort/filter field (e.g. timestamp).

## How filtering meets HNSW
- Qdrant estimates filter cardinality from the payload index to pick: weak filter → plain HNSW; very strict filter (below `full_scan_threshold`, default ~10000 KiB) → full scan (rescore if quantized); middle band → filterable HNSW (payload-aware graph edges).
- CRITICAL: those extra edges are built only if the payload index exists BEFORE ingestion. Indexing a field after load forces an HNSW rebuild (e.g. bump `ef_construct` by 1). Over-filtering can fragment the graph — ACORN (v1.16) explores 2nd-hop neighbors to recover recall; `enable_hnsw:false` (v1.17) skips edge-building for sparse-only filters.
- Filtering never replaces rescoring: with quantization, filters + refine keep recall — see lore/qdrant/search-and-quantization.md.

## DON'T
- DON'T filter unindexed high-cardinality fields in the hot path.
- DON'T add the payload index after bulk upsert and expect filterable-HNSW speed without a rebuild.
- DON'T rely on substring/phrase match without a `text` index.
- DON'T over-index: each index costs memory/disk and slows writes — index only fields you filter on.

See lore/qdrant/collections-and-indexing.md, lore/qdrant/performance.md, lore/databases.md.

## Sources
qdrant.tech/documentation/concepts/{filtering,indexing,payload} · qdrant.tech/documentation/concepts/hybrid-queries
