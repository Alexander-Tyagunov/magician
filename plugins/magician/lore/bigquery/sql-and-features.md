# Google BigQuery — SQL and Features

GoogleSQL is the default/recommended ANSI dialect; legacy SQL is still available (Google recommends migrating), not deprecated. Serverless — no version to gate, but the model (on-demand bytes vs slots, editions) evolves; see lore/bigquery/cost-and-slots.md.

## Nested & repeated data is the idiom — denormalize, don't star-join
Prefer wide tables with `STRUCT` (record) + `ARRAY` (repeated) columns over normalized joins. Flatten with `UNNEST` on the right of a `CROSS`/`LEFT`/`INNER JOIN` (INNER preferred); `FROM t, UNNEST(t.arr)` expands its array to child rows.
DO nest one-to-many facts as arrays of structs — joins vanish; scan only referenced sub-fields.
DON'T build `ARRAY<ARRAY<...>>`: arrays of arrays aren't allowed — wrap in a STRUCT. A result array can't hold NULL elements (errors); a NULL array persists as empty.
Types: exact decimals `NUMERIC`(P38,S9)/`BIGNUMERIC`(P76,S38); native `JSON` (dot/`[]` paths); `GEOGRAPHY`, `INTERVAL`, `RANGE<DATE|DATETIME|TIMESTAMP>` (lower-incl, upper-excl).

## Query features that cut scan or code
- `QUALIFY` filters on window-function output without a wrapping subquery.
- `SELECT * EXCEPT(a,b)` / `* REPLACE(expr AS c)` prune/patch wide columns inline.
- `PIVOT`/`UNPIVOT`; `TABLESAMPLE SYSTEM (n PERCENT)`; `WITH RECURSIVE`.
- `SAFE.`/`SAFE_CAST` make per-row errors NULL, not a failed scan; approx aggs (`APPROX_COUNT_DISTINCT`, `APPROX_QUANTILES`) for cheap high-cardinality stats.
DO parameterize with named `@p`/positional `?` (blocks SQL injection); identifiers (table/column/dataset names) CANNOT be parameters — allow-list them (see lore/databases.md).

## DML & upserts are batch, not row-at-a-time
DO upsert/dedup with one atomic `MERGE` (INSERT/UPDATE/DELETE), never per-row UPDATE. A MERGE matching >1 source row per target errors ("must match at most one source row") — dedup the source first.
Concurrency is partition-scoped: up to 2 mutating DML (UPDATE/DELETE/MERGE) run at once, up to 20 more queue as `PENDING`; conflicts (same partition) auto-retry up to 3×. INSERT never conflicts.
DON'T drip tiny INSERTs. Bulk-load via load jobs, or stream via the **Storage Write API** (default at-least-once; committed exactly-once; pending atomic batch) — recommended over and cheaper than the legacy `tabledata.insertAll` streaming API.

## Multi-statement transactions
`BEGIN`/`COMMIT`/`ROLLBACK TRANSACTION` give ACID **snapshot isolation** — reads see a consistent snapshot; `CURRENT_TIMESTAMP()` returns the tx start time. Conflicting transactions on one table are **cancelled** (standalone DML queues instead). Limits: ≤100 tables, ≤100k partition mods; no DDL on permanent objects; a failed tx rolls back, no retry. Multi-query only in **Session** mode.

## Table lifecycle features
- **Time travel**: query the last 7 days (configurable 2–7) via `FOR SYSTEM_TIME AS OF ts`; restore dropped tables. A non-queryable 7-day fail-safe follows.
- **Snapshots** (read-only, store only bytes differing from base) vs **clones** (mutable) — both cheap, sharing storage until diverged.
- **Materialized views**: incrementally auto-refreshed; BigQuery smart-tunes base-table queries to rewrite onto them. Restricted SQL, no DML.

## Sources
- cloud.google.com/bigquery/docs/reference/standard-sql/{query-syntax,data-types,dml-syntax}
- cloud.google.com/bigquery/docs/{data-manipulation-language,transactions,parameterized-queries}
- cloud.google.com/bigquery/docs/{write-api,time-travel,table-snapshots-intro,materialized-views-intro}
