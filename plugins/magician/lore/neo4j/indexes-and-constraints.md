# Neo4j — Indexes & Constraints

Version: 5.x LTS (5.26) + calendar releases (2025.xx / 2026.xx, e.g. 2026.06). Cypher is GQL-aligned. Index-free adjacency makes hops cheap ONCE you anchor on an indexed start node — indexes exist to find the *starting points* of a pattern, not to speed the traversal itself.

## Index types (5.x)
- **Token lookup** (label / rel-type): two exist by default, backing `NodeByLabelScan`. Drop them and label matches fall back to `AllNodesScan` (reads every node). Don't drop them.
- **RANGE** (default): `CREATE INDEX idx FOR (n:Person) ON (n.email)`. Solves `=`, `IN`, `>`/`<`, `STARTS WITH`, `IS NOT NULL`. Composite: `ON (n.a, n.b)`.
- **TEXT**: `CREATE TEXT INDEX t FOR (n:Person) ON (n.name)` — chosen only for `CONTAINS` / `ENDS WITH`; RANGE wins otherwise.
- **POINT**: spatial `point.distance()` / `point.withinBBox()`.
- **FULLTEXT** (Lucene): `CREATE FULLTEXT INDEX ft FOR (n:Doc) ON EACH [n.body]`. NOT auto-used by the planner — you must `CALL db.index.fulltext.queryNodes('ft', 'term')`.
- **VECTOR** (5.13+): `OPTIONS {indexConfig:{`vector.dimensions`:1536,`vector.similarity_function`:'cosine'}}` (dims 1–4096); query via `db.index.vector.queryNodes` (deprecated 2026.04 in favor of the `SEARCH` clause).

Relationship-property indexes: `FOR ()-[r:KNOWS]-() ON (r.since)`.

## DO
- Index (or unique-constrain) the property you look start nodes up by; PROFILE and confirm `NodeIndexSeek`, not `NodeByLabelScan`/`AllNodesScan`.
- Name every index/constraint and append `IF NOT EXISTS` for idempotent migrations.
- Composites: equality props first, at most one range/prefix predicate; a suffix/`CONTAINS` decays to existence-only, so add a TEXT index for those STRING props.
- Wait for `ONLINE`: an index is unusable while `POPULATING` — check `SHOW INDEXES` (state, failureMessage).

## DON'T
- Don't add a plain index on a property already covered by a uniqueness or node/rel-key constraint — those are **backed by a RANGE index** of the same schema (a duplicate is redundant). Existence & property-type constraints are NOT backed by an index.
- Don't expect an index when `null` isn't excluded — Neo4j indexes skip nulls; add `IS NOT NULL` or a type predicate to restore index use.
- Don't rely on FULLTEXT/VECTOR firing from a `WHERE` clause — they only engage via their procedures.

## Constraints (5.x `REQUIRE`)
- Uniqueness (Community; node & relationship): `CREATE CONSTRAINT c FOR (n:User) REQUIRE n.id IS UNIQUE`.
- Node/rel KEY, existence (`IS NOT NULL`), property type (`IS :: STRING`): Enterprise. Composite allowed only for uniqueness/key. Inspect with `SHOW CONSTRAINTS`.

## 4.4 → 5.x
- **BTREE removed in 5.0** → replaced by RANGE (+ TEXT/POINT). Drop old BTREE indexes and recreate as RANGE before/at upgrade, or the store won't start.
- Constraint syntax `CREATE CONSTRAINT ON (n:L) ASSERT ...` → `FOR (n:L) REQUIRE ...` (ON/ASSERT removed in 5.0).
- Relationship uniqueness (5.7), relationship-key & property-type constraints (5.9+) — don't use before their version.

Deep dives: lore/neo4j/cypher-and-modeling.md, lore/neo4j/performance.md, lore/databases/resilience-and-observability.md.

## Sources
neo4j.com/docs/cypher-manual/current/indexes · .../constraints/managing-constraints
