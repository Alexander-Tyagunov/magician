# Amazon Redshift — Distribution & Sort Keys

Managed cloud DW; SQL is Postgres-derived but storage/execution are MPP + columnar, so `DISTKEY`/`SORTKEY`/`DISTSTYLE` have **no PostgreSQL equivalent** — and Redshift has **no partitions, tablespaces, or B-tree secondary indexes** ("does not... support partitioning data within database objects"). Physical layout is chosen by these two knobs. `AUTO` is the default for both on RA3 and Serverless; Automatic Table Optimization (ATO) watches the workload and alters `AUTO` tables in the background within hours.

## Distribution — collocate joins, kill the shuffle
A cluster is leader + compute nodes; each node splits into **slices** that run queries in parallel. On load, rows land on slices per `DISTSTYLE`; at query time the optimizer **redistributes** rows over the network for joins/aggregations — the dominant cost you tune to avoid.
- **KEY** — hash one column to slices. Matching values collocate, so equi-joins and `GROUP BY` on that key run locally with no movement.
- **ALL** — a full copy on **every node**. Small, slow-changing dimensions only; multiplies storage and load/vacuum time. Use strictly as the **inner** join table.
- **EVEN** — round-robin; for tables that don't join.
- **AUTO** (default) — `ALL` while tiny → may switch to `KEY` (on the PK) as it grows → `EVEN` if no column suits; ATO does this transparently.

A table has **one** `DISTKEY`: collocate the fact with its single largest / most-joined dimension on the join column; make other dimensions `ALL`. A `DISTKEY` that is also the frequent `GROUP BY` key removes the aggregation shuffle too.

## Read the plan — `DS_` operators (EXPLAIN)
- `DS_DIST_NONE`, `DS_DIST_ALL_NONE` — **good**: collocated, no redistribution.
- `DS_DIST_INNER` — inner redistributed; set the inner table's `DISTKEY` to the join key to make it `DS_DIST_NONE`.
- `DS_BCAST_INNER`, `DS_DIST_BOTH` — **bad**: whole inner broadcast / both sides shuffled because the tables aren't joined on their distkeys.
- `DS_DIST_ALL_INNER` — **bad**: `ALL` used on the **outer** table forces a serial single-slice join (`ALL` is inner-only).

Ignore the first run's time (query compilation).

## Skew is the silent killer
A `DISTKEY` must be **high-cardinality and uniform**. A skewed or NULL-heavy key piles rows onto one slice and the whole parallel query waits on it — often worse than `EVEN`. Check `SVV_TABLE_INFO.skew_rows` (≈1.0 is even).

## Sort keys = the index replacement
Columnar data lives in 1 MB blocks whose **min/max ("zone map")** are kept in metadata; sorted data lets a range predicate **skip blocks** (up to ~98%). No secondary indexes exist — the sort key is how scans get cheap.
- **COMPOUND** (default) — sorts by column **prefix**; helps queries filtering the leading column(s) in order. Lowest maintenance; best when the table takes regular `INSERT`/`UPDATE`/`DELETE`.
- **INTERLEAVED** — equal weight to up to **8** columns for ad-hoc filtering on any subset. **Not** for monotonic columns (dates, timestamps, identity). Costs more to load, needs `VACUUM REINDEX`, and interleave skew grows over time (`SVV_INTERLEAVED_COLUMNS`). Serverless migration converts interleaved + `DISTKEY` tables to compound.
- `SORTKEY AUTO` (recommended) lets ATO pick and evolve the key.

## Maintenance & gotchas
- New rows append to an **unsorted region**; automatic table sort and auto-vacuum re-sort in the background, but heavy churn may still need explicit `VACUUM`.
- `ALTER TABLE ... ALTER DISTKEY col` / `ALTER DISTSTYLE {ALL|EVEN|KEY|AUTO}` / `ALTER [COMPOUND] SORTKEY (...)` change layout in place in supported cases; otherwise rebuild via CTAS / deep copy.
- Load **bulk and pre-sorted** with `COPY`; row-at-a-time `INSERT`s bloat the unsorted region and defeat zone maps.

## Sources
- docs.aws.amazon.com/redshift/latest/dg/c_choosing_dist_sort.html (AUTO/EVEN/KEY/ALL, no partitioning)
- docs.aws.amazon.com/redshift/latest/dg/c_data_redistribution.html (DS_DIST_* / DS_BCAST_INNER plan labels)
- docs.aws.amazon.com/redshift/latest/dg/t_Sorting_data.html + t_Sorting_data-interleaved.html (zone maps, compound vs interleaved, VACUUM REINDEX)
- docs.aws.amazon.com/redshift/latest/dg/t_Creating_tables.html (Automatic Table Optimization) · c_best_practices_best_dist_key.html (collocation, skew)
