# Amazon Redshift — deep dive

> On-demand companion to `lore/redshift.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Distribution & Sort Keys](#distribution-and-sort-keys) · [Loading and maintenance](#loading-and-maintenance) · [Performance playbook](#performance) · [Performance and concurrency](#performance-and-concurrency) · [Spectrum & Federation](#spectrum-and-federation)

## Distribution & Sort Keys <a id="distribution-and-sort-keys"></a>

Managed cloud DW; SQL is Postgres-derived but storage/execution are MPP + columnar, so `DISTKEY`/`SORTKEY`/`DISTSTYLE` have **no PostgreSQL equivalent** — and Redshift has **no partitions, tablespaces, or B-tree secondary indexes** ("does not... support partitioning data within database objects"). Physical layout is chosen by these two knobs. `AUTO` is the default for both on RA3 and Serverless; Automatic Table Optimization (ATO) watches the workload and alters `AUTO` tables in the background within hours.

### Distribution — collocate joins, kill the shuffle
A cluster is leader + compute nodes; each node splits into **slices** that run queries in parallel. On load, rows land on slices per `DISTSTYLE`; at query time the optimizer **redistributes** rows over the network for joins/aggregations — the dominant cost you tune to avoid.
- **KEY** — hash one column to slices. Matching values collocate, so equi-joins and `GROUP BY` on that key run locally with no movement.
- **ALL** — a full copy on **every node**. Small, slow-changing dimensions only; multiplies storage and load/vacuum time. Use strictly as the **inner** join table.
- **EVEN** — round-robin; for tables that don't join.
- **AUTO** (default) — `ALL` while tiny → may switch to `KEY` (on the PK) as it grows → `EVEN` if no column suits; ATO does this transparently.

A table has **one** `DISTKEY`: collocate the fact with its single largest / most-joined dimension on the join column; make other dimensions `ALL`. A `DISTKEY` that is also the frequent `GROUP BY` key removes the aggregation shuffle too.

### Read the plan — `DS_` operators (EXPLAIN)
- `DS_DIST_NONE`, `DS_DIST_ALL_NONE` — **good**: collocated, no redistribution.
- `DS_DIST_INNER` — inner redistributed; set the inner table's `DISTKEY` to the join key to make it `DS_DIST_NONE`.
- `DS_BCAST_INNER`, `DS_DIST_BOTH` — **bad**: whole inner broadcast / both sides shuffled because the tables aren't joined on their distkeys.
- `DS_DIST_ALL_INNER` — **bad**: `ALL` used on the **outer** table forces a serial single-slice join (`ALL` is inner-only).

Ignore the first run's time (query compilation).

### Skew is the silent killer
A `DISTKEY` must be **high-cardinality and uniform**. A skewed or NULL-heavy key piles rows onto one slice and the whole parallel query waits on it — often worse than `EVEN`. Check `SVV_TABLE_INFO.skew_rows` (≈1.0 is even).

### Sort keys = the index replacement
Columnar data lives in 1 MB blocks whose **min/max ("zone map")** are kept in metadata; sorted data lets a range predicate **skip blocks** (up to ~98%). No secondary indexes exist — the sort key is how scans get cheap.
- **COMPOUND** (default) — sorts by column **prefix**; helps queries filtering the leading column(s) in order. Lowest maintenance; best when the table takes regular `INSERT`/`UPDATE`/`DELETE`.
- **INTERLEAVED** — equal weight to up to **8** columns for ad-hoc filtering on any subset. **Not** for monotonic columns (dates, timestamps, identity). Costs more to load, needs `VACUUM REINDEX`, and interleave skew grows over time (`SVV_INTERLEAVED_COLUMNS`). Serverless migration converts interleaved + `DISTKEY` tables to compound.
- `SORTKEY AUTO` (recommended) lets ATO pick and evolve the key.

### Maintenance & gotchas
- New rows append to an **unsorted region**; automatic table sort and auto-vacuum re-sort in the background, but heavy churn may still need explicit `VACUUM`.
- `ALTER TABLE ... ALTER DISTKEY col` / `ALTER DISTSTYLE {ALL|EVEN|KEY|AUTO}` / `ALTER [COMPOUND] SORTKEY (...)` change layout in place in supported cases; otherwise rebuild via CTAS / deep copy.
- Load **bulk and pre-sorted** with `COPY`; row-at-a-time `INSERT`s bloat the unsorted region and defeat zone maps.

### Sources
- docs.aws.amazon.com/redshift/latest/dg/c_choosing_dist_sort.html (AUTO/EVEN/KEY/ALL, no partitioning)
- docs.aws.amazon.com/redshift/latest/dg/c_data_redistribution.html (DS_DIST_* / DS_BCAST_INNER plan labels)
- docs.aws.amazon.com/redshift/latest/dg/t_Sorting_data.html + t_Sorting_data-interleaved.html (zone maps, compound vs interleaved, VACUUM REINDEX)
- docs.aws.amazon.com/redshift/latest/dg/t_Creating_tables.html (Automatic Table Optimization) · c_best_practices_best_dist_key.html (collocation, skew)

## Loading and maintenance <a id="loading-and-maintenance"></a>

Managed cloud DW; SQL is Postgres-derived but **load and maintenance diverge sharply from PostgreSQL**. No user version — RA3 (managed storage, compute/storage split) and Serverless (RPU-hours) evolve; confirm current docs. OLAP rule: ingest in **batch** via `COPY`, never row-by-row. See `lore/databases.md`.

### Bulk load with COPY
- `COPY` is the most efficient load: one command reads **many files in parallel** across slices (MPP), sorting and distributing rows. `INSERT ... VALUES` row-at-a-time is far slower and fragments the table — never build a pipeline on it.
- File shape drives parallelism. Splittable inputs (uncompressed CSV; Parquet/ORC) **auto-split at 128 MB**; Parquet/ORC **under 128 MB don't split**. Non-splittable (JSON, GZIP-compressed CSV) must be **manually split** into similar-sized files of **1 MB–1 GB after compression**, count a **multiple of the slice count**.
- Compress with `GZIP`/`LZOP`/`BZIP2`/`ZSTD`; prefer typed Parquet. Load an exact file set with a **manifest**. Auth with `IAM_ROLE`, not keys.
- **One COPY per table** — concurrent COPYs into one table force a **serialized load** and a VACUUM afterward if it has a sort key.
- Into an **empty** table COPY auto-applies column encodings and runs `ANALYZE` (`COMPUPDATE`/`STATUPDATE` control it); `ENCODE AUTO` lets Redshift manage encodings.

### Continuous & streaming ingestion
- **auto-copy**: after an S3 event integration, `COPY t FROM 's3://…' IAM_ROLE '…' JOB CREATE my_job AUTO ON;` auto-loads new S3 files, **tracks loaded files (no dupes)**, batches per COPY. Defined once; manage via CREATE/LIST/SHOW/DROP/ALTER/RUN JOB, watch `SYS_COPY_JOB*`.
- **Streaming ingestion**: Kinesis Data Streams / MSK land directly into a **materialized view** (no S3 hop), low latency.
- **Data lake**: Spectrum external tables are read-only (no COPY/INSERT) — `INSERT INTO local SELECT …`, or zero-ETL from operational sources.

### Upserts — MERGE, not row DML
- Stage via COPY into a temp table, then `MERGE INTO target USING staging ON …`. Replace-all-columns = delete-by-inner-join + one insert (single target scan); use a column-list method for partial-column updates.
- Avoid per-row `UPDATE`/`DELETE`. `ALTER TABLE APPEND` moves rows without copying (fast) but fragments the target — follow with VACUUM DELETE.
- A **deep copy** (CTAS / `CREATE TABLE LIKE` + reload) can beat VACUUM for fully re-sorting a heavily unsorted table.

### VACUUM — very different from PostgreSQL
- Redshift VACUUM **re-sorts rows AND reclaims space**; the **default is `VACUUM FULL`** (Postgres' default just reclaims). Forms: `FULL | SORT ONLY | DELETE ONLY | REINDEX | RECLUSTER`, plus `TO n PERCENT`, `BOOST`.
- **Automatic** table sort and `VACUUM DELETE` run in the background at low load — you rarely run `DELETE ONLY` manually. Run manual `VACUUM (FULL|SORT ONLY)` after a big load when you need fully-sorted data.
- Skips the sort phase when **≥95% sorted** (default threshold; tune with `TO n PERCENT`). `REINDEX` re-analyzes interleaved sort keys (extra pass, slower). `RECLUSTER` sorts only the unsorted tail with no full merge — for large, frequently-ingested tables queried on recent data; **not on interleaved sort keys or `ALL` distribution**. `BOOST` uses extra resources but blocks concurrent update/delete — run at low load.
- **Can't VACUUM inside a transaction block.** Gauge need via `svv_table_info.unsorted` and `vacuum_sort_benefit`.

### ANALYZE & table design
- `ANALYZE` refreshes planner stats. **Automatic analyze** runs in background (`auto_analyze` on by default), skipping tables with `<10%` changed rows (`analyze_threshold_percent`). Use `ANALYZE … PREDICATE COLUMNS` to refresh only join/filter/group-by plus dist/sort columns.
- **Automatic Table Optimization**: tables with `DISTSTYLE AUTO` / `SORTKEY AUTO` get dist and sort keys applied automatically from observed workload (e.g. `AUTO`→`KEY`). Leave AUTO unless you have a proven better key.

### Sources
- https://docs.aws.amazon.com/redshift/latest/dg/t_Loading_data.html
- https://docs.aws.amazon.com/redshift/latest/dg/c_best-practices-use-multiple-files.html
- https://docs.aws.amazon.com/redshift/latest/dg/r_VACUUM_command.html
- https://docs.aws.amazon.com/redshift/latest/dg/t_Analyzing_tables.html
- https://docs.aws.amazon.com/redshift/latest/dg/loading-data-copy-job.html
- https://docs.aws.amazon.com/redshift/latest/dg/t_updating-inserting-using-staging-tables-.html

## Performance playbook <a id="performance"></a>

Managed MPP columnar DW; cost = compute (node-hours / RPU-hr) + storage (+ Spectrum bytes-scanned on provisioned). Every lever cuts **blocks scanned** or **cross-slice movement**. Measure first, tune the worst. Universal rules: `lore/databases.md`, `lore/deep/databases.md#indexing-and-query-plans`.

### Priority order (biggest wins first)
1. **Distribution + sort keys (dominant lever).** `DISTKEY` a high-cardinality, evenly-distributed join column to collocate the fact with its largest dimension (no redistribution); `SORTKEY` the range/filter columns (lead with time) so per-block **zone maps skip blocks**. Keep `AUTO` unless you have a proven better key. → `lore/deep/redshift.md#distribution-and-sort-keys`
2. **Scan fewer bytes.** Columnar storage reads only referenced columns — never `SELECT *` on wide tables. COPY picks encodings (AZ64 numerics/dates, ZSTD/LZO text). No secondary indexes — sort key + encoding replace them.
3. **Reuse results.** **Result cache** serves identical-text queries at zero compute unless base data changed. **Materialized views** (incremental / AUTO REFRESH) precompute hot aggregates; automatic rewrite + **AutoMV** use them even when a query doesn't name the MV. → `lore/deep/redshift.md#performance-and-concurrency`
4. **Keep stats + layout healthy.** Stale stats + unsorted regions defeat the planner and zone maps. Auto analyze / table-sort / vacuum-delete cover most; after a big load run `ANALYZE` (+ `VACUUM` for fully-sorted data). → `lore/deep/redshift.md#loading-and-maintenance`
5. **Absorb spikes with elastic compute, not a bigger cluster.** Automatic **WLM** priorities workloads; **Concurrency Scaling** (`auto` per queue) adds clusters for bursts (~1 free hr/day/cluster, then per-second); Serverless auto-scales RPUs. → `lore/deep/redshift.md#performance-and-concurrency`
6. **Load in parallel.** `COPY` from S3 fans out across all slices — far past row `INSERT`s; manifest + one COPY per table. → `lore/deep/redshift.md#loading-and-maintenance`
7. **Right architecture.** RA3 splits compute from managed storage; RG node types add a built-in data-lake query engine (no separate Spectrum charge). AQUA was an older RA3 accelerator — verify.

### Top anti-patterns
- Skewed/low-cardinality `DISTKEY` (one slice stalls the query); no or wrong `SORTKEY` (full scans); `SELECT *` on wide tables.
- Row-by-row `INSERT`/`UPDATE`/`DELETE`; churny tables never vacuumed (bloat + unsorted region).
- `INTERLEAVED` sort keys by default (VACUUM REINDEX; no concurrency scaling).
- Trusting unenforced PK/FK/UNIQUE — a violated constraint the optimizer believes → **wrong results**.
- A bigger cluster for spikes instead of Concurrency Scaling / Serverless.

### How to measure
- **`EXPLAIN`** — `DS_BCAST_INNER` / `DS_DIST_BOTH` = bad distribution; `DS_DIST_NONE` = collocated; watch nested loops. Ignore the first (compile) run.
- **`SVV_TABLE_INFO`** — `skew_rows`, `unsorted`, `stats_off`, `vacuum_sort_benefit` per table.
- **`STL_ALERT_EVENT_LOG`** — planner alerts (missing stats, nested loops, large scans).
- **`SYS_QUERY_HISTORY` / `SYS_QUERY_DETAIL`** (provisioned + Serverless), `SVL_QUERY_SUMMARY` / `SVL_QUERY_REPORT`, console **Query monitoring** for step + queue time.
- **Redshift Advisor** — dist/sort/encoding/vacuum recs.

### Sources
- docs.aws.amazon.com/redshift/latest/dg: c_designing-tables-best-practices · c-query-tuning · materialized-view-auto-mv · concurrency-scaling
- aws.amazon.com/redshift/pricing (Spectrum bytes-scanned + 10 MB min/query; Concurrency Scaling free credits)

## Performance and concurrency <a id="performance-and-concurrency"></a>

Managed MPP columnar DW, Postgres-derived SQL — physical design diverges hard from PostgreSQL. No user version; RA3 (compute/storage separate), RG, Serverless coexist and evolve — verify terms. See lore/databases.md for universal rules. Cost = compute time (node-hours / Serverless RPU-hours) + storage. Optimize to **scan fewer blocks**: prune with sort keys, avoid redistribution with dist keys.

### Distribution + sort (the two big levers)
- **Distribution style** places rows across slices so joins/aggs stay local: `KEY` (hash), `ALL` (full copy per node), `EVEN`, `AUTO`. DO collocate the fact table and its most-joined dimension on the join column (DISTKEY on fact FK + dim PK) to skip redistribution. DO use `ALL` for small static dims (multiplies storage + load). DON'T pick a low-cardinality/skewed DISTKEY — check `SVV_TABLE_INFO.skew_rows`.
- **Sort keys** store blocks in order; per-block min/max (**zone maps**) skip blocks outside a predicate. DO lead the sort key with the timestamp for recency and with your range/equality-filter column. DO set sort key = dist key = join key for a sort-merge (skips the sort) over a hash join.
- **AUTO** (default DISTSTYLE + SORTKEY) lets **Automatic Table Optimization** learn from queries and ALTER to KEY/sort within hours — prefer it. Auto vacuum (sort+delete), auto analyze, Advisor encoding recs run in background.
- DON'T use **interleaved** sort keys casually: need `VACUUM REINDEX`, degrade on writes, **not eligible for concurrency scaling**. Compound (default) is right almost always.
- DON'T leave wide columns RAW; let COPY pick encodings (**AZ64** numerics/dates, LZO/ZSTD text). Never `SELECT *` on wide tables.

### Ingestion + writes (batch, not row-by-row)
- DO bulk-load with `COPY` from S3 (parallel across slices) or streaming ingestion; files ~equal-sized, a multiple of slice count. DON'T fire single-row `INSERT`s.
- Upsert via `MERGE` or staging + delete/insert — not per-row UPDATE. UPDATE/DELETE = delete-mark + reinsert reclaimed by VACUUM (not per-tuple autovacuum), so churny tables bloat and need vacuum-sort.

### WLM, concurrency scaling, Serverless
- Prefer **automatic WLM**: up to 8 queues; set **priority** High/Normal/Low per workload instead of hand-tuning memory/slots. Manual WLM caps at 50 slots/queue but AWS recommends ≤15 total. **SQA** fast-lanes short queries; **QMR** governs runaways — under auto WLM use `query_execution_time` (no `timeout`) and `change priority` (no `HOP`).
- **Concurrency scaling**: enable per-queue (`auto`) to spin transient clusters for queued read *and* write (COPY/INSERT/UPDATE/DELETE/CTAS/VACUUM, MV manual refresh) on RA3/RG. Bounded by `max_concurrency_scaling_clusters` (default 1); daily free-credit tier then per-second. NOT for interleaved-sort/temp tables, DISTSTYLE ALL / identity-column write targets, or clusters >32 nodes.
- **Serverless**: capacity in **RPUs** (1 RPU = 16 GB RAM), base 8–512 (default 128; 4 RPU for <32 TB), per-second. **AI-driven scaling** targets a **price-performance** setting (default Balanced); cap spend with Max capacity / Max RPU-hours.
- **Result cache** returns identical-text queries with zero compute unless base data changed (`enable_result_cache_for_session`); compiled code cached locally + remotely (survives reboots).

### Divergence from PostgreSQL (critical)
- PK/UNIQUE/FK are **informational, NOT enforced** — yet the optimizer trusts them for rewrites, so a violated constraint gives **wrong results**. Declare only keys that truly hold.
- No secondary/B-tree indexes — sort key + zone maps replace them. `EXPLAIN` is MPP: `DS_BCAST`/`DS_DIST` steps signal a bad DISTKEY.
- Use **materialized views** (incremental/AUTO REFRESH, AutoMV + automatic rewrite) for repeated dashboard aggregations; plain views don't precompute.

### Sources
- https://docs.aws.amazon.com/redshift/latest/dg/c_designing-tables-best-practices.html
- https://docs.aws.amazon.com/redshift/latest/dg/cm-c-implementing-workload-management.html
- https://docs.aws.amazon.com/redshift/latest/dg/concurrency-scaling.html
- https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-capacity.html

## Spectrum & Federation <a id="spectrum-and-federation"></a>

Postgres-derived SQL, two ways to reach data you don't store: **Spectrum** (S3 files via an external catalog) and **federated query** (live RDS/Aurora Postgres & MySQL). Both attach via `CREATE EXTERNAL SCHEMA` but diverge from PostgreSQL; verify.

### Diverges from PostgreSQL
- `EXTERNAL SCHEMA`/`TABLE`/`PARTITIONED BY` and `$path`/`$size` are Redshift-only. Redshift has no `postgres_fdw` / `FOREIGN TABLE`; federated query is a distinct engine (docs note federated queries aren't reachable through a PostgreSQL FDW).
- External data is **read-only** — no writes to the source; export via `UNLOAD` to S3.

### Spectrum
DO register the external DB in **AWS Glue Data Catalog** (Athena catalog is legacy) via `FROM DATA CATALOG DATABASE '..' REGION '..' IAM_ROLE '..'`. Role needs S3 GET/LIST + `glue:GetTable`; add `CATALOG_ROLE` cross-account.
DO store facts as **Parquet/ORC** — columnar column pruning + predicate pushdown (text/JSON scan whole rows) + nested types.
DO **partition** on a filtered key (usually time) so the planner prunes folders. Partition columns live in the S3 path, not the row data: `PARTITIONED BY (saledate char(10))` then `ALTER TABLE ... ADD PARTITION (saledate='2008-01') LOCATION '.../saledate=2008-01/'`. Partitions are invisible until registered (crawler or `ADD PARTITION`, ≤100/stmt); inspect `SVV_EXTERNAL_PARTITIONS`.
DO keep big facts in S3, **small dimensions local**, join in one query. `EXPLAIN` shows `S3 Seq Scan` steps pushed to Spectrum.

**Cost:** Spectrum bills **bytes scanned from S3** (per-TB, ~10 MB min/query; DDL/failed queries free) — partitions + narrow columns cut it. On **provisioned clusters (incl. RA3)** it bills **separately, on top of node-hours**. Only **Serverless** folds external-S3 scans into RPU compute (no separate Spectrum charge); newer built-in data-lake nodes avoid one. Selecting `$path`/`$size` is a charged scan.

DON'T `SELECT *` on wide external tables, leave gzip-JSON, use many tiny files, or skip registering new partitions (silently missing data).

### Federated query
DO source-type the schema; creds come from **Secrets Manager** (never inline), role needs `secretsmanager:GetSecretValue`:
```sql
CREATE EXTERNAL SCHEMA pg_live FROM POSTGRES
  DATABASE 'appdb' SCHEMA 'public' URI 'host.rds.amazonaws.com' PORT 5432
  IAM_ROLE 'arn:...:role/FedRole' SECRET_ARN 'arn:...:secret/db';
```
`FROM MYSQL` takes no `SCHEMA` and defaults PORT 3306. Redshift pushes predicates to the remote, then parallelizes results across compute nodes.
DO use it for **ELT / live lookups** — `INSERT ... SELECT` operational rows into a local table — not to scan huge remote tables (hammers the OLTP source).

**Txn semantics:** Postgres federation opens `READ ONLY REPEATABLE READ` on the remote (`pg_export_snapshot` + read lock); an Aurora **reader** endpoint may raise "invalid snapshot" — use an instance endpoint or `pg_federation_repeatable_read=false` (READ COMMITTED). MySQL is READ COMMITTED only.

DON'T expect writes, `ALTER SCHEMA` (drop+recreate), concurrency scaling, or cheap cross-Region. Source must reach the cluster VPC (SG/peering; VPC routing + a Secrets Manager endpoint cross-VPC). MySQL zero `DATE`/`TIMESTAMP` → NULL.

### Sources
- docs.aws.amazon.com/redshift/latest/dg: c-getting-started-using-spectrum · r_CREATE_EXTERNAL_SCHEMA · c-spectrum-external-tables
- docs.aws.amazon.com/redshift/latest/dg: federated-overview · federated-limitations (no PostgreSQL FDW)
