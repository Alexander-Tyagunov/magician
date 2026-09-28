# jdbc — deep dive

> On-demand companion to `lore/jdbc.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [SQL safety (injection, PreparedStatement)](#sql-safety) · [Connections & pooling (HikariCP)](#connections-and-pooling) · [Transactions](#transactions) · [Performance & batching](#performance-and-batching)

## SQL safety (injection, PreparedStatement) <a id="sql-safety"></a>

Senior-reviewer checklist. **#1 rule: user input reaches SQL only as a bound parameter, never
as concatenated text.** JDBC lives in the JDK `java.sql` package — no `javax`/`jakarta`
namespace split (that break is Hibernate/JPA, not JDBC). API is stable across Java 8+ (JDBC
4.2, JSR 221); `setObject(int, Object, SQLType)` default methods arrived in JDBC 4.2 / Java 8.

### DO — always parameterize

- **DO** use `PreparedStatement` with `?` placeholders for every value derived from input.
  The DBMS precompiles the SQL, then binds values as data. Oracle's tutorial: *"Prepared
  statements always treat client-supplied data as content of a parameter and never as a part
  of an SQL statement."*
  ```java
  String sql = "SELECT balance FROM accounts WHERE user_name = ?";
  try (PreparedStatement ps = con.prepareStatement(sql)) {
      ps.setString(1, custName);      // input can never become SQL code
      try (ResultSet rs = ps.executeQuery()) { ... }
  }
  ```
- **DO** index parameters from **1**, not 0 (`setInt(1, ...)` = first `?`). Match setter type
  to column type: `setString`, `setInt`, `setLong`, `setBigDecimal`, `setTimestamp`, `setBytes`.
- **DO** bind SQL NULL with `setNull(idx, sqlType)` — you must pass a type code from
  `java.sql.Types` (e.g. `setNull(2, Types.VARCHAR)`). For UDT/REF use the 3-arg overload
  `setNull(idx, sqlType, typeName)`. Never format the string `"NULL"` into SQL.
- **DO** use `setObject(idx, value)` for dynamic/nullable values; prefer the typed overload
  `setObject(idx, value, JDBCType.XXX)` when the driver needs a type hint.
- **DO** close statements/results with try-with-resources; reuse one `PreparedStatement` across
  a loop with `addBatch()`/`executeBatch()` and `clearParameters()` between iterations.
- **DO** route input through stored procs safely with `CallableStatement`
  (`con.prepareCall("{call sp_get(?)}")`) — still bind, never concatenate.

### DON'T — the injection traps

- **DON'T** build SQL by string concatenation / `String.format` / string templates of input.
  This is the SQL-injection root cause. `"... WHERE name = '" + name + "'"` lets `x' OR '1'='1`
  rewrite the query.
  ```java
  // NEVER
  st.executeQuery("SELECT * FROM users WHERE name = '" + name + "'");
  ```
- **DON'T** treat plain `Statement` as interchangeable with `PreparedStatement`. Use
  `Statement` only for fixed SQL with **no** input. Any variable value ⇒ `PreparedStatement`.
- **DON'T** assume escaping or type-casting input makes concatenation safe. It doesn't —
  binding is the only reliable defense.

### Identifiers cannot be bound — allowlist them

`?` binds **values only**. Table names, column names, and sort direction (`ASC`/`DESC`) can
**not** be parameters. OWASP: *"parts of SQL queries that can't use bind variables, such as
table names, column names, or sort order indicators."* Never concatenate raw identifier input.

- **DO** map input to a fixed, code-defined allowlist; reject anything else.
  ```java
  // sort column: allowlist, then it's safe to concatenate the mapped literal
  String col = switch (sortField) {
      case "name"    -> "name";
      case "created" -> "created_at";
      default -> throw new IllegalArgumentException("bad sort field");
  };
  String dir = "desc".equalsIgnoreCase(sortDir) ? "DESC" : "ASC"; // boolean-ize
  String sql = "SELECT * FROM users ORDER BY " + col + " " + dir;
  ```

### IN-lists — generate placeholders, then bind

A single `?` can't hold a list. **DON'T** join values into the SQL. **DO** emit one `?` per
element and bind each:
```java
String ph = String.join(",", Collections.nCopies(ids.size(), "?"));
try (PreparedStatement ps =
         con.prepareStatement("SELECT * FROM t WHERE id IN (" + ph + ")")) {
    for (int i = 0; i < ids.size(); i++) ps.setLong(i + 1, ids.get(i));
}
```
Note: varying list size defeats statement caching. For large/variable sets prefer
`setArray` + `WHERE id = ANY(?)` (Postgres) or a temp-table join.

### LIKE — escape wildcards in the value

Binding stops injection, but `%` and `_` in bound input are still wildcards. To match them
literally, escape in the **value** and declare the `ESCAPE` char in SQL:
```java
String term = raw.replace("!", "!!").replace("%", "!%").replace("_", "!_");
PreparedStatement ps =
    con.prepareStatement("SELECT * FROM t WHERE name LIKE ? ESCAPE '!'");
ps.setString(1, "%" + term + "%");
```

### Named parameters

Core JDBC has **no** named parameters — positional `?` only. Named params
(`:name`) come from higher layers: Spring `NamedParameterJdbcTemplate`, JPA/Hibernate,
MyBatis. Those still bind under the hood; the no-concatenation rule is unchanged. Assume Spring
lore covers `JdbcTemplate`/`NamedParameterJdbcTemplate` specifics.

### Review triggers (reject on sight)

- Any `Statement.execute*` with a `+` on the SQL string.
- Input reaching SQL outside a `setXxx` call.
- Identifier/sort input concatenated without an allowlist.
- IN-list built by joining values instead of placeholders.
- `"NULL"` literal instead of `setNull`.

### Sources

- Oracle JDBC Tutorial — Using Prepared Statements: https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html
- `java.sql.PreparedStatement` API (Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/java/sql/PreparedStatement.html
- `java.sql` module summary (Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- OWASP SQL Injection Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- OWASP Query Parameterization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html

## Connections & pooling (HikariCP) <a id="connections-and-pooling"></a>

Data-layer specifics for obtaining, pooling, and returning JDBC connections. Assume general Java/framework lore lives elsewhere. Verified against Oracle's JDBC tutorial, the HikariCP repo/wiki, and Spring Boot reference (see Sources).

**Version baseline.** HikariCP `com.zaxxer:HikariCP:7.1.0` requires **Java 11+**. Older runtimes use deprecated maintenance artifacts: Java 8 → `HikariCP:4.0.3`, Java 7 → `HikariCP-java7:2.4.13`, Java 6 → `HikariCP-java6:2.3.13`. Spring Boot's default pool **is** HikariCP: with `spring-boot-starter-jdbc` or `spring-boot-starter-data-jpa` you get it automatically ("If HikariCP is available, we always choose it"; fallback order Tomcat → DBCP2 → Oracle UCP). Tune via `spring.datasource.hikari.*`.

### DO

- **Always use a connection pool.** Creating physical connections is costly in time and resources. HikariCP is the de-facto default. Obtain connections from a `DataSource`, never from `DriverManager`, in production.
- **Size the pool small.** Start from the PostgreSQL-project throughput formula:
  `connections = ((core_count * 2) + effective_spindle_count)`
  `core_count` = physical cores (exclude hyperthread siblings). `effective_spindle_count` ≈ 0 when the working set is fully cached, approaching the real spindle count as the cache-hit rate drops. A 4-core, single-disk box → `(4*2)+1 = 9` (round to ~10). HikariCP's `maximumPoolSize` default is 10. Axiom: "a small pool, saturated with threads waiting for connections" beats a large one — big pools have a demonstrable *negative* throughput impact.
- **Set `maxLifetime` a few seconds shorter than any DB/infra connection time limit** (default 1,800,000 ms = 30 min). This retires connections before the DB, proxy, or firewall kills them out from under you.
- **Return connections with try-with-resources.** `Connection#close()` returns it to the pool; it does not physically close it.
  ```java
  String sql = "SELECT id, email FROM users WHERE tenant_id = ?";
  try (Connection con = dataSource.getConnection();
       PreparedStatement ps = con.prepareStatement(sql)) {
      ps.setLong(1, tenantId);
      try (ResultSet rs = ps.executeQuery()) {
          while (rs.next()) { /* ... */ }
      }
  } // con, ps, rs all closed/returned in reverse order
  ```
- **Enable leak detection in non-prod / when hunting bugs.** `leakDetectionThreshold` (default 0 = off; min enable 2000 ms). Logs a stack trace when a connection is out longer than the threshold.
- **Rely on JDBC4 validation.** HikariCP validates via `Connection.isValid()` automatically; leave `connectionTestQuery` unset unless the driver is a legacy non-JDBC4 driver. `validationTimeout` default 5000 ms (must be < `connectionTimeout`).
- **Prefer a fixed-size pool for predictable latency.** Leave `minimumIdle` unset so it equals `maximumPoolSize` — HikariCP then runs as a fixed pool, best for responding to demand spikes.
- **Parameterize every query with `PreparedStatement` and `?` placeholders.** Set values with typed setters (1-indexed): `ps.setString(1, name)`, `ps.setLong(2, id)`. Prepared statements are precompiled (faster on reuse) and — critically — "always treat client-supplied data as content of a parameter and never as part of an SQL statement."
- **Manage transactions explicitly when spanning statements:** `con.setAutoCommit(false)`, then `con.commit()` / `con.rollback()`. Keep transactions short.
- **Configure `keepaliveTime`** (default 120000 ms; min 30000; must be < `maxLifetime`) and/or TCP keepalive to avoid the rare "pool drains to zero and never recovers" condition on flaky networks.
- **Sync clocks (NTP).** HikariCP timers assume accurate wall/monotonic time — critical on VMs.

### DON'T

- **DON'T build SQL by concatenating user input.** This is SQL injection — the single vulnerability all such attacks exploit. Never do:
  ```java
  // VULNERABLE — never
  var rs = st.executeQuery("SELECT * FROM users WHERE email = '" + email + "'");
  ```
  Use a bound parameter instead. String-concat is only acceptable for *non-user* static identifiers (e.g., a validated table name from an allow-list — identifiers can't be bound as `?`).
- **DON'T over-provision the pool.** 10,000 front-end users do not need 10,000 (or even 100) connections; benchmarks flatten around ~50. Match the pool to what the DB can process concurrently, not to thread count.
- **DON'T hold a connection across user think-time,** network round-trips to other services, or long CPU work. Acquire late, release fast — check out, query, return. A connection parked waiting on a human starves the pool.
- **DON'T leak connections.** Every `getConnection()` needs a guaranteed `close()`. Without try-with-resources or a `finally` block, an exception path exhausts the pool; new callers then block until `connectionTimeout` (default 30000 ms; min 250) and fail.
- **DON'T set `connectionTestQuery`** on a JDBC4-compliant driver — it disables the faster `isValid()` path. HikariCP logs an error if the driver isn't JDBC4 compliant.
- **DON'T set `maxLifetime` ≥ the DB's idle/connection timeout.** The DB will reap the connection first, surfacing as intermittent "connection closed"/broken-pipe errors mid-query.
- **DON'T cache/share a single `Connection` across threads.** Connections are not thread-safe; hand each unit of work its own from the pool.
- **DON'T disable `maxLifetime` (set to 0) in production** unless the DB genuinely never times out connections — you lose protection against stale/half-dead connections.

### Key HikariCP config (defaults, milliseconds unless noted)

| Property | Default | Notes |
|---|---|---|
| `maximumPoolSize` | 10 | Total max connections. Size small (see formula). |
| `minimumIdle` | = `maximumPoolSize` | Leave unset → fixed-size pool. |
| `connectionTimeout` | 30000 | Max wait for a connection; min 250. |
| `idleTimeout` | 600000 | Only applies below `maximumPoolSize`; 0 = never; min 10000. |
| `maxLifetime` | 1800000 | Set < DB timeout; 0 = infinite; min 30000. |
| `keepaliveTime` | 120000 | 0 = off; must be < `maxLifetime`; min 30000. |
| `validationTimeout` | 5000 | Must be < `connectionTimeout`; min 250. |
| `leakDetectionThreshold` | 0 (off) | Enable ≥ 2000 to log leaks. |
| `connectionTestQuery` | none | Legacy non-JDBC4 drivers only. |
| `dataSourceClassName` / `jdbcUrl` | none | One is required. Spring Boot auto-config uses `jdbcUrl`. |

### Sources

- Oracle JDBC Tutorial — Using Prepared Statements: https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html
- Oracle JDBC Tutorial — Connecting with DataSource / Connection Pooling: https://docs.oracle.com/javase/tutorial/jdbc/basics/sqldatasources.html
- Oracle JDBC Tutorial index: https://docs.oracle.com/javase/tutorial/jdbc/
- `java.sql` module summary (Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- HikariCP (config reference, defaults, requirements): https://github.com/brettwooldridge/HikariCP
- HikariCP — About Pool Sizing (formula): https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing
- Spring Boot Reference — SQL Databases / connection pool selection: https://docs.spring.io/spring-boot/reference/data/sql.html

## Transactions <a id="transactions"></a>

Hand-rolled JDBC transactions. For `@Transactional`/Spring/JPA propagation, defer to framework lore. Java + JDBC lore assumed separate.

Baseline: `java.sql` (JDK). Savepoints + `rollback(Savepoint)` require JDBC 3.0 / Java 1.4+. All methods throw `SQLException`.

---

### DO — the transaction skeleton

```java
Connection con = ds.getConnection();
boolean prevAuto = con.getAutoCommit();
try {
    con.setAutoCommit(false);                 // begin: leave auto-commit
    try (PreparedStatement ps1 = con.prepareStatement(
             "UPDATE accounts SET balance = balance - ? WHERE id = ?");
         PreparedStatement ps2 = con.prepareStatement(
             "UPDATE accounts SET balance = balance + ? WHERE id = ?")) {
        ps1.setBigDecimal(1, amt); ps1.setLong(2, from); ps1.executeUpdate();
        ps2.setBigDecimal(1, amt); ps2.setLong(2, to);   ps2.executeUpdate();
    }
    con.commit();                             // all-or-nothing
} catch (SQLException e) {
    con.rollback();                           // undo the whole unit
    throw e;
} finally {
    con.setAutoCommit(prevAuto);              // restore BEFORE returning to pool
    con.close();                              // pool: returns; DriverManager: closes
}
```

- **DO** `setAutoCommit(false)` to open a multi-statement unit. New connections default to auto-commit `true` — each statement is its own committed transaction.
- **DO** call exactly one of `commit()` / `rollback()` on every path; both release the connection's DB locks. Calling either in auto-commit mode throws `SQLException`.
- **DO** `rollback()` in `catch`. A caught `SQLException` says something failed, not what committed — rollback is the only reliable way to know the state.
- **DO** finalize (`commit`/`rollback`) *before* `close()`. Closing with an open transaction is implementation-defined — never rely on close-to-commit/rollback.
- **DO** restore prior auto-commit / isolation before returning a pooled connection.

### DON'T

- **DON'T** leave auto-commit on for a logical unit → partial writes on failure.
- **DON'T** assume `close()` commits or rolls back. Undefined. Be explicit.

---

### DO — security: never concatenate SQL (always applies)

- **DO** use `PreparedStatement` with `?` placeholders + `setXxx(...)` for every user value. Parameterization defeats SQL injection and lets the driver cache plans.
- **DON'T** build SQL by string concatenation / interpolation of input:

```java
stmt.executeUpdate("UPDATE accounts SET balance="+v+" WHERE id="+id); // NEVER — injection
```

---

### try-with-resources ordering

- **DO** manage the transaction on the **`Connection`**; put `Statement`/`ResultSet` in try-with-resources so they close first (LIFO — reverse of declaration).
- **DON'T** put the `Connection` in the *same* try-with-resources as the statements when you commit after the block — it would close before `commit()`. Commit inside the block, or manage the connection in `finally` (as above).
- Nesting is safe: outer `try (Connection…)` for lifecycle, inner `try (PreparedStatement…)` per unit; commit before the connection closes.

---

### Isolation levels & anomalies

Set on the connection; only valid *between* transactions (mid-transaction change is implementation-defined):

```java
con.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
```

Constants (JDBC standard), weakest→strongest, with anomalies **allowed**:

| `Connection.` constant       | Dirty read | Non-repeatable | Phantom |
|------------------------------|:----------:|:--------------:|:-------:|
| `TRANSACTION_READ_UNCOMMITTED` | yes | yes | yes |
| `TRANSACTION_READ_COMMITTED`   | no  | yes | yes |
| `TRANSACTION_REPEATABLE_READ`  | no  | no  | yes |
| `TRANSACTION_SERIALIZABLE`     | no  | no  | no  |

`TRANSACTION_NONE` = transactions unsupported; valid for `getTransactionIsolation()` but **illegal** to pass to `setTransactionIsolation`.

Dirty read = read another tx's uncommitted change; non-repeatable = re-read row changed by committed tx; phantom = re-run range query, new rows appear.

**Defaults are DB-specific — verify, don't assume:**
- PostgreSQL → `READ COMMITTED`. No true `READ UNCOMMITTED` (maps to READ COMMITTED); its `REPEATABLE READ` snapshot also prevents phantoms.
- MySQL / InnoDB → `REPEATABLE READ` (next-key/gap locks).
- Oracle, SQL Server → typically `READ COMMITTED`. Confirm against the target DB's docs.

- **DO** treat `READ_COMMITTED` as the safe default; raise only for read-consistency needs, and expect serialization failures — retry the whole transaction.
- **DON'T** assume the JDBC constant means identical semantics across engines (see PG/MySQL).
- **DON'T** set a level the driver can't honor: it may silently substitute a *stronger* level or throw. Check `DatabaseMetaData.supportsTransactionIsolationLevel(level)`.

---

### Keep transactions short

- **DO** open late, write, commit fast. Open transactions hold DB locks until commit/rollback → contention, deadlocks, bloat.
- **DON'T** do network calls, user interaction, file I/O, or `Thread.sleep` inside a transaction.
- **DON'T** batch unbounded row counts in one transaction — commit in chunks (lock duration vs. rollback granularity).

---

### Savepoints (partial rollback)

```java
con.setAutoCommit(false);
Savepoint sp = con.setSavepoint("beforeRisky");   // or con.setSavepoint()
try {
    // risky work...
} catch (SQLException e) {
    con.rollback(sp);            // undo back to sp; transaction stays open
}
con.commit();                    // commits everything not rolled back
```

- `setSavepoint()` / `setSavepoint(String)` return a `Savepoint`; `rollback(sp)` undoes only work after `sp`; `releaseSavepoint(sp)` discards it.
- **DO** wrap savepoint calls expecting `SQLFeatureNotSupportedException` — not every driver supports them.
- **DON'T** use a savepoint after it's released, or after `commit()`/full `rollback()`, or after rolling back to an *earlier* savepoint (those release later ones) → `SQLException`.
- Savepoints require an active transaction (auto-commit off).

---

### Connection pooling (HikariCP) & connection-per-statement

- **DON'T** open a new `Connection` per statement for a multi-statement unit — statements on different connections are different transactions and can't be committed atomically. One transaction = one connection.
- **DO** run every statement of the unit on the same `Connection` handed out of the pool.
- HikariCP config: `autoCommit` (default `true`) and `transactionIsolation` (default = driver default; value is the `Connection` constant name, e.g. `TRANSACTION_READ_COMMITTED`) set the *baseline* for handed-out connections. HikariCP restores per-connection state on return, but **DO** still leave it as you found it — never strand a returned connection mid-transaction.
- **DO** enable `leakDetectionThreshold` (ms, e.g. `20000`) in dev to catch connections held too long. Keep `maxLifetime` (default 30 min) below any DB/infra idle timeout.
- **DON'T** hold a pooled connection across user think-time or long computation — acquire late, release fast; the pool is finite.

---

### Propagation (basics — defer to framework lore)

- Plain JDBC has **no propagation**: one physical connection = one transaction; nesting = savepoints only.
- **DON'T** hand-roll nested-transaction semantics. For REQUIRED / REQUIRES_NEW / NESTED, use the framework's transaction manager (`@Transactional`) — see framework lore. Passing one `Connection` down the call chain to "join" a transaction works but is what a framework manages for you.

---

### Sources

- JDBC Basics — Using Transactions (Java Tutorials): https://docs.oracle.com/javase/tutorial/jdbc/basics/transactions.html
- `java.sql.Connection` API (JDK 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/java/sql/Connection.html
- `java.sql` module summary (JDK 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- HikariCP (config: autoCommit, transactionIsolation, leakDetectionThreshold, maxLifetime): https://github.com/brettwooldridge/HikariCP
- PostgreSQL — Transaction Isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- MySQL 8.4 — InnoDB Transaction Isolation Levels: https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html

## Performance & batching <a id="performance-and-batching"></a>

Data-layer specifics for high-throughput JDBC. Assume Java/framework lore lives elsewhere.
API: `java.sql.*` (JDBC 4.2+, Java 8 baseline; unchanged shape through Java 21/25).

### Security first (non-negotiable)

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

### Batch DML — addBatch / executeBatch

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

#### Driver rewrite is what makes batching fast

Plain JDBC batching still sends N statements unless the driver rewrites into one multi-row statement. Enable it:

- MySQL Connector/J: `rewriteBatchedStatements=true` (default `false`; since 3.1.13). Rewrites INSERT/REPLACE batches into multi-VALUES. Caveat: `getGeneratedKeys()` only works if the whole batch is INSERT/REPLACE; unspecified stream length on `set*Stream()` can error.
- PostgreSQL pgjdbc: `reWriteBatchedInserts=true` (default `false`). Merges batch inserts into one multi-values INSERT; docs cite "2-3x performance improvement".
- DON'T assume batching helps without these flags on MySQL/Postgres — measure.

### Prepared-statement caching

- MySQL: `cachePrepStmts=true` (default `false`), `prepStmtCacheSize` (default 25 → raise, e.g. 250), `prepStmtCacheSqlLimit` (default 256 → raise, e.g. 2048), `useServerPrepStmts=true` for server-side prepares.
- Postgres: server-side prepare kicks in after `prepareThreshold` executions (default 5) of the same `PreparedStatement`.
- HikariCP README MySQL example (marked "DO NOT COPY VERBATIM"): `cachePrepStmts=true`, `prepStmtCacheSize=250`, `prepStmtCacheSqlLimit=2048`.

### Large reads — fetch size & streaming

`setFetchSize(n)` hints how many rows to pull per round trip. Default fetches everything → OOM on big result sets.

- DO set a fetch size for large scans (statement-level `setFetchSize`, or driver default).
- DON'T scroll large results: keep `ResultSet.TYPE_FORWARD_ONLY` (the default) for streaming.

#### PostgreSQL (cursor streaming — strict requirements)

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

#### MySQL (Connector/J)

- Cursor fetch: `useCursorFetch=true` + `defaultFetchSize>0` (or `setFetchSize>0`); auto-sets `useServerPrepStmts=true`.
- Row-by-row streaming alternative: `stmt.setFetchSize(Integer.MIN_VALUE)` (Connector/J special value) — reads one row at a time; the connection is unusable for other queries until the `ResultSet` is fully read/closed.

### Query hygiene (driver-agnostic)

- DON'T `SELECT *`. Name the columns you use — smaller payloads, index-only scans possible, resilient to schema changes.
- DO push filtering/paging to SQL (`WHERE`, `LIMIT`/`OFFSET` or keyset), not into Java.
- DO be index-aware: filter/join/sort on indexed columns; a leading wildcard `LIKE '%x'` or a function on a column defeats the index. Verify with `EXPLAIN`.
- DO mark read paths read-only (`con.setReadOnly(true)` or HikariCP pool `readOnly=true`) — some DBs use it for optimization / routing to replicas (HikariCP `readOnly` default `false`).
- DO close `ResultSet`/`Statement`/`Connection` (try-with-resources). Leaked connections starve the pool.

### Connection pool (HikariCP)

- DO reuse pooled connections; NEVER open a raw connection per request.
- `maximumPoolSize` default 10 — size to the DB, not the app (small pools often beat large). See HikariCP sizing wiki.
- `connectionTimeout` default 30000 ms (min 250 ms) — time `getConnection()` blocks before `SQLException`.
- DO keep transactions short; a connection held across slow work blocks the pool.

### Sources

- Oracle JDBC Tutorial — Retrieving/Modifying & Batch Updates: https://docs.oracle.com/javase/tutorial/jdbc/basics/retrieving.html , https://docs.oracle.com/javase/tutorial/jdbc/basics/batch.html
- java.sql module (JDBC API, Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- PostgreSQL JDBC — Query/cursor streaming: https://jdbc.postgresql.org/documentation/query/
- PostgreSQL JDBC — Connection parameters (reWriteBatchedInserts, defaultRowFetchSize, prepareThreshold): https://jdbc.postgresql.org/documentation/use/
- MySQL Connector/J — Performance Extensions (rewriteBatchedStatements, cachePrepStmts, useCursorFetch, defaultFetchSize): https://dev.mysql.com/doc/connector-j/en/connector-j-connp-props-performance-extensions.html
- HikariCP README (pool config, MySQL prep-stmt example, readOnly): https://github.com/brettwooldridge/HikariCP
