# PostgreSQL — Transactions and Locking

Version: 18 stable; majors 14–18. SSI since 9.1; `SKIP LOCKED` since 9.5 (NOWAIT far older); `idle_in_transaction_session_timeout` since 9.6; `MERGE` since 15; `transaction_timeout` since **17**. 4 ANSI levels, **3** real (Read Uncommitted = Read Committed).

## Isolation (MVCC snapshots)
- **Read Committed** (default): fresh snapshot per *statement*; never raises `40001`, waits on row locks.
- **Repeatable Read** = snapshot isolation: snapshot frozen at first statement; no phantoms. Committed concurrent UPDATE/DELETE of a row you write → `40001`.
- **Serializable** (SSI): RR + predicate locks on read/write deps → also `40001`; catches write-skew, no extra blocking.
- **Retry mandatory** on `40001`/deadlock `40P01`: replay the *whole* tx, not the failing statement (snapshot stale; deadlock victim unpredictable, not always the "later" tx). Under Serializable, reads trustworthy only after commit.
- **RC lost-update trap:** `UPDATE ... WHERE` re-checks its predicate on the *new* row version, so a matching row can be silently skipped. Guard: `SELECT ... FOR UPDATE`, SQL arithmetic, `INSERT ... ON CONFLICT`, or RR/Serializable + retry.

## Locking modes
**Table** (eight; only conflicts matter, "ROW" names are still table locks): `ACCESS SHARE` (SELECT) vs only `ACCESS EXCLUSIVE`; `ROW EXCLUSIVE` (INSERT/UPDATE/DELETE/MERGE) vs SHARE+; `SHARE UPDATE EXCLUSIVE` (VACUUM, `CREATE INDEX CONCURRENTLY`) self-conflicts; `ACCESS EXCLUSIVE` (DROP/TRUNCATE/most `ALTER`, bare `LOCK TABLE`) blocks all incl. SELECT. Locks live to tx end.
**Row** (weak→strong): `FOR KEY SHARE` < `FOR SHARE` < `FOR NO KEY UPDATE` < `FOR UPDATE`. FK parent takes `FOR KEY SHARE`; non-key `UPDATE` takes `FOR NO KEY UPDATE`, so they don't block each other. `NOWAIT` (error) or `SKIP LOCKED` (skip); `FOR UPDATE SKIP LOCKED` = work-queue dequeue.

## Deadlocks, timeouts, advisory, 2PC
- Deadlocks after `deadlock_timeout` (**1s**); one tx aborts (`40P01`). Defenses: consistent lock order, strongest mode first, retry. Without a cycle a waiter blocks *forever* — never hold a tx across think-time.
- Guardrails (default 0/off): `lock_timeout` (set before `ALTER`/`CREATE INDEX`), `statement_timeout`, `idle_in_transaction_session_timeout`, `transaction_timeout` (17+). Set narrowly.
- **Advisory locks** (`pg_advisory_lock`/`_xact_lock`, `_try_` variants): advisory, not data-enforced. Session-level survive rollback + need explicit unlock (ref-counted); prefer `_xact_` (auto-release). Never `pg_advisory_lock(id) ... LIMIT n` — LIMIT may run after the lock → dangling locks.
- **2PC**: `PREPARE TRANSACTION` needs `max_prepared_transactions > 0` (default **0**); orphaned prepared xacts hold locks + block vacuum/wraparound — monitor `pg_prepared_xacts`.

## DON'T / driver gotchas
- Never leave sessions `idle in transaction` — they pin `xmin`, block VACUUM, bloat tables; the pool must COMMIT/ROLLBACK on every path.
- `nextval` never rolls back — `serial`/identity gaps are normal.
- Don't `SAVEPOINT` every statement: each is a subtransaction; past ~64 cached subxids per backend, all sessions pay `pg_subtrans` SLRU lookups (cluster-wide).
- Heavy shared row locks / FK churn create multixacts — watch multixact wraparound on write-heavy tables.
- DDL is transactional but takes strong table locks — keep short, pair `lock_timeout`.

## Sources
- postgresql.org/docs/18: transaction-iso, explicit-locking, runtime-config-{client,locks}.
