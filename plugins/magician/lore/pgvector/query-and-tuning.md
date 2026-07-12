# pgvector — Query and Tuning

pgvector 0.8.x (0.8.5), a PostgreSQL extension. Complements lore/postgres and lore/databases — here: making ANN queries hit the index, recall↔latency knobs, filtered/hybrid idioms.

## Get the index used
An HNSW/IVFFlat scan fires ONLY for `ORDER BY <col> <op> $q ASC LIMIT k` where `<op>` is a distance operator (`<->` L2, `<#>` neg inner product, `<=>` cosine, `<+>` L1, `<~>` hamming, `<%>` jaccard) applied directly — not wrapped in an expression. `ORDER BY 1 - (embedding <=> $q) DESC` does NOT use the index; order by raw distance ascending, convert for display only.
DO verify with `EXPLAIN (ANALYZE, BUFFERS)` — expect an Index Scan, not a Sort over Seq Scan.
DO nudge off a seq scan on small/misestimated tables: `SET LOCAL enable_seqscan = off;` (per-tx).

## Recall knobs (per query, SET LOCAL)
- HNSW `hnsw.ef_search` (default 40): raise (100–400) for recall at latency cost; must be ≥ LIMIT.
- IVFFlat `ivfflat.probes` (default 1): raise toward ≈`sqrt(lists)`; `probes = lists` degenerates to exact (planner skips index).
Tune ONE query at a time and measure; don't set these globally.

## Filtered ANN (the recall trap)
With an ANN index the WHERE filter applies AFTER the index returns candidates, so a selective filter can return far fewer than `k` rows (over-filtering). Cheapest first:
- Iterative scans (0.8): `SET hnsw.iterative_scan = strict_order | relaxed_order` (default `off`); IVFFlat supports `relaxed_order` only. Scans more of the index until `k` filtered rows are found. `relaxed_order` may return slightly out-of-order rows; bound work with `hnsw.max_scan_tuples` (default 20000) and `hnsw.scan_mem_multiplier` (default 1× work_mem).
- Partial index per hot filter value: `CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops) WHERE (tenant_id = 42);`.
- B-tree on the filter column when matches are a small % of rows — filter first, exact-order the survivors.
- Distance threshold: MATERIALIZED CTE with `embedding <=> $q AS dist`, filter `WHERE dist < 0.3` outside it; on PG 17+ add `+ 0` to the ORDER BY key to keep strict ordering.

## Re-ranking (quantized → exact)
Over-fetch with a compact/approx representation, then re-order by the full vector:
```sql
SELECT * FROM (
  SELECT * FROM items
  ORDER BY binary_quantize(embedding)::bit(768) <~> binary_quantize($q) LIMIT 200
) s ORDER BY s.embedding <=> $q LIMIT 10;
```
Same over-fetch → re-rank → LIMIT-k for `halfvec` and `subvector()` (matryoshka) indexes.

## Metric & value gotchas
- Operator/opclass MUST match training: cosine `<=>`, dot `<#>`, L2 `<->`. Normalized embeddings? prefer `<#>`, the NEGATIVE inner product (Postgres indexes ascending) — negate to display.
- NULL vectors are never indexed; zero vectors are skipped for cosine — both silently drop from results.
- Exact recall baseline: `SET LOCAL enable_indexscan = off;` (raise `max_parallel_workers_per_gather` to speed the brute-force scan), then compare approx top-k against it.

## Hybrid search
Combine dense ANN with Postgres FTS (`tsvector @@ plainto_tsquery`, rank via `ts_rank_cd`) and fuse rankings with Reciprocal Rank Fusion or a cross-encoder reranker.

See lore/pgvector/performance.md for lever order and lore/pgvector/index-types-and-build.md for M / ef_construction / lists tradeoffs.

## Sources
github.com/pgvector/pgvector (0.8.5 README — Querying, Filtering, Iterative Index Scans, Hybrid Search) · postgresql.org/docs/current
