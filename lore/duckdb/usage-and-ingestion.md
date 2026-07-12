# DuckDB — Usage & Ingestion

Stable 1.5.4 ("Variegata" line); 1.4.x is LTS ("Andium", 2025-09-16). `MERGE INTO` since 1.4.0; `filename` virtual column since 1.3.0. In-process/embedded: the engine runs in your process against one file (or `:memory:`) — no server, no round-trip.

## Load in bulk — never row-by-row
Point the vectorized reader at the files and let it parallelize:
```sql
CREATE TABLE t AS SELECT * FROM 'data/*.parquet';   -- CTAS, zero DDL
COPY t FROM 'data/*.parquet';                        -- append to existing table
COPY t FROM 'in.csv' (FORMAT csv, HEADER, DELIMITER '|');
```
`read_csv`/`read_parquet`/`read_json` (and bare `'file'`) take globs and lists: `read_parquet(['a/*.parquet','b/*.parquet'])`. DON'T emit thousands of single-row `INSERT`s — per-row parse/plan overhead makes loops "detrimental to performance"; below ~100k rows only. If forced, batch multi-row `VALUES` inside `BEGIN TRANSACTION`/`COMMIT` — auto-commit `fsync`s every statement.

## Appender for programmatic loads
When rows come from app code, use the **Appender** (C/C++/Go/Java/JDBC/Rust/Node.js/Julia), not prepared `INSERT`s. `AppendRow(...)` caches and auto-commits every 204,800 rows; `Flush()`/`Close()` (or scope exit) writes the rest — rows aren't visible until flushed. Binds to one table + one connection; reuse the connection (reconnecting drops cached metadata).

## Readers push down — scan less
Parquet gets **projection pushdown** (only referenced columns read) and **filter pushdown** (predicates skip row groups via zonemaps), so `SELECT a,b FROM 't.parquet' WHERE d='x'` reads a fraction — DON'T `SELECT *` on wide/remote files. `hive_partitioning` (auto) turns `k=v/` segments into prunable columns; `union_by_name=true` aligns differing schemas by name. Remote (`s3://`,`https://`) needs the `httpfs` extension and uses synchronous IO — one HTTP request per thread — so raise `threads` (2–5× cores) for many small objects, and filter to cut requests.

## Upserts: MERGE / ON CONFLICT, not UPDATE loops
```sql
INSERT INTO t VALUES (1,52) ON CONFLICT (id) DO UPDATE SET j = EXCLUDED.j;  -- needs a key
INSERT OR IGNORE INTO t ...;   INSERT OR REPLACE INTO t ...;                -- shorthands
MERGE INTO t USING src ON (src.id=t.id)                                      -- no PK required
  WHEN MATCHED THEN UPDATE SET j=src.j  WHEN NOT MATCHED THEN INSERT;
```
`INSERT INTO t BY NAME (SELECT ...)` matches by column name; `RETURNING *` (plus `merge_action` on MERGE) reports affected rows.

## Writing out & partitioning
```sql
COPY (SELECT * FROM t) TO 'out.parquet' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880);
COPY t TO 'lake' (FORMAT parquet, PARTITION_BY (year, month), OVERWRITE_OR_IGNORE);
```
Parquet default is `snappy` (also `zstd`/`gzip`/`brotli`/`lz4`; `COMPRESSION_LEVEL` for zstd). `PER_THREAD_OUTPUT`/`FILE_SIZE_BYTES` split output; `FILENAME_PATTERN` supports `{uuid}`/`{i}`.

## Config for big loads
- Parallelism keys off row groups (default 122,880 rows): a scan uses *k* threads only with ≥ *k*×122,880 rows; tune via `ATTACH '...' (ROW_GROUP_SIZE ...)`.
- `SET memory_limit='16GB'; SET threads=8;` — budget memory per thread; joins are heavier than aggregations, so cut `threads` if RAM is tight.
- Larger-than-memory GROUP BY/JOIN/ORDER BY/window spill to `SET temp_directory='...'` (SSD/NVMe); `list()`/`string_agg()` and holistic sort-aggregates DON'T spill and can OOM.
- OOM on order-insensitive import/export: `SET preserve_insertion_order=false`. Persistent DBs compress on disk (in-memory doesn't) — a disk DB can outrun `:memory:`.

## Transactions
Single-writer MVCC snapshot isolation over the file; writers from separate processes conflict. Treat DML as batch ops in explicit transactions, not OLTP per-row commits.

## Sources
- duckdb.org/docs/current/data/{overview,insert,appender} (readers, INSERT overhead, Appender batching/languages)
- duckdb.org/docs/current/sql/statements/{copy,insert,merge_into} (COPY options, ON CONFLICT/EXCLUDED, MERGE)
- duckdb.org/docs/current/data/parquet/overview, /guides/performance/{import,environment,how_to_tune_workloads} (pushdown, row groups, memory/threads/temp_directory, preserve_insertion_order)
- duckdb.org/release_calendar (1.5.4 stable, 1.4.x LTS, MERGE since 1.4.0)
