# Amazon Neptune — Query languages (Gremlin, openCypher, SPARQL)

Managed AWS graph DB; engine auto-updates, no version to pin. One quad store (S,P,O,G), two models: a **property graph** (Gremlin + openCypher) and **RDF** (SPARQL). Pick one per graph — RDF and property-graph data aren't cross-queryable.

## Choosing a language
- DO note Gremlin (TinkerPop, imperative `g.V().has(...).out(...)`) and openCypher (declarative `MATCH (a)-[:R]->(b)`) share the **same property graph** — either reads/mutates the other's data; mix by task.
- DO use SPARQL 1.1 (Query + Update) only for RDF; `G` holds the named-graph IRI.
- DO know Neptune Analytics (in-memory, algorithms + vector search) is **openCypher-only**; Neptune Database serves all three.

## Anchoring & index-free adjacency (the cost model)
- Neptune auto-maintains its indexes (SPOG/POGS/GPSO) — you never CREATE any. Traversal cost ≈ edges visited, **but only once anchored**.
- DO anchor on a selective start: `MATCH (n:Person {email:$e})` / `g.V().has('Person','email',x)`; a direct id lookup (`g.V(id)`, custom `~id`) is fastest. Bare `g.V()` / `MATCH (n)` is a full scan.
- DON'T leave variable-length paths unbounded (`-[:R*]->`, `repeat()` with no `times()/until()`) or write disconnected MATCH patterns (Cartesian product).

## Parameterize (plan cache + injection safety)
- DO pass a `parameters` JSON map and reference `$name` in the text — Neptune caches the AST. HTTPS `/openCypher` (`query=…&parameters={…}`) or Bolt `bolt+s://…:8182`; Gremlin binds via GLV. Never string-concat values.

## openCypher gotchas (spec = openCypher 9, not Neo4j)
- IDs are **strings**; `id()` returns a string. `CREATE`/`MERGE`/`MATCH` accept custom `~id`.
- Unsupported: `shortestPath()`/`allShortestPath()`, `CALL{}`/`YIELD`, user-defined funcs + APOC, dynamic `map[key]`, non-constant `SKIP`/`LIMIT`, mutating `UNION`. Rewrite migrated Neo4j Cypher.
- Multi-valued props (from Gremlin/loader) → openCypher picks one arbitrarily (non-deterministic); `NaN` comparisons undefined.

## Gremlin tuning
- A traversal is a mutation if it has `addV/addE/property/drop`, else read-only. Default is BFS.
- DO `profile`/`explain` (`/gremlin/profile`, `/gremlin/explain`) for index ops + per-step counts; apply hints `g.withSideEffect('Neptune#repeatMode','DFS')`, `'Neptune#useDFE',true`.

## Transactions & isolation
- Read-only runs under **SNAPSHOT** (MVCC) — no dirty/non-repeatable/phantom reads, never blocks writers. Replicas are snapshot + read-only with small lag; query the writer for read-your-writes.
- Mutations run **READ COMMITTED** but range/gap-lock read ranges, giving repeatable + no phantoms. Gremlin/Bolt read-write sessions put all queries under mutation isolation on the writer (10-min cap, rollback on failure).
- Conflicts: lock-wait up to 60s then rollback; deadlock rolls back the smaller txn at once. Gap locks yield ~3-4% false conflicts under load — **retry with backoff, idempotently** (lore/databases/resilience-and-observability.md).

See lore/neptune/data-loading-and-modeling.md and lore/neptune/performance.md.

## Sources
- docs.aws.amazon.com/neptune/latest/userguide/ — feature-overview-data-model, feature-opencypher-compliance, transactions-neptune, gremlin-query-hints, access-graph-gremlin-sessions
- docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html
