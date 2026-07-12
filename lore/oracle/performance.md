# Oracle Database — Performance

The prioritized playbook. Ground truth: the cost-based optimizer costs plans from **dictionary stats, not live data** — so tune in this order. Current stable **26ai**; **19c** the ubiquitous LTR. Many levers are license-gated (Diagnostics/Tuning Pack, Partitioning) — verify entitlement first.

## Do these, in order
1. **Keep stats fresh & honest.** `DBMS_STATS` with `AUTO_SAMPLE_SIZE` + `METHOD_OPT 'SIZE AUTO'`; add extended (column-group) stats for correlated predicates; gather right after bulk loads. Stale/absent stats drive every downstream mis-plan. Histograms + adaptive plans: `lore/oracle/optimizer-and-indexing.md`.
2. **Bind, don't literal.** `:x` avoids per-value hard parses and library-cache latch thrash; adaptive cursor sharing handles skew when a histogram exists. DON'T leave `CURSOR_SHARING=FORCE` on as a fix.
3. **Right access path / index.** B-tree for selective OLTP; **bitmap** only for low-NDV, read-mostly DW columns (never OLTP-hot — segment locking); **function-based** index (or fix the type) when a function/implicit conversion hides the column; cover the query to skip `TABLE ACCESS BY INDEX ROWID`. See optimizer-and-indexing.md.
4. **Partition big tables for pruning** (separately licensed EE option). RANGE/LIST/HASH/composite/interval. Confirm pruning in the plan's `PSTART/PSTOP`: `PARTITION RANGE SINGLE/ITERATOR` = pruned, `RANGE ALL` = not. DON'T wrap the partition key in a function or mismatch its type (defeats pruning as it does indexes) — use a **virtual-column partition** if queries must. Equipartition join keys for **partition-wise joins** (cut PX/RAC traffic).
5. **Result-cache expensive, stable aggregates.** `/*+ RESULT_CACHE */` — keep mode default `MANUAL` (`FORCE` latches and can cache non-deterministic PL/SQL). Size `RESULT_CACHE_MAX_SIZE`; auto-invalidated on base-table DML; watch `V$RESULT_CACHE_STATISTICS`. Read-mostly lookups from many client procs: the OCI **client result cache** (`CLIENT_RESULT_CACHE_SIZE`).
6. **Pool connections.** Reuse sessions (UCP/HikariCP client pool; DRCP for many idle clients) so you never pay dedicated-server spawn cost or hit ORA-00020. See `lore/oracle/connection-and-pooling.md`.

Cross-DB fundamentals: `lore/databases/{indexing-and-query-plans,connection-pooling,resilience-and-observability}.md`.

## How to measure (see it before you tune)
- **`SET AUTOTRACE ON`** (SQL*Plus/SQLcl) — fast plan + logical reads/sorts per statement.
- **Actual vs estimate**: run it, then `DBMS_XPLAN.DISPLAY_CURSOR(FORMAT=>'ALLSTATS LAST')` (with `GATHER_PLAN_STATISTICS`); a big **E-Rows vs A-Rows** gap = a cardinality/stats miss. `EXPLAIN PLAN` alone lies — compile-time only, never peeks binds.
- **Real-Time SQL Monitoring** (Tuning Pack): auto-tracks SQL run in parallel or ≥5s CPU/IO; `DBMS_SQL_MONITOR.REPORT_SQL_MONITOR`, `V$SQL_MONITOR` / `V$SQL_PLAN_MONITOR` — best for one slow/long statement, live per-step.
- **AWR + ASH** (Diagnostics Pack; gated by `CONTROL_MANAGEMENT_PACK_ACCESS`): `awrrpt.sql`/`DBMS_WORKLOAD_REPOSITORY` for system-wide load & top SQL; `V$ACTIVE_SESSION_HISTORY`/`ashrpt.sql` for what sessions waited on. Unlicensed? **Statspack** (free, no ASH/ADDM).

## Sources
docs.oracle.com/en/database/oracle/oracle-database/26/ — tgsql/generating-and-displaying-execution-plans.html · tgsql/monitoring-database-operations.html · tgsql/gathering-optimizer-statistics.html · tgdba/tuning-result-cache.html · partition pruning → …/23/vldbg/partition-pruning.html
