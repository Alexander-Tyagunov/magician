# JDBC — core digest

*JVM-wide: `java.sql` is identical from Java/Kotlin/Scala/Groovy (examples in Java).*

DO parameterize every query: `PreparedStatement` + `?`, set via `ps.setString(1,v)` (1-based). Precompiled + injection-safe.
DON'T ever concatenate/interpolate user input into SQL — injection. No exceptions; allowlist dynamic identifiers.
DO wrap Connection/Statement/ResultSet in try-with-resources (Java 7+) so they always close.
DO group related writes in a tx: `con.setAutoCommit(false)` → work → `commit()`, `rollback()` on catch. Default is autocommit per statement.
DO batch bulk DML: `addBatch()` in loop + `executeBatch()`, inside one tx.
DON'T open a raw connection per request — pool it (HikariCP). No `Class.forName`: JDBC 4.0+ auto-loads drivers via ServiceLoader.

HikariCP defaults (ms): maximumPoolSize 10, minimumIdle=max, connectionTimeout 30000, idleTimeout 600000, maxLifetime 1800000, autoCommit true. Right-size, don't inflate.

Version: JDBC lives in the `java.sql` module (Java 9+). ORM above it — Hibernate 6.x → `jakarta.persistence.*` (Jakarta EE 9+, Java 11/17+); Hibernate 5.x → `javax.persistence.*` (Java 8).

Deep dive when writing non-trivial jdbc — read lore/jdbc/{sql-safety,connections-and-pooling,transactions,performance-and-batching}.md

Sources: docs.oracle.com/javase/tutorial/jdbc • docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html • github.com/brettwooldridge/HikariCP
