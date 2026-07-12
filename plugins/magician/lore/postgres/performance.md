# PostgreSQL — Performance

Ordered playbook: fix the biggest lever first, measure every change. Current stable 18; verify version gates. Depth lives in the linked deep-dives — this is the checklist, not a restatement.

## 0. Measure first — you can't tune what you can't see
- DO find costly queries before touching anything: `pg_stat_statements` (needs `shared_preload_libraries`), sort by `total_exec_time` — not gut feel. Live stalls: `pg_stat_activity` `wait_event`/`state`. See lore/databases/resilience-and-observability.md.
- DO read the plan with `EXPLAIN (ANALYZE, BUFFERS)` — ANALYZE actually runs it (wrap DML in `BEGIN…ROLLBACK`); BUFFERS is auto-on with ANALYZE in PG18. Estimated-vs-actual rows far apart ⇒ stale stats (`ANALYZE`); high `Buffers: read` ⇒ I/O; `loops=N` ⇒ per-loop averages. Plan-reading depth: lore/databases/indexing-and-query-plans.md.
- DON'T trust plans on tiny/empty tables — the planner rationally scans them.

## 1. Fix query shape (cheapest big wins)
- DO kill N+1: one JOIN/aggregate over the set, never a query per row in app code — a round-trip per row dwarfs any index.
- DO keep predicates sargable (bare column, no `func(col)`; else an expression index) — see lore/databases/indexing-and-query-plans.md.
- DO know CTE folding (PG12+): a non-recursive, side-effect-free `WITH` referenced once inlines; referenced more than once it materializes as a fence — `NOT MATERIALIZED` to push predicates down, `MATERIALIZED` to compute an expensive CTE once.

## 2. Index the right columns, right type
- DO index FK columns (unindexed FKs ⇒ slow joins + heavy locks on parent delete/update), plus filter and `ORDER BY` cols; order equality→range→sort. Types: B-tree default; partial (hot subset); covering `INCLUDE`; GIN (jsonb/FTS/array, `@>`); BRIN (append-only). Full matrix + `CREATE INDEX CONCURRENTLY`: lore/postgres/indexing-mvcc-and-vacuum.md.
- DON'T over-index — each index taxes every write and bloats.

## 3. Pool connections, cap max_connections
- DO front Postgres with PgBouncer transaction mode; keep `max_connections` modest (default 100) — a fork/backend per connection. Active pool ≈ `cores*2 + spindles`. lore/postgres/connection-and-pooling.md, lore/databases/connection-pooling.md.
- DON'T raise `max_connections` into the thousands to dodge pooling.

## 4. Kill bloat & long transactions
- DO tune (never disable) autovacuum and set `idle_in_transaction_session_timeout` — a long/idle txn pins `xmin` and stops vacuum DB-wide, growing bloat. lore/postgres/indexing-mvcc-and-vacuum.md.

## 5. Memory & parallelism
- DO raise `work_mem` when sorts/hashes spill (`Sort Method: external`/temp files in EXPLAIN) — but it is per-node per-session, so total is many × the value; hashes get ×`hash_mem_multiplier` (2.0). Default 4MB.
- DO allow parallelism: `max_parallel_workers_per_gather` (2), `max_parallel_workers` (8) ≤ `max_worker_processes` (8); each worker gets its own `work_mem`. `maintenance_work_mem` (64MB) speeds index builds/vacuum.

## 6. Scale big tables & bulk paths
- DO partition only when pruning leaves few partitions per query (RANGE for time-series + cheap retention). lore/postgres/partitioning-and-scale.md.
- DO bulk-load with `COPY` (far less overhead than many INSERTs); load first, then create indexes/FKs, then `ANALYZE`. Raise `maintenance_work_mem`/`max_wal_size` for the load.
- DO use server-prepared (`$1`) statements to skip re-parse/plan; PG averages 5 custom plans before trying a generic one (`plan_cache_mode auto`). Under txn pooling requires PgBouncer ≥1.21.

## Sources
- postgresql.org/docs/current/{using-explain,runtime-config-resource,populate,sql-prepare,queries-with}.html
- postgresql.org/docs/current/pgstatstatements.html
