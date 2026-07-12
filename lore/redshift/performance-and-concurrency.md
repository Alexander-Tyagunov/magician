# Amazon Redshift — Performance and concurrency

Managed MPP columnar DW, Postgres-derived SQL — physical design diverges hard from PostgreSQL. No user version; RA3 (compute/storage separate), RG, Serverless coexist and evolve — verify terms. See lore/databases.md for universal rules. Cost = compute time (node-hours / Serverless RPU-hours) + storage. Optimize to **scan fewer blocks**: prune with sort keys, avoid redistribution with dist keys.

## Distribution + sort (the two big levers)
- **Distribution style** places rows across slices so joins/aggs stay local: `KEY` (hash), `ALL` (full copy per node), `EVEN`, `AUTO`. DO collocate the fact table and its most-joined dimension on the join column (DISTKEY on fact FK + dim PK) to skip redistribution. DO use `ALL` for small static dims (multiplies storage + load). DON'T pick a low-cardinality/skewed DISTKEY — check `SVV_TABLE_INFO.skew_rows`.
- **Sort keys** store blocks in order; per-block min/max (**zone maps**) skip blocks outside a predicate. DO lead the sort key with the timestamp for recency and with your range/equality-filter column. DO set sort key = dist key = join key for a sort-merge (skips the sort) over a hash join.
- **AUTO** (default DISTSTYLE + SORTKEY) lets **Automatic Table Optimization** learn from queries and ALTER to KEY/sort within hours — prefer it. Auto vacuum (sort+delete), auto analyze, Advisor encoding recs run in background.
- DON'T use **interleaved** sort keys casually: need `VACUUM REINDEX`, degrade on writes, **not eligible for concurrency scaling**. Compound (default) is right almost always.
- DON'T leave wide columns RAW; let COPY pick encodings (**AZ64** numerics/dates, LZO/ZSTD text). Never `SELECT *` on wide tables.

## Ingestion + writes (batch, not row-by-row)
- DO bulk-load with `COPY` from S3 (parallel across slices) or streaming ingestion; files ~equal-sized, a multiple of slice count. DON'T fire single-row `INSERT`s.
- Upsert via `MERGE` or staging + delete/insert — not per-row UPDATE. UPDATE/DELETE = delete-mark + reinsert reclaimed by VACUUM (not per-tuple autovacuum), so churny tables bloat and need vacuum-sort.

## WLM, concurrency scaling, Serverless
- Prefer **automatic WLM**: up to 8 queues; set **priority** High/Normal/Low per workload instead of hand-tuning memory/slots. Manual WLM caps at 50 slots/queue but AWS recommends ≤15 total. **SQA** fast-lanes short queries; **QMR** governs runaways — under auto WLM use `query_execution_time` (no `timeout`) and `change priority` (no `HOP`).
- **Concurrency scaling**: enable per-queue (`auto`) to spin transient clusters for queued read *and* write (COPY/INSERT/UPDATE/DELETE/CTAS/VACUUM, MV manual refresh) on RA3/RG. Bounded by `max_concurrency_scaling_clusters` (default 1); daily free-credit tier then per-second. NOT for interleaved-sort/temp tables, DISTSTYLE ALL / identity-column write targets, or clusters >32 nodes.
- **Serverless**: capacity in **RPUs** (1 RPU = 16 GB RAM), base 8–512 (default 128; 4 RPU for <32 TB), per-second. **AI-driven scaling** targets a **price-performance** setting (default Balanced); cap spend with Max capacity / Max RPU-hours.
- **Result cache** returns identical-text queries with zero compute unless base data changed (`enable_result_cache_for_session`); compiled code cached locally + remotely (survives reboots).

## Divergence from PostgreSQL (critical)
- PK/UNIQUE/FK are **informational, NOT enforced** — yet the optimizer trusts them for rewrites, so a violated constraint gives **wrong results**. Declare only keys that truly hold.
- No secondary/B-tree indexes — sort key + zone maps replace them. `EXPLAIN` is MPP: `DS_BCAST`/`DS_DIST` steps signal a bad DISTKEY.
- Use **materialized views** (incremental/AUTO REFRESH, AutoMV + automatic rewrite) for repeated dashboard aggregations; plain views don't precompute.

## Sources
- https://docs.aws.amazon.com/redshift/latest/dg/c_designing-tables-best-practices.html
- https://docs.aws.amazon.com/redshift/latest/dg/cm-c-implementing-workload-management.html
- https://docs.aws.amazon.com/redshift/latest/dg/concurrency-scaling.html
- https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-capacity.html
