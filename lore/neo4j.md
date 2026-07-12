# Neo4j — core digest
Version: 5.26 LTS + 2025.x/2026.x calendar releases; 4.4 EOL 2025-11. Cypher aligns to GQL. Gates: 5.0 dropped BTREE (use RANGE/POINT/TEXT/LOOKUP); 5.x adds VECTOR indexes + CALL{} IN TRANSACTIONS.

DO index start-node lookup props (CREATE INDEX/constraint): index-free adjacency is O(rels visited) ONLY with an indexed anchor — else full label scan.
DO PROFILE/EXPLAIN; watch db-hits/rows; avoid Eager, CARTESIAN products (disconnected patterns), unbounded [*].
DO batch writes with $params: UNWIND $rows in one stmt; CALL{} IN TRANSACTIONS OF n ROWS for big writes; neo4j-admin import to bulk-load. Never concat (plan-cache/injection-safe).
DO model rel direction + type for hot traversals; MERGE only on a constrained key. KEY/existence/type constraints = Enterprise.
DO use Bolt drivers (execute_read/write, retries, bookmarks for causal reads); prefer APOC/GDS over hand-rolling.

DON'T let supernodes sit on hot traversals — split via intermediate nodes/rel types or off-load hub props.
DON'T MERGE a full pattern on unindexed props: scans + duplicate nodes. MATCH-then-CREATE or constrain the key.
DON'T commit one node/edge per request, or run one giant unbatched tx (heap/GC blowups).

Deep dive when writing non-trivial Neo4j — read lore/neo4j/{cypher-and-modeling,indexes-and-constraints,transactions-and-consistency,performance}.md

## Sources
neo4j.com/docs/cypher-manual/current · neo4j.com/developer/kb/neo4j-supported-versions
