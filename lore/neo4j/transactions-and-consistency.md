# Neo4j — Transactions & Consistency

Version-adaptive: calendar versioning (2026.xx current; 5.26 LTS; 4.4 legacy), Cypher 25. Complements lore/databases/transactions-and-isolation.md.

## Isolation & anomalies
- Default is **read-committed** — reads never block concurrent writes; serializable only via **explicit locks**.
- Expect **lost updates**, **non-repeatable reads**, and **missing/double reads** during index scans.
- Cypher auto-locks ONLY when a write directly depends on the read value: `SET n.c = n.c + 1` locks; read-then-write across statements does not — force a lock (dummy write) or serialize, never treat it as atomic.

## Locks & deadlocks
- Write locks hit node/property create-update-delete and relationship create/delete (both endpoints + the rel), held until commit/rollback.
- Deadlocks surface as `Neo.TransientError.Transaction.DeadlockDetected` (GQLSTATUS `50N05`, 5.25+) — **transient, retry the whole tx**, don't resume.
- DON'T let concurrent writers touch the same entities in different orders — lock in a consistent order. Neo4j auto-sorts only relationship create/delete locks; sort property updates yourself.
- Prefer `CREATE` over `MERGE` on hot paths (MERGE can lock out of order → deadlock). Set `db.lock.acquisition.timeout` (default `0`=off) so a stuck writer fails fast.

## Driver transactions
- DO default to **managed transactions**: `executeRead`/`executeWrite` (5.x; `readTransaction`/`writeTransaction` in 4.4). The driver **auto-retries transient errors**, so the callback MUST be idempotent. Never return the raw `Result`; consume it inside.
- Use **explicit transactions** (`beginTransaction`→`commit`/`rollback`) only when a tx spans functions or wraps a non-rollbackable external call — no auto-retry. Set per-tx **timeout**/**metadata** via config. Sessions are NOT thread-safe (one tx at a time).

## CALL { } IN TRANSACTIONS (batched writes)
- DO wrap large imports/updates/deletes so each batch commits separately, avoiding one heap-eating tx (OOM/GC). Default batch **1000**; tune `OF 10000 ROWS`.
- CRITICAL: rows must come from a clause **before** the subquery (`UNWIND $rows AS r CALL {...} IN TRANSACTIONS`). A `MATCH` inside batches nothing — runs as one tx.
- **Auto-commit only**: forbidden inside an explicit tx (`:auto` in Browser). Committed batches are NOT rolled back if a later one fails.
- `ON ERROR CONTINUE|BREAK|FAIL` (default FAIL); `REPORT STATUS AS s` requires CONTINUE/BREAK. A failing batch rolls back whole — keep batches independent.
- `IN n CONCURRENT TRANSACTIONS` (slotted runtime only) is non-deterministic and deadlocks on shared `MERGE` — mitigate with `ON ERROR RETRY`. `DISJOINT BY` is Cypher-25 only.

## Cluster consistency
- Clusters give **causal consistency** via **bookmarks**: a session auto-chains its reads-after-writes. Pass bookmarks across sessions when a later one must see an earlier one's writes — a write is NOT globally visible the instant `executeWrite` returns; a follower read can lag.

Related: lore/neo4j/cypher-and-modeling.md · lore/neo4j/indexes-and-constraints.md · lore/neo4j/performance.md

## Sources
neo4j.com/docs/operations-manual/current/database-internals/concurrent-data-access · neo4j.com/docs/cypher-manual/current/subqueries/subqueries-in-transactions · neo4j.com/docs/java-manual/current/transactions
