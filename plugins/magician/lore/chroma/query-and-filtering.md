# Chroma — Query and Filtering

Version: chromadb 1.x stable (1.5.x). Single-node/embedded uses HNSW; Chroma Cloud uses SPANN. Same collection API across Python/TS/Rust; queries run through the collection's embedding function unless you pass raw vectors.

## query vs get
`collection.query(...)` runs ANN nearest-neighbor search, ranked by distance. `collection.get(...)` fetches records by `ids` and/or filters with NO ranking — use it for lookups/pagination, not search.

DO pass `query_texts=[...]` when the collection has an embedding function: Chroma embeds each with THAT function. It is a batch API — send many query texts in one call, not one per query.
DO pass `query_embeddings=[...]` when no embedding function is attached, or to reuse precomputed vectors. Query dimension MUST equal stored dimension, and you must embed with the SAME model/version used at upsert — mismatched vectors return silently-wrong neighbors.
DO set `n_results` deliberately (default 10). Over-fetch, then rerank app-side rather than trusting raw top-k.
DO scope `include=["documents","metadatas","distances"]` — `distances` exist only on query results; `ids` always return. Omit `embeddings` unless needed (large payloads).
DON'T treat `distances` as similarity — they are raw metric distance (lower = closer for `l2`/`cosine`). Convert to a score if needed; know your `space`.
DON'T paginate `query`; paginate `get` with `limit`/`offset` (or explicit `ids`).

## Metadata filtering (`where`)
Operators: `$eq` `$ne` `$gt` `$gte` `$lt` `$lte` (scalars), `$in` `$nin` (lists), `$and` `$or` (nest clause lists), and `$contains` `$not_contains` for metadata holding a homogeneous scalar array (no empty/nested arrays). `{"page":10}` == `{"page":{"$eq":10}}`.

DO build `where` as structured dicts from validated app inputs — never string-concatenate a filter; treat it like a bound query.
DO index the fields you filter on at scale and keep metadata values typed consistently (an int stored as string won't match `$gt`).

## Document filtering (`where_document`)
Full-text over document text: `$contains`, `$not_contains`, `$regex`, `$not_regex`, combinable with `$and`/`$or`. CASE-SENSITIVE — normalize case at write+query time for case-insensitive matching.

## Filter ↔ ANN interaction (the key gotcha)
Filters constrain the candidate set the ANN search draws from. A filter that excludes most vectors is over-filtering: HNSW may not find enough valid neighbors within its budget, so recall drops and you get fewer/worse hits than `n_results`.
DO raise recall on selective filters via `ef_search` (local HNSW default 100, modifiable). Cloud SPANN tunes `search_nprobe` (default 64) but its config is server-managed/read-only.
DON'T post-filter in the app to fake selectivity — push predicates into `where`/`where_document` so the engine's filtered search runs, then verify recall.

## Hybrid / rerank
The newer Search API (dense+sparse hybrid, rerank, query builder) is a Chroma Cloud feature; on single-node, combine a dense query with `where`/`where_document` and rerank app-side.

See lore/chroma/collections-and-usage.md (embedding functions, `space` choice) and lore/chroma/performance.md (recall↔latency tuning). Filter-injection discipline: lore/databases/parameterized-queries-and-injection.md.

## Sources
docs.trychroma.com/docs/querying-collections/{query-and-get,metadata-filtering,full-text-search} · docs.trychroma.com/docs/collections/configure · pypi.org/project/chromadb
