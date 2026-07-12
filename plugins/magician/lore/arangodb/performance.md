# ArangoDB — Performance

Version: 3.12 stable (multi-model doc+graph+key/value, AQL; SmartGraphs/SatelliteGraphs are Enterprise; BSL 1.1). Verify version + edition before assuming SmartGraph/vertex-centric. Plan costs are heuristic, unit-less — measure on real data.

## Prioritized levers (highest impact first)
1. ANCHOR on an indexed start. `FOR d IN c FILTER d.x==@v` with no `persistent` index on `x` is an `EnumerateCollectionNode` (full scan); `ensureIndex({type:"persistent",fields:["x"]})` makes it an `IndexNode`. Traversal starts need an indexed anchor too.
2. INDEX FOR PREDICATE + SORT. Persistent indexes are ordered: one serves FILTER + SORT (`use-index-for-sort` drops the SortNode) and ranges (`use-index-range`). Honor leftmost-prefix (equality before range). One index per collection per branch — build composites, not single-field ones.
3. RETURN LESS: project only needed fields (`RETURN {a:d.a}`) for index-only scans (plan note `index only, projections`); avoid bare `RETURN d`.
4. BOUND traversals: always `IN min..max` with a real upper bound; `PRUNE` to stop descending when true (one per FOR). For reachability use `OPTIONS {order:"bfs", uniqueVertices:"global"}` (global needs bfs/weighted) to cap revisits.
5. BEAT SUPERNODES with vertex-centric indexes: `persistent` on `["_from",attr]` (OUTBOUND) or `["_to",attr]` (INBOUND); `mdi-prefixed` for range attrs — matches edges directly, not every hub edge.
6. BATCH writes: `FOR d IN @rows INSERT d INTO @@coll` in one statement, or `arangoimport` — not a request per document. Keep txns bounded (single-server ACID; cluster txns add coordination cost).
7. PARAMETERIZE with `@bindVars` (`@@coll` for collections) — plan-cache reuse + injection safety; never string-concat.
8. CACHE hot repeats: results cache is single-server only (off/on/demand, keyed on string+binds); cluster leans on plan cache + indexes.

## How to profile / measure
- `db._profileQuery(q, binds, {colors:false})` (or web Profile): per-stage **Call / Items / Filtered / Runtime** — spot the busiest.
- `db._createStatement(q).explain()` (or `require("@arangodb/aql/explainer").explain(q)`): pipeline, chosen indexes, applied rules. Confirm an `IndexNode` (not `EnumerateCollectionNode`) and `use-indexes`/`use-index-for-sort` fired; watch `stats.peakMemoryUsage`.
- Cluster: read the **Site** column — keep FILTERs on **DBS** shards to ship less over Scatter/Gather/Remote nodes.

## Top anti-patterns
- Unindexed anchor, or unbounded `[*]` path → scans + memory blowups.
- CROSS PRODUCT: two `FOR`s with no join predicate — nested full scans.
- Row-by-row writes; unbounded txns; filtering through supernodes without a vertex-centric index.
- Trusting estimates over an actual profile.

Cross-refs: lore/arangodb/aql-and-modeling.md; lore/arangodb/indexes-and-graph-traversal.md; lore/databases/connection-pooling.md; lore/databases/resilience-and-observability.md.

## Sources
docs.arangodb.com/3.12/aql/execution-and-performance/{query-optimization,query-profiling,caching-query-results}; .../indexes-and-search/indexing/{index-utilization,working-with-indexes/vertex-centric-indexes}; .../aql/graph-queries/traversals
