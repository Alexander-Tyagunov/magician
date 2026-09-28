# Neo4j — deep dive

> On-demand companion to `lore/neo4j.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Cypher & modeling](#cypher-and-modeling) · [Indexes & Constraints](#indexes-and-constraints) · [Transactions & Consistency](#transactions-and-consistency) · [Performance](#performance)

## Cypher & modeling <a id="cypher-and-modeling"></a>

Calendar-versioned (2026.06 at writing); **5.x is LTS**, **4.4 legacy**. Two Cypher languages: **Cypher 5** (frozen) and **Cypher 25** (from 2025.06, ISO-GQL-aligned). Select via a `CYPHER 25` prefix or per-DB `SET DEFAULT LANGUAGE`.

### Property graph model
Nodes carry **0+ labels** (lookup tags) + properties; relationships carry **exactly one type**, are **always directed** (start+end), and may hold properties. Properties are scalars or single-type lists (no nested maps) — decompose structured data into nodes+rels.

### Reading: anchor, then traverse
Index-free adjacency makes hops cheap **only once you have a start node**. Anchor on an **indexed** property (`MATCH (p:Person {email:$e})`), then traverse; an unanchored match is a full label scan. `PROFILE` nontrivial queries — a scan on a hot path means a missing index (lore/deep/neo4j.md#indexes-and-constraints). Two disconnected `MATCH` patterns make a **cartesian product** — connect or split them.

### Variable-length & quantified paths
`-[:KNOWS*1..3]->`: **always bound it** — unbounded `[*]` walks the whole reachable subgraph and blows up. **Quantified path patterns** repeat a segment: `((a)-[:R]->(b)){1,5}` — prefer QPP over `*`. Use `shortestPath`/`SHORTEST k` for reachability, not hand-rolled traversal.

### Writing: MERGE & batches
`MERGE` matches or creates the **entire** pattern — the top footgun: merging a full path that includes a new node duplicates nodes you meant to reuse. Idiom: **MERGE anchor nodes first, then the relationship** (`ON CREATE SET`/`ON MATCH SET` for upsert). MERGE locks end nodes but is *not* uniqueness — back each key with a uniqueness constraint. Batch with **UNWIND** (one plan): `UNWIND $rows AS r MERGE (p:Person{id:r.id}) SET p += r.props`.

### Subqueries & batching
Use the **scope-clause** form `CALL (var) { … }` (importing `WITH` is deprecated). For big loads/deletes, chunk commits with `CALL (row) { … } IN TRANSACTIONS OF 10000 ROWS` so heap isn't exhausted.

### Modeling idioms
- **Specific relationship types** beat generic `:REL`+type-property — the type prunes traversal; model direction+shape for hottest traversals.
- **Supernodes** (very high-degree hubs) wreck traversal — split by rel type, insert intermediate nodes, or move hot filters onto the relationship (lore/deep/neo4j.md#performance). Reify n-ary/attributed events as **nodes** (an `:Order` between `:Customer`/`:Product`), not overloaded relationships.

### Version gotchas (4.4 → 5+)
`id()` deprecated — use **`elementId()`** (STRING; unstable across deletes, so key on your own IDs). `exists(n.prop)`→`n.prop IS NOT NULL`; `EXISTS { … }` is now a subquery. Index DDL is `CREATE INDEX … FOR (n:Label) ON (n.prop)` (old `ON :Label(prop)` and `START` removed).

### APOC & GDS
**APOC** = utility procedures (`apoc.periodic.iterate` batched writes, import/export). **GDS** runs parallel algorithms (centrality, community, pathfinding, embeddings) over an **in-memory projected graph** (`gds.graph.project`) — a snapshot; re-project after writes. Always `$parameterize` (plan cache + injection safety, lore/deep/databases.md#parameterized-queries-and-injection); transactions: lore/deep/neo4j.md#transactions-and-consistency.

### Sources
neo4j.com/docs/cypher-manual/current: /queries/select-version · /clauses/merge · /subqueries/call-subquery · /patterns/reference

## Indexes & Constraints <a id="indexes-and-constraints"></a>

Version: 5.x LTS (5.26) + calendar releases (2025.xx / 2026.xx, e.g. 2026.06). Cypher is GQL-aligned. Index-free adjacency makes hops cheap ONCE you anchor on an indexed start node — indexes exist to find the *starting points* of a pattern, not to speed the traversal itself.

### Index types (5.x)
- **Token lookup** (label / rel-type): two exist by default, backing `NodeByLabelScan`. Drop them and label matches fall back to `AllNodesScan` (reads every node). Don't drop them.
- **RANGE** (default): `CREATE INDEX idx FOR (n:Person) ON (n.email)`. Solves `=`, `IN`, `>`/`<`, `STARTS WITH`, `IS NOT NULL`. Composite: `ON (n.a, n.b)`.
- **TEXT**: `CREATE TEXT INDEX t FOR (n:Person) ON (n.name)` — chosen only for `CONTAINS` / `ENDS WITH`; RANGE wins otherwise.
- **POINT**: spatial `point.distance()` / `point.withinBBox()`.
- **FULLTEXT** (Lucene): `CREATE FULLTEXT INDEX ft FOR (n:Doc) ON EACH [n.body]`. NOT auto-used by the planner — you must `CALL db.index.fulltext.queryNodes('ft', 'term')`.
- **VECTOR** (5.13+): `OPTIONS {indexConfig:{`vector.dimensions`:1536,`vector.similarity_function`:'cosine'}}` (dims 1–4096); query via `db.index.vector.queryNodes` (deprecated 2026.04 in favor of the `SEARCH` clause).

Relationship-property indexes: `FOR ()-[r:KNOWS]-() ON (r.since)`.

### DO
- Index (or unique-constrain) the property you look start nodes up by; PROFILE and confirm `NodeIndexSeek`, not `NodeByLabelScan`/`AllNodesScan`.
- Name every index/constraint and append `IF NOT EXISTS` for idempotent migrations.
- Composites: equality props first, at most one range/prefix predicate; a suffix/`CONTAINS` decays to existence-only, so add a TEXT index for those STRING props.
- Wait for `ONLINE`: an index is unusable while `POPULATING` — check `SHOW INDEXES` (state, failureMessage).

### DON'T
- Don't add a plain index on a property already covered by a uniqueness or node/rel-key constraint — those are **backed by a RANGE index** of the same schema (a duplicate is redundant). Existence & property-type constraints are NOT backed by an index.
- Don't expect an index when `null` isn't excluded — Neo4j indexes skip nulls; add `IS NOT NULL` or a type predicate to restore index use.
- Don't rely on FULLTEXT/VECTOR firing from a `WHERE` clause — they only engage via their procedures.

### Constraints (5.x `REQUIRE`)
- Uniqueness (Community; node & relationship): `CREATE CONSTRAINT c FOR (n:User) REQUIRE n.id IS UNIQUE`.
- Node/rel KEY, existence (`IS NOT NULL`), property type (`IS :: STRING`): Enterprise. Composite allowed only for uniqueness/key. Inspect with `SHOW CONSTRAINTS`.

### 4.4 → 5.x
- **BTREE removed in 5.0** → replaced by RANGE (+ TEXT/POINT). Drop old BTREE indexes and recreate as RANGE before/at upgrade, or the store won't start.
- Constraint syntax `CREATE CONSTRAINT ON (n:L) ASSERT ...` → `FOR (n:L) REQUIRE ...` (ON/ASSERT removed in 5.0).
- Relationship uniqueness (5.7), relationship-key & property-type constraints (5.9+) — don't use before their version.

Deep dives: lore/deep/neo4j.md#cypher-and-modeling, lore/deep/neo4j.md#performance, lore/deep/databases.md#resilience-and-observability.

### Sources
neo4j.com/docs/cypher-manual/current/indexes · .../constraints/managing-constraints

## Transactions & Consistency <a id="transactions-and-consistency"></a>

Version-adaptive: calendar versioning (2026.xx current; 5.26 LTS; 4.4 legacy), Cypher 25. Complements lore/deep/databases.md#transactions-and-isolation.

### Isolation & anomalies
- Default is **read-committed** — reads never block concurrent writes; serializable only via **explicit locks**.
- Expect **lost updates**, **non-repeatable reads**, and **missing/double reads** during index scans.
- Cypher auto-locks ONLY when a write directly depends on the read value: `SET n.c = n.c + 1` locks; read-then-write across statements does not — force a lock (dummy write) or serialize, never treat it as atomic.

### Locks & deadlocks
- Write locks hit node/property create-update-delete and relationship create/delete (both endpoints + the rel), held until commit/rollback.
- Deadlocks surface as `Neo.TransientError.Transaction.DeadlockDetected` (GQLSTATUS `50N05`, 5.25+) — **transient, retry the whole tx**, don't resume.
- DON'T let concurrent writers touch the same entities in different orders — lock in a consistent order. Neo4j auto-sorts only relationship create/delete locks; sort property updates yourself.
- Prefer `CREATE` over `MERGE` on hot paths (MERGE can lock out of order → deadlock). Set `db.lock.acquisition.timeout` (default `0`=off) so a stuck writer fails fast.

### Driver transactions
- DO default to **managed transactions**: `executeRead`/`executeWrite` (5.x; `readTransaction`/`writeTransaction` in 4.4). The driver **auto-retries transient errors**, so the callback MUST be idempotent. Never return the raw `Result`; consume it inside.
- Use **explicit transactions** (`beginTransaction`→`commit`/`rollback`) only when a tx spans functions or wraps a non-rollbackable external call — no auto-retry. Set per-tx **timeout**/**metadata** via config. Sessions are NOT thread-safe (one tx at a time).

### CALL { } IN TRANSACTIONS (batched writes)
- DO wrap large imports/updates/deletes so each batch commits separately, avoiding one heap-eating tx (OOM/GC). Default batch **1000**; tune `OF 10000 ROWS`.
- CRITICAL: rows must come from a clause **before** the subquery (`UNWIND $rows AS r CALL {...} IN TRANSACTIONS`). A `MATCH` inside batches nothing — runs as one tx.
- **Auto-commit only**: forbidden inside an explicit tx (`:auto` in Browser). Committed batches are NOT rolled back if a later one fails.
- `ON ERROR CONTINUE|BREAK|FAIL` (default FAIL); `REPORT STATUS AS s` requires CONTINUE/BREAK. A failing batch rolls back whole — keep batches independent.
- `IN n CONCURRENT TRANSACTIONS` (slotted runtime only) is non-deterministic and deadlocks on shared `MERGE` — mitigate with `ON ERROR RETRY`. `DISJOINT BY` is Cypher-25 only.

### Cluster consistency
- Clusters give **causal consistency** via **bookmarks**: a session auto-chains its reads-after-writes. Pass bookmarks across sessions when a later one must see an earlier one's writes — a write is NOT globally visible the instant `executeWrite` returns; a follower read can lag.

Related: lore/deep/neo4j.md#cypher-and-modeling · lore/deep/neo4j.md#indexes-and-constraints · lore/deep/neo4j.md#performance

### Sources
neo4j.com/docs/operations-manual/current/database-internals/concurrent-data-access · neo4j.com/docs/cypher-manual/current/subqueries/subqueries-in-transactions · neo4j.com/docs/java-manual/current/transactions

## Performance <a id="performance"></a>

Fix the biggest lever first, PROFILE every change. Current stable: 2026.x (CalVer `YYYY.MM.patch`), **5.26 LTS**; Cypher 5 + Cypher 25; 4.4 legacy (`dbms.*` → `server.*`). Depth is in the linked deep-dives — this is the checklist.

### 0. Measure first — PROFILE, don't guess
- DO `PROFILE`: runs the query, reports actual **Rows** + **DB Hits** per operator (read bottom-up). `EXPLAIN` only plans (no execution/counts) — use on writes you can't run.
- DO flag **Estimated Rows** far from actual **Rows** — a mis-estimate ⇒ poor plan (missing index/stale stats). The operator with huge DB Hits is the hotspot. lore/deep/neo4j.md#cypher-and-modeling.

### 1. Anchor on an indexed start node (index-free adjacency)
- DO open the plan with **NodeIndexSeek**, not **NodeByLabelScan**/**AllNodesScan**. Traversal is O(rels visited) *only once anchored*; an unindexed anchor scans the whole label first. Index every property you look start nodes up by. lore/deep/neo4j.md#indexes-and-constraints.
- DO match predicate to index type: RANGE for `=`/`<`/`>`/prefix, TEXT for `CONTAINS`/`ENDS WITH`, POINT for spatial. Leading-wildcard `CONTAINS` can't seek.

### 2. Fix query shape (cheapest big wins)
- DO parameterize (`$param`): plan-cache reuse + injection-safe; never string-concat.
- DO bound variable-length paths `[:R*1..3]`, never `[*]` (combinatorial blow-up); `RETURN` only needed fields, not whole nodes/rels.
- DON'T leave disconnected MATCH patterns ⇒ **CartesianProduct** (row explosion); connect them or split with `WITH`/subquery.
- DON'T trip an **Eager** operator (read-then-write over one set) — it buffers *all* upstream rows in heap; split the pass or batch it.

### 3. Model around supernodes
- DO avoid traversing *through* very high-degree hubs — a supernode makes `Expand` touch millions of rels. Split with intermediate nodes or a more specific rel type, or move hot attributes off the hub; direction + rel type narrow the expand. lore/deep/neo4j.md#cypher-and-modeling.

### 4. Batch writes — never node-per-request
- DO `UNWIND $rows` to create/merge a whole list in one statement. For big loads: `CALL { … } IN TRANSACTIONS OF 1000 ROWS` (implicit txn / `:auto`), `ON ERROR RETRY` for deadlocks, `IN n CONCURRENT TRANSACTIONS` for parallelism. lore/deep/neo4j.md#transactions-and-consistency.
- DO back every `MERGE` key with a uniqueness/key constraint — else full label scan *and* concurrent duplicates. MERGE nodes first, then the relationship.
- DON'T hold one giant transaction (heap-bound) — `IN TRANSACTIONS` commits per batch, dodging OOM/GC.

### 5. Memory & server (self-hosted)
- DO size `server.memory.pagecache.size` to hold store + native indexes (~1.2× on-disk); set heap `initial_size` = `max_size` to avoid full-GC pauses. Start from `neo4j-admin server memory-recommendation`.
- DO cap runaway queries: `db.memory.transaction.max` / `dbms.memory.transaction.total.max`. Pooling & timeouts/retries: lore/deep/databases.md#connection-pooling, lore/deep/databases.md#resilience-and-observability.

### Sources
- neo4j.com/docs/cypher-manual/current/planning-and-tuning/execution-plans/
- neo4j.com/docs/cypher-manual/current/planning-and-tuning/query-tuning/
- neo4j.com/docs/cypher-manual/current/subqueries/subqueries-in-transactions/
- neo4j.com/docs/cypher-manual/current/clauses/merge/
- neo4j.com/docs/operations-manual/current/performance/memory-configuration/
