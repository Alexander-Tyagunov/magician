# MongoDB — deep dive

> On-demand companion to `lore/mongodb.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Schema design](#schema-design) · [Indexes & query](#indexes-and-query) · [Aggregation Pipeline](#aggregation-pipeline) · [Transactions and Consistency](#transactions-and-consistency) · [Performance](#performance)

## Schema design <a id="schema-design"></a>

Data modeling (engine layer). Manual 8.3; 8.0 GA, span 6.0/7.0/8.0. Mongoose subdocs/`ref`/`populate()`: see lore/mongoose.md.

### Model for the query, not the entity

**Data accessed together is stored together.** No server-side JOINs — `$lookup` is an aggregation stage, not a cheap join. List access patterns FIRST, then shape docs so a screen is one/few single-collection reads.

DO
- Embed the "many" side when loaded with the parent, bounded, owned (1:1, 1:few) — one read, no join.
- Reference (store `_id`, resolve via 2nd query or `$lookup`) when child data is large, shared, unbounded, or queried alone.
- Denormalize read-hot fields you'd otherwise `$lookup` — **Extended Reference** — accepting fan-out updates on change.
- Exploit polymorphism: a collection needn't have uniform fields/types; group docs read together (**Single Collection**, indexed `type`) vs tiny ones.

DON'T
- Don't normalize by reflex — a 3NF collection graph makes every page N `$lookup`s.
- Don't split into a collection per type/tenant when docs are read together (Reduce Number of Collections).

### Single-document atomicity is the design lever

A write to a **single document is always atomic** (all fields, embedded subdocs) — *why* you embed: relationships in one doc need no transaction. Multi-doc ACID txns exist (replica sets 4.0, sharded 4.2) but MongoDB says they're "not a replacement for effective schema design".

DO
- Keep an atomic invariant inside ONE document (order + line items).
- Mutate in place with `$inc`/`$push`/`$pull`/`$addToSet` + array filters; `findOneAndUpdate` for read-modify-write.

DON'T
- Don't make a common op *need* a transaction. If unavoidable: 60s default cap (`transactionLifetimeLimitSeconds`); a txn now spans multiple oplog entries (16MB total-txn cap dropped in 4.2; each *entry* still ≤16MB BSON); callback API auto-retries `TransientTransactionError`.

### Hard limits shape the schema

- **16MB max BSON document**; **100 levels** max nesting.
- **Unbounded arrays = #1 anti-pattern**: they blow the 16MB cap, degrade multikey indexes, and rewrite the whole doc on each push. Cap embedded arrays; if unbounded, reference a child collection or apply **Group Data** (bucket; fixed-size buckets).
- **Bloated documents** (large fields read on each hot query) waste cache — apply **Subset**: embed the top-N, archive the rest.

### Enforce shape; version; design `_id`

DO
- Add `$jsonSchema` validators (`bsonType`/`required`/`properties`/`enum`) via `validator` on `createCollection`/`collMod`; `title`/`description` surface in the descriptive error. Tune `validationLevel` (`strict`|`moderate`) + `validationAction` (`error`|`warn`).
- Stamp a `schemaVersion` field (**Document and Schema Versioning**) — migrate lazily on read, no big-bang.
- Precompute rollups at write (Handle Computed Values); archive cold data.
- Design `_id` deliberately (always-indexed PK): natural key or ObjectId; clustered collections key storage on `_id` for range scans.

DON'T
- Don't skip validation on a shared/prod collection — flexible schema silently accepts typos + wrong types.

Shard-key + index sizing/measurement: lore/deep/mongodb.md#performance, lore/deep/databases.md#indexing-and-query-plans.

### Sources
mongodb.com/docs/manual/ · data-modeling/{design-antipatterns,design-patterns} · core/{transactions,transactions-production-consideration,schema-validation}. Extended Reference & Subset: MongoDB *Building with Patterns* series.

## Indexes & query <a id="indexes-and-query"></a>

Index + planner behavior. Server **8.x** stable (8.0 GA; 8.3 latest rapid); 7.0/8.0 supported, 6.0 EOL (2025-07). ODM concerns (`lean`/`select`/sanitization) → lore/mongoose.md*.

No server-side JOIN — embed/denormalize (see schema-design); back **each** query with an index. Unindexed predicate = `COLLSCAN`; `_id` is the only auto index.

### Index types

- **Single / compound** `createIndex({a:1,b:-1})` — serves only a **left prefix** (`a`, then `a,b`), never `b` alone.
- **Multikey** — automatic on array fields; a compound index allows **at most one array-valued field per document**. Bounds loose (matches if *any* element does).
- **Wildcard** `{"$**":1}` (4.2+; compound 7.0+) — arbitrary keys; no substitute for targeted indexes.
- **Hashed** — even spread for sharding; equality only, no range/sort.
- **Geospatial** `2dsphere`; **text** `$text` — prefer Atlas/MongoDB Search for text.
- Properties: **TTL** (`expireAfterSeconds`, single date field), **unique**, **partial** (`partialFilterExpression`; prefer over **sparse**; `unique`+partial constrains only matching docs), **hidden** (4.4+, invisible), **collation** (case-insensitive `strength:1|2`).
- **Clustered collections** (5.3+) store docs `_id`-ordered → `CLUSTERED_IXSCAN`, no separate `_id` index.

### Compound order: ESR

Order keys **Equality → Sort → Range**. Equality (`$eq`, small `$in`) pins a value, keeping later keys sorted; sort is index-served only when equality covers all preceding keys (no blocking `SORT`); range (`$gt/$lt/$ne/$nin/$regex`) last — a range *before* sort forces an in-memory `SORT` (**ERS** if selective).

### Read the plan

`db.c.find(q).explain("executionStats")` (or `allPlansExecution`). Compare `nReturned` vs `totalDocsExamined` vs `totalKeysExamined` — ideal: all ≈ equal.
- `totalDocsExamined >> nReturned` → weak index; `COLLSCAN` on a big coll → missing index; `SORT` stage → not index-backed.
- **Covered query**: an `IXSCAN` with **no `FETCH`** — all fields indexed, projection returns only those (exclude `_id` unless indexed); `totalDocsExamined:0`, cheapest.
- `explain` bypasses the plan cache. Stages `IXSCAN/FETCH/COLLSCAN/SORT/IDHACK`, `OR` (`$or` union). SBE (5.1+, explainVersion 2) nests `queryPlan`/`slotBasedPlan`; **EXPRESS_\*** (8.0+) fast-path simple `_id`/single-index ops.

### Idioms & gotchas

- **Paginate by range**, not `skip()` (walks skipped): `find({_id:{$gt:last}}).sort({_id:1}).limit(n)` — stable, O(page).
- **Project** to cut payload + enable covered reads: `find(q,{a:1,_id:0})`.
- **Sargable**: don't wrap the indexed field (`$expr` math, unanchored `$regex:/x/`, `$where`) — kills index use.
- Build large indexes **rolling** per member (`background` is a no-op/ignored since hybrid builds in 4.2).
- Drop dead indexes via `$indexStats` — each index taxes writes + RAM (index + hot data should fit memory).
- Consistency: reads default to `readConcern:"local"`; use `"majority"`/`"snapshot"` + causal-consistent sessions to see prior writes (see transactions).

See lore/deep/mongodb.md#performance and lore/deep/databases.md#indexing-and-query-plans.

### Sources

- Indexing & ESR: https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/
- Index types & properties: https://www.mongodb.com/docs/manual/core/indexes/index-types/ , index-properties/
- Explain & analyze plan: https://www.mongodb.com/docs/manual/reference/explain-results/ , tutorial/analyze-query-plan/

## Aggregation Pipeline <a id="aggregation-pipeline"></a>

Version span 6.0/7.0/8.0 (8.0 = current LTS/major, 8.3 = latest rapid release; `$rankFusion` needs 8.0+). Ordered stages, each feeding the next. `db.coll.aggregate([...])` returns a **cursor**, never mutating data unless it ends in `$out`/`$merge`. NoSQL physics: unfiltered work is paid per doc.

### Filter and index at the front
Only `$match`/`$sort` at the **start** hit a collection index — `$match` only as the first stage, `$sort` only if no `$project`/`$unwind`/`$group` precedes it. `$match`+`$sort` at the head collapses to an indexed query+sort — order the index Equality→Sort→Range (ESR).
DO lead with `$match` to cut the set, then `$sort`, then `$limit`. Verify via `explain("executionStats")` — want `IXSCAN`, `totalKeysExamined≈nReturned`, no `COLLSCAN`/in-memory `SORT`.
DON'T front-load `$project` to "trim fields" — pushdown is automatic, and a leading one can *block* an index on a later `$sort`. Shape output with `$project`/`$unset` **last**.

### Let the optimizer coalesce
`$sort`+`$limit` (no count-changing stage between) fuses into a top-N sort keeping N in memory — even with `allowDiskUse`. `$limit`+`$limit`→min; `$skip`+`$skip`→sum. `$lookup`+`$unwind` on its `as` field coalesces, no huge array. DON'T deep-paginate with `$skip` (scans skipped docs); page an indexed range (`_id`/sort-key) cursor.

### Memory: 100MB per stage, spill or die
Blocking stages — `$group`, `$sort` (when not index-backed), `$bucket`, `$bucketAuto`, `$sortByCount`, `$setWindowFields` — buffer input, capped **100MB RAM**. Since 6.0 `allowDiskUseByDefault` (default true) spills them to disk; `allowDiskUse:false` forbids, `true` forces when off. `$search` runs out-of-process, unbound. `usedDisk` in log/profiler flags a spill — cue to add an index or leading `$match`/`$limit`.

### Result limits
Each **returned** doc obeys the 16MB BSON cap (else error); intermediate docs may exceed it mid-pipeline. Batches stream, so the full result set can far exceed 16MB. Max 1000 stages.

### $lookup — the join is not free
Left outer join within one db: equality on `localField`/`foreignField`, matches land in the `as` array (empty on no match). Reads the foreign collection **per input doc** — index `foreignField` or it's slow. Use `let`+`pipeline` for correlated/non-equality joins (inner `$match` needs `$expr`; outer vars are `$$var`). `$expr` uses a foreign index only against a constant, not multikey/partial/sparse. Sharded `from` since 5.1; `$lookup` in a sharded-collection txn since 8.0. No `$out`/`$merge` in the sub-pipeline. Lookup-heavy pipelines signal over-normalization — embed data read together.

### Materialize instead of recomputing
For heavy repeated aggregations, precompute with `$merge` (incremental upsert/merge into a collection, may target another db) or `$out` (replaces the target). Both are last-only, once — trade storage + recompute for cheap reads. `$facet` runs independent sub-pipelines in one pass (none can use the leading-stage index); `$setWindowFields` (5.0) gives running totals/ranks, no self-join; `$unwind` explodes arrays — set `preserveNullAndEmptyArrays: true` to keep no-array docs. For a consistent multi-collection view, use a `snapshot` txn.

### Sources
mongodb.com/docs/manual/core/aggregation-pipeline · /aggregation-pipeline-limits · /aggregation-pipeline-optimization · /reference/operator/aggregation/lookup · /reference/operator/aggregation/rankFusion (2026-07)

## Transactions and Consistency <a id="transactions-and-consistency"></a>

Version: 8.0 current. Multi-doc ACID txns since **4.0** (replica set) / **4.2** (sharded); standalone `mongod` can't (no oplog). Default reads are **read-uncommitted**; single-**doc** writes are always atomic.

### Model to AVOID needing transactions
- **A single-doc write is atomic** — no reader sees a half-updated doc; embed related data so one `updateOne`/`$inc`/`$push` mutates the whole invariant.
- A distributed txn costs far more than a single-doc write; use one only for true cross-doc invariants (transfer, double-entry).
- `updateMany`/multi-doc ops are **atomic per document, not as a whole** — concurrent writers interleave, so a reader may see some docs updated, not others.

### Read concern
- `local` (default): freshest on the node, **can roll back** on failover. `available` (sharded): low-latency, may return orphans.
- `majority`: acknowledged by a majority — **durable, never rolled back**.
- `linearizable`: reflects all majority writes before it began (single doc, primary, pair `w:"majority"`).
- `snapshot`: majority-committed point-in-time; in a sharded txn **synchronized across shards**.

### Write concern
- Default since 5.0 is `w:"majority"`; `j:true` forces a journal ack. `w:1` acks the primary only — **a failover can roll it back**. `w:0` is unacknowledged (no operationTime, breaks causal ordering).

### Transaction semantics & scope
- Use the **callback API** (`session.withTransaction`) — retries `TransientTransactionError`/`UnknownTransactionCommitResult`. Each op must carry the session.
- Txn-level read/write concern wins; **per-op write concern in a txn is an error**. Commit with `w:"majority"` or the txn can roll back. Txn reads use read preference **primary**.
- Snapshot isolation covers txn reads; changes invisible outside until commit. One open txn per session; ending it aborts. Can't write capped/`config`/`admin`/`local`/`system.*`; collection/index creation needs read concern `local`.

### Causal consistency (sessions)
A **causally consistent session** gives read-your-writes, monotonic reads/writes, writes-follow-reads — **required when reading a secondary** after a write. Needs `majority` read **and** write concern, one thread per session. Advance cluster time to chain sessions.

### Production limits & write conflicts
- `transactionLifetimeLimitSeconds` **default 60s**; a sweeper aborts older txns. Keep short; split large work.
- Each **oplog entry** obeys the 16MB BSON cap; a txn spans many (no single 16MB total since 4.2), but a huge one strains WiredTiger cache → **write conflict** abort, or `TransactionTooLargeForCache` if it never fits.
- **First-writer-wins:** an outside write that modifies a doc **before** the txn does aborts the txn (write conflict); if the txn holds the lock first, an outside write waits until the txn ends. `maxTransactionLockRequestTimeoutMillis` (**5ms** default) = how long the *txn* waits to acquire a held lock before aborting. Chunk migration/DDL (`createIndex`, `renameCollection`) block/abort in-flight txns.

### DON'T
- Don't use txns as a schema crutch, run them long, or touch thousands of docs; don't assume `updateMany` is all-or-nothing.
- Don't set per-op write concern, trust `w:1`/`local` across a failover, or read a txn from a secondary.

### Sources
mongodb.com/docs/manual/core/{transactions,transactions-production-consideration,read-isolation-consistency-recency}/, /reference/{read-concern,write-concern}/

## Performance <a id="performance"></a>

Spans **6.0 / 7.0 / 8.0** (stable 8.3; 8.0 LTS — no release rescues a bad key or `COLLSCAN`). **Measure first.**

### Prioritized levers (highest impact first)

1. **Keep the working set in RAM** — biggest lever. WiredTiger cache = `max(50% of (RAM−1GB), 256MB)` (+ a compressed FS-cache copy). If the working set doesn't fit, misses hit disk. Don't raise `wiredTigerCacheSizeGB` (starves the FS cache); scale RAM or shard.
2. **Index the access pattern; aim for covered queries.** One compound index per query shape, ordered **ESR** (Equality, Sort, Range). Covered = index-only (project indexed fields, `_id:0`). See `lore/deep/mongodb.md#indexes-and-query`, `lore/deep/databases.md#indexing-and-query-plans`.
3. **Design the shard/`_id` key for even spread.** A hot partition caps throughput. Avoid monotonic keys (timestamp, ObjectId prefix); use hashed or high-cardinality compound. See `lore/deep/mongodb.md#schema-design`.
4. **Model for the query, not normalization.** Embed what you read together; reference only large/unbounded data. `$lookup` is a nested loop — index the foreign field; its `EQ_LOOKUP` slot engine (6.0+) needs the `from` unsharded, not a view, and a plain equality join. See `lore/deep/mongodb.md#schema-design`.
5. **Batch writes; never chatter per-item.** `bulkWrite` (8.0: multi-collection) with `ordered:false`. Mutate server-side (`$inc`/`$set`/`$push`), never read-modify-write a doc.
6. **Right-size consistency.** `w:"majority"` in 8.0 acks once the oplog entry is *written*. Offload reads to secondaries (`secondaryPreferred`; causal session for read-your-writes). Reserve multi-doc txns for true invariants. See `lore/deep/mongodb.md#transactions-and-consistency`.

### Aggregation

`$match`/`$sort` first so an index applies; put `$project`/`$addFields` **last**. Let `$sort`+`$limit` coalesce. Blocking stages (`$group`, indexless `$sort`, `$bucket`, `$setWindowFields`) cap at **100 MB**; since 6.0 `allowDiskUseByDefault:true` spills to temp files (watch `usedDisk`). See `lore/deep/mongodb.md#aggregation-pipeline`.

### How to measure

- **`explain("executionStats")`** — want `IXSCAN`/`DISTINCT_SCAN`, not `COLLSCAN`; `totalKeysExamined ≈ nReturned` (ratio ≫1 = weak index); `totalDocsExamined:0` confirms covered.
- **Profiler** — 8.0 `workingMillis` excludes lock/flow waits.
- **`serverStatus`** — `queues.execution` (exec tickets; was `wiredTiger.concurrentTransactions` pre-8.0, dynamic since 7.0 — watch **queued**), `globalLock.currentQueue`, `connections`, cache eviction %.
- Pooling + observability: `lore/deep/databases.md#{connection-pooling,resilience-and-observability}`. ODM pitfalls: `lore/mongoose.md`.

### Top anti-patterns

- **`COLLSCAN` on a hot path** — `$ne`/`$nin`/negation, unanchored `$regex`, `$where`/`$expr`. Keep selective + indexed.
- **`skip(n)` pagination** — scans+discards n docs (O(n)); use keyset (`_id > lastId`).
- **Unbounded arrays / ever-growing docs** — near the 16 MB BSON cap; churn + bloat. Cap arrays or split to a child collection.
- **Over-indexing** — each index costs a write + eats cache; drop unused (`$indexStats`).
- **N+1 round trips** — replace client loops with `bulkWrite`, `$in`, or one `$lookup`.

### Sources
- https://www.mongodb.com/docs/manual/administration/analyzing-mongodb-performance/ · core/query-optimization/ · core/aggregation-pipeline-optimization/
- https://www.mongodb.com/docs/manual/core/wiredtiger/ · release-notes/8.0/ · reference/command/serverStatus/
