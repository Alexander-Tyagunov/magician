# Amazon Redshift — Performance playbook

Managed MPP columnar DW; cost = compute (node-hours / RPU-hr) + storage (+ Spectrum bytes-scanned on provisioned). Every lever cuts **blocks scanned** or **cross-slice movement**. Measure first, tune the worst. Universal rules: `lore/databases.md`, `lore/databases/indexing-and-query-plans.md`.

## Priority order (biggest wins first)
1. **Distribution + sort keys (dominant lever).** `DISTKEY` a high-cardinality, evenly-distributed join column to collocate the fact with its largest dimension (no redistribution); `SORTKEY` the range/filter columns (lead with time) so per-block **zone maps skip blocks**. Keep `AUTO` unless you have a proven better key. → `distribution-and-sort-keys.md`
2. **Scan fewer bytes.** Columnar storage reads only referenced columns — never `SELECT *` on wide tables. COPY picks encodings (AZ64 numerics/dates, ZSTD/LZO text). No secondary indexes — sort key + encoding replace them.
3. **Reuse results.** **Result cache** serves identical-text queries at zero compute unless base data changed. **Materialized views** (incremental / AUTO REFRESH) precompute hot aggregates; automatic rewrite + **AutoMV** use them even when a query doesn't name the MV. → `performance-and-concurrency.md`
4. **Keep stats + layout healthy.** Stale stats + unsorted regions defeat the planner and zone maps. Auto analyze / table-sort / vacuum-delete cover most; after a big load run `ANALYZE` (+ `VACUUM` for fully-sorted data). → `loading-and-maintenance.md`
5. **Absorb spikes with elastic compute, not a bigger cluster.** Automatic **WLM** priorities workloads; **Concurrency Scaling** (`auto` per queue) adds clusters for bursts (~1 free hr/day/cluster, then per-second); Serverless auto-scales RPUs. → `performance-and-concurrency.md`
6. **Load in parallel.** `COPY` from S3 fans out across all slices — far past row `INSERT`s; manifest + one COPY per table. → `loading-and-maintenance.md`
7. **Right architecture.** RA3 splits compute from managed storage; RG node types add a built-in data-lake query engine (no separate Spectrum charge). AQUA was an older RA3 accelerator — verify.

## Top anti-patterns
- Skewed/low-cardinality `DISTKEY` (one slice stalls the query); no or wrong `SORTKEY` (full scans); `SELECT *` on wide tables.
- Row-by-row `INSERT`/`UPDATE`/`DELETE`; churny tables never vacuumed (bloat + unsorted region).
- `INTERLEAVED` sort keys by default (VACUUM REINDEX; no concurrency scaling).
- Trusting unenforced PK/FK/UNIQUE — a violated constraint the optimizer believes → **wrong results**.
- A bigger cluster for spikes instead of Concurrency Scaling / Serverless.

## How to measure
- **`EXPLAIN`** — `DS_BCAST_INNER` / `DS_DIST_BOTH` = bad distribution; `DS_DIST_NONE` = collocated; watch nested loops. Ignore the first (compile) run.
- **`SVV_TABLE_INFO`** — `skew_rows`, `unsorted`, `stats_off`, `vacuum_sort_benefit` per table.
- **`STL_ALERT_EVENT_LOG`** — planner alerts (missing stats, nested loops, large scans).
- **`SYS_QUERY_HISTORY` / `SYS_QUERY_DETAIL`** (provisioned + Serverless), `SVL_QUERY_SUMMARY` / `SVL_QUERY_REPORT`, console **Query monitoring** for step + queue time.
- **Redshift Advisor** — dist/sort/encoding/vacuum recs.

## Sources
- docs.aws.amazon.com/redshift/latest/dg: c_designing-tables-best-practices · c-query-tuning · materialized-view-auto-mv · concurrency-scaling
- aws.amazon.com/redshift/pricing (Spectrum bytes-scanned + 10 MB min/query; Concurrency Scaling free credits)
