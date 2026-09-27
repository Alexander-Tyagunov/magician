# Chroma — deep dive

> On-demand companion to `lore/chroma.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Collections and usage](#collections-and-usage) · [Query and Filtering](#query-and-filtering) · [Performance](#performance)

## Collections and usage <a id="collections-and-usage"></a>

Stable 1.x (Rust single-node core; 1.0 rewrote the engine). Run: `PersistentClient(path=)` (embedded, on-disk), `Client()`/`EphemeralClient()` (in-memory, lost on exit), `HttpClient(host,port)` against `chroma run --path` (client/server), `CloudClient(api_key=)` (managed). One HNSW graph per collection.

### Collections
- DO create with `create_collection(name, embedding_function=, configuration=, metadata=)`; `get_or_create_collection` is idempotent (ignores create-args if it exists); `get_collection` returns name/metadata/configuration/embedding_function.
- Names: 3–512 chars, start/end lowercase-alnum, dots/dashes/underscores between, no `..`, not an IP, unique per database.
- DO page `list_collections(limit=, offset=)` (default 100, oldest→newest); `count()` for records, `peek()` for the first 10.
- DO `collection.modify(name=, metadata=, configuration=)` to rename/retune — only some HNSW knobs are mutable (below).
- DON'T treat `delete_collection` as reversible — it drops embeddings, documents, and metadata permanently.

### Configuration (HNSW + metric)
`configuration={"hnsw": {...}}`. Defaults: `space` l2, `ef_construction` 100, `max_neighbors` 16 (HNSW M), `ef_search` 100, `num_threads`=cores, `batch_size` 100, `sync_threshold` 1000, `resize_factor` 1.2.
- Immutable after create: `space`, `ef_construction`, `max_neighbors`. Mutable via `modify`: `ef_search`, `num_threads`, `batch_size`, `sync_threshold`, `resize_factor`.
- DO set `space` to match how the embedding model was trained — `cosine` (most text models), `ip`, or `l2`. **Default is `l2`; leaving l2 under a cosine-trained model silently tanks recall.** `space` must be one the EF supports.
- DO raise `ef_search` (query breadth) live for recall at latency cost; raise `ef_construction`/`max_neighbors` (build-time, immutable) for a higher-quality graph at more RAM/build time.
- Distributed/Chroma Cloud uses SPANN, not HNSW; its params aren't customizable yet.

### Embedding functions
- DO attach one EF per collection; passing `documents`/`query_texts` auto-embeds through it. Python default is `all-MiniLM-L6-v2` (ONNX, CPU); JS installs `@chroma-core/default-embed`.
- DO let the EF persist server-side (Python ≥1.1.13, JS ≥3.0.4) so `get_collection` reconstructs it; on older clients re-pass the identical EF or you embed with the wrong model. Keys resolve from env (`OPENAI_API_KEY`) or `api_key_env_var`.

### Writing & reading
- DO `add(ids=, documents=, embeddings=, metadatas=)` in batches — parallel lists, never one row per request. Supply documents (auto-embedded), embeddings, or both (both → stored as-is, no re-embed).
- DO `upsert(...)` for idempotent writes: `add` silently ignores duplicate `ids`; only upsert/update overwrite. Mismatched embedding dim raises.
- Metadata values: str/int/float/bool or homogeneous non-empty arrays — consumed by `where` filters.
- Dimensions fix at first insert; single-node Chroma has no PQ/SQ quantization, so RAM ≈ N×dims×4B — cut dims with a matryoshka/truncated model upstream.
- `query`/`get` return column-major arrays; filtering, `include`, and hybrid search live in query-and-filtering.

See lore/deep/chroma.md#{query-and-filtering,performance} and lore/databases.md.

### Sources
docs.trychroma.com/docs/collections/{manage-collections,configure,add-data} · querying-collections/query-and-get

## Query and Filtering <a id="query-and-filtering"></a>

Version: chromadb 1.x stable (1.5.x). Single-node/embedded uses HNSW; Chroma Cloud uses SPANN. Same collection API across Python/TS/Rust; queries run through the collection's embedding function unless you pass raw vectors.

### query vs get
`collection.query(...)` runs ANN nearest-neighbor search, ranked by distance. `collection.get(...)` fetches records by `ids` and/or filters with NO ranking — use it for lookups/pagination, not search.

DO pass `query_texts=[...]` when the collection has an embedding function: Chroma embeds each with THAT function. It is a batch API — send many query texts in one call, not one per query.
DO pass `query_embeddings=[...]` when no embedding function is attached, or to reuse precomputed vectors. Query dimension MUST equal stored dimension, and you must embed with the SAME model/version used at upsert — mismatched vectors return silently-wrong neighbors.
DO set `n_results` deliberately (default 10). Over-fetch, then rerank app-side rather than trusting raw top-k.
DO scope `include=["documents","metadatas","distances"]` — `distances` exist only on query results; `ids` always return. Omit `embeddings` unless needed (large payloads).
DON'T treat `distances` as similarity — they are raw metric distance (lower = closer for `l2`/`cosine`). Convert to a score if needed; know your `space`.
DON'T paginate `query`; paginate `get` with `limit`/`offset` (or explicit `ids`).

### Metadata filtering (`where`)
Operators: `$eq` `$ne` `$gt` `$gte` `$lt` `$lte` (scalars), `$in` `$nin` (lists), `$and` `$or` (nest clause lists), and `$contains` `$not_contains` for metadata holding a homogeneous scalar array (no empty/nested arrays). `{"page":10}` == `{"page":{"$eq":10}}`.

DO build `where` as structured dicts from validated app inputs — never string-concatenate a filter; treat it like a bound query.
DO index the fields you filter on at scale and keep metadata values typed consistently (an int stored as string won't match `$gt`).

### Document filtering (`where_document`)
Full-text over document text: `$contains`, `$not_contains`, `$regex`, `$not_regex`, combinable with `$and`/`$or`. CASE-SENSITIVE — normalize case at write+query time for case-insensitive matching.

### Filter ↔ ANN interaction (the key gotcha)
Filters constrain the candidate set the ANN search draws from. A filter that excludes most vectors is over-filtering: HNSW may not find enough valid neighbors within its budget, so recall drops and you get fewer/worse hits than `n_results`.
DO raise recall on selective filters via `ef_search` (local HNSW default 100, modifiable). Cloud SPANN tunes `search_nprobe` (default 64) but its config is server-managed/read-only.
DON'T post-filter in the app to fake selectivity — push predicates into `where`/`where_document` so the engine's filtered search runs, then verify recall.

### Hybrid / rerank
The newer Search API (dense+sparse hybrid, rerank, query builder) is a Chroma Cloud feature; on single-node, combine a dense query with `where`/`where_document` and rerank app-side.

See lore/deep/chroma.md#collections-and-usage (embedding functions, `space` choice) and lore/deep/chroma.md#performance (recall↔latency tuning). Filter-injection discipline: lore/deep/databases.md#parameterized-queries-and-injection.

### Sources
docs.trychroma.com/docs/querying-collections/{query-and-get,metadata-filtering,full-text-search} · docs.trychroma.com/docs/collections/configure · pypi.org/project/chromadb

## Performance <a id="performance"></a>

Version: Python `chromadb` 1.5.9; JS/TS client `chromadb` 3.x (~3.5.x — versioned independently of the Python package). Single-node HNSW (in-process hnswlib) keeps the whole graph + vectors in RAM; distributed/Cloud uses SPANN (server-managed, not user-tunable — set values are ignored). Levers below are single-node HNSW unless noted.

Canonical playbook — cross-ref lore/deep/chroma.md#collections-and-usage, lore/deep/chroma.md#query-and-filtering, and lore/deep/databases.md#{connection-pooling,resilience-and-observability}.

### Levers (highest ROI first)
1. **Match `space` to the model, once.** Set on create: `configuration={"hnsw":{"space":"cosine"}}` (`l2` default, or `ip`). Wrong metric silently wrecks recall, and you cannot change it after creation — recreate. Normalize vectors if the model expects cosine but you use `ip`.
2. **Batch every write.** `add`/`upsert` many vectors per call; never one-per-request. Stay under `client.get_max_batch_size()`. Bulk-load first, then query — build cost amortizes.
3. **Tune the recall↔latency dial at query time.** Raise `ef_search` (default 100) via `collection.modify(configuration={"hnsw":{"ef_search":N}})` for higher recall at more latency — cheapest knob, no rebuild.
4. **Set graph density at build time.** `max_neighbors` (Chroma's HNSW *M*, default 16) and `ef_construction` (default 100): higher = better recall but more RAM and slower build. Pick before bulk load; changing them means a rebuild.
5. **Cut dimensions.** Fewer dims = less RAM and less CPU per compare. Use a Matryoshka-capable model and truncate (request smaller `dimensions`) instead of storing full-width vectors you don't need.
6. **Build hnswlib for your CPU.** Default wheels skip SIMD/AVX: `pip install --no-binary :all: chroma-hnswlib` (or Docker `--build-arg REBUILD_HNSWLIB=true`).
7. **Defragment after churn.** Heavy update/delete fragments the index (more RAM/disk, slower queries, lower recall) — compact with `chops hnsw rebuild`.

### Anti-patterns
- One vector per `add()`; row-by-row ingestion.
- Default `l2` when the model was trained for cosine, with no normalization.
- Collection larger than RAM on single-node HNSW (it is memory-resident) — split by collection or move to Cloud/SPANN.
- Aggressive `where`/`where_document` over a huge collection with a small `ef_search`: over-filtering starves the ANN graph. Widen `ef_search`/`n_results`; keep filter fields low-cardinality.
- Turning `ef_search`/`max_neighbors` knobs blindly without measuring recall.
- Long-lived update/delete churn with no `rebuild`.

### How to measure
- **Recall@k:** compute exact brute-force top-k on a query sample, compare to Chroma's; sweep `ef_search` and plot recall vs p95 latency.
- **Latency:** p50/p95/p99 at target concurrency, not single-shot.
- **Memory:** track process RSS / on-disk index size — graph + vectors must fit RAM.
- Re-measure after any `space`/`max_neighbors`/`ef_construction`/dimension change; those force a rebuild.

### Sources
docs.trychroma.com/docs/collections/configure · cookbook.chromadb.dev/running/performance-tips · github.com/chroma-core/chroma (v1.5.9)
