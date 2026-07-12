# Snowflake — Performance

Ordered playbook: two levers dominate — **scan fewer micro-partitions** and **keep warehouses busy then off**. Fix in this order; SEE each problem with the named tool. Managed cloud DW; editions gate features — verify current docs. Depth lives in the siblings; this is the checklist, not a restatement.

## 0. Measure first
- DO open the **Query Profile** (Snowsight, per query): compare *Partitions scanned* vs *Partitions total* on TableScan — a small ratio = good pruning. *Bytes spilled to local/remote storage* = the op outgrew memory → size up or batch smaller. See lore/snowflake/storage-clustering-and-pruning.md.
- DO rank costly queries fleet-wide via the **Query History** page, `ACCOUNT_USAGE.QUERY_HISTORY` (view, 365-day) or `INFORMATION_SCHEMA.QUERY_HISTORY` (live table function); attribute credits with `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY`.
- DON'T tune from a plan on a tiny table.

## 1. Scan less (biggest lever)
- DO project only needed columns — `SELECT *` on wide tables defeats columnar pruning and inflates credits.
- DO write prunable predicates: filter on load-order-correlated columns; never wrap the column in a func/cast (transform the constant side); subquery-derived values don't prune.
- DO rely on **natural clustering** (load order); add a `CLUSTER BY` key only on large (multi-TB) tables queried off their load order, checking `SYSTEM$CLUSTERING_INFORMATION` — Automatic Clustering is serverless and costs credits. Rules: lore/snowflake/storage-clustering-and-pruning.md.

## 2. Right-size + suspend the warehouse
- DO match size to query complexity, not data volume — larger isn't faster for simple queries; test on queries running ~5–10 min. Credits/hr double per size step (XS=1).
- DO set **AUTO_SUSPEND** low, aligned to workload gaps (e.g. 60s) — billing is per-second after a **60s minimum per start**; AUTO_RESUME is on by default. Never leave warehouses idle.
- DO isolate workloads (ETL vs BI) on separate warehouses to right-size + attribute cost; set **resource monitors**. See lore/snowflake/warehouses-and-cost.md.

## 3. Exploit the caches
- DO reuse the **result cache**: a byte-identical query over unchanged data returns in ~0 compute for 24h (extended per reuse, max 31 days). Case/alias/whitespace diffs, `RANDOM`/`UUID_STRING`, external functions, and hybrid-table reads defeat it; toggle `USE_CACHED_RESULT` when benchmarking.
- The **warehouse-local (SSD) cache** speeds repeat scans but drops on suspend/resize — a real trade-off vs aggressive auto-suspend. See lore/snowflake/query-features-and-time-travel.md.

## 4. Scale OUT for concurrency, not UP
- DO add a **multi-cluster warehouse** (Enterprise+, auto-scale MIN≠MAX) when queries **queue** under many concurrent users — a bigger warehouse does NOT fix concurrency. Reserve scale-up for large/complex queries or spilling. See lore/snowflake/warehouses-and-cost.md.

## 5. Ingest bulk, write in batches
- DO bulk-load with `COPY INTO` from staged files (~100–250 MB compressed), **Snowpipe** for continuous file load, Snowpipe Streaming for low-latency rows.
- DON'T run row-at-a-time `INSERT`/`UPDATE` — each rewrites micro-partitions and fragments storage. Upsert with `MERGE`; drive incremental pipelines with Streams+Tasks or **dynamic tables** (`TARGET_LAG`). See lore/snowflake/loading-and-streaming.md; cross-engine write batching: lore/databases.md.

## Sources
- https://docs.snowflake.com/en/user-guide/ui-query-profile
- https://docs.snowflake.com/en/user-guide/warehouses-considerations
- https://docs.snowflake.com/en/user-guide/querying-persisted-results
- https://docs.snowflake.com/en/user-guide/warehouses-multicluster
- https://docs.snowflake.com/en/sql-reference/account-usage/query_history
