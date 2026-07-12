# Microsoft SQL Server — Execution plans and indexing

Plans are gated by database **compat level** (140=2017, 150=2019, 160=2022, 170=2025), not server version — an upgrade keeps the old level until `ALTER DATABASE…SET COMPATIBILITY_LEVEL`.

**Read the actual plan** (`SET STATISTICS XML ON`), not estimated: the Estimated-vs-Actual row skew pinpoints bad estimates that cascade into wrong joins and grant spills. Add `SET STATISTICS IO,TIME ON` — heavy reads on a "seek" reveal a Key Lookup loop.

**Cardinality estimation.** New CE (2014) at compat 120+ is usually better but can regress a legacy-tuned query; pin legacy via `LEGACY_CARDINALITY_ESTIMATION=ON` without a global level drop.

**Statistics drive CE.** Auto-update fires past a mod threshold: compat ≤120 `500+0.20×n`; compat 130+ `MIN(500+0.20×n, SQRT(1000×n))` (pre-2016: trace flag 2371). Table variables get no column stats (1-row guess).

**Index structure.** The clustered index IS the table (leaf=data rows); its key is the row locator in every nonclustered (NC) index. A wide/random clustering key bloats and fragments all NC indexes — prefer narrow, unique, static, increasing, not-null keys. A NC seek for columns it lacks does a Key Lookup (clustered)/RID Lookup (heap) per row — catastrophic; fix with a covering index (key = predicate/join/sort cols, payload in `INCLUDE`, exempt from key limits). Key limits: since 2016, 32 key cols, 900 B clustered / 1700 B NC; before 2016 ALL index keys were 16 cols / 900 B. Composite order: equality cols first, then one range col (later cols stop seeking).

**Missing-index DMVs are hints, not prescriptions.** `sys.dm_db_missing_index_*` are compile-time guesses — blind to key order + INCLUDE cost, never clustered/unique/filtered/columnstore, cap 600 groups. Rank by `avg_total_user_cost × avg_user_impact × (seeks+scans)`, hand-order by selectivity; never create verbatim.

**Columnstore + batch mode.** Clustered columnstore packs a fact table into rowgroups up to 1,048,576; trickle loads (<102,400) wait in the deltastore for the tuple-mover. Batch mode (~900 rows/call) since 2019 (compat 150) extends to rowstore via `BATCH_MODE_ON_ROWSTORE` (default ON).

**IQP by version.** 2017/140: adaptive joins, interleaved execution for MSTVFs, batch-mode memory-grant feedback. 2019/150: batch mode on rowstore, table-variable deferred compilation, scalar UDF inlining. 2022/160: Parameter Sensitive Plan optimization, CE feedback, DOP feedback, optimized plan forcing.

**DON'T:** write non-sargable predicates — a function on the column or a column-side implicit conversion kills the seek. Rebuild on a live table without `ONLINE=ON` (Enterprise/Azure) — offline it takes a blocking Sch-M lock; add `WAIT_AT_LOW_PRIORITY` + `RESUMABLE=ON` (online rebuild 2017+, create 2019+). Ignore last-page contention on an increasing key (PAGELATCH_EX) — set `OPTIMIZE_FOR_SEQUENTIAL_KEY=ON` (2019+). Over-index write-heavy tables (each NC index taxes every DML). Lower global compat to fix one estimate — scope it (`OPTIMIZE FOR`, `RECOMPILE`, a legacy-CE hint, or a Query Store hint / forced plan via `sp_query_store_force_plan`, default-on since 2022).

## Sources
- learn.microsoft.com/sql/relational-databases/{performance/cardinality-estimation-sql-server, performance/intelligent-query-processing-details, sql-server-index-design-guide, indexes/columnstore-indexes-overview, statistics/statistics} · /t-sql/statements/create-index-transact-sql
