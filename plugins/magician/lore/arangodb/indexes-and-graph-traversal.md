# ArangoDB — Indexes and Graph Traversal

Version: stable 3.12.x (3.12.9; devel 4.0). Multi-model (doc+graph+KV) via AQL; BSL 1.1 since 3.12. Auto indexes: `_key` (primary; `_id` derived) per collection, both `_from`+`_to` (edge index) per edge collection — enabling index-free adjacency (O(edges-visited)).

## Anchoring
- Traversal is O(edges traversed) ONLY when the start node is index-resolved. A `startNode` as an `_id` string / `{_id}` uses the primary index (cheap). Pick start nodes via `FILTER d.attr==@x`? Add a **persistent** index on `attr` or you full-scan the collection.
- DON'T pass the direction (`OUTBOUND|INBOUND|ANY`) as a bind parameter — must be literal. DO parameterize `startNode` and filter values (`@bind`) for plan reuse + safety.

## Persistent index (the workhorse)
- Serves equality, leftmost-prefix, range, sort; logarithmic. Options: `unique`, `sparse`, `storedValues` (covering projections, not filter/sort), `cacheEnabled` (caches full-cover `==`).
- Combined `["a","b"]` serves `a` and `a== && b<…`, NOT `b` alone. Later fields count only after earlier ones are pinned by `==`/`IN`; the first range field ends the chain.
- `sparse` skips docs missing the field or holding `null` — smaller/faster, but can't serve `== null` or when the optimizer can't prove non-null. Good for optional-unique keys.
- Used only with `== < <= > >= IN`; wrapping the attribute (`TO_NUMBER(d.v)`, `d.v-1==42`) disables it. One index/collection under `AND`; several under `OR` (folded to `IN`). Confirm with `db._explain(q)` and check the selectivity estimates.

## Vertex-centric indexes (supernodes)
For high-degree hubs filtered during traversal, index `["_from", attr]` (OUTBOUND) or `["_to", attr]` (INBOUND) — both for `ANY`; use `mdi-prefixed` for range filters on numeric edge attrs. Optimizer MAY pick it (not guaranteed); `indexHint` (3.12.1) prefers it over the edge index but can't force.

## Traversal idioms
- `FOR v,e,p IN min..max OUTBOUND @start GRAPH "g"` — `min` defaults 1 (floor 0); `max` defaults to `min`. Path exposes `p.vertices`/`p.edges`/`p.weights`.
- `PRUNE cond` stops descending a path as early as possible — far cheaper than post-`FILTER`; use it to bound expansion (one per FOR).
- `OPTIONS`: `order` = `dfs` (default)/`bfs`/`weighted` (3.8+; `weightAttribute`/`defaultWeight`, no negatives). `uniqueVertices` = `none` (default)/`path`/`global` (needs bfs/weighted; non-deterministic). `uniqueEdges` = `path` (default)/`none` (follows cycles — avoid).
- DON'T leave depth open-ended: unbounded / huge `max` with no uniqueness explodes on cycles. Bound `max`; use `path` uniqueness on cyclic graphs.
- Shortest paths: use `SHORTEST_PATH`, `K_SHORTEST_PATHS`, `K_PATHS`, `ALL_SHORTEST_PATHS` — don't emulate with deep traversals.
- Cluster: `WITH vColl,…` at query top is REQUIRED to declare vertex collections (missing → error). Enterprise SmartGraphs shard by a smart attribute to keep traversals node-local. Anonymous graph = an edge-collection list instead of `GRAPH "g"`.

See lore/arangodb/aql-and-modeling.md for schema/query shape and lore/arangodb/performance.md for the prioritized playbook (incl. `parallelism`/`maxProjections`/`useCache`).

## Sources
docs.arango.ai/arangodb/3.12 — indexing (which-index-to-use-when, index-utilization, vertex-centric-indexes); aql/graph-queries (traversals, traversals-explained)
