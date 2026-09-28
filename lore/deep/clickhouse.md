# ClickHouse — deep dive

> On-demand companion to `lore/clickhouse.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [MergeTree & Schema](#mergetree-and-schema) · [Ingestion & Inserts](#ingestion-and-inserts) · [Materialized Views & Query Performance](#materialized-views-and-query-perf) · [Sharding & Replication](#sharding-and-replication) · [Performance](#performance)

## MergeTree & Schema <a id="mergetree-and-schema"></a>

Version-adaptive: MergeTree fundamentals are stable across the fast-moving 25.x/26.x line, but lightweight `UPDATE` and its patch-part internals are still **beta** (verify GA before relying on them) — confirm against the release you run.

### Sorting key (ORDER BY) is the whole game
`ORDER BY` defines physical row order per part and doubles as the (sparse) primary key. There is no row-level index: the in-memory index stores one mark per **granule** (`index_granularity`, default 8192 rows). Queries binary-search marks to pick granules, then scan whole granules.

DO order key columns by **ascending cardinality** (low → high). Two wins: (1) a filter on the *leading* column binary-searches marks; a filter on a later column falls back to a generic-exclusion search that prunes only when its predecessor is low-cardinality. (2) Low-cardinality-first clusters similar values, so compression improves sharply. DO put your most-filtered column early. DON'T treat `ORDER BY` like an OLTP PK — it needn't be unique and isn't enforced.

DO split key vs. index when memory matters: `PRIMARY KEY` may be a **prefix** of `ORDER BY` (fewer columns in the RAM index; the rest still sort for compression).

DON'T use `Nullable` columns in the key (needs `allow_nullable_key`, discouraged) — model absence with a sentinel/default.

### Partitioning: pruning, not perf
`PARTITION BY` (commonly `toYYYYMM(date)`) enables partition pruning and cheap `DROP PARTITION` / `TTL` expiry. Parts never merge across partitions. DON'T over-partition — high-cardinality partition keys create thousands of tiny parts → "too many parts" errors and slow merges. Rule: coarse partitions (day/month), fine sorting key.

### Data types drive compression
Compression = ordering + types + codecs. DO pick the narrowest correct type: smallest unsigned int that fits (`UInt16` vs `Int32`), coarsest date (`Date`/`DateTime` over `DateTime64`), `Enum8/16` for closed sets (insert-time validation), `LowCardinality(String)` under ~10k distinct values. DON'T default to `Nullable` — it adds a parallel `UInt8` mask read on every access.

DO add codecs for time-series: `CODEC(DoubleDelta)` for monotonic timestamps, `CODEC(Gorilla)` for slow-changing floats, or `CODEC(Delta, ZSTD)` pipelines (default `LZ4` self-managed / `ZSTD` Cloud).

### Merges, mutations, upserts
Parts are immutable; background merges combine them. Mutations (`ALTER TABLE … UPDATE/DELETE`) are **heavyweight** — they rewrite affected columns of whole parts. Lightweight `DELETE` marks rows via a hidden `_row_exists` mask (physical removal at next merge). Lightweight `UPDATE` (beta) writes **patch parts** (changed cols/rows only), immediately visible, materialized later — meant for < ~10% of rows.

DON'T upsert row-by-row. Use `ReplacingMergeTree` (dedup by `ORDER BY` at merge time; optional `ver` picks the winner, `is_deleted` tombstones) and read with `FINAL`, or use aggregations tolerant of pre-merge dupes. Dedup is **eventual and non-deterministic** — never assume merges ran.

### Sources
- https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree
- https://clickhouse.com/docs/optimize/sparse-primary-indexes
- https://clickhouse.com/docs/data-modeling/schema-design
- https://clickhouse.com/docs/engines/table-engines/mergetree-family/replacingmergetree
- https://clickhouse.com/docs/sql-reference/statements/update
- https://clickhouse.com/docs/sql-reference/statements/create/table

## Ingestion & Inserts <a id="ingestion-and-inserts"></a>

Current stable **26.6** (YY.M scheme, monthly cadence — verify feature gates against your server). Ingestion is the make-or-break OLAP discipline: each INSERT writes an immutable, sorted **data part**; a background pool merges small parts into big ones. Your job is to feed ClickHouse **few large batches**, not a stream of tiny rows.

### Batch — the cardinal rule
- Insert **10,000–100,000 rows per batch** (at least 1,000); keep synchronous inserts to roughly **1/sec**. Larger batches write fewer parts, cut merge load, and amortize the fixed per-insert overhead.
- DON'T do row-at-a-time or many small `INSERT ... VALUES` — each spawns a part, background merges fall behind, and you hit the **`Too many parts`** error (a hard write stall). This is the #1 ClickHouse ingestion mistake.
- One part is created **per distinct partition-key value per flush** — a high-cardinality `PARTITION BY` multiplies parts and triggers the same error. Partition coarsely (e.g. by month), not by a high-cardinality column.

### Format & pre-sorting
- Prefer **Native** (columnar, minimal server parsing) or **RowBinary**; `JSONEachRow`/CSV are convenient but CPU-expensive to parse server-side — reserve for low volume.
- Data is stored ordered by the `ORDER BY` (primary) key; pre-sorting the batch client-side lets the server skip its sort step (optional optimization, only when the batch is already near-ordered).

### Bulk load paths
- From files/object storage use table functions in `INSERT ... SELECT`, e.g. `INSERT INTO t SELECT * FROM s3('…','Parquet')` or `file('data.parquet')`; globs (`*`,`{1,2}`,`{1..9}`) fan out over many files.
- `INSERT INTO t FROM INFILE 'x.csv.gz' COMPRESSION 'gzip' FORMAT CSV` loads a client-side file (compression auto-detected from extension).
- `INSERT ... SELECT` **always runs synchronously** — `async_insert` does not apply to it.

### Async inserts — server-side batching
When clients can't batch (many agents, small real-time payloads), enable `async_insert=1`: rows buffer server-side per insert-shape and flush when **any** threshold hits first — `async_insert_max_data_size` (100 MiB), `async_insert_busy_timeout_max_ms` (200 ms; 1000 ms on Cloud), or `async_insert_max_query_number` (450). Adaptive timeout (`async_insert_use_adaptive_busy_timeout`, on since **24.2**) floats between `…_min_ms` (50 ms) and max by data rate.
- Keep `wait_for_async_insert=1` (default): the client is acked only after the flush to disk, so errors surface. `=0` is fire-and-forget — low latency but **silent data loss** and no dead-letter; the docs call it "very risky".
- Buffered rows aren't queryable until flushed; parse/type errors reject the **whole** query at flush time. Drain before maintenance with `SYSTEM FLUSH ASYNC INSERT QUEUE`.

### Idempotency & dedup
Synchronous MergeTree inserts are **idempotent**: identical blocks (same content **and** order) are deduplicated by block hash, so retrying a dropped batch is safe — don't split/reorder on retry or you defeat it. Deduplication is **OFF for async inserts** unless you enable it, and you should not enable it when the table feeds dependent materialized views.

### Upserts & deletes (not row UPDATEs)
- **Upsert** via `ReplacingMergeTree([ver[, is_deleted]])`: rows with the same `ORDER BY` key collapse to the max-`ver` (or last-inserted) row — but **only at merge time**, eventually. Read with `SELECT … FINAL` for correct de-duplicated results; `OPTIMIZE … FINAL CLEANUP` (needs `allow_experimental_replacing_merge_with_cleanup`) purges `is_deleted=1` rows.
- **Lightweight `DELETE FROM … WHERE`** flags rows via the `_row_exists` mask (no immediate rewrite); physical removal waits for a merge (`lightweight_deletes_sync`, `min_age_to_force_merge_seconds`). Far cheaper than `ALTER TABLE … DELETE`, which is a **mutation** that rewrites whole columns of every affected part.
- **Lightweight `UPDATE … SET … WHERE`** (beta) writes **patch parts** with only changed columns — immediately visible, materialized on later merge; designed for small updates (≤~10% of the table). For large rewrites use the heavyweight `ALTER TABLE … UPDATE` mutation. DON'T model per-row OLTP churn on ClickHouse.

### Sources
- ClickHouse — Selecting an insert strategy (batch sizes, formats, idempotency): https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy
- ClickHouse — Asynchronous inserts (thresholds, wait mode, adaptive timeout): https://clickhouse.com/docs/optimize/asynchronous-inserts
- ClickHouse — ReplacingMergeTree (ver/is_deleted, FINAL, merge-time dedup): https://clickhouse.com/docs/engines/table-engines/mergetree-family/replacingmergetree
- ClickHouse — Lightweight DELETE / UPDATE (masks, patch parts, mutations): https://clickhouse.com/docs/sql-reference/statements/delete · /statements/update

## Materialized Views & Query Performance <a id="materialized-views-and-query-perf"></a>

Version-adaptive; verify current stable. Gates: `_part_offset`-only projections since **25.5**, multi-projection part pruning since **25.6**, adaptive async-insert timeout since **24.2**. Lightweight `UPDATE` is still **beta**; refreshable MVs are standard now (older builds need `allow_experimental_refreshable_materialized_view`).

### Incremental MV = insert trigger, not a snapshot
Runs its SELECT on **each inserted block** into a target table (compute moves to insert time). Use the explicit `TO` form (a real, tunable target):
```sql
CREATE MATERIALIZED VIEW votes_daily_mv TO votes_daily AS
SELECT toStartOfDay(ts)::Date AS day, countIf(kind=2) AS up
FROM votes GROUP BY day;
```
Inside the trigger the source name is **the inserted block only** — self-lookups see just new rows (use a plain `VIEW` to read the full table). In a JOIN **only the left-most table triggers**; right tables are a static snapshot at insert time, so pre-load dimensions or filter them by the block's keys (`WHERE id IN (SELECT fk FROM <block>)`) — an unfiltered big-right JOIN makes inserts crawl. `UNION ALL` won't fully trigger — one MV per branch into a shared target. CTEs are inlined, not materialized.

### Aggregating targets: partial state, merge on read
`SummingMergeTree` for additive counters. For avg/quantile/uniq use `AggregatingMergeTree` + `AggregateFunction` columns, write `xxxState()`, read `xxxMerge()` — averaging pre-averaged rows is wrong. The MV `GROUP BY` **must match the target `ORDER BY`** or merges skew. Merges are async — re-aggregate at read (`GROUP BY`+`sumMerge`), not `FINAL`.

### Refreshable MVs for joins/DAGs
`REFRESH EVERY 1 MINUTE` (or `AFTER`) re-runs the full query and **atomically swaps** the target — for JOINs incremental can't express. Chain via dependencies (a mini-scheduler); `APPEND` accumulates snapshots. Watch `system.view_refreshes`; force with `SYSTEM REFRESH VIEW`. Incremental scales far better — use refreshable only when it can't.

### Projections: optimizer's alt-ordering / pre-agg
A hidden reordered/pre-aggregated copy **inside the same table**, auto-synced; query the base table and the optimizer picks the variant scanning least (`optimize_use_projections`, on).
```sql
ALTER TABLE trips ADD PROJECTION p_by_fare (SELECT * ORDER BY fare);
ALTER TABLE trips MATERIALIZE PROJECTION p_by_fare;  -- backfill
```
`MATERIALIZE` is required or only new parts are covered; `GROUP BY` makes it an aggregate projection. Since 25.5 a `_part_offset`-only projection acts as a pure index (locate via projection, read base) cutting double-write cost; 25.6 prunes whole parts using several. Confirm via `EXPLAIN projections=1`. Limits: no JOIN/`WHERE` in the definition, no chaining, TTL tied to base, **lightweight update/delete disabled** by default.

### Scan-less query idioms
**Select only needed columns — never `SELECT *` on wide tables**; push the most selective predicate into `PREWHERE`; filter a prefix of the `ORDER BY` key so granules prune. Ingest in **big batches** — many tiny INSERTs make too many parts; if the client can't batch, set `async_insert=1, wait_for_async_insert=1` (server buffering; not for `INSERT ... SELECT`). Mutate sparingly: lightweight `DELETE` sets a `_row_exists` mask (rewritten as `ALTER ... UPDATE _row_exists=0`), lightweight `UPDATE` writes patch parts applied at read time — both add read cost and suit <~10% of rows; bulk lifecycle is cheapest via `DROP PARTITION`.

### Sources
- clickhouse.com/docs/materialized-view/incremental-materialized-view
- clickhouse.com/docs/materialized-view/refreshable-materialized-view
- clickhouse.com/docs/data-modeling/projections
- clickhouse.com/docs/optimize/asynchronous-inserts
- clickhouse.com/docs/sql-reference/statements/update ; .../delete

## Sharding & Replication <a id="sharding-and-replication"></a>

Version-adaptive (25.x/26.x): **ClickHouse Keeper** is the recommended coordinator (ZooKeeper ≥3.4.5 still works). Self-managed uses `ReplicatedMergeTree` + `Distributed`; **ClickHouse Cloud** rewrites plain `MergeTree` to **SharedMergeTree** and manages HA/scaling for you — the two worlds differ sharply, so know which you target.

Two orthogonal axes: a **shard** is a disjoint subset of the data on its own host set; a **replica** is a full copy of one shard for redundancy and read fan-out. Replication scales availability/reads; sharding scales storage and write/scan throughput. Most clusters combine both (e.g. 2 shards × 2 replicas).

### Replication — ReplicatedMergeTree + Keeper
Use a `Replicated*MergeTree` engine; all coordination (part metadata, insert dedup log, leader election for merges) flows through Keeper. Run **≥3 Keeper nodes** on dedicated hosts (Raft quorum). Replication is **asynchronous and multi-master**: any replica accepts writes and others fetch parts later.

```sql
CREATE TABLE events ON CLUSTER my_cluster (…)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/events', '{replica}')
ORDER BY (ts, id);
```

DO template the Keeper path with **`<macros>`** (`{shard}`, `{replica}`, built-in `{database}`/`{table}`) set uniquely per node; or set server-level `default_replica_path` = `/clickhouse/tables/{uuid}/{shard}` + `default_replica_name` = `{replica}` and omit the engine args entirely. DON'T reuse one zk_path across two replicas of *different* shards, and DON'T bake `{database}`/`{table}` into the path if you'll rename — **the Keeper path cannot be changed** after creation.

DO run schema changes with `ON CLUSTER` so DDL fans out to every node via the distributed-DDL queue. DON'T set the same `{replica}` on two hosts — they'll fight over one replica identity.

Durability: a default INSERT is acked after **one** replica persists it; if that host dies before propagation the block is lost. For stronger guarantees set `insert_quorum` (e.g. `2` or `auto`) with `insert_quorum_parallel`; reads needing freshness use `select_sequential_consistency=1`. DON'T enable quorum globally without cause — it adds latency and Keeper load.

### Sharding — Distributed engine
A `Distributed` table stores no data; it fans reads across shards and (optionally) routes inserts.

```sql
ENGINE = Distributed(my_cluster, mydb, events_local, cityHash64(user_id));
```

The **sharding key** must be an integer expression: `rand()` for even spread, or a hash of a co-location key (`intHash64(user_id)`) to keep one entity on one shard (enables local JOINs and `optimize_skip_unused_shards`). Per-shard `<weight>` splits data proportionally.

**`internal_replication` is the critical knob** in `<remote_servers>`: with `Replicated*` local tables set it **`true`** — the Distributed write hits *one* healthy replica and replication propagates it. Leaving it `false` (default) makes the Distributed table write every replica itself, bypassing consistency checks → drift. DO set `true` whenever local tables are replicated.

Reads: SELECT hits one replica per shard (`load_balancing`), pushes down partial aggregation, and merges intermediate states on the initiator. DO enable **`max_parallel_replicas`** to also parallelize a shard's scan across its replicas.

Writes: prefer **inserting directly into the local `*_local` tables** on each shard (most optimal, full control of routing). Inserting into the Distributed table buffers locally then forwards in the background (`distributed_background_insert_*`); a hard crash mid-forward can lose staged data. DON'T point ingestion at a Distributed table when you can shard client-side.

### Cloud — SharedMergeTree
Cloud separates compute from shared object storage; replicas are **leaderless** and coordinate only via storage + Keeper, so you scale to many replicas **without shards**. DON'T write `ReplicatedMergeTree`, `Distributed`, macros, or `insert_quorum` — create plain `MergeTree` (it maps to `SharedMergeTree`; all inserts are already quorum). Use `remote()`/`remoteSecure()` instead of `Distributed`, and `SYSTEM SYNC REPLICA LIGHTWEIGHT` for read-after-write across nodes.

### Sources
- https://clickhouse.com/docs/engines/table-engines/mergetree-family/replication
- https://clickhouse.com/docs/engines/table-engines/special/distributed
- https://clickhouse.com/docs/architecture/horizontal-scaling
- https://clickhouse.com/docs/cloud/reference/shared-merge-tree

## Performance <a id="performance"></a>

Ordered playbook: fix the biggest lever first, measure every change. Version-adaptive (25.x/26.x); verify gates. Checklist only; depth in the deep-dives.

### 0. Measure first
- DO find costly queries in `system.query_log`: sort by `query_duration_ms`, `read_rows`, `memory_usage`; group by `normalized_query_hash` for repeat offenders.
- DO read the plan: `EXPLAIN indexes=1` shows whether the primary index prunes granules or the query full-scans; `EXPLAIN PIPELINE` shows real parallelism. For honest timing `SET enable_filesystem_cache=0`. Plan discipline: lore/deep/databases.md#indexing-and-query-plans.
- DON'T tune on tiny tables — scanning a small part is rational.

### 1. Ingest in big batches (the OLAP make-or-break)
- DO insert 10k–100k rows per batch (~1 insert/sec); each INSERT writes an immutable part; merges chase them. Tiny INSERTs → `Too many parts` stall.
- DO set `async_insert=1` (keep `wait_for_async_insert=1`) when clients can't batch — server buffering, adaptive since 24.2. Detail: lore/deep/clickhouse.md#ingestion-and-inserts.

### 2. Shape ORDER BY around your filters (biggest read lever)
- DO make the `ORDER BY`/primary key a prefix of your hot filter+sort predicates, low-cardinality first — a sparse granule index, so a leading-column filter prunes most granules and compresses better. Coarse `PARTITION BY` (e.g. `toYYYYMM`) for pruning + cheap `DROP PARTITION`. Model: lore/deep/clickhouse.md#mergetree-and-schema.
- DON'T over-partition (high-cardinality key) → part explosion.

### 3. Read fewer bytes per query
- DO select only needed columns — never `SELECT *` on wide tables (each column = separate I/O).
- DO rely on `PREWHERE` — automatic (`optimize_move_to_prewhere`, on) so the smallest/most-selective columns filter first; write it manually only to override. Tighten types (`LowCardinality`, narrow ints) to shrink scans.

### 4. Alternate access paths (when ORDER BY can't help)
- DO precompute: incremental **materialized views** (compute at insert) and **projections** (auto-synced reordered/pre-agg copy; confirm with `EXPLAIN projections=1`). See lore/deep/clickhouse.md#materialized-views-and-query-perf.
- DO add a **data-skipping index** (`minmax`, `set`, `bloom_filter`) ONLY when the target column strongly correlates with the primary key — else every block matches, dead weight. Use the `text` index for full-text (`tokenbf_v1`/`ngrambf_v1` deprecated).

### 5. Keep FINAL & mutations off the hot path
- DO dedup with `ReplacingMergeTree` + query-time `GROUP BY`/`argMax`, not `SELECT … FINAL` on every read (merges are eventual). lore/deep/clickhouse.md#mergetree-and-schema.
- DON'T run frequent `ALTER TABLE UPDATE/DELETE` mutations — they rewrite whole columns; use lightweight delete/update (small %) or `DROP PARTITION` for bulk.

### 6. Scale out
- DO shard with a `Distributed` table over `ReplicatedMergeTree` (co-locate by hash key for local JOINs) and enable `max_parallel_replicas` to parallelize a shard across replicas. Cloud: plain `MergeTree` → SharedMergeTree. lore/deep/clickhouse.md#sharding-and-replication.

### 7. Resource knobs (last, not first)
- DO raise `max_threads` (default = CPU cores) for scan-heavy queries; lower it to cut memory. `max_insert_threads` (default 0/1) parallelizes `INSERT SELECT`.
- DO cap `max_memory_usage` (default 0 = unlimited per query) to protect the server, and enable spill via `max_bytes_before_external_group_by`/`_sort` (default 0 = in-memory) so big GROUP BY/ORDER BY don't OOM.

### Sources
- clickhouse.com/docs/optimize/{query-optimization,prewhere,skipping-indexes}
- clickhouse.com/docs/best-practices/selecting-an-insert-strategy
- ClickHouse src/Core/Settings.cpp — max_threads / max_memory_usage / max_insert_threads defaults
