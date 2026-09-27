# Pinecone — deep dive

> On-demand companion to `lore/pinecone.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Indexes and Upsert](#indexes-and-upsert) · [Metadata & Namespaces](#metadata-and-namespaces) · [Query & Hybrid Search](#query-and-hybrid-search) · [Performance](#performance)

## Indexes and Upsert <a id="indexes-and-upsert"></a>

Managed serverless vector DB (no self-hosted version). Verify current API version header (stable `2025-10`; document/BM25 schema is preview `2026-01.alpha`) and limits against live docs — pricing and hosted models evolve.

### Creating an index
- DO choose `vector_type`: `dense` (semantic) or `sparse` (lexical/learned). Sparse indexes MUST use `metric: dotproduct`; dense supports `cosine`, `dotproduct`, `euclidean` (euclidean returns *squared* distance, lower = closer).
- DO match `metric` to how your embedding model was trained. `cosine` normalizes internally (ignores magnitude); if you pick `dotproduct` for cosine-style models, L2-normalize vectors yourself first.
- DO set `dimension` to your model's output — it is FIXED for the index's life. Max 20,000. Prefer Matryoshka truncation (e.g. hosted `llama-text-embed-v2` supports 384/512/768/1024/2048) to cut memory/cost when recall allows.
- DO treat serverless as the default: `spec.serverless` with `cloud`+`region`, immutable after creation. Legacy pod indexes are effectively deprecated for new work — don't reach for pod `M`/`ef` knobs; Pinecone manages the ANN structure. Your levers are metric, dimension, namespaces, and filtering — not HNSW/IVF params.
- DO use `create_index_for_model` (integrated inference) when you want Pinecone to embed text server-side via `embed.model` + `field_map`. Note: integrated indexes can't be updated/imported with raw vectors of a mismatched shape, and require text ingestion (`upsert_records`).
- DO set `deletion_protection` and `tags` on important indexes.

### Upserting
- DO batch: up to 1000 records OR 2 MB per request (whichever first) — a dim-1536 + 2 KB metadata payload caps near ~245/batch. Integrated text upsert caps at 96 records (hosted model batch limit).
- DO parallelize: Python `async_req=True` with `pool_threads`, the `[grpc]` client for multiplexed throughput, or JS `Promise.all` over chunks. Never one vector per request.
- DO know semantics: same `id` OVERWRITES the whole record. To change part of a record use `update`, not upsert. `id`/`_id` max 512 chars; filterable metadata max 40 KB/record.
- DO supply sparse as `sparse_values` = `{indices, values}`, max 2048 non-zero entries.
- DON'T assume read-after-write: upserts are eventually consistent — a freshly upserted vector may not be immediately queryable. Poll `describe_index_stats` / retry rather than assuming instant visibility.
- DON'T upsert huge cold loads: for 10M+ records use bulk **import** (async `start_import`) from Parquet on S3/GCS/Azure — far cheaper than write-unit upserts. Import namespaces must NOT pre-exist (`__default__` subdir must be empty); indexing after load takes ≥10 min.

### Namespaces and metadata at write time
- DO write into a namespace (created on first upsert; `__default__` is the default) to isolate tenants — see lore/deep/pinecone.md#metadata-and-namespaces.
- DO decide metadata indexing at CREATION: all fields are filterable by default; restrict via a `schema` with `filterable: true` fields (index- or namespace-level) to cut cost/memory. This is IMMUTABLE after creation.

Query/hybrid/rerank: lore/deep/pinecone.md#query-and-hybrid-search. Tuning + measurement: lore/deep/pinecone.md#performance. Universal rules: lore/databases.md.

### Sources
- https://docs.pinecone.io/guides/index-data/create-an-index
- https://docs.pinecone.io/guides/index-data/upsert-data
- https://docs.pinecone.io/guides/index-data/import-data

## Metadata & Namespaces <a id="metadata-and-namespaces"></a>

Managed serverless vector DB; verify current API — GA except early-access flags noted inline.

### Metadata model
Each record carries flat key/value metadata. Value types: string, number (ints stored as 64-bit float), boolean, list of strings. NO nested objects, no null (drop the key), keys are strings not starting with `$`. Budget ~40KB per record — store filter keys + a small pointer, not whole documents (keep source text/blobs in your own store, reference by id).

### Filtering (single-stage ANN)
Pass `filter` at query time; filter and vector search run together, so results are top-k WITHIN the matching subset (not post-filtered). Operators: `$eq`,`$ne`,`$exists` (num/str/bool); `$gt`,`$gte`,`$lt`,`$lte` (number only); `$in`,`$nin` (str/num, ≤10,000 values). Only `$and`/`$or` at the top level. Shorthand `{"genre":"drama"}` == `$eq`. A list-valued field matches ANY of its values — you can't require two via `$and`, and a raw array as a filter value is a compile error.
- Over-filtering hurts recall/latency: a predicate excluding almost everything forces scanning far more of the namespace to fill top-k. Prefer namespaces for the highest-cardinality partition; reserve filters for secondary, less selective attributes.
- Numeric ranges need number type; years/prices stored as strings won't `$gt`.

### Selective metadata indexing
By default serverless indexes ALL metadata for filtering (costs build + query work). To restrict, declare `schema.fields` with `"filterable": true` — index-level rules apply to namespaces without their own; namespace rules override. Early access, API version `2025-10`, not in the CLI, and IMMUTABLE after index/namespace creation — plan the schema up front. Unindexed fields are stored and returned but not filterable.

### Namespaces
Records are partitioned into namespaces; every upsert/query/fetch/list targets exactly ONE namespace, created implicitly on first upsert (`"__default__"` for the unnamed default). One namespace per tenant/customer gives isolation AND speed — a scoped query scans only that partition, the biggest structural latency lever at scale. No cross-namespace query: to search several, fan out in parallel and merge/rerank client-side. Rename/move records isn't supported — delete + re-upsert.
- Scale: Standard/Enterprise handle very large namespace counts; >100k → contact support. Starter is limited.
- Manage: list returns up to 100 (page via `pagination_token`/`limit`); describe returns `record_count`; delete is IRREVERSIBLE.

### Rerank interplay
`fields` controls which metadata is returned; integrated `rerank` (`rank_fields`, `top_n` over `top_k` candidates) re-scores results from the queried namespace. Retrieve a wide `top_k` under your filter, then rerank down. See lore/deep/pinecone.md#query-and-hybrid-search.

DO partition the dominant tenant/segment as namespaces; filter on secondary attributes.
DO keep metadata lean; pin numeric fields to number type.
DO decide selective-index schema before creation (immutable).
DON'T post-filter client-side to fake missing operators — it under-fetches top-k.
DON'T rely on cross-namespace search or namespace rename — neither exists.

See also lore/deep/pinecone.md#indexes-and-upsert, lore/deep/pinecone.md#performance, lore/databases.md.

### Sources
docs.pinecone.io/guides: index-data/indexing-overview · search/filter-by-metadata · index-data/create-an-index · manage-data/manage-namespaces · search/rerank-results

## Query & Hybrid Search <a id="query-and-hybrid-search"></a>

Managed serverless; verify vs your account (`X-Pinecone-Api-Version` now `2025-10`). Pricing/models evolve.

### Querying a dense index
- `query()` takes EITHER `vector` OR `id` (mutually exclusive; `id` reuses that record's vector). Plus `top_k` (1–10000), `namespace`, `filter`, `include_values`/`include_metadata`.
- DO leave `include_values`/`include_metadata` `false` unless needed — they bloat read units and latency at high `top_k`. Payload caps 4MB.
- Scores use the index metric (`cosine`/`dotproduct`/`euclidean`) — DON'T compare across indexes; metric must match the embedding model's training (normalize for cosine).
- Integrated-embedding indexes: `search` with `query.inputs.text` embeds the query; response is `result.hits[]` (`_id`,`_score`,`fields`) + `usage`.
- Eventually consistent: a just-upserted record may not appear at once. DON'T assume read-after-write.

### Metadata filtering
- `filter` ops: `$eq $ne $gt $gte $lt $lte $in $nin $exists $and $or`. Only `$and`/`$or` at top level. Shorthand `{"cat":"x"}` == `{"cat":{"$eq":"x"}}`.
- Types: string, number, boolean, list-of-strings. No nulls, nested objects, or non-string lists. `$in`/`$nin` ≤10000 values. Metadata ≤40KB/record.
- Filters apply server-side during search (not naive post-filter), so a selective filter narrows the scan rather than wrecking recall. DON'T pass a bare list value or `$eq:[...]` (compile errors) — use `$in`. More: lore/deep/pinecone.md#metadata-and-namespaces.

### Hybrid (dense + sparse) search
Two shapes:
- **Single index** — must be `vector_type=dense`, `metric=dotproduct` (only combo accepting sparse). Upsert dense in `values`, sparse in `sparse_values={indices,values}`; query with both `vector` and `sparse_vector`. No sparse-only queries, no integrated embed/rerank here.
- **Separate dense + sparse indexes** linked by shared `_id` — enables sparse-only queries, integrated inference, and independent reranking.
- Weight signals with `alpha`: `combined = alpha*dense + (1-alpha)*sparse` (`1`=dense-only, `0`=sparse-only). Sparse/BM25 scores are unbounded while dotproduct sits ~[-1,1], so unweighted sparse dominates. `hybrid_score_norm(dense,sparse,alpha)` scales query vectors (index stores raw). Start ~0.75 for prose, ~0.25 for SKUs/IDs.
- Separate-index flow: over-fetch each (e.g. `top_k=40`), merge client-side (dedup by `_id`, sort `_score`), then rerank; full-text/BM25 also runs on FTS-enabled `string` fields.

### Reranking (cascading retrieval)
Over-fetch, then rerank to a small `top_n` — cheapest RAG quality lever. Via `rerank` inside `search` (`model`,`top_n`,`rank_fields`) or standalone `POST /rerank` (`model`,`query`,`documents`,`top_n`,`rank_fields` [default `["text"]`]). Reranked `_score` normalized 0–1.
- Models: `cohere-rerank-4-fast` (multi-field, ≤250 docs), `bge-reranker-v2-m3` (single field, ≤100), `pinecone-rerank-v0` (preview, ≤100). `cohere-rerank-3.5` deprecated (Jul 1 2026; after Aug 1 2026 auto-served by 4-fast with DIFFERENT scores — re-tune thresholds).

DO run independent queries concurrently (SDK v6+ async or a thread pool); scope every op to one `namespace`. Siblings: lore/deep/pinecone.md#indexes-and-upsert, lore/deep/pinecone.md#performance; lore/deep/databases.md#resilience-and-observability.

### Sources
docs.pinecone.io/guides/search/{search-overview,hybrid-search,rerank-results,filter-by-metadata} · docs.pinecone.io/reference/api/latest/data-plane/query

## Performance <a id="performance"></a>

Managed serverless vector DB — storage/compute separated, no version knob. You tune **recall ↔ latency ↔ read-unit cost**, not machines. **Measure first.**

### Prioritized levers (highest impact first)

1. **Namespace = your search space.** A query hits one namespace, so fewer records scanned = lower latency + fewer read units. One namespace per tenant/shard — never dump all in the default. See `lore/deep/pinecone.md#metadata-and-namespaces`.
2. **Match the metric to the embedding model** — `cosine`/`dotproduct`/`euclidean`, fixed at create; sparse must be `dotproduct`. Wrong metric silently tanks recall, unfixable — recreate. See `lore/deep/pinecone.md#indexes-and-upsert`.
3. **Keep `top_k` small; drop payloads you don't use.** `top_k` (max 10,000) and returned data drive read units + the 4 MB result cap. Set `include_values=false` / `include_metadata=false` unless needed; over-fetch only to feed a reranker.
4. **Pre-filter with lean, indexed metadata.** Filters drop non-matching records *before* ANN, so filtering is recall-safe (unlike single-node HNSW post-filter) — only make filtered fields `filterable` and keep metadata ≤40 KB flat JSON (`$in`/`$nin` cap 10,000). See `lore/deep/pinecone.md#metadata-and-namespaces`.
5. **Batch writes / use import.** Upsert ≤1,000 records or 2 MB per request (100 req/s, 50 MB/s per namespace); never one vector per call. For bulk backfills / large datasets use async `import` from object storage (Standard/Enterprise; reads Parquet from S3/GCS/Azure). Writes ack 200 then apply async (eventually consistent). See `lore/deep/pinecone.md#indexes-and-upsert`.
6. **Two-stage retrieve→rerank for quality.** Retrieve a wider `top_k`, then rerank `top_n` with a hosted model (`cohere-rerank-4-fast` ≤250 docs; `bge-reranker-v2-m3`/`pinecone-rerank-v0` ≤100). Rerank latency scales with docs/tokens — bound it. Hybrid: merge separate dense/sparse searches client-side. See `lore/deep/pinecone.md#query-and-hybrid-search`.
7. **Cut dimensions at the source.** Dim is fixed per index (max 20,000); high dims cost memory + result size. Prefer a smaller model or matryoshka truncation.

### How to measure

- **Read units** (`pinecone_db_read_unit_count`) = the query cost signal; limit 2,000/s per index. Track it, not wall-clock alone.
- **Latency**: `rate(pinecone_db_op_query_duration_sum)/rate(pinecone_db_op_query_count)` (ms). **Throughput**: `rate(..._count[5m])`. Also `pinecone_db_record_total`, `pinecone_db_storage_size_bytes`.
- Console **Metrics** tab; Prometheus/Datadog need Builder+ plans.
- Pooling + observability: `lore/deep/databases.md#{connection-pooling,resilience-and-observability}`.

### Top anti-patterns

- **Per-vector upserts** — batch or `import` instead.
- **Huge `top_k` / returning values** you discard — read-unit + 4 MB blowup.
- **Cold namespaces** — first query after idle pays an object-storage slab fetch; warm hot paths.
- **Wrong metric / dimension** for the model — unfixable post-create; recreate.
- **One giant namespace** for all tenants — bigger scan, slower and pricier.
- **Bloated / over-`filterable` metadata** — wasted storage; keep it flat, filterable only where filtered.

### Sources
- docs.pinecone.io/reference/architecture/serverless-architecture
- docs.pinecone.io/guides/search/search-overview · rerank-results
- docs.pinecone.io/reference/api/database-limits · guides/production/monitoring
