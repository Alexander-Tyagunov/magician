# jdbc — Performance & batching

Data-layer specifics for high-throughput JDBC. Assume Java/framework lore lives elsewhere.
API: `java.sql.*` (JDBC 4.2+, Java 8 baseline; unchanged shape through Java 21/25).

## Security first (non-negotiable)

- DO use `PreparedStatement` with `?` placeholders for every value — always, batched or not.
- DON'T concatenate user input into SQL. String-built SQL = injection.

```java
// DON'T
stmt.executeQuery("SELECT * FROM users WHERE id = " + userId);
// DO
var ps = con.prepareStatement("SELECT id, email FROM users WHERE id = ?");
ps.setLong(1, userId);
```

- WARNING: MySQL `rewriteBatchedStatements=true` "might allow SQL injection when using plain statements and the provided input is not properly sanitized" (per Connector/J docs). Parameterize + prepared statements neutralize this.

## Batch DML — addBatch / executeBatch

- DO batch bulk INSERT/UPDATE/DELETE. Add commands, then execute as a unit.
- DO disable auto-commit before the batch, commit explicitly after ("always disable auto-commit mode before beginning a batch update").
- DO reuse ONE `PreparedStatement`, varying params per row (parameterized batch).
- DON'T put a `SELECT` (any result-set-producing statement) in a batch → `BatchUpdateException`.
- DON'T let batches grow unbounded — flush every N rows (e.g. 500–1000) to cap memory/packet size.

```java
con.setAutoCommit(false);
try (var ps = con.prepareStatement("INSERT INTO coffees(name, price) VALUES (?, ?)")) {
    int n = 0;
    for (Coffee c : coffees) {
        ps.setString(1, c.name());
        ps.setBigDecimal(2, c.price());
        ps.addBatch();
        if (++n % 1000 == 0) ps.executeBatch();   // periodic flush
    }
    ps.executeBatch();
    con.commit();
} catch (SQLException e) { con.rollback(); throw e; }
finally { con.setAutoCommit(true); }
```

- `executeBatch()` returns `int[]` update counts, in command order. Successful single-row INSERT = `1`.
- On `MySQL rewriteBatchedStatements` with `ON DUPLICATE KEY UPDATE`, driver returns `Statement.SUCCESS_NO_INFO` per element (server collapses counts) — don't assert exact counts.
- On failure `executeBatch` throws `BatchUpdateException` (extends `SQLException`); use `getUpdateCounts()` to see which succeeded.
- For counts that may exceed `Integer.MAX_VALUE`, use `executeLargeBatch()` → `long[]` (JDBC 4.2 / Java 8+).

### Driver rewrite is what makes batching fast

Plain JDBC batching still sends N statements unless the driver rewrites into one multi-row statement. Enable it:

- MySQL Connector/J: `rewriteBatchedStatements=true` (default `false`; since 3.1.13). Rewrites INSERT/REPLACE batches into multi-VALUES. Caveat: `getGeneratedKeys()` only works if the whole batch is INSERT/REPLACE; unspecified stream length on `set*Stream()` can error.
- PostgreSQL pgjdbc: `reWriteBatchedInserts=true` (default `false`). Merges batch inserts into one multi-values INSERT; docs cite "2-3x performance improvement".
- DON'T assume batching helps without these flags on MySQL/Postgres — measure.

## Prepared-statement caching

- MySQL: `cachePrepStmts=true` (default `false`), `prepStmtCacheSize` (default 25 → raise, e.g. 250), `prepStmtCacheSqlLimit` (default 256 → raise, e.g. 2048), `useServerPrepStmts=true` for server-side prepares.
- Postgres: server-side prepare kicks in after `prepareThreshold` executions (default 5) of the same `PreparedStatement`.
- HikariCP README MySQL example (marked "DO NOT COPY VERBATIM"): `cachePrepStmts=true`, `prepStmtCacheSize=250`, `prepStmtCacheSqlLimit=2048`.

## Large reads — fetch size & streaming

`setFetchSize(n)` hints how many rows to pull per round trip. Default fetches everything → OOM on big result sets.

- DO set a fetch size for large scans (statement-level `setFetchSize`, or driver default).
- DON'T scroll large results: keep `ResultSet.TYPE_FORWARD_ONLY` (the default) for streaming.

### PostgreSQL (cursor streaming — strict requirements)

Postgres streams ONLY when ALL hold, else it buffers the whole result:
- `Connection` NOT in autocommit mode (`con.setAutoCommit(false)`) — else "the backend will have closed the cursor before anything can be fetched".
- `Statement` created `TYPE_FORWARD_ONLY` (default).
- fetch size > 0 (per-statement `setFetchSize`, or URL `defaultRowFetchSize`, default `0`=all).
- single statement (no `;`-joined queries).

```java
con.setAutoCommit(false);                 // REQUIRED for pg streaming
try (var ps = con.prepareStatement("SELECT id, email FROM users WHERE active = ?")) {
    ps.setFetchSize(1000);
    ps.setBoolean(1, true);
    try (var rs = ps.executeQuery()) { while (rs.next()) { /* ... */ } }
}
```

### MySQL (Connector/J)

- Cursor fetch: `useCursorFetch=true` + `defaultFetchSize>0` (or `setFetchSize>0`); auto-sets `useServerPrepStmts=true`.
- Row-by-row streaming alternative: `stmt.setFetchSize(Integer.MIN_VALUE)` (Connector/J special value) — reads one row at a time; the connection is unusable for other queries until the `ResultSet` is fully read/closed.

## Query hygiene (driver-agnostic)

- DON'T `SELECT *`. Name the columns you use — smaller payloads, index-only scans possible, resilient to schema changes.
- DO push filtering/paging to SQL (`WHERE`, `LIMIT`/`OFFSET` or keyset), not into Java.
- DO be index-aware: filter/join/sort on indexed columns; a leading wildcard `LIKE '%x'` or a function on a column defeats the index. Verify with `EXPLAIN`.
- DO mark read paths read-only (`con.setReadOnly(true)` or HikariCP pool `readOnly=true`) — some DBs use it for optimization / routing to replicas (HikariCP `readOnly` default `false`).
- DO close `ResultSet`/`Statement`/`Connection` (try-with-resources). Leaked connections starve the pool.

## Connection pool (HikariCP)

- DO reuse pooled connections; NEVER open a raw connection per request.
- `maximumPoolSize` default 10 — size to the DB, not the app (small pools often beat large). See HikariCP sizing wiki.
- `connectionTimeout` default 30000 ms (min 250 ms) — time `getConnection()` blocks before `SQLException`.
- DO keep transactions short; a connection held across slow work blocks the pool.

## Sources

- Oracle JDBC Tutorial — Retrieving/Modifying & Batch Updates: https://docs.oracle.com/javase/tutorial/jdbc/basics/retrieving.html , https://docs.oracle.com/javase/tutorial/jdbc/basics/batch.html
- java.sql module (JDBC API, Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- PostgreSQL JDBC — Query/cursor streaming: https://jdbc.postgresql.org/documentation/query/
- PostgreSQL JDBC — Connection parameters (reWriteBatchedInserts, defaultRowFetchSize, prepareThreshold): https://jdbc.postgresql.org/documentation/use/
- MySQL Connector/J — Performance Extensions (rewriteBatchedStatements, cachePrepStmts, useCursorFetch, defaultFetchSize): https://dev.mysql.com/doc/connector-j/en/connector-j-connp-props-performance-extensions.html
- HikariCP README (pool config, MySQL prep-stmt example, readOnly): https://github.com/brettwooldridge/HikariCP
