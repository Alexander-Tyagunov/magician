# Pinecone — Indexes and Upsert

Managed serverless vector DB (no self-hosted version). Verify current API version header (stable `2025-10`; document/BM25 schema is preview `2026-01.alpha`) and limits against live docs — pricing and hosted models evolve.

## Creating an index
- DO choose `vector_type`: `dense` (semantic) or `sparse` (lexical/learned). Sparse indexes MUST use `metric: dotproduct`; dense supports `cosine`, `dotproduct`, `euclidean` (euclidean returns *squared* distance, lower = closer).
- DO match `metric` to how your embedding model was trained. `cosine` normalizes internally (ignores magnitude); if you pick `dotproduct` for cosine-style models, L2-normalize vectors yourself first.
- DO set `dimension` to your model's output — it is FIXED for the index's life. Max 20,000. Prefer Matryoshka truncation (e.g. hosted `llama-text-embed-v2` supports 384/512/768/1024/2048) to cut memory/cost when recall allows.
- DO treat serverless as the default: `spec.serverless` with `cloud`+`region`, immutable after creation. Legacy pod indexes are effectively deprecated for new work — don't reach for pod `M`/`ef` knobs; Pinecone manages the ANN structure. Your levers are metric, dimension, namespaces, and filtering — not HNSW/IVF params.
- DO use `create_index_for_model` (integrated inference) when you want Pinecone to embed text server-side via `embed.model` + `field_map`. Note: integrated indexes can't be updated/imported with raw vectors of a mismatched shape, and require text ingestion (`upsert_records`).
- DO set `deletion_protection` and `tags` on important indexes.

## Upserting
- DO batch: up to 1000 records OR 2 MB per request (whichever first) — a dim-1536 + 2 KB metadata payload caps near ~245/batch. Integrated text upsert caps at 96 records (hosted model batch limit).
- DO parallelize: Python `async_req=True` with `pool_threads`, the `[grpc]` client for multiplexed throughput, or JS `Promise.all` over chunks. Never one vector per request.
- DO know semantics: same `id` OVERWRITES the whole record. To change part of a record use `update`, not upsert. `id`/`_id` max 512 chars; filterable metadata max 40 KB/record.
- DO supply sparse as `sparse_values` = `{indices, values}`, max 2048 non-zero entries.
- DON'T assume read-after-write: upserts are eventually consistent — a freshly upserted vector may not be immediately queryable. Poll `describe_index_stats` / retry rather than assuming instant visibility.
- DON'T upsert huge cold loads: for 10M+ records use bulk **import** (async `start_import`) from Parquet on S3/GCS/Azure — far cheaper than write-unit upserts. Import namespaces must NOT pre-exist (`__default__` subdir must be empty); indexing after load takes ≥10 min.

## Namespaces and metadata at write time
- DO write into a namespace (created on first upsert; `__default__` is the default) to isolate tenants — see lore/pinecone/metadata-and-namespaces.md.
- DO decide metadata indexing at CREATION: all fields are filterable by default; restrict via a `schema` with `filterable: true` fields (index- or namespace-level) to cut cost/memory. This is IMMUTABLE after creation.

Query/hybrid/rerank: lore/pinecone/query-and-hybrid-search.md. Tuning + measurement: lore/pinecone/performance.md. Universal rules: lore/databases.md.

## Sources
- https://docs.pinecone.io/guides/index-data/create-an-index
- https://docs.pinecone.io/guides/index-data/upsert-data
- https://docs.pinecone.io/guides/index-data/import-data
