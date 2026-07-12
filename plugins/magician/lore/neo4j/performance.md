# Neo4j — Performance

Fix the biggest lever first, PROFILE every change. Current stable: 2026.x (CalVer `YYYY.MM.patch`), **5.26 LTS**; Cypher 5 + Cypher 25; 4.4 legacy (`dbms.*` → `server.*`). Depth is in the linked deep-dives — this is the checklist.

## 0. Measure first — PROFILE, don't guess
- DO `PROFILE`: runs the query, reports actual **Rows** + **DB Hits** per operator (read bottom-up). `EXPLAIN` only plans (no execution/counts) — use on writes you can't run.
- DO flag **Estimated Rows** far from actual **Rows** — a mis-estimate ⇒ poor plan (missing index/stale stats). The operator with huge DB Hits is the hotspot. lore/neo4j/cypher-and-modeling.md.

## 1. Anchor on an indexed start node (index-free adjacency)
- DO open the plan with **NodeIndexSeek**, not **NodeByLabelScan**/**AllNodesScan**. Traversal is O(rels visited) *only once anchored*; an unindexed anchor scans the whole label first. Index every property you look start nodes up by. lore/neo4j/indexes-and-constraints.md.
- DO match predicate to index type: RANGE for `=`/`<`/`>`/prefix, TEXT for `CONTAINS`/`ENDS WITH`, POINT for spatial. Leading-wildcard `CONTAINS` can't seek.

## 2. Fix query shape (cheapest big wins)
- DO parameterize (`$param`): plan-cache reuse + injection-safe; never string-concat.
- DO bound variable-length paths `[:R*1..3]`, never `[*]` (combinatorial blow-up); `RETURN` only needed fields, not whole nodes/rels.
- DON'T leave disconnected MATCH patterns ⇒ **CartesianProduct** (row explosion); connect them or split with `WITH`/subquery.
- DON'T trip an **Eager** operator (read-then-write over one set) — it buffers *all* upstream rows in heap; split the pass or batch it.

## 3. Model around supernodes
- DO avoid traversing *through* very high-degree hubs — a supernode makes `Expand` touch millions of rels. Split with intermediate nodes or a more specific rel type, or move hot attributes off the hub; direction + rel type narrow the expand. lore/neo4j/cypher-and-modeling.md.

## 4. Batch writes — never node-per-request
- DO `UNWIND $rows` to create/merge a whole list in one statement. For big loads: `CALL { … } IN TRANSACTIONS OF 1000 ROWS` (implicit txn / `:auto`), `ON ERROR RETRY` for deadlocks, `IN n CONCURRENT TRANSACTIONS` for parallelism. lore/neo4j/transactions-and-consistency.md.
- DO back every `MERGE` key with a uniqueness/key constraint — else full label scan *and* concurrent duplicates. MERGE nodes first, then the relationship.
- DON'T hold one giant transaction (heap-bound) — `IN TRANSACTIONS` commits per batch, dodging OOM/GC.

## 5. Memory & server (self-hosted)
- DO size `server.memory.pagecache.size` to hold store + native indexes (~1.2× on-disk); set heap `initial_size` = `max_size` to avoid full-GC pauses. Start from `neo4j-admin server memory-recommendation`.
- DO cap runaway queries: `db.memory.transaction.max` / `dbms.memory.transaction.total.max`. Pooling & timeouts/retries: lore/databases/connection-pooling.md, lore/databases/resilience-and-observability.md.

## Sources
- neo4j.com/docs/cypher-manual/current/planning-and-tuning/execution-plans/
- neo4j.com/docs/cypher-manual/current/planning-and-tuning/query-tuning/
- neo4j.com/docs/cypher-manual/current/subqueries/subqueries-in-transactions/
- neo4j.com/docs/cypher-manual/current/clauses/merge/
- neo4j.com/docs/operations-manual/current/performance/memory-configuration/
