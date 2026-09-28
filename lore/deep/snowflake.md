# Snowflake — deep dive

> On-demand companion to `lore/snowflake.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Performance](#performance) · [Warehouses and cost](#warehouses-and-cost) · [Storage, Clustering & Pruning](#storage-clustering-and-pruning) · [Loading and streaming](#loading-and-streaming) · [Query features & Time Travel](#query-features-and-time-travel)

## Performance <a id="performance"></a>

Ordered playbook: two levers dominate — **scan fewer micro-partitions** and **keep warehouses busy then off**. Fix in this order; SEE each problem with the named tool. Managed cloud DW; editions gate features — verify current docs. Depth lives in the siblings; this is the checklist, not a restatement.

### 0. Measure first
- DO open the **Query Profile** (Snowsight, per query): compare *Partitions scanned* vs *Partitions total* on TableScan — a small ratio = good pruning. *Bytes spilled to local/remote storage* = the op outgrew memory → size up or batch smaller. See lore/deep/snowflake.md#storage-clustering-and-pruning.
- DO rank costly queries fleet-wide via the **Query History** page, `ACCOUNT_USAGE.QUERY_HISTORY` (view, 365-day) or `INFORMATION_SCHEMA.QUERY_HISTORY` (live table function); attribute credits with `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY`.
- DON'T tune from a plan on a tiny table.

### 1. Scan less (biggest lever)
- DO project only needed columns — `SELECT *` on wide tables defeats columnar pruning and inflates credits.
- DO write prunable predicates: filter on load-order-correlated columns; never wrap the column in a func/cast (transform the constant side); subquery-derived values don't prune.
- DO rely on **natural clustering** (load order); add a `CLUSTER BY` key only on large (multi-TB) tables queried off their load order, checking `SYSTEM$CLUSTERING_INFORMATION` — Automatic Clustering is serverless and costs credits. Rules: lore/deep/snowflake.md#storage-clustering-and-pruning.

### 2. Right-size + suspend the warehouse
- DO match size to query complexity, not data volume — larger isn't faster for simple queries; test on queries running ~5–10 min. Credits/hr double per size step (XS=1).
- DO set **AUTO_SUSPEND** low, aligned to workload gaps (e.g. 60s) — billing is per-second after a **60s minimum per start**; AUTO_RESUME is on by default. Never leave warehouses idle.
- DO isolate workloads (ETL vs BI) on separate warehouses to right-size + attribute cost; set **resource monitors**. See lore/deep/snowflake.md#warehouses-and-cost.

### 3. Exploit the caches
- DO reuse the **result cache**: a byte-identical query over unchanged data returns in ~0 compute for 24h (extended per reuse, max 31 days). Case/alias/whitespace diffs, `RANDOM`/`UUID_STRING`, external functions, and hybrid-table reads defeat it; toggle `USE_CACHED_RESULT` when benchmarking.
- The **warehouse-local (SSD) cache** speeds repeat scans but drops on suspend/resize — a real trade-off vs aggressive auto-suspend. See lore/deep/snowflake.md#query-features-and-time-travel.

### 4. Scale OUT for concurrency, not UP
- DO add a **multi-cluster warehouse** (Enterprise+, auto-scale MIN≠MAX) when queries **queue** under many concurrent users — a bigger warehouse does NOT fix concurrency. Reserve scale-up for large/complex queries or spilling. See lore/deep/snowflake.md#warehouses-and-cost.

### 5. Ingest bulk, write in batches
- DO bulk-load with `COPY INTO` from staged files (~100–250 MB compressed), **Snowpipe** for continuous file load, Snowpipe Streaming for low-latency rows.
- DON'T run row-at-a-time `INSERT`/`UPDATE` — each rewrites micro-partitions and fragments storage. Upsert with `MERGE`; drive incremental pipelines with Streams+Tasks or **dynamic tables** (`TARGET_LAG`). See lore/deep/snowflake.md#loading-and-streaming; cross-engine write batching: lore/databases.md.

### Sources
- https://docs.snowflake.com/en/user-guide/ui-query-profile
- https://docs.snowflake.com/en/user-guide/warehouses-considerations
- https://docs.snowflake.com/en/user-guide/querying-persisted-results
- https://docs.snowflake.com/en/user-guide/warehouses-multicluster
- https://docs.snowflake.com/en/sql-reference/account-usage/query_history

## Warehouses and cost <a id="warehouses-and-cost"></a>

Managed cloud DW: no user version, but editions/features/pricing evolve — verify current terms. Compute (**virtual warehouses**, in **credits**) and storage (compressed micro-partitions, per TB-month) bill separately. Optimize by scanning less and keeping compute wall-clock short.

### Sizing & billing
- Sizes are T-shirt (X-Small … 6X-Large); credits/hour **double each step**: XS=1, S=2, M=4, L=8, XL=16 … 6XL=512.
- Billing is **per-second, 60s minimum each time a warehouse starts** — no gain suspending before the first 60s.
- DO size to query complexity, not data volume: simple queries gain nothing from a huge warehouse.
- DO resize down freely. Resizing affects only queued/new queries, not those already running; new resources bill immediately.

### Suspend, resume, cache
- DO set **AUTO_SUSPEND** low (e.g. 60s) for bursty work, aligned to gaps so you don't thrash; consider disabling for a heavy steady stream. AUTO_RESUME (default on) restarts on the next statement.
- Each warehouse warms a **local disk cache**; suspend or resize **drops** it.
- **Result cache**: identical query text + unchanged data returns the prior result with **zero warehouse compute**, cached 24h. RANDOM/UUID_STRING and changed micro-partitions defeat it; toggle USE_CACHED_RESULT.

### Scale up vs scale out
- **Scale up** (resize): larger/complex queries or queuing from insufficient per-query resources. NOT for concurrency.
- **Scale out** (multi-cluster, **Enterprise+**): concurrency. Auto-scale (MIN≠MAX) starts clusters when queries queue, stops under low load. **Standard** policy favors starting clusters to avoid queuing; **Economy** keeps clusters loaded (starts only if ~6 min of work), trading latency for credits. Maximized (MIN=MAX>1) runs all clusters for steady high concurrency.

### Query Acceleration Service (Enterprise+)
Offloads large scans with selective filters, and big COPY/INSERT/UPDATE/DELETE, to serverless. **SCALE_FACTOR** caps leased compute as a multiple of warehouse size (default 8 explicit; 2 implicit on Gen2/multi-cluster; 0 = no cap). Billed **separately** as serverless credits.

### Micro-partitions, pruning, clustering
- Tables auto-split into immutable **micro-partitions (50–500 MB uncompressed)**; column min/max metadata drives **pruning**. DO filter on columns correlated with load order so partitions get skipped.
- DO add a **clustering key** only on large tables whose clustering degrades (check `SYSTEM$CLUSTERING_INFORMATION`). Automatic reclustering is **serverless and costs credits** — don't cluster small or churny tables.
- DON'T expect pruning on predicates with a subquery (not pruned).

### Ingestion & upserts (batch, not row-by-row)
- DO bulk-load via `COPY INTO` from staged files **~100–250 MB compressed** (split huge files; avoid 100 GB+; a load >24h may abort). Use **Snowpipe** (serverless) for continuous load, ~one file per minute.
- DON'T issue many tiny single-row INSERTs. Upsert with **MERGE**, not per-row UPDATE loops.

### Cost governance
- DO isolate workloads on separate warehouses (ETL vs BI) to right-size and attribute cost.
- DO set **resource monitors** (credit quota + NOTIFY / SUSPEND / SUSPEND_IMMEDIATE) per account or warehouse; use **budgets** for serverless. Audit via `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY`.
- Editions gate: multi-cluster, materialized views, QAS, and extended Time Travel (90 days) need **Enterprise+**.

### Sources
- https://docs.snowflake.com/en/user-guide/warehouses-overview
- https://docs.snowflake.com/en/user-guide/warehouses-considerations
- https://docs.snowflake.com/en/user-guide/warehouses-multicluster
- https://docs.snowflake.com/en/user-guide/query-acceleration-service
- https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions
- https://docs.snowflake.com/en/user-guide/resource-monitors

## Storage, Clustering & Pruning <a id="storage-clustering-and-pruning"></a>

Managed cloud DW: no user version — editions (Standard/Enterprise/Business Critical) and rates evolve, confirm current. Compute = virtual-warehouse **credits** (per-second billing, 60s minimum per start; credits/hr double per size step — Small 2 → Medium 4 → Large 8 → 2XL 32; X-Small smallest). Storage = flat rate per TB of **compressed** bytes. The one OLAP lever: **scan fewer micro-partitions** so warehouses run shorter.

### Micro-partitions: automatic, immutable
Every table auto-splits into **micro-partitions** of ~50–500 MB *uncompressed* (stored compressed, per-column codec auto-chosen), rows **columnar**. You never create or size them. Each carries metadata: **min/max range per column** + distinct counts. They're immutable — any DML rewrites whole micro-partitions (old ones retained for Time Travel + Fail-safe); `DROP COLUMN` does **not** rewrite (dropped data lingers).

### Pruning is the whole game
Min/max metadata skips micro-partitions that can't match a predicate, then prunes columns within survivors — a filter hitting 10% of a range ideally scans ~10% of micro-partitions. Verify in **Query Profile**: *Partitions scanned* vs *Partitions total* on TableScan. Killers:
- Wrapping the filtered column in a function/cast (`WHERE CAST(c AS NUMBER)=2`, `UPPER(name)=…`) — transform the constant side instead, or cluster/search-optimize on an order-preserving expr.
- Predicates against a **subquery** don't prune, even if it returns a constant.
- `SELECT *` on wide tables defeats column pruning — project only needed columns.

### Natural vs. defined clustering
Data clusters **naturally by load order** — load files already sorted (e.g. by event date) and pruning often works for free. Add a **clustering key** only for large tables (docs: multi-**TB**, many micro-partitions, growing depth) queried selectively on the same key: `CREATE/ALTER TABLE … CLUSTER BY (expr[, …])`, `DROP CLUSTERING KEY`.
- Max **3–4 columns/exprs**; order **lowest→highest cardinality**; prioritize selective-filter then join columns.
- Avoid cardinality extremes: a Boolean prunes little; nanosecond timestamps over-fragment — use an order-preserving expr like `to_date(ts)`. `GEOGRAPHY/VARIANT/OBJECT/ARRAY` can't be keyed directly (VARIANT needs a typed path expr). Standard tables cluster on only the **first 5 bytes** of a VARCHAR.
- Inspect via `SYSTEM$CLUSTERING_INFORMATION` / `SYSTEM$CLUSTERING_DEPTH` (lower avg depth = better; 0 = empty); check `valid_for_clustering` before keying on a function.

### Automatic Clustering & when NOT to cluster
Reclustering is **serverless and automatic** (no warehouse) but **consumes credits** proportional to data reorganized, and rewrites micro-partitions → extra retained storage. **Don't** cluster small/sub-TB tables, high-churn tables (perpetual recluster cost — batch DML), or unique/point-lookup keys where cost outweighs benefit. Cluster only at a high query-to-DML ratio; baseline representative queries first.

### Search Optimization Service — pruning for point lookups
Complementary serverless feature: `ALTER TABLE t ADD SEARCH OPTIMIZATION`. Builds a maintained **search access path** tracking which values live in each micro-partition, so selective **point lookups**, equality/IN, substring/regex (`LIKE`/`RLIKE`), semi-structured, and geospatial queries skip most micro-partitions — where range-oriented clustering helps less. Costs storage + maintenance compute; enable per-table.

### Ingestion shapes storage
Bulk `COPY INTO` from staged files (or Snowpipe) yields well-formed micro-partitions; **many tiny row-at-a-time `INSERT`s fragment and churn them** — batch instead. Upserts use `MERGE`, not per-row updates.

### Sources
- docs.snowflake.com/en/user-guide/tables-clustering-micropartitions (micro-partitions, metadata, pruning, clustering depth)
- docs.snowflake.com/en/user-guide/tables-clustering-keys (CLUSTER BY, column count/order, cost, when-not, functions)
- docs.snowflake.com/en/user-guide/search-optimization-service (search access path, supported query types)
- docs.snowflake.com/en/user-guide/credits (credits, per-second billing, storage flat-rate, serverless/cloud-services)

## Loading and streaming <a id="loading-and-streaming"></a>

Managed cloud DW (no user version; ingestion features/pricing evolve — verify current docs). Ingestion is **batch-first**: bulk-load staged files with `COPY INTO`, or stream with Snowpipe / Snowpipe Streaming. Row-at-a-time `INSERT ... VALUES` wastes compute and fragments micro-partitions — never build pipelines on it.

### Stages & file prep
- A **stage** holds files before load: **internal** (user `@~`, table `@%t`, named `@stg`; `PUT` uploads, auto-gzip) vs **external** (S3/GCS/Azure via a `STORAGE INTEGRATION` — prefer integrations over inline creds).
- DO size files **~100–250 MB compressed (or larger)**; aggregate tiny files, split huge ones. Avoid 100 GB+; a load running >24h may abort uncommitted. Parallelism is bounded by **file count** and warehouse size — one giant file can't parallelize.
- Prefer columnar **Parquet** for typed, compressed loads; define a reusable `FILE FORMAT` object.

### Bulk load: COPY INTO <table>
- `COPY INTO t FROM @stg` loads new files. Snowflake keeps **load metadata (~64 days)** and **skips already-loaded files** by path+checksum — so re-running is idempotent. `FORCE=TRUE` reloads all (risks duplicates); restaging a changed file makes a new checksum.
- DO set `ON_ERROR` deliberately: bulk default `ABORT_STATEMENT`; also `CONTINUE`, `SKIP_FILE`, `SKIP_FILE_<n>`/`<n>%`. Dry-run with `VALIDATION_MODE = RETURN_ERRORS`.
- Load semi-structured columns by name with `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` (order-independent), or transform inline: `COPY INTO t(c1) FROM (SELECT $1::int FROM @stg d)`. `PATTERN='.*\.parquet'` filters files; `PURGE=TRUE` deletes on success.

### Snowpipe (continuous, file-based)
- A **PIPE** wraps a COPY and loads files **serverlessly within minutes** of arrival. Automate with **cloud event notifications** (auto-ingest) over the polling REST endpoint; enable event filtering to cut noise/cost.
- Billed on **serverless compute Snowpipe consumes** (not your warehouse) + small per-file overhead — so file sizing still matters; stage roughly **one file per minute**. Load history lives in the pipe (~14 days); order is not guaranteed. Use bulk COPY **or** a pipe for a file set, never both (duplicates).

### Snowpipe Streaming (rows, seconds)
- Ingests **rows directly via SDK** (Java/Python/Node share a Rust core) or Kafka connector — no staged files — queryable in **seconds**. The current **high-performance architecture** centers on a server-side **PIPE**; the classic `snowflake-ingest-sdk` path is legacy/deprecating.
- **Exactly-once** via per-channel **offset tokens**; **ordered within a channel**. Billed **per uncompressed GB ingested**, not per file. Use for true low-latency event streams; if your source already writes files to blob storage, plain Snowpipe is cheaper.

### Upserts, Streams & Tasks
- DO upsert with `MERGE`, never per-row UPDATE loops.
- A **STREAM** is CDC: stores only an **offset** over a table's versioning and exposes changed rows (`METADATA$ACTION`, `METADATA$ISUPDATE`). Offset advances **only when consumed in a committed DML** (e.g. the MERGE) — querying alone doesn't. **One stream per consumer.** `APPEND_ONLY` streams are cheaper for insert-only ELT; streams go **stale** past source retention — recreate them.
- **TASKS** run scheduled/triggered SQL (gate with `WHEN SYSTEM$STREAM_HAS_DATA('s')` to fire only on change), chained into DAGs, on a warehouse or serverless.

### Dynamic tables (declarative pipelines)
- Prefer **dynamic tables** over hand-wired streams+tasks: declare a `SELECT` + `TARGET_LAG` (min **60s**, or `DOWNSTREAM`); Snowflake infers the DAG and refreshes **incrementally** when possible (`REFRESH_MODE AUTO/INCREMENTAL/FULL`). Billed as refresh warehouse compute + cloud services + storage. Not for sub-minute freshness or stored-proc/volatile logic.

### Sources
- https://docs.snowflake.com/en/user-guide/data-load-considerations-prepare
- https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
- https://docs.snowflake.com/en/user-guide/data-load-snowpipe-intro
- https://docs.snowflake.com/en/user-guide/data-load-snowpipe-streaming-overview
- https://docs.snowflake.com/en/user-guide/streams-intro
- https://docs.snowflake.com/en/user-guide/dynamic-tables-about

## Query features & Time Travel <a id="query-features-and-time-travel"></a>

Managed cloud DW: no user-installed version. Compute = virtual warehouses billed in **credits, per-second (60s minimum per resume)**; storage billed separately (incl. Time Travel + Fail-safe overhead). Behavior is edition-gated (Standard vs Enterprise+) and evolves — verify current docs.

### Scan-less querying (the cost lever)
Every table is auto-split into immutable **micro-partitions** (~50–500 MB uncompressed, stored columnar + compressed). Per-partition metadata (min/max range, distinct counts) drives **pruning**.

DO write predicates that prune: filter on columns correlated with load order; project only needed columns (columnar storage scans referenced columns only). `SELECT *` on wide tables defeats column pruning and inflates credits.
DO check what actually pruned: the query profile shows "partitions scanned / total". Aim to scan a small fraction.
DON'T expect pruning from a predicate whose value comes from a **subquery** — Snowflake does not prune on subquery-derived constants even when constant. Inline literals or use a join instead.

### Clustering (for very large tables)
Natural load order clusters data for free. Define an explicit key only when a big table is queried on a dimension uncorrelated with insert order and pruning has degraded:
```sql
ALTER TABLE events CLUSTER BY (event_date, tenant_id);
SELECT SYSTEM$CLUSTERING_INFORMATION('events', '(event_date, tenant_id)');
```
DO monitor `average_depth` (lower = better clustered). DON'T cluster small/churny tables — Automatic Clustering is a serverless, credit-consuming background service; the maintenance cost can exceed the scan savings. Choose low-to-moderate cardinality keys, most-selective first.

### Result cache & warehouse cache
Two distinct caches. **Result cache**: an identical query re-served with zero compute for 24h (each reuse extends up to 31 days from first run).
DO exploit it — reuse requires byte-identical query text (case, aliases, whitespace all matter), unchanged underlying micro-partitions, sufficient role privileges, and no non-deterministic functions (`RANDOM`, `UUID_STRING`, `RANDSTR`, external functions, hybrid tables).
DON'T assume it fired; toggle with `USE_CACHED_RESULT = FALSE` when benchmarking. Post-process a prior result without recompute:
```sql
SELECT $1 FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "rows" = 0;
```
The **warehouse-local (SSD) cache** holds recently scanned micro-partition data; it is lost on suspend/resize, so aggressive auto-suspend trades a cold cache for lower idle credits.

### Time Travel
`DATA_RETENTION_TIME_IN_DAYS`: Standard edition max **1** day; Enterprise+ permanent objects **0–90** days (0 disables). Extra retained versions cost storage.
```sql
SELECT * FROM t AT(TIMESTAMP => '2026-06-26 09:20:00'::timestamp_tz);
SELECT * FROM t AT(OFFSET => -60*5);              -- 5 minutes ago
SELECT * FROM t BEFORE(STATEMENT => '<query_id>'); -- just before a bad DML
CREATE TABLE t_restored CLONE t AT(OFFSET => -3600); -- zero-copy point-in-time clone
```
DO recover a dropped object with `UNDROP TABLE t;` (also SCHEMA/DATABASE); list droppable versions via `SHOW TABLES HISTORY;`. UNDROP fails if a same-named object exists — rename it first.
DON'T rely on Time Travel past the retention window: data then enters **Fail-safe** — a non-configurable 7-day period recoverable **only by Snowflake support** (best-effort, hours-to-days), not self-serve SQL. It also incurs storage cost, so it is not a query feature.

### Upserts, not row DML
Batch changes via `MERGE` / `INSERT` from staged files; avoid row-at-a-time `UPDATE`/`INSERT` loops (each rewrites micro-partitions). See `lore/deep/snowflake.md#loading-and-streaming` and `lore/databases.md`.

### Sources
- https://docs.snowflake.com/en/user-guide/data-time-travel
- https://docs.snowflake.com/en/user-guide/data-failsafe
- https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions
- https://docs.snowflake.com/en/user-guide/querying-persisted-results
- https://docs.snowflake.com/en/user-guide/warehouses-overview
