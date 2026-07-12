# jdbc — Connections & pooling (HikariCP)

Data-layer specifics for obtaining, pooling, and returning JDBC connections. Assume general Java/framework lore lives elsewhere. Verified against Oracle's JDBC tutorial, the HikariCP repo/wiki, and Spring Boot reference (see Sources).

**Version baseline.** HikariCP `com.zaxxer:HikariCP:7.1.0` requires **Java 11+**. Older runtimes use deprecated maintenance artifacts: Java 8 → `HikariCP:4.0.3`, Java 7 → `HikariCP-java7:2.4.13`, Java 6 → `HikariCP-java6:2.3.13`. Spring Boot's default pool **is** HikariCP: with `spring-boot-starter-jdbc` or `spring-boot-starter-data-jpa` you get it automatically ("If HikariCP is available, we always choose it"; fallback order Tomcat → DBCP2 → Oracle UCP). Tune via `spring.datasource.hikari.*`.

## DO

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

## DON'T

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

## Key HikariCP config (defaults, milliseconds unless noted)

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

## Sources

- Oracle JDBC Tutorial — Using Prepared Statements: https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html
- Oracle JDBC Tutorial — Connecting with DataSource / Connection Pooling: https://docs.oracle.com/javase/tutorial/jdbc/basics/sqldatasources.html
- Oracle JDBC Tutorial index: https://docs.oracle.com/javase/tutorial/jdbc/
- `java.sql` module summary (Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- HikariCP (config reference, defaults, requirements): https://github.com/brettwooldridge/HikariCP
- HikariCP — About Pool Sizing (formula): https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing
- Spring Boot Reference — SQL Databases / connection pool selection: https://docs.spring.io/spring-boot/reference/data/sql.html
