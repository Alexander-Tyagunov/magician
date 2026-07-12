# Microsoft SQL Server — Performance

The high-signal entry point: fix in THIS order, and SEE each problem with the named tool. Deep detail lives in siblings — this is the checklist, not a restatement. Current **2025 (17.x)**; plan behavior is gated by DB **compat level**, not server build.

## Measure first
- **Actual plan, not estimated.** `SET STATISTICS XML ON` (or SSMS "Include Actual Execution Plan"); estimated-only = `SET SHOWPLAN_XML ON`. A large Estimated-vs-Actual row gap = a stats/CE problem, not an index one. Live Query Statistics shows row flow on an in-flight query.
- **Per-query cost:** `SET STATISTICS IO, TIME ON` — logical reads + CPU/elapsed. Heavy reads on a "seek" reveal a Key/RID Lookup loop.
- **Fleet view:** Query Store (regressions, forced plans, per-query waits since 2017) and `sys.dm_exec_query_stats` (rank by total_worker_time / logical_reads); `sys.dm_os_wait_stats` for the systemic bottleneck. DON'T tune from plans on tiny tables.

## The ordered playbook
1. **Right indexes** — covering (`INCLUDE`) to kill lookups, filtered for hot subsets, clustered columnstore + batch mode for analytic/fact scans. Design rules, key limits, missing-index DMV caveats: see lore/sqlserver/execution-plans-and-indexing.md.
2. **Sargable predicates** — no function or implicit conversion on the indexed column (same file).
3. **Current statistics** — stale stats → bad estimates → wrong plan; `UPDATE STATISTICS` or auto-update after a bulk change (same file).
4. **Tame parameter sniffing** — below.
5. **Stabilize with Query Store** — force the good plan (`sp_query_store_force_plan`) or apply a Query Store hint, no app change. Default-ON for new DBs since **2022 (16.x)**; OFF on 2016–2019 — enable `ALTER DATABASE … SET QUERY_STORE = ON (OPERATION_MODE = READ_WRITE)`.
6. **Set-based + bulk** — kill row-by-row loops/cursors; bulk-load (`BULK INSERT`/`bcp`/`INSERT…SELECT`) with `TABLOCK` under SIMPLE/BULK_LOGGED for minimal logging.

## Parameter sniffing
One plan compiled for an atypical value, then reused for all.
- **2022 (16.x)/compat 160 PSP optimization** auto-builds variant plans (up to 3 skewed *equality* predicates), on by default; 2025/compat 170 adds DML + tempdb.
- Manual knobs: `OPTION (RECOMPILE)` (fresh plan per run), `OPTIMIZE FOR (@p = <typical>)`, `OPTIMIZE FOR UNKNOWN` (density average). Disable PSP per-query via `USE HINT('DISABLE_PARAMETER_SENSITIVE_PLAN')`. DON'T lower global compat to fix one query — scope it.

## TempDB contention
Allocation-page (GAM/SGAM/PFS) latch waits under concurrent temp-object churn show as `PAGELATCH_*` on pages like `2:1:1`.
- **DO** run multiple equal-sized data files: one per logical CPU up to 8, then add in multiples of 4 if contention persists; identical size + autogrow (proportional-fill). TF 1117/1118 unneeded since 2016.
- **DO** enable memory-optimized tempdb metadata (2019+) for metadata contention: `ALTER SERVER CONFIGURATION SET MEMORY_OPTIMIZED TEMPDB_METADATA = ON` (restart; bind to a Resource Governor pool). 2019 PFS + 2022 GAM/SGAM concurrency cut this natively.
- Watch `sys.dm_db_file_space_usage` / `sys.dm_db_task_space_usage`. Spills to tempdb come from bad memory grants — fix the estimate, don't grow tempdb.

## Pooling
Reuse pooled connections; open late, always close/dispose. Sizing, resiliency, encryption: see lore/sqlserver/connection-and-pooling.md.

## Sources
- learn.microsoft.com/sql/relational-databases/performance/{monitoring-performance-by-using-the-query-store, parameter-sensitive-plan-optimization, execution-plans}
- learn.microsoft.com/sql/relational-databases/databases/tempdb-database
