# TimescaleDB — Continuous Aggregates & Compression

Current 2.x; Community/TSL features (free, no DBaaS) — data tiering is Tiger/Timescale Cloud only. Policies run as TimescaleDB **background jobs** — size `timescaledb.max_background_workers` + PG `max_worker_processes` or they silently queue. Complements lore/postgres.

## Continuous aggregates (incremental rollups)
A CAgg is a hypertable auto-maintained from a `time_bucket()` GROUP BY — the downsampling primitive.
```sql
CREATE MATERIALIZED VIEW metrics_1h WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', ts) AS bucket, device_id, avg(val), max(val)
FROM metrics GROUP BY bucket, device_id WITH NO DATA;
SELECT add_continuous_aggregate_policy('metrics_1h',
  start_offset => INTERVAL '3 days',
  end_offset   => INTERVAL '1 hour',   -- skips the still-writing bucket
  schedule_interval => INTERVAL '1 hour');
```
DO create `WITH NO DATA`, keep `start_offset` > `end_offset`, and `end_offset` ≥ one bucket so it never re-refreshes the hot bucket; DON'T set `end_offset => NULL`.
DO enable real-time aggregation (`SET (timescaledb.materialized_only=false)`) for current reads — UNIONs materialized with raw past `end_offset` (OFF since 2.13).
DO stack **hierarchical** CAggs (daily on the hourly CAgg). Backfill: `CALL refresh_continuous_aggregate('metrics_1h', start, end);` — a procedure (can't run in a txn block); batches since 2.28.
DON'T use window functions, `DISTINCT ON`, or non-aggregate output in the definition — bucket first, apply window funcs when *querying* (JOINs are version-gated: INNER 2.10+, LEFT 2.16+).

## Columnstore compression (hypercore)
Convert cold chunks rowstore→columnstore: 90–98% shrink, fast columnar scans.
```sql
ALTER TABLE metrics SET (
  timescaledb.enable_columnstore,
  timescaledb.segmentby = 'device_id',
  timescaledb.orderby   = 'ts DESC');
SELECT add_columnstore_policy('metrics', after => INTERVAL '7 days');
```
(Older aliases: `timescaledb.compress`, `compress_segmentby/orderby`, `add_compression_policy`.)
DO set `segmentby` = the low-cardinality columns you filter/group on — many tiny segments wreck ratio and scans; never an unbounded id (→ cardinality in hypertables-and-modeling.md). `orderby` (default time DESC) = your WHERE/ORDER BY cols so batches prune.
DO run INSERT/UPDATE/DELETE/UPSERT on columnstore chunks (modern 2.x); `convert_to_rowstore`/`convert_to_columnstore` for one-offs; `minmax`+`bloom` sparse indexes prune scans.
DON'T bake keys late: `segmentby`/`orderby` are fixed at conversion — changing them needs re-conversion.

## Retention & tiering
`SELECT add_retention_policy('metrics', drop_after => INTERVAL '90 days');` drops whole chunks (metadata-only, not a big `DELETE`). One per hypertable/CAgg.
DO order the lifecycle: compress first; keep raw `drop_after` LONGER than the CAgg refresh window — dropping raw the CAgg hasn't materialized loses it.
Data tiering (`add_tiering_policy`, read via `timescaledb.enable_tiered_reads`) offloads cold chunks to S3/Parquet — **Tiger Cloud only**; no DML on tiered chunks. Perf → lore/timescaledb/performance.md.

## Sources
- tigerdata.com/docs/use-timescale/latest/continuous-aggregates (about/real-time/hierarchical)
- tigerdata.com/docs/api/latest/{continuous-aggregates,hypercore,data-retention} (signatures)
- tigerdata.com/docs/use-timescale/latest/{compression,data-tiering}; Timescale License (TSL)
