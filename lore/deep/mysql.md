# MySQL — deep dive

> On-demand companion to `lore/mysql.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Connection and pooling](#connection-and-pooling) · [Engines, types, and charset](#engines-types-and-charset) · [Indexing and EXPLAIN](#indexing-and-explain) · [Transactions and Isolation](#transactions-and-isolation) · [Replication & Scale](#replication-and-scale) · [Performance](#performance)

## Connection and pooling <a id="connection-and-pooling"></a>

Engine-side connection lifecycle and the driver-level gotchas that bite through any client. Verified against MySQL **8.4 LTS** (also 9.x Innovation, with 9.7 the newer LTS); spans **5.7 → 8.4**. This complements — does not restate — the engine/pooler overview in `lore/deep/databases.md#connection-pooling` (ProxySQL/RDS Proxy multiplexing & pinning) and the JVM client-pool tuning in `lore/deep/jdbc.md#connections-and-pooling`.

### The connection model (thread-per-connection)

Default `thread_handling=one-thread-per-connection`: the server dedicates **one OS thread per connection** for auth + request handling, so "there are as many threads as clients connected." Consequences: thread create/destroy cost under churn, and per-thread stack (`thread_stack`) memory. `thread_cache_size` (**autosized** at startup) recycles idle threads — watch `Threads_created` climbing vs a warm `Threads_cached` to size it. A real server-side thread pool exists **only in MySQL Enterprise** (the Thread Pool *plugin*) — Community MySQL has none (Percona adds one). See MariaDB below.

`max_connections` defaults to **151**; the server actually permits **`max_connections + 1`**, the extra reserved for `CONNECTION_ADMIN`/`SUPER` to log in and run `SHOW PROCESSLIST` when full. Overflow → error **1040 `ER_CON_COUNT_ERROR` "Too many connections"** and bumps `Connection_errors_max_connections`. `back_log` (default **-1** = autosize to `max_connections`) is the TCP listen-queue depth that absorbs connection bursts. There is also a dedicated **admin interface** (`admin_address`/`admin_port`, default **33062**) that accepts a connection even when normal slots are exhausted — wire it for ops. Ports: classic protocol **3306**, X Protocol (Document Store) **33060**.

### Timeouts that silently drop connections

The #1 cause of **`CR_SERVER_GONE_ERROR` (2006) "MySQL server has gone away"** and **`CR_SERVER_LOST` (2013)** is idle reaping: the server closes an idle **non-interactive** connection after **`wait_timeout` (default 28800s = 8h)**. Interactive clients instead use `interactive_timeout` — and crucially, a client's `interactive_timeout` **seeds the session's `wait_timeout` at connect**, so pooled app connections (non-interactive) are governed by `wait_timeout`, not `interactive_timeout`. `net_read_timeout`/`net_write_timeout` abort a stalled read/write mid-statement (a slow client consuming a huge result set can trip `net_write_timeout`); `connect_timeout` bounds the handshake. NAT/firewall/proxy idle timers and `KILL` also sever sockets invisibly.

### Pool recycling (driver-generic)

- Set client-pool **`maxLifetime` shorter than server `wait_timeout`** (and shorter than any proxy/firewall idle timer) so the pool retires sockets before the server reaps them — otherwise the next checkout hands you a dead socket → 2006/2013 on first query.
- **Validate on borrow** (lightweight ping / `SELECT 1`) or rely on maxLifetime + test-on-checkout; idle server-side reaping and network middleboxes drop sockets with no notice.
- **Do NOT enable driver auto-reconnect** (`autoReconnect`, the CLI `reconnect` flag). It transparently opens a fresh session that has **lost all session state**: `SET` session vars, `USE db`, user/`@`-variables, temp tables, server-side prepared statements, table locks, `LAST_INSERT_ID()`, and any open transaction. Let the pool replace the connection and let the caller retry.
- Prefer a **small warm bounded pool** over connect-per-request — thread setup + full auth per connect is the cost you are avoiding.

### Auth on connect + TLS

Default plugin since 8.0.4 is **`caching_sha2_password`**. `mysql_native_password` is **deprecated (8.0.34)**, **disabled by default (8.4)**, and **removed (9.0.0)** — old connectors that only speak native password can no longer log in against a default 8.4 server. `caching_sha2_password` never sends cleartext: it needs **either a secure transport (TLS / Unix socket / shared memory) OR RSA key-pair exchange** on the first (uncached) auth; a warm server cache then allows a fast challenge-response with no TLS/RSA. Over plaintext TCP the client must fetch the server's RSA public key — `--get-server-public-key` (JDBC/other drivers: an "allow public key retrieval" flag). Enabling blind public-key retrieval is a **MITM risk**; prefer real TLS. Enforce TLS server-side with `require_secure_transport=ON` and set the client `ssl-mode` to `REQUIRED`/`VERIFY_CA`/`VERIFY_IDENTITY`. Set **`skip_name_resolve=ON`** to skip the reverse-DNS lookup MySQL does per connect (removes connect-time hangs when DNS is slow) — but then account host parts must be IPs/wildcards, not hostnames.

### Packet size + charset on the wire

`max_allowed_packet` defaults to **64MB (server)** / **16MB (`mysql` client)**, max **1GB**, and **must be raised on BOTH ends** for large rows/BLOBs/bulk inserts — an oversized packet yields `ER_NET_PACKET_TOO_LARGE` or a "Lost connection during query". Server default charset is **`utf8mb4`** (collation `utf8mb4_0900_ai_ci`) since 8.0 (5.7 defaulted to `latin1`); ensure the **connection** charset is `utf8mb4`, not the 3-byte `utf8`/`utf8mb3` alias, or 4-byte characters (emoji, some CJK) truncate or error.

### MariaDB divergence

MariaDB ships a **built-in** thread pool (no plugin/license): `thread_handling=pool-of-threads` (default on Windows), `thread_pool_size` default = **number of CPUs**. Auth also differs — MariaDB keeps **`mysql_native_password` as a default-capable plugin** and offers **`ed25519`**; it does **not** implement `caching_sha2_password` or the X Protocol. Treat "MySQL" connector defaults (auth plugin, X port) as non-portable to MariaDB.

### DO / DON'T

- **DO** keep client-pool `maxLifetime` < `wait_timeout` and < any proxy/firewall idle timeout; validate connections on checkout.
- **DO** front high-fan-in workloads with a server-side pooler (see `lore/deep/databases.md#connection-pooling`) rather than raising `max_connections` into the thousands past the throughput knee.
- **DO** use TLS (`require_secure_transport`) or an RSA key file for `caching_sha2_password`; reserve the admin port for ops.
- **DON'T** enable driver auto-reconnect — it silently discards session state mid-flight.
- **DON'T** assume a default 8.4 server accepts `mysql_native_password`, or that the connection is `utf8mb4` — set both explicitly.
- **DON'T** forget to raise `max_allowed_packet` on the client too; server-only changes still fail large packets.

### Sources

- MySQL 8.4 — Connection Interfaces (thread-per-connection, thread_cache_size, admin/X interfaces): https://dev.mysql.com/doc/refman/8.4/en/connection-interfaces.html
- MySQL 8.4 — Too Many Connections (max_connections default 151, +1 admin reserve): https://dev.mysql.com/doc/refman/8.4/en/too-many-connections.html
- MySQL 8.4 — "MySQL server has gone away" (wait_timeout 8h, 2006/2013 causes): https://dev.mysql.com/doc/refman/8.4/en/gone-away.html
- MySQL 8.4 — Packet Too Large (max_allowed_packet 64MB/16MB/1GB): https://dev.mysql.com/doc/refman/8.4/en/packet-too-large.html
- MySQL 8.4 — Native Pluggable Authentication (mysql_native_password deprecated 8.0.34 / disabled 8.4 / removed 9.0): https://dev.mysql.com/doc/refman/8.4/en/native-pluggable-authentication.html
- MySQL 8.4 — Caching SHA-2 Pluggable Authentication (TLS/RSA, cache): https://dev.mysql.com/doc/refman/8.4/en/caching-sha2-pluggable-authentication.html
- MySQL 8.4 — Server System Variables (back_log -1, character_set_server utf8mb4): https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html
- MySQL EOL notice (8.4 LTS; 8.0 sustaining 2026-04-21; 5.7 sustaining 2023-10-25): https://www.mysql.com/support/eol-notice.html
- MariaDB — Thread Pool (built-in, thread_pool_size = #CPUs): https://mariadb.com/kb/en/thread-pool-in-mariadb/

## Engines, types, and charset <a id="engines-types-and-charset"></a>

Engine-level storage, type, and encoding semantics for MySQL 8.0/8.4 LTS (spanning 5.7→8.4). For EXPLAIN, sargability, and composite-index order see lore/deep/databases.md#indexing-and-query-plans — this file is storage/type behavior, not the planner.

### Pick the engine deliberately

- **InnoDB is the default and the only sane OLTP choice.** Only InnoDB (and NDB Cluster) give **transactions, row-level locking, MVCC, crash recovery, and enforced `FOREIGN KEY`s**. MyISAM and MEMORY are table-lock-only, non-transactional, and lose data on crash. MyISAM *parses* FK syntax but silently ignores it — a table full of dangling refs looks fine until you migrate to InnoDB.
- **DON'T** mix engines in one transactional workflow: a write touching a MyISAM table is not rolled back when the surrounding InnoDB tx aborts. Verify with `SHOW TABLE STATUS` / `SHOW ENGINES`.

### Row format governs off-page storage AND index limits

- Default `ROW_FORMAT` is **`DYNAMIC`** (since 5.7.9; set by `innodb_default_row_format`). Legacy `COMPACT`/`REDUNDANT` store a **768-byte prefix of every `VARCHAR`/`BLOB`/`TEXT` inline** in the clustered leaf plus a 20-byte pointer — bloating B-tree nodes and cutting rows/page. `DYNAMIC` pushes long columns fully off-page (20-byte pointer only).
- The max **index key prefix is 3072 bytes on DYNAMIC/COMPRESSED but only 767 on COMPACT/REDUNDANT** (`innodb_large_prefix` was removed in 8.0 — the large limit is now unconditional). This applies to full-column keys too, and scales *down* with a smaller `innodb_page_size`.
- **GOTCHA:** a rebuild (`OPTIMIZE TABLE`, copy `ALTER`) on a table with no explicit `ROW_FORMAT` silently adopts the current default — pin it explicitly if it matters.

### Numeric & date/time traps

- `DECIMAL(M,D)` is exact — use it for money. `FLOAT`/`DOUBLE` are approximate; never `=`-compare them. `FLOAT(M,D)` fixed-precision syntax is **deprecated (8.0.17)**.
- Integer **display width (`INT(11)`) and `ZEROFILL` are deprecated (8.0.17)** and never affected stored range — drop them; size by value (`UNSIGNED` doubles the positive range). `BIGINT UNSIGNED` in arithmetic can overflow/wrap silently.
- `TIMESTAMP` is 4 bytes, range **`1970-01-01 00:00:01`→`2038-01-19 03:14:07` UTC** (the 2038 cliff) — it is stored as UTC and converted to the session `time_zone` both ways, so the same row reads back differently under a different session tz. `DATETIME` (range to 9999) does **no** conversion. Rule: store UTC; use `DATETIME` for far-future/tz-agnostic values, `TIMESTAMP` only when you want session-tz conversion.
- Both support `DEFAULT CURRENT_TIMESTAMP` / `ON UPDATE CURRENT_TIMESTAMP`. `explicit_defaults_for_timestamp` is **ON by default since 8.0**, removing the legacy implicit `NOT NULL`/auto-init on the first `TIMESTAMP` column — declare defaults yourself. `fsp` (fractional seconds) defaults to **0**, not the SQL-standard 6.

### String types & JSON

- `CHAR` is right-padded and trailing spaces are stripped on read; `VARCHAR` carries a 1–2 byte length prefix. The **row size limit is 65,535 bytes across all columns** (charset-inflated: `utf8mb4` counts 4 bytes/char) — `BLOB`/`TEXT` only count ~9–12 bytes toward it, so wide tables force those types.
- `ENUM`/`SET` store a compact integer/bitmask, but `ENUM` **sorts by internal index, not by label** — an easy silent bug. `''`/index 0 is the error value.
- `JSON` is a **native binary type (5.7.8+)**, validated on insert; 8.0 does partial in-place updates (`JSON_SET`) with optimized binlog. It can't be indexed directly or have a literal default — index a `GENERATED` column, or use a **multi-valued index (8.0.17)** for `JSON` arrays.

### Charset & collation: utf8mb4 or nothing

- Server default is **`utf8mb4` / `utf8mb4_0900_ai_ci` since 8.0** (was `latin1`/`latin1_swedish_ci` in 5.7). **`utf8` is a deprecated alias for `utf8mb3`** (BMP-only, 3 bytes) — it cannot store emoji/supplementary chars. Always use `utf8mb4`.
- `_0900` collations are UCA-9.0.0-based, **faster**, and **`NO PAD`** — trailing spaces are significant, unlike older `PAD SPACE` collations (`'a' <> 'a '`), a real behavior change on upgrade. `_ai_ci` = accent/case-insensitive; `_as_cs` = accent+case-sensitive; `_bin` = codepoint.
- **Set the connection charset in the driver/DSN** (or `SET NAMES utf8mb4`, which sets `character_set_client`/`_connection`/`_results`). A latin1 connection writing to utf8mb4 columns produces double-encoded mojibake. Comparing/joining columns of **different charset or collation** triggers "illegal mix of collations" or a forced conversion that **disables the index** — keep joined keys identical.

### MariaDB divergence

- MariaDB is **not** charset-compatible with MySQL 8: `utf8` still aliases `utf8mb3` (flip via `old_mode`), historic default collation is `utf8mb4_general_ci`, `uca1400` collations arrived in 10.10, and MySQL's `_0900` collations only in 11.4.5.
- MariaDB **`JSON` is an alias for `LONGTEXT COLLATE utf8mb4_bin`** with an auto-added `JSON_VALID()` CHECK — not a binary type; this **breaks row-based replication of JSON from MySQL → MariaDB**. MariaDB also lacks NDB and adds the Aria engine and native `SEQUENCE`s.

### Sources

- MySQL 8.4 — Storage Engines: https://dev.mysql.com/doc/refman/8.4/en/storage-engines.html
- MySQL 8.4 — InnoDB Row Formats & Limits: https://dev.mysql.com/doc/refman/8.4/en/innodb-row-format.html , https://dev.mysql.com/doc/refman/8.4/en/innodb-limits.html
- MySQL 8.4 — Data Types, DATETIME/TIMESTAMP: https://dev.mysql.com/doc/refman/8.4/en/data-types.html , https://dev.mysql.com/doc/refman/8.4/en/datetime.html
- MySQL 8.4 — Character Sets & Unicode collations: https://dev.mysql.com/doc/refman/8.4/en/charset.html , https://dev.mysql.com/doc/refman/8.4/en/charset-unicode-sets.html
- MariaDB — Unicode & JSON: https://mariadb.com/kb/en/unicode/ , https://mariadb.com/kb/en/json-data-type/

## Indexing and EXPLAIN <a id="indexing-and-explain"></a>

Version: 8.4 LTS / 9.x. Gates: invisible (8.0.0), descending (8.0.1), histograms (8.0.3), functional key parts + skip scan (8.0.13), multi-valued JSON (8.0.17), `EXPLAIN ANALYZE` + hash join (8.0.18). Never on 5.7. InnoDB=BTREE (+FULLTEXT/SPATIAL).

### Clustered structure
InnoDB clusters rows on the PK (else first UNIQUE NOT NULL, else hidden rowid). Secondary leaves store key **+ PK**, so a wide PK bloats every index and non-covering lookups pay a 2nd descent (bookmark lookup). Keep PK small/monotonic.

### Composite: leftmost prefix + skip scan
`(a,b,c)` serves `a`, `a,b`, `a,b,c` + a **range on the last used part only**; anything right of a range/`IN` is dead for equality. Order equality-first, range-last; `ORDER BY` after them (free sort). A **covering** index (all SELECT+WHERE cols) needs no row read. No predicate on `a` normally kills it; **skip scan** (`Using index for skip scan`) may rescue: cost-based, favored when `a` has **few distinct values** (preference, not a gate); needs single-table, index-only (no `GROUP BY`/`DISTINCT`), equality on leading parts.

### Reading EXPLAIN
`type` best→worst: `system`>`const`>`eq_ref`>`ref`>`range`>`index`>`ALL` (last two = full scans). `key_len` = composite parts used; short = a trailing part unused. `rows × filtered/100` = rows to next table; low `filtered` on `ALL`/`index` is the flag. `Extra`: `Using index`=covering; `index condition`=ICP; `filesort`/`temporary`=no index for `GROUP BY`/`ORDER BY`; `index_merge`=single-col indexes combined (add a composite). `EXPLAIN ANALYZE` (8.0.18, `FORMAT=TREE`): actual vs estimated rows, big gap = stale stats/bad selectivity; the only view of hash joins.

### Special index types
- **Descending** `(a ASC, b DESC)`: real reverse storage → mixed-direction `ORDER BY`, no filesort.
- **Invisible** — `ALTER TABLE t ALTER INDEX x INVISIBLE`: maintained but planner-ignored; toggle via `optimizer_switch='use_invisible_indexes=on'`. PKs can't be invisible.
- **Functional** `((col1+col2))`: hidden virtual generated column; expression must match **exactly**, no prefixes, not in FKs.
- **Multi-valued** JSON arrays: `CAST(js->'$.tags' AS UNSIGNED ARRAY)` via `MEMBER OF`/`JSON_CONTAINS`/`JSON_OVERLAPS`; never covering, no range scan, `ALGORITHM=COPY`.
- **Prefix** `col(20)`: can't cover or fully serve `ORDER BY`.

### Statistics
`ANALYZE TABLE` refreshes index cardinality (sampled) under a **read lock**. **Histograms** (`ANALYZE TABLE t UPDATE HISTOGRAM ON col`) give selectivity for **un-indexed** cols to sharpen `filtered`/join order; no new access path.

### DON'T
- Coercion: a string col vs number (`WHERE vc = 1`) casts the *column* per row → full scan. Non-sargable: leading-wildcard `LIKE '%x'`, a bare function on a column (use a functional index).
- Don't join on mismatched charset/collation — conversion disables the index on the join side.
- Don't index low-cardinality leading cols or over-index write-heavy tables — each index is a B-tree to maintain, bloating the clustered pointer.
- Don't trust `rows` (InnoDB estimate) or leave stats stale after bulk loads — re-`ANALYZE`.
- **MariaDB**: no `EXPLAIN ANALYZE` (use `ANALYZE SELECT`, `r_rows`/`r_filtered`); no functional/multi-valued JSON (generated cols); histograms + ignored-index syntax differ.

### Sources
- refman/8.4/en/: explain-output.html, explain.html, create-index.html, {index-condition-pushdown,index-merge,range,hash-joins,analyze-table}-optimization.html

## Transactions and Isolation <a id="transactions-and-isolation"></a>

Version: 9.7 newest LTS (2026-04), 8.4 LTS supported, 8.0 EOL 2026-04; InnoDB isolation/locking unchanged 8.0→8.4→9.7. InnoDB only — MyISAM: no transactions, no rollback. Default REPEATABLE READ (not READ COMMITTED). `FOR SHARE`/`SKIP LOCKED`/`NOWAIT`/`OF` added 8.0.1. `autocommit=1` default. Can't change level mid-tx.

### Four levels (InnoDB)
- REPEATABLE READ (default): plain `SELECT` = snapshot from tx's first read. Locking reads + `UPDATE`/`DELETE` take next-key locks (record+gap) over the scan range → phantoms blocked; unique hit on one existing row = record lock only, no gap.
- READ COMMITTED: re-snapshots per statement. Gap locking off (except FK/dup-key) → phantoms possible; `UPDATE` uses semi-consistent read. Needs row binlog: `MIXED` auto-switches to ROW, but `STATEMENT` is NOT coerced — transactional DML errors out. Same for READ UNCOMMITTED.
- READ UNCOMMITTED: nonlocking — dirty reads.
- SERIALIZABLE: RR + `autocommit=0` promotes plain `SELECT` to `FOR SHARE`.

### MVCC & snapshots
Reads rebuild old rows from the undo log. Snapshot governs `SELECT` only — an `UPDATE`/`DELETE` in the same tx hits latest committed data, touching rows a prior SELECT couldn't see. A long/forgotten tx pins an old read view → purge can't reclaim undo → history-list bloat, slow reads; keep tx short. `START TRANSACTION WITH CONSISTENT SNAPSHOT` snapshots up front. Copy-rebuilding `ALTER`/`DROP` invalidates it → `ER_TABLE_DEF_CHANGED`, retry.

### Locks
On index records (no-PK table → hidden clustered index). Next-key = record + gap lock on the gap before it. Gap locks only block inserts (purely inhibitive). `INSERT` sets an insert-intention gap lock: inserts to different spots of a gap don't block, but wait on a covering next-key lock. Duplicate-key `INSERT` = shared lock on the row → concurrent same-key inserts deadlock. `INSERT … ON DUPLICATE KEY UPDATE`/`REPLACE` = exclusive next-key locks. FK checks = shared record locks on parent. A locking read/UPDATE without a usable index locks every scanned row (≈ whole table) — always index the `WHERE`.

### Deadlock vs lock-wait (rollback scope differs)
- Deadlock (1213, SQLSTATE 40001): `innodb_deadlock_detect` ON; rolls back cheapest victim + whole tx — retry it. RR gap locks make range-write/INSERT deadlocks likelier than RC.
- Lock-wait timeout (1205): `innodb_lock_wait_timeout` 50s; rolls back ONLY the failing statement, not the tx (keeps other locks). Set `innodb_rollback_on_timeout` (OFF) for full-tx rollback — else code assuming 1205 == full rollback breaks.
- Diagnose: `SHOW ENGINE INNODB STATUS`, `performance_schema.data_locks`/`data_lock_waits`, `INNODB_TRX`.

### DDL, MDL, XA
DDL and `LOCK TABLES` force an implicit COMMIT (not transactional, no rollback). Every statement (even `SELECT`) takes an MDL to tx end: one open tx blocks an `ALTER`, whose exclusive wait blocks all queries (metadata-lock pileup). `lock_wait_timeout` (MDL) default 31536000s/1yr — set low (5s) before DDL so it fails fast. `XA PREPARE`d tx hold locks across restart until commit/rollback — orphans block DDL indefinitely.

### MariaDB
Separate engine: same four levels + default RR, but `NOWAIT`/`SKIP LOCKED` versions, `FOR SHARE` spelling, replication internals differ — verify vs MariaDB KB.

### Sources
- dev.mysql.com/doc/refman/8.4/en/: innodb-transaction-isolation-levels.html, innodb-locking.html, metadata-locking.html, binary-log-setting.html

## Replication & Scale <a id="replication-and-scale"></a>

8.4 LTS (5.7→8.4). Async by default; sync only via Group Replication or NDB Cluster. **8.4 removed legacy `master`/`slave` SQL** → syntax error; use `CHANGE REPLICATION SOURCE TO`, `START REPLICA`, `RESET BINARY LOGS AND GTIDS`, `SHOW BINARY LOG STATUS`, `SHOW REPLICA STATUS`.

### Format & GTID
`binlog_format=ROW` (default 5.7.7; deprecated 8.0.34). GTID needs ROW; SBR non-deterministic (`NOW()`, `UUID()`, unkeyed multi-row). Enable: `gtid_mode=ON` (set `enforce_gtid_consistency=ON` first) + `log_bin`. `SOURCE_AUTO_POSITION=1` negotiates missing txns — failover needs no file/pos. `enforce_gtid_consistency=ON` hard-rejects one statement/txn updating both transactional and non-transactional engines; `CREATE TABLE ... SELECT` OK on atomic-DDL engines (one txn); `CREATE/DROP TEMPORARY TABLE` in a txn OK under ROW/MIXED (not replicated), rejected under STATEMENT.

### Semisync
Plugin, both ends (`rpl_semi_sync_source`/`_replica`). Source blocks at commit until `rpl_semi_sync_source_wait_for_replica_count` replicas (default 1) ack — ack = in replica **relay log**, not applied. `..._wait_point=AFTER_SYNC` (default) waits *before* commit (lossless); `AFTER_COMMIT` after. On `..._timeout` (default 10000 ms), no acks → async — **not** hard durability. Failed-over source may hold un-acked txns — **discard, don't re-add**.

### Threads, applier, crash safety
Multithreaded: `replica_parallel_workers > 0` (0 = single thread) + `replica_preserve_commit_order=ON` for commit order. Don't set `replica_parallel_type` — whole variable deprecated (8.0.29); default `LOGICAL_CLOCK` since 8.0.27, so use the default. **8.4 removed `binlog_transaction_dependency_tracking`** — source *always* emits writeset deps (row-based), no knob. Crash-safe replica = `relay_log_recovery=ON` + `sync_binlog=1` + `innodb_flush_log_at_trx_commit=1`. `relay_log_info_repository`/`master_info_repository` deprecated 8.0, **removed 8.4** — metadata in crash-safe InnoDB tables.

### Read scale & routing
Reads → replicas, writes → source; **no native sharding**. Guard replicas: `super_read_only=ON` (blocks even `CONNECTION_ADMIN`/`SUPER`). Don't trust `Seconds_Behind_Source` (0 when idle, jumps on long txn); measure lag from `performance_schema.replication_applier_status_by_worker`. `log_replica_updates` (default ON) needed for chained topologies + a replica's own binlog.

### Group Replication / InnoDB Cluster
Virtually-synchronous Paxos groups; **single-primary default since 8.0**. Every table InnoDB+PK; GTIDs+ROW on; conflicts resolve by certification. `group_replication_consistency` (`EVENTUAL`→`BEFORE`/`AFTER`/`BEFORE_AND_AFTER`) default → `BEFORE_ON_PRIMARY_FAILOVER` (8.4). Wrap as **InnoDB Cluster** (Shell AdminAPI) + **MySQL Router** for R/W split, failover. HA, not write scale-out.

### MariaDB divergence
MariaDB GTIDs `domain-server-sequence` (`gtid_domain_id`), **not** MySQL's `uuid:seqno` — incompatible (replicates *from* MySQL, not reverse). Keeps `CHANGE MASTER TO ... MASTER_USE_GTID={slave_pos|current_pos|no}` and master/slave terms; parallel apply `slave_parallel_threads` + `slave_parallel_mode`; multi-master sync = Galera (`wsrep`), not Group Replication.

### Sources
- refman/8.4/en/ — gtids-restrictions, semisync, group-replication, options-replica, nutshell (8.4 removals)
- relnotes/8.0 news-8-0-29 (replica_parallel_type deprecated), 8-0-27 (LOGICAL_CLOCK default)
- mariadb.com/.../standard-replication/gtid

## Performance <a id="performance"></a>

Prioritized playbook — do these in order. InnoDB assumed. Gates: `EXPLAIN FORMAT=TREE` 8.0.16, `EXPLAIN ANALYZE` 8.0.18. LTS 8.4 / 9.7. Measure before you tune.

### 0. Measure first — you can't tune what you can't see
- **DO** find cost by aggregate: `performance_schema.events_statements_summary_by_digest` (normalized, in-memory) + its `sys` views. The file **slow log** (`slow_query_log=ON`, `long_query_time` default 10s, `log_queries_not_using_indexes`) misses high-QPS cheap queries. See lore/deep/databases.md#resilience-and-observability.
- **DO** read the plan first: `EXPLAIN ANALYZE` (runs it — actual vs estimated rows; big gap = stale stats → `ANALYZE TABLE`). `type`/`Extra`/`key_len` decoding → lore/deep/mysql.md#indexing-and-explain.
- **DON'T** benchmark on tiny tables — the optimizer rationally scans them.

### 1. Size the buffer pool (single biggest knob)
- **DO** fit the working set in `innodb_buffer_pool_size` — default is only **128M**. On a MySQL-only host, start `--innodb-dedicated-server` (default OFF): auto-sets pool to **~0.75×RAM** (>4GB; 0.5× for 1–4GB) plus redo capacity.
- **DO** watch `Innodb_buffer_pool_reads` (disk) vs `..._read_requests` (logical) — a rising miss ratio = pool too small.
- **DON'T** exceed RAM — swapping the pool is catastrophic.

### 2. Index for the query; keep predicates sargable
- **DO** build composites equality-first, range-last, `ORDER BY` last (leftmost-prefix); make hot queries **covering** (`Extra: Using index`) to skip the clustered bookmark lookup. Keep the PK small/monotonic (copied into every secondary index).
- **DON'T** compare an indexed column to a mismatched type (`WHERE varchar_col = 1`) or join across mismatched charset/collation — implicit coercion casts the *column* and disables the index → full scan. No bare function on an indexed column (use a functional index). Prune low-selectivity + unused indexes (`sys.schema_unused_indexes`).

### 3. Pool connections
Thread-per-connection: a warm bounded pool beats connect-per-request; keep `maxLifetime` < `wait_timeout`; front high fan-in with a pooler. See lore/deep/mysql.md#connection-and-pooling + lore/deep/databases.md#connection-pooling.

### 4. Write in bulk, not row-by-row
- **DO** batch many rows per `INSERT`, or `LOAD DATA` for imports; wrap in one transaction (`SET autocommit=0`…`COMMIT`) — autocommit flushes redo per row. Insert in PK order.
- **DO** for big trusted loads: `SET unique_checks=0`, `foreign_key_checks=0`. Disable redo (`ALTER INSTANCE DISABLE INNODB REDO_LOG`) **only** on a fresh, disposable instance. (`innodb_autoinc_lock_mode` is a startup-only option, already `2`/interleaved by default.)

### 5. Scale out — only after 0–4
- **Partitioning** buys **pruning** (skips partitions per the `WHERE` — confirm in `EXPLAIN`'s `partitions` column) + instant drop-partition purge; not a substitute for indexing. Rules: every unique/PK contains the partition key; no FKs; InnoDB/NDB only.
- **Read replicas**: reads → replicas, writes → source (no native sharding); guard with `super_read_only`; measure lag via `performance_schema.replication_applier_status_by_worker`, not `Seconds_Behind_Source`. See lore/deep/mysql.md#replication-and-scale.
- **DO** bound runaway reads with `max_execution_time` (or the `MAX_EXECUTION_TIME(n)` hint).

### Sources
- refman/8.4/en: explain.html, innodb-buffer-pool-resize.html, innodb-dedicated-server.html, optimizing-innodb-bulk-data-loading.html, alter-instance.html, optimizer-hints.html, partitioning-pruning.html, statement-summary-tables.html, slow-query-log.html
