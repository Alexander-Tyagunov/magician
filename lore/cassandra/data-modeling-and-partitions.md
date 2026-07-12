# Apache Cassandra — Data modeling & partitions

Spans 3.x/4.x/5.0 (5.0 GA Sep 2024). Wide-column store: rows group into partitions by token = Murmur3 hash of the partition key. Model QUERY-FIRST — no joins, no foreign keys/referential integrity, `ORDER BY` only on clustering order. Schema follows access patterns, not normal forms.

## Partition & clustering keys — the primary lever
- PRIMARY KEY = partition key + clustering columns: `PRIMARY KEY ((tenant, day), ts, id)`. First component (parenthesized if composite) = partition key → owning node/replicas; the rest cluster (sort) rows within it.
- DO pick a HIGH-CARDINALITY partition key spreading writes/reads evenly. Low-cardinality keys (`status`, a bare date) create HOT PARTITIONS that cap throughput regardless of nodes.
- DON'T use monotonic keys (timestamps, sequential ids) — they hot-spot one token range.
- Clustering columns fix sort order (`WITH CLUSTERING ORDER BY (ts DESC)`), enabling fast in-partition range slices; order only by those columns/direction.
- Static columns (`Ns`): one value shared across the partition.

## Bounding partition size
- Keep partitions well under ~100k rows / ~100MB; hard limit is 2 billion cells, but pain arrives far earlier. Cells ≈ `Nv = Nr(Nc − Npk − Ns) + Ns`.
- DO bound growth via BUCKETING (add a `month` bucket to the key) or a SHARD column (`((id, shard))`, scatter-gather N shards on read). Size buckets from the query — over-bucketing multiplies round-trips.

## Reads follow the model
- Make each query a SINGLE-PARTITION point/range read; denormalize one query table per access path, synced on write.
- DON'T `ALLOW FILTERING` in production — unbounded partition/node scan. Avoid large multi-partition `IN (...)` — fans out across coordinators.
- DON'T lean on Materialized Views — EXPERIMENTAL since 4.0; a hand-maintained table is safer.

## SAI (5.0) — secondary indexes done right
- `CREATE CUSTOM INDEX ON t(col) USING 'sai'` — one index per column, equality AND numeric range (text via analyzers); supersedes 2i/SASI at far lower write/space cost. Not needed on a single-column partition key (already indexed).
- SAI is LOCAL (per-node): an unrestricted query scatter-gathers across replicas. Pair predicates with a partition restriction; reserve SAI for low-frequency filters — a purpose-built table wins the hot path.

## Consistency & write-model gotchas
- Consistency TUNABLE per query (`ONE`/`LOCAL_QUORUM`/`QUORUM`/`ALL`); `R + W > RF` = read-your-writes. No cross-partition ACID.
- LWT (`IF NOT EXISTS`/`IF col=?`) is Paxos — multi-round, expensive; keep minimal, never in a tight loop.
- TOMBSTONES: deletes, TTL expiry, and inserted NULLs write tombstones that linger `gc_grace_seconds` (default 10 days). Queue patterns (write-then-delete) and range deletes breed them; scanning past `tombstone_failure_threshold` (default 100k) aborts the read. Model to APPEND, not churn.
- Collections (list/set/map) store one cell per element and read whole — keep small/bounded; never use an unbounded collection where a clustering key belongs.

ScyllaDB (CQL/data-model-compatible, shard-per-core) inherits these rules.

See lore/cassandra/performance.md, lore/databases/indexing-and-query-plans.md for detail.

## Sources
- cassandra.apache.org/doc/latest/cassandra/developing/data-modeling/
- cassandra.apache.org/doc/latest/cassandra/developing/cql/indexing/sai/sai-overview.html
- cassandra.apache.org/_/blog.html (5.0 GA, Sep 2024)
