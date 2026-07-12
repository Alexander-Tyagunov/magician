# Snowflake — Warehouses and cost

Managed cloud DW: no user version, but editions/features/pricing evolve — verify current terms. Compute (**virtual warehouses**, in **credits**) and storage (compressed micro-partitions, per TB-month) bill separately. Optimize by scanning less and keeping compute wall-clock short.

## Sizing & billing
- Sizes are T-shirt (X-Small … 6X-Large); credits/hour **double each step**: XS=1, S=2, M=4, L=8, XL=16 … 6XL=512.
- Billing is **per-second, 60s minimum each time a warehouse starts** — no gain suspending before the first 60s.
- DO size to query complexity, not data volume: simple queries gain nothing from a huge warehouse.
- DO resize down freely. Resizing affects only queued/new queries, not those already running; new resources bill immediately.

## Suspend, resume, cache
- DO set **AUTO_SUSPEND** low (e.g. 60s) for bursty work, aligned to gaps so you don't thrash; consider disabling for a heavy steady stream. AUTO_RESUME (default on) restarts on the next statement.
- Each warehouse warms a **local disk cache**; suspend or resize **drops** it.
- **Result cache**: identical query text + unchanged data returns the prior result with **zero warehouse compute**, cached 24h. RANDOM/UUID_STRING and changed micro-partitions defeat it; toggle USE_CACHED_RESULT.

## Scale up vs scale out
- **Scale up** (resize): larger/complex queries or queuing from insufficient per-query resources. NOT for concurrency.
- **Scale out** (multi-cluster, **Enterprise+**): concurrency. Auto-scale (MIN≠MAX) starts clusters when queries queue, stops under low load. **Standard** policy favors starting clusters to avoid queuing; **Economy** keeps clusters loaded (starts only if ~6 min of work), trading latency for credits. Maximized (MIN=MAX>1) runs all clusters for steady high concurrency.

## Query Acceleration Service (Enterprise+)
Offloads large scans with selective filters, and big COPY/INSERT/UPDATE/DELETE, to serverless. **SCALE_FACTOR** caps leased compute as a multiple of warehouse size (default 8 explicit; 2 implicit on Gen2/multi-cluster; 0 = no cap). Billed **separately** as serverless credits.

## Micro-partitions, pruning, clustering
- Tables auto-split into immutable **micro-partitions (50–500 MB uncompressed)**; column min/max metadata drives **pruning**. DO filter on columns correlated with load order so partitions get skipped.
- DO add a **clustering key** only on large tables whose clustering degrades (check `SYSTEM$CLUSTERING_INFORMATION`). Automatic reclustering is **serverless and costs credits** — don't cluster small or churny tables.
- DON'T expect pruning on predicates with a subquery (not pruned).

## Ingestion & upserts (batch, not row-by-row)
- DO bulk-load via `COPY INTO` from staged files **~100–250 MB compressed** (split huge files; avoid 100 GB+; a load >24h may abort). Use **Snowpipe** (serverless) for continuous load, ~one file per minute.
- DON'T issue many tiny single-row INSERTs. Upsert with **MERGE**, not per-row UPDATE loops.

## Cost governance
- DO isolate workloads on separate warehouses (ETL vs BI) to right-size and attribute cost.
- DO set **resource monitors** (credit quota + NOTIFY / SUSPEND / SUSPEND_IMMEDIATE) per account or warehouse; use **budgets** for serverless. Audit via `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY`.
- Editions gate: multi-cluster, materialized views, QAS, and extended Time Travel (90 days) need **Enterprise+**.

## Sources
- https://docs.snowflake.com/en/user-guide/warehouses-overview
- https://docs.snowflake.com/en/user-guide/warehouses-considerations
- https://docs.snowflake.com/en/user-guide/warehouses-multicluster
- https://docs.snowflake.com/en/user-guide/query-acceleration-service
- https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions
- https://docs.snowflake.com/en/user-guide/resource-monitors
