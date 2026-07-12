# ClickHouse — Performance

Ordered playbook: fix the biggest lever first, measure every change. Version-adaptive (25.x/26.x); verify gates. Checklist only; depth in the deep-dives.

## 0. Measure first
- DO find costly queries in `system.query_log`: sort by `query_duration_ms`, `read_rows`, `memory_usage`; group by `normalized_query_hash` for repeat offenders.
- DO read the plan: `EXPLAIN indexes=1` shows whether the primary index prunes granules or the query full-scans; `EXPLAIN PIPELINE` shows real parallelism. For honest timing `SET enable_filesystem_cache=0`. Plan discipline: lore/databases/indexing-and-query-plans.md.
- DON'T tune on tiny tables — scanning a small part is rational.

## 1. Ingest in big batches (the OLAP make-or-break)
- DO insert 10k–100k rows per batch (~1 insert/sec); each INSERT writes an immutable part; merges chase them. Tiny INSERTs → `Too many parts` stall.
- DO set `async_insert=1` (keep `wait_for_async_insert=1`) when clients can't batch — server buffering, adaptive since 24.2. Detail: lore/clickhouse/ingestion-and-inserts.md.

## 2. Shape ORDER BY around your filters (biggest read lever)
- DO make the `ORDER BY`/primary key a prefix of your hot filter+sort predicates, low-cardinality first — a sparse granule index, so a leading-column filter prunes most granules and compresses better. Coarse `PARTITION BY` (e.g. `toYYYYMM`) for pruning + cheap `DROP PARTITION`. Model: lore/clickhouse/mergetree-and-schema.md.
- DON'T over-partition (high-cardinality key) → part explosion.

## 3. Read fewer bytes per query
- DO select only needed columns — never `SELECT *` on wide tables (each column = separate I/O).
- DO rely on `PREWHERE` — automatic (`optimize_move_to_prewhere`, on) so the smallest/most-selective columns filter first; write it manually only to override. Tighten types (`LowCardinality`, narrow ints) to shrink scans.

## 4. Alternate access paths (when ORDER BY can't help)
- DO precompute: incremental **materialized views** (compute at insert) and **projections** (auto-synced reordered/pre-agg copy; confirm with `EXPLAIN projections=1`). See lore/clickhouse/materialized-views-and-query-perf.md.
- DO add a **data-skipping index** (`minmax`, `set`, `bloom_filter`) ONLY when the target column strongly correlates with the primary key — else every block matches, dead weight. Use the `text` index for full-text (`tokenbf_v1`/`ngrambf_v1` deprecated).

## 5. Keep FINAL & mutations off the hot path
- DO dedup with `ReplacingMergeTree` + query-time `GROUP BY`/`argMax`, not `SELECT … FINAL` on every read (merges are eventual). lore/clickhouse/mergetree-and-schema.md.
- DON'T run frequent `ALTER TABLE UPDATE/DELETE` mutations — they rewrite whole columns; use lightweight delete/update (small %) or `DROP PARTITION` for bulk.

## 6. Scale out
- DO shard with a `Distributed` table over `ReplicatedMergeTree` (co-locate by hash key for local JOINs) and enable `max_parallel_replicas` to parallelize a shard across replicas. Cloud: plain `MergeTree` → SharedMergeTree. lore/clickhouse/sharding-and-replication.md.

## 7. Resource knobs (last, not first)
- DO raise `max_threads` (default = CPU cores) for scan-heavy queries; lower it to cut memory. `max_insert_threads` (default 0/1) parallelizes `INSERT SELECT`.
- DO cap `max_memory_usage` (default 0 = unlimited per query) to protect the server, and enable spill via `max_bytes_before_external_group_by`/`_sort` (default 0 = in-memory) so big GROUP BY/ORDER BY don't OOM.

## Sources
- clickhouse.com/docs/optimize/{query-optimization,prewhere,skipping-indexes}
- clickhouse.com/docs/best-practices/selecting-an-insert-strategy
- ClickHouse src/Core/Settings.cpp — max_threads / max_memory_usage / max_insert_threads defaults
