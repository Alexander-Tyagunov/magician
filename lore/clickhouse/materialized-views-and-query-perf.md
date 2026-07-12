# ClickHouse — Materialized Views & Query Performance

Version-adaptive; verify current stable. Gates: `_part_offset`-only projections since **25.5**, multi-projection part pruning since **25.6**, adaptive async-insert timeout since **24.2**. Lightweight `UPDATE` is still **beta**; refreshable MVs are standard now (older builds need `allow_experimental_refreshable_materialized_view`).

## Incremental MV = insert trigger, not a snapshot
Runs its SELECT on **each inserted block** into a target table (compute moves to insert time). Use the explicit `TO` form (a real, tunable target):
```sql
CREATE MATERIALIZED VIEW votes_daily_mv TO votes_daily AS
SELECT toStartOfDay(ts)::Date AS day, countIf(kind=2) AS up
FROM votes GROUP BY day;
```
Inside the trigger the source name is **the inserted block only** — self-lookups see just new rows (use a plain `VIEW` to read the full table). In a JOIN **only the left-most table triggers**; right tables are a static snapshot at insert time, so pre-load dimensions or filter them by the block's keys (`WHERE id IN (SELECT fk FROM <block>)`) — an unfiltered big-right JOIN makes inserts crawl. `UNION ALL` won't fully trigger — one MV per branch into a shared target. CTEs are inlined, not materialized.

## Aggregating targets: partial state, merge on read
`SummingMergeTree` for additive counters. For avg/quantile/uniq use `AggregatingMergeTree` + `AggregateFunction` columns, write `xxxState()`, read `xxxMerge()` — averaging pre-averaged rows is wrong. The MV `GROUP BY` **must match the target `ORDER BY`** or merges skew. Merges are async — re-aggregate at read (`GROUP BY`+`sumMerge`), not `FINAL`.

## Refreshable MVs for joins/DAGs
`REFRESH EVERY 1 MINUTE` (or `AFTER`) re-runs the full query and **atomically swaps** the target — for JOINs incremental can't express. Chain via dependencies (a mini-scheduler); `APPEND` accumulates snapshots. Watch `system.view_refreshes`; force with `SYSTEM REFRESH VIEW`. Incremental scales far better — use refreshable only when it can't.

## Projections: optimizer's alt-ordering / pre-agg
A hidden reordered/pre-aggregated copy **inside the same table**, auto-synced; query the base table and the optimizer picks the variant scanning least (`optimize_use_projections`, on).
```sql
ALTER TABLE trips ADD PROJECTION p_by_fare (SELECT * ORDER BY fare);
ALTER TABLE trips MATERIALIZE PROJECTION p_by_fare;  -- backfill
```
`MATERIALIZE` is required or only new parts are covered; `GROUP BY` makes it an aggregate projection. Since 25.5 a `_part_offset`-only projection acts as a pure index (locate via projection, read base) cutting double-write cost; 25.6 prunes whole parts using several. Confirm via `EXPLAIN projections=1`. Limits: no JOIN/`WHERE` in the definition, no chaining, TTL tied to base, **lightweight update/delete disabled** by default.

## Scan-less query idioms
**Select only needed columns — never `SELECT *` on wide tables**; push the most selective predicate into `PREWHERE`; filter a prefix of the `ORDER BY` key so granules prune. Ingest in **big batches** — many tiny INSERTs make too many parts; if the client can't batch, set `async_insert=1, wait_for_async_insert=1` (server buffering; not for `INSERT ... SELECT`). Mutate sparingly: lightweight `DELETE` sets a `_row_exists` mask (rewritten as `ALTER ... UPDATE _row_exists=0`), lightweight `UPDATE` writes patch parts applied at read time — both add read cost and suit <~10% of rows; bulk lifecycle is cheapest via `DROP PARTITION`.

## Sources
- clickhouse.com/docs/materialized-view/incremental-materialized-view
- clickhouse.com/docs/materialized-view/refreshable-materialized-view
- clickhouse.com/docs/data-modeling/projections
- clickhouse.com/docs/optimize/asynchronous-inserts
- clickhouse.com/docs/sql-reference/statements/update ; .../delete
