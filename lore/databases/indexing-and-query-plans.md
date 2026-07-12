# Databases — Indexing & query plans

Engine-level index + planner behavior across relational engines (not ORM usage — see lore/orm.md). Current stable: PostgreSQL **18**, MySQL **8.4 LTS**, SQL Server **2025** (v17), SQLite **3.x**. Verify version-gated facts against the target engine.

## Read the plan before you touch an index

- **Postgres**: `EXPLAIN (ANALYZE, BUFFERS) <query>`. `ANALYZE` executes the query — wrap DML in `BEGIN; … ROLLBACK;`. Since **PG18** `BUFFERS` is auto-on with `ANALYZE` (`BUFFERS OFF` to suppress). Compare estimated `rows=` vs `(actual … rows=… loops=N)`; when `loops>1` the shown time/rows are **per-loop averages** — multiply by `loops` for the total. A big estimate-vs-actual gap = a stats problem, not an index problem.
- **MySQL**: `EXPLAIN FORMAT=TREE` (8.0.16+) or `EXPLAIN ANALYZE` (8.0.18+, runs the query). In classic EXPLAIN, `type` best→worst: `const`/`eq_ref`/`ref` (good) → `range` → `index` (full index scan) → `ALL` (full table scan, bad). `Extra` red flags: `Using filesort`, `Using temporary`; good: `Using index` (covering), `Using index condition` (ICP).
- **SQLite**: `EXPLAIN QUERY PLAN` — `SEARCH … USING INDEX` good, `SCAN` = full scan.
- **SQL Server**: capture the *actual* plan (`SET STATISTICS IO, TIME ON`; `SET SHOWPLAN_XML ON`) or Query Store. Look for Index Seek vs Scan and stray Key/RID Lookups.
- **DON'T** trust plans from tiny or empty tables — costs aren't linear and the planner rationally scans small tables. Test on realistic row counts.

## Keep predicates sargable

- **DO** leave the indexed column bare on one side: `WHERE created_at >= $1`, never `WHERE date(created_at)=$1` or `WHERE price+0=$1`. Any function/cast on the column disables its B-tree index (→ full scan). Fix with an **expression index** (Postgres `CREATE INDEX ON t ((lower(email)))`; SQL Server computed+indexed column) or rewrite as a range.
- Leading-wildcard `LIKE '%x'` can't use a B-tree; anchored `LIKE 'x%'` can — but in Postgres a non-C locale needs a `text_pattern_ops`/`varchar_pattern_ops` opclass for pattern indexing.
- **Implicit coercion** silently kills indexes: comparing an indexed `VARCHAR` to a number, or joining columns with mismatched type/charset/collation (MySQL: comparing `utf8mb4` to `latin1`) forces a scan.

## Composite indexes: column order is the whole game

- An index on `(a,b,c)` serves `a`, `(a,b)`, `(a,b,c)` — **never** `b` alone or `(b,c)` (leftmost-prefix rule, same in Postgres/MySQL/SQLite/SQL Server).
- Put equality columns first, then **one** range/inequality column, then the `ORDER BY` column. A range predicate "uses up" the prefix: columns after it can't be used for seeking (only filtering).
- An index that matches `WHERE` **and** `ORDER BY` eliminates the sort (no `Using filesort` / no `Sort` node). MySQL 8.0+ can also read an index backward for `DESC`.
- **DON'T** keep an index that is a strict prefix of another — it's redundant; drop it.
- Postgres **PG18** skip-scan lets a multicolumn B-tree help even when the leading column isn't filtered (visible as multiple `Index Searches`), but a purpose-ordered index still beats it.

## Covering / index-only scans

- **Postgres**: an index-only scan needs every referenced column in the index **and** the heap pages marked all-visible — so it depends on VACUUM. Check `Heap Fetches:` in EXPLAIN; high fetches mean VACUUM lag, not a win. Add payload with `INCLUDE` (PG11+) to keep the key narrow and uniqueness on key columns only. GIN indexes can't do index-only scans.
- **InnoDB**: every secondary-index leaf stores the **primary key** (not a row pointer), so a non-covering lookup does a second "bookmark" seek into the clustered index. A covering index (`Extra: Using index`) skips it. Keep the PK short — it is copied into every secondary index.
- **SQL Server**: a nonclustered index with `INCLUDE` columns removes the Key/RID Lookup.

## Clustered vs heap storage

- InnoDB, SQLite rowid tables, and SQL Server clustered tables store rows in key order — PK lookups hit the leaf directly. A random/UUID PK scatters inserts and causes page splits + index fragmentation; prefer a monotonic surrogate key (or accept the documented write cost). SQLite `WITHOUT ROWID` swaps the rowid for the declared PK.
- **DON'T** make the clustered/primary key wide in InnoDB or SQL Server — it inflates every secondary index.

## Statistics drive the planner (cost-based)

- Stale stats → wrong cardinality estimates → wrong plan (scan chosen over seek, or a bad join order). After a bulk load or big delete, refresh explicitly: Postgres `ANALYZE` (autovacuum does it lazily), MySQL `ANALYZE TABLE` (+ `UPDATE HISTOGRAM` for skewed **non-indexed** columns), SQLite `ANALYZE`, SQL Server auto-update stats / `UPDATE STATISTICS`.
- SQL Server caches plans and reuses them — beware **parameter sniffing** (a plan compiled for an atypical parameter reused for all); mitigate with `OPTIMIZE FOR`, `RECOMPILE`, or Query Store plan forcing.

## Don't over-index — indexes cost writes

- Every index is maintained on every INSERT/UPDATE/DELETE and consumes buffer cache. **DON'T** add indexes on low-cardinality columns for equality alone — the planner will scan anyway. Use **partial indexes** (Postgres/SQLite `… WHERE active`; SQL Server filtered index) for a hot subset.
- Match index type to the query — B-tree for `=`, range, and sort; Postgres **GIN** for `jsonb`/array/full-text containment (`@>`, `&&`), **GiST** for ranges/geo/KNN (`<->`), **BRIN** for huge naturally-ordered tables, hash only for `=`.
- A Postgres Bitmap Heap Scan combining two indexes (BitmapAnd/Or) is a hint that one well-ordered composite index would serve better.

## Sources

- PostgreSQL 18 — Using EXPLAIN: https://www.postgresql.org/docs/current/using-explain.html
- PostgreSQL 18 — Index Types & Index-Only Scans: https://www.postgresql.org/docs/current/indexes-types.html , https://www.postgresql.org/docs/current/indexes-index-only-scans.html
- MySQL 8.4 — EXPLAIN Output & How MySQL Uses Indexes: https://dev.mysql.com/doc/refman/8.4/en/explain-output.html , https://dev.mysql.com/doc/refman/8.4/en/mysql-indexes.html
- SQLite — Query Planner: https://www.sqlite.org/queryplanner.html
- SQL Server 2025 — Execution Plans Overview: https://learn.microsoft.com/en-us/sql/relational-databases/performance/execution-plans
