# MongoDB — Indexes & query

Index + planner behavior. Server **8.x** stable (8.0 GA; 8.3 latest rapid); 7.0/8.0 supported, 6.0 EOL (2025-07). ODM concerns (`lean`/`select`/sanitization) → lore/mongoose*.

No server-side JOIN — embed/denormalize (see schema-design); back **each** query with an index. Unindexed predicate = `COLLSCAN`; `_id` is the only auto index.

## Index types

- **Single / compound** `createIndex({a:1,b:-1})` — serves only a **left prefix** (`a`, then `a,b`), never `b` alone.
- **Multikey** — automatic on array fields; a compound index allows **at most one array-valued field per document**. Bounds loose (matches if *any* element does).
- **Wildcard** `{"$**":1}` (4.2+; compound 7.0+) — arbitrary keys; no substitute for targeted indexes.
- **Hashed** — even spread for sharding; equality only, no range/sort.
- **Geospatial** `2dsphere`; **text** `$text` — prefer Atlas/MongoDB Search for text.
- Properties: **TTL** (`expireAfterSeconds`, single date field), **unique**, **partial** (`partialFilterExpression`; prefer over **sparse**; `unique`+partial constrains only matching docs), **hidden** (4.4+, invisible), **collation** (case-insensitive `strength:1|2`).
- **Clustered collections** (5.3+) store docs `_id`-ordered → `CLUSTERED_IXSCAN`, no separate `_id` index.

## Compound order: ESR

Order keys **Equality → Sort → Range**. Equality (`$eq`, small `$in`) pins a value, keeping later keys sorted; sort is index-served only when equality covers all preceding keys (no blocking `SORT`); range (`$gt/$lt/$ne/$nin/$regex`) last — a range *before* sort forces an in-memory `SORT` (**ERS** if selective).

## Read the plan

`db.c.find(q).explain("executionStats")` (or `allPlansExecution`). Compare `nReturned` vs `totalDocsExamined` vs `totalKeysExamined` — ideal: all ≈ equal.
- `totalDocsExamined >> nReturned` → weak index; `COLLSCAN` on a big coll → missing index; `SORT` stage → not index-backed.
- **Covered query**: an `IXSCAN` with **no `FETCH`** — all fields indexed, projection returns only those (exclude `_id` unless indexed); `totalDocsExamined:0`, cheapest.
- `explain` bypasses the plan cache. Stages `IXSCAN/FETCH/COLLSCAN/SORT/IDHACK`, `OR` (`$or` union). SBE (5.1+, explainVersion 2) nests `queryPlan`/`slotBasedPlan`; **EXPRESS_\*** (8.0+) fast-path simple `_id`/single-index ops.

## Idioms & gotchas

- **Paginate by range**, not `skip()` (walks skipped): `find({_id:{$gt:last}}).sort({_id:1}).limit(n)` — stable, O(page).
- **Project** to cut payload + enable covered reads: `find(q,{a:1,_id:0})`.
- **Sargable**: don't wrap the indexed field (`$expr` math, unanchored `$regex:/x/`, `$where`) — kills index use.
- Build large indexes **rolling** per member (`background` is a no-op/ignored since hybrid builds in 4.2).
- Drop dead indexes via `$indexStats` — each index taxes writes + RAM (index + hot data should fit memory).
- Consistency: reads default to `readConcern:"local"`; use `"majority"`/`"snapshot"` + causal-consistent sessions to see prior writes (see transactions).

See lore/mongodb/performance.md and lore/databases/indexing-and-query-plans.md.

## Sources

- Indexing & ESR: https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/
- Index types & properties: https://www.mongodb.com/docs/manual/core/indexes/index-types/ , index-properties/
- Explain & analyze plan: https://www.mongodb.com/docs/manual/reference/explain-results/ , tutorial/analyze-query-plan/
