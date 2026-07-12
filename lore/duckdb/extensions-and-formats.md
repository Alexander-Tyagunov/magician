# DuckDB — Extensions & Formats

Targets the 1.x line (1.0 GA Jun 2024; verify the current 1.3+ point release — feature gates below note their version). Extensions are versioned to the engine: after upgrading DuckDB, re-resolve them.

## Extension lifecycle
- `INSTALL httpfs; LOAD httpfs;` — `INSTALL` downloads to the local extension dir (once per version); `LOAD` activates it for the session. Known extensions **autoload** on first use, so a plain `SELECT * FROM 's3://…'` or `read_json(...)` pulls `httpfs`/`json` automatically — explicit `INSTALL`/`LOAD` is only needed offline, when autoload is disabled, or for a pinned repo.
- Core extensions (`httpfs`, `parquet`, `json`, `icu`, `spatial`, `iceberg`, `delta`, `postgres`, `mysql`, `sqlite`, `excel`, `fts`, `vss`, …) ship from the official repo; `parquet`/`json`/`icu`/`httpfs` are Primary-tier and statically linked in most builds.
- Community extensions: `INSTALL <name> FROM community; LOAD <name>;` — signed/built by the community CI but not DuckDB-maintained, so vet them. Lock them out with `SET allow_community_extensions = false;` (irreversible for the session).
- `UPDATE EXTENSIONS;` refreshes installed extensions; `FORCE INSTALL name;` re-downloads a corrupt/stale copy. Load unsigned local builds only with `allow_unsigned_extensions` set at startup.

## Parquet — the default interchange format
- Read: `SELECT col_a, col_b FROM 'data/*.parquet';` — the `read_parquet`/`parquet_scan` wrapper is implicit for `.parquet`. Never `SELECT *` on wide files: DuckDB does **projection pushdown** (reads only referenced column chunks) and **predicate pushdown** via per-row-group zonemaps (min/max stats) to skip whole groups — a `WHERE` on a sorted/clustered column is what makes scans cheap.
- Glob a dir, a list, or mixed: `read_parquet(['a/*.parquet','b/*.parquet'])`. Track source rows with the `filename` virtual column (auto since v1.3.0): `SELECT *, filename FROM 'part/*.parquet'`.
- `hive_partitioning => true` (auto-detected) turns `year=2024/month=1/…` path segments into queryable columns and prunes directories by predicate. `union_by_name => true` aligns files with differing/added columns by name not position (cannot combine with an explicit `schema`).
- Write: `COPY (SELECT …) TO 'out.parquet' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880);`. Default codec is Snappy; ZSTD (with `COMPRESSION_LEVEL`) usually wins size/scan. Row groups too small = metadata overhead; too large = coarse pruning.

## Partitioned & remote writes
- `COPY tbl TO 'orders' (FORMAT parquet, PARTITION_BY (year, month));` emits a Hive tree `year=…/month=…/data_0.parquet`. One file is written **per thread per directory**, so partitions hold multiple files — expected, not a bug.
- `FILENAME_PATTERN 'orders_{i}'` or `'{uuid}'` names outputs; `OVERWRITE`/`OVERWRITE_OR_IGNORE` clears an existing dir (local only — remote FS rejects overwrite); `APPEND` adds UUID-named files safely. Tune `SET partitioned_write_max_open_files` and aim for ≥~100 MB per partition; over-partitioning produces tiny-file sprawl.

## JSON, CSV, and object stores
- `read_json`/`read_ndjson` (autoloaded `json`). Set `format => 'array'` vs `'newline_delimited'`, and pass `columns => {…}` to pin schema instead of paying for sampling on big feeds. JSON `->` returns JSON, `->>` returns VARCHAR; note JSON-type indexing is **0-based** while LIST/ARRAY are 1-based.
- S3/GCS/R2 via `httpfs`: authenticate with the Secrets manager, not env-only. `CREATE SECRET (TYPE s3, PROVIDER credential_chain);` uses the AWS SDK chain (env, SSO, instance role); or `PROVIDER config, KEY_ID …, SECRET …, REGION …` for explicit keys. Then read/glob/`COPY … TO 's3://…'` directly. Prefer bulk `COPY`/staged files — never row-by-row INSERT over the network.

## Lakehouse tables
- `iceberg` and `delta` read table snapshots (metadata + manifest driven), giving pruning and time-travel over object storage; treat DuckDB as the scan engine and let the table format own layout. Write support lags read — check current extension docs before relying on DuckDB to mutate a managed table.

## Sources
- https://duckdb.org/docs/stable/core_extensions/overview
- https://duckdb.org/docs/stable/data/parquet/overview
- https://duckdb.org/docs/stable/data/partitioning/partitioned_writes
- https://duckdb.org/docs/stable/core_extensions/httpfs/s3api
- https://duckdb.org/community_extensions/
