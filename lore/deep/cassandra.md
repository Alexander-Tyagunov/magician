# Apache Cassandra — deep dive

> On-demand companion to `lore/cassandra.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Data modeling & partitions](#data-modeling-and-partitions) · [Consistency & Replication](#consistency-and-replication) · [Queries & secondary indexes](#queries-and-secondary-indexes) · [Compaction & Storage](#compaction-and-storage) · [Performance](#performance)

## Data modeling & partitions <a id="data-modeling-and-partitions"></a>

Spans 3.x/4.x/5.0 (5.0 GA Sep 2024). Wide-column store: rows group into partitions by token = Murmur3 hash of the partition key. Model QUERY-FIRST — no joins, no foreign keys/referential integrity, `ORDER BY` only on clustering order. Schema follows access patterns, not normal forms.

### Partition & clustering keys — the primary lever
- PRIMARY KEY = partition key + clustering columns: `PRIMARY KEY ((tenant, day), ts, id)`. First component (parenthesized if composite) = partition key → owning node/replicas; the rest cluster (sort) rows within it.
- DO pick a HIGH-CARDINALITY partition key spreading writes/reads evenly. Low-cardinality keys (`status`, a bare date) create HOT PARTITIONS that cap throughput regardless of nodes.
- DON'T use monotonic keys (timestamps, sequential ids) — they hot-spot one token range.
- Clustering columns fix sort order (`WITH CLUSTERING ORDER BY (ts DESC)`), enabling fast in-partition range slices; order only by those columns/direction.
- Static columns (`Ns`): one value shared across the partition.

### Bounding partition size
- Keep partitions well under ~100k rows / ~100MB; hard limit is 2 billion cells, but pain arrives far earlier. Cells ≈ `Nv = Nr(Nc − Npk − Ns) + Ns`.
- DO bound growth via BUCKETING (add a `month` bucket to the key) or a SHARD column (`((id, shard))`, scatter-gather N shards on read). Size buckets from the query — over-bucketing multiplies round-trips.

### Reads follow the model
- Make each query a SINGLE-PARTITION point/range read; denormalize one query table per access path, synced on write.
- DON'T `ALLOW FILTERING` in production — unbounded partition/node scan. Avoid large multi-partition `IN (...)` — fans out across coordinators.
- DON'T lean on Materialized Views — EXPERIMENTAL since 4.0; a hand-maintained table is safer.

### SAI (5.0) — secondary indexes done right
- `CREATE CUSTOM INDEX ON t(col) USING 'sai'` — one index per column, equality AND numeric range (text via analyzers); supersedes 2i/SASI at far lower write/space cost. Not needed on a single-column partition key (already indexed).
- SAI is LOCAL (per-node): an unrestricted query scatter-gathers across replicas. Pair predicates with a partition restriction; reserve SAI for low-frequency filters — a purpose-built table wins the hot path.

### Consistency & write-model gotchas
- Consistency TUNABLE per query (`ONE`/`LOCAL_QUORUM`/`QUORUM`/`ALL`); `R + W > RF` = read-your-writes. No cross-partition ACID.
- LWT (`IF NOT EXISTS`/`IF col=?`) is Paxos — multi-round, expensive; keep minimal, never in a tight loop.
- TOMBSTONES: deletes, TTL expiry, and inserted NULLs write tombstones that linger `gc_grace_seconds` (default 10 days). Queue patterns (write-then-delete) and range deletes breed them; scanning past `tombstone_failure_threshold` (default 100k) aborts the read. Model to APPEND, not churn.
- Collections (list/set/map) store one cell per element and read whole — keep small/bounded; never use an unbounded collection where a clustering key belongs.

ScyllaDB (CQL/data-model-compatible, shard-per-core) inherits these rules.

See lore/deep/cassandra.md#performance, lore/deep/databases.md#indexing-and-query-plans for detail.

### Sources
- cassandra.apache.org/doc/latest/cassandra/developing/data-modeling/
- cassandra.apache.org/doc/latest/cassandra/developing/cql/indexing/sai/sai-overview.html
- cassandra.apache.org/_/blog.html (5.0 GA, Sep 2024)

## Consistency & Replication <a id="consistency-and-replication"></a>

Current stable **5.0** (GA); spans 3.x/4.x/5.0. Cassandra is AP-leaning: it favors Availability + Partition-tolerance and offers **tunable, per-operation consistency** — a Dynamo-style `R + W > RF` knob, not ACID. Guarantees are **per single partition**; no cross-partition transactions. ScyllaDB is wire/CQL-compatible and shares these semantics (version gates differ).

### Tunable consistency — set it per query, not per cluster
CL is chosen **per statement** (driver `ConsistencyLevel`), independently for reads and writes. For read-your-writes on `RF=3`: `QUORUM` write + `QUORUM` read (2+2>3 overlaps). Multi-DC: use **`LOCAL_QUORUM`** as the default — it stays in the local DC (no cross-DC latency) yet is strong *within* that DC. Levels: `ONE`/`TWO`/`THREE`, `QUORUM` (`n/2+1` over all replicas), `LOCAL_QUORUM`, `EACH_QUORUM` (writes only), `ALL`, `LOCAL_ONE`, `ANY` (write-only; a stored hint counts). Writes are **always sent to all replicas**; CL only sets how many acks the coordinator awaits. CL alone doesn't make stale replicas converge — schedule repair.

### Replication strategy & RF
DO use **`NetworkTopologyStrategy`** in every real cluster; set RF **per datacenter** (`{'class':'NetworkTopologyStrategy','dc1':3}`) — it places replicas across racks via the snitch. `SimpleStrategy` is DC/rack-blind — test only. RF = copies of each partition (distinct nodes). **Transient replication** is experimental (4.0+): it cuts storage but forbids LWT, logged batches, counters, and monotonic reads — avoid in prod.

### Conflict resolution: last-write-wins on timestamps
Every column mutation carries a timestamp; the highest wins (LWW). Clock skew silently drops writes or resurrects data — DO run NTP on every node. A `DELETE` writes a **tombstone**; DO run `nodetool repair` on **every** table within `gc_grace_seconds` (default **864000 = 10 days**), or a node that missed the delete "resurrects" the row after tombstones are compacted away.

### Anti-entropy: hints, read-repair, repair
Three converging mechanisms: **hinted handoff** (coordinator stores + replays a hint for a down replica, bounded by `max_hint_window`), **read repair** (fixes replicas hit during a read), and **anti-entropy repair** (`nodetool repair`, Merkle-tree comparison). DO prefer **incremental** or **sub-range** repair on large tables; a full repair on a huge dataset streams hard. Repair is the *only* guarantee everything converges — schedule it, don't lean on hints/read-repair.

### LWT & batches — narrow tools, not SQL transactions
**LWT** (`IF NOT EXISTS`, `IF EXISTS`, `IF col=...`) gives single-partition linearizable compare-and-set via **Paxos**, paired with `SERIAL`/`LOCAL_SERIAL` read CL. It costs extra round-trips — DON'T use it on hot paths or as a general lock. **Batches are for atomicity, not speed**: `LOGGED` (default) guarantees all-or-nothing via a batchlog but is slow across partitions; a single-partition LOGGED batch is auto-downgraded to UNLOGGED. `UNLOGGED` multi-partition batches can apply **partially** on failure. Isolation exists **only within one partition**. DON'T batch across partitions to "save round-trips" — it overloads the coordinator; batch only same-partition rows.

### Sources
- cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html (consistency levels, R+W>RF, NetworkTopologyStrategy/SimpleStrategy, transient replication, hints/read-repair/repair, Merkle trees, LWW)
- cassandra.apache.org/doc/latest/cassandra/architecture/guarantees.html (eventual consistency, per-table/local scope, LWT linearizability, batch atomicity)
- cassandra.apache.org/doc/latest/cassandra/developing/cql/dml.html (LWT IF/Paxos cost, BATCH LOGGED/UNLOGGED/COUNTER, single-partition isolation)

## Queries & secondary indexes <a id="queries-and-secondary-indexes"></a>

Wide-column, tunable consistency. 5.0.x current stable (GA 2024; SAI + vector search new in 5.0); 4.0/4.1 supported, 3.11 EOL — verify. ScyllaDB is CQL-compatible (global 2i is materialized-view-backed; SAI is Cassandra-only) — verify parity first.

### The query drives the schema
No JOINs, no ad-hoc filtering. A `SELECT` must hit a partition by equality on the **full partition key** (`IN` counts as equality); within it, clustering columns restrict a **contiguous prefix** and only the **last** restricted one may be a range (`>`/`<`). `ORDER BY` is limited to clustering order or its reverse. So the idiom is **one table per access pattern** — denormalize, write each row to every query table; the primary key answers the read. Indexes are *secondary*, never a substitute for a good key.

- DO restrict the full partition key + clustering prefix; use `token(pk)` for partition-range scans, `PER PARTITION LIMIT`, and cursor paging — never OFFSET.
- DON'T reach for `ALLOW FILTERING` in app code: it scans every partition, latency grows with data, rejected by default. Fine only for known-tiny or admin queries.

### Secondary options, in order of preference
1. **Second query table / denormalize** — default; predictable single-partition reads.
2. **SAI (Storage-Attached Index, 5.0)** — `CREATE INDEX ix ON t(col) USING 'sai'`. One index per column, many per table (`sai_indexes_per_table_failure_threshold`=10 default), ~20-35% disk overhead, **synchronous** write path (indexed on ack), `Murmur3Partitioner` only. Numeric/timestamp/uuid support ranges (`=,<,>,<=,>=`, k-d tree); text supports `=`, `CONTAINS`, `CONTAINS KEY` only — **no `LIKE`/`!=`/text ranges**. Collections via `KEYS`/`VALUES`/`ENTRIES`, UDTs, and vectors (`ORDER BY ... ANN OF`, LIMIT ≤1000). `AND` processes up to two SAI indexes; extra indexed predicates are post-filtered; `OR` supported. Options: `case_sensitive` (default true), `normalize`, `ascii`. Removes `ALLOW FILTERING` for indexed predicates — but mixing in a non-indexed column needs it.
3. **Legacy 2i** (`CREATE INDEX` without `USING`) and **SASI** — scatter-gather across nodes; latency scales with cluster size, not matches. Avoid high-cardinality (near-unique) and very low-cardinality (boolean) columns — the classic 2i trap. SASI is experimental; on 5.0 prefer SAI.

### Gotchas
- An index read is still **cluster-wide** unless you co-restrict the partition key to pin it to one node — add PK equality when the pattern allows.
- SAI can index one column of a **composite** partition key, but not a single-column PK (it errors — the PK already answers it).
- Indexing a hot/low-cardinality value recreates the **hot-partition** problem in the index.
- Consistency is tunable per statement (`LOCAL_QUORUM` typical); an index read uses the normal read path — not transactional or point-in-time.

See lore/deep/cassandra.md#performance for the fast-path/anti-pattern playbook and lore/deep/databases.md#{indexing-and-query-plans,resilience-and-observability}.

### Sources
- cassandra.apache.org/doc/latest/cassandra/developing/cql/indexing/sai/{sai-query,sai-faq,sai-overview}.html (SAI operators, ranges, collections, limits)
- cassandra.apache.org/doc/latest/cassandra/developing/cql/dml.html (WHERE/clustering/IN/token/ORDER BY/ALLOW FILTERING rules)
- cassandra.apache.org/doc/latest/cassandra/reference/cql-commands/create-index.html (CREATE INDEX ... USING 'sai', KEYS/VALUES/ENTRIES, options)

## Compaction & Storage <a id="compaction-and-storage"></a>

LSM-tree engine: writes append-only; deletes/updates are new writes reconciled at read/compaction by write-timestamp (last-write-wins). Current stable 5.0.8; 4.1.x/4.0.x still maintained — verify gates.

### Write path & SSTable anatomy
- Write → **commit log** (durability; `commitlog_sync` `periodic`=default fsync ~10s / `batch`=ack after fsync; `commitlog_segment_size` 32MiB) → **memtable** (sorted, in-mem) → **flush** → immutable **SSTable**. Commit-log segments purge after their memtables flush.
- SSTable components (Big format): `Data.db`, `Index.db`, `Summary.db` (every 128th index entry), `Filter.db` (partition-key bloom filter), `Statistics.db`, `CompressionInfo.db`, `Digest.crc32`; `SAI_*.db` when a storage-attached index (SAI, new in 5.0) exists.
- **BTI (trie-indexed) format**, new in 5.0 (CEP-25): replaces `Index.db`+`Summary.db` with `Partitions.db`+`Rows.db` tries — smaller, faster lookups, better for large partitions. Enable via `cassandra.yaml`: `sstable: {selected_format: bti}` (default stays `big`/`oa`, whose 5.0 rev widened `deletionTime` to a long, fixing the 2038 TTL overflow). Run `nodetool upgradesstables` after a format/major-version change.

### Compaction fundamentals
Compaction merge-sorts SSTables into fewer, purging shadowed cells, expired TTL rows, and droppable **tombstones**. Fewer SSTables per read = fewer bloom/index probes = faster reads. Two costs: **write amplification** (data rewritten repeatedly) and transient **space amplification** (old + new SSTables coexist mid-compaction — keep free disk ≥ the largest compaction's output).
- Tombstones survive `gc_grace_seconds` (default 864000 = 10 days) so deletes reach all replicas. DON'T let repair lapse past gc_grace or deleted data resurrects. `tombstone_threshold` 0.2 / `tombstone_compaction_interval` 86400s trigger single-SSTable purges.

### Strategies (pick by access pattern — the NoSQL storage-modeling lever)
- **UCS (UnifiedCompactionStrategy)** — 5.0 default recommendation; stateless, params change in-flight, shards for parallel compaction on dense nodes. `scaling_parameters` `w`: `T4`≈STCS (tiered, low WA/high RA), `L10`≈LCS (leveled, high WA/low RA), `N`=middle; per-level lists allowed. `target_sstable_size` 1GiB, `base_shard_count` 4, `min_sstable_size` 100MiB, `sstable_growth` 0.333.
- **STCS** — buckets similar-sized SSTables (`min_threshold` 4/`max_threshold` 32, `bucket_low` 0.5/`bucket_high` 1.5). Write-cheap but high space amplification; rows spread across many SSTables.
- **LCS** — levels each ~10× prior (`sstable_size_in_mb` 160, `fanout_size` 10); non-overlapping within a level ⇒ ~1 SSTable/level per read. Read-heavy; ~10% extra disk but IO/CPU-heavy. Falls back to STCS-in-L0 above 32 SSTables.
- **TWCS** — time-series + TTL. `compaction_window_unit` DAYS/`compaction_window_size` (aim 20–30 windows); once a window fully expires, the whole SSTable drops — no tombstone scan. DON'T `DELETE`, `USING TIMESTAMP`, or skip repair: comingled old/new data (read-repair/hints) defeats whole-SSTable expiry. `unsafe_aggressive_sstable_expiration` risks data resurrection.

```sql
ALTER TABLE ks.t WITH compaction =
  {'class':'UnifiedCompactionStrategy','scaling_parameters':'L10','target_sstable_size':'256MiB'};
```

DON'T run `nodetool compact` (major) on STCS/LCS — one giant SSTable results that never re-compacts. ScyllaDB is C*-CQL-compatible; adds ICS to cut STCS space-amp.

### Sources
- cassandra.apache.org/doc/latest/cassandra/managing/operating/compaction/ (ucs, stcs, lcs, twcs, overview)
- cassandra.apache.org/doc/latest/cassandra/architecture/storage-engine.html
- cwiki.apache.org/confluence/display/CASSANDRA/CEP-25%3A+Trie-indexed+SSTable+format

## Performance <a id="performance"></a>

Span **3.x / 4.x / 5.0** (GA **5.0.8**; 4.1/4.0 maintained). Write-optimized LSM (no read-before-write); **reads are the cost center** — no release fixes a bad partition key. Measure first.

### Prioritized levers (highest impact first)

1. **Partition key is the #1 lever** — fixes placement and per-request node count. Pick high-cardinality keys that spread evenly; a hot/low-cardinality key (status, day) caps throughput. Keep partitions bounded — docs target **< 100 MB and < 100k rows/cells**; bucket before they grow. See lore/deep/cassandra.md#data-modeling-and-partitions.
2. **One table per query; denormalize.** No server-side JOIN. Every read should hit **one partition on one node** — duplicate into query-specific tables. Multi-partition `IN`/scatter reads are latency traps.
3. **Read by partition key, never by filtering.** A non-key `WHERE` / `ALLOW FILTERING` is a cluster-wide scan (never in prod). Serve secondary access via a denorm table or **SAI** (5.0: text trie, numeric kd-tree, multi-index) — but SAI is still a token-ordered multi-node range read (adaptive concurrency), so it complements, never replaces, partition-key access. See lore/deep/cassandra.md#queries-and-secondary-indexes.
4. **Right-size consistency per query.** Tunable: prefer **LOCAL_QUORUM** (multi-DC: stays in-DC); `R+W>RF` gives read-your-writes. Don't default to QUORUM/ALL (cross-DC hops) or route reads through **LWT/Paxos** — multiple Paxos round trips (non-negligible cost), reserve for invariants. See lore/deep/cassandra.md#consistency-and-replication.
5. **Match compaction to the workload.** 5.0 **UCS** (recommended; scaling param tunes read/write amp, default T4) generalizes tiered/leveled; pre-5.0 default **STCS** (space-cheap, higher read amp), **LCS** for read/update-heavy, **TWCS** for time-series + TTL. See lore/deep/cassandra.md#compaction-and-storage.
6. **Batch for atomicity, not throughput.** A multi-partition `BATCH` funnels through the batchlog and overloads the coordinator (`batch_size_warn` 5 KiB / fail 50 KiB). Batch only same-partition writes; else async concurrent single writes (token-aware driver).

### Top anti-patterns

- **Hot / unbounded partitions, `ALLOW FILTERING`, large multi-partition batches** — see levers 1/3/6.
- **Tombstone overload** — deletes, TTL expiry, collection overwrites, `null` writes emit tombstones reads scan past (`tombstone_warn_threshold` 1000; `tombstone_failure_threshold` 100000 aborts read). Queue patterns are the classic trap; `gc_grace_seconds` 864000 (10 d) delays reclaim.
- **Read-path LWT / legacy 2i** — Paxos contention, per-node scatter-gather; reserve LWT for real CAS, prefer SAI over 2i.

### How to measure

- **`nodetool tablestats`/`tablehistograms`** — p99 latency, SSTables-per-read, partition size, tombstones-per-read; **`tpstats`** — dropped mutations, pending threads (`concurrent_reads`/`writes` 32).
- **`TRACING ON`**, **`proxyhistograms`**, **`compactionstats`** — coordinator↔replica hops, tombstone scans, coordinator latency, compaction backlog.
- Pooling + observability: lore/deep/databases.md#{connection-pooling,resilience-and-observability}.
- **ScyllaDB** is CQL-compatible (shard-per-core); same modeling rules, verify parity.

### Sources
cassandra.apache.org/doc/latest/cassandra/: developing/data-modeling/intro.html; architecture/dynamo.html; managing/operating/compaction/{ucs,tombstones}.html; developing/cql/indexing/sai/sai-concepts.html
