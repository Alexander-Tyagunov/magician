# Google BigQuery — deep dive

> On-demand companion to `lore/bigquery.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Cost and Slots](#cost-and-slots) · [Partitioning & Clustering](#partitioning-and-clustering) · [Loading and Streaming](#loading-and-streaming) · [SQL and Features](#sql-and-features) · [Performance](#performance)

## Cost and Slots <a id="cost-and-slots"></a>

Serverless managed DW: no user-installed version; dialect GoogleSQL. Two evolving billing models — verify current terms:
- **On-demand**: pay per **bytes scanned** (per TiB), with a **10 MiB minimum billed per query** and a **monthly free-tier of query bytes**. Compute uses transient burst slots under a per-project/org cap.
- **Capacity (editions)**: buy **slots** (virtual compute units) over time via **reservations** on the **Standard / Enterprise / Enterprise Plus** editions. Slot-time is billed; bytes scanned are not.

### Bytes-scanned is the on-demand lever (columnar)
DO select only needed columns — cost ≈ bytes in the **columns referenced**, not rows returned; `SELECT * EXCEPT(col)` to drop a few from a wide table.
DON'T `SELECT *` on wide tables, and DON'T use `LIMIT` as a cost control: on non-clustered tables it still reads all referenced bytes (LIMIT prunes only on clustered tables).
DO prune by partition — filter on the partition column or `_PARTITIONTIME`, and set `require_partition_filter` so unfiltered scans error; keep the column bare (no `DATE(func(col))`) or pruning is lost.
DO cluster hot tables so filters/`ORDER BY`+`LIMIT` skip blocks; pre-aggregate before joins; use `APPROX_COUNT_DISTINCT`/`APPROX_QUANTILES` for high-cardinality stats.

### Estimate and cap before you spend
DO dry-run nontrivial queries (`bq query --dry_run`, API `dryRun:true`, `QueryJobConfig(dry_run=True)`) — the estimate is an **upper bound**.
DO set `maximum_bytes_billed` (bq `--maximum_bytes_billed` / API `maximumBytesBilled`): a query over the cap **fails with no charge**. Add **custom daily query quotas** per project/user as a backstop.

### Free recompute avoidance
- **Query results cache** (**0 bytes billed**, ~24h): needs **byte-identical** text; skipped by non-deterministic funcs (`CURRENT_TIMESTAMP()`), wildcard tables, a destination table, streaming-fresh tables, or RLS. `--nouse_cache` forces fresh.
- **Materialized views** precompute + incrementally refresh aggregates; **BI Engine** gives in-memory dashboard acceleration.
- **CTEs (`WITH`) are for readability, not reuse** — a CTE may re-execute per reference; materialize hot intermediates to a temp table.

### Slots and editions (capacity)
DON'T issue many tiny `INSERT`s — batch via **load jobs** or the **Storage Write API**; use `MERGE` for upserts, not row-at-a-time UPDATE.
- **Reservations** hold **baseline** (always-on, always billed) + **autoscale** slots; autoscale steps in multiples of **50**, bills per-second with a **1-min minimum**, and scaled slots bill **even if the triggering query fails**.
- **Commitments** (1yr / 3yr) discount slots but can't be reduced mid-term; baseline over commitment bills PAYG.
- **Idle slots** auto-share within an edition/admin project (`ignore_idle_slots=true` to pin); **fair scheduling** splits across projects then jobs; queued/borrowed slots aren't billed extra.
- Autoscaling suits **heavy, concurrent** workloads, not one-off queries.
DO pick on-demand for spiky/low volume, capacity for steady high concurrency; assign reservations at folder/org level to avoid surprise on-demand spend.

### Storage cost note
Billed **active** vs **long-term** (untouched ~90 days, cheaper), under a per-dataset **logical** or **physical** (compressed) model — physical often wins on well-compressed data.

### Sources
- cloud.google.com/bigquery/pricing
- cloud.google.com/bigquery/docs/slots
- cloud.google.com/bigquery/docs/best-practices-costs
- cloud.google.com/bigquery/docs/best-practices-performance-compute
- cloud.google.com/bigquery/docs/cached-results

## Partitioning & Clustering <a id="partitioning-and-clustering"></a>

Serverless DW: no user version. On-demand cost = **bytes scanned per TiB** (first 1 TiB/month free; **10 MiB min billed per referenced table and per query**); capacity mode bills **slots** (Standard / Enterprise / Enterprise Plus editions). Scan less — that's the game. GoogleSQL. Pricing/editions evolve — confirm live.

### Partitioning — one column, prunes bytes

A table has **exactly one** partitioning column, a top-level scalar (not `REPEATED`, not a `RECORD`/`STRUCT` leaf). Three kinds:

- **Time-unit column** on `DATE`/`TIMESTAMP`/`DATETIME`. `DATE` → DAY/MONTH/YEAR; `TIMESTAMP`/`DATETIME` add HOUR. Boundaries are **UTC**.
- **Ingestion-time** via pseudocolumns `_PARTITIONTIME` / `_PARTITIONDATE` (no stored column).
- **Integer-range** via `RANGE_BUCKET(col, GENERATE_ARRAY(start, end, interval))`.

```sql
CREATE TABLE ds.events (id INT64, ts TIMESTAMP, uid INT64)
PARTITION BY TIMESTAMP_TRUNC(ts, DAY)        -- or DATE_TRUNC(d, MONTH), or the bare DATE col
OPTIONS (partition_expiration_days = 90, require_partition_filter = TRUE);
```

DO set `require_partition_filter = TRUE` so every query must filter the partition column — hard-stops full scans. DO filter with a **constant/pruning-friendly predicate** (`WHERE ts >= '2026-07-01'`); a subquery or wrapping the column in a function often defeats pruning and scans everything. NULL keys land in `__NULL__`; out-of-range rows land in `__UNPARTITIONED__`.

DON'T create tiny partitions: aim **≥ ~10 GB average per partition**; too many inflate metadata and slow planning. Hard cap **10,000 partitions per table**; one load/query job touches **≤ 4,000 partitions**; ingestion-time mods **≤ 11,000/day/table**; a multi-statement transaction **≤ 100,000 partition mods**. Beyond ~500 date-partitions or >1 dimension, **cluster instead of (or plus) partition**.

### Clustering — sorts within blocks, up to 4 columns

`CLUSTER BY` sorts data into blocks by **up to 4 columns**; **order matters** — blocks prune only on a **leftmost prefix** (`c1`, `c1,c2`, …); filtering `c2` alone won't prune. Types: `INT64`, `STRING` (first **1024 chars** only), `BOOL`, `DATE`, `DATETIME`, `TIMESTAMP`, `NUMERIC`, `BIGNUMERIC`, `GEOGRAPHY`, `RANGE`.

```sql
CREATE TABLE ds.events (id INT64, ts TIMESTAMP, region STRING, uid INT64)
PARTITION BY DATE(ts)
CLUSTER BY region, uid;      -- partition first, then cluster within each partition
```

DO order cluster columns most-filtered-first to match query prefixes. DO cluster tables/partitions **> ~64 MB** (below that, one block — no gain). **Automatic reclustering** re-sorts blocks as you load — free, no slot charge, per-partition.

DON'T expect an accurate cost estimate before running a clustered query — block count is unknown until execution (unlike partition pruning). DON'T rely on `LIMIT` to cut cost on an unclustered table (it doesn't); on a clustered table `LIMIT` can reduce blocks scanned.

### Cost hygiene

DO `--dry_run` (`QueryJobConfig.dry_run`) to see bytes before paying; cap `maximum_bytes_billed`. DO select only needed columns — columnar storage means `SELECT *` on a wide table reads every column. A partition untouched **90 consecutive days** auto-drops to long-term storage pricing.

### Sources
- docs.cloud.google.com/bigquery/docs/partitioned-tables · /clustered-tables
- docs.cloud.google.com/bigquery/quotas · /docs/best-practices-costs

## Loading and Streaming <a id="loading-and-streaming"></a>

Serverless managed DW: no user version. Cost model evolves — GoogleSQL dialect; on-demand billing charges bytes scanned on read, capacity/editions (slots) charge compute-time. Ingestion has its own pricing lane (below). Verify current terms before quoting numbers.

### Choose the path by latency, not habit
- **Batch load (free)** — infrequently changing data, hourly/nightly. Load jobs from Cloud Storage (or local files), or the `LOAD DATA` SQL statement. Runs on the shared slot pool at **no charge** (cross-region reads may incur transfer). Loads are **atomic**: all rows or none.
- **Storage Write API** — the unified, recommended path for real-time and high-throughput batch. gRPC, protobuf/Arrow, first **2 TiB/month free**, then billed — but far cheaper than legacy insertAll.
- **Managed pipes** — Pub/Sub BigQuery subscription (high-throughput streaming loads), Datastream (CDC replication), Dataflow (preprocess then stream), Data Transfer Service (scheduled batch). Federated/external tables query GCS/Drive in place — that is not ingestion.

### Batch load — DO / DON'T
- DO prefer **Avro or Parquet**: self-describing (no schema needed) and read in parallel *even when compressed*. ORC also parallel. For CSV/JSON, **uncompressed loads faster** (parallel splits); `gzip` is the only supported compression and is slower.
- DO set write disposition deliberately: `WRITE_APPEND` (default), `WRITE_TRUNCATE` (replace + overwrite schema), `WRITE_EMPTY`. Combine `WRITE_TRUNCATE` with **partition decorators** (`table$YYYYMMDD`) for idempotent per-partition reloads and safe retries with backoff.
- DO load straight into **partitioned + clustered** tables so downstream reads prune. Use hive-partitioned layouts in GCS with `--autodetect` for schema on CSV/JSON.
- DON'T micro-batch load jobs: the default quota is **~1,500 loads per table per day**. Frequent tiny jobs exhaust it — switch to the Storage Write API for near-real-time.
- DON'T dump thousands of tiny files; consolidate so parallel readers stay busy.

### Storage Write API — stream types
- **Default stream** — at-least-once, immediate query visibility, no explicit stream to create, highest throughput. Use when duplicates are tolerable.
- **Committed** — exactly-once via client-supplied **offsets** (the API never writes the same offset twice); rows readable immediately. `CreateWriteStream → AppendRows(loop) → FinalizeWriteStream(optional)`.
- **Pending** — rows buffered until an atomic `BatchCommitWriteStreams`; a batch alternative to load jobs. `Create → AppendRows → Finalize → BatchCommit`.
- **Buffered** — advanced, Apache Beam connector only; otherwise avoid.
- Batch rows per `AppendRows` call; don't send one row per RPC.

### Gotchas
- Legacy `tabledata.insertAll` (REST) is the old streaming path: higher cost, streaming-buffer restrictions (recently streamed rows resist UPDATE/DELETE/export until flushed). Prefer the Storage Write API.
- Streaming is billed; batch load is free — don't stream data that could be nightly-batched.
- Upserts are **MERGE**, not row-by-row UPDATE. OLTP-style single-row DML at volume is an anti-pattern.
- Don't `SELECT *` to sanity-check a load — on-demand you pay per byte scanned; count/inspect specific columns.

### Sources
- docs.cloud.google.com/bigquery/docs/loading-data
- docs.cloud.google.com/bigquery/docs/batch-loading-data
- docs.cloud.google.com/bigquery/docs/write-api

## SQL and Features <a id="sql-and-features"></a>

GoogleSQL is the default/recommended ANSI dialect; legacy SQL is still available (Google recommends migrating), not deprecated. Serverless — no version to gate, but the model (on-demand bytes vs slots, editions) evolves; see lore/deep/bigquery.md#cost-and-slots.

### Nested & repeated data is the idiom — denormalize, don't star-join
Prefer wide tables with `STRUCT` (record) + `ARRAY` (repeated) columns over normalized joins. Flatten with `UNNEST` on the right of a `CROSS`/`LEFT`/`INNER JOIN` (INNER preferred); `FROM t, UNNEST(t.arr)` expands its array to child rows.
DO nest one-to-many facts as arrays of structs — joins vanish; scan only referenced sub-fields.
DON'T build `ARRAY<ARRAY<...>>`: arrays of arrays aren't allowed — wrap in a STRUCT. A result array can't hold NULL elements (errors); a NULL array persists as empty.
Types: exact decimals `NUMERIC`(P38,S9)/`BIGNUMERIC`(P76,S38); native `JSON` (dot/`[]` paths); `GEOGRAPHY`, `INTERVAL`, `RANGE<DATE|DATETIME|TIMESTAMP>` (lower-incl, upper-excl).

### Query features that cut scan or code
- `QUALIFY` filters on window-function output without a wrapping subquery.
- `SELECT * EXCEPT(a,b)` / `* REPLACE(expr AS c)` prune/patch wide columns inline.
- `PIVOT`/`UNPIVOT`; `TABLESAMPLE SYSTEM (n PERCENT)`; `WITH RECURSIVE`.
- `SAFE.`/`SAFE_CAST` make per-row errors NULL, not a failed scan; approx aggs (`APPROX_COUNT_DISTINCT`, `APPROX_QUANTILES`) for cheap high-cardinality stats.
DO parameterize with named `@p`/positional `?` (blocks SQL injection); identifiers (table/column/dataset names) CANNOT be parameters — allow-list them (see lore/databases.md).

### DML & upserts are batch, not row-at-a-time
DO upsert/dedup with one atomic `MERGE` (INSERT/UPDATE/DELETE), never per-row UPDATE. A MERGE matching >1 source row per target errors ("must match at most one source row") — dedup the source first.
Concurrency is partition-scoped: up to 2 mutating DML (UPDATE/DELETE/MERGE) run at once, up to 20 more queue as `PENDING`; conflicts (same partition) auto-retry up to 3×. INSERT never conflicts.
DON'T drip tiny INSERTs. Bulk-load via load jobs, or stream via the **Storage Write API** (default at-least-once; committed exactly-once; pending atomic batch) — recommended over and cheaper than the legacy `tabledata.insertAll` streaming API.

### Multi-statement transactions
`BEGIN`/`COMMIT`/`ROLLBACK TRANSACTION` give ACID **snapshot isolation** — reads see a consistent snapshot; `CURRENT_TIMESTAMP()` returns the tx start time. Conflicting transactions on one table are **cancelled** (standalone DML queues instead). Limits: ≤100 tables, ≤100k partition mods; no DDL on permanent objects; a failed tx rolls back, no retry. Multi-query only in **Session** mode.

### Table lifecycle features
- **Time travel**: query the last 7 days (configurable 2–7) via `FOR SYSTEM_TIME AS OF ts`; restore dropped tables. A non-queryable 7-day fail-safe follows.
- **Snapshots** (read-only, store only bytes differing from base) vs **clones** (mutable) — both cheap, sharing storage until diverged.
- **Materialized views**: incrementally auto-refreshed; BigQuery smart-tunes base-table queries to rewrite onto them. Restricted SQL, no DML.

### Sources
- cloud.google.com/bigquery/docs/reference/standard-sql/{query-syntax,data-types,dml-syntax}
- cloud.google.com/bigquery/docs/{data-manipulation-language,transactions,parameterized-queries}
- cloud.google.com/bigquery/docs/{write-api,time-travel,table-snapshots-intro,materialized-views-intro}

## Performance <a id="performance"></a>

Serverless columnar DW: cut **bytes processed** (on-demand, per TiB) or spend **slots** efficiently (capacity/editions). Ordered playbook; fix the biggest lever first, measure every change. Depth in the deep-dives. Pricing/editions evolve — verify live.

### 0. Measure first — bytes and slots
- DO **dry-run** first: `bq query --dry_run`, API `dryRun:true`, or the console validator. The byte estimate is an **upper bound**. Preview tables at **no charge** — never `SELECT *` to eyeball.
- DO read the **query plan / execution graph** (console execution details; `INFORMATION_SCHEMA.JOBS` → `total_bytes_billed`, `total_slot_ms`, per-stage rows). Estimated ≫ actual rows, or one stage hogging slot-time, ⇒ skew/shuffle. See lore/deep/databases.md#indexing-and-query-plans.
- DO cap spend: `maximum_bytes_billed` (over-cap query fails, **no charge**) + custom daily quotas per project/user.

### 1. Cut bytes processed — #1 on-demand lever
- DO **SELECT only needed columns** — columnar cost ≈ bytes in **referenced columns**, not rows; `SELECT * EXCEPT(a,b)` on a wide table.
- DON'T use `LIMIT`/preview as cost control: on non-clustered tables `LIMIT` **won't reduce bytes billed** (it prunes only on clustered tables).
- DO **partition** (time-unit / ingestion-time / integer-range) and filter the **bare** partition column so pruning fires (`require_partition_filter=TRUE` hard-stops full scans); DO **cluster** (≤4 cols, leftmost-prefix) so filters + `ORDER BY`/`LIMIT` skip blocks. Rules: lore/deep/bigquery.md#partitioning-and-clustering.

### 2. Precompute hot aggregates
- DO build **materialized views** for repeated aggregations — incrementally refreshed; the optimizer auto-rewrites base-table queries onto them.
- DO enable **BI Engine** (in-memory acceleration) for dashboards / low-latency repeated aggregations; pairs with materialized views + pre-aggregated tables. See lore/deep/bigquery.md#sql-and-features, lore/deep/bigquery.md#cost-and-slots.

### 3. Fix query shape — skew, shuffle, joins
- DO **pre-aggregate before a JOIN** and place the **largest table first**; `GROUP BY` and joins run on **shuffle**, where skew bites.
- DON'T self- or cross-join a large table; watch the plan for a **high-cardinality join**. Join on `INT64` keys over `STRING`; model one-to-many as ARRAY/STRUCT to remove joins (lore/deep/bigquery.md#sql-and-features).
- DO use **approximate aggregates** (`APPROX_COUNT_DISTINCT`, `APPROX_QUANTILES`, `APPROX_TOP_COUNT`) for high-cardinality stats — far cheaper than exact `COUNT(DISTINCT)` when small error is fine.

### 4. Right-size compute — on-demand vs capacity
- DO pick **on-demand** (per-TiB) for spiky/low volume; **capacity slots** for steady high concurrency. Commitments (1yr/3yr discount) are **Enterprise / Enterprise Plus only**; **Standard** is autoscaling pay-as-you-go. Reservation/autoscale/idle-slot mechanics: lore/deep/bigquery.md#cost-and-slots.

### 5. Move big data over the right pipe
- DO extract large table/result data with the **Storage Read API** (rpc, parallel streams, Avro/Arrow, column projection + filter) — not paginated `tabledata.list` or `SELECT *` dumps.
- DO **batch-load (free)** over streaming when latency allows; stream fresh rows via the **Storage Write API** (billed), never legacy `insertAll`. See lore/deep/bigquery.md#loading-and-streaming.

### Sources (docs.cloud.google.com/bigquery/docs/)
- best-practices-performance-compute · best-practices-costs
- materialized-views-intro · bi-engine-intro
- reference/storage · reference/standard-sql/approximate_aggregate_functions
- editions-intro
