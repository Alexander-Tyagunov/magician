# TimescaleDB — Performance

Version: 2.28.x stable — PostgreSQL 15-18 (last series to support PG15). Compression, retention, CAgg/job policies and data tiering are TSL/Community-licensed, NOT in Apache-2 core. 2.18+ rebranded compression "hypercore/columnstore"; legacy `compress`/`add_compression_policy` still work. Builds on lore/postgres/performance.md + lore/timescaledb/hypertables-and-modeling.md.

## Prioritized levers
1. Chunk sizing (`chunk_time_interval`). Size so indexes of chunks *currently being written* fit in ~25% of main memory (`shared_buffers`); else indexes spill to disk mid-ingest. Default 7 days. `set_chunk_time_interval` affects only NEW chunks. >1000 chunks slows planning, risks OOM.
2. Bound cardinality. No hard tag limit, but high-cardinality `segmentby` fragments the columnstore. Model dimensions as columns; segment only what you filter by.
3. Columnstore compression. `ALTER TABLE metrics SET (timescaledb.enable_columnstore, timescaledb.segmentby='device_id', timescaledb.orderby='ts DESC')` then `add_columnstore_policy('metrics', after => INTERVAL '7 days')` (legacy `compress*` settings still work). `segmentby` = low-cardinality equality/group cols; `orderby` = time. Batches ≤1000 rows; too-granular segmentby kills the ratio. Unlocks minmax/bloom sparse indexes, chunk-skipping, vectorized aggregates.
4. Downsample via continuous aggregates. Serve dashboards from a CAgg, not raw scans. `add_continuous_aggregate_policy(start_offset, end_offset, schedule_interval)` — keep `end_offset` behind now so recent buckets aren't re-materialized. Real-time aggregation is OFF by default (2.13+). Compress old CAgg chunks too.
5. Retention. `add_retention_policy('metrics', drop_after => INTERVAL '90 days')` uses `drop_chunks` — whole-chunk metadata drop (near-free, no bloat) vs row-by-row DELETE. Don't drop raw data a CAgg hasn't materialized yet.
6. Batch writes — multi-row INSERT / COPY, thousands of rows per statement; single-row inserts waste WAL + planning.

## Anti-patterns
- Sub-hour chunks on high-rate streams → thousands of chunks, slow planning, weak compression.
- High-cardinality `segmentby` (UUID / request id) → tiny batches, no compression win.
- No bounded time predicate → planner can't exclude chunks; every scan touches all.
- Hot-path DELETE/UPDATE on compressed chunks (decompress cost) — use retention/tiering instead.
- Apache-2 core lacks compression/CAggs (needs TSL build); object-storage tiering is Cloud-only.

## How to measure
- `EXPLAIN (ANALYZE, BUFFERS)` — confirm chunk exclusion + columnstore/vectorized nodes.
- `hypertable_columnstore_stats`/`hypertable_compression_stats`, `chunks_detailed_size`, `hypertable_detailed_size` — ratios + chunk sizes.
- `timescaledb_information.jobs` + `job_stats` + `job_errors` — policies succeeding, not lagging.
- `pg_stat_statements` for hot queries. See lore/databases/{resilience-and-observability,connection-pooling}.md.

## Sources
tigerdata.com/docs/use-timescale/latest/{hypertables,hypercore,continuous-aggregates,data-retention} · docs/learn/hypertables/sizing-hypertable-chunks · github.com/timescale/timescaledb/releases (2.28.x)
