# BigQuery — core digest
Version: serverless managed DW; no version. Compute: on-demand (per TiB processed; ~1 TiB/mo free) or Editions slots (autoscaling; 1/3yr commits on Enterprise[+]). GoogleSQL recommended; legacy SQL available (migrate). Storage: active/long-term (90d→~half). Terms evolve — verify.

DO SELECT only needed columns (bills bytes processed); never SELECT *; LIMIT/preview won't cut cost.
DO partition (time-unit/ingestion-time/integer-range) AND cluster (<=4 cols, order matters) to prune partitions + blocks.
DO filter the bare partition column; require_partition_filter to force; dry-run to estimate bytes.
DO batch-load (free) when latency allows; stream fresh rows via Storage Write API; big extracts via Storage Read API.
DO upsert via MERGE (not per-row UPDATE); nest data as ARRAY/STRUCT; materialized views/BI Engine for hot aggregates.

DON'T drip tiny INSERTs/loads or legacy insertAll when batch fits — cost + quota churn.
DON'T make thousands of micro-partitions (<~10 GB): metadata overhead; cluster instead.
DON'T rely on legacy SQL or per-row transactions — snapshot isolation, table-level DML limits.

Deep dive — read lore/bigquery/{cost-and-slots,partitioning-and-clustering,loading-and-streaming,sql-and-features,performance}.md

## Sources
cloud.google.com/bigquery/pricing · docs/partitioned-tables · docs/loading-data · docs/introduction-sql
