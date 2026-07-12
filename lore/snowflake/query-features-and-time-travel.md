# Snowflake — Query features & Time Travel

Managed cloud DW: no user-installed version. Compute = virtual warehouses billed in **credits, per-second (60s minimum per resume)**; storage billed separately (incl. Time Travel + Fail-safe overhead). Behavior is edition-gated (Standard vs Enterprise+) and evolves — verify current docs.

## Scan-less querying (the cost lever)
Every table is auto-split into immutable **micro-partitions** (~50–500 MB uncompressed, stored columnar + compressed). Per-partition metadata (min/max range, distinct counts) drives **pruning**.

DO write predicates that prune: filter on columns correlated with load order; project only needed columns (columnar storage scans referenced columns only). `SELECT *` on wide tables defeats column pruning and inflates credits.
DO check what actually pruned: the query profile shows "partitions scanned / total". Aim to scan a small fraction.
DON'T expect pruning from a predicate whose value comes from a **subquery** — Snowflake does not prune on subquery-derived constants even when constant. Inline literals or use a join instead.

## Clustering (for very large tables)
Natural load order clusters data for free. Define an explicit key only when a big table is queried on a dimension uncorrelated with insert order and pruning has degraded:
```sql
ALTER TABLE events CLUSTER BY (event_date, tenant_id);
SELECT SYSTEM$CLUSTERING_INFORMATION('events', '(event_date, tenant_id)');
```
DO monitor `average_depth` (lower = better clustered). DON'T cluster small/churny tables — Automatic Clustering is a serverless, credit-consuming background service; the maintenance cost can exceed the scan savings. Choose low-to-moderate cardinality keys, most-selective first.

## Result cache & warehouse cache
Two distinct caches. **Result cache**: an identical query re-served with zero compute for 24h (each reuse extends up to 31 days from first run).
DO exploit it — reuse requires byte-identical query text (case, aliases, whitespace all matter), unchanged underlying micro-partitions, sufficient role privileges, and no non-deterministic functions (`RANDOM`, `UUID_STRING`, `RANDSTR`, external functions, hybrid tables).
DON'T assume it fired; toggle with `USE_CACHED_RESULT = FALSE` when benchmarking. Post-process a prior result without recompute:
```sql
SELECT $1 FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "rows" = 0;
```
The **warehouse-local (SSD) cache** holds recently scanned micro-partition data; it is lost on suspend/resize, so aggressive auto-suspend trades a cold cache for lower idle credits.

## Time Travel
`DATA_RETENTION_TIME_IN_DAYS`: Standard edition max **1** day; Enterprise+ permanent objects **0–90** days (0 disables). Extra retained versions cost storage.
```sql
SELECT * FROM t AT(TIMESTAMP => '2026-06-26 09:20:00'::timestamp_tz);
SELECT * FROM t AT(OFFSET => -60*5);              -- 5 minutes ago
SELECT * FROM t BEFORE(STATEMENT => '<query_id>'); -- just before a bad DML
CREATE TABLE t_restored CLONE t AT(OFFSET => -3600); -- zero-copy point-in-time clone
```
DO recover a dropped object with `UNDROP TABLE t;` (also SCHEMA/DATABASE); list droppable versions via `SHOW TABLES HISTORY;`. UNDROP fails if a same-named object exists — rename it first.
DON'T rely on Time Travel past the retention window: data then enters **Fail-safe** — a non-configurable 7-day period recoverable **only by Snowflake support** (best-effort, hours-to-days), not self-serve SQL. It also incurs storage cost, so it is not a query feature.

## Upserts, not row DML
Batch changes via `MERGE` / `INSERT` from staged files; avoid row-at-a-time `UPDATE`/`INSERT` loops (each rewrites micro-partitions). See `lore/snowflake/loading-and-streaming.md` and `lore/databases.md`.

## Sources
- https://docs.snowflake.com/en/user-guide/data-time-travel
- https://docs.snowflake.com/en/user-guide/data-failsafe
- https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions
- https://docs.snowflake.com/en/user-guide/querying-persisted-results
- https://docs.snowflake.com/en/user-guide/warehouses-overview
