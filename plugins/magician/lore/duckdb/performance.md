# DuckDB — Performance

Ordered playbook: fix the biggest lever first, measure every change. Current stable 1.5.4; 1.4.x LTS — verify version gates. This is the checklist; depth lives in the linked deep-dives, not restated here.

DuckDB is in-process and columnar: no server, no network hop for local files, so "cost" is local I/O + RAM + CPU. You go fast by scanning fewer bytes and keeping the working set inside the memory budget.

## 0. Measure first
- DO run `EXPLAIN ANALYZE <query>` — executes it and prints per-operator cumulative wall-clock time plus estimated (`EC`) vs actual rows; a big EC/actual gap ⇒ wrong join order/build side. Plain `EXPLAIN` shows the plan without running.
- DO profile deeper: `PRAGMA enable_profiling='json'` (+ `profiling_mode='detailed'`, `profiling_output='f.json'`). Inspect config via `SELECT * FROM duckdb_settings();`, spills via `FROM duckdb_temporary_files();`. Plan-reading depth: lore/databases/indexing-and-query-plans.md; memory metrics: lore/duckdb/performance-and-memory.md.

## 1. Scan less — the columnar win
- DO query Parquet/CSV directly (`FROM 'data/*.parquet'`), no import step — DuckDB applies projection pushdown (reads only named columns) and predicate pushdown (row-group zonemaps skip data). Never `SELECT *` on wide/remote files.
- DO sort/partition files by your filter columns (Hive dirs, `PARTITION_BY`) so predicates prune whole files/row groups; predicates on random columns scan everything. Formats depth: lore/duckdb/extensions-and-formats.md.

## 2. Load in bulk, never row-by-row
- DO ingest with `COPY`, `read_parquet`/`read_csv`, `CREATE TABLE AS SELECT`, `INSERT … SELECT`, or the Appender (C/C++/Go/Java/Rust…). Row-at-a-time `INSERT`s (even prepared) are "detrimental to performance" — ok only <100k rows; otherwise wrap in one transaction. Ingestion depth: lore/duckdb/usage-and-ingestion.md.

## 3. Right-size memory & threads
- DO set `memory_limit` (alias `max_memory`, default 80% RAM) and `threads` (default = CPU cores) on shared/containerized hosts — on low-RAM hosts cut `threads` so concurrent blocking operators don't each claim a memory slice and OOM.
- DO point `temp_directory` at fast scratch: blocking `GROUP BY`/`JOIN`/`ORDER BY`/window operators spill there for larger-than-memory queries (`max_temp_directory_size` default 90% of available disk). Holistic `list()`/`string_agg()` do NOT spill and can OOM.
- DO `SET preserve_insertion_order=false` (default true) for order-insensitive bulk import/export to cut peak RAM.

## 4. Keep the DB local, reuse the connection
- DO keep the `.duckdb` file on local SSD/NVMe (avoid NAS/network FS); persistent DBs compress on disk and can beat `:memory:`.
- DO reuse one connection — "DuckDB will perform best when reusing the same database connection many times"; the buffer + metadata cache is dropped when the last connection closes. A single long-lived connection stays warm; pool only if you must.
- DO minimize remote (`s3://`/`https://`) reads — synchronous IO, so raise `threads` to ~2–5× cores and push filters/projection to cut bytes and requests.

## Sources
- duckdb.org/docs/current/guides/performance/{how_to_tune_workloads,import,environment}
- duckdb.org/docs/current/guides/meta/explain_analyze · dev/profiling · configuration/overview
- duckdb.org/release_calendar (1.5.4 stable, 1.4.5 LTS)
