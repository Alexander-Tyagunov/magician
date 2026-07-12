# Couchbase — Durability & Consistency

Version: Server 8.0 GA (durable writes since 6.5; SQL++ `BEGIN TRANSACTION` since 7.0). Capella applies the same levels. With the **default 1 replica** majority = 2 nodes, so a single-node dev cluster can't meet it → `DurabilityImpossibleException`; **0 replicas** needs only 1 node (majority met).

## The write path: vBuckets, active/replica, CAS
Each key hashes (CRC32) to a vBucket (1024 on Couchstore; 128/1024 on Magma). Each vBucket has one **active** plus up to 3 **replicas**; writes hit the active, then stream to replicas via DCP. KV `get` reads the active, so a plain get is always RYOW — the eventual-consistency gap is the **index/query** side, not KV.
- Each doc carries a **CAS** that changes per mutation. Pass it back on `replace`/subdoc for optimistic locking; a stale CAS raises `CasMismatchException` — retry the get-modify-write with bounded backoff. Use `getAndLock` for short pessimistic locks on hot docs.

## Durability levels (per-write, tunable)
Default write is **async**: acked once in the active's memory — lost if that node dies before replication. Opt into synchronous **durable writes**:
- `MAJORITY` — a majority of Data nodes hold it in memory (only level for Ephemeral buckets).
- `MAJORITY_AND_PERSIST_TO_ACTIVE` — majority in memory + fsync on the active.
- `PERSIST_TO_MAJORITY` — fsync on a majority; strongest, slowest.

Majority math: **2 replicas→2 nodes; 3 replicas can't use durability** (`EDurabilityImpossible`). Default SDK timeout 10 s; a second durable write to the same in-flight key returns `SYNC_WRITE_IN_PROGRESS`. Use legacy `PersistTo`/`ReplicateTo` (observe API) only pre-6.5.

DON'T assume writes survive node loss without a level. DON'T set `durabilityImpossibleFallback=true` — it silently degrades durable writes to async. On auto-failover, majority loss before propagation can lose a "successful" durable write; cap `maxCount` below majority or enable `failoverPreserveDurabilityMajority` (EE).

## Query/index consistency (`scan_consistency`)
GSI maintenance is **async** to the write, so SQL++ over an index is eventually consistent. Choose per query:
- `NOT_BOUNDED` — default; whatever is indexed now. Lowest latency, no RYOW.
- `REQUEST_PLUS` — index caught up to all mutations first; full RYOW, highest latency.
- `AT_PLUS` via `consistentWith(MutationState)` — waits only on *your* mutation tokens; RYOW cheaper than `REQUEST_PLUS`.

DON'T default read-after-write flows to `NOT_BOUNDED`; use `AT_PLUS` with the write's mutation token, not the blunt `REQUEST_PLUS`.

## Multi-document ACID transactions
Distributed transactions span docs across collections/scopes/buckets. Isolation is **Read Committed** with a Monotonic Atomic View — a commit is never partially observed; lost updates are blocked via CAS. Statement-level atomicity: a failed SQL++ statement rolls back alone, the txn continues. Queries in a txn default to `request_plus` to see its own writes. Keep docs <10 MB, txns short (default expiry ~15 s), require NTP-synced clocks, and never mix non-transactional writes into docs a txn is mutating.

## Sources
- Server 8.0 — Durability: https://docs.couchbase.com/server/current/learn/data/durability.html
- Server 8.0 — Distributed ACID Transactions: https://docs.couchbase.com/server/current/learn/data/transactions.html
- Java SDK — KV & N1QL scan consistency: https://docs.couchbase.com/java-sdk/current/howtos/kv-operations.html
