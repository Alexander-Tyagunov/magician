# Pinecone — Query & Hybrid Search
Managed serverless; verify vs your account (`X-Pinecone-Api-Version` now `2025-10`). Pricing/models evolve.

## Querying a dense index
- `query()` takes EITHER `vector` OR `id` (mutually exclusive; `id` reuses that record's vector). Plus `top_k` (1–10000), `namespace`, `filter`, `include_values`/`include_metadata`.
- DO leave `include_values`/`include_metadata` `false` unless needed — they bloat read units and latency at high `top_k`. Payload caps 4MB.
- Scores use the index metric (`cosine`/`dotproduct`/`euclidean`) — DON'T compare across indexes; metric must match the embedding model's training (normalize for cosine).
- Integrated-embedding indexes: `search` with `query.inputs.text` embeds the query; response is `result.hits[]` (`_id`,`_score`,`fields`) + `usage`.
- Eventually consistent: a just-upserted record may not appear at once. DON'T assume read-after-write.

## Metadata filtering
- `filter` ops: `$eq $ne $gt $gte $lt $lte $in $nin $exists $and $or`. Only `$and`/`$or` at top level. Shorthand `{"cat":"x"}` == `{"cat":{"$eq":"x"}}`.
- Types: string, number, boolean, list-of-strings. No nulls, nested objects, or non-string lists. `$in`/`$nin` ≤10000 values. Metadata ≤40KB/record.
- Filters apply server-side during search (not naive post-filter), so a selective filter narrows the scan rather than wrecking recall. DON'T pass a bare list value or `$eq:[...]` (compile errors) — use `$in`. More: lore/pinecone/metadata-and-namespaces.md.

## Hybrid (dense + sparse) search
Two shapes:
- **Single index** — must be `vector_type=dense`, `metric=dotproduct` (only combo accepting sparse). Upsert dense in `values`, sparse in `sparse_values={indices,values}`; query with both `vector` and `sparse_vector`. No sparse-only queries, no integrated embed/rerank here.
- **Separate dense + sparse indexes** linked by shared `_id` — enables sparse-only queries, integrated inference, and independent reranking.
- Weight signals with `alpha`: `combined = alpha*dense + (1-alpha)*sparse` (`1`=dense-only, `0`=sparse-only). Sparse/BM25 scores are unbounded while dotproduct sits ~[-1,1], so unweighted sparse dominates. `hybrid_score_norm(dense,sparse,alpha)` scales query vectors (index stores raw). Start ~0.75 for prose, ~0.25 for SKUs/IDs.
- Separate-index flow: over-fetch each (e.g. `top_k=40`), merge client-side (dedup by `_id`, sort `_score`), then rerank; full-text/BM25 also runs on FTS-enabled `string` fields.

## Reranking (cascading retrieval)
Over-fetch, then rerank to a small `top_n` — cheapest RAG quality lever. Via `rerank` inside `search` (`model`,`top_n`,`rank_fields`) or standalone `POST /rerank` (`model`,`query`,`documents`,`top_n`,`rank_fields` [default `["text"]`]). Reranked `_score` normalized 0–1.
- Models: `cohere-rerank-4-fast` (multi-field, ≤250 docs), `bge-reranker-v2-m3` (single field, ≤100), `pinecone-rerank-v0` (preview, ≤100). `cohere-rerank-3.5` deprecated (Jul 1 2026; after Aug 1 2026 auto-served by 4-fast with DIFFERENT scores — re-tune thresholds).

DO run independent queries concurrently (SDK v6+ async or a thread pool); scope every op to one `namespace`. Siblings: lore/pinecone/indexes-and-upsert.md, lore/pinecone/performance.md; lore/databases/resilience-and-observability.md.

## Sources
docs.pinecone.io/guides/search/{search-overview,hybrid-search,rerank-results,filter-by-metadata} · docs.pinecone.io/reference/api/latest/data-plane/query
