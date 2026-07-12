# Snowflake — Storage, Clustering & Pruning

Managed cloud DW: no user version — editions (Standard/Enterprise/Business Critical) and rates evolve, confirm current. Compute = virtual-warehouse **credits** (per-second billing, 60s minimum per start; credits/hr double per size step — Small 2 → Medium 4 → Large 8 → 2XL 32; X-Small smallest). Storage = flat rate per TB of **compressed** bytes. The one OLAP lever: **scan fewer micro-partitions** so warehouses run shorter.

## Micro-partitions: automatic, immutable
Every table auto-splits into **micro-partitions** of ~50–500 MB *uncompressed* (stored compressed, per-column codec auto-chosen), rows **columnar**. You never create or size them. Each carries metadata: **min/max range per column** + distinct counts. They're immutable — any DML rewrites whole micro-partitions (old ones retained for Time Travel + Fail-safe); `DROP COLUMN` does **not** rewrite (dropped data lingers).

## Pruning is the whole game
Min/max metadata skips micro-partitions that can't match a predicate, then prunes columns within survivors — a filter hitting 10% of a range ideally scans ~10% of micro-partitions. Verify in **Query Profile**: *Partitions scanned* vs *Partitions total* on TableScan. Killers:
- Wrapping the filtered column in a function/cast (`WHERE CAST(c AS NUMBER)=2`, `UPPER(name)=…`) — transform the constant side instead, or cluster/search-optimize on an order-preserving expr.
- Predicates against a **subquery** don't prune, even if it returns a constant.
- `SELECT *` on wide tables defeats column pruning — project only needed columns.

## Natural vs. defined clustering
Data clusters **naturally by load order** — load files already sorted (e.g. by event date) and pruning often works for free. Add a **clustering key** only for large tables (docs: multi-**TB**, many micro-partitions, growing depth) queried selectively on the same key: `CREATE/ALTER TABLE … CLUSTER BY (expr[, …])`, `DROP CLUSTERING KEY`.
- Max **3–4 columns/exprs**; order **lowest→highest cardinality**; prioritize selective-filter then join columns.
- Avoid cardinality extremes: a Boolean prunes little; nanosecond timestamps over-fragment — use an order-preserving expr like `to_date(ts)`. `GEOGRAPHY/VARIANT/OBJECT/ARRAY` can't be keyed directly (VARIANT needs a typed path expr). Standard tables cluster on only the **first 5 bytes** of a VARCHAR.
- Inspect via `SYSTEM$CLUSTERING_INFORMATION` / `SYSTEM$CLUSTERING_DEPTH` (lower avg depth = better; 0 = empty); check `valid_for_clustering` before keying on a function.

## Automatic Clustering & when NOT to cluster
Reclustering is **serverless and automatic** (no warehouse) but **consumes credits** proportional to data reorganized, and rewrites micro-partitions → extra retained storage. **Don't** cluster small/sub-TB tables, high-churn tables (perpetual recluster cost — batch DML), or unique/point-lookup keys where cost outweighs benefit. Cluster only at a high query-to-DML ratio; baseline representative queries first.

## Search Optimization Service — pruning for point lookups
Complementary serverless feature: `ALTER TABLE t ADD SEARCH OPTIMIZATION`. Builds a maintained **search access path** tracking which values live in each micro-partition, so selective **point lookups**, equality/IN, substring/regex (`LIKE`/`RLIKE`), semi-structured, and geospatial queries skip most micro-partitions — where range-oriented clustering helps less. Costs storage + maintenance compute; enable per-table.

## Ingestion shapes storage
Bulk `COPY INTO` from staged files (or Snowpipe) yields well-formed micro-partitions; **many tiny row-at-a-time `INSERT`s fragment and churn them** — batch instead. Upserts use `MERGE`, not per-row updates.

## Sources
- docs.snowflake.com/en/user-guide/tables-clustering-micropartitions (micro-partitions, metadata, pruning, clustering depth)
- docs.snowflake.com/en/user-guide/tables-clustering-keys (CLUSTER BY, column count/order, cost, when-not, functions)
- docs.snowflake.com/en/user-guide/search-optimization-service (search access path, supported query types)
- docs.snowflake.com/en/user-guide/credits (credits, per-second billing, storage flat-rate, serverless/cloud-services)
