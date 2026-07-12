# ArangoDB — core digest
Version: 3.12 stable (devel → 4.0); 3.10 EOL 2024-04, 3.11 maintenance. BUSL-1.1 → Apache 2.0 after 4y. Community 3.12.5+ = all Enterprise features, 100 GiB cap. Multi-model doc+graph+KV, AQL/RocksDB.

DO anchor traversals on an INDEXED vertex — index-free adjacency is O(edges) from an indexed key, else full scan; bind @params (never concat AQL), EXPLAIN nontrivial queries.
DO index lookup props: persistent (unique/sparse/covering), auto edge index (_from/_to), ArangoSearch/inverted for search; vertex-centric indexes tame hubs.
DO bound-depth traverse FOR v,e,p IN 1..n OUTBOUND|INBOUND|ANY start GRAPH 'g'; uniqueVertices/uniqueEdges, PRUNE early; SHORTEST_PATH for paths.
DO batch writes: FOR d IN @docs INSERT d IN coll (UPSERT differs: UPSERT <search> INSERT <doc> UPDATE|REPLACE <doc> IN coll); arangoimport to bulk-load, never per-doc.
DO use named graphs (edge defs enforce integrity); SmartGraphs/OneShard keep traversals local.

DON'T let supernodes sit on hot paths — split via intermediate nodes / typed edges / vertex-centric indexes.
DON'T leave depth unbounded or write disconnected FORs (cartesian blowup).
DON'T span multi-doc ACID across shards; single-doc writes atomic.

Deep dive — read lore/arangodb/{aql-and-modeling,indexes-and-graph-traversal,performance}.md

## Sources
docs.arango.ai/arangodb/3.12 · github.com/arangodb/arangodb
