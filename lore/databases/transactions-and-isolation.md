# Databases — Transactions & Isolation

Engine-side transaction semantics: how each SQL server actually implements a level. For the driver API (setAutoCommit, savepoints, pooling) see lore/jdbc/transactions.md; for ORM unit-of-work see lore/orm.md.

Reference (mid-2026): PostgreSQL 18 (14–18 supported), MySQL 8.4 LTS (+9.x Innovation), SQL Server 2022/2025, Oracle 23ai. Semantics stable across those minors; version gates noted inline.

## The standard's trap

ANSI names three read anomalies (dirty read, non-repeatable read, phantom); engines also expose a **serialization anomaly** (write skew): each txn reads consistently, yet the committed set matches no serial order. The standard only says which anomalies *must not* occur — an engine may prevent more. A level *name* does not pin behavior; verify per engine.

## Defaults & implementation differ per engine

| Engine | Default | REPEATABLE READ | Phantoms at RR? |
|---|---|---|---|
| PostgreSQL | READ COMMITTED | true snapshot (MVCC) | **No** |
| MySQL/InnoDB | REPEATABLE READ | snapshot for plain SELECT; **next-key/gap locks** for locking reads | No |
| SQL Server | READ COMMITTED (locking) | shared locks held to commit | **Yes** |
| Oracle | READ COMMITTED | not offered (use SERIALIZABLE) | n/a |

- **PostgreSQL** implements only 3 levels: `READ UNCOMMITTED` acts as READ COMMITTED (no dirty reads, ever). RR = snapshot as of the first statement; SERIALIZABLE adds SSI monitoring (since 9.1 — before that "serializable" meant RR).
- **InnoDB** RR fixes the snapshot at the first consistent read; locking reads (`FOR UPDATE/SHARE`, `UPDATE`, `DELETE`) take gap/next-key locks to stop phantoms. READ COMMITTED disables gap locking (phantoms possible) and re-snapshots each statement. SERIALIZABLE upgrades plain `SELECT`→`FOR SHARE` when autocommit is off.
- **SQL Server** RR/SERIALIZABLE are *lock*-based (readers block writers). `SNAPSHOT` and `READ_COMMITTED_SNAPSHOT` (RCSI) use a tempdb version store, but must be enabled via `ALTER DATABASE SET ALLOW_SNAPSHOT_ISOLATION ON` / `SET READ_COMMITTED_SNAPSHOT ON` (RCSI defaults ON on Azure SQL). You cannot switch *into* SNAPSHOT mid-txn — it aborts.
- **Oracle** offers only READ COMMITTED + SERIALIZABLE (+ READ ONLY); MVCC via undo/SCN, so writers never block readers or vice versa (`SELECT … FOR UPDATE` is the exception).

Set with `SET TRANSACTION ISOLATION LEVEL …` before the first statement; PG/MySQL also `SET SESSION`/server default.

## Snapshot isolation ≠ SERIALIZABLE

Snapshot isolation (PG RR, SQL Server SNAPSHOT, Oracle's read model) blocks dirty/non-repeatable/phantom reads but **allows write skew**: two txns read an overlapping set, update disjoint rows, both commit, invariant broken. Only true SERIALIZABLE catches it — PG via SSI (non-blocking SIRead predicate locks), SQL Server via range locks. Cross-row invariants ("≥1 on call") need SERIALIZABLE or an explicit lock, not snapshot.

## Retry is mandatory at RR/SERIALIZABLE

These levels abort conflicting txns instead of blocking — the app MUST catch and retry the whole transaction idempotently with backoff, not just re-run the failed statement:

- PostgreSQL: **SQLSTATE 40001** `could not serialize access…`; `40P01` deadlock.
- MySQL/InnoDB: **1213** deadlock (→40001); **1205** lock-wait timeout (`innodb_lock_wait_timeout`, default 50s).
- SQL Server: **3960** snapshot update conflict; **1205** deadlock victim.
- Oracle: **ORA-08177** can't serialize; **ORA-00060** deadlock.

Under snapshot RR only *writing* txns hit these; mark read-only txns `READ ONLY` (PG SSI skips them; `DEFERRABLE` waits for a safe snapshot).

## Deadlocks & lock ordering

Any 2PL engine deadlocks when txns take rows in different orders; the engine kills a victim. Acquire rows/tables in a consistent order app-wide, keep txns short, prefer one `UPDATE … WHERE` over read-then-write. InnoDB RR is deadlock-prone via gap locks on range updates and `INSERT … ON DUPLICATE KEY`; READ COMMITTED reduces this.

## Gotchas that bite through any driver

- **Keep txns short.** Open locks/old snapshots block VACUUM/undo cleanup → bloat. No network I/O or user think-time inside a txn; watch PG `idle_in_transaction_session_timeout`.
- **Sequences/identity don't roll back** — expect ID gaps after aborts; never assume gapless IDs.
- **Isolation is per-txn and reverts** after commit; setting it does not begin a txn.
- **`READ UNCOMMITTED` is not portable**: real dirty read in MySQL/SQL Server, an alias for READ COMMITTED in PG, absent in Oracle.
- **SERIALIZABLE costs**: PG predicate-lock memory (`max_pred_locks_per_transaction`; seq scans escalate to relation locks), SQL Server range-lock contention. Reserve for invariant-critical txns.

## Sources
- PostgreSQL 18 — Transaction Isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- MySQL 8.4 — InnoDB Transaction Isolation Levels: https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html
- SQL Server — SET TRANSACTION ISOLATION LEVEL: https://learn.microsoft.com/en-us/sql/t-sql/statements/set-transaction-isolation-level-transact-sql
- Oracle 23ai — Data Concurrency and Consistency: https://docs.oracle.com/en/database/oracle/oracle-database/23/cncpt/data-concurrency-and-consistency.html
