# Amazon Redshift — Loading and maintenance

Managed cloud DW; SQL is Postgres-derived but **load and maintenance diverge sharply from PostgreSQL**. No user version — RA3 (managed storage, compute/storage split) and Serverless (RPU-hours) evolve; confirm current docs. OLAP rule: ingest in **batch** via `COPY`, never row-by-row. See `lore/databases.md`.

## Bulk load with COPY
- `COPY` is the most efficient load: one command reads **many files in parallel** across slices (MPP), sorting and distributing rows. `INSERT ... VALUES` row-at-a-time is far slower and fragments the table — never build a pipeline on it.
- File shape drives parallelism. Splittable inputs (uncompressed CSV; Parquet/ORC) **auto-split at 128 MB**; Parquet/ORC **under 128 MB don't split**. Non-splittable (JSON, GZIP-compressed CSV) must be **manually split** into similar-sized files of **1 MB–1 GB after compression**, count a **multiple of the slice count**.
- Compress with `GZIP`/`LZOP`/`BZIP2`/`ZSTD`; prefer typed Parquet. Load an exact file set with a **manifest**. Auth with `IAM_ROLE`, not keys.
- **One COPY per table** — concurrent COPYs into one table force a **serialized load** and a VACUUM afterward if it has a sort key.
- Into an **empty** table COPY auto-applies column encodings and runs `ANALYZE` (`COMPUPDATE`/`STATUPDATE` control it); `ENCODE AUTO` lets Redshift manage encodings.

## Continuous & streaming ingestion
- **auto-copy**: after an S3 event integration, `COPY t FROM 's3://…' IAM_ROLE '…' JOB CREATE my_job AUTO ON;` auto-loads new S3 files, **tracks loaded files (no dupes)**, batches per COPY. Defined once; manage via CREATE/LIST/SHOW/DROP/ALTER/RUN JOB, watch `SYS_COPY_JOB*`.
- **Streaming ingestion**: Kinesis Data Streams / MSK land directly into a **materialized view** (no S3 hop), low latency.
- **Data lake**: Spectrum external tables are read-only (no COPY/INSERT) — `INSERT INTO local SELECT …`, or zero-ETL from operational sources.

## Upserts — MERGE, not row DML
- Stage via COPY into a temp table, then `MERGE INTO target USING staging ON …`. Replace-all-columns = delete-by-inner-join + one insert (single target scan); use a column-list method for partial-column updates.
- Avoid per-row `UPDATE`/`DELETE`. `ALTER TABLE APPEND` moves rows without copying (fast) but fragments the target — follow with VACUUM DELETE.
- A **deep copy** (CTAS / `CREATE TABLE LIKE` + reload) can beat VACUUM for fully re-sorting a heavily unsorted table.

## VACUUM — very different from PostgreSQL
- Redshift VACUUM **re-sorts rows AND reclaims space**; the **default is `VACUUM FULL`** (Postgres' default just reclaims). Forms: `FULL | SORT ONLY | DELETE ONLY | REINDEX | RECLUSTER`, plus `TO n PERCENT`, `BOOST`.
- **Automatic** table sort and `VACUUM DELETE` run in the background at low load — you rarely run `DELETE ONLY` manually. Run manual `VACUUM (FULL|SORT ONLY)` after a big load when you need fully-sorted data.
- Skips the sort phase when **≥95% sorted** (default threshold; tune with `TO n PERCENT`). `REINDEX` re-analyzes interleaved sort keys (extra pass, slower). `RECLUSTER` sorts only the unsorted tail with no full merge — for large, frequently-ingested tables queried on recent data; **not on interleaved sort keys or `ALL` distribution**. `BOOST` uses extra resources but blocks concurrent update/delete — run at low load.
- **Can't VACUUM inside a transaction block.** Gauge need via `svv_table_info.unsorted` and `vacuum_sort_benefit`.

## ANALYZE & table design
- `ANALYZE` refreshes planner stats. **Automatic analyze** runs in background (`auto_analyze` on by default), skipping tables with `<10%` changed rows (`analyze_threshold_percent`). Use `ANALYZE … PREDICATE COLUMNS` to refresh only join/filter/group-by plus dist/sort columns.
- **Automatic Table Optimization**: tables with `DISTSTYLE AUTO` / `SORTKEY AUTO` get dist and sort keys applied automatically from observed workload (e.g. `AUTO`→`KEY`). Leave AUTO unless you have a proven better key.

## Sources
- https://docs.aws.amazon.com/redshift/latest/dg/t_Loading_data.html
- https://docs.aws.amazon.com/redshift/latest/dg/c_best-practices-use-multiple-files.html
- https://docs.aws.amazon.com/redshift/latest/dg/r_VACUUM_command.html
- https://docs.aws.amazon.com/redshift/latest/dg/t_Analyzing_tables.html
- https://docs.aws.amazon.com/redshift/latest/dg/loading-data-copy-job.html
- https://docs.aws.amazon.com/redshift/latest/dg/t_updating-inserting-using-staging-tables-.html
