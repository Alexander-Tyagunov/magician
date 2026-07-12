# Google BigQuery — Cost and Slots

Serverless managed DW: no user-installed version; dialect GoogleSQL. Two evolving billing models — verify current terms:
- **On-demand**: pay per **bytes scanned** (per TiB), with a **10 MiB minimum billed per query** and a **monthly free-tier of query bytes**. Compute uses transient burst slots under a per-project/org cap.
- **Capacity (editions)**: buy **slots** (virtual compute units) over time via **reservations** on the **Standard / Enterprise / Enterprise Plus** editions. Slot-time is billed; bytes scanned are not.

## Bytes-scanned is the on-demand lever (columnar)
DO select only needed columns — cost ≈ bytes in the **columns referenced**, not rows returned; `SELECT * EXCEPT(col)` to drop a few from a wide table.
DON'T `SELECT *` on wide tables, and DON'T use `LIMIT` as a cost control: on non-clustered tables it still reads all referenced bytes (LIMIT prunes only on clustered tables).
DO prune by partition — filter on the partition column or `_PARTITIONTIME`, and set `require_partition_filter` so unfiltered scans error; keep the column bare (no `DATE(func(col))`) or pruning is lost.
DO cluster hot tables so filters/`ORDER BY`+`LIMIT` skip blocks; pre-aggregate before joins; use `APPROX_COUNT_DISTINCT`/`APPROX_QUANTILES` for high-cardinality stats.

## Estimate and cap before you spend
DO dry-run nontrivial queries (`bq query --dry_run`, API `dryRun:true`, `QueryJobConfig(dry_run=True)`) — the estimate is an **upper bound**.
DO set `maximum_bytes_billed` (bq `--maximum_bytes_billed` / API `maximumBytesBilled`): a query over the cap **fails with no charge**. Add **custom daily query quotas** per project/user as a backstop.

## Free recompute avoidance
- **Query results cache** (**0 bytes billed**, ~24h): needs **byte-identical** text; skipped by non-deterministic funcs (`CURRENT_TIMESTAMP()`), wildcard tables, a destination table, streaming-fresh tables, or RLS. `--nouse_cache` forces fresh.
- **Materialized views** precompute + incrementally refresh aggregates; **BI Engine** gives in-memory dashboard acceleration.
- **CTEs (`WITH`) are for readability, not reuse** — a CTE may re-execute per reference; materialize hot intermediates to a temp table.

## Slots and editions (capacity)
DON'T issue many tiny `INSERT`s — batch via **load jobs** or the **Storage Write API**; use `MERGE` for upserts, not row-at-a-time UPDATE.
- **Reservations** hold **baseline** (always-on, always billed) + **autoscale** slots; autoscale steps in multiples of **50**, bills per-second with a **1-min minimum**, and scaled slots bill **even if the triggering query fails**.
- **Commitments** (1yr / 3yr) discount slots but can't be reduced mid-term; baseline over commitment bills PAYG.
- **Idle slots** auto-share within an edition/admin project (`ignore_idle_slots=true` to pin); **fair scheduling** splits across projects then jobs; queued/borrowed slots aren't billed extra.
- Autoscaling suits **heavy, concurrent** workloads, not one-off queries.
DO pick on-demand for spiky/low volume, capacity for steady high concurrency; assign reservations at folder/org level to avoid surprise on-demand spend.

## Storage cost note
Billed **active** vs **long-term** (untouched ~90 days, cheaper), under a per-dataset **logical** or **physical** (compressed) model — physical often wins on well-compressed data.

## Sources
- cloud.google.com/bigquery/pricing
- cloud.google.com/bigquery/docs/slots
- cloud.google.com/bigquery/docs/best-practices-costs
- cloud.google.com/bigquery/docs/best-practices-performance-compute
- cloud.google.com/bigquery/docs/cached-results
