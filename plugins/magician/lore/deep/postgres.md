# PostgreSQL — deep dive

> On-demand companion to `lore/postgres.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Connection & pooling](#connection-and-pooling) · [Types & JSONB](#types-and-jsonb) · [Indexing, MVCC & vacuum](#indexing-mvcc-and-vacuum) · [Transactions and Locking](#transactions-and-locking) · [Partitioning & Scale](#partitioning-and-scale) · [Performance](#performance)

## Connection & pooling <a id="connection-and-pooling"></a>

Engine-side connection semantics plus the libpq parameters every driver inherits (pgx, rust-postgres, npgsql, psycopg, JDBC mirror these keyword/URI options). Current stable **18**; supported **14–18** (13 EOL 2025-11). Client-pool config: lore/deep/jdbc.md#connections-and-pooling; PgBouncer modes and the pool-size formula: lore/deep/databases.md#connection-pooling — this file is the *server + protocol* layer.

### Process model — why you must pool

The postmaster **forks an OS process (backend) per connection**. Each connect pays fork + authentication + optional TLS handshake + catalog/relcache warmup; idle backends still hold memory and get scanned for snapshot/xid work. `max_connections` (default **100**) is **restart-only** and directly sizes shared memory — don't crank it to dodge pooling. `superuser_reserved_connections` (**3**) and `reserved_connections` (**0**, since 16) keep emergency slots so admins can still log in when full; exhaustion returns `FATAL 53300` "sorry, too many clients already". Front Postgres with an external pooler for any web workload.

### libpq connection semantics (driver-generic)

- `host=a,b,c` tries hosts in order; **`connect_timeout` is per-host** (N hosts × timeout = worst case) — always set it.
- `target_session_attrs`: `any`/`read-write` since 10; `read-only`/`primary`/`standby`/`prefer-standby` **since 14** — cheap read/write split and failover with no proxy.
- `load_balance_hosts=random` **since 16** shuffles hosts and DNS addresses; pair with `connect_timeout` to skip dead nodes.
- Set `application_name` — it surfaces in `pg_stat_activity` and logs, making load attributable per service.

### TLS & auth — never ship `prefer`

- `sslmode=prefer` (default) encrypts but does **not** verify and silently downgrades to plaintext. Use **`verify-full`** for real MITM protection. `sslrootcert=system` (16+) loads the OS CA store and *implies* `verify-full`.
- `sslnegotiation=direct` (**17**) starts TLS immediately, saving the negotiation round trip; requires `sslmode>=require`.
- `password_encryption` defaults to **`scram-sha-256` since 14** (md5 deprecated). Harden SCRAM with `channel_binding=require`; pin the server's method via `require_auth=scram-sha-256` (16+).
- GSSAPI encryption is preferred over SSL when available — set `gssencmode=disable` if you rely on `sslmode`.

### Dead-connection detection

Poolers, NAT, and firewalls silently reap idle sockets; the app later hands out a corpse. Defenses: server `tcp_keepalives_idle/interval/count` and `tcp_user_timeout`; **`client_connection_check_interval`** (**14**, Linux/BSD/macOS) lets a backend notice a vanished client mid-query and abort wasted work; client-side libpq `keepalives*`; and a client-pool `maxLifetime` shorter than any idle reaper on the path.

### Session-hygiene timeouts

Set per-role/session, not globally in `postgresql.conf`:
- **`idle_in_transaction_session_timeout`** — the most important one: kills sessions that `BEGIN` then stall, which pin `xmin`, block vacuum, and bloat tables.
- `statement_timeout`, `lock_timeout`; **`transaction_timeout`** (**17**) bounds the whole transaction (prepared txns exempt).
- `idle_session_timeout` (**14**) reaps idle non-tx sessions — use cautiously behind a pooler that validates/reuses sockets. Apply via `ALTER ROLE app SET statement_timeout='30s'` or connect `options='-c statement_timeout=30000'`.

### Pooler interaction (engine side)

Under **transaction pooling** a client hops backends every transaction, so session state does not persist: plain `SET`, session temp tables, `LISTEN/NOTIFY`, session advisory locks, and `WITH HOLD` cursors break. Use `SET LOCAL` inside the tx; put durable knobs on the role. Drivers that default to **server-side prepared statements** (extended protocol) fail under transaction pooling unless the pooler tracks them (PgBouncer ≥1.21) or you disable statement caching. Watch `pg_stat_activity.state` (`active`/`idle`/`idle in transaction`/`idle in transaction (aborted)`); rising `idle in transaction` = a leak. `pg_stat_ssl`/`pg_stat_gssapi` confirm per-backend encryption.

### Sources

- PostgreSQL 18 — Connection settings (max_connections, reserved_connections, tcp/keepalive, client_connection_check_interval): https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL 18 — libpq connect parameters (target_session_attrs, load_balance_hosts, sslmode, sslnegotiation, require_auth): https://www.postgresql.org/docs/current/libpq-connect.html
- PostgreSQL 18 — Client statement/idle timeouts (idle_session_timeout 14, transaction_timeout 17): https://www.postgresql.org/docs/current/runtime-config-client.html
- PostgreSQL — Versioning policy (18 stable; 14–18 supported): https://www.postgresql.org/support/versioning/
- PostgreSQL 18 — Monitoring / pg_stat_activity state values: https://www.postgresql.org/docs/current/monitoring-stats.html

## Types & JSONB <a id="types-and-jsonb"></a>

Spans supported majors 14–18 (18 stable; 13 EOL 2025-11). Feature gates noted inline.

### Scalar type choices
- `numeric`/`decimal` is exact; `real`/`double precision` are inexact IEEE floats (`0.1::real+0.2::real` ≠ `0.3`). Use `numeric` for money — never `float` or the locale-dependent `money`.
- `timestamptz` stores no zone: input converts to UTC, renders back in the session `TimeZone`. `timestamp` is zoneless wall-clock. Prefer `timestamptz` and set `TimeZone` explicitly.
- `text`, `varchar`, `varchar(n)` share identical storage; `char(n)` is blank-padded and slower — avoid. Length caps are check constraints, no perf win.
- Prefer `GENERATED ALWAYS AS IDENTITY` over `serial`; key on `bigint` or `uuidv7()` (18). `gen_random_uuid()` is built in (no `pgcrypto`). Arrays are 1-based (`= ANY(arr)`; GIN `array_ops` for `@>`/`&&`). Enum order follows declaration; `ALTER TYPE ... ADD VALUE` can't be used later in the same transaction that added it, and labels can't be reordered/removed.

### json vs jsonb
`json` keeps exact text (whitespace, key order, duplicate keys), is re-parsed per access, and can't be indexed. `jsonb` is decomposed binary: duplicate keys collapse (last wins), order/whitespace lost, numbers normalize to `numeric` (big integers round-trip exactly in-engine, though a JS driver parsing to `double` may lose precision). Default to `jsonb`; pick `json` only for byte-exact reproduction.

### Operators & path
- Extract `->` (jsonb), `->>` (text), `#>`/`#>>` (path) return SQL NULL on a missing path, never error.
- `@>` containment is nested and order-insensitive; `?`/`?|`/`?&` existence is **top-level only**, matching keys/array-elements, never values.
- jsonpath (12+): `@?` (any match), `@@` (predicate) suppress structural/type errors. `lax` (default) auto-wraps/unwraps arrays and swallows structural errors; `strict` raises them — reserve `.**` for strict (it double-selects in lax).
- SQL/JSON constructors + `IS JSON` arrived in 16; `JSON_TABLE`/`JSON_QUERY`/`JSON_VALUE`/`JSON_EXISTS` in 17 — don't reference on ≤15.

### Indexing jsonb
- GIN `jsonb_ops` (default) indexes every key and value; supports `@>`,`@?`,`@@`,`?`,`?|`,`?&`. Larger.
- GIN `jsonb_path_ops` indexes value-paths only; supports just `@>`,`@?`,`@@` (no key-existence), smaller/faster, but emits nothing for valueless structures like `{"a":{}}`.
- `WHERE data->>'k'='v'` uses neither — add a btree **expression index** on `(data->>'k')`, or an expression GIN on a subdocument (`(data->'tags')`).
- GIN serves no ordering or `<`/`>` ranges. `fastupdate` defers inserts to a pending list (flushed by vacuum / `gin_pending_list_limit` / `gin_clean_pending_list()`): fast writes, but searches also scan the list and an oversized one forces a slow foreground cleanup — disable it when latency must be steady.

### Mutation & subscripting
- Subscripting (14+) is 0-based (`data['a']['b']`), auto-creates/pads nested containers, no slices. `jsonb_set(target,path,val,create_if_missing)` edits by path; `jsonb_set_lax` (13+) handles a SQL-NULL value via `null_value_treatment` (`use_json_null` default, or `raise_exception`/`delete_key`/`return_target`). Plain `jsonb_set` with any SQL-NULL argument returns NULL for the whole row — a silent data-wipe.
- MVCC: editing one key rewrites the whole document as a new row version and re-inserts all its GIN entries; large `jsonb` is TOAST-compressed and read/written whole. Keep hot-updated or heavily-filtered fields as real columns, not buried in a blob.

### Driver gotchas
- `?`/`?|`/`?&` collide with `?` bind placeholders. In pgJDBC escape as `??`; else avoid the family with `jsonb_path_exists(col,'$.key')` (no `?` char).
- Bind `jsonb` params with an explicit `::jsonb` cast (or the driver's json type); as `unknown`/text, inference can fail or store as `text`.
- SQL NULL, JSON `null`, and an absent key differ: `->>'missing'` is SQL NULL; `->'k'` of a JSON null is `'null'::jsonb`. A NUL char is illegal inside `jsonb` strings even when escaped.

### Sources
- https://www.postgresql.org/docs/current/datatype-json.html
- https://www.postgresql.org/docs/current/functions-json.html
- https://www.postgresql.org/docs/current/datatype.html
- https://www.postgresql.org/docs/current/gin.html
- https://jdbc.postgresql.org/documentation/query/

## Indexing, MVCC & vacuum <a id="indexing-mvcc-and-vacuum"></a>

Version span 13→18 (current stable 18.4). PG18 adds an async-I/O subsystem (`io_method`, speeds seq/bitmap scans and vacuum) plus B-tree skip scan and `autovacuum_vacuum_max_threshold`; PG17 lifted VACUUM's old 1 GB memory cap. Verify any "since vX" against the target server before relying on it.

### MVCC: how row versions and dead tuples arise
Every heap tuple carries hidden `xmin` (creating XID) and `xmax` (deleting/obsoleting XID). UPDATE is never in-place — it writes a NEW tuple and stamps the old one's `xmax`; DELETE just stamps `xmax`. Each statement (Read Committed) or transaction (Repeatable Read / Serializable) runs against a snapshot; a tuple is visible if its `xmin` committed before the snapshot and `xmax` is unset or not-yet-visible. Hence readers never block writers. The cost: obsolete versions ("dead tuples") linger on-page until no snapshot can see them — that is bloat, and only VACUUM reclaims it.
- The oldest live snapshot pins the removal cutoff. A long query, an abandoned `idle in transaction` session, an unused replication slot, or `hot_standby_feedback = on` all hold back the global `xmin` and stop VACUUM from cleaning dead tuples DB-wide, even in unrelated tables. Hunt them: `SELECT pid, state, xact_start, backend_xmin FROM pg_stat_activity ORDER BY backend_xmin;` and set `idle_in_transaction_session_timeout`.

### Index types — pick by access pattern
- **B-tree** (default): `=`, range, `ORDER BY`, `IS NULL`, anchored `LIKE 'foo%'`. Backs UNIQUE/PK, multicolumn, `INCLUDE`. Multicolumn `(a,b)` historically needed a leading-`a` predicate; **PG18 skip scan** lets it serve `WHERE b = …` (or non-equality on `a`) by skipping distinct `a` values.
- **Hash**: `=` only; WAL-logged and crash-safe since 10, but rarely beats B-tree.
- **GIN**: multi-valued columns — `jsonb`, arrays, full-text (`tsvector`), trigram (`pg_trgm`). For containment use `jsonb_path_ops` + `@>` (smaller/faster than default `jsonb_ops`).
- **GiST**: geometry, ranges, exclusion constraints, nearest-neighbor (`ORDER BY geom <-> point`).
- **SP-GiST**: non-balanced (quadtree/trie) — points, IP/inet, text prefixes.
- **BRIN**: tiny per-block-range summaries; only pays off when the column is physically correlated with heap order (append-only timestamps/ids). PG14+ `minmax_multi` opclasses tolerate mild disorder.

### HOT updates — keep churn off the indexes
A **HOT** (heap-only tuple) update skips creating new index entries when (a) NO indexed column changed and (b) the new version fits on the same page. HOT chains are pruned during ordinary reads, not just VACUUM — a large win for hot-updated rows. Encourage it: lower `fillfactor` (`WITH (fillfactor=80)`) to reserve page space, and don't index columns you update frequently. Measure `n_tup_hot_upd / n_tup_upd` in `pg_stat_all_tables`. (BRIN is a "summarizing" index and does not block HOT eligibility.)

### Index-only scans & covering indexes
An index-only scan avoids the heap — but only for heap pages flagged all-visible in the **visibility map**, which VACUUM maintains. So on a write-heavy, under-vacuumed table, "index-only" plans still fault into the heap; watch `Heap Fetches` in EXPLAIN. `INCLUDE` adds non-key payload (`CREATE INDEX … (x) INCLUDE (y)`) so a covering index works without widening the uniqueness key. GIN never supports index-only scans (entries hold only part of the value).

### Building indexes without an outage
Plain `CREATE INDEX` takes a `SHARE` lock and blocks writes. On live tables use `CREATE INDEX CONCURRENTLY` (SHARE UPDATE EXCLUSIVE, writes continue): it does two heap passes, is slower, cannot run inside a transaction block, and on failure leaves an INVALID index you must `DROP INDEX` then recreate (check `pg_index.indisvalid`). `REINDEX INDEX CONCURRENTLY` (12+) rebuilds bloated indexes online. Always pair schema DDL with `SET lock_timeout` so a blocked `ALTER`/index build cannot queue an `ACCESS EXCLUSIVE` request ahead of normal traffic.

### VACUUM, freezing & wraparound
Plain `VACUUM` marks dead space reusable (non-blocking; space is returned to the OS only for trailing empty pages). `VACUUM FULL` and `CLUSTER` rewrite the table under `ACCESS EXCLUSIVE` — avoid on live tables; use them only for one-off heavy bloat. Beyond bloat, VACUUM must **freeze** old XIDs: XIDs are 32-bit, so every table must be vacuumed before ~2 billion transactions or wraparound makes committed rows vanish (WARNING at 40M remaining, writes refused at 3M). Track `age(relfrozenxid)` per table and `age(datfrozenxid)` per DB.
- Autovacuum fires at `autovacuum_vacuum_threshold` (50) + `autovacuum_vacuum_scale_factor` (0.2) × reltuples — too lazy on big tables; lower the per-table scale factor (e.g. `0.02`) on hot ones. Insert-mostly tables need `autovacuum_vacuum_insert_threshold` (1000, since 13) to get visibility-map/freeze maintenance. PG18 caps the computed trigger with `autovacuum_vacuum_max_threshold` (100M).
- Freeze knobs: `autovacuum_freeze_max_age` (200M) forces an anti-wraparound autovacuum even if autovacuum is disabled and even amid conflicting locks; `vacuum_failsafe_age` (14+, default 1.6B) makes VACUUM drop cost delays and skip index cleanup to race wraparound. PG18 `vacuum_max_eager_freeze_failure_rate` lets normal vacuums proactively freeze all-visible pages, cutting future aggressive-scan work.
- **PG17** removed VACUUM's silent 1 GB dead-tuple memory limit and stores TIDs far more compactly, so raising `maintenance_work_mem` / `autovacuum_work_mem` now genuinely reduces index-cleanup passes. Monitor with `pg_stat_progress_vacuum` (17 switched its counters to byte-based: `max_dead_tuple_bytes`, `num_dead_item_ids`). PG13+ vacuums multiple indexes in parallel, bounded by `max_parallel_maintenance_workers`.

### Diagnosing
Use `EXPLAIN (ANALYZE, BUFFERS)`: compare estimated vs actual rows (large gap ⇒ stale stats — run `ANALYZE` or raise `default_statistics_target`/`ALTER TABLE … SET STATISTICS`); a big `Rows Removed by Filter` signals dead-tuple bloat or a missing partial/expression index; high `Heap Fetches` on an index-only scan means the visibility map is stale (VACUUM). `ANALYZE` is a distinct step from space reclamation, though autovacuum runs both.

### Sources
postgresql.org/docs/current/routine-vacuuming.html · postgresql.org/docs/current/runtime-config-vacuum.html · postgresql.org/docs/current/indexes-index-only-scans.html · postgresql.org/docs/current/storage-hot.html · postgresql.org/docs/current/btree.html · postgresql.org/docs/release/18.0 · postgresql.org/docs/release/17.0

## Transactions and Locking <a id="transactions-and-locking"></a>

Version: 18 stable; majors 14–18. SSI since 9.1; `SKIP LOCKED` since 9.5 (NOWAIT far older); `idle_in_transaction_session_timeout` since 9.6; `MERGE` since 15; `transaction_timeout` since **17**. 4 ANSI levels, **3** real (Read Uncommitted = Read Committed).

### Isolation (MVCC snapshots)
- **Read Committed** (default): fresh snapshot per *statement*; never raises `40001`, waits on row locks.
- **Repeatable Read** = snapshot isolation: snapshot frozen at first statement; no phantoms. Committed concurrent UPDATE/DELETE of a row you write → `40001`.
- **Serializable** (SSI): RR + predicate locks on read/write deps → also `40001`; catches write-skew, no extra blocking.
- **Retry mandatory** on `40001`/deadlock `40P01`: replay the *whole* tx, not the failing statement (snapshot stale; deadlock victim unpredictable, not always the "later" tx). Under Serializable, reads trustworthy only after commit.
- **RC lost-update trap:** `UPDATE ... WHERE` re-checks its predicate on the *new* row version, so a matching row can be silently skipped. Guard: `SELECT ... FOR UPDATE`, SQL arithmetic, `INSERT ... ON CONFLICT`, or RR/Serializable + retry.

### Locking modes
**Table** (eight; only conflicts matter, "ROW" names are still table locks): `ACCESS SHARE` (SELECT) vs only `ACCESS EXCLUSIVE`; `ROW EXCLUSIVE` (INSERT/UPDATE/DELETE/MERGE) vs SHARE+; `SHARE UPDATE EXCLUSIVE` (VACUUM, `CREATE INDEX CONCURRENTLY`) self-conflicts; `ACCESS EXCLUSIVE` (DROP/TRUNCATE/most `ALTER`, bare `LOCK TABLE`) blocks all incl. SELECT. Locks live to tx end.
**Row** (weak→strong): `FOR KEY SHARE` < `FOR SHARE` < `FOR NO KEY UPDATE` < `FOR UPDATE`. FK parent takes `FOR KEY SHARE`; non-key `UPDATE` takes `FOR NO KEY UPDATE`, so they don't block each other. `NOWAIT` (error) or `SKIP LOCKED` (skip); `FOR UPDATE SKIP LOCKED` = work-queue dequeue.

### Deadlocks, timeouts, advisory, 2PC
- Deadlocks after `deadlock_timeout` (**1s**); one tx aborts (`40P01`). Defenses: consistent lock order, strongest mode first, retry. Without a cycle a waiter blocks *forever* — never hold a tx across think-time.
- Guardrails (default 0/off): `lock_timeout` (set before `ALTER`/`CREATE INDEX`), `statement_timeout`, `idle_in_transaction_session_timeout`, `transaction_timeout` (17+). Set narrowly.
- **Advisory locks** (`pg_advisory_lock`/`_xact_lock`, `_try_` variants): advisory, not data-enforced. Session-level survive rollback + need explicit unlock (ref-counted); prefer `_xact_` (auto-release). Never `pg_advisory_lock(id) ... LIMIT n` — LIMIT may run after the lock → dangling locks.
- **2PC**: `PREPARE TRANSACTION` needs `max_prepared_transactions > 0` (default **0**); orphaned prepared xacts hold locks + block vacuum/wraparound — monitor `pg_prepared_xacts`.

### DON'T / driver gotchas
- Never leave sessions `idle in transaction` — they pin `xmin`, block VACUUM, bloat tables; the pool must COMMIT/ROLLBACK on every path.
- `nextval` never rolls back — `serial`/identity gaps are normal.
- Don't `SAVEPOINT` every statement: each is a subtransaction; past ~64 cached subxids per backend, all sessions pay `pg_subtrans` SLRU lookups (cluster-wide).
- Heavy shared row locks / FK churn create multixacts — watch multixact wraparound on write-heavy tables.
- DDL is transactional but takes strong table locks — keep short, pair `lock_timeout`.

### Sources
- postgresql.org/docs/18: transaction-iso, explicit-locking, runtime-config-{client,locks}.

## Partitioning & Scale <a id="partitioning-and-scale"></a>

Current stable 18; supported line 14→18. Declarative partitioning is the engine feature — treat legacy inheritance + `constraint_exclusion` (default `partition`) as legacy: plan-time only, degrades past ~100 children. Partition to shrink hot indexes and make bulk data lifecycle cheap — "never assume more partitions are better."

### Pick the method by access pattern
- **RANGE** (time-series, monotonic IDs): cheap retention — `DETACH`+`DROP TABLE` of an old partition is metadata-only versus a giant `DELETE`+`VACUUM`. Bounds are lower-inclusive, upper-exclusive (`10` lands in `[10,20)`).
- **LIST**: discrete keys (region, tenant class).
- **HASH** (`MODULUS m, REMAINDER r`): even write spread, but **no pruning on range predicates** — only equality on the key prunes.

Updating a row's partition-key value moves it to the right partition (row movement). A `DEFAULT` partition catches unmatched rows; without one, an unroutable INSERT errors.

### Pruning is the point — and it only reads the partition key
`enable_partition_pruning` is `on`. The planner prunes at **plan time** from key predicates; for prepared-statement params or subquery/nested-loop values it prunes at **execution time** — see `Subplans Removed` and `(never executed)` in `EXPLAIN (ANALYZE, BUFFERS)`. Pruning is driven by partition-**key** constraints, **not indexes**: a query that doesn't filter the partition key touches every partition. Gotcha: partitions pruned at executor *init* are still **locked** at statement start, so lock count scales with partitions even when scans don't.

### Keys, uniqueness, indexes
A UNIQUE/PRIMARY KEY is enforced per-partition, so its columns **must include every partition-key column**, and the key **can't be an expression**; there is no global cross-partition unique index. Exclusion constraints must compare all partition-key columns for equality. `CREATE INDEX CONCURRENTLY` is unsupported on the parent — build it bottom-up without long locks:
```sql
CREATE INDEX ON ONLY parent (col);                 -- invalid parent stub
CREATE INDEX CONCURRENTLY p1_col ON part1 (col);   -- per partition
ALTER INDEX parent_col ATTACH PARTITION p1_col;     -- parent flips valid once all attach
```

### ATTACH / DETACH without an outage
`ATTACH PARTITION` takes only `SHARE UPDATE EXCLUSIVE` on the parent (since 12) but **full-scans the new table under ACCESS EXCLUSIVE** to validate the bound — pre-add a matching `CHECK` so the scan is skipped, then drop it. A present `DEFAULT` partition is also scanned unless it carries a `CHECK` excluding the new range. `DETACH PARTITION CONCURRENTLY` (14+) uses a reduced lock across two transactions; it **cannot run in a transaction block** and is refused when a `DEFAULT` partition exists — finish an interrupted one with `DETACH PARTITION ... FINALIZE`. Pre-14, `DETACH` needs `ACCESS EXCLUSIVE`. Since 14, UPDATE/DELETE also use execution-time pruning with far less planner overhead.

### Partitionwise join/aggregate: off by default
`enable_partitionwise_join` and `enable_partitionwise_aggregate` are both **`off`**. They help only when both inputs share identical partition bounds on the join/`GROUP BY` keys, and each makes the count of `work_mem`-bounded plan nodes grow linearly with partitions and planning far heavier in CPU/memory. Enable per-session for large matched-partition analytics, never globally on OLTP.

### Count discipline & scale-out
Keep partitions to at most a few thousand, and only when pruning leaves a handful per query: each partition's catalog metadata loads into **every session's** local memory, and unpruned partitions inflate planning time and memory. For read scale, add hot-standby physical replicas (streaming replication) and route reads there; front all backends with an external pool. FK constraints **referencing** a partitioned table work since 12. Cross-node "sharding" via `postgres_fdw` foreign-table partitions is possible, but joins/pruning run largely per foreign-scan and aren't automatically parallel — read the plan before relying on it.

### Sources
- postgresql.org/docs/18/ddl-partitioning.html (methods, pruning, ATTACH/DETACH, key/index limits, best practices)
- postgresql.org/docs/18/runtime-config-query.html (partition_pruning + partitionwise defaults & memory caveats, constraint_exclusion)
- postgresql.org/docs/18/sql-altertable.html (DETACH CONCURRENTLY/FINALIZE locks & restrictions, ATTACH lock levels)
- postgresql.org/docs/release/14.0/ and /release/12.0/ (DETACH CONCURRENTLY + exec-time UPDATE/DELETE pruning in 14; FK-referencing + reduced ATTACH lock + many-partition perf in 12)

## Performance <a id="performance"></a>

Ordered playbook: fix the biggest lever first, measure every change. Current stable 18; verify version gates. Depth lives in the linked deep-dives — this is the checklist, not a restatement.

### 0. Measure first — you can't tune what you can't see
- DO find costly queries before touching anything: `pg_stat_statements` (needs `shared_preload_libraries`), sort by `total_exec_time` — not gut feel. Live stalls: `pg_stat_activity` `wait_event`/`state`. See lore/deep/databases.md#resilience-and-observability.
- DO read the plan with `EXPLAIN (ANALYZE, BUFFERS)` — ANALYZE actually runs it (wrap DML in `BEGIN…ROLLBACK`); BUFFERS is auto-on with ANALYZE in PG18. Estimated-vs-actual rows far apart ⇒ stale stats (`ANALYZE`); high `Buffers: read` ⇒ I/O; `loops=N` ⇒ per-loop averages. Plan-reading depth: lore/deep/databases.md#indexing-and-query-plans.
- DON'T trust plans on tiny/empty tables — the planner rationally scans them.

### 1. Fix query shape (cheapest big wins)
- DO kill N+1: one JOIN/aggregate over the set, never a query per row in app code — a round-trip per row dwarfs any index.
- DO keep predicates sargable (bare column, no `func(col)`; else an expression index) — see lore/deep/databases.md#indexing-and-query-plans.
- DO know CTE folding (PG12+): a non-recursive, side-effect-free `WITH` referenced once inlines; referenced more than once it materializes as a fence — `NOT MATERIALIZED` to push predicates down, `MATERIALIZED` to compute an expensive CTE once.

### 2. Index the right columns, right type
- DO index FK columns (unindexed FKs ⇒ slow joins + heavy locks on parent delete/update), plus filter and `ORDER BY` cols; order equality→range→sort. Types: B-tree default; partial (hot subset); covering `INCLUDE`; GIN (jsonb/FTS/array, `@>`); BRIN (append-only). Full matrix + `CREATE INDEX CONCURRENTLY`: lore/deep/postgres.md#indexing-mvcc-and-vacuum.
- DON'T over-index — each index taxes every write and bloats.

### 3. Pool connections, cap max_connections
- DO front Postgres with PgBouncer transaction mode; keep `max_connections` modest (default 100) — a fork/backend per connection. Active pool ≈ `cores*2 + spindles`. lore/deep/postgres.md#connection-and-pooling, lore/deep/databases.md#connection-pooling.
- DON'T raise `max_connections` into the thousands to dodge pooling.

### 4. Kill bloat & long transactions
- DO tune (never disable) autovacuum and set `idle_in_transaction_session_timeout` — a long/idle txn pins `xmin` and stops vacuum DB-wide, growing bloat. lore/deep/postgres.md#indexing-mvcc-and-vacuum.

### 5. Memory & parallelism
- DO raise `work_mem` when sorts/hashes spill (`Sort Method: external`/temp files in EXPLAIN) — but it is per-node per-session, so total is many × the value; hashes get ×`hash_mem_multiplier` (2.0). Default 4MB.
- DO allow parallelism: `max_parallel_workers_per_gather` (2), `max_parallel_workers` (8) ≤ `max_worker_processes` (8); each worker gets its own `work_mem`. `maintenance_work_mem` (64MB) speeds index builds/vacuum.

### 6. Scale big tables & bulk paths
- DO partition only when pruning leaves few partitions per query (RANGE for time-series + cheap retention). lore/deep/postgres.md#partitioning-and-scale.
- DO bulk-load with `COPY` (far less overhead than many INSERTs); load first, then create indexes/FKs, then `ANALYZE`. Raise `maintenance_work_mem`/`max_wal_size` for the load.
- DO use server-prepared (`$1`) statements to skip re-parse/plan; PG averages 5 custom plans before trying a generic one (`plan_cache_mode auto`). Under txn pooling requires PgBouncer ≥1.21.

### Sources
- postgresql.org/docs/current/{using-explain,runtime-config-resource,populate,sql-prepare,queries-with}.html
- postgresql.org/docs/current/pgstatstatements.html
