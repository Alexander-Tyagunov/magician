# TimescaleDB — core digest
Version: 2.28; extension for PG 15-18 (13/14 legacy). Extends lore/postgres. Apache-2 = hypertables/chunks/time_bucket; TSL Community = columnstore compression, continuous aggregates, retention, jobs. S3 tiering = Tiger Cloud only.

DO make hypertables: CREATE TABLE ... WITH (tsdb.hypertable) (preferred), or create_hypertable('t', by_range('ts')) for existing tables (by_range since 2.13; 2-arg form legacy).
DO size chunk_time_interval so chunk + indexes fit ~25% RAM (default 7d; tune to ingest).
DO slice with time_bucket()/time_bucket_gapfill(); bound time range so chunks prune.
DO pre-aggregate with continuous aggregates + refresh policy; stack hierarchical CAggs.
DO columnstore (hypercore) old chunks via add_columnstore_policy: segmentby=filter cols, orderby=time.
DO expire raw rows with add_retention_policy after downsampling to CAggs.

DON'T put unbounded high-cardinality values (UUIDs, request IDs) in a space partition — chunk/planning bloat.
DON'T add a space dimension by default; only for parallel I/O — over-partitioning hurts.
DON'T mutate compressed chunks (UPDATE/DELETE/DDL) without decompress on older versions.

Deep dive for non-trivial work — read lore/timescaledb/{hypertables-and-modeling,continuous-aggregates-and-compression,performance}.md

## Sources
tigerdata.com/docs · timescaledb-editions · timescale/timescaledb 2.28.2
