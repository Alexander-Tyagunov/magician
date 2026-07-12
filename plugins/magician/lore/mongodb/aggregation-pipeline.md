# MongoDB — Aggregation Pipeline

Version span 6.0/7.0/8.0 (8.0 = current LTS/major, 8.3 = latest rapid release; `$rankFusion` needs 8.0+). Ordered stages, each feeding the next. `db.coll.aggregate([...])` returns a **cursor**, never mutating data unless it ends in `$out`/`$merge`. NoSQL physics: unfiltered work is paid per doc.

## Filter and index at the front
Only `$match`/`$sort` at the **start** hit a collection index — `$match` only as the first stage, `$sort` only if no `$project`/`$unwind`/`$group` precedes it. `$match`+`$sort` at the head collapses to an indexed query+sort — order the index Equality→Sort→Range (ESR).
DO lead with `$match` to cut the set, then `$sort`, then `$limit`. Verify via `explain("executionStats")` — want `IXSCAN`, `totalKeysExamined≈nReturned`, no `COLLSCAN`/in-memory `SORT`.
DON'T front-load `$project` to "trim fields" — pushdown is automatic, and a leading one can *block* an index on a later `$sort`. Shape output with `$project`/`$unset` **last**.

## Let the optimizer coalesce
`$sort`+`$limit` (no count-changing stage between) fuses into a top-N sort keeping N in memory — even with `allowDiskUse`. `$limit`+`$limit`→min; `$skip`+`$skip`→sum. `$lookup`+`$unwind` on its `as` field coalesces, no huge array. DON'T deep-paginate with `$skip` (scans skipped docs); page an indexed range (`_id`/sort-key) cursor.

## Memory: 100MB per stage, spill or die
Blocking stages — `$group`, `$sort` (when not index-backed), `$bucket`, `$bucketAuto`, `$sortByCount`, `$setWindowFields` — buffer input, capped **100MB RAM**. Since 6.0 `allowDiskUseByDefault` (default true) spills them to disk; `allowDiskUse:false` forbids, `true` forces when off. `$search` runs out-of-process, unbound. `usedDisk` in log/profiler flags a spill — cue to add an index or leading `$match`/`$limit`.

## Result limits
Each **returned** doc obeys the 16MB BSON cap (else error); intermediate docs may exceed it mid-pipeline. Batches stream, so the full result set can far exceed 16MB. Max 1000 stages.

## $lookup — the join is not free
Left outer join within one db: equality on `localField`/`foreignField`, matches land in the `as` array (empty on no match). Reads the foreign collection **per input doc** — index `foreignField` or it's slow. Use `let`+`pipeline` for correlated/non-equality joins (inner `$match` needs `$expr`; outer vars are `$$var`). `$expr` uses a foreign index only against a constant, not multikey/partial/sparse. Sharded `from` since 5.1; `$lookup` in a sharded-collection txn since 8.0. No `$out`/`$merge` in the sub-pipeline. Lookup-heavy pipelines signal over-normalization — embed data read together.

## Materialize instead of recomputing
For heavy repeated aggregations, precompute with `$merge` (incremental upsert/merge into a collection, may target another db) or `$out` (replaces the target). Both are last-only, once — trade storage + recompute for cheap reads. `$facet` runs independent sub-pipelines in one pass (none can use the leading-stage index); `$setWindowFields` (5.0) gives running totals/ranks, no self-join; `$unwind` explodes arrays — set `preserveNullAndEmptyArrays: true` to keep no-array docs. For a consistent multi-collection view, use a `snapshot` txn.

## Sources
mongodb.com/docs/manual/core/aggregation-pipeline · /aggregation-pipeline-limits · /aggregation-pipeline-optimization · /reference/operator/aggregation/lookup · /reference/operator/aggregation/rankFusion (2026-07)
