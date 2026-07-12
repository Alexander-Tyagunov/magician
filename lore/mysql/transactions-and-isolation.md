# MySQL — Transactions and Isolation

Version: 9.7 newest LTS (2026-04), 8.4 LTS supported, 8.0 EOL 2026-04; InnoDB isolation/locking unchanged 8.0→8.4→9.7. InnoDB only — MyISAM: no transactions, no rollback. Default REPEATABLE READ (not READ COMMITTED). `FOR SHARE`/`SKIP LOCKED`/`NOWAIT`/`OF` added 8.0.1. `autocommit=1` default. Can't change level mid-tx.

## Four levels (InnoDB)
- REPEATABLE READ (default): plain `SELECT` = snapshot from tx's first read. Locking reads + `UPDATE`/`DELETE` take next-key locks (record+gap) over the scan range → phantoms blocked; unique hit on one existing row = record lock only, no gap.
- READ COMMITTED: re-snapshots per statement. Gap locking off (except FK/dup-key) → phantoms possible; `UPDATE` uses semi-consistent read. Needs row binlog: `MIXED` auto-switches to ROW, but `STATEMENT` is NOT coerced — transactional DML errors out. Same for READ UNCOMMITTED.
- READ UNCOMMITTED: nonlocking — dirty reads.
- SERIALIZABLE: RR + `autocommit=0` promotes plain `SELECT` to `FOR SHARE`.

## MVCC & snapshots
Reads rebuild old rows from the undo log. Snapshot governs `SELECT` only — an `UPDATE`/`DELETE` in the same tx hits latest committed data, touching rows a prior SELECT couldn't see. A long/forgotten tx pins an old read view → purge can't reclaim undo → history-list bloat, slow reads; keep tx short. `START TRANSACTION WITH CONSISTENT SNAPSHOT` snapshots up front. Copy-rebuilding `ALTER`/`DROP` invalidates it → `ER_TABLE_DEF_CHANGED`, retry.

## Locks
On index records (no-PK table → hidden clustered index). Next-key = record + gap lock on the gap before it. Gap locks only block inserts (purely inhibitive). `INSERT` sets an insert-intention gap lock: inserts to different spots of a gap don't block, but wait on a covering next-key lock. Duplicate-key `INSERT` = shared lock on the row → concurrent same-key inserts deadlock. `INSERT … ON DUPLICATE KEY UPDATE`/`REPLACE` = exclusive next-key locks. FK checks = shared record locks on parent. A locking read/UPDATE without a usable index locks every scanned row (≈ whole table) — always index the `WHERE`.

## Deadlock vs lock-wait (rollback scope differs)
- Deadlock (1213, SQLSTATE 40001): `innodb_deadlock_detect` ON; rolls back cheapest victim + whole tx — retry it. RR gap locks make range-write/INSERT deadlocks likelier than RC.
- Lock-wait timeout (1205): `innodb_lock_wait_timeout` 50s; rolls back ONLY the failing statement, not the tx (keeps other locks). Set `innodb_rollback_on_timeout` (OFF) for full-tx rollback — else code assuming 1205 == full rollback breaks.
- Diagnose: `SHOW ENGINE INNODB STATUS`, `performance_schema.data_locks`/`data_lock_waits`, `INNODB_TRX`.

## DDL, MDL, XA
DDL and `LOCK TABLES` force an implicit COMMIT (not transactional, no rollback). Every statement (even `SELECT`) takes an MDL to tx end: one open tx blocks an `ALTER`, whose exclusive wait blocks all queries (metadata-lock pileup). `lock_wait_timeout` (MDL) default 31536000s/1yr — set low (5s) before DDL so it fails fast. `XA PREPARE`d tx hold locks across restart until commit/rollback — orphans block DDL indefinitely.

## MariaDB
Separate engine: same four levels + default RR, but `NOWAIT`/`SKIP LOCKED` versions, `FOR SHARE` spelling, replication internals differ — verify vs MariaDB KB.

## Sources
- dev.mysql.com/doc/refman/8.4/en/: innodb-transaction-isolation-levels.html, innodb-locking.html, metadata-locking.html, binary-log-setting.html
