# TimescaleDB — deep dive

> On-demand companion to `lore/timescaledb.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Hypertables & Modeling](#hypertables-and-modeling) · [Continuous Aggregates & Compression](#continuous-aggregates-and-compression) · [Performance](#performance)

## Hypertables & Modeling <a id="hypertables-and-modeling"></a>

Version: extension 2.x on PostgreSQL 15-18 (13/14 legacy) (`\dx timescaledb`). A hypertable is a regular PG table auto-partitioned into **chunks** by a time column; INSERT/SELECT it like any table (standard SQL — lore/postgres.md applies). Multi-node removed in 2.14; space partitioning is legacy.

### Create
Declarative form (since 2.20; from 2.23 omit `partition_column` to auto-pick the first timestamp column — errors if several are ambiguous):
```sql
CREATE TABLE conditions (
  time timestamptz NOT NULL,
  device text NOT NULL,
  temp  double precision
) WITH (tsdb.hypertable, tsdb.partition_column='time', tsdb.chunk_interval='1 day');
```
Classic builder (still supported):
```sql
SELECT create_hypertable('conditions', by_range('time', INTERVAL '1 day'));
```
`chunk_time_interval` defaults to **7 days**. `set_chunk_time_interval('conditions', INTERVAL '1 day')` retunes future chunks only — never rewrites existing.

### DO
- Size chunks so the **active (most-recent) chunk + its indexes fit in ~25% of RAM**: too small = planning overhead, too large = memory pressure + coarse retention. Start ~1 day.
- Keep the time column `NOT NULL`; write **batched, roughly time-ordered** inserts (COPY / multi-row INSERT), not row-at-a-time.
- Include the partitioning column in every **PRIMARY KEY / UNIQUE** index — Timescale rejects one that omits `time`.
- Add composite indexes for per-entity reads, e.g. `(device, time DESC)`; a `(time DESC)` index is auto-created.
- Model low-cardinality dimensions (device, region, type) as columns — they become `segmentby` keys for compression and cheap filters.
- Query bounded time ranges so the planner does **chunk exclusion** (prunes chunks).

### DON'T
- Don't space-partition (`add_dimension` / `by_hash`) reflexively — on a single node it rarely parallelizes I/O, just multiplies chunks; never hash a high-cardinality id (user/uuid/request) to "shard".
- Don't over-index write-heavy hypertables; every index is maintained per chunk.
- Don't dedupe on non-time columns alone via `UNIQUE` — it can't exist without the partitioning column.
- Don't create a hypertable→hypertable FK (the only unsupported case); regular↔hypertable FKs (either direction) work.
- Don't expect `chunk_time_interval` edits or most `ALTER`s to touch old chunks — choose it up front.

### Cardinality & downstream design
`segmentby`/`orderby` are set at model time; pick `segmentby` = the low-cardinality column you filter on most. Downsample with continuous aggregates and expire raw data via `add_retention_policy(relation, drop_after => INTERVAL '30 days')` (keep the cagg longer). Only hypertables, chunks, and `time_bucket` are Apache-2.0; continuous aggregates, compression, and retention are Community(TSL); tiering to object storage is **Tiger/Timescale Cloud-only** — confirm your edition.

See lore/deep/timescaledb.md#{continuous-aggregates-and-compression,performance}.

### Sources
- tigerdata.com/docs/use-timescale — hypertables, create_hypertable, add_dimension, tiering (Cloud)
- tigerdata.com/docs/api — add_retention_policy, add_columnstore_policy
- lore/postgres.md · lore/databases.md

## Continuous Aggregates & Compression <a id="continuous-aggregates-and-compression"></a>

Current 2.x; Community/TSL features (free, no DBaaS) — data tiering is Tiger/Timescale Cloud only. Policies run as TimescaleDB **background jobs** — size `timescaledb.max_background_workers` + PG `max_worker_processes` or they silently queue. Complements lore/postgres.md.

### Continuous aggregates (incremental rollups)
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

### Columnstore compression (hypercore)
Convert cold chunks rowstore→columnstore: 90–98% shrink, fast columnar scans.
```sql
ALTER TABLE metrics SET (
  timescaledb.enable_columnstore,
  timescaledb.segmentby = 'device_id',
  timescaledb.orderby   = 'ts DESC');
SELECT add_columnstore_policy('metrics', after => INTERVAL '7 days');
```
(Older aliases: `timescaledb.compress`, `compress_segmentby/orderby`, `add_compression_policy`.)
DO set `segmentby` = the low-cardinality columns you filter/group on — many tiny segments wreck ratio and scans; never an unbounded id (→ cardinality in lore/deep/timescaledb.md#hypertables-and-modeling). `orderby` (default time DESC) = your WHERE/ORDER BY cols so batches prune.
DO run INSERT/UPDATE/DELETE/UPSERT on columnstore chunks (modern 2.x); `convert_to_rowstore`/`convert_to_columnstore` for one-offs; `minmax`+`bloom` sparse indexes prune scans.
DON'T bake keys late: `segmentby`/`orderby` are fixed at conversion — changing them needs re-conversion.

### Retention & tiering
`SELECT add_retention_policy('metrics', drop_after => INTERVAL '90 days');` drops whole chunks (metadata-only, not a big `DELETE`). One per hypertable/CAgg.
DO order the lifecycle: compress first; keep raw `drop_after` LONGER than the CAgg refresh window — dropping raw the CAgg hasn't materialized loses it.
Data tiering (`add_tiering_policy`, read via `timescaledb.enable_tiered_reads`) offloads cold chunks to S3/Parquet — **Tiger Cloud only**; no DML on tiered chunks. Perf → lore/deep/timescaledb.md#performance.

### Sources
- tigerdata.com/docs/use-timescale/latest/continuous-aggregates (about/real-time/hierarchical)
- tigerdata.com/docs/api/latest/{continuous-aggregates,hypercore,data-retention} (signatures)
- tigerdata.com/docs/use-timescale/latest/{compression,data-tiering}; Timescale License (TSL)

## Performance <a id="performance"></a>

Version: 2.28.x stable — PostgreSQL 15-18 (last series to support PG15). Compression, retention, CAgg/job policies and data tiering are TSL/Community-licensed, NOT in Apache-2 core. 2.18+ rebranded compression "hypercore/columnstore"; legacy `compress`/`add_compression_policy` still work. Builds on lore/deep/postgres.md#performance + lore/deep/timescaledb.md#hypertables-and-modeling.

### Prioritized levers
1. Chunk sizing (`chunk_time_interval`). Size so indexes of chunks *currently being written* fit in ~25% of main memory (`shared_buffers`); else indexes spill to disk mid-ingest. Default 7 days. `set_chunk_time_interval` affects only NEW chunks. >1000 chunks slows planning, risks OOM.
2. Bound cardinality. No hard tag limit, but high-cardinality `segmentby` fragments the columnstore. Model dimensions as columns; segment only what you filter by.
3. Columnstore compression. `ALTER TABLE metrics SET (timescaledb.enable_columnstore, timescaledb.segmentby='device_id', timescaledb.orderby='ts DESC')` then `add_columnstore_policy('metrics', after => INTERVAL '7 days')` (legacy `compress*` settings still work). `segmentby` = low-cardinality equality/group cols; `orderby` = time. Batches ≤1000 rows; too-granular segmentby kills the ratio. Unlocks minmax/bloom sparse indexes, chunk-skipping, vectorized aggregates.
4. Downsample via continuous aggregates. Serve dashboards from a CAgg, not raw scans. `add_continuous_aggregate_policy(start_offset, end_offset, schedule_interval)` — keep `end_offset` behind now so recent buckets aren't re-materialized. Real-time aggregation is OFF by default (2.13+). Compress old CAgg chunks too.
5. Retention. `add_retention_policy('metrics', drop_after => INTERVAL '90 days')` uses `drop_chunks` — whole-chunk metadata drop (near-free, no bloat) vs row-by-row DELETE. Don't drop raw data a CAgg hasn't materialized yet.
6. Batch writes — multi-row INSERT / COPY, thousands of rows per statement; single-row inserts waste WAL + planning.

### Anti-patterns
- Sub-hour chunks on high-rate streams → thousands of chunks, slow planning, weak compression.
- High-cardinality `segmentby` (UUID / request id) → tiny batches, no compression win.
- No bounded time predicate → planner can't exclude chunks; every scan touches all.
- Hot-path DELETE/UPDATE on compressed chunks (decompress cost) — use retention/tiering instead.
- Apache-2 core lacks compression/CAggs (needs TSL build); object-storage tiering is Cloud-only.

### How to measure
- `EXPLAIN (ANALYZE, BUFFERS)` — confirm chunk exclusion + columnstore/vectorized nodes.
- `hypertable_columnstore_stats`/`hypertable_compression_stats`, `chunks_detailed_size`, `hypertable_detailed_size` — ratios + chunk sizes.
- `timescaledb_information.jobs` + `job_stats` + `job_errors` — policies succeeding, not lagging.
- `pg_stat_statements` for hot queries. See lore/deep/databases.md#{resilience-and-observability,connection-pooling}.

### Sources
tigerdata.com/docs/use-timescale/latest/{hypertables,hypercore,continuous-aggregates,data-retention} · docs/learn/hypertables/sizing-hypertable-chunks · github.com/timescale/timescaledb/releases (2.28.x)
