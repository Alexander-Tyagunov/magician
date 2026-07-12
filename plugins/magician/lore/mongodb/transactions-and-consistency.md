# MongoDB — Transactions and Consistency

Version: 8.0 current. Multi-doc ACID txns since **4.0** (replica set) / **4.2** (sharded); standalone `mongod` can't (no oplog). Default reads are **read-uncommitted**; single-**doc** writes are always atomic.

## Model to AVOID needing transactions
- **A single-doc write is atomic** — no reader sees a half-updated doc; embed related data so one `updateOne`/`$inc`/`$push` mutates the whole invariant.
- A distributed txn costs far more than a single-doc write; use one only for true cross-doc invariants (transfer, double-entry).
- `updateMany`/multi-doc ops are **atomic per document, not as a whole** — concurrent writers interleave, so a reader may see some docs updated, not others.

## Read concern
- `local` (default): freshest on the node, **can roll back** on failover. `available` (sharded): low-latency, may return orphans.
- `majority`: acknowledged by a majority — **durable, never rolled back**.
- `linearizable`: reflects all majority writes before it began (single doc, primary, pair `w:"majority"`).
- `snapshot`: majority-committed point-in-time; in a sharded txn **synchronized across shards**.

## Write concern
- Default since 5.0 is `w:"majority"`; `j:true` forces a journal ack. `w:1` acks the primary only — **a failover can roll it back**. `w:0` is unacknowledged (no operationTime, breaks causal ordering).

## Transaction semantics & scope
- Use the **callback API** (`session.withTransaction`) — retries `TransientTransactionError`/`UnknownTransactionCommitResult`. Each op must carry the session.
- Txn-level read/write concern wins; **per-op write concern in a txn is an error**. Commit with `w:"majority"` or the txn can roll back. Txn reads use read preference **primary**.
- Snapshot isolation covers txn reads; changes invisible outside until commit. One open txn per session; ending it aborts. Can't write capped/`config`/`admin`/`local`/`system.*`; collection/index creation needs read concern `local`.

## Causal consistency (sessions)
A **causally consistent session** gives read-your-writes, monotonic reads/writes, writes-follow-reads — **required when reading a secondary** after a write. Needs `majority` read **and** write concern, one thread per session. Advance cluster time to chain sessions.

## Production limits & write conflicts
- `transactionLifetimeLimitSeconds` **default 60s**; a sweeper aborts older txns. Keep short; split large work.
- Each **oplog entry** obeys the 16MB BSON cap; a txn spans many (no single 16MB total since 4.2), but a huge one strains WiredTiger cache → **write conflict** abort, or `TransactionTooLargeForCache` if it never fits.
- **First-writer-wins:** an outside write that modifies a doc **before** the txn does aborts the txn (write conflict); if the txn holds the lock first, an outside write waits until the txn ends. `maxTransactionLockRequestTimeoutMillis` (**5ms** default) = how long the *txn* waits to acquire a held lock before aborting. Chunk migration/DDL (`createIndex`, `renameCollection`) block/abort in-flight txns.

## DON'T
- Don't use txns as a schema crutch, run them long, or touch thousands of docs; don't assume `updateMany` is all-or-nothing.
- Don't set per-op write concern, trust `w:1`/`local` across a failover, or read a txn from a secondary.

## Sources
mongodb.com/docs/manual/core/{transactions,transactions-production-consideration,read-isolation-consistency-recency}/, /reference/{read-concern,write-concern}/
