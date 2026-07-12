# Amazon Neptune — Performance

By impact; profile before/after. Managed (auto-updates) — verify limits. openCypher **always** runs on DFE; Gremlin and SPARQL use DFE only when opted in (§2).

## 0. Measure first
- DO EXPLAIN/PROFILE nontrivial. openCypher: `explain=dynamic|details` on `/openCypher` (`dynamic` runs → per-op `Units In/Out`, `Ratio`, `Time (ms)`; `details` adds `patternEstimate`; read-only). Gremlin: `/gremlin/profile` (`profile.indexOps=true`)/`/gremlin/explain` — per-`PatternNode` `estimatedCardinality`, index-ops, no-edge-label reverse warns.
- DON'T tune blind: huge `Units In` at a scan, or estimate ≫ actual ⇒ bad anchor/stale stats.
- DO watch CW: `BufferCacheHitRatio` (<99.9% ⇒ scale up), `MainRequestQueuePendingRequests` (throttling), `NumIndexReadsPerSec` (scan-heavy), `NCUUtilization` (Serverless). lore/databases/resilience-and-observability.md.

## 1. Anchor + prune (biggest win)
- DO anchor traversals on a selective auto-indexed key — direct id (`g.V(id)`) fastest, else indexable property lookup. Bare `g.V()`/`MATCH (n)` = full scan; index-free adjacency pays only post-anchor.
- DO name edge labels + direction (`out('KNOWS')`, not `both()`) to prune; bound var-length paths (`times()`/limit); avoid disconnected patterns (Cartesian). lore/neptune/query-languages-gremlin-opencypher-sparql.md.

## 2. Keep DFE stats fresh; opt in
- DO leave DFE stats auto-gen on (regen at >10% change or >10 days) — stale/absent stats ⇒ poor plans. Check `/propertygraph/statistics` (or `/rdf`); `mode=refresh` after bulk load; watch `StatsNumStatementsScanned`. Disabled on `T3`/`T4g`.
- DO opt Gremlin/SPARQL into DFE for analytic/large-fan-out: per-query `useDFE` hint (Gremlin `g.withSideEffect('Neptune#useDFE', true)`), or `neptune_dfe_query_engine=enabled` for all (default `viaQueryHint`).

## 3. Parameterize + cache hot reads
- DO parameterize for plan-cache reuse + injection safety; never string-concat.
- DO cache repeated identical reads: Gremlin `Neptune#enableResultCache`/`enableResultCacheWithTTL` (secs); re-run hits, clear via `invalidateResultCache`. Many-value/literal reads: **lookup cache** (`R5d` NVMe) cuts latency; not on Serverless.

## 4. Model around supernodes; hints last
- DO break supernodes (high-degree hubs) with intermediate/bucket nodes, dedicated edge types, or hot attrs off the hub — dominate traversal cost. lore/neptune/data-loading-and-modeling.md.
- DO use hints only post-profiling: `Neptune#repeatMode` `DFS` (deep single-path vs default `BFS`) and `Neptune#noReordering`.

## 5. Batch writes; scale the right thing
- DO batch writes in one request: openCypher `UNWIND $rows AS row MERGE (...)`; Gremlin `g.inject(rows).unfold()...mergeV/mergeE`. Bulk-load large sets (never per-element loops). Single writer. lore/databases/connection-pooling.md.
- DO route reads to replicas (writes→writer), reuse pooled conns. If `BufferCacheHitRatio` low or `UndoLogListSize` grows, upsize writer; Serverless (≤128 NCU/256 GB, 1 NCU=2 GiB) for spikes.

## Sources
- docs.aws.amazon.com/neptune/latest/userguide/ — oc-explain, gremlin-profile, dfe-statistics, parameters, useDFE-hint, results-cache, lookup-cache, cw-metrics, serverless
