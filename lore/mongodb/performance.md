# MongoDB — Performance

Spans **6.0 / 7.0 / 8.0** (stable 8.3; 8.0 LTS — no release rescues a bad key or `COLLSCAN`). **Measure first.**

## Prioritized levers (highest impact first)

1. **Keep the working set in RAM** — biggest lever. WiredTiger cache = `max(50% of (RAM−1GB), 256MB)` (+ a compressed FS-cache copy). If the working set doesn't fit, misses hit disk. Don't raise `wiredTigerCacheSizeGB` (starves the FS cache); scale RAM or shard.
2. **Index the access pattern; aim for covered queries.** One compound index per query shape, ordered **ESR** (Equality, Sort, Range). Covered = index-only (project indexed fields, `_id:0`). See `lore/mongodb/indexes-and-query.md`, `lore/databases/indexing-and-query-plans.md`.
3. **Design the shard/`_id` key for even spread.** A hot partition caps throughput. Avoid monotonic keys (timestamp, ObjectId prefix); use hashed or high-cardinality compound. See `lore/mongodb/schema-design.md`.
4. **Model for the query, not normalization.** Embed what you read together; reference only large/unbounded data. `$lookup` is a nested loop — index the foreign field; its `EQ_LOOKUP` slot engine (6.0+) needs the `from` unsharded, not a view, and a plain equality join. See `lore/mongodb/schema-design.md`.
5. **Batch writes; never chatter per-item.** `bulkWrite` (8.0: multi-collection) with `ordered:false`. Mutate server-side (`$inc`/`$set`/`$push`), never read-modify-write a doc.
6. **Right-size consistency.** `w:"majority"` in 8.0 acks once the oplog entry is *written*. Offload reads to secondaries (`secondaryPreferred`; causal session for read-your-writes). Reserve multi-doc txns for true invariants. See `lore/mongodb/transactions-and-consistency.md`.

## Aggregation

`$match`/`$sort` first so an index applies; put `$project`/`$addFields` **last**. Let `$sort`+`$limit` coalesce. Blocking stages (`$group`, indexless `$sort`, `$bucket`, `$setWindowFields`) cap at **100 MB**; since 6.0 `allowDiskUseByDefault:true` spills to temp files (watch `usedDisk`). See `lore/mongodb/aggregation-pipeline.md`.

## How to measure

- **`explain("executionStats")`** — want `IXSCAN`/`DISTINCT_SCAN`, not `COLLSCAN`; `totalKeysExamined ≈ nReturned` (ratio ≫1 = weak index); `totalDocsExamined:0` confirms covered.
- **Profiler** — 8.0 `workingMillis` excludes lock/flow waits.
- **`serverStatus`** — `queues.execution` (exec tickets; was `wiredTiger.concurrentTransactions` pre-8.0, dynamic since 7.0 — watch **queued**), `globalLock.currentQueue`, `connections`, cache eviction %.
- Pooling + observability: `lore/databases/{connection-pooling,resilience-and-observability}.md`. ODM pitfalls: `lore/mongoose`.

## Top anti-patterns

- **`COLLSCAN` on a hot path** — `$ne`/`$nin`/negation, unanchored `$regex`, `$where`/`$expr`. Keep selective + indexed.
- **`skip(n)` pagination** — scans+discards n docs (O(n)); use keyset (`_id > lastId`).
- **Unbounded arrays / ever-growing docs** — near the 16 MB BSON cap; churn + bloat. Cap arrays or split to a child collection.
- **Over-indexing** — each index costs a write + eats cache; drop unused (`$indexStats`).
- **N+1 round trips** — replace client loops with `bulkWrite`, `$in`, or one `$lookup`.

## Sources
- https://www.mongodb.com/docs/manual/administration/analyzing-mongodb-performance/ · core/query-optimization/ · core/aggregation-pipeline-optimization/
- https://www.mongodb.com/docs/manual/core/wiredtiger/ · release-notes/8.0/ · reference/command/serverStatus/
