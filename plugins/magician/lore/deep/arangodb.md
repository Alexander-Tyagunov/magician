# ArangoDB — deep dive

> On-demand companion to `lore/arangodb.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [AQL & Modeling](#aql-and-modeling) · [Indexes and Graph Traversal](#indexes-and-graph-traversal) · [Performance](#performance)

## AQL & Modeling <a id="aql-and-modeling"></a>

Version: 3.12.x stable (3.12.9). Multi-model — document + graph + key/value in one engine, queried with AQL. The self-managed build is BSL 1.1 since 3.12 (→ Apache 2.0 four years after release). SmartGraphs and OneShard are Enterprise-only.

### Data model
Property graph, labeled. Nodes live in **document collections**, edges in **edge collections**. Every edge carries `_from`/`_to` with the full endpoint `_id` (`Collection/_key`) — edges are always directed. Address a node by `_id`; `_key` is unique per collection only.

DO model many-to-many and anything traversed deeply as edges; embed 1:1 / 1:few data you always read together into the node (fewer lookups).
DO group edges by meaning into separate edge collections — the name is the relationship label, so traversing one type never scans the others.
DO give edges a stable `_key` and upsert (`UPSERT {_from,_to} INSERT … UPDATE …`) so re-imports stay idempotent.
DON'T over-normalize — splitting read-together fields across collections turns one read into a join.

### AQL essentials
Pipeline: `FOR … FILTER … LET … COLLECT … SORT … LIMIT … RETURN`. Bind parameters are mandatory — `@name` for values, `@@coll` for collection names — for plan-cache reuse and injection safety; never string-concat query text.

### Graph traversal
```
FOR v, e, p IN min..max OUTBOUND|INBOUND|ANY startNode
  GRAPH "myGraph"                 // named graph
  // or: edgeColl1, edgeColl2     // anonymous set
  [PRUNE cond] [OPTIONS { … }]
```
`v`=node, `e`=edge, `p`=path (`p.vertices`/`.edges`/`.weights`). `min..max` defaults to `1..1`, and **max defaults to min** — a bare `IN OUTBOUND` visits depth 1 only. `startNode` is an `_id` string (or doc with `_id`); a missing id → empty result, no error. Direction is a keyword, not bindable. In a **cluster**, declare collections up front with `WITH`.

DO always bound `max` — unbounded depth explodes on cyclic data.
DO use `PRUNE` to stop descending a path the instant a condition holds — it cuts far more than a trailing `FILTER`, which still traverses everything.
DO set `OPTIONS { uniqueVertices:"global", order:"bfs" }` for reachability/shortest-hop (`global` requires `bfs` or `weighted`); default `uniqueEdges:"path"` already blocks edge repeats per path.
DO scope with the `edgeCollections`/`vertexCollections` options, or cost paths with `order:"weighted"` + `weightAttribute` (negative weights error).
DON'T rely on default `dfs` order when you need nearest-first results.

### Path finding
Prefer built-ins to hand-rolling: `SHORTEST_PATH`, `K_SHORTEST_PATHS` (weighted, ranked), `K_PATHS` (all paths in a depth band). All anchor on start/end `_id`s.

### Writes & scale
Batch: `FOR d IN @docs INSERT d INTO coll`, or `arangoimport` for bulk load — never one round-trip per node/edge. Supernodes (huge-degree hubs) throttle traversal; split via intermediate nodes, a dedicated edge type, or vertex-centric indexes. SmartGraphs (Enterprise) shard by a `smartGraphAttribute` to keep most edges node-local in a cluster.

Anchor and index choice: lore/deep/arangodb.md#indexes-and-graph-traversal; tuning/measurement: lore/deep/arangodb.md#performance. Universal DB rules: lore/databases.md (not repeated).

### Sources
- docs.arango.ai/arangodb/stable/aql/graph-queries/traversals/ (3.12.9)
- docs.arango.ai/arangodb/stable/graphs/ , /graphs/smartgraphs/
- github.com/arangodb/arangodb LICENSE (BSL 1.1)

## Indexes and Graph Traversal <a id="indexes-and-graph-traversal"></a>

Version: stable 3.12.x (3.12.9; devel 4.0). Multi-model (doc+graph+KV) via AQL; BSL 1.1 since 3.12. Auto indexes: `_key` (primary; `_id` derived) per collection, both `_from`+`_to` (edge index) per edge collection — enabling index-free adjacency (O(edges-visited)).

### Anchoring
- Traversal is O(edges traversed) ONLY when the start node is index-resolved. A `startNode` as an `_id` string / `{_id}` uses the primary index (cheap). Pick start nodes via `FILTER d.attr==@x`? Add a **persistent** index on `attr` or you full-scan the collection.
- DON'T pass the direction (`OUTBOUND|INBOUND|ANY`) as a bind parameter — must be literal. DO parameterize `startNode` and filter values (`@bind`) for plan reuse + safety.

### Persistent index (the workhorse)
- Serves equality, leftmost-prefix, range, sort; logarithmic. Options: `unique`, `sparse`, `storedValues` (covering projections, not filter/sort), `cacheEnabled` (caches full-cover `==`).
- Combined `["a","b"]` serves `a` and `a== && b<…`, NOT `b` alone. Later fields count only after earlier ones are pinned by `==`/`IN`; the first range field ends the chain.
- `sparse` skips docs missing the field or holding `null` — smaller/faster, but can't serve `== null` or when the optimizer can't prove non-null. Good for optional-unique keys.
- Used only with `== < <= > >= IN`; wrapping the attribute (`TO_NUMBER(d.v)`, `d.v-1==42`) disables it. One index/collection under `AND`; several under `OR` (folded to `IN`). Confirm with `db._explain(q)` and check the selectivity estimates.

### Vertex-centric indexes (supernodes)
For high-degree hubs filtered during traversal, index `["_from", attr]` (OUTBOUND) or `["_to", attr]` (INBOUND) — both for `ANY`; use `mdi-prefixed` for range filters on numeric edge attrs. Optimizer MAY pick it (not guaranteed); `indexHint` (3.12.1) prefers it over the edge index but can't force.

### Traversal idioms
- `FOR v,e,p IN min..max OUTBOUND @start GRAPH "g"` — `min` defaults 1 (floor 0); `max` defaults to `min`. Path exposes `p.vertices`/`p.edges`/`p.weights`.
- `PRUNE cond` stops descending a path as early as possible — far cheaper than post-`FILTER`; use it to bound expansion (one per FOR).
- `OPTIONS`: `order` = `dfs` (default)/`bfs`/`weighted` (3.8+; `weightAttribute`/`defaultWeight`, no negatives). `uniqueVertices` = `none` (default)/`path`/`global` (needs bfs/weighted; non-deterministic). `uniqueEdges` = `path` (default)/`none` (follows cycles — avoid).
- DON'T leave depth open-ended: unbounded / huge `max` with no uniqueness explodes on cycles. Bound `max`; use `path` uniqueness on cyclic graphs.
- Shortest paths: use `SHORTEST_PATH`, `K_SHORTEST_PATHS`, `K_PATHS`, `ALL_SHORTEST_PATHS` — don't emulate with deep traversals.
- Cluster: `WITH vColl,…` at query top is REQUIRED to declare vertex collections (missing → error). Enterprise SmartGraphs shard by a smart attribute to keep traversals node-local. Anonymous graph = an edge-collection list instead of `GRAPH "g"`.

See lore/deep/arangodb.md#aql-and-modeling for schema/query shape and lore/deep/arangodb.md#performance for the prioritized playbook (incl. `parallelism`/`maxProjections`/`useCache`).

### Sources
docs.arango.ai/arangodb/3.12 — indexing (which-index-to-use-when, index-utilization, vertex-centric-indexes); aql/graph-queries (traversals, traversals-explained)

## Performance <a id="performance"></a>

Version: 3.12 stable (multi-model doc+graph+key/value, AQL; SmartGraphs/SatelliteGraphs are Enterprise; BSL 1.1). Verify version + edition before assuming SmartGraph/vertex-centric. Plan costs are heuristic, unit-less — measure on real data.

### Prioritized levers (highest impact first)
1. ANCHOR on an indexed start. `FOR d IN c FILTER d.x==@v` with no `persistent` index on `x` is an `EnumerateCollectionNode` (full scan); `ensureIndex({type:"persistent",fields:["x"]})` makes it an `IndexNode`. Traversal starts need an indexed anchor too.
2. INDEX FOR PREDICATE + SORT. Persistent indexes are ordered: one serves FILTER + SORT (`use-index-for-sort` drops the SortNode) and ranges (`use-index-range`). Honor leftmost-prefix (equality before range). One index per collection per branch — build composites, not single-field ones.
3. RETURN LESS: project only needed fields (`RETURN {a:d.a}`) for index-only scans (plan note `index only, projections`); avoid bare `RETURN d`.
4. BOUND traversals: always `IN min..max` with a real upper bound; `PRUNE` to stop descending when true (one per FOR). For reachability use `OPTIONS {order:"bfs", uniqueVertices:"global"}` (global needs bfs/weighted) to cap revisits.
5. BEAT SUPERNODES with vertex-centric indexes: `persistent` on `["_from",attr]` (OUTBOUND) or `["_to",attr]` (INBOUND); `mdi-prefixed` for range attrs — matches edges directly, not every hub edge.
6. BATCH writes: `FOR d IN @rows INSERT d INTO @@coll` in one statement, or `arangoimport` — not a request per document. Keep txns bounded (single-server ACID; cluster txns add coordination cost).
7. PARAMETERIZE with `@bindVars` (`@@coll` for collections) — plan-cache reuse + injection safety; never string-concat.
8. CACHE hot repeats: results cache is single-server only (off/on/demand, keyed on string+binds); cluster leans on plan cache + indexes.

### How to profile / measure
- `db._profileQuery(q, binds, {colors:false})` (or web Profile): per-stage **Call / Items / Filtered / Runtime** — spot the busiest.
- `db._createStatement(q).explain()` (or `require("@arangodb/aql/explainer").explain(q)`): pipeline, chosen indexes, applied rules. Confirm an `IndexNode` (not `EnumerateCollectionNode`) and `use-indexes`/`use-index-for-sort` fired; watch `stats.peakMemoryUsage`.
- Cluster: read the **Site** column — keep FILTERs on **DBS** shards to ship less over Scatter/Gather/Remote nodes.

### Top anti-patterns
- Unindexed anchor, or unbounded `[*]` path → scans + memory blowups.
- CROSS PRODUCT: two `FOR`s with no join predicate — nested full scans.
- Row-by-row writes; unbounded txns; filtering through supernodes without a vertex-centric index.
- Trusting estimates over an actual profile.

Cross-refs: lore/deep/arangodb.md#aql-and-modeling; lore/deep/arangodb.md#indexes-and-graph-traversal; lore/deep/databases.md#connection-pooling; lore/deep/databases.md#resilience-and-observability.

### Sources
docs.arangodb.com/3.12/aql/execution-and-performance/{query-optimization,query-profiling,caching-query-results}; .../indexes-and-search/indexing/{index-utilization,working-with-indexes/vertex-centric-indexes}; .../aql/graph-queries/traversals
