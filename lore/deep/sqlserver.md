# Microsoft SQL Server — deep dive

> On-demand companion to `lore/sqlserver.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Connection & pooling](#connection-and-pooling) · [T-SQL & types](#tsql-and-types) · [Execution plans and indexing](#execution-plans-and-indexing) · [Performance](#performance) · [Transactions and isolation](#transactions-and-isolation)

## Connection & pooling <a id="connection-and-pooling"></a>

TDS behavior is cross-driver, but **pool knobs here are Microsoft.Data.SqlClient-only** — `mssql-jdbc`/`go-mssqldb` use external / `database/sql` pools. Current **2025 (17.x)**; 2017–2022 supported.

### Thread model

Thread-per-request (SQLOS), **not** process-per-connection; concurrency is capped by `max worker threads` (`0`=auto), not connection count. `user connections` defaults **`0` = 32,767 max** (dynamic; needs restart) — don't raise it to mask leaks.

### Client-side pooling (Microsoft.Data.SqlClient)

`Pooling=true` default. Pools key **per process, AppDomain, exact connection-string text, and (integrated security) Windows identity** — keyword order/whitespace forks another pool. `Max Pool Size`=**100**, `Min Pool Size`=**0**, `Connect Timeout`=**15s** (**30s** Azure). Saturated → requests queue to `Connect Timeout` then throw. Login/timeout failure → **blocking period** (5s, doubling to a 1-min cap), **off by default for Azure SQL**; tune `PoolBlockingPeriod`. Idle reaped ~**4–8 min**; `Load Balance Timeout`/`Connection Lifetime` (default `0`) caps connection age.

- **Reset on reuse:** `sp_reset_connection` rolls back transactions, drops temp tables, resets `SET` options and DB context to the connection's **default catalog (Initial Catalog)** — no state leak. Doesn't re-run login triggers; **can't** reset an activated app role (`sp_setapprole`) — that connection errors on reuse, so avoid app roles with pooling.
- **Always close/dispose** (`using`), or it isn't returned. `ClearPool`/`ClearAllPools` drop a poisoned pool (cleared on fatal errors, e.g. failover).
- **Fragmentation:** per-user integrated security or per-tenant strings multiply pools + idle sockets — use one common DB, then `USE`/`EXECUTE AS`.

### Encryption — default flipped

`Encrypt` defaults **`true`/Mandatory** in SqlClient **4.0+**, ODBC **18**, JDBC **10.2+** — cleartext upgrades fail without a trusted cert. SqlClient 5+ adds **`strict` = TDS 8.0** (TLS first, `TrustServerCertificate` ignored). With `TrustServerCertificate=false`, cert CN/SAN **must match** the server — use `HostNameInCertificate` (or `ServerCertificate` to pin), not `TrustServerCertificate=true`. 2025 adds **TLS 1.3 over TDS 8.0**.

### Connection resiliency & transient retry

`ConnectRetryCount` (**1** on-prem, **2** Azure SQL, **5** Azure serverless) × `ConnectRetryInterval` (**10s**) drive resiliency for **both** the initial `Open` (within `Connect Timeout`) **and** broken idle connections (within `Command Timeout`). They do **not** retry an in-flight command — mid-query + login-time transients (e.g. `40197, 40613, 11001`) still need app retry with backoff + jitter; make retried writes idempotent.

### HA/DR & Azure routing

- `ApplicationIntent=ReadOnly` → **read-only routing** to a readable AG secondary; pair with the listener. `MultiSubnetFailover=True` (default `False`) parallelizes across listener IPs — always set for listeners.
- **Azure SQL** fronts on a **1433** gateway. **Redirect** (default *inside* Azure) → the node (allow outbound **11000–11999**); **Proxy** (default *outside*) tunnels via 1433. Prefer Redirect where allowed.

### Sources

- learn.microsoft.com/sql/connect/ado-net/sql-server-connection-pooling · dotnet/api/microsoft.data.sqlclient.sqlconnection.connectionstring
- learn.microsoft.com/azure/azure-sql/database/{troubleshoot-common-connectivity-issues, connectivity-architecture}

## T-SQL & types <a id="tsql-and-types"></a>

Spans 2017 (14.x) → 2022 (16.x); current stable 2025 (17.x). Azure SQL DB/MI track "always up-to-date" and often gain features first. Gates noted inline.

### Strings, Unicode & UTF-8
- `nvarchar`/`nchar` store UTF-16 (`n` = byte-*pairs*, ≤4000); `varchar`/`char` store one code page (`n` = *bytes*, ≤8000) — `n` never counts characters. Prefix every Unicode literal `N'…'`: a bare `'…'` is parsed in the code page and silently drops non-representable chars before it reaches the column.
- UTF-8 collations (`…_UTF8`, 2019/15.x; char/varchar only) let `varchar` hold full Unicode: ASCII costs 1 byte (~50% smaller than nvarchar for mostly-ASCII), but CJK costs 3 bytes vs 2 in UTF-16 — choose by data. `_SC` supplementary support is built into 140-version collations; without an SC/UTF8-aware collation, `LEN`/`SUBSTRING`/`LEFT` split surrogate pairs and miscount.
- Comparing/joining columns of different collations raises "cannot resolve the collation conflict"; forcing `COLLATE` fixes it but makes the predicate non-sargable. Keep join-key collations identical.
- `char(n)` is blank-padded. `text`/`ntext`/`image` are deprecated — use the `(max)` types.

### Numbers, money & dates
- `decimal(p,s)`/`numeric` are exact — use for money. `float`/`real` are approximate IEEE — never `=`-compare. `money` is fixed 4-dp and rounds intermediate division badly (`$100/3*3` ≠ `$100`); prefer `decimal(19,4)`.
- `datetime` (1753–9999, accuracy 1/300 s) rounds stored values to .000/.003/.007 s — a silent mutation. `datetime2(n)` (default 7, 0001–9999, 6–8 bytes, 100 ns) is strictly better; make it the default. Neither stores a zone. `datetimeoffset` keeps a *fixed* offset only — no named tz, no DST — and the engine never auto-converts by session tz. Store UTC; convert with `AT TIME ZONE`.

### NULL, precedence & implicit conversion
- Three-valued logic: `col = NULL` is never true — use `IS NULL`. `SET ANSI_NULLS OFF` is deprecated. Unlike Oracle, `''` is an empty string, **not** NULL. `+` propagates NULL; `CONCAT` treats NULL as `''`. 2022 (16.x) adds null-safe `IS [NOT] DISTINCT FROM`.
- Type precedence drives silent conversion: `nvarchar` outranks `varchar`; numerics outrank strings. So `WHERE varchar_col = @nvarchar_param` converts the **column** up to nvarchar, defeating its index (scan) — a common footgun since many drivers bind strings as Unicode by default. Match parameter types to columns; don't pass dates/numbers as strings (forces per-row CONVERT).
- On overflow, 2019+ (and 2017 CU12) report the offending table/column/value (error 2628) instead of the vague 8152 truncation error.

### SET options poison the plan cache
`QUOTED_IDENTIFIER`, `ANSI_NULLS`, `ANSI_WARNINGS`, `ARITHABORT`, `CONCAT_NULL_YIELDS_NULL` are baked into each cached plan and gate the usability of indexed views, computed columns, and filtered indexes. An app whose connection defaults differ from SSMS gets a *separate* plan (the classic "fast in SSMS, slow from the app") and can error on those objects. Set them explicitly and identically in the driver/DSN.

### Version-gated T-SQL surface
- 2017 (14.x): `STRING_AGG` (+`WITHIN GROUP`), `TRIM`, `CONCAT_WS`, `TRANSLATE`, `APPROX_COUNT_DISTINCT`.
- 2022 (16.x): `GREATEST`/`LEAST`, `DATE_BUCKET`, `GENERATE_SERIES`, `STRING_SPLIT` ordinal column, `JSON_OBJECT`/`JSON_ARRAY`, bit-manipulation functions, `WINDOW` clause.
- JSON: functions (`ISJSON`, `JSON_VALUE`, `JSON_QUERY`, `JSON_MODIFY`, `OPENJSON`) exist since 2016 over `nvarchar`. A native binary `json` type (in-place `.modify()`, stored `Latin1_General_100_BIN2_UTF8`, accepts only a top-level object/array) is GA on Azure SQL DB/MI, preview on 2025 (17.x); it can't be an index key — index a computed/`OPENJSON`-derived column.
- 2025 (17.x): regex functions (`REGEXP_LIKE`/`_REPLACE`/`_SUBSTR`…) and the `vector` type.

### Sources
learn.microsoft.com/sql — t-sql/data-types: data-types-transact-sql, data-type-precedence-transact-sql, datetime2-transact-sql, json-data-type · relational-databases/collations/collation-and-unicode-support (UTF-8/_SC) · t-sql/functions: string-agg-transact-sql, logical-functions-greatest-transact-sql (2017/2022 gates)

## Execution plans and indexing <a id="execution-plans-and-indexing"></a>

Plans are gated by database **compat level** (140=2017, 150=2019, 160=2022, 170=2025), not server version — an upgrade keeps the old level until `ALTER DATABASE…SET COMPATIBILITY_LEVEL`.

**Read the actual plan** (`SET STATISTICS XML ON`), not estimated: the Estimated-vs-Actual row skew pinpoints bad estimates that cascade into wrong joins and grant spills. Add `SET STATISTICS IO,TIME ON` — heavy reads on a "seek" reveal a Key Lookup loop.

**Cardinality estimation.** New CE (2014) at compat 120+ is usually better but can regress a legacy-tuned query; pin legacy via `LEGACY_CARDINALITY_ESTIMATION=ON` without a global level drop.

**Statistics drive CE.** Auto-update fires past a mod threshold: compat ≤120 `500+0.20×n`; compat 130+ `MIN(500+0.20×n, SQRT(1000×n))` (pre-2016: trace flag 2371). Table variables get no column stats (1-row guess).

**Index structure.** The clustered index IS the table (leaf=data rows); its key is the row locator in every nonclustered (NC) index. A wide/random clustering key bloats and fragments all NC indexes — prefer narrow, unique, static, increasing, not-null keys. A NC seek for columns it lacks does a Key Lookup (clustered)/RID Lookup (heap) per row — catastrophic; fix with a covering index (key = predicate/join/sort cols, payload in `INCLUDE`, exempt from key limits). Key limits: since 2016, 32 key cols, 900 B clustered / 1700 B NC; before 2016 ALL index keys were 16 cols / 900 B. Composite order: equality cols first, then one range col (later cols stop seeking).

**Missing-index DMVs are hints, not prescriptions.** `sys.dm_db_missing_index_*` are compile-time guesses — blind to key order + INCLUDE cost, never clustered/unique/filtered/columnstore, cap 600 groups. Rank by `avg_total_user_cost × avg_user_impact × (seeks+scans)`, hand-order by selectivity; never create verbatim.

**Columnstore + batch mode.** Clustered columnstore packs a fact table into rowgroups up to 1,048,576; trickle loads (<102,400) wait in the deltastore for the tuple-mover. Batch mode (~900 rows/call) since 2019 (compat 150) extends to rowstore via `BATCH_MODE_ON_ROWSTORE` (default ON).

**IQP by version.** 2017/140: adaptive joins, interleaved execution for MSTVFs, batch-mode memory-grant feedback. 2019/150: batch mode on rowstore, table-variable deferred compilation, scalar UDF inlining. 2022/160: Parameter Sensitive Plan optimization, CE feedback, DOP feedback, optimized plan forcing.

**DON'T:** write non-sargable predicates — a function on the column or a column-side implicit conversion kills the seek. Rebuild on a live table without `ONLINE=ON` (Enterprise/Azure) — offline it takes a blocking Sch-M lock; add `WAIT_AT_LOW_PRIORITY` + `RESUMABLE=ON` (online rebuild 2017+, create 2019+). Ignore last-page contention on an increasing key (PAGELATCH_EX) — set `OPTIMIZE_FOR_SEQUENTIAL_KEY=ON` (2019+). Over-index write-heavy tables (each NC index taxes every DML). Lower global compat to fix one estimate — scope it (`OPTIMIZE FOR`, `RECOMPILE`, a legacy-CE hint, or a Query Store hint / forced plan via `sp_query_store_force_plan`, default-on since 2022).

### Sources
- learn.microsoft.com/sql/relational-databases/{performance/cardinality-estimation-sql-server, performance/intelligent-query-processing-details, sql-server-index-design-guide, indexes/columnstore-indexes-overview, statistics/statistics} · /t-sql/statements/create-index-transact-sql

## Performance <a id="performance"></a>

The high-signal entry point: fix in THIS order, and SEE each problem with the named tool. Deep detail lives in siblings — this is the checklist, not a restatement. Current **2025 (17.x)**; plan behavior is gated by DB **compat level**, not server build.

### Measure first
- **Actual plan, not estimated.** `SET STATISTICS XML ON` (or SSMS "Include Actual Execution Plan"); estimated-only = `SET SHOWPLAN_XML ON`. A large Estimated-vs-Actual row gap = a stats/CE problem, not an index one. Live Query Statistics shows row flow on an in-flight query.
- **Per-query cost:** `SET STATISTICS IO, TIME ON` — logical reads + CPU/elapsed. Heavy reads on a "seek" reveal a Key/RID Lookup loop.
- **Fleet view:** Query Store (regressions, forced plans, per-query waits since 2017) and `sys.dm_exec_query_stats` (rank by total_worker_time / logical_reads); `sys.dm_os_wait_stats` for the systemic bottleneck. DON'T tune from plans on tiny tables.

### The ordered playbook
1. **Right indexes** — covering (`INCLUDE`) to kill lookups, filtered for hot subsets, clustered columnstore + batch mode for analytic/fact scans. Design rules, key limits, missing-index DMV caveats: see lore/deep/sqlserver.md#execution-plans-and-indexing.
2. **Sargable predicates** — no function or implicit conversion on the indexed column (same file).
3. **Current statistics** — stale stats → bad estimates → wrong plan; `UPDATE STATISTICS` or auto-update after a bulk change (same file).
4. **Tame parameter sniffing** — below.
5. **Stabilize with Query Store** — force the good plan (`sp_query_store_force_plan`) or apply a Query Store hint, no app change. Default-ON for new DBs since **2022 (16.x)**; OFF on 2016–2019 — enable `ALTER DATABASE … SET QUERY_STORE = ON (OPERATION_MODE = READ_WRITE)`.
6. **Set-based + bulk** — kill row-by-row loops/cursors; bulk-load (`BULK INSERT`/`bcp`/`INSERT…SELECT`) with `TABLOCK` under SIMPLE/BULK_LOGGED for minimal logging.

### Parameter sniffing
One plan compiled for an atypical value, then reused for all.
- **2022 (16.x)/compat 160 PSP optimization** auto-builds variant plans (up to 3 skewed *equality* predicates), on by default; 2025/compat 170 adds DML + tempdb.
- Manual knobs: `OPTION (RECOMPILE)` (fresh plan per run), `OPTIMIZE FOR (@p = <typical>)`, `OPTIMIZE FOR UNKNOWN` (density average). Disable PSP per-query via `USE HINT('DISABLE_PARAMETER_SENSITIVE_PLAN')`. DON'T lower global compat to fix one query — scope it.

### TempDB contention
Allocation-page (GAM/SGAM/PFS) latch waits under concurrent temp-object churn show as `PAGELATCH_*` on pages like `2:1:1`.
- **DO** run multiple equal-sized data files: one per logical CPU up to 8, then add in multiples of 4 if contention persists; identical size + autogrow (proportional-fill). TF 1117/1118 unneeded since 2016.
- **DO** enable memory-optimized tempdb metadata (2019+) for metadata contention: `ALTER SERVER CONFIGURATION SET MEMORY_OPTIMIZED TEMPDB_METADATA = ON` (restart; bind to a Resource Governor pool). 2019 PFS + 2022 GAM/SGAM concurrency cut this natively.
- Watch `sys.dm_db_file_space_usage` / `sys.dm_db_task_space_usage`. Spills to tempdb come from bad memory grants — fix the estimate, don't grow tempdb.

### Pooling
Reuse pooled connections; open late, always close/dispose. Sizing, resiliency, encryption: see lore/deep/sqlserver.md#connection-and-pooling.

### Sources
- learn.microsoft.com/sql/relational-databases/performance/{monitoring-performance-by-using-the-query-store, parameter-sensitive-plan-optimization, execution-plans}
- learn.microsoft.com/sql/relational-databases/databases/tempdb-database

## Transactions and isolation <a id="transactions-and-isolation"></a>

Engine-level T-SQL transaction, isolation, and locking semantics — driver-agnostic (behaves the same via `Microsoft.Data.SqlClient`, `mssql-jdbc`, `msodbcsql 18`, `go-mssqldb`). Current stable **2025 (17.x)**; guidance holds for **2017/2019/2022** unless gated. Big divergence: **Azure SQL Database defaults `READ_COMMITTED_SNAPSHOT` and `ALLOW_SNAPSHOT_ISOLATION` ON**; on-prem/Managed Instance both default **OFF**. ORM-side tx wrapping lives in lore/orm.md and lore/deep/databases.md#transactions-and-isolation — this is the engine.

### Five levels, two of them row-versioning
Set per-connection with `SET TRANSACTION ISOLATION LEVEL ...` (or a table hint). Default is **READ COMMITTED**, and its meaning flips on a DB option:
- **RCSI OFF (on-prem default)** — READ COMMITTED takes real shared locks; writers block readers and vice-versa.
- **RCSI ON** — READ COMMITTED serves each *statement* a row-versioned snapshot from `tempdb`; readers never block writers. No `SET`-level change, no update conflicts. Turning it on requires the `ALTER DATABASE` connection to be the only one in the DB.
- **SNAPSHOT** (needs `ALLOW_SNAPSHOT_ISOLATION ON`) is *transaction*-level: the snapshot freezes at first data access, not per statement. A write whose row changed since then aborts with **Msg 3960 (update conflict)** — you must catch and retry the whole tx. DDL on objects it touched fails with **3961**.
- **REPEATABLE READ** holds shared locks to tx end (no non-repeatable reads, phantoms still possible). **SERIALIZABLE** adds **key-range locks** (`RangeS-S`, `RangeI-N`) over the predicate to block phantom inserts — needs an index on the range column or it locks far more; expect *n+1* range locks.

Gotcha: you **cannot switch *into* SNAPSHOT mid-transaction** — it aborts the tx; you can switch out of it. `SET TRANSACTION ISOLATION LEVEL` inside a proc/trigger reverts to the caller's level on return. RCSI/SNAPSHOT both feed a `tempdb` version store that grows with the *oldest* open tx — a forgotten snapshot tx bloats tempdb.

### Locking, escalation, and hints
Update (`U`) locks exist so a read-then-write doesn't self-deadlock via two `S→X` upgrades. Escalation goes **row/page → table directly at ~5000 locks per statement** (retries every +1250); `ROWLOCK`/`PAGLOCK` hints tune *acquisition* but do **not** prevent escalation — **batch big DML** (`DELETE TOP (n) ... ` in a loop) instead. Useful hints: `WITH (UPDLOCK, HOLDLOCK)` on the `SELECT` of an upsert to serialize it correctly; `READPAST` to skip locked rows for a queue (`SELECT TOP(1) ... WITH (UPDLOCK, READPAST)`); `READCOMMITTEDLOCK` to force locking reads even when RCSI is ON. Avoid `NOLOCK`/READ UNCOMMITTED — it yields dirty, missing, and duplicated rows, not speed.

### Deadlocks and lock timeout
The monitor picks a victim and rolls its tx back with **Msg 1205**; bias the victim with `SET DEADLOCK_PRIORITY LOW`. Always **retry the entire transaction** (its work is gone) with backoff — never just the failed statement. Read the deadlock graph via the `system_health` Extended Events session. `SET LOCK_TIMEOUT` is **-1 (wait forever) by default**; a timeout raises **Msg 1222** but — like a mid-tx runtime error under default `XACT_ABORT OFF` — cancels only the statement, leaving the tx open. Cap it before contentious `ALTER`/index ops so they fail fast.

### Nesting, savepoints, and error handling
Nested transactions are largely **cosmetic**: `BEGIN TRAN` just increments `@@TRANCOUNT`; an inner `COMMIT` only decrements it (nothing is durable until the outermost commit drops it to 0); committing at `@@TRANCOUNT = 0` errors. Crucially, a plain **`ROLLBACK TRANSACTION` rolls back *everything* to `@@TRANCOUNT = 0`**, ignoring inner scopes — only `ROLLBACK TRANSACTION <savepoint>` (paired with `SAVE TRANSACTION`) is partial, and savepoints are illegal in distributed transactions.
- **`SET XACT_ABORT ON`** for any explicit-tx write proc: default OFF lets a runtime error (FK violation, etc.) roll back only the statement and blunder on with the tx still open; ON aborts and rolls back the whole tx. It's **required** for DML over linked servers / most OLE DB providers, and is ON by default inside triggers.
- In `TRY/CATCH`, check **`XACT_STATE()`**: `-1` = a *doomed* (uncommittable) tx — you may only `ROLLBACK`; `1` = committable; `0` = none. Prefer **`THROW`** (honors `XACT_ABORT`) over `RAISERROR` (doesn't).

Batch-scoped transactions under MARS auto-roll-back if a batch ends with one open. Distributed tx (`BEGIN DISTRIBUTED TRANSACTION`) commit via MS DTC two-phase. **2019+**: Accelerated Database Recovery (ADR) makes rollback of huge/long tx near-instant and bounds log growth; **2025** optimized locking (needs ADR + ideally RCSI) holds one transaction-lifetime `XACT`/TID lock and frees row locks early, sharply cutting escalation and blocking.

### Sources
- learn.microsoft.com/en-us/sql/t-sql/statements/set-transaction-isolation-level-transact-sql (levels, RCSI vs SNAPSHOT, no-switch-into-SNAPSHOT, proc scoping)
- learn.microsoft.com/en-us/sql/relational-databases/sql-server-transaction-locking-and-row-versioning-guide (lock modes, escalation ~5000, key-range, 3960/3961/1204, optimized locking)
- learn.microsoft.com/en-us/sql/t-sql/language-elements/commit-transaction-transact-sql + .../set-xact-abort-transact-sql + .../statements/set-lock-timeout-transact-sql (@@TRANCOUNT nesting, XACT_ABORT default OFF/trigger ON, LOCK_TIMEOUT -1 / Msg 1222)
