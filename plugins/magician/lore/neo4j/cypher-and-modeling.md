# Neo4j — Cypher & modeling

Calendar-versioned (2026.06 at writing); **5.x is LTS**, **4.4 legacy**. Two Cypher languages: **Cypher 5** (frozen) and **Cypher 25** (from 2025.06, ISO-GQL-aligned). Select via a `CYPHER 25` prefix or per-DB `SET DEFAULT LANGUAGE`.

## Property graph model
Nodes carry **0+ labels** (lookup tags) + properties; relationships carry **exactly one type**, are **always directed** (start+end), and may hold properties. Properties are scalars or single-type lists (no nested maps) — decompose structured data into nodes+rels.

## Reading: anchor, then traverse
Index-free adjacency makes hops cheap **only once you have a start node**. Anchor on an **indexed** property (`MATCH (p:Person {email:$e})`), then traverse; an unanchored match is a full label scan. `PROFILE` nontrivial queries — a scan on a hot path means a missing index (lore/neo4j/indexes-and-constraints.md). Two disconnected `MATCH` patterns make a **cartesian product** — connect or split them.

## Variable-length & quantified paths
`-[:KNOWS*1..3]->`: **always bound it** — unbounded `[*]` walks the whole reachable subgraph and blows up. **Quantified path patterns** repeat a segment: `((a)-[:R]->(b)){1,5}` — prefer QPP over `*`. Use `shortestPath`/`SHORTEST k` for reachability, not hand-rolled traversal.

## Writing: MERGE & batches
`MERGE` matches or creates the **entire** pattern — the top footgun: merging a full path that includes a new node duplicates nodes you meant to reuse. Idiom: **MERGE anchor nodes first, then the relationship** (`ON CREATE SET`/`ON MATCH SET` for upsert). MERGE locks end nodes but is *not* uniqueness — back each key with a uniqueness constraint. Batch with **UNWIND** (one plan): `UNWIND $rows AS r MERGE (p:Person{id:r.id}) SET p += r.props`.

## Subqueries & batching
Use the **scope-clause** form `CALL (var) { … }` (importing `WITH` is deprecated). For big loads/deletes, chunk commits with `CALL (row) { … } IN TRANSACTIONS OF 10000 ROWS` so heap isn't exhausted.

## Modeling idioms
- **Specific relationship types** beat generic `:REL`+type-property — the type prunes traversal; model direction+shape for hottest traversals.
- **Supernodes** (very high-degree hubs) wreck traversal — split by rel type, insert intermediate nodes, or move hot filters onto the relationship (lore/neo4j/performance.md). Reify n-ary/attributed events as **nodes** (an `:Order` between `:Customer`/`:Product`), not overloaded relationships.

## Version gotchas (4.4 → 5+)
`id()` deprecated — use **`elementId()`** (STRING; unstable across deletes, so key on your own IDs). `exists(n.prop)`→`n.prop IS NOT NULL`; `EXISTS { … }` is now a subquery. Index DDL is `CREATE INDEX … FOR (n:Label) ON (n.prop)` (old `ON :Label(prop)` and `START` removed).

## APOC & GDS
**APOC** = utility procedures (`apoc.periodic.iterate` batched writes, import/export). **GDS** runs parallel algorithms (centrality, community, pathfinding, embeddings) over an **in-memory projected graph** (`gds.graph.project`) — a snapshot; re-project after writes. Always `$parameterize` (plan cache + injection safety, lore/databases/parameterized-queries-and-injection.md); transactions: lore/neo4j/transactions-and-consistency.md.

## Sources
neo4j.com/docs/cypher-manual/current: /queries/select-version · /clauses/merge · /subqueries/call-subquery · /patterns/reference
