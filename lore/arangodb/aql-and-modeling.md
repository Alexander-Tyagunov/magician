# ArangoDB — AQL & Modeling

Version: 3.12.x stable (3.12.9). Multi-model — document + graph + key/value in one engine, queried with AQL. The self-managed build is BSL 1.1 since 3.12 (→ Apache 2.0 four years after release). SmartGraphs and OneShard are Enterprise-only.

## Data model
Property graph, labeled. Nodes live in **document collections**, edges in **edge collections**. Every edge carries `_from`/`_to` with the full endpoint `_id` (`Collection/_key`) — edges are always directed. Address a node by `_id`; `_key` is unique per collection only.

DO model many-to-many and anything traversed deeply as edges; embed 1:1 / 1:few data you always read together into the node (fewer lookups).
DO group edges by meaning into separate edge collections — the name is the relationship label, so traversing one type never scans the others.
DO give edges a stable `_key` and upsert (`UPSERT {_from,_to} INSERT … UPDATE …`) so re-imports stay idempotent.
DON'T over-normalize — splitting read-together fields across collections turns one read into a join.

## AQL essentials
Pipeline: `FOR … FILTER … LET … COLLECT … SORT … LIMIT … RETURN`. Bind parameters are mandatory — `@name` for values, `@@coll` for collection names — for plan-cache reuse and injection safety; never string-concat query text.

## Graph traversal
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

## Path finding
Prefer built-ins to hand-rolling: `SHORTEST_PATH`, `K_SHORTEST_PATHS` (weighted, ranked), `K_PATHS` (all paths in a depth band). All anchor on start/end `_id`s.

## Writes & scale
Batch: `FOR d IN @docs INSERT d INTO coll`, or `arangoimport` for bulk load — never one round-trip per node/edge. Supernodes (huge-degree hubs) throttle traversal; split via intermediate nodes, a dedicated edge type, or vertex-centric indexes. SmartGraphs (Enterprise) shard by a `smartGraphAttribute` to keep most edges node-local in a cluster.

Anchor and index choice: lore/arangodb/indexes-and-graph-traversal.md; tuning/measurement: lore/arangodb/performance.md. Universal DB rules: lore/databases.md (not repeated).

## Sources
- docs.arango.ai/arangodb/stable/aql/graph-queries/traversals/ (3.12.9)
- docs.arango.ai/arangodb/stable/graphs/ , /graphs/smartgraphs/
- github.com/arangodb/arangodb LICENSE (BSL 1.1)
