# Apache Cassandra — Performance

Span **3.x / 4.x / 5.0** (GA **5.0.8**; 4.1/4.0 maintained). Write-optimized LSM (no read-before-write); **reads are the cost center** — no release fixes a bad partition key. Measure first.

## Prioritized levers (highest impact first)

1. **Partition key is the #1 lever** — fixes placement and per-request node count. Pick high-cardinality keys that spread evenly; a hot/low-cardinality key (status, day) caps throughput. Keep partitions bounded — docs target **< 100 MB and < 100k rows/cells**; bucket before they grow. See lore/cassandra/data-modeling-and-partitions.md.
2. **One table per query; denormalize.** No server-side JOIN. Every read should hit **one partition on one node** — duplicate into query-specific tables. Multi-partition `IN`/scatter reads are latency traps.
3. **Read by partition key, never by filtering.** A non-key `WHERE` / `ALLOW FILTERING` is a cluster-wide scan (never in prod). Serve secondary access via a denorm table or **SAI** (5.0: text trie, numeric kd-tree, multi-index) — but SAI is still a token-ordered multi-node range read (adaptive concurrency), so it complements, never replaces, partition-key access. See lore/cassandra/queries-and-secondary-indexes.md.
4. **Right-size consistency per query.** Tunable: prefer **LOCAL_QUORUM** (multi-DC: stays in-DC); `R+W>RF` gives read-your-writes. Don't default to QUORUM/ALL (cross-DC hops) or route reads through **LWT/Paxos** — multiple Paxos round trips (non-negligible cost), reserve for invariants. See lore/cassandra/consistency-and-replication.md.
5. **Match compaction to the workload.** 5.0 **UCS** (recommended; scaling param tunes read/write amp, default T4) generalizes tiered/leveled; pre-5.0 default **STCS** (space-cheap, higher read amp), **LCS** for read/update-heavy, **TWCS** for time-series + TTL. See lore/cassandra/compaction-and-storage.md.
6. **Batch for atomicity, not throughput.** A multi-partition `BATCH` funnels through the batchlog and overloads the coordinator (`batch_size_warn` 5 KiB / fail 50 KiB). Batch only same-partition writes; else async concurrent single writes (token-aware driver).

## Top anti-patterns

- **Hot / unbounded partitions, `ALLOW FILTERING`, large multi-partition batches** — see levers 1/3/6.
- **Tombstone overload** — deletes, TTL expiry, collection overwrites, `null` writes emit tombstones reads scan past (`tombstone_warn_threshold` 1000; `tombstone_failure_threshold` 100000 aborts read). Queue patterns are the classic trap; `gc_grace_seconds` 864000 (10 d) delays reclaim.
- **Read-path LWT / legacy 2i** — Paxos contention, per-node scatter-gather; reserve LWT for real CAS, prefer SAI over 2i.

## How to measure

- **`nodetool tablestats`/`tablehistograms`** — p99 latency, SSTables-per-read, partition size, tombstones-per-read; **`tpstats`** — dropped mutations, pending threads (`concurrent_reads`/`writes` 32).
- **`TRACING ON`**, **`proxyhistograms`**, **`compactionstats`** — coordinator↔replica hops, tombstone scans, coordinator latency, compaction backlog.
- Pooling + observability: lore/databases/{connection-pooling,resilience-and-observability}.md.
- **ScyllaDB** is CQL-compatible (shard-per-core); same modeling rules, verify parity.

## Sources
cassandra.apache.org/doc/latest/cassandra/: developing/data-modeling/intro.html; architecture/dynamo.html; managing/operating/compaction/{ucs,tombstones}.html; developing/cql/indexing/sai/sai-concepts.html
