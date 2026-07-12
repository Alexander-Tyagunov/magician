# Databases — Connection pooling

Engine-side connection management: the server's per-connection cost model, and the external/server-side poolers that front it. This is orthogonal to *client*-side pools (HikariCP etc. — see lore/jdbc/connections-and-pooling.md) and to ORM config. Verified against PostgreSQL 18, MySQL 8.4, PgBouncer 1.25.x, ProxySQL, and AWS RDS Proxy docs (see Sources).

## Why the engine forces you to pool

A DB connection is **not** cheap on the server, and the cost model differs by engine:

- **PostgreSQL forks an OS process per connection** (backend). `max_connections` defaults to **100** (`initdb` may lower it to fit kernel limits), is settable **only at server start**, and directly sizes shared memory — raising it wastes RAM even when idle. `superuser_reserved_connections` (default **3**) and `reserved_connections` (default **0**) carve slots out of that total. Idle connections still cost memory and add contention (spinlocks, snapshot/xid scans). Postgres itself ships **no built-in pooler** → you *need* an external one.
- **MySQL/MariaDB spawn a thread per connection** (`thread_handling=one-thread-per-connection`). `max_connections` defaults to **151**; the server actually permits `max_connections + 1`, the extra reserved for `CONNECTION_ADMIN`/`SUPER` to log in and diagnose. Exceeding it → `ER_CON_COUNT_ERROR` "Too many connections". `thread_cache_size` (autosized) recycles idle threads to dodge create/destroy cost. A true **thread pool** exists only in MySQL **Enterprise** (plugin), Percona, and MariaDB — Community MySQL has none.

The throughput knee is real: past `~((core_count*2) + effective_spindle_count)` active connections, added connections *reduce* throughput via disk/lock/cache-line contention and context switches. Count physical cores (exclude hyperthread siblings); `effective_spindle_count` ≈ 0 when the working set is cached. Keep the *active* pool small; set `max_connections` a little above pool size so maintenance/monitoring sessions still fit.

## Two-tier reality

App → client pool → (optional) server-side pooler → engine. The server-side pooler exists to let **thousands** of app/client connections share a **small** number of physical backends. If you run both, size the client pool's max ≤ what the server pooler admits, or the pooler just queues/sheds.

## PgBouncer pooling modes (and what breaks)

`pool_mode` (default **session**); `default_pool_size` **20**; `max_client_conn` **100**; `max_db_connections` **0** (unlimited).

- **session** — server returned to pool only when the *client* disconnects. Safe for all session state; `server_reset_query` = `DISCARD ALL` cleans it between clients. Poor connection amplification.
- **transaction** — server returned when the *transaction* ends. The high-density mode. But each transaction may land on a different backend, so **session state doesn't persist**: plain `SET`/`SET SESSION`, `LISTEN`/`NOTIFY`, session-level advisory locks, `WITH HOLD` cursors, session temp tables, and `DISCARD` all misbehave. Use `SET LOCAL` inside a tx instead. `server_reset_query` is *not* run in this mode.
- **statement** — returned after each statement; multi-statement transactions are **disallowed** entirely.

**Prepared statements:** protocol-level named prepared statements work in transaction/statement mode since PgBouncer **1.21.0** (2023-10) via `max_prepared_statements` (default **200**) — PgBouncer tracks and re-prepares them on whichever backend the query lands. SQL-level `PREPARE`/`EXECUTE`/`DEALLOCATE` are forwarded raw and are **not** tracked, so avoid them under transaction pooling. Managed Postgres poolers (Supabase Supavisor, others) expose the same session/transaction split.

## MySQL: ProxySQL / RDS Proxy multiplexing

ProxySQL and RDS Proxy achieve the same density via **multiplexing** (many frontends reuse one backend). Multiplexing auto-disables — for that backend, often permanently — when a session takes state the next query would inherit: an open transaction (until commit/rollback), `LOCK TABLES`/`FLUSH TABLES WITH READ LOCK` (until `UNLOCK`), `GET_LOCK()` (never re-enabled), any query with `@` user/session vars, certain `SET`s (`SQL_SAFE_UPDATES`, `FOREIGN_KEY_CHECKS`, `UNIQUE_CHECKS`…), `SQL_CALC_FOUND_ROWS`, `CREATE TEMPORARY TABLE`, text-protocol `PREPARE`, and `SQL_LOG_BIN=0`. RDS Proxy calls this **pinning**; a statement text > **16 KB** also pins, and it doesn't support session-pinning filters for PostgreSQL. Minimize pinning by keeping sessions stateless (prefer `SET LOCAL`, avoid temp tables/user vars on the hot path).

## DO / DON'T

- **DO** put a server-side pooler in front of Postgres for any web workload; Postgres has none built in.
- **DO** use transaction pooling for density, but audit every session-scoped feature your app/driver relies on first.
- **DO** set the pooler's `max_db_connections` (or RDS Proxy `MaxConnectionsPercent`) to protect `max_connections`, and set client-pool `maxLifetime` shorter than the pooler/DB idle timeout so nobody hands you a dead socket.
- **DON'T** raise Postgres `max_connections` into the thousands as a substitute for pooling — it inflates shared memory and pushes you past the throughput knee.
- **DON'T** rely on `SET`/temp tables/`LISTEN`/advisory locks under transaction pooling or multiplexing — they leak across or vanish between transactions.
- **DON'T** stack a large client pool behind a small server pooler; the effective ceiling is the *smaller* of the two.
- **DON'T** disable `maxLifetime`/connection recycling — poolers and firewalls silently reap idle backends.

## Sources

- PostgreSQL 18 — Connections & Authentication (max_connections, reserved_connections): https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL Wiki — Number Of Database Connections (process model, pool-size formula): https://wiki.postgresql.org/wiki/Number_Of_Database_Connections
- MySQL 8.4 — Connection Interfaces / thread handling & thread_cache_size: https://dev.mysql.com/doc/refman/8.4/en/connection-interfaces.html
- MySQL 8.4 — Too many connections (max_connections default 151, +1 reserved): https://dev.mysql.com/doc/refman/8.4/en/too-many-connections.html
- PgBouncer — config & pooling modes / max_prepared_statements: https://www.pgbouncer.org/config.html
- PgBouncer — changelog (1.25.2; 1.21.0 prepared statements): https://github.com/pgbouncer/pgbouncer/blob/master/NEWS.md
- ProxySQL — Multiplexing (disable conditions): https://proxysql.com/documentation/multiplexing/
- AWS RDS Proxy — overview & pinning/limitations: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html
