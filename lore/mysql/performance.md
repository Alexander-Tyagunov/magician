# MySQL — Performance

Prioritized playbook — do these in order. InnoDB assumed. Gates: `EXPLAIN FORMAT=TREE` 8.0.16, `EXPLAIN ANALYZE` 8.0.18. LTS 8.4 / 9.7. Measure before you tune.

## 0. Measure first — you can't tune what you can't see
- **DO** find cost by aggregate: `performance_schema.events_statements_summary_by_digest` (normalized, in-memory) + its `sys` views. The file **slow log** (`slow_query_log=ON`, `long_query_time` default 10s, `log_queries_not_using_indexes`) misses high-QPS cheap queries. See lore/databases/resilience-and-observability.md.
- **DO** read the plan first: `EXPLAIN ANALYZE` (runs it — actual vs estimated rows; big gap = stale stats → `ANALYZE TABLE`). `type`/`Extra`/`key_len` decoding → lore/mysql/indexing-and-explain.md.
- **DON'T** benchmark on tiny tables — the optimizer rationally scans them.

## 1. Size the buffer pool (single biggest knob)
- **DO** fit the working set in `innodb_buffer_pool_size` — default is only **128M**. On a MySQL-only host, start `--innodb-dedicated-server` (default OFF): auto-sets pool to **~0.75×RAM** (>4GB; 0.5× for 1–4GB) plus redo capacity.
- **DO** watch `Innodb_buffer_pool_reads` (disk) vs `..._read_requests` (logical) — a rising miss ratio = pool too small.
- **DON'T** exceed RAM — swapping the pool is catastrophic.

## 2. Index for the query; keep predicates sargable
- **DO** build composites equality-first, range-last, `ORDER BY` last (leftmost-prefix); make hot queries **covering** (`Extra: Using index`) to skip the clustered bookmark lookup. Keep the PK small/monotonic (copied into every secondary index).
- **DON'T** compare an indexed column to a mismatched type (`WHERE varchar_col = 1`) or join across mismatched charset/collation — implicit coercion casts the *column* and disables the index → full scan. No bare function on an indexed column (use a functional index). Prune low-selectivity + unused indexes (`sys.schema_unused_indexes`).

## 3. Pool connections
Thread-per-connection: a warm bounded pool beats connect-per-request; keep `maxLifetime` < `wait_timeout`; front high fan-in with a pooler. See lore/mysql/connection-and-pooling.md + lore/databases/connection-pooling.md.

## 4. Write in bulk, not row-by-row
- **DO** batch many rows per `INSERT`, or `LOAD DATA` for imports; wrap in one transaction (`SET autocommit=0`…`COMMIT`) — autocommit flushes redo per row. Insert in PK order.
- **DO** for big trusted loads: `SET unique_checks=0`, `foreign_key_checks=0`. Disable redo (`ALTER INSTANCE DISABLE INNODB REDO_LOG`) **only** on a fresh, disposable instance. (`innodb_autoinc_lock_mode` is a startup-only option, already `2`/interleaved by default.)

## 5. Scale out — only after 0–4
- **Partitioning** buys **pruning** (skips partitions per the `WHERE` — confirm in `EXPLAIN`'s `partitions` column) + instant drop-partition purge; not a substitute for indexing. Rules: every unique/PK contains the partition key; no FKs; InnoDB/NDB only.
- **Read replicas**: reads → replicas, writes → source (no native sharding); guard with `super_read_only`; measure lag via `performance_schema.replication_applier_status_by_worker`, not `Seconds_Behind_Source`. See lore/mysql/replication-and-scale.md.
- **DO** bound runaway reads with `max_execution_time` (or the `MAX_EXECUTION_TIME(n)` hint).

## Sources
- refman/8.4/en: explain.html, innodb-buffer-pool-resize.html, innodb-dedicated-server.html, optimizing-innodb-bulk-data-loading.html, alter-instance.html, optimizer-hints.html, partitioning-pruning.html, statement-summary-tables.html, slow-query-log.html
