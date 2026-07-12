# MySQL — Connection and pooling

Engine-side connection lifecycle and the driver-level gotchas that bite through any client. Verified against MySQL **8.4 LTS** (also 9.x Innovation, with 9.7 the newer LTS); spans **5.7 → 8.4**. This complements — does not restate — the engine/pooler overview in `lore/databases/connection-pooling.md` (ProxySQL/RDS Proxy multiplexing & pinning) and the JVM client-pool tuning in `lore/jdbc/connections-and-pooling.md`.

## The connection model (thread-per-connection)

Default `thread_handling=one-thread-per-connection`: the server dedicates **one OS thread per connection** for auth + request handling, so "there are as many threads as clients connected." Consequences: thread create/destroy cost under churn, and per-thread stack (`thread_stack`) memory. `thread_cache_size` (**autosized** at startup) recycles idle threads — watch `Threads_created` climbing vs a warm `Threads_cached` to size it. A real server-side thread pool exists **only in MySQL Enterprise** (the Thread Pool *plugin*) — Community MySQL has none (Percona adds one). See MariaDB below.

`max_connections` defaults to **151**; the server actually permits **`max_connections + 1`**, the extra reserved for `CONNECTION_ADMIN`/`SUPER` to log in and run `SHOW PROCESSLIST` when full. Overflow → error **1040 `ER_CON_COUNT_ERROR` "Too many connections"** and bumps `Connection_errors_max_connections`. `back_log` (default **-1** = autosize to `max_connections`) is the TCP listen-queue depth that absorbs connection bursts. There is also a dedicated **admin interface** (`admin_address`/`admin_port`, default **33062**) that accepts a connection even when normal slots are exhausted — wire it for ops. Ports: classic protocol **3306**, X Protocol (Document Store) **33060**.

## Timeouts that silently drop connections

The #1 cause of **`CR_SERVER_GONE_ERROR` (2006) "MySQL server has gone away"** and **`CR_SERVER_LOST` (2013)** is idle reaping: the server closes an idle **non-interactive** connection after **`wait_timeout` (default 28800s = 8h)**. Interactive clients instead use `interactive_timeout` — and crucially, a client's `interactive_timeout` **seeds the session's `wait_timeout` at connect**, so pooled app connections (non-interactive) are governed by `wait_timeout`, not `interactive_timeout`. `net_read_timeout`/`net_write_timeout` abort a stalled read/write mid-statement (a slow client consuming a huge result set can trip `net_write_timeout`); `connect_timeout` bounds the handshake. NAT/firewall/proxy idle timers and `KILL` also sever sockets invisibly.

## Pool recycling (driver-generic)

- Set client-pool **`maxLifetime` shorter than server `wait_timeout`** (and shorter than any proxy/firewall idle timer) so the pool retires sockets before the server reaps them — otherwise the next checkout hands you a dead socket → 2006/2013 on first query.
- **Validate on borrow** (lightweight ping / `SELECT 1`) or rely on maxLifetime + test-on-checkout; idle server-side reaping and network middleboxes drop sockets with no notice.
- **Do NOT enable driver auto-reconnect** (`autoReconnect`, the CLI `reconnect` flag). It transparently opens a fresh session that has **lost all session state**: `SET` session vars, `USE db`, user/`@`-variables, temp tables, server-side prepared statements, table locks, `LAST_INSERT_ID()`, and any open transaction. Let the pool replace the connection and let the caller retry.
- Prefer a **small warm bounded pool** over connect-per-request — thread setup + full auth per connect is the cost you are avoiding.

## Auth on connect + TLS

Default plugin since 8.0.4 is **`caching_sha2_password`**. `mysql_native_password` is **deprecated (8.0.34)**, **disabled by default (8.4)**, and **removed (9.0.0)** — old connectors that only speak native password can no longer log in against a default 8.4 server. `caching_sha2_password` never sends cleartext: it needs **either a secure transport (TLS / Unix socket / shared memory) OR RSA key-pair exchange** on the first (uncached) auth; a warm server cache then allows a fast challenge-response with no TLS/RSA. Over plaintext TCP the client must fetch the server's RSA public key — `--get-server-public-key` (JDBC/other drivers: an "allow public key retrieval" flag). Enabling blind public-key retrieval is a **MITM risk**; prefer real TLS. Enforce TLS server-side with `require_secure_transport=ON` and set the client `ssl-mode` to `REQUIRED`/`VERIFY_CA`/`VERIFY_IDENTITY`. Set **`skip_name_resolve=ON`** to skip the reverse-DNS lookup MySQL does per connect (removes connect-time hangs when DNS is slow) — but then account host parts must be IPs/wildcards, not hostnames.

## Packet size + charset on the wire

`max_allowed_packet` defaults to **64MB (server)** / **16MB (`mysql` client)**, max **1GB**, and **must be raised on BOTH ends** for large rows/BLOBs/bulk inserts — an oversized packet yields `ER_NET_PACKET_TOO_LARGE` or a "Lost connection during query". Server default charset is **`utf8mb4`** (collation `utf8mb4_0900_ai_ci`) since 8.0 (5.7 defaulted to `latin1`); ensure the **connection** charset is `utf8mb4`, not the 3-byte `utf8`/`utf8mb3` alias, or 4-byte characters (emoji, some CJK) truncate or error.

## MariaDB divergence

MariaDB ships a **built-in** thread pool (no plugin/license): `thread_handling=pool-of-threads` (default on Windows), `thread_pool_size` default = **number of CPUs**. Auth also differs — MariaDB keeps **`mysql_native_password` as a default-capable plugin** and offers **`ed25519`**; it does **not** implement `caching_sha2_password` or the X Protocol. Treat "MySQL" connector defaults (auth plugin, X port) as non-portable to MariaDB.

## DO / DON'T

- **DO** keep client-pool `maxLifetime` < `wait_timeout` and < any proxy/firewall idle timeout; validate connections on checkout.
- **DO** front high-fan-in workloads with a server-side pooler (see `lore/databases/connection-pooling.md`) rather than raising `max_connections` into the thousands past the throughput knee.
- **DO** use TLS (`require_secure_transport`) or an RSA key file for `caching_sha2_password`; reserve the admin port for ops.
- **DON'T** enable driver auto-reconnect — it silently discards session state mid-flight.
- **DON'T** assume a default 8.4 server accepts `mysql_native_password`, or that the connection is `utf8mb4` — set both explicitly.
- **DON'T** forget to raise `max_allowed_packet` on the client too; server-only changes still fail large packets.

## Sources

- MySQL 8.4 — Connection Interfaces (thread-per-connection, thread_cache_size, admin/X interfaces): https://dev.mysql.com/doc/refman/8.4/en/connection-interfaces.html
- MySQL 8.4 — Too Many Connections (max_connections default 151, +1 admin reserve): https://dev.mysql.com/doc/refman/8.4/en/too-many-connections.html
- MySQL 8.4 — "MySQL server has gone away" (wait_timeout 8h, 2006/2013 causes): https://dev.mysql.com/doc/refman/8.4/en/gone-away.html
- MySQL 8.4 — Packet Too Large (max_allowed_packet 64MB/16MB/1GB): https://dev.mysql.com/doc/refman/8.4/en/packet-too-large.html
- MySQL 8.4 — Native Pluggable Authentication (mysql_native_password deprecated 8.0.34 / disabled 8.4 / removed 9.0): https://dev.mysql.com/doc/refman/8.4/en/native-pluggable-authentication.html
- MySQL 8.4 — Caching SHA-2 Pluggable Authentication (TLS/RSA, cache): https://dev.mysql.com/doc/refman/8.4/en/caching-sha2-pluggable-authentication.html
- MySQL 8.4 — Server System Variables (back_log -1, character_set_server utf8mb4): https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html
- MySQL EOL notice (8.4 LTS; 8.0 sustaining 2026-04-21; 5.7 sustaining 2023-10-25): https://www.mysql.com/support/eol-notice.html
- MariaDB — Thread Pool (built-in, thread_pool_size = #CPUs): https://mariadb.com/kb/en/thread-pool-in-mariadb/
