# ClickHouse — Sharding & Replication

Version-adaptive (25.x/26.x): **ClickHouse Keeper** is the recommended coordinator (ZooKeeper ≥3.4.5 still works). Self-managed uses `ReplicatedMergeTree` + `Distributed`; **ClickHouse Cloud** rewrites plain `MergeTree` to **SharedMergeTree** and manages HA/scaling for you — the two worlds differ sharply, so know which you target.

Two orthogonal axes: a **shard** is a disjoint subset of the data on its own host set; a **replica** is a full copy of one shard for redundancy and read fan-out. Replication scales availability/reads; sharding scales storage and write/scan throughput. Most clusters combine both (e.g. 2 shards × 2 replicas).

## Replication — ReplicatedMergeTree + Keeper
Use a `Replicated*MergeTree` engine; all coordination (part metadata, insert dedup log, leader election for merges) flows through Keeper. Run **≥3 Keeper nodes** on dedicated hosts (Raft quorum). Replication is **asynchronous and multi-master**: any replica accepts writes and others fetch parts later.

```sql
CREATE TABLE events ON CLUSTER my_cluster (…)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/events', '{replica}')
ORDER BY (ts, id);
```

DO template the Keeper path with **`<macros>`** (`{shard}`, `{replica}`, built-in `{database}`/`{table}`) set uniquely per node; or set server-level `default_replica_path` = `/clickhouse/tables/{uuid}/{shard}` + `default_replica_name` = `{replica}` and omit the engine args entirely. DON'T reuse one zk_path across two replicas of *different* shards, and DON'T bake `{database}`/`{table}` into the path if you'll rename — **the Keeper path cannot be changed** after creation.

DO run schema changes with `ON CLUSTER` so DDL fans out to every node via the distributed-DDL queue. DON'T set the same `{replica}` on two hosts — they'll fight over one replica identity.

Durability: a default INSERT is acked after **one** replica persists it; if that host dies before propagation the block is lost. For stronger guarantees set `insert_quorum` (e.g. `2` or `auto`) with `insert_quorum_parallel`; reads needing freshness use `select_sequential_consistency=1`. DON'T enable quorum globally without cause — it adds latency and Keeper load.

## Sharding — Distributed engine
A `Distributed` table stores no data; it fans reads across shards and (optionally) routes inserts.

```sql
ENGINE = Distributed(my_cluster, mydb, events_local, cityHash64(user_id));
```

The **sharding key** must be an integer expression: `rand()` for even spread, or a hash of a co-location key (`intHash64(user_id)`) to keep one entity on one shard (enables local JOINs and `optimize_skip_unused_shards`). Per-shard `<weight>` splits data proportionally.

**`internal_replication` is the critical knob** in `<remote_servers>`: with `Replicated*` local tables set it **`true`** — the Distributed write hits *one* healthy replica and replication propagates it. Leaving it `false` (default) makes the Distributed table write every replica itself, bypassing consistency checks → drift. DO set `true` whenever local tables are replicated.

Reads: SELECT hits one replica per shard (`load_balancing`), pushes down partial aggregation, and merges intermediate states on the initiator. DO enable **`max_parallel_replicas`** to also parallelize a shard's scan across its replicas.

Writes: prefer **inserting directly into the local `*_local` tables** on each shard (most optimal, full control of routing). Inserting into the Distributed table buffers locally then forwards in the background (`distributed_background_insert_*`); a hard crash mid-forward can lose staged data. DON'T point ingestion at a Distributed table when you can shard client-side.

## Cloud — SharedMergeTree
Cloud separates compute from shared object storage; replicas are **leaderless** and coordinate only via storage + Keeper, so you scale to many replicas **without shards**. DON'T write `ReplicatedMergeTree`, `Distributed`, macros, or `insert_quorum` — create plain `MergeTree` (it maps to `SharedMergeTree`; all inserts are already quorum). Use `remote()`/`remoteSecure()` instead of `Distributed`, and `SYSTEM SYNC REPLICA LIGHTWEIGHT` for read-after-write across nodes.

## Sources
- https://clickhouse.com/docs/engines/table-engines/mergetree-family/replication
- https://clickhouse.com/docs/engines/table-engines/special/distributed
- https://clickhouse.com/docs/architecture/horizontal-scaling
- https://clickhouse.com/docs/cloud/reference/shared-merge-tree
