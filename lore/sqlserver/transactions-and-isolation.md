# Microsoft SQL Server — Transactions and isolation

Engine-level T-SQL transaction, isolation, and locking semantics — driver-agnostic (behaves the same via `Microsoft.Data.SqlClient`, `mssql-jdbc`, `msodbcsql 18`, `go-mssqldb`). Current stable **2025 (17.x)**; guidance holds for **2017/2019/2022** unless gated. Big divergence: **Azure SQL Database defaults `READ_COMMITTED_SNAPSHOT` and `ALLOW_SNAPSHOT_ISOLATION` ON**; on-prem/Managed Instance both default **OFF**. ORM-side tx wrapping lives in lore/orm.md and lore/databases/transactions-and-isolation.md — this is the engine.

## Five levels, two of them row-versioning
Set per-connection with `SET TRANSACTION ISOLATION LEVEL ...` (or a table hint). Default is **READ COMMITTED**, and its meaning flips on a DB option:
- **RCSI OFF (on-prem default)** — READ COMMITTED takes real shared locks; writers block readers and vice-versa.
- **RCSI ON** — READ COMMITTED serves each *statement* a row-versioned snapshot from `tempdb`; readers never block writers. No `SET`-level change, no update conflicts. Turning it on requires the `ALTER DATABASE` connection to be the only one in the DB.
- **SNAPSHOT** (needs `ALLOW_SNAPSHOT_ISOLATION ON`) is *transaction*-level: the snapshot freezes at first data access, not per statement. A write whose row changed since then aborts with **Msg 3960 (update conflict)** — you must catch and retry the whole tx. DDL on objects it touched fails with **3961**.
- **REPEATABLE READ** holds shared locks to tx end (no non-repeatable reads, phantoms still possible). **SERIALIZABLE** adds **key-range locks** (`RangeS-S`, `RangeI-N`) over the predicate to block phantom inserts — needs an index on the range column or it locks far more; expect *n+1* range locks.

Gotcha: you **cannot switch *into* SNAPSHOT mid-transaction** — it aborts the tx; you can switch out of it. `SET TRANSACTION ISOLATION LEVEL` inside a proc/trigger reverts to the caller's level on return. RCSI/SNAPSHOT both feed a `tempdb` version store that grows with the *oldest* open tx — a forgotten snapshot tx bloats tempdb.

## Locking, escalation, and hints
Update (`U`) locks exist so a read-then-write doesn't self-deadlock via two `S→X` upgrades. Escalation goes **row/page → table directly at ~5000 locks per statement** (retries every +1250); `ROWLOCK`/`PAGLOCK` hints tune *acquisition* but do **not** prevent escalation — **batch big DML** (`DELETE TOP (n) ... ` in a loop) instead. Useful hints: `WITH (UPDLOCK, HOLDLOCK)` on the `SELECT` of an upsert to serialize it correctly; `READPAST` to skip locked rows for a queue (`SELECT TOP(1) ... WITH (UPDLOCK, READPAST)`); `READCOMMITTEDLOCK` to force locking reads even when RCSI is ON. Avoid `NOLOCK`/READ UNCOMMITTED — it yields dirty, missing, and duplicated rows, not speed.

## Deadlocks and lock timeout
The monitor picks a victim and rolls its tx back with **Msg 1205**; bias the victim with `SET DEADLOCK_PRIORITY LOW`. Always **retry the entire transaction** (its work is gone) with backoff — never just the failed statement. Read the deadlock graph via the `system_health` Extended Events session. `SET LOCK_TIMEOUT` is **-1 (wait forever) by default**; a timeout raises **Msg 1222** but — like a mid-tx runtime error under default `XACT_ABORT OFF` — cancels only the statement, leaving the tx open. Cap it before contentious `ALTER`/index ops so they fail fast.

## Nesting, savepoints, and error handling
Nested transactions are largely **cosmetic**: `BEGIN TRAN` just increments `@@TRANCOUNT`; an inner `COMMIT` only decrements it (nothing is durable until the outermost commit drops it to 0); committing at `@@TRANCOUNT = 0` errors. Crucially, a plain **`ROLLBACK TRANSACTION` rolls back *everything* to `@@TRANCOUNT = 0`**, ignoring inner scopes — only `ROLLBACK TRANSACTION <savepoint>` (paired with `SAVE TRANSACTION`) is partial, and savepoints are illegal in distributed transactions.
- **`SET XACT_ABORT ON`** for any explicit-tx write proc: default OFF lets a runtime error (FK violation, etc.) roll back only the statement and blunder on with the tx still open; ON aborts and rolls back the whole tx. It's **required** for DML over linked servers / most OLE DB providers, and is ON by default inside triggers.
- In `TRY/CATCH`, check **`XACT_STATE()`**: `-1` = a *doomed* (uncommittable) tx — you may only `ROLLBACK`; `1` = committable; `0` = none. Prefer **`THROW`** (honors `XACT_ABORT`) over `RAISERROR` (doesn't).

Batch-scoped transactions under MARS auto-roll-back if a batch ends with one open. Distributed tx (`BEGIN DISTRIBUTED TRANSACTION`) commit via MS DTC two-phase. **2019+**: Accelerated Database Recovery (ADR) makes rollback of huge/long tx near-instant and bounds log growth; **2025** optimized locking (needs ADR + ideally RCSI) holds one transaction-lifetime `XACT`/TID lock and frees row locks early, sharply cutting escalation and blocking.

## Sources
- learn.microsoft.com/en-us/sql/t-sql/statements/set-transaction-isolation-level-transact-sql (levels, RCSI vs SNAPSHOT, no-switch-into-SNAPSHOT, proc scoping)
- learn.microsoft.com/en-us/sql/relational-databases/sql-server-transaction-locking-and-row-versioning-guide (lock modes, escalation ~5000, key-range, 3960/3961/1204, optimized locking)
- learn.microsoft.com/en-us/sql/t-sql/language-elements/commit-transaction-transact-sql + .../set-xact-abort-transact-sql + .../statements/set-lock-timeout-transact-sql (@@TRANCOUNT nesting, XACT_ABORT default OFF/trigger ON, LOCK_TIMEOUT -1 / Msg 1222)
