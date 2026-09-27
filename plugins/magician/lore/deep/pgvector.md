# pgvector — deep dive

> On-demand companion to `lore/pgvector.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Index Types and Build](#index-types-and-build) · [Query and Tuning](#query-and-tuning) · [Performance](#performance)

## Index Types and Build <a id="index-types-and-build"></a>

pgvector 0.8.x (0.8.5) — a PostgreSQL extension, so ANN indexes are real access methods (`hnsw`, `ivfflat`) built with `CREATE INDEX`. Approximate indexes trade recall for speed; without one, search is exact (perfect recall, full scan). Match the opclass to how the model was trained — see lore/deep/pgvector.md#query-and-tuning for `ef_search`/`probes`.

### Choose the index type
- **HNSW** (graph): best recall/latency, slower builds, more memory. No training step — builds on an empty table and grows incrementally on insert. Default for most workloads.
- **IVFFlat** (inverted lists): faster builds, less memory, lower recall. Needs a k-means training step, so **create it only after the table holds representative data** — an empty/tiny table gives bad lists. `lists = rows/1000` (≤1M rows) or `sqrt(rows)` (>1M).

### Operator classes (metric must match the model)
Suffix by metric: `_l2_ops` (`<->`), `_ip_ops` (`<#>` dot), `_cosine_ops` (`<=>`), `_l1_ops` (`<+>`, HNSW only). Prefix by type: `vector_*`, `halfvec_*`, `sparsevec_*`, plus `bit_hamming_ops`/`bit_jaccard_ops`. IVFFlat covers L2/IP/cosine/Hamming only (no L1/Jaccard).
```sql
CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```
HNSW build knobs: `m` (links/layer, default 16), `ef_construction` (candidate list, default 64) — higher = better recall, slower build/insert. IVFFlat sets `lists` at build; recall is bought later via `ivfflat.probes`.

### Index dimension limits (below storage)
Storage allows up to 16,000 dims/nnz, but **indexes cap lower:** `vector` ≤2000, `halfvec` ≤4000, `bit` ≤64000, `sparsevec` ≤1000 nnz. Over 2000 dims → index `halfvec`, or reduce via `subvector`/matryoshka truncation.

### Quantization via expression indexes
Cut index memory without changing the column, then re-rank by the original vector:
```sql
-- half precision: ~2 B/dim, indexes up to 4000 dims
CREATE INDEX ON items USING hnsw ((embedding::halfvec(1536)) halfvec_cosine_ops);
-- binary quantization (binary_quantize, 0.7.0+): tiny index, coarse recall
CREATE INDEX ON items USING hnsw ((binary_quantize(embedding)::bit(1536)) bit_hamming_ops);
```

### Build fast
- Bulk-load with `COPY` first, **then** create the index — cheaper than inserting through an existing HNSW graph.
- Raise `maintenance_work_mem` so the HNSW graph fits in memory (a NOTICE warns on spill); not so high the server OOMs.
- Parallelize: `max_parallel_maintenance_workers` (default 2, plus a leader); may also need `max_parallel_workers` (default 8) raised.
- Production: `CREATE INDEX CONCURRENTLY` avoids an ACCESS EXCLUSIVE lock on writes (slower; a failed build leaves an INVALID index — drop and retry).
- Progress: `SELECT phase, round(100.0*blocks_done/nullif(blocks_total,0),1) FROM pg_stat_progress_create_index;`

### DON'T
- DON'T build IVFFlat on empty/small data — the k-means lists are meaningless; drop it until you have volume.
- DON'T index >2000-dim `vector` — cast to `halfvec` or truncate.
- DON'T expect NULL (or zero, under cosine) vectors to be indexed — they're skipped.
- DON'T just `VACUUM` a churned HNSW index (slow) — `REINDEX INDEX CONCURRENTLY`, then vacuum. See lore/deep/pgvector.md#performance and lore/deep/databases.md#resilience-and-observability.

### Sources
github.com/pgvector/pgvector (0.8.5 README: Indexing, HNSW/IVFFlat, Reference) · postgresql.org/docs (CREATE INDEX, pg_stat_progress_create_index)

## Query and Tuning <a id="query-and-tuning"></a>

pgvector 0.8.x (0.8.5), a PostgreSQL extension. Complements lore/postgres.md and lore/databases.md — here: making ANN queries hit the index, recall↔latency knobs, filtered/hybrid idioms.

### Get the index used
An HNSW/IVFFlat scan fires ONLY for `ORDER BY <col> <op> $q ASC LIMIT k` where `<op>` is a distance operator (`<->` L2, `<#>` neg inner product, `<=>` cosine, `<+>` L1, `<~>` hamming, `<%>` jaccard) applied directly — not wrapped in an expression. `ORDER BY 1 - (embedding <=> $q) DESC` does NOT use the index; order by raw distance ascending, convert for display only.
DO verify with `EXPLAIN (ANALYZE, BUFFERS)` — expect an Index Scan, not a Sort over Seq Scan.
DO nudge off a seq scan on small/misestimated tables: `SET LOCAL enable_seqscan = off;` (per-tx).

### Recall knobs (per query, SET LOCAL)
- HNSW `hnsw.ef_search` (default 40): raise (100–400) for recall at latency cost; must be ≥ LIMIT.
- IVFFlat `ivfflat.probes` (default 1): raise toward ≈`sqrt(lists)`; `probes = lists` degenerates to exact (planner skips index).
Tune ONE query at a time and measure; don't set these globally.

### Filtered ANN (the recall trap)
With an ANN index the WHERE filter applies AFTER the index returns candidates, so a selective filter can return far fewer than `k` rows (over-filtering). Cheapest first:
- Iterative scans (0.8): `SET hnsw.iterative_scan = strict_order | relaxed_order` (default `off`); IVFFlat supports `relaxed_order` only. Scans more of the index until `k` filtered rows are found. `relaxed_order` may return slightly out-of-order rows; bound work with `hnsw.max_scan_tuples` (default 20000) and `hnsw.scan_mem_multiplier` (default 1× work_mem).
- Partial index per hot filter value: `CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops) WHERE (tenant_id = 42);`.
- B-tree on the filter column when matches are a small % of rows — filter first, exact-order the survivors.
- Distance threshold: MATERIALIZED CTE with `embedding <=> $q AS dist`, filter `WHERE dist < 0.3` outside it; on PG 17+ add `+ 0` to the ORDER BY key to keep strict ordering.

### Re-ranking (quantized → exact)
Over-fetch with a compact/approx representation, then re-order by the full vector:
```sql
SELECT * FROM (
  SELECT * FROM items
  ORDER BY binary_quantize(embedding)::bit(768) <~> binary_quantize($q) LIMIT 200
) s ORDER BY s.embedding <=> $q LIMIT 10;
```
Same over-fetch → re-rank → LIMIT-k for `halfvec` and `subvector()` (matryoshka) indexes.

### Metric & value gotchas
- Operator/opclass MUST match training: cosine `<=>`, dot `<#>`, L2 `<->`. Normalized embeddings? prefer `<#>`, the NEGATIVE inner product (Postgres indexes ascending) — negate to display.
- NULL vectors are never indexed; zero vectors are skipped for cosine — both silently drop from results.
- Exact recall baseline: `SET LOCAL enable_indexscan = off;` (raise `max_parallel_workers_per_gather` to speed the brute-force scan), then compare approx top-k against it.

### Hybrid search
Combine dense ANN with Postgres FTS (`tsvector @@ plainto_tsquery`, rank via `ts_rank_cd`) and fuse rankings with Reciprocal Rank Fusion or a cross-encoder reranker.

See lore/deep/pgvector.md#performance for lever order and lore/deep/pgvector.md#index-types-and-build for M / ef_construction / lists tradeoffs.

### Sources
github.com/pgvector/pgvector (0.8.5 README — Querying, Filtering, Iterative Index Scans, Hybrid Search) · postgresql.org/docs/current

## Performance <a id="performance"></a>

Version: 0.8.x (0.8.5). A PostgreSQL EXTENSION, so throughput first depends on Postgres itself (buffer cache, autovacuum, external pooling — see lore/postgres.md and lore/deep/databases.md#{connection-pooling,resilience-and-observability}). ANN adds one dominant tradeoff: recall ↔ latency ↔ memory. Tuning the index is THE lever, not the SQL.

### Prioritized levers (highest ROI first)
1. Right index + build params. HNSW (m=16, ef_construction=64) for the recall/latency frontier; IVFFlat only for fast builds / low memory. Wrong opclass = wrong recall — match the metric the model trained on (`vector_cosine_ops`/`_ip_ops`/`_l2_ops`). See lore/deep/pgvector.md#index-types-and-build.
2. Per-query recall dial. Raise `hnsw.ef_search` (default 40) or `ivfflat.probes` (default 1, start √lists) until recall targets are met, then stop — latency scales with it. Set per session/transaction, not globally. See lore/deep/pgvector.md#query-and-tuning.
3. Fit the working set in RAM. Index random-reads the graph; if it spills to disk, p99 explodes. Cut bytes: `halfvec` (2B/dim, indexable ≤4000 dims) or `binary_quantize()`+bit index, then re-rank top-K by the original `vector` to restore precision. Keep hot index in `shared_buffers`/OS cache.
4. Build fast. Bulk `COPY` (FORMAT BINARY), THEN build the index. Bump `maintenance_work_mem` so the HNSW graph fits in memory (else builds crawl); raise `max_parallel_maintenance_workers` (default 2). Use `CREATE INDEX CONCURRENTLY` in prod.
5. Filtering. A selective WHERE over-filters HNSW and collapses recall. Enable `hnsw.iterative_scan` (`strict_order`/`relaxed_order`, 0.8+), cap with `hnsw.max_scan_tuples` (20000) / `hnsw.scan_mem_multiplier`; back filter columns with b-tree/GIN. See lore/deep/pgvector.md#query-and-tuning.
6. Exact search (no index / recall=100%): raise `max_parallel_workers_per_gather` to parallelize the seq scan.

### Top anti-patterns
- One vector per INSERT, or rebuilding the index each write — batch instead.
- Indexing >2000 dims as `vector` — cast to `halfvec` or reduce (matryoshka/`subvector`).
- Query without `ORDER BY <op> ... LIMIT` — the ANN index is only used for that shape.
- Post-filtering without iterative scan; global `SET hnsw.ef_search` pinned high for all traffic.
- Tuning ef/probes without measuring recall against a ground-truth set.

### How to measure
- Latency + I/O: `EXPLAIN (ANALYZE, BUFFERS)` — confirm `Index Scan using ...hnsw`, watch shared read vs hit (spilling).
- Recall: sample queries, compute exact top-K (no index / `SET LOCAL enable_indexscan=off`), measure overlap vs ANN result; tune ef_search/probes to hit target.
- After big loads: `VACUUM ANALYZE`; `REINDEX INDEX CONCURRENTLY` before vacuuming a bloated index.

### Sources
github.com/pgvector/pgvector (0.8.5 README — indexing, iterative scan, tuning) · postgresql.org/docs (EXPLAIN, maintenance_work_mem, parallel workers)
