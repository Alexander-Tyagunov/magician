# DuckDB — deep dive

> On-demand companion to `lore/duckdb.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Usage & Ingestion](#usage-and-ingestion) · [Performance](#performance) · [Performance & memory](#performance-and-memory) · [Extensions & Formats](#extensions-and-formats)

## Usage & Ingestion <a id="usage-and-ingestion"></a>

Stable 1.5.4 ("Variegata" line); 1.4.x is LTS ("Andium", 2025-09-16). `MERGE INTO` since 1.4.0; `filename` virtual column since 1.3.0. In-process/embedded: the engine runs in your process against one file (or `:memory:`) — no server, no round-trip.

### Load in bulk — never row-by-row
Point the vectorized reader at the files and let it parallelize:
```sql
CREATE TABLE t AS SELECT * FROM 'data/*.parquet';   -- CTAS, zero DDL
COPY t FROM 'data/*.parquet';                        -- append to existing table
COPY t FROM 'in.csv' (FORMAT csv, HEADER, DELIMITER '|');
```
`read_csv`/`read_parquet`/`read_json` (and bare `'file'`) take globs and lists: `read_parquet(['a/*.parquet','b/*.parquet'])`. DON'T emit thousands of single-row `INSERT`s — per-row parse/plan overhead makes loops "detrimental to performance"; below ~100k rows only. If forced, batch multi-row `VALUES` inside `BEGIN TRANSACTION`/`COMMIT` — auto-commit `fsync`s every statement.

### Appender for programmatic loads
When rows come from app code, use the **Appender** (C/C++/Go/Java/JDBC/Rust/Node.js/Julia), not prepared `INSERT`s. `AppendRow(...)` caches and auto-commits every 204,800 rows; `Flush()`/`Close()` (or scope exit) writes the rest — rows aren't visible until flushed. Binds to one table + one connection; reuse the connection (reconnecting drops cached metadata).

### Readers push down — scan less
Parquet gets **projection pushdown** (only referenced columns read) and **filter pushdown** (predicates skip row groups via zonemaps), so `SELECT a,b FROM 't.parquet' WHERE d='x'` reads a fraction — DON'T `SELECT *` on wide/remote files. `hive_partitioning` (auto) turns `k=v/` segments into prunable columns; `union_by_name=true` aligns differing schemas by name. Remote (`s3://`,`https://`) needs the `httpfs` extension and uses synchronous IO — one HTTP request per thread — so raise `threads` (2–5× cores) for many small objects, and filter to cut requests.

### Upserts: MERGE / ON CONFLICT, not UPDATE loops
```sql
INSERT INTO t VALUES (1,52) ON CONFLICT (id) DO UPDATE SET j = EXCLUDED.j;  -- needs a key
INSERT OR IGNORE INTO t ...;   INSERT OR REPLACE INTO t ...;                -- shorthands
MERGE INTO t USING src ON (src.id=t.id)                                      -- no PK required
  WHEN MATCHED THEN UPDATE SET j=src.j  WHEN NOT MATCHED THEN INSERT;
```
`INSERT INTO t BY NAME (SELECT ...)` matches by column name; `RETURNING *` (plus `merge_action` on MERGE) reports affected rows.

### Writing out & partitioning
```sql
COPY (SELECT * FROM t) TO 'out.parquet' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880);
COPY t TO 'lake' (FORMAT parquet, PARTITION_BY (year, month), OVERWRITE_OR_IGNORE);
```
Parquet default is `snappy` (also `zstd`/`gzip`/`brotli`/`lz4`; `COMPRESSION_LEVEL` for zstd). `PER_THREAD_OUTPUT`/`FILE_SIZE_BYTES` split output; `FILENAME_PATTERN` supports `{uuid}`/`{i}`.

### Config for big loads
- Parallelism keys off row groups (default 122,880 rows): a scan uses *k* threads only with ≥ *k*×122,880 rows; tune via `ATTACH '...' (ROW_GROUP_SIZE ...)`.
- `SET memory_limit='16GB'; SET threads=8;` — budget memory per thread; joins are heavier than aggregations, so cut `threads` if RAM is tight.
- Larger-than-memory GROUP BY/JOIN/ORDER BY/window spill to `SET temp_directory='...'` (SSD/NVMe); `list()`/`string_agg()` and holistic sort-aggregates DON'T spill and can OOM.
- OOM on order-insensitive import/export: `SET preserve_insertion_order=false`. Persistent DBs compress on disk (in-memory doesn't) — a disk DB can outrun `:memory:`.

### Transactions
Single-writer MVCC snapshot isolation over the file; writers from separate processes conflict. Treat DML as batch ops in explicit transactions, not OLTP per-row commits.

### Sources
- duckdb.org/docs/current/data/{overview,insert,appender} (readers, INSERT overhead, Appender batching/languages)
- duckdb.org/docs/current/sql/statements/{copy,insert,merge_into} (COPY options, ON CONFLICT/EXCLUDED, MERGE)
- duckdb.org/docs/current/data/parquet/overview, /guides/performance/{import,environment,how_to_tune_workloads} (pushdown, row groups, memory/threads/temp_directory, preserve_insertion_order)
- duckdb.org/release_calendar (1.5.4 stable, 1.4.x LTS, MERGE since 1.4.0)

## Performance <a id="performance"></a>

Ordered playbook: fix the biggest lever first, measure every change. Current stable 1.5.4; 1.4.x LTS — verify version gates. This is the checklist; depth lives in the linked deep-dives, not restated here.

DuckDB is in-process and columnar: no server, no network hop for local files, so "cost" is local I/O + RAM + CPU. You go fast by scanning fewer bytes and keeping the working set inside the memory budget.

### 0. Measure first
- DO run `EXPLAIN ANALYZE <query>` — executes it and prints per-operator cumulative wall-clock time plus estimated (`EC`) vs actual rows; a big EC/actual gap ⇒ wrong join order/build side. Plain `EXPLAIN` shows the plan without running.
- DO profile deeper: `PRAGMA enable_profiling='json'` (+ `profiling_mode='detailed'`, `profiling_output='f.json'`). Inspect config via `SELECT * FROM duckdb_settings();`, spills via `FROM duckdb_temporary_files();`. Plan-reading depth: lore/deep/databases.md#indexing-and-query-plans; memory metrics: lore/deep/duckdb.md#performance-and-memory.

### 1. Scan less — the columnar win
- DO query Parquet/CSV directly (`FROM 'data/*.parquet'`), no import step — DuckDB applies projection pushdown (reads only named columns) and predicate pushdown (row-group zonemaps skip data). Never `SELECT *` on wide/remote files.
- DO sort/partition files by your filter columns (Hive dirs, `PARTITION_BY`) so predicates prune whole files/row groups; predicates on random columns scan everything. Formats depth: lore/deep/duckdb.md#extensions-and-formats.

### 2. Load in bulk, never row-by-row
- DO ingest with `COPY`, `read_parquet`/`read_csv`, `CREATE TABLE AS SELECT`, `INSERT … SELECT`, or the Appender (C/C++/Go/Java/Rust…). Row-at-a-time `INSERT`s (even prepared) are "detrimental to performance" — ok only <100k rows; otherwise wrap in one transaction. Ingestion depth: lore/deep/duckdb.md#usage-and-ingestion.

### 3. Right-size memory & threads
- DO set `memory_limit` (alias `max_memory`, default 80% RAM) and `threads` (default = CPU cores) on shared/containerized hosts — on low-RAM hosts cut `threads` so concurrent blocking operators don't each claim a memory slice and OOM.
- DO point `temp_directory` at fast scratch: blocking `GROUP BY`/`JOIN`/`ORDER BY`/window operators spill there for larger-than-memory queries (`max_temp_directory_size` default 90% of available disk). Holistic `list()`/`string_agg()` do NOT spill and can OOM.
- DO `SET preserve_insertion_order=false` (default true) for order-insensitive bulk import/export to cut peak RAM.

### 4. Keep the DB local, reuse the connection
- DO keep the `.duckdb` file on local SSD/NVMe (avoid NAS/network FS); persistent DBs compress on disk and can beat `:memory:`.
- DO reuse one connection — "DuckDB will perform best when reusing the same database connection many times"; the buffer + metadata cache is dropped when the last connection closes. A single long-lived connection stays warm; pool only if you must.
- DO minimize remote (`s3://`/`https://`) reads — synchronous IO, so raise `threads` to ~2–5× cores and push filters/projection to cut bytes and requests.

### Sources
- duckdb.org/docs/current/guides/performance/{how_to_tune_workloads,import,environment}
- duckdb.org/docs/current/guides/meta/explain_analyze · dev/profiling · configuration/overview
- duckdb.org/release_calendar (1.5.4 stable, 1.4.5 LTS)

## Performance & memory <a id="performance-and-memory"></a>

Current stable 1.5.x ("Variegata", Mar 2026); 1.4.x is the LTS line (API stable since 1.0, Jun 2024). DuckDB is an in-process columnar engine sharing your host's RAM and CPU, so "cost" is local memory + CPU time — tune by scanning less and keeping the working set inside the memory budget. Check features with `PRAGMA version;`.

### Memory budget and threads
`memory_limit` (alias `max_memory`) defaults to **80% of physical RAM**; set it on shared/containerized hosts: `SET memory_limit = '10GB';`. `threads` defaults to the **CPU core count**. They interact: budget memory per thread. With 8 cores but 4 GB RAM, cut threads (`SET threads = 4;`) so concurrent blocking operators don't each claim a slice and OOM. In containers pin BOTH settings to the cgroup limits, not the host's.

### Larger-than-memory (out-of-core) and spilling
The blocking operators — `GROUP BY`, `JOIN`, `ORDER BY`, windowing (`OVER (PARTITION BY … ORDER BY …)`) — buffer their whole input and are the memory hogs, but each spills to disk. Temp files go to `temp_directory` (`⟨db⟩.tmp`, or `.tmp` in-memory), capped by `max_temp_directory_size` (default **90% of available disk**); point it at fast scratch: `SET temp_directory = '/nvme/duck.tmp';`. Spilling works in persistent and in-memory modes. Caveats: several blocking operators in one query can still OOM; holistic aggregates `list()`/`string_agg()` (and `PIVOT`, which builds a `list()`) buffer fully and do **not** offload. For bulk import/export near/over RAM, `SET preserve_insertion_order = false;` reorders unordered results and cuts peak memory sharply.

### Scan less: pruning, projection, pushdown
Columnar means projection is free money — never `SELECT *` on wide tables; name columns so unused ones are never read. On Parquet, DuckDB pushes filters/projections down and uses row-group stats to skip data, so **partition and sort files by your filter columns** (Hive dirs or `PARTITION_BY` on COPY): predicates on partition/sort keys prune whole files/row groups; predicates on random columns scan everything.

### Parallelism granularity
DuckDB parallelizes over **row groups** (default 122,880 rows): a query uses *k* threads only if it scans ≥ *k* × 122,880 rows, so small tables run single-threaded regardless of `threads`. For many small files or narrow row groups, tune `ROW_GROUP_SIZE` at write time.

### Ingestion is batch
Prefer bulk `COPY` / `INSERT … SELECT` / `read_parquet` / `read_csv` over row-at-a-time inserts; the Appender amortizes many rows (1.5 added a flush threshold to bound its memory). Thousands of tiny autocommit `INSERT`s each pay transaction + checkpoint overhead — batch into one transaction or one COPY.

### Storage & environment
Persistent DBs compress by default; in-memory tables do NOT — an on-disk or `ATTACH ':memory:' (COMPRESS)` DB is often *faster* and smaller than plain in-memory. Use SSD/NVMe (XFS or ext4; avoid NAS read-write). Prefer glibc builds — musl is >5× slower on compute-heavy work. On many-core hosts the bundled `jemalloc` background threads help release memory to the OS.

### Remote files
Reads use synchronous IO (one HTTP request per thread at a time), so for many small object-store requests raise `threads` **above** core count (~2–5×). Minimize bytes: avoid `SELECT *`, push filters, sort/partition remote Parquet by filter columns. Since 1.3.0 remote data is kept in an external file cache (reused across queries).

### Diagnosing
`EXPLAIN ANALYZE` shows per-operator time and cardinalities (1.5 adds a `TOTAL_MEMORY_ALLOCATED` metric); watch actual-vs-estimated rows on joins (bad estimates pick the wrong build side). Read config with `SELECT * FROM duckdb_settings();`, spill with `FROM duckdb_temporary_files();`.

### Sources
duckdb.org/docs/stable/guides/performance/how_to_tune_workloads · duckdb.org/docs/stable/guides/performance/environment · duckdb.org/docs/stable/configuration/overview · github.com/duckdb/duckdb/releases (v1.4.0, v1.5.0)

## Extensions & Formats <a id="extensions-and-formats"></a>

Targets the 1.x line (1.0 GA Jun 2024; verify the current 1.3+ point release — feature gates below note their version). Extensions are versioned to the engine: after upgrading DuckDB, re-resolve them.

### Extension lifecycle
- `INSTALL httpfs; LOAD httpfs;` — `INSTALL` downloads to the local extension dir (once per version); `LOAD` activates it for the session. Known extensions **autoload** on first use, so a plain `SELECT * FROM 's3://…'` or `read_json(...)` pulls `httpfs`/`json` automatically — explicit `INSTALL`/`LOAD` is only needed offline, when autoload is disabled, or for a pinned repo.
- Core extensions (`httpfs`, `parquet`, `json`, `icu`, `spatial`, `iceberg`, `delta`, `postgres`, `mysql`, `sqlite`, `excel`, `fts`, `vss`, …) ship from the official repo; `parquet`/`json`/`icu`/`httpfs` are Primary-tier and statically linked in most builds.
- Community extensions: `INSTALL <name> FROM community; LOAD <name>;` — signed/built by the community CI but not DuckDB-maintained, so vet them. Lock them out with `SET allow_community_extensions = false;` (irreversible for the session).
- `UPDATE EXTENSIONS;` refreshes installed extensions; `FORCE INSTALL name;` re-downloads a corrupt/stale copy. Load unsigned local builds only with `allow_unsigned_extensions` set at startup.

### Parquet — the default interchange format
- Read: `SELECT col_a, col_b FROM 'data/*.parquet';` — the `read_parquet`/`parquet_scan` wrapper is implicit for `.parquet`. Never `SELECT *` on wide files: DuckDB does **projection pushdown** (reads only referenced column chunks) and **predicate pushdown** via per-row-group zonemaps (min/max stats) to skip whole groups — a `WHERE` on a sorted/clustered column is what makes scans cheap.
- Glob a dir, a list, or mixed: `read_parquet(['a/*.parquet','b/*.parquet'])`. Track source rows with the `filename` virtual column (auto since v1.3.0): `SELECT *, filename FROM 'part/*.parquet'`.
- `hive_partitioning => true` (auto-detected) turns `year=2024/month=1/…` path segments into queryable columns and prunes directories by predicate. `union_by_name => true` aligns files with differing/added columns by name not position (cannot combine with an explicit `schema`).
- Write: `COPY (SELECT …) TO 'out.parquet' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880);`. Default codec is Snappy; ZSTD (with `COMPRESSION_LEVEL`) usually wins size/scan. Row groups too small = metadata overhead; too large = coarse pruning.

### Partitioned & remote writes
- `COPY tbl TO 'orders' (FORMAT parquet, PARTITION_BY (year, month));` emits a Hive tree `year=…/month=…/data_0.parquet`. One file is written **per thread per directory**, so partitions hold multiple files — expected, not a bug.
- `FILENAME_PATTERN 'orders_{i}'` or `'{uuid}'` names outputs; `OVERWRITE`/`OVERWRITE_OR_IGNORE` clears an existing dir (local only — remote FS rejects overwrite); `APPEND` adds UUID-named files safely. Tune `SET partitioned_write_max_open_files` and aim for ≥~100 MB per partition; over-partitioning produces tiny-file sprawl.

### JSON, CSV, and object stores
- `read_json`/`read_ndjson` (autoloaded `json`). Set `format => 'array'` vs `'newline_delimited'`, and pass `columns => {…}` to pin schema instead of paying for sampling on big feeds. JSON `->` returns JSON, `->>` returns VARCHAR; note JSON-type indexing is **0-based** while LIST/ARRAY are 1-based.
- S3/GCS/R2 via `httpfs`: authenticate with the Secrets manager, not env-only. `CREATE SECRET (TYPE s3, PROVIDER credential_chain);` uses the AWS SDK chain (env, SSO, instance role); or `PROVIDER config, KEY_ID …, SECRET …, REGION …` for explicit keys. Then read/glob/`COPY … TO 's3://…'` directly. Prefer bulk `COPY`/staged files — never row-by-row INSERT over the network.

### Lakehouse tables
- `iceberg` and `delta` read table snapshots (metadata + manifest driven), giving pruning and time-travel over object storage; treat DuckDB as the scan engine and let the table format own layout. Write support lags read — check current extension docs before relying on DuckDB to mutate a managed table.

### Sources
- https://duckdb.org/docs/stable/core_extensions/overview
- https://duckdb.org/docs/stable/data/parquet/overview
- https://duckdb.org/docs/stable/data/partitioning/partitioned_writes
- https://duckdb.org/docs/stable/core_extensions/httpfs/s3api
- https://duckdb.org/community_extensions/
