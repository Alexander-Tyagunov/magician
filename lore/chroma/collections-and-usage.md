# Chroma — Collections and usage

Stable 1.x (Rust single-node core; 1.0 rewrote the engine). Run: `PersistentClient(path=)` (embedded, on-disk), `Client()`/`EphemeralClient()` (in-memory, lost on exit), `HttpClient(host,port)` against `chroma run --path` (client/server), `CloudClient(api_key=)` (managed). One HNSW graph per collection.

## Collections
- DO create with `create_collection(name, embedding_function=, configuration=, metadata=)`; `get_or_create_collection` is idempotent (ignores create-args if it exists); `get_collection` returns name/metadata/configuration/embedding_function.
- Names: 3–512 chars, start/end lowercase-alnum, dots/dashes/underscores between, no `..`, not an IP, unique per database.
- DO page `list_collections(limit=, offset=)` (default 100, oldest→newest); `count()` for records, `peek()` for the first 10.
- DO `collection.modify(name=, metadata=, configuration=)` to rename/retune — only some HNSW knobs are mutable (below).
- DON'T treat `delete_collection` as reversible — it drops embeddings, documents, and metadata permanently.

## Configuration (HNSW + metric)
`configuration={"hnsw": {...}}`. Defaults: `space` l2, `ef_construction` 100, `max_neighbors` 16 (HNSW M), `ef_search` 100, `num_threads`=cores, `batch_size` 100, `sync_threshold` 1000, `resize_factor` 1.2.
- Immutable after create: `space`, `ef_construction`, `max_neighbors`. Mutable via `modify`: `ef_search`, `num_threads`, `batch_size`, `sync_threshold`, `resize_factor`.
- DO set `space` to match how the embedding model was trained — `cosine` (most text models), `ip`, or `l2`. **Default is `l2`; leaving l2 under a cosine-trained model silently tanks recall.** `space` must be one the EF supports.
- DO raise `ef_search` (query breadth) live for recall at latency cost; raise `ef_construction`/`max_neighbors` (build-time, immutable) for a higher-quality graph at more RAM/build time.
- Distributed/Chroma Cloud uses SPANN, not HNSW; its params aren't customizable yet.

## Embedding functions
- DO attach one EF per collection; passing `documents`/`query_texts` auto-embeds through it. Python default is `all-MiniLM-L6-v2` (ONNX, CPU); JS installs `@chroma-core/default-embed`.
- DO let the EF persist server-side (Python ≥1.1.13, JS ≥3.0.4) so `get_collection` reconstructs it; on older clients re-pass the identical EF or you embed with the wrong model. Keys resolve from env (`OPENAI_API_KEY`) or `api_key_env_var`.

## Writing & reading
- DO `add(ids=, documents=, embeddings=, metadatas=)` in batches — parallel lists, never one row per request. Supply documents (auto-embedded), embeddings, or both (both → stored as-is, no re-embed).
- DO `upsert(...)` for idempotent writes: `add` silently ignores duplicate `ids`; only upsert/update overwrite. Mismatched embedding dim raises.
- Metadata values: str/int/float/bool or homogeneous non-empty arrays — consumed by `where` filters.
- Dimensions fix at first insert; single-node Chroma has no PQ/SQ quantization, so RAM ≈ N×dims×4B — cut dims with a matryoshka/truncated model upstream.
- `query`/`get` return column-major arrays; filtering, `include`, and hybrid search live in query-and-filtering.

See lore/chroma/{query-and-filtering,performance}.md and lore/databases.md.

## Sources
docs.trychroma.com/docs/collections/{manage-collections,configure,add-data} · querying-collections/query-and-get
