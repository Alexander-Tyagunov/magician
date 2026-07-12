# DuckDB — Performance & memory

Current stable 1.5.x ("Variegata", Mar 2026); 1.4.x is the LTS line (API stable since 1.0, Jun 2024). DuckDB is an in-process columnar engine sharing your host's RAM and CPU, so "cost" is local memory + CPU time — tune by scanning less and keeping the working set inside the memory budget. Check features with `PRAGMA version;`.

## Memory budget and threads
`memory_limit` (alias `max_memory`) defaults to **80% of physical RAM**; set it on shared/containerized hosts: `SET memory_limit = '10GB';`. `threads` defaults to the **CPU core count**. They interact: budget memory per thread. With 8 cores but 4 GB RAM, cut threads (`SET threads = 4;`) so concurrent blocking operators don't each claim a slice and OOM. In containers pin BOTH settings to the cgroup limits, not the host's.

## Larger-than-memory (out-of-core) and spilling
The blocking operators — `GROUP BY`, `JOIN`, `ORDER BY`, windowing (`OVER (PARTITION BY … ORDER BY …)`) — buffer their whole input and are the memory hogs, but each spills to disk. Temp files go to `temp_directory` (`⟨db⟩.tmp`, or `.tmp` in-memory), capped by `max_temp_directory_size` (default **90% of available disk**); point it at fast scratch: `SET temp_directory = '/nvme/duck.tmp';`. Spilling works in persistent and in-memory modes. Caveats: several blocking operators in one query can still OOM; holistic aggregates `list()`/`string_agg()` (and `PIVOT`, which builds a `list()`) buffer fully and do **not** offload. For bulk import/export near/over RAM, `SET preserve_insertion_order = false;` reorders unordered results and cuts peak memory sharply.

## Scan less: pruning, projection, pushdown
Columnar means projection is free money — never `SELECT *` on wide tables; name columns so unused ones are never read. On Parquet, DuckDB pushes filters/projections down and uses row-group stats to skip data, so **partition and sort files by your filter columns** (Hive dirs or `PARTITION_BY` on COPY): predicates on partition/sort keys prune whole files/row groups; predicates on random columns scan everything.

## Parallelism granularity
DuckDB parallelizes over **row groups** (default 122,880 rows): a query uses *k* threads only if it scans ≥ *k* × 122,880 rows, so small tables run single-threaded regardless of `threads`. For many small files or narrow row groups, tune `ROW_GROUP_SIZE` at write time.

## Ingestion is batch
Prefer bulk `COPY` / `INSERT … SELECT` / `read_parquet` / `read_csv` over row-at-a-time inserts; the Appender amortizes many rows (1.5 added a flush threshold to bound its memory). Thousands of tiny autocommit `INSERT`s each pay transaction + checkpoint overhead — batch into one transaction or one COPY.

## Storage & environment
Persistent DBs compress by default; in-memory tables do NOT — an on-disk or `ATTACH ':memory:' (COMPRESS)` DB is often *faster* and smaller than plain in-memory. Use SSD/NVMe (XFS or ext4; avoid NAS read-write). Prefer glibc builds — musl is >5× slower on compute-heavy work. On many-core hosts the bundled `jemalloc` background threads help release memory to the OS.

## Remote files
Reads use synchronous IO (one HTTP request per thread at a time), so for many small object-store requests raise `threads` **above** core count (~2–5×). Minimize bytes: avoid `SELECT *`, push filters, sort/partition remote Parquet by filter columns. Since 1.3.0 remote data is kept in an external file cache (reused across queries).

## Diagnosing
`EXPLAIN ANALYZE` shows per-operator time and cardinalities (1.5 adds a `TOTAL_MEMORY_ALLOCATED` metric); watch actual-vs-estimated rows on joins (bad estimates pick the wrong build side). Read config with `SELECT * FROM duckdb_settings();`, spill with `FROM duckdb_temporary_files();`.

## Sources
duckdb.org/docs/stable/guides/performance/how_to_tune_workloads · duckdb.org/docs/stable/guides/performance/environment · duckdb.org/docs/stable/configuration/overview · github.com/duckdb/duckdb/releases (v1.4.0, v1.5.0)
