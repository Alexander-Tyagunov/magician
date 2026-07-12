# Oracle Database — Transactions and Locking

Version: 26ai is the current long-term release (GA 2026), successor to 23ai (2024); 19c is still the most widely deployed LTS (21c was an Innovation release). Semantics below hold 19c→26ai. Version gates: `SKIP LOCKED` (since 11g), **Lock-Free Reservations** / `RESERVABLE` columns (**23ai**), transaction **priority** + auto-abort of low-priority blockers (23ai→26ai). Oracle exposes only **3** isolation modes — there is no READ UNCOMMITTED and no REPEATABLE READ level.

## Isolation: three modes, MVCC via undo + SCN
- **Read Committed** (default): every *query* sees data committed before that query (not the transaction) began — so two queries in one tx can differ; nonrepeatable reads and phantoms are possible. Dirty reads are **never** possible at any level.
- **Serializable**: the whole tx sees a snapshot as of when the *transaction* began, plus its own writes — no dirty/nonrepeatable/phantom reads. A write to a row another tx committed after yours began raises **ORA-08177 `can't serialize access`** — you must retry the whole tx.
- **Read Only**: like Serializable but DML is disallowed (except `SYS`); great for consistent multi-query reports, and immune to ORA-08177.

Set with `SET TRANSACTION ISOLATION LEVEL {READ COMMITTED|SERIALIZABLE}` or `ALTER SESSION SET ISOLATION_LEVEL=…` **before the first statement**. Multiversioning is powered by **undo segments** + **SCN**: readers get consistent-read (CR) block clones rebuilt from undo, so **readers never block writers and writers never block readers** (the only exception is a pending distributed transaction). A writer only blocks a *concurrent writer of the same row*.

## Read Committed lost-update trap
Under Read Committed a blocked `UPDATE … WHERE` re-reads the row after the other writer commits, so app-side read-then-write can silently lose updates. Fix: do arithmetic in SQL (`SET bal = bal - :n`), take `SELECT … FOR UPDATE` first, use `MERGE`, or (for hot counters) a `RESERVABLE` column.

## Row (TX) vs table (TM) locks — Oracle never escalates
- **Row locks (TX)** are always **exclusive**, taken per row by `INSERT/UPDATE/DELETE/MERGE/SELECT … FOR UPDATE`, and stored **in the data-block header** — there is no central lock manager, so locking millions of rows costs no extra memory and Oracle **never escalates** a row lock to block/table level (escalation would only breed deadlocks).
- **Table locks (TM)** guard against conflicting DDL. DML takes **Row Exclusive (RX/SX)**; `SELECT … FOR UPDATE` takes an exclusive row lock plus a **Row Share (RS)** table lock. `LOCK TABLE … IN {ROW SHARE|ROW EXCLUSIVE|SHARE|SHARE ROW EXCLUSIVE|EXCLUSIVE} MODE` requests stronger modes explicitly. Oracle does *convert* modes (RS→RX) but never escalates.
- **DDL** takes exclusive/share DDL locks (plus breakable parse locks) and does an **automatic COMMIT before and after** — DDL silently ends your transaction.

## FOR UPDATE: default waits forever
`SELECT … FOR UPDATE` **blocks indefinitely** on a contended row by default. Control it:
- `NOWAIT` — fail immediately with **ORA-00054 `resource busy…`** if any target row is locked.
- `WAIT n` — wait up to *n* seconds, then ORA-00054.
- `SKIP LOCKED` — return only currently-unlocked rows (the idiomatic work-queue dequeue; combine with `FETCH FIRST n ROWS ONLY`).
- `FOR UPDATE OF col` narrows which table's rows are locked in a join. `FOR UPDATE` can't be combined with `DISTINCT`, `GROUP BY`, aggregates, or set operators.

For DDL, set `ALTER SESSION SET DDL_LOCK_TIMEOUT=n` so `ALTER TABLE` waits for its TM lock instead of failing with ORA-00054.

## Deadlocks & retry
Oracle auto-detects deadlocks and raises **ORA-00060**, rolling back **only the one statement** that closed the cycle (not the whole tx) in the session that detected it — you must still decide whether to roll back further and retry. Deadlocks are rare here (row-level locking, no read locks, no escalation) and usually appear only when apps override default locking or take rows in inconsistent order. Defenses: lock rows/tables in a consistent app-wide order, keep txns short, prefer one set-based `UPDATE` over row-at-a-time loops. **Retry logic is mandatory** for ORA-08177 (Serializable) and appropriate for ORA-00060 — replay the whole transaction with backoff, idempotently.

## Lock-Free Reservations & priority (23ai+)
A **`RESERVABLE`** numeric column lets many txns concurrently add/subtract (e.g. reserve inventory or account balance) **without holding the row lock until commit**: each change is journaled as a reservation and *verified against the column's check constraint at commit*, failing only if the aggregate would violate it. This removes the hot-row bottleneck that `SELECT … FOR UPDATE` on a single counter creates. Newer releases also add transaction **priority**, letting a low-priority tx that blocks a high-priority one be auto-aborted.

## DON'T / driver gotchas
- DON'T leave a driver in **autocommit** mode for multi-statement work: each DML commits instantly, breaking atomicity and releasing `FOR UPDATE` locks at once. Oracle itself does **not** autocommit (only DDL does).
- DON'T run long queries against tables under heavy DML with tight undo — CR reconstruction can hit **ORA-01555 `snapshot too old`**; size `UNDO_RETENTION`/retention guarantee, and never fetch across commits in the same cursor.
- DON'T assume sequences roll back — `NEXTVAL` is non-transactional; `CACHE`/`NOORDER` gaps after rollback/RAC are normal, IDs aren't gapless.
- DON'T treat `PRAGMA AUTONOMOUS_TRANSACTION` casually — it commits independently and can **deadlock against its own parent** on the same row.
- DON'T hold a tx open across user think-time or network calls; watch for orphaned **in-doubt distributed transactions** (2PC) — they hold locks until resolved.

## Sources
- docs.oracle.com/en/database/oracle/oracle-database/23/cncpt/data-concurrency-and-consistency.html (isolation, undo/SCN read consistency, TX/TM locks, no escalation, ORA-00060/08177, DDL locks)
- docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/SELECT.html (for_update_clause, wait_clause: NOWAIT/WAIT/SKIP LOCKED)
- docs.oracle.com/en/database/oracle/oracle-database/26/nfcoa/intro_feature_highlights.html (Lock-Free Reservations, priority transactions; 26ai current release)
