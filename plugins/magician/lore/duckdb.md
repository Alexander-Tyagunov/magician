# DuckDB — core digest
Version: 1.5.4 stable (2026-06), 1.4.x LTS. In-process columnar OLAP, no server. Storage stable since 1.0 (Jun 2024): new engines read old .duckdb; pin storage version when sharing.

DO think columnar: SELECT only needed columns; never SELECT * on wide tables — scan less.
DO ingest in bulk: COPY, read_parquet/read_csv_auto, or the Appender; never per-row INSERT loops (ok <100k rows).
DO order data by filter columns so auto zonemaps prune row groups — DuckDB scans with these, not indexes.
DO pick the tightest type (BIGINT/DATE/TIMESTAMP not VARCHAR): less RAM, faster joins, smaller files.
DO cap resources: SET memory_limit, threads; big ops spill to temp_directory; preserve_insertion_order=false cuts RAM.
DO store/exchange as Parquet; partition writes (PARTITION BY / Hive) on filter cols; upsert via INSERT ... ON CONFLICT.

DON'T add PK/UNIQUE/CREATE INDEX before bulk load (2-4x slower) — add ART indexes after, only for selective lookups.
DON'T open one .duckdb from multiple writers — one writer, many READ_ONLY readers; retry MVCC conflicts.
DON'T scatter tiny writes or per-row UPDATEs — stage & batch.

Deep dive when writing non-trivial DuckDB — read lore/duckdb/{usage-and-ingestion,performance,performance-and-memory,extensions-and-formats}.md

## Sources
duckdb.org/docs/current/guides/performance/{import,schema,indexing} · connect/concurrency · release_calendar
