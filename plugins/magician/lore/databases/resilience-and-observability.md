# Databases — Resilience & observability

*Engine-side reliability and telemetry, driver-agnostic. Pool sizing lives in lore/jdbc/connections-and-pooling.md — this file is the engine's own timeouts, retry semantics, failover, and stats surfaces.*

Versions: PostgreSQL 18 / MySQL 8.4 LTS. OpenTelemetry DB **semconv is Stable** for span attrs (`db.system.name`, `db.query.text`, `db.namespace`, `db.operation.name`) and the metric `db.client.operation.duration`; connection-pool metrics remain Development.

## Bound everything with a timeout — DO
Uncapped statements are the top cause of pile-ups and connection exhaustion. Set them **server-side**, not just as a client socket read timeout:
- Postgres (all default `0`=off, ms; set per-role/session, NOT globally in postgresql.conf): `statement_timeout` (per-statement exec), `lock_timeout` (per lock-wait — must be `< statement_timeout` or it never fires), `idle_in_transaction_session_timeout` (kills sessions holding locks / blocking vacuum), `transaction_timeout` (whole-txn, **added in PG 17**; prepared txns exempt).
- MySQL: `max_execution_time` ms (SELECT only) or the `MAX_EXECUTION_TIME(n)` hint; `innodb_lock_wait_timeout` (default 50s); `wait_timeout`/`interactive_timeout` for idle conns.
- DON'T rely on a client read-timeout alone — it abandons the result but the server keeps executing, burning CPU and holding locks.

## Retry the retryable, only — DO
Classify by SQLSTATE, not message text (codes are stable across releases):
- **Always retry the whole transaction:** `40001` serialization_failure, `40P01` deadlock_detected (MySQL `1213` deadlock, `1205` lock-wait timeout). The loser rolled back cleanly, so replay is safe.
- **Reconnect, then retry:** class `08` connection failures (`08006`/`08001`/`08004`) — the txn never committed.
- **DON'T blind-retry** `40003`/`08007` (completion/resolution unknown) or non-idempotent writes — outcome is ambiguous; verify state or use an idempotency key.
- Use **exponential backoff with full jitter**, bounded (~5 tries). Un-jittered retries resynchronize clients into a thundering herd. Retry at the transaction boundary (re-run `BEGIN…COMMIT`), never a single statement mid-txn.

## Failover & connection storms — DO
- libpq multi-host + `target_session_attrs=read-write` auto-lands on the current primary (skips hot-standbys and `default_transaction_read_only`); pair with a small `connect_timeout` (it applies *per host*, so N×timeout is worst case). `load_balance_hosts=random` spreads reads across replicas.
- Set TCP `keepalives` / `tcp_user_timeout` so a black-holed peer is detected in seconds, not the OS default minutes.
- After an outage, prevent a reconnect stampede: cap pool growth, jitter reconnects, and put a **circuit breaker** in front so a downed DB fast-fails instead of queuing every request onto pool wait-time.
- DON'T route writes to a replica — check writability via `target_session_attrs`; a static host role moves on failover.

## Observe what the engine already records — DO
- **Postgres:** `pg_stat_statements` (needs `shared_preload_libraries` + `compute_query_id=on`) aggregates *normalized* queries by `queryid` with `calls`, `total_exec_time`, `mean_exec_time`, `rows`, buffer hit-ratio, `wal_bytes` — sort by total time to find real cost. `auto_explain` (`session_preload_libraries`, set `log_min_duration`) logs slow-statement plans automatically, but `log_analyze` times **every** node of **every** query (severe overhead) — use `sample_rate`, consider `log_timing=off`. Live state: `pg_stat_activity` (`wait_event`, `state`), `pg_stat_replication`/`_slots` for lag.
- **MySQL:** prefer `performance_schema.events_statements_summary_by_digest` (in-memory, all statements, normalized digest) and `sys`-schema views over the file slow log, which misses fast-but-frequent queries. Slow log: `slow_query_log`, `long_query_time` (default 10s), `log_queries_not_using_indexes`.
- **Trace & correlate:** emit OTel client spans whose duration covers *all retries*; sanitize literals from `db.query.text` (→ `?`) — parameterized text may be captured as-is. Use **SQLCommenter** to append `/*key='val'*/` tags so slow-log and `pg_stat_statements` rows carry the originating service/route/trace-id.
- DON'T ship raw statement text with embedded literals to your APM — PII leak plus cardinality blow-up; lean on the engine's normalization.

## Sources
- https://www.postgresql.org/docs/current/runtime-config-client.html
- https://www.postgresql.org/docs/current/errcodes-appendix.html
- https://www.postgresql.org/docs/current/pgstatstatements.html
- https://www.postgresql.org/docs/current/auto-explain.html
- https://www.postgresql.org/docs/current/libpq-connect.html
- https://dev.mysql.com/doc/refman/8.4/en/slow-query-log.html
- https://opentelemetry.io/docs/specs/semconv/database/database-spans/
- https://opentelemetry.io/docs/specs/semconv/database/database-metrics/
- https://google.github.io/sqlcommenter/
