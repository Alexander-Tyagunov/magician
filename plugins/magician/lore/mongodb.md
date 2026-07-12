# MongoDB — core digest
Version: 8.0 Major/LTS (Rapid Release 8.3 latest); span 7.0/8.0. Multi-doc ACID txns since 4.0 (replica set)/4.2 (sharded) — design to avoid them. Complements lore/mongoose (ODM).

DO model for the query, not normalization: embed bounded 1:1/1:few, reference large/unbounded; 16MB doc cap, no unbounded arrays.
DO pick a shard key: even spread + high cardinality; monotonic/low-card = hot chunk that caps throughput.
DO index every hot query, compound keys Equality-Sort-Range (ESR); prefer covered queries; explain: IXSCAN not COLLSCAN/SORT.
DO set concerns: `w:"majority"`+`readConcern:"majority"` or causal sessions for read-your-writes; single-doc writes are atomic.
DO batch with bulkWrite; page via range/`_id` (not skip()); project to cut payload.

DON'T use transactions as a schema crutch — costlier than single-doc; embed instead.
DON'T leave critical data on `w:1`/`readConcern:"local"` — may read uncommitted/rolled-back.
DON'T run unindexed queries or `$lookup`-heavy pipelines at scale; no cheap server JOINs.

Deep dive when writing non-trivial MongoDB — read lore/mongodb/{schema-design,indexes-and-query,aggregation-pipeline,transactions-and-consistency,performance}.md

## Sources
mongodb.com/docs/manual/{release-notes/8.0,data-modeling,core/indexes,core/sharding-choose-a-shard-key,core/transactions,read-isolation-consistency-recency} (2026-07)
