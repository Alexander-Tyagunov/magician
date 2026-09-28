# Amazon Neptune — deep dive

> On-demand companion to `lore/neptune.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Query languages (Gremlin, openCypher, SPARQL)](#query-languages-gremlin-opencypher-sparql) · [Data loading & modeling](#data-loading-and-modeling) · [Performance](#performance)

## Query languages (Gremlin, openCypher, SPARQL) <a id="query-languages-gremlin-opencypher-sparql"></a>

Managed AWS graph DB; engine auto-updates, no version to pin. One quad store (S,P,O,G), two models: a **property graph** (Gremlin + openCypher) and **RDF** (SPARQL). Pick one per graph — RDF and property-graph data aren't cross-queryable.

### Choosing a language
- DO note Gremlin (TinkerPop, imperative `g.V().has(...).out(...)`) and openCypher (declarative `MATCH (a)-[:R]->(b)`) share the **same property graph** — either reads/mutates the other's data; mix by task.
- DO use SPARQL 1.1 (Query + Update) only for RDF; `G` holds the named-graph IRI.
- DO know Neptune Analytics (in-memory, algorithms + vector search) is **openCypher-only**; Neptune Database serves all three.

### Anchoring & index-free adjacency (the cost model)
- Neptune auto-maintains its indexes (SPOG/POGS/GPSO) — you never CREATE any. Traversal cost ≈ edges visited, **but only once anchored**.
- DO anchor on a selective start: `MATCH (n:Person {email:$e})` / `g.V().has('Person','email',x)`; a direct id lookup (`g.V(id)`, custom `~id`) is fastest. Bare `g.V()` / `MATCH (n)` is a full scan.
- DON'T leave variable-length paths unbounded (`-[:R*]->`, `repeat()` with no `times()/until()`) or write disconnected MATCH patterns (Cartesian product).

### Parameterize (plan cache + injection safety)
- DO pass a `parameters` JSON map and reference `$name` in the text — Neptune caches the AST. HTTPS `/openCypher` (`query=…&parameters={…}`) or Bolt `bolt+s://…:8182`; Gremlin binds via GLV. Never string-concat values.

### openCypher gotchas (spec = openCypher 9, not Neo4j)
- IDs are **strings**; `id()` returns a string. `CREATE`/`MERGE`/`MATCH` accept custom `~id`.
- Unsupported: `shortestPath()`/`allShortestPath()`, `CALL{}`/`YIELD`, user-defined funcs + APOC, dynamic `map[key]`, non-constant `SKIP`/`LIMIT`, mutating `UNION`. Rewrite migrated Neo4j Cypher.
- Multi-valued props (from Gremlin/loader) → openCypher picks one arbitrarily (non-deterministic); `NaN` comparisons undefined.

### Gremlin tuning
- A traversal is a mutation if it has `addV/addE/property/drop`, else read-only. Default is BFS.
- DO `profile`/`explain` (`/gremlin/profile`, `/gremlin/explain`) for index ops + per-step counts; apply hints `g.withSideEffect('Neptune#repeatMode','DFS')`, `'Neptune#useDFE',true`.

### Transactions & isolation
- Read-only runs under **SNAPSHOT** (MVCC) — no dirty/non-repeatable/phantom reads, never blocks writers. Replicas are snapshot + read-only with small lag; query the writer for read-your-writes.
- Mutations run **READ COMMITTED** but range/gap-lock read ranges, giving repeatable + no phantoms. Gremlin/Bolt read-write sessions put all queries under mutation isolation on the writer (10-min cap, rollback on failure).
- Conflicts: lock-wait up to 60s then rollback; deadlock rolls back the smaller txn at once. Gap locks yield ~3-4% false conflicts under load — **retry with backoff, idempotently** (lore/deep/databases.md#resilience-and-observability).

See lore/deep/neptune.md#data-loading-and-modeling and lore/deep/neptune.md#performance.

### Sources
- docs.aws.amazon.com/neptune/latest/userguide/ — feature-overview-data-model, feature-opencypher-compliance, transactions-neptune, gremlin-query-hints, access-graph-gremlin-sessions
- docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-features.html

## Data loading & modeling <a id="data-loading-and-modeling"></a>

Managed AWS graph service; no version knob (verify limits). One **property-graph** store serves both **Gremlin and openCypher** — either CSV dialect is queryable by both; **RDF/SPARQL** is a separate triple store. Neptune auto-indexes; **no user-defined secondary indexes**.

### Bulk loader, not per-element writes
DON'T ingest with loops of `addV`/`addE`/`MERGE`/`INSERT` — use the **Loader** (`POST …:port/loader`). Prereqs: files in **S3 same-Region**, an **IAM role attached to the cluster** (S3 read/list; no SSE-C), and an **S3 VPC endpoint**. Files: **UTF-8**, per-file `.gz`/`.bz2` only. Formats: `csv` (Gremlin), `opencypher`, `ntriples`, `nquads`, `turtle`, `rdfxml`. Params: `source` (S3 prefix), `format`, `iamRoleArn`, `mode` (`AUTO|NEW|RESUME`), `failOnError` (default TRUE), `parallelism` (`LOW|MEDIUM|HIGH`(default)`|OVERSUBSCRIBE`), `updateSingleCardinalityProperties`, `queueRequest` (**64** FIFO).

### Property-graph CSV headers (exact)
Gremlin — vertex: `~id` (required, unique), `~label` (multi via `;`); edge: `~id`,`~from`,`~to`,`~label` (single). Properties `name:Type`; cardinality `name:Type(single|set)` (default **set**), arrays `name:Type[]`; **edge props single-valued only**. Typed: numeric/Bool/String/Date/Datetime.
openCypher — nodes: `:ID` (+optional `:ID(space)`), `:LABEL`; rels: `:START_ID`,`:END_ID` (required), `:TYPE`, `:ID` required unless `userProvidedEdgeIds=FALSE`. Auto-cast types (Date/Duration/Point) stored verbatim.

### Ordering, resume & duplicate gotchas
Loader loads **all vertices before edges** — put nodes and edges under **separate S3 prefixes**. `edgeOnlyLoad=TRUE` skips the classification scan but errors `FROM_OR_TO_VERTEX_ARE_MISSING` if endpoints are absent. `mode=RESUME/AUTO` skips already-loaded files (cheap retries). Duplicate node IDs **merge** (single-value props chosen non-deterministically). Supply explicit relationship `:ID`s — without them the loader can't dedupe edges or resume, and a reload **duplicates every edge**. `HIGH`/`OVERSUBSCRIBE` on openCypher can throw `LOAD_DATA_DEADLOCK` → lower `parallelism`.

### Modeling for traversal
Use meaningful **user-supplied string IDs** — `g.V('user_42')` is a direct auto-indexed lookup; ID-less property lookups scan. **Anchor every traversal on an indexed start**, then index-free adjacency costs O(edges-visited). **Specific edge labels** prune early. Break **supernodes** with intermediate/bucket nodes; move hot attributes off the hub. Model a value as an **edge** when you traverse it, a **property** when you won't.

### Runtime writes & Neptune Analytics
Live writes: batch `UNWIND` + `mergeV()`/`mergeE()` upserts (parameterized), single writer. **Neptune Analytics** loads via `CALL neptune.load({source,region,format,concurrency,failOnError})` using the **caller's IAM creds** (no `iamRoleArn`) and adds `parquet` (`columnar`); ~2.5 GB/request per 128 m-NCU (scales ~linearly). Reloading the same edge file duplicates edges.

Deep dive: lore/deep/neptune.md#performance; lore/deep/databases.md#{connection-pooling,resilience-and-observability}

### Sources
AWS docs (docs.aws.amazon.com): neptune/latest/userguide/{bulk-load, bulk-load-tutorial-format-gremlin, bulk-load-tutorial-format-opencypher, load-api-reference-load, bulk-load-optimize}.html; neptune-analytics/latest/userguide/batch-load.html

## Performance <a id="performance"></a>

By impact; profile before/after. Managed (auto-updates) — verify limits. openCypher **always** runs on DFE; Gremlin and SPARQL use DFE only when opted in (§2).

### 0. Measure first
- DO EXPLAIN/PROFILE nontrivial. openCypher: `explain=dynamic|details` on `/openCypher` (`dynamic` runs → per-op `Units In/Out`, `Ratio`, `Time (ms)`; `details` adds `patternEstimate`; read-only). Gremlin: `/gremlin/profile` (`profile.indexOps=true`)/`/gremlin/explain` — per-`PatternNode` `estimatedCardinality`, index-ops, no-edge-label reverse warns.
- DON'T tune blind: huge `Units In` at a scan, or estimate ≫ actual ⇒ bad anchor/stale stats.
- DO watch CW: `BufferCacheHitRatio` (<99.9% ⇒ scale up), `MainRequestQueuePendingRequests` (throttling), `NumIndexReadsPerSec` (scan-heavy), `NCUUtilization` (Serverless). lore/deep/databases.md#resilience-and-observability.

### 1. Anchor + prune (biggest win)
- DO anchor traversals on a selective auto-indexed key — direct id (`g.V(id)`) fastest, else indexable property lookup. Bare `g.V()`/`MATCH (n)` = full scan; index-free adjacency pays only post-anchor.
- DO name edge labels + direction (`out('KNOWS')`, not `both()`) to prune; bound var-length paths (`times()`/limit); avoid disconnected patterns (Cartesian). lore/deep/neptune.md#query-languages-gremlin-opencypher-sparql.

### 2. Keep DFE stats fresh; opt in
- DO leave DFE stats auto-gen on (regen at >10% change or >10 days) — stale/absent stats ⇒ poor plans. Check `/propertygraph/statistics` (or `/rdf`); `mode=refresh` after bulk load; watch `StatsNumStatementsScanned`. Disabled on `T3`/`T4g`.
- DO opt Gremlin/SPARQL into DFE for analytic/large-fan-out: per-query `useDFE` hint (Gremlin `g.withSideEffect('Neptune#useDFE', true)`), or `neptune_dfe_query_engine=enabled` for all (default `viaQueryHint`).

### 3. Parameterize + cache hot reads
- DO parameterize for plan-cache reuse + injection safety; never string-concat.
- DO cache repeated identical reads: Gremlin `Neptune#enableResultCache`/`enableResultCacheWithTTL` (secs); re-run hits, clear via `invalidateResultCache`. Many-value/literal reads: **lookup cache** (`R5d` NVMe) cuts latency; not on Serverless.

### 4. Model around supernodes; hints last
- DO break supernodes (high-degree hubs) with intermediate/bucket nodes, dedicated edge types, or hot attrs off the hub — dominate traversal cost. lore/deep/neptune.md#data-loading-and-modeling.
- DO use hints only post-profiling: `Neptune#repeatMode` `DFS` (deep single-path vs default `BFS`) and `Neptune#noReordering`.

### 5. Batch writes; scale the right thing
- DO batch writes in one request: openCypher `UNWIND $rows AS row MERGE (...)`; Gremlin `g.inject(rows).unfold()...mergeV/mergeE`. Bulk-load large sets (never per-element loops). Single writer. lore/deep/databases.md#connection-pooling.
- DO route reads to replicas (writes→writer), reuse pooled conns. If `BufferCacheHitRatio` low or `UndoLogListSize` grows, upsize writer; Serverless (≤128 NCU/256 GB, 1 NCU=2 GiB) for spikes.

### Sources
- docs.aws.amazon.com/neptune/latest/userguide/ — oc-explain, gremlin-profile, dfe-statistics, parameters, useDFE-hint, results-cache, lookup-cache, cw-metrics, serverless
