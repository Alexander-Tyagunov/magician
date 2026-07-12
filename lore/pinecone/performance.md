# Pinecone — Performance

Managed serverless vector DB — storage/compute separated, no version knob. You tune **recall ↔ latency ↔ read-unit cost**, not machines. **Measure first.**

## Prioritized levers (highest impact first)

1. **Namespace = your search space.** A query hits one namespace, so fewer records scanned = lower latency + fewer read units. One namespace per tenant/shard — never dump all in the default. See `lore/pinecone/metadata-and-namespaces.md`.
2. **Match the metric to the embedding model** — `cosine`/`dotproduct`/`euclidean`, fixed at create; sparse must be `dotproduct`. Wrong metric silently tanks recall, unfixable — recreate. See `lore/pinecone/indexes-and-upsert.md`.
3. **Keep `top_k` small; drop payloads you don't use.** `top_k` (max 10,000) and returned data drive read units + the 4 MB result cap. Set `include_values=false` / `include_metadata=false` unless needed; over-fetch only to feed a reranker.
4. **Pre-filter with lean, indexed metadata.** Filters drop non-matching records *before* ANN, so filtering is recall-safe (unlike single-node HNSW post-filter) — only make filtered fields `filterable` and keep metadata ≤40 KB flat JSON (`$in`/`$nin` cap 10,000). See `lore/pinecone/metadata-and-namespaces.md`.
5. **Batch writes / use import.** Upsert ≤1,000 records or 2 MB per request (100 req/s, 50 MB/s per namespace); never one vector per call. For bulk backfills / large datasets use async `import` from object storage (Standard/Enterprise; reads Parquet from S3/GCS/Azure). Writes ack 200 then apply async (eventually consistent). See `lore/pinecone/indexes-and-upsert.md`.
6. **Two-stage retrieve→rerank for quality.** Retrieve a wider `top_k`, then rerank `top_n` with a hosted model (`cohere-rerank-4-fast` ≤250 docs; `bge-reranker-v2-m3`/`pinecone-rerank-v0` ≤100). Rerank latency scales with docs/tokens — bound it. Hybrid: merge separate dense/sparse searches client-side. See `lore/pinecone/query-and-hybrid-search.md`.
7. **Cut dimensions at the source.** Dim is fixed per index (max 20,000); high dims cost memory + result size. Prefer a smaller model or matryoshka truncation.

## How to measure

- **Read units** (`pinecone_db_read_unit_count`) = the query cost signal; limit 2,000/s per index. Track it, not wall-clock alone.
- **Latency**: `rate(pinecone_db_op_query_duration_sum)/rate(pinecone_db_op_query_count)` (ms). **Throughput**: `rate(..._count[5m])`. Also `pinecone_db_record_total`, `pinecone_db_storage_size_bytes`.
- Console **Metrics** tab; Prometheus/Datadog need Builder+ plans.
- Pooling + observability: `lore/databases/{connection-pooling,resilience-and-observability}.md`.

## Top anti-patterns

- **Per-vector upserts** — batch or `import` instead.
- **Huge `top_k` / returning values** you discard — read-unit + 4 MB blowup.
- **Cold namespaces** — first query after idle pays an object-storage slab fetch; warm hot paths.
- **Wrong metric / dimension** for the model — unfixable post-create; recreate.
- **One giant namespace** for all tenants — bigger scan, slower and pricier.
- **Bloated / over-`filterable` metadata** — wasted storage; keep it flat, filterable only where filtered.

## Sources
- docs.pinecone.io/reference/architecture/serverless-architecture
- docs.pinecone.io/guides/search/search-overview · rerank-results
- docs.pinecone.io/reference/api/database-limits · guides/production/monitoring
