# Chroma — Performance

Version: Python `chromadb` 1.5.9; JS/TS client `chromadb` 3.x (~3.5.x — versioned independently of the Python package). Single-node HNSW (in-process hnswlib) keeps the whole graph + vectors in RAM; distributed/Cloud uses SPANN (server-managed, not user-tunable — set values are ignored). Levers below are single-node HNSW unless noted.

Canonical playbook — cross-ref lore/chroma/collections-and-usage.md, lore/chroma/query-and-filtering.md, and lore/databases/{connection-pooling,resilience-and-observability}.md.

## Levers (highest ROI first)
1. **Match `space` to the model, once.** Set on create: `configuration={"hnsw":{"space":"cosine"}}` (`l2` default, or `ip`). Wrong metric silently wrecks recall, and you cannot change it after creation — recreate. Normalize vectors if the model expects cosine but you use `ip`.
2. **Batch every write.** `add`/`upsert` many vectors per call; never one-per-request. Stay under `client.get_max_batch_size()`. Bulk-load first, then query — build cost amortizes.
3. **Tune the recall↔latency dial at query time.** Raise `ef_search` (default 100) via `collection.modify(configuration={"hnsw":{"ef_search":N}})` for higher recall at more latency — cheapest knob, no rebuild.
4. **Set graph density at build time.** `max_neighbors` (Chroma's HNSW *M*, default 16) and `ef_construction` (default 100): higher = better recall but more RAM and slower build. Pick before bulk load; changing them means a rebuild.
5. **Cut dimensions.** Fewer dims = less RAM and less CPU per compare. Use a Matryoshka-capable model and truncate (request smaller `dimensions`) instead of storing full-width vectors you don't need.
6. **Build hnswlib for your CPU.** Default wheels skip SIMD/AVX: `pip install --no-binary :all: chroma-hnswlib` (or Docker `--build-arg REBUILD_HNSWLIB=true`).
7. **Defragment after churn.** Heavy update/delete fragments the index (more RAM/disk, slower queries, lower recall) — compact with `chops hnsw rebuild`.

## Anti-patterns
- One vector per `add()`; row-by-row ingestion.
- Default `l2` when the model was trained for cosine, with no normalization.
- Collection larger than RAM on single-node HNSW (it is memory-resident) — split by collection or move to Cloud/SPANN.
- Aggressive `where`/`where_document` over a huge collection with a small `ef_search`: over-filtering starves the ANN graph. Widen `ef_search`/`n_results`; keep filter fields low-cardinality.
- Turning `ef_search`/`max_neighbors` knobs blindly without measuring recall.
- Long-lived update/delete churn with no `rebuild`.

## How to measure
- **Recall@k:** compute exact brute-force top-k on a query sample, compare to Chroma's; sweep `ef_search` and plot recall vs p95 latency.
- **Latency:** p50/p95/p99 at target concurrency, not single-shot.
- **Memory:** track process RSS / on-disk index size — graph + vectors must fit RAM.
- Re-measure after any `space`/`max_neighbors`/`ef_construction`/dimension change; those force a rebuild.

## Sources
docs.trychroma.com/docs/collections/configure · cookbook.chromadb.dev/running/performance-tips · github.com/chroma-core/chroma (v1.5.9)
