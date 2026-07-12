# Google BigQuery — Performance

Serverless columnar DW: cut **bytes processed** (on-demand, per TiB) or spend **slots** efficiently (capacity/editions). Ordered playbook; fix the biggest lever first, measure every change. Depth in the deep-dives. Pricing/editions evolve — verify live.

## 0. Measure first — bytes and slots
- DO **dry-run** first: `bq query --dry_run`, API `dryRun:true`, or the console validator. The byte estimate is an **upper bound**. Preview tables at **no charge** — never `SELECT *` to eyeball.
- DO read the **query plan / execution graph** (console execution details; `INFORMATION_SCHEMA.JOBS` → `total_bytes_billed`, `total_slot_ms`, per-stage rows). Estimated ≫ actual rows, or one stage hogging slot-time, ⇒ skew/shuffle. See lore/databases/indexing-and-query-plans.md.
- DO cap spend: `maximum_bytes_billed` (over-cap query fails, **no charge**) + custom daily quotas per project/user.

## 1. Cut bytes processed — #1 on-demand lever
- DO **SELECT only needed columns** — columnar cost ≈ bytes in **referenced columns**, not rows; `SELECT * EXCEPT(a,b)` on a wide table.
- DON'T use `LIMIT`/preview as cost control: on non-clustered tables `LIMIT` **won't reduce bytes billed** (it prunes only on clustered tables).
- DO **partition** (time-unit / ingestion-time / integer-range) and filter the **bare** partition column so pruning fires (`require_partition_filter=TRUE` hard-stops full scans); DO **cluster** (≤4 cols, leftmost-prefix) so filters + `ORDER BY`/`LIMIT` skip blocks. Rules: lore/bigquery/partitioning-and-clustering.md.

## 2. Precompute hot aggregates
- DO build **materialized views** for repeated aggregations — incrementally refreshed; the optimizer auto-rewrites base-table queries onto them.
- DO enable **BI Engine** (in-memory acceleration) for dashboards / low-latency repeated aggregations; pairs with materialized views + pre-aggregated tables. See lore/bigquery/sql-and-features.md, cost-and-slots.md.

## 3. Fix query shape — skew, shuffle, joins
- DO **pre-aggregate before a JOIN** and place the **largest table first**; `GROUP BY` and joins run on **shuffle**, where skew bites.
- DON'T self- or cross-join a large table; watch the plan for a **high-cardinality join**. Join on `INT64` keys over `STRING`; model one-to-many as ARRAY/STRUCT to remove joins (lore/bigquery/sql-and-features.md).
- DO use **approximate aggregates** (`APPROX_COUNT_DISTINCT`, `APPROX_QUANTILES`, `APPROX_TOP_COUNT`) for high-cardinality stats — far cheaper than exact `COUNT(DISTINCT)` when small error is fine.

## 4. Right-size compute — on-demand vs capacity
- DO pick **on-demand** (per-TiB) for spiky/low volume; **capacity slots** for steady high concurrency. Commitments (1yr/3yr discount) are **Enterprise / Enterprise Plus only**; **Standard** is autoscaling pay-as-you-go. Reservation/autoscale/idle-slot mechanics: lore/bigquery/cost-and-slots.md.

## 5. Move big data over the right pipe
- DO extract large table/result data with the **Storage Read API** (rpc, parallel streams, Avro/Arrow, column projection + filter) — not paginated `tabledata.list` or `SELECT *` dumps.
- DO **batch-load (free)** over streaming when latency allows; stream fresh rows via the **Storage Write API** (billed), never legacy `insertAll`. See lore/bigquery/loading-and-streaming.md.

## Sources (docs.cloud.google.com/bigquery/docs/)
- best-practices-performance-compute · best-practices-costs
- materialized-views-intro · bi-engine-intro
- reference/storage · reference/standard-sql/approximate_aggregate_functions
- editions-intro
