# Databases — deep dive

> On-demand companion to `lore/databases.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Connection pooling](#connection-pooling) · [Transactions & Isolation](#transactions-and-isolation) · [Parameterized queries & injection](#parameterized-queries-and-injection) · [Indexing & query plans](#indexing-and-query-plans) · [Migrations & schema changes](#migrations-and-schema-changes) · [Resilience & observability](#resilience-and-observability)

## Connection pooling <a id="connection-pooling"></a>

Engine-side connection management: the server's per-connection cost model, and the external/server-side poolers that front it. This is orthogonal to *client*-side pools (HikariCP etc. — see lore/deep/jdbc.md#connections-and-pooling) and to ORM config. Verified against PostgreSQL 18, MySQL 8.4, PgBouncer 1.25.x, ProxySQL, and AWS RDS Proxy docs (see Sources).

### Why the engine forces you to pool

A DB connection is **not** cheap on the server, and the cost model differs by engine:

- **PostgreSQL forks an OS process per connection** (backend). `max_connections` defaults to **100** (`initdb` may lower it to fit kernel limits), is settable **only at server start**, and directly sizes shared memory — raising it wastes RAM even when idle. `superuser_reserved_connections` (default **3**) and `reserved_connections` (default **0**) carve slots out of that total. Idle connections still cost memory and add contention (spinlocks, snapshot/xid scans). Postgres itself ships **no built-in pooler** → you *need* an external one.
- **MySQL/MariaDB spawn a thread per connection** (`thread_handling=one-thread-per-connection`). `max_connections` defaults to **151**; the server actually permits `max_connections + 1`, the extra reserved for `CONNECTION_ADMIN`/`SUPER` to log in and diagnose. Exceeding it → `ER_CON_COUNT_ERROR` "Too many connections". `thread_cache_size` (autosized) recycles idle threads to dodge create/destroy cost. A true **thread pool** exists only in MySQL **Enterprise** (plugin), Percona, and MariaDB — Community MySQL has none.

The throughput knee is real: past `~((core_count*2) + effective_spindle_count)` active connections, added connections *reduce* throughput via disk/lock/cache-line contention and context switches. Count physical cores (exclude hyperthread siblings); `effective_spindle_count` ≈ 0 when the working set is cached. Keep the *active* pool small; set `max_connections` a little above pool size so maintenance/monitoring sessions still fit.

### Two-tier reality

App → client pool → (optional) server-side pooler → engine. The server-side pooler exists to let **thousands** of app/client connections share a **small** number of physical backends. If you run both, size the client pool's max ≤ what the server pooler admits, or the pooler just queues/sheds.

### PgBouncer pooling modes (and what breaks)

`pool_mode` (default **session**); `default_pool_size` **20**; `max_client_conn` **100**; `max_db_connections` **0** (unlimited).

- **session** — server returned to pool only when the *client* disconnects. Safe for all session state; `server_reset_query` = `DISCARD ALL` cleans it between clients. Poor connection amplification.
- **transaction** — server returned when the *transaction* ends. The high-density mode. But each transaction may land on a different backend, so **session state doesn't persist**: plain `SET`/`SET SESSION`, `LISTEN`/`NOTIFY`, session-level advisory locks, `WITH HOLD` cursors, session temp tables, and `DISCARD` all misbehave. Use `SET LOCAL` inside a tx instead. `server_reset_query` is *not* run in this mode.
- **statement** — returned after each statement; multi-statement transactions are **disallowed** entirely.

**Prepared statements:** protocol-level named prepared statements work in transaction/statement mode since PgBouncer **1.21.0** (2023-10) via `max_prepared_statements` (default **200**) — PgBouncer tracks and re-prepares them on whichever backend the query lands. SQL-level `PREPARE`/`EXECUTE`/`DEALLOCATE` are forwarded raw and are **not** tracked, so avoid them under transaction pooling. Managed Postgres poolers (Supabase Supavisor, others) expose the same session/transaction split.

### MySQL: ProxySQL / RDS Proxy multiplexing

ProxySQL and RDS Proxy achieve the same density via **multiplexing** (many frontends reuse one backend). Multiplexing auto-disables — for that backend, often permanently — when a session takes state the next query would inherit: an open transaction (until commit/rollback), `LOCK TABLES`/`FLUSH TABLES WITH READ LOCK` (until `UNLOCK`), `GET_LOCK()` (never re-enabled), any query with `@` user/session vars, certain `SET`s (`SQL_SAFE_UPDATES`, `FOREIGN_KEY_CHECKS`, `UNIQUE_CHECKS`…), `SQL_CALC_FOUND_ROWS`, `CREATE TEMPORARY TABLE`, text-protocol `PREPARE`, and `SQL_LOG_BIN=0`. RDS Proxy calls this **pinning**; a statement text > **16 KB** also pins, and it doesn't support session-pinning filters for PostgreSQL. Minimize pinning by keeping sessions stateless (prefer `SET LOCAL`, avoid temp tables/user vars on the hot path).

### DO / DON'T

- **DO** put a server-side pooler in front of Postgres for any web workload; Postgres has none built in.
- **DO** use transaction pooling for density, but audit every session-scoped feature your app/driver relies on first.
- **DO** set the pooler's `max_db_connections` (or RDS Proxy `MaxConnectionsPercent`) to protect `max_connections`, and set client-pool `maxLifetime` shorter than the pooler/DB idle timeout so nobody hands you a dead socket.
- **DON'T** raise Postgres `max_connections` into the thousands as a substitute for pooling — it inflates shared memory and pushes you past the throughput knee.
- **DON'T** rely on `SET`/temp tables/`LISTEN`/advisory locks under transaction pooling or multiplexing — they leak across or vanish between transactions.
- **DON'T** stack a large client pool behind a small server pooler; the effective ceiling is the *smaller* of the two.
- **DON'T** disable `maxLifetime`/connection recycling — poolers and firewalls silently reap idle backends.

### Sources

- PostgreSQL 18 — Connections & Authentication (max_connections, reserved_connections): https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL Wiki — Number Of Database Connections (process model, pool-size formula): https://wiki.postgresql.org/wiki/Number_Of_Database_Connections
- MySQL 8.4 — Connection Interfaces / thread handling & thread_cache_size: https://dev.mysql.com/doc/refman/8.4/en/connection-interfaces.html
- MySQL 8.4 — Too many connections (max_connections default 151, +1 reserved): https://dev.mysql.com/doc/refman/8.4/en/too-many-connections.html
- PgBouncer — config & pooling modes / max_prepared_statements: https://www.pgbouncer.org/config.html
- PgBouncer — changelog (1.25.2; 1.21.0 prepared statements): https://github.com/pgbouncer/pgbouncer/blob/master/NEWS.md
- ProxySQL — Multiplexing (disable conditions): https://proxysql.com/documentation/multiplexing/
- AWS RDS Proxy — overview & pinning/limitations: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html

## Transactions & Isolation <a id="transactions-and-isolation"></a>

Engine-side transaction semantics: how each SQL server actually implements a level. For the driver API (setAutoCommit, savepoints, pooling) see lore/deep/jdbc.md#transactions; for ORM unit-of-work see lore/orm.md.

Reference (mid-2026): PostgreSQL 18 (14–18 supported), MySQL 8.4 LTS (+9.x Innovation), SQL Server 2022/2025, Oracle 23ai. Semantics stable across those minors; version gates noted inline.

### The standard's trap

ANSI names three read anomalies (dirty read, non-repeatable read, phantom); engines also expose a **serialization anomaly** (write skew): each txn reads consistently, yet the committed set matches no serial order. The standard only says which anomalies *must not* occur — an engine may prevent more. A level *name* does not pin behavior; verify per engine.

### Defaults & implementation differ per engine

| Engine | Default | REPEATABLE READ | Phantoms at RR? |
|---|---|---|---|
| PostgreSQL | READ COMMITTED | true snapshot (MVCC) | **No** |
| MySQL/InnoDB | REPEATABLE READ | snapshot for plain SELECT; **next-key/gap locks** for locking reads | No |
| SQL Server | READ COMMITTED (locking) | shared locks held to commit | **Yes** |
| Oracle | READ COMMITTED | not offered (use SERIALIZABLE) | n/a |

- **PostgreSQL** implements only 3 levels: `READ UNCOMMITTED` acts as READ COMMITTED (no dirty reads, ever). RR = snapshot as of the first statement; SERIALIZABLE adds SSI monitoring (since 9.1 — before that "serializable" meant RR).
- **InnoDB** RR fixes the snapshot at the first consistent read; locking reads (`FOR UPDATE/SHARE`, `UPDATE`, `DELETE`) take gap/next-key locks to stop phantoms. READ COMMITTED disables gap locking (phantoms possible) and re-snapshots each statement. SERIALIZABLE upgrades plain `SELECT`→`FOR SHARE` when autocommit is off.
- **SQL Server** RR/SERIALIZABLE are *lock*-based (readers block writers). `SNAPSHOT` and `READ_COMMITTED_SNAPSHOT` (RCSI) use a tempdb version store, but must be enabled via `ALTER DATABASE SET ALLOW_SNAPSHOT_ISOLATION ON` / `SET READ_COMMITTED_SNAPSHOT ON` (RCSI defaults ON on Azure SQL). You cannot switch *into* SNAPSHOT mid-txn — it aborts.
- **Oracle** offers only READ COMMITTED + SERIALIZABLE (+ READ ONLY); MVCC via undo/SCN, so writers never block readers or vice versa (`SELECT … FOR UPDATE` is the exception).

Set with `SET TRANSACTION ISOLATION LEVEL …` before the first statement; PG/MySQL also `SET SESSION`/server default.

### Snapshot isolation ≠ SERIALIZABLE

Snapshot isolation (PG RR, SQL Server SNAPSHOT, Oracle's read model) blocks dirty/non-repeatable/phantom reads but **allows write skew**: two txns read an overlapping set, update disjoint rows, both commit, invariant broken. Only true SERIALIZABLE catches it — PG via SSI (non-blocking SIRead predicate locks), SQL Server via range locks. Cross-row invariants ("≥1 on call") need SERIALIZABLE or an explicit lock, not snapshot.

### Retry is mandatory at RR/SERIALIZABLE

These levels abort conflicting txns instead of blocking — the app MUST catch and retry the whole transaction idempotently with backoff, not just re-run the failed statement:

- PostgreSQL: **SQLSTATE 40001** `could not serialize access…`; `40P01` deadlock.
- MySQL/InnoDB: **1213** deadlock (→40001); **1205** lock-wait timeout (`innodb_lock_wait_timeout`, default 50s).
- SQL Server: **3960** snapshot update conflict; **1205** deadlock victim.
- Oracle: **ORA-08177** can't serialize; **ORA-00060** deadlock.

Under snapshot RR only *writing* txns hit these; mark read-only txns `READ ONLY` (PG SSI skips them; `DEFERRABLE` waits for a safe snapshot).

### Deadlocks & lock ordering

Any 2PL engine deadlocks when txns take rows in different orders; the engine kills a victim. Acquire rows/tables in a consistent order app-wide, keep txns short, prefer one `UPDATE … WHERE` over read-then-write. InnoDB RR is deadlock-prone via gap locks on range updates and `INSERT … ON DUPLICATE KEY`; READ COMMITTED reduces this.

### Gotchas that bite through any driver

- **Keep txns short.** Open locks/old snapshots block VACUUM/undo cleanup → bloat. No network I/O or user think-time inside a txn; watch PG `idle_in_transaction_session_timeout`.
- **Sequences/identity don't roll back** — expect ID gaps after aborts; never assume gapless IDs.
- **Isolation is per-txn and reverts** after commit; setting it does not begin a txn.
- **`READ UNCOMMITTED` is not portable**: real dirty read in MySQL/SQL Server, an alias for READ COMMITTED in PG, absent in Oracle.
- **SERIALIZABLE costs**: PG predicate-lock memory (`max_pred_locks_per_transaction`; seq scans escalate to relation locks), SQL Server range-lock contention. Reserve for invariant-critical txns.

### Sources
- PostgreSQL 18 — Transaction Isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- MySQL 8.4 — InnoDB Transaction Isolation Levels: https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html
- SQL Server — SET TRANSACTION ISOLATION LEVEL: https://learn.microsoft.com/en-us/sql/t-sql/statements/set-transaction-isolation-level-transact-sql
- Oracle 23ai — Data Concurrency and Consistency: https://docs.oracle.com/en/database/oracle/oracle-database/23/cncpt/data-concurrency-and-consistency.html

## Parameterized queries & injection <a id="parameterized-queries-and-injection"></a>

A parameterized query compiles the SQL text (placeholders) once, then binds values as typed data
**never re-lexed as SQL** — quotes, `;`, comments stay inert. Separation, not escaping, is the
defense. Verified: PostgreSQL 18, MySQL 8.4 LTS, SQL Server 2022/2025, Oracle 23ai, SQLite 3.

### Placeholders (positional unless noted)
- **PostgreSQL:** `$1,$2` numbered.
- **MySQL/MariaDB:** `?` only — no wire-level named params.
- **SQLite:** `?`,`?NNN`,`:name`,`@name`,`$name`; bare `?` *discouraged* (miscount risk), don't
  mix named/numbered.
- **SQL Server:** `sp_executesql` uses `@p`; ODBC/TDS expose `?`.
- **Oracle:** `:name`/`:1`, but `EXECUTE IMMEDIATE ... USING` binds **by position** — name
  cosmetic; a repeated name consumes one arg each.

### Server-side vs client-side
Bind server-side; values ship apart from the text. Many drivers **emulate** params client-side,
interpolating escaped strings. OWASP: *"These libraries often just build queries with string
concatenation ... Please ensure that query parameterization is done server-side!"* Emulation
reopens charset/escaping edges — prefer server-side prepares for untrusted input.

### Stacked queries
Prepared/extended paths run **one command only** (two statements = syntax error). Paths that *do*
stack into `; DROP TABLE ...`: Postgres **simple protocol**/`PQexec` and MySQL multi-statement
mode — off by default, toggled per driver (JDBC/Connector-J `allowMultiQueries=true`, C API
`CLIENT_MULTI_STATEMENTS`). Never route untrusted text through those.

### Identifiers can't be bound
`?`/`$1` bind **values only**; table/column names and `ASC`/`DESC` can't be params (OWASP). Map
input to a fixed code-side allowlist, reject the rest. Quote a dynamic identifier with the
engine's quoter — Postgres `format('%I',x)`/`quote_ident()`, SQL Server `QUOTENAME()` — never
hand-built quotes.

### Dynamic SQL in procedures
Procedures aren't auto-safe: Oracle `EXECUTE IMMEDIATE ... USING` and SQL Server `sp_executesql`
bind, but `EXEC(@sql)` and Oracle string-built SQL don't. Beware **second-order injection** — a
value safely bound on insert, later concatenated into dynamic SQL, stays exploitable; bind again
at the second use.

### Gotchas (any driver)
- **LIKE:** binding stops injection, but `%`/`_` in the value stay wildcards — escape them,
  declare `ESCAPE '\'`.
- **NULL:** `col = $1` never matches NULL — use `IS NOT DISTINCT FROM`. Oracle `USING` rejects
  literal `NULL`; pass a typed variable.
- **Plan-cache cliffs:** Postgres `plan_cache_mode=auto` runs 5 custom plans then may lock a
  **generic** plan (bad for skewed data) — pin `force_custom_plan`; same class as Oracle bind
  peeking / SQL Server parameter sniffing.
- **IN-lists:** one placeholder ≠ a list — emit one marker per element or bind an array
  (`WHERE id = ANY($1)` on Postgres); one stable plan, dodges `max_prepared_stmt_count`.
- **Least privilege:** never run the app as DBA/owner (OWASP).

### Sources
- PostgreSQL 18 — libpq `PQexecParams`: https://www.postgresql.org/docs/current/libpq-exec.html
- MySQL Connector/J — Security props: https://dev.mysql.com/doc/connector-j/en/connector-j-connp-props-security.html
- OWASP — SQL Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- OWASP — Query Parameterization: https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html

## Indexing & query plans <a id="indexing-and-query-plans"></a>

Engine-level index + planner behavior across relational engines (not ORM usage — see lore/orm.md). Current stable: PostgreSQL **18**, MySQL **8.4 LTS**, SQL Server **2025** (v17), SQLite **3.x**. Verify version-gated facts against the target engine.

### Read the plan before you touch an index

- **Postgres**: `EXPLAIN (ANALYZE, BUFFERS) <query>`. `ANALYZE` executes the query — wrap DML in `BEGIN; … ROLLBACK;`. Since **PG18** `BUFFERS` is auto-on with `ANALYZE` (`BUFFERS OFF` to suppress). Compare estimated `rows=` vs `(actual … rows=… loops=N)`; when `loops>1` the shown time/rows are **per-loop averages** — multiply by `loops` for the total. A big estimate-vs-actual gap = a stats problem, not an index problem.
- **MySQL**: `EXPLAIN FORMAT=TREE` (8.0.16+) or `EXPLAIN ANALYZE` (8.0.18+, runs the query). In classic EXPLAIN, `type` best→worst: `const`/`eq_ref`/`ref` (good) → `range` → `index` (full index scan) → `ALL` (full table scan, bad). `Extra` red flags: `Using filesort`, `Using temporary`; good: `Using index` (covering), `Using index condition` (ICP).
- **SQLite**: `EXPLAIN QUERY PLAN` — `SEARCH … USING INDEX` good, `SCAN` = full scan.
- **SQL Server**: capture the *actual* plan (`SET STATISTICS IO, TIME ON`; `SET SHOWPLAN_XML ON`) or Query Store. Look for Index Seek vs Scan and stray Key/RID Lookups.
- **DON'T** trust plans from tiny or empty tables — costs aren't linear and the planner rationally scans small tables. Test on realistic row counts.

### Keep predicates sargable

- **DO** leave the indexed column bare on one side: `WHERE created_at >= $1`, never `WHERE date(created_at)=$1` or `WHERE price+0=$1`. Any function/cast on the column disables its B-tree index (→ full scan). Fix with an **expression index** (Postgres `CREATE INDEX ON t ((lower(email)))`; SQL Server computed+indexed column) or rewrite as a range.
- Leading-wildcard `LIKE '%x'` can't use a B-tree; anchored `LIKE 'x%'` can — but in Postgres a non-C locale needs a `text_pattern_ops`/`varchar_pattern_ops` opclass for pattern indexing.
- **Implicit coercion** silently kills indexes: comparing an indexed `VARCHAR` to a number, or joining columns with mismatched type/charset/collation (MySQL: comparing `utf8mb4` to `latin1`) forces a scan.

### Composite indexes: column order is the whole game

- An index on `(a,b,c)` serves `a`, `(a,b)`, `(a,b,c)` — **never** `b` alone or `(b,c)` (leftmost-prefix rule, same in Postgres/MySQL/SQLite/SQL Server).
- Put equality columns first, then **one** range/inequality column, then the `ORDER BY` column. A range predicate "uses up" the prefix: columns after it can't be used for seeking (only filtering).
- An index that matches `WHERE` **and** `ORDER BY` eliminates the sort (no `Using filesort` / no `Sort` node). MySQL 8.0+ can also read an index backward for `DESC`.
- **DON'T** keep an index that is a strict prefix of another — it's redundant; drop it.
- Postgres **PG18** skip-scan lets a multicolumn B-tree help even when the leading column isn't filtered (visible as multiple `Index Searches`), but a purpose-ordered index still beats it.

### Covering / index-only scans

- **Postgres**: an index-only scan needs every referenced column in the index **and** the heap pages marked all-visible — so it depends on VACUUM. Check `Heap Fetches:` in EXPLAIN; high fetches mean VACUUM lag, not a win. Add payload with `INCLUDE` (PG11+) to keep the key narrow and uniqueness on key columns only. GIN indexes can't do index-only scans.
- **InnoDB**: every secondary-index leaf stores the **primary key** (not a row pointer), so a non-covering lookup does a second "bookmark" seek into the clustered index. A covering index (`Extra: Using index`) skips it. Keep the PK short — it is copied into every secondary index.
- **SQL Server**: a nonclustered index with `INCLUDE` columns removes the Key/RID Lookup.

### Clustered vs heap storage

- InnoDB, SQLite rowid tables, and SQL Server clustered tables store rows in key order — PK lookups hit the leaf directly. A random/UUID PK scatters inserts and causes page splits + index fragmentation; prefer a monotonic surrogate key (or accept the documented write cost). SQLite `WITHOUT ROWID` swaps the rowid for the declared PK.
- **DON'T** make the clustered/primary key wide in InnoDB or SQL Server — it inflates every secondary index.

### Statistics drive the planner (cost-based)

- Stale stats → wrong cardinality estimates → wrong plan (scan chosen over seek, or a bad join order). After a bulk load or big delete, refresh explicitly: Postgres `ANALYZE` (autovacuum does it lazily), MySQL `ANALYZE TABLE` (+ `UPDATE HISTOGRAM` for skewed **non-indexed** columns), SQLite `ANALYZE`, SQL Server auto-update stats / `UPDATE STATISTICS`.
- SQL Server caches plans and reuses them — beware **parameter sniffing** (a plan compiled for an atypical parameter reused for all); mitigate with `OPTIMIZE FOR`, `RECOMPILE`, or Query Store plan forcing.

### Don't over-index — indexes cost writes

- Every index is maintained on every INSERT/UPDATE/DELETE and consumes buffer cache. **DON'T** add indexes on low-cardinality columns for equality alone — the planner will scan anyway. Use **partial indexes** (Postgres/SQLite `… WHERE active`; SQL Server filtered index) for a hot subset.
- Match index type to the query — B-tree for `=`, range, and sort; Postgres **GIN** for `jsonb`/array/full-text containment (`@>`, `&&`), **GiST** for ranges/geo/KNN (`<->`), **BRIN** for huge naturally-ordered tables, hash only for `=`.
- A Postgres Bitmap Heap Scan combining two indexes (BitmapAnd/Or) is a hint that one well-ordered composite index would serve better.

### Sources

- PostgreSQL 18 — Using EXPLAIN: https://www.postgresql.org/docs/current/using-explain.html
- PostgreSQL 18 — Index Types & Index-Only Scans: https://www.postgresql.org/docs/current/indexes-types.html , https://www.postgresql.org/docs/current/indexes-index-only-scans.html
- MySQL 8.4 — EXPLAIN Output & How MySQL Uses Indexes: https://dev.mysql.com/doc/refman/8.4/en/explain-output.html , https://dev.mysql.com/doc/refman/8.4/en/mysql-indexes.html
- SQLite — Query Planner: https://www.sqlite.org/queryplanner.html
- SQL Server 2025 — Execution Plans Overview: https://learn.microsoft.com/en-us/sql/relational-databases/performance/execution-plans

## Migrations & schema changes <a id="migrations-and-schema-changes"></a>

Engine-level DDL mechanics: how ALTER/CREATE execute, lock, rewrite, replicate. For migration-*tool* workflow (checksums, changesets, expand-contract sequencing) see lore/deep/db-migrations.md. Verified against PostgreSQL 18, MySQL 8.0 / 8.4 LTS, SQLite 3.53 (see Sources).

### Transactional DDL — sizes your migrations
- **PostgreSQL: fully transactional.** CREATE/ALTER/DROP roll back atomically, so a multi-statement migration is all-or-nothing. Can't run in a txn block: `CREATE/DROP INDEX CONCURRENTLY`, `CREATE DATABASE`, `VACUUM`, `ALTER SYSTEM`.
- **MySQL / MariaDB: not transactional.** MySQL 8 "atomic DDL" makes a *single* statement crash-safe (InnoDB data dictionary) but "is not transactional DDL" — DDL "implicitly end[s] any transaction … as if you had done a COMMIT." One DDL per migration; a mid-migration failure leaves earlier statements committed. InnoDB only.
- **SQLite: transactional**, but `ALTER` is minimal (below).

### PostgreSQL lock levels — the real footgun
Most `ALTER TABLE` forms take `ACCESS EXCLUSIVE`; with multiple subcommands "the lock acquired will be the strictest one required by any subcommand." The danger is the queue: a blocked ALTER waits behind one long query, then every *new* query queues behind the ALTER — a sub-ms lock request freezes the whole table. Guard each session: `SET lock_timeout='3s';` (+ `statement_timeout`) so contended DDL fails fast, then retry. Cheaper locks (writes continue): `VALIDATE CONSTRAINT`, `SET STATISTICS` = `SHARE UPDATE EXCLUSIVE`; `ADD FOREIGN KEY` = `SHARE ROW EXCLUSIVE`.

### PostgreSQL — dodge rewrites & full scans (version-gated)
- **ADD COLUMN with a non-volatile DEFAULT is metadata-only** — value stored in the catalog, "very fast even on large tables" (PG11+). A *volatile* default, stored generated column, or identity column rewrites the whole table + indexes.
- **SET NOT NULL scans the table**, but the scan "is skipped" "if a valid CHECK constraint exists … which proves no NULL can exist" (PG12+): `ADD CONSTRAINT c CHECK (col IS NOT NULL) NOT VALID` → `VALIDATE CONSTRAINT c` → `SET NOT NULL`.
- **Constraints: `ADD … NOT VALID` then `VALIDATE`.** NOT VALID commits immediately without scanning (enforced on new rows); VALIDATE takes only `SHARE UPDATE EXCLUSIVE`. Allowed for FK, CHECK, not-null.
- **`ALTER COLUMN … TYPE` rewrites** table + indexes *unless* the old type is binary-coercible (e.g. `text`↔`varchar`, no collation change). Bundle subcommands in one `ALTER TABLE` to make a single pass. Rewriting forms "are not MVCC-safe": the table "will appear empty" to snapshots taken before the rewrite.

### PostgreSQL — indexes without blocking writes
`CREATE INDEX CONCURRENTLY` builds without blocking DML (plain `CREATE INDEX` "locks out writes … until it's done"). Cost: can't run in a txn block, does *two* scans and "must wait for all existing transactions … to terminate," and on failure "leave[s] behind an 'invalid' index" that still adds write overhead — `DROP` and retry, or `REINDEX INDEX CONCURRENTLY` (PG12+). A failed *unique* index keeps enforcing uniqueness. On partitioned tables build per-partition then create the parent index (metadata only). Remove with `DROP INDEX CONCURRENTLY`.

### MySQL — online DDL (ALGORITHM / LOCK)
Name both so the server *errors* rather than silently doing a copy.
- **`ALGORITHM=INSTANT`** (metadata only): default for `ADD COLUMN` since 8.0.12, `DROP COLUMN` since 8.0.29 (any position since 8.0.29). Caps: max **64** row versions before INSTANT add/drop is rejected (a table rebuild / `OPTIMIZE TABLE` resets it); ≤1022 internal columns; unavailable on `ROW_FORMAT=COMPRESSED` or FULLTEXT tables.
- **`ALGORITHM=INPLACE, LOCK=NONE`**: rebuilds in place with concurrent read+write (add secondary index, NULL/NOT NULL).
- **Falls to `ALGORITHM=COPY`** (blocks writes) for: changing a column's data type, shrinking a VARCHAR or crossing the 256-byte boundary, dropping a PK alone, adding a STORED generated column.
- **Metadata locks (MDL)** are held until the surrounding transaction ends — one long/idle-in-transaction session blocks *all* DDL on that table. Kill blockers; set `lock_wait_timeout` low.

### Replication & tables too big to lock
DDL replicates; a long copying `ALTER` on the primary serializes on each replica's apply → replication lag. For tables too big to lock, use a shadow-copy+swap tool: **gh-ost** / **pt-online-schema-change** (MySQL), **pg_repack** (Postgres). PostgreSQL logical replication does NOT ship DDL — apply the change on each side yourself, or a new column breaks the apply.

### SQLite — minimal ALTER
Supported: `RENAME TABLE`, `RENAME COLUMN` (3.25+), `ADD COLUMN` (appended; NOT NULL needs a non-NULL default), `DROP COLUMN` (3.35+; fails if PK/UNIQUE/indexed/in a CHECK/FK/generated/trigger/view), `ALTER COLUMN SET/DROP NOT NULL` (3.53+). Anything else (reorder, retype, add/drop PK or UNIQUE) needs the recreate procedure: `PRAGMA foreign_keys=OFF` → `BEGIN` → CREATE new table → `INSERT…SELECT` → DROP old → RENAME new *into* place → recreate indexes/triggers/views → `PRAGMA foreign_key_check` → `COMMIT` → `PRAGMA foreign_keys=ON`. Build under a temp name and rename into the final name; renaming the *old* table first "might corrupt references … in triggers, views, and foreign key constraints."

### Sources
- PostgreSQL 18 ALTER TABLE (locks, rewrite rules, NOT VALID, fast default, MVCC): https://www.postgresql.org/docs/current/sql-altertable.html
- PostgreSQL 18 CREATE INDEX (CONCURRENTLY, invalid index): https://www.postgresql.org/docs/current/sql-createindex.html
- PostgreSQL versioning (18 current; 14–18 supported): https://www.postgresql.org/support/versioning/
- MySQL 8.4 Atomic DDL (atomic ≠ transactional; implicit commit): https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html
- MySQL 8.0 InnoDB online DDL (ALGORITHM/LOCK, INSTANT limits/versions): https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html
- SQLite ALTER TABLE (supported forms, versions, recreate procedure): https://www.sqlite.org/lang_altertable.html

## Resilience & observability <a id="resilience-and-observability"></a>

*Engine-side reliability and telemetry, driver-agnostic. Pool sizing lives in lore/deep/jdbc.md#connections-and-pooling — this file is the engine's own timeouts, retry semantics, failover, and stats surfaces.*

Versions: PostgreSQL 18 / MySQL 8.4 LTS. OpenTelemetry DB **semconv is Stable** for span attrs (`db.system.name`, `db.query.text`, `db.namespace`, `db.operation.name`) and the metric `db.client.operation.duration`; connection-pool metrics remain Development.

### Bound everything with a timeout — DO
Uncapped statements are the top cause of pile-ups and connection exhaustion. Set them **server-side**, not just as a client socket read timeout:
- Postgres (all default `0`=off, ms; set per-role/session, NOT globally in postgresql.conf): `statement_timeout` (per-statement exec), `lock_timeout` (per lock-wait — must be `< statement_timeout` or it never fires), `idle_in_transaction_session_timeout` (kills sessions holding locks / blocking vacuum), `transaction_timeout` (whole-txn, **added in PG 17**; prepared txns exempt).
- MySQL: `max_execution_time` ms (SELECT only) or the `MAX_EXECUTION_TIME(n)` hint; `innodb_lock_wait_timeout` (default 50s); `wait_timeout`/`interactive_timeout` for idle conns.
- DON'T rely on a client read-timeout alone — it abandons the result but the server keeps executing, burning CPU and holding locks.

### Retry the retryable, only — DO
Classify by SQLSTATE, not message text (codes are stable across releases):
- **Always retry the whole transaction:** `40001` serialization_failure, `40P01` deadlock_detected (MySQL `1213` deadlock, `1205` lock-wait timeout). The loser rolled back cleanly, so replay is safe.
- **Reconnect, then retry:** class `08` connection failures (`08006`/`08001`/`08004`) — the txn never committed.
- **DON'T blind-retry** `40003`/`08007` (completion/resolution unknown) or non-idempotent writes — outcome is ambiguous; verify state or use an idempotency key.
- Use **exponential backoff with full jitter**, bounded (~5 tries). Un-jittered retries resynchronize clients into a thundering herd. Retry at the transaction boundary (re-run `BEGIN…COMMIT`), never a single statement mid-txn.

### Failover & connection storms — DO
- libpq multi-host + `target_session_attrs=read-write` auto-lands on the current primary (skips hot-standbys and `default_transaction_read_only`); pair with a small `connect_timeout` (it applies *per host*, so N×timeout is worst case). `load_balance_hosts=random` spreads reads across replicas.
- Set TCP `keepalives` / `tcp_user_timeout` so a black-holed peer is detected in seconds, not the OS default minutes.
- After an outage, prevent a reconnect stampede: cap pool growth, jitter reconnects, and put a **circuit breaker** in front so a downed DB fast-fails instead of queuing every request onto pool wait-time.
- DON'T route writes to a replica — check writability via `target_session_attrs`; a static host role moves on failover.

### Observe what the engine already records — DO
- **Postgres:** `pg_stat_statements` (needs `shared_preload_libraries` + `compute_query_id=on`) aggregates *normalized* queries by `queryid` with `calls`, `total_exec_time`, `mean_exec_time`, `rows`, buffer hit-ratio, `wal_bytes` — sort by total time to find real cost. `auto_explain` (`session_preload_libraries`, set `log_min_duration`) logs slow-statement plans automatically, but `log_analyze` times **every** node of **every** query (severe overhead) — use `sample_rate`, consider `log_timing=off`. Live state: `pg_stat_activity` (`wait_event`, `state`), `pg_stat_replication`/`_slots` for lag.
- **MySQL:** prefer `performance_schema.events_statements_summary_by_digest` (in-memory, all statements, normalized digest) and `sys`-schema views over the file slow log, which misses fast-but-frequent queries. Slow log: `slow_query_log`, `long_query_time` (default 10s), `log_queries_not_using_indexes`.
- **Trace & correlate:** emit OTel client spans whose duration covers *all retries*; sanitize literals from `db.query.text` (→ `?`) — parameterized text may be captured as-is. Use **SQLCommenter** to append `/*key='val'*/` tags so slow-log and `pg_stat_statements` rows carry the originating service/route/trace-id.
- DON'T ship raw statement text with embedded literals to your APM — PII leak plus cardinality blow-up; lean on the engine's normalization.

### Sources
- https://www.postgresql.org/docs/current/runtime-config-client.html
- https://www.postgresql.org/docs/current/errcodes-appendix.html
- https://www.postgresql.org/docs/current/pgstatstatements.html
- https://www.postgresql.org/docs/current/auto-explain.html
- https://www.postgresql.org/docs/current/libpq-connect.html
- https://dev.mysql.com/doc/refman/8.4/en/slow-query-log.html
- https://opentelemetry.io/docs/specs/semconv/database/database-spans/
- https://opentelemetry.io/docs/specs/semconv/database/database-metrics/
- https://google.github.io/sqlcommenter/
