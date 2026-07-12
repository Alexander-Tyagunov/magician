# PostgreSQL — Connection & pooling

Engine-side connection semantics plus the libpq parameters every driver inherits (pgx, rust-postgres, npgsql, psycopg, JDBC mirror these keyword/URI options). Current stable **18**; supported **14–18** (13 EOL 2025-11). Client-pool config: lore/jdbc/connections-and-pooling.md; PgBouncer modes and the pool-size formula: lore/databases/connection-pooling.md — this file is the *server + protocol* layer.

## Process model — why you must pool

The postmaster **forks an OS process (backend) per connection**. Each connect pays fork + authentication + optional TLS handshake + catalog/relcache warmup; idle backends still hold memory and get scanned for snapshot/xid work. `max_connections` (default **100**) is **restart-only** and directly sizes shared memory — don't crank it to dodge pooling. `superuser_reserved_connections` (**3**) and `reserved_connections` (**0**, since 16) keep emergency slots so admins can still log in when full; exhaustion returns `FATAL 53300` "sorry, too many clients already". Front Postgres with an external pooler for any web workload.

## libpq connection semantics (driver-generic)

- `host=a,b,c` tries hosts in order; **`connect_timeout` is per-host** (N hosts × timeout = worst case) — always set it.
- `target_session_attrs`: `any`/`read-write` since 10; `read-only`/`primary`/`standby`/`prefer-standby` **since 14** — cheap read/write split and failover with no proxy.
- `load_balance_hosts=random` **since 16** shuffles hosts and DNS addresses; pair with `connect_timeout` to skip dead nodes.
- Set `application_name` — it surfaces in `pg_stat_activity` and logs, making load attributable per service.

## TLS & auth — never ship `prefer`

- `sslmode=prefer` (default) encrypts but does **not** verify and silently downgrades to plaintext. Use **`verify-full`** for real MITM protection. `sslrootcert=system` (16+) loads the OS CA store and *implies* `verify-full`.
- `sslnegotiation=direct` (**17**) starts TLS immediately, saving the negotiation round trip; requires `sslmode>=require`.
- `password_encryption` defaults to **`scram-sha-256` since 14** (md5 deprecated). Harden SCRAM with `channel_binding=require`; pin the server's method via `require_auth=scram-sha-256` (16+).
- GSSAPI encryption is preferred over SSL when available — set `gssencmode=disable` if you rely on `sslmode`.

## Dead-connection detection

Poolers, NAT, and firewalls silently reap idle sockets; the app later hands out a corpse. Defenses: server `tcp_keepalives_idle/interval/count` and `tcp_user_timeout`; **`client_connection_check_interval`** (**14**, Linux/BSD/macOS) lets a backend notice a vanished client mid-query and abort wasted work; client-side libpq `keepalives*`; and a client-pool `maxLifetime` shorter than any idle reaper on the path.

## Session-hygiene timeouts

Set per-role/session, not globally in `postgresql.conf`:
- **`idle_in_transaction_session_timeout`** — the most important one: kills sessions that `BEGIN` then stall, which pin `xmin`, block vacuum, and bloat tables.
- `statement_timeout`, `lock_timeout`; **`transaction_timeout`** (**17**) bounds the whole transaction (prepared txns exempt).
- `idle_session_timeout` (**14**) reaps idle non-tx sessions — use cautiously behind a pooler that validates/reuses sockets. Apply via `ALTER ROLE app SET statement_timeout='30s'` or connect `options='-c statement_timeout=30000'`.

## Pooler interaction (engine side)

Under **transaction pooling** a client hops backends every transaction, so session state does not persist: plain `SET`, session temp tables, `LISTEN/NOTIFY`, session advisory locks, and `WITH HOLD` cursors break. Use `SET LOCAL` inside the tx; put durable knobs on the role. Drivers that default to **server-side prepared statements** (extended protocol) fail under transaction pooling unless the pooler tracks them (PgBouncer ≥1.21) or you disable statement caching. Watch `pg_stat_activity.state` (`active`/`idle`/`idle in transaction`/`idle in transaction (aborted)`); rising `idle in transaction` = a leak. `pg_stat_ssl`/`pg_stat_gssapi` confirm per-backend encryption.

## Sources

- PostgreSQL 18 — Connection settings (max_connections, reserved_connections, tcp/keepalive, client_connection_check_interval): https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL 18 — libpq connect parameters (target_session_attrs, load_balance_hosts, sslmode, sslnegotiation, require_auth): https://www.postgresql.org/docs/current/libpq-connect.html
- PostgreSQL 18 — Client statement/idle timeouts (idle_session_timeout 14, transaction_timeout 17): https://www.postgresql.org/docs/current/runtime-config-client.html
- PostgreSQL — Versioning policy (18 stable; 14–18 supported): https://www.postgresql.org/support/versioning/
- PostgreSQL 18 — Monitoring / pg_stat_activity state values: https://www.postgresql.org/docs/current/monitoring-stats.html
