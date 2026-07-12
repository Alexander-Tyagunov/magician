# PostgreSQL — Indexing, MVCC & vacuum

Version span 13→18 (current stable 18.4). PG18 adds an async-I/O subsystem (`io_method`, speeds seq/bitmap scans and vacuum) plus B-tree skip scan and `autovacuum_vacuum_max_threshold`; PG17 lifted VACUUM's old 1 GB memory cap. Verify any "since vX" against the target server before relying on it.

## MVCC: how row versions and dead tuples arise
Every heap tuple carries hidden `xmin` (creating XID) and `xmax` (deleting/obsoleting XID). UPDATE is never in-place — it writes a NEW tuple and stamps the old one's `xmax`; DELETE just stamps `xmax`. Each statement (Read Committed) or transaction (Repeatable Read / Serializable) runs against a snapshot; a tuple is visible if its `xmin` committed before the snapshot and `xmax` is unset or not-yet-visible. Hence readers never block writers. The cost: obsolete versions ("dead tuples") linger on-page until no snapshot can see them — that is bloat, and only VACUUM reclaims it.
- The oldest live snapshot pins the removal cutoff. A long query, an abandoned `idle in transaction` session, an unused replication slot, or `hot_standby_feedback = on` all hold back the global `xmin` and stop VACUUM from cleaning dead tuples DB-wide, even in unrelated tables. Hunt them: `SELECT pid, state, xact_start, backend_xmin FROM pg_stat_activity ORDER BY backend_xmin;` and set `idle_in_transaction_session_timeout`.

## Index types — pick by access pattern
- **B-tree** (default): `=`, range, `ORDER BY`, `IS NULL`, anchored `LIKE 'foo%'`. Backs UNIQUE/PK, multicolumn, `INCLUDE`. Multicolumn `(a,b)` historically needed a leading-`a` predicate; **PG18 skip scan** lets it serve `WHERE b = …` (or non-equality on `a`) by skipping distinct `a` values.
- **Hash**: `=` only; WAL-logged and crash-safe since 10, but rarely beats B-tree.
- **GIN**: multi-valued columns — `jsonb`, arrays, full-text (`tsvector`), trigram (`pg_trgm`). For containment use `jsonb_path_ops` + `@>` (smaller/faster than default `jsonb_ops`).
- **GiST**: geometry, ranges, exclusion constraints, nearest-neighbor (`ORDER BY geom <-> point`).
- **SP-GiST**: non-balanced (quadtree/trie) — points, IP/inet, text prefixes.
- **BRIN**: tiny per-block-range summaries; only pays off when the column is physically correlated with heap order (append-only timestamps/ids). PG14+ `minmax_multi` opclasses tolerate mild disorder.

## HOT updates — keep churn off the indexes
A **HOT** (heap-only tuple) update skips creating new index entries when (a) NO indexed column changed and (b) the new version fits on the same page. HOT chains are pruned during ordinary reads, not just VACUUM — a large win for hot-updated rows. Encourage it: lower `fillfactor` (`WITH (fillfactor=80)`) to reserve page space, and don't index columns you update frequently. Measure `n_tup_hot_upd / n_tup_upd` in `pg_stat_all_tables`. (BRIN is a "summarizing" index and does not block HOT eligibility.)

## Index-only scans & covering indexes
An index-only scan avoids the heap — but only for heap pages flagged all-visible in the **visibility map**, which VACUUM maintains. So on a write-heavy, under-vacuumed table, "index-only" plans still fault into the heap; watch `Heap Fetches` in EXPLAIN. `INCLUDE` adds non-key payload (`CREATE INDEX … (x) INCLUDE (y)`) so a covering index works without widening the uniqueness key. GIN never supports index-only scans (entries hold only part of the value).

## Building indexes without an outage
Plain `CREATE INDEX` takes a `SHARE` lock and blocks writes. On live tables use `CREATE INDEX CONCURRENTLY` (SHARE UPDATE EXCLUSIVE, writes continue): it does two heap passes, is slower, cannot run inside a transaction block, and on failure leaves an INVALID index you must `DROP INDEX` then recreate (check `pg_index.indisvalid`). `REINDEX INDEX CONCURRENTLY` (12+) rebuilds bloated indexes online. Always pair schema DDL with `SET lock_timeout` so a blocked `ALTER`/index build cannot queue an `ACCESS EXCLUSIVE` request ahead of normal traffic.

## VACUUM, freezing & wraparound
Plain `VACUUM` marks dead space reusable (non-blocking; space is returned to the OS only for trailing empty pages). `VACUUM FULL` and `CLUSTER` rewrite the table under `ACCESS EXCLUSIVE` — avoid on live tables; use them only for one-off heavy bloat. Beyond bloat, VACUUM must **freeze** old XIDs: XIDs are 32-bit, so every table must be vacuumed before ~2 billion transactions or wraparound makes committed rows vanish (WARNING at 40M remaining, writes refused at 3M). Track `age(relfrozenxid)` per table and `age(datfrozenxid)` per DB.
- Autovacuum fires at `autovacuum_vacuum_threshold` (50) + `autovacuum_vacuum_scale_factor` (0.2) × reltuples — too lazy on big tables; lower the per-table scale factor (e.g. `0.02`) on hot ones. Insert-mostly tables need `autovacuum_vacuum_insert_threshold` (1000, since 13) to get visibility-map/freeze maintenance. PG18 caps the computed trigger with `autovacuum_vacuum_max_threshold` (100M).
- Freeze knobs: `autovacuum_freeze_max_age` (200M) forces an anti-wraparound autovacuum even if autovacuum is disabled and even amid conflicting locks; `vacuum_failsafe_age` (14+, default 1.6B) makes VACUUM drop cost delays and skip index cleanup to race wraparound. PG18 `vacuum_max_eager_freeze_failure_rate` lets normal vacuums proactively freeze all-visible pages, cutting future aggressive-scan work.
- **PG17** removed VACUUM's silent 1 GB dead-tuple memory limit and stores TIDs far more compactly, so raising `maintenance_work_mem` / `autovacuum_work_mem` now genuinely reduces index-cleanup passes. Monitor with `pg_stat_progress_vacuum` (17 switched its counters to byte-based: `max_dead_tuple_bytes`, `num_dead_item_ids`). PG13+ vacuums multiple indexes in parallel, bounded by `max_parallel_maintenance_workers`.

## Diagnosing
Use `EXPLAIN (ANALYZE, BUFFERS)`: compare estimated vs actual rows (large gap ⇒ stale stats — run `ANALYZE` or raise `default_statistics_target`/`ALTER TABLE … SET STATISTICS`); a big `Rows Removed by Filter` signals dead-tuple bloat or a missing partial/expression index; high `Heap Fetches` on an index-only scan means the visibility map is stale (VACUUM). `ANALYZE` is a distinct step from space reclamation, though autovacuum runs both.

## Sources
postgresql.org/docs/current/routine-vacuuming.html · postgresql.org/docs/current/runtime-config-vacuum.html · postgresql.org/docs/current/indexes-index-only-scans.html · postgresql.org/docs/current/storage-hot.html · postgresql.org/docs/current/btree.html · postgresql.org/docs/release/18.0 · postgresql.org/docs/release/17.0
