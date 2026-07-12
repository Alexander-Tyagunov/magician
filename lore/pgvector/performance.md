# pgvector — Performance

Version: 0.8.x (0.8.5). A PostgreSQL EXTENSION, so throughput first depends on Postgres itself (buffer cache, autovacuum, external pooling — see lore/postgres and lore/databases/{connection-pooling,resilience-and-observability}.md). ANN adds one dominant tradeoff: recall ↔ latency ↔ memory. Tuning the index is THE lever, not the SQL.

## Prioritized levers (highest ROI first)
1. Right index + build params. HNSW (m=16, ef_construction=64) for the recall/latency frontier; IVFFlat only for fast builds / low memory. Wrong opclass = wrong recall — match the metric the model trained on (`vector_cosine_ops`/`_ip_ops`/`_l2_ops`). See lore/pgvector/index-types-and-build.md.
2. Per-query recall dial. Raise `hnsw.ef_search` (default 40) or `ivfflat.probes` (default 1, start √lists) until recall targets are met, then stop — latency scales with it. Set per session/transaction, not globally. See lore/pgvector/query-and-tuning.md.
3. Fit the working set in RAM. Index random-reads the graph; if it spills to disk, p99 explodes. Cut bytes: `halfvec` (2B/dim, indexable ≤4000 dims) or `binary_quantize()`+bit index, then re-rank top-K by the original `vector` to restore precision. Keep hot index in `shared_buffers`/OS cache.
4. Build fast. Bulk `COPY` (FORMAT BINARY), THEN build the index. Bump `maintenance_work_mem` so the HNSW graph fits in memory (else builds crawl); raise `max_parallel_maintenance_workers` (default 2). Use `CREATE INDEX CONCURRENTLY` in prod.
5. Filtering. A selective WHERE over-filters HNSW and collapses recall. Enable `hnsw.iterative_scan` (`strict_order`/`relaxed_order`, 0.8+), cap with `hnsw.max_scan_tuples` (20000) / `hnsw.scan_mem_multiplier`; back filter columns with b-tree/GIN. See lore/pgvector/query-and-tuning.md.
6. Exact search (no index / recall=100%): raise `max_parallel_workers_per_gather` to parallelize the seq scan.

## Top anti-patterns
- One vector per INSERT, or rebuilding the index each write — batch instead.
- Indexing >2000 dims as `vector` — cast to `halfvec` or reduce (matryoshka/`subvector`).
- Query without `ORDER BY <op> ... LIMIT` — the ANN index is only used for that shape.
- Post-filtering without iterative scan; global `SET hnsw.ef_search` pinned high for all traffic.
- Tuning ef/probes without measuring recall against a ground-truth set.

## How to measure
- Latency + I/O: `EXPLAIN (ANALYZE, BUFFERS)` — confirm `Index Scan using ...hnsw`, watch shared read vs hit (spilling).
- Recall: sample queries, compute exact top-K (no index / `SET LOCAL enable_indexscan=off`), measure overlap vs ANN result; tune ef_search/probes to hit target.
- After big loads: `VACUUM ANALYZE`; `REINDEX INDEX CONCURRENTLY` before vacuuming a bloated index.

## Sources
github.com/pgvector/pgvector (0.8.5 README — indexing, iterative scan, tuning) · postgresql.org/docs (EXPLAIN, maintenance_work_mem, parallel workers)
