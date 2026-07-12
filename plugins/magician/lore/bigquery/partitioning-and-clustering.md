# Google BigQuery — Partitioning & Clustering

Serverless DW: no user version. On-demand cost = **bytes scanned per TiB** (first 1 TiB/month free; **10 MiB min billed per referenced table and per query**); capacity mode bills **slots** (Standard / Enterprise / Enterprise Plus editions). Scan less — that's the game. GoogleSQL. Pricing/editions evolve — confirm live.

## Partitioning — one column, prunes bytes

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

## Clustering — sorts within blocks, up to 4 columns

`CLUSTER BY` sorts data into blocks by **up to 4 columns**; **order matters** — blocks prune only on a **leftmost prefix** (`c1`, `c1,c2`, …); filtering `c2` alone won't prune. Types: `INT64`, `STRING` (first **1024 chars** only), `BOOL`, `DATE`, `DATETIME`, `TIMESTAMP`, `NUMERIC`, `BIGNUMERIC`, `GEOGRAPHY`, `RANGE`.

```sql
CREATE TABLE ds.events (id INT64, ts TIMESTAMP, region STRING, uid INT64)
PARTITION BY DATE(ts)
CLUSTER BY region, uid;      -- partition first, then cluster within each partition
```

DO order cluster columns most-filtered-first to match query prefixes. DO cluster tables/partitions **> ~64 MB** (below that, one block — no gain). **Automatic reclustering** re-sorts blocks as you load — free, no slot charge, per-partition.

DON'T expect an accurate cost estimate before running a clustered query — block count is unknown until execution (unlike partition pruning). DON'T rely on `LIMIT` to cut cost on an unclustered table (it doesn't); on a clustered table `LIMIT` can reduce blocks scanned.

## Cost hygiene

DO `--dry_run` (`QueryJobConfig.dry_run`) to see bytes before paying; cap `maximum_bytes_billed`. DO select only needed columns — columnar storage means `SELECT *` on a wide table reads every column. A partition untouched **90 consecutive days** auto-drops to long-term storage pricing.

## Sources
- docs.cloud.google.com/bigquery/docs/partitioned-tables · /clustered-tables
- docs.cloud.google.com/bigquery/quotas · /docs/best-practices-costs
