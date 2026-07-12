# jdbc — SQL safety (injection, PreparedStatement)

Senior-reviewer checklist. **#1 rule: user input reaches SQL only as a bound parameter, never
as concatenated text.** JDBC lives in the JDK `java.sql` package — no `javax`/`jakarta`
namespace split (that break is Hibernate/JPA, not JDBC). API is stable across Java 8+ (JDBC
4.2, JSR 221); `setObject(int, Object, SQLType)` default methods arrived in JDBC 4.2 / Java 8.

## DO — always parameterize

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

## DON'T — the injection traps

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

## Identifiers cannot be bound — allowlist them

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

## IN-lists — generate placeholders, then bind

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

## LIKE — escape wildcards in the value

Binding stops injection, but `%` and `_` in bound input are still wildcards. To match them
literally, escape in the **value** and declare the `ESCAPE` char in SQL:
```java
String term = raw.replace("!", "!!").replace("%", "!%").replace("_", "!_");
PreparedStatement ps =
    con.prepareStatement("SELECT * FROM t WHERE name LIKE ? ESCAPE '!'");
ps.setString(1, "%" + term + "%");
```

## Named parameters

Core JDBC has **no** named parameters — positional `?` only. Named params
(`:name`) come from higher layers: Spring `NamedParameterJdbcTemplate`, JPA/Hibernate,
MyBatis. Those still bind under the hood; the no-concatenation rule is unchanged. Assume Spring
lore covers `JdbcTemplate`/`NamedParameterJdbcTemplate` specifics.

## Review triggers (reject on sight)

- Any `Statement.execute*` with a `+` on the SQL string.
- Input reaching SQL outside a `setXxx` call.
- Identifier/sort input concatenated without an allowlist.
- IN-list built by joining values instead of placeholders.
- `"NULL"` literal instead of `setNull`.

## Sources

- Oracle JDBC Tutorial — Using Prepared Statements: https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html
- `java.sql.PreparedStatement` API (Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/java/sql/PreparedStatement.html
- `java.sql` module summary (Java 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- OWASP SQL Injection Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- OWASP Query Parameterization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html
