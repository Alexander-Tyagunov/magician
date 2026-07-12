# jdbc — Transactions

Hand-rolled JDBC transactions. For `@Transactional`/Spring/JPA propagation, defer to framework lore. Java + JDBC lore assumed separate.

Baseline: `java.sql` (JDK). Savepoints + `rollback(Savepoint)` require JDBC 3.0 / Java 1.4+. All methods throw `SQLException`.

---

## DO — the transaction skeleton

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

## DON'T

- **DON'T** leave auto-commit on for a logical unit → partial writes on failure.
- **DON'T** assume `close()` commits or rolls back. Undefined. Be explicit.

---

## DO — security: never concatenate SQL (always applies)

- **DO** use `PreparedStatement` with `?` placeholders + `setXxx(...)` for every user value. Parameterization defeats SQL injection and lets the driver cache plans.
- **DON'T** build SQL by string concatenation / interpolation of input:

```java
stmt.executeUpdate("UPDATE accounts SET balance="+v+" WHERE id="+id); // NEVER — injection
```

---

## try-with-resources ordering

- **DO** manage the transaction on the **`Connection`**; put `Statement`/`ResultSet` in try-with-resources so they close first (LIFO — reverse of declaration).
- **DON'T** put the `Connection` in the *same* try-with-resources as the statements when you commit after the block — it would close before `commit()`. Commit inside the block, or manage the connection in `finally` (as above).
- Nesting is safe: outer `try (Connection…)` for lifecycle, inner `try (PreparedStatement…)` per unit; commit before the connection closes.

---

## Isolation levels & anomalies

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

## Keep transactions short

- **DO** open late, write, commit fast. Open transactions hold DB locks until commit/rollback → contention, deadlocks, bloat.
- **DON'T** do network calls, user interaction, file I/O, or `Thread.sleep` inside a transaction.
- **DON'T** batch unbounded row counts in one transaction — commit in chunks (lock duration vs. rollback granularity).

---

## Savepoints (partial rollback)

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

## Connection pooling (HikariCP) & connection-per-statement

- **DON'T** open a new `Connection` per statement for a multi-statement unit — statements on different connections are different transactions and can't be committed atomically. One transaction = one connection.
- **DO** run every statement of the unit on the same `Connection` handed out of the pool.
- HikariCP config: `autoCommit` (default `true`) and `transactionIsolation` (default = driver default; value is the `Connection` constant name, e.g. `TRANSACTION_READ_COMMITTED`) set the *baseline* for handed-out connections. HikariCP restores per-connection state on return, but **DO** still leave it as you found it — never strand a returned connection mid-transaction.
- **DO** enable `leakDetectionThreshold` (ms, e.g. `20000`) in dev to catch connections held too long. Keep `maxLifetime` (default 30 min) below any DB/infra idle timeout.
- **DON'T** hold a pooled connection across user think-time or long computation — acquire late, release fast; the pool is finite.

---

## Propagation (basics — defer to framework lore)

- Plain JDBC has **no propagation**: one physical connection = one transaction; nesting = savepoints only.
- **DON'T** hand-roll nested-transaction semantics. For REQUIRED / REQUIRES_NEW / NESTED, use the framework's transaction manager (`@Transactional`) — see framework lore. Passing one `Connection` down the call chain to "join" a transaction works but is what a framework manages for you.

---

## Sources

- JDBC Basics — Using Transactions (Java Tutorials): https://docs.oracle.com/javase/tutorial/jdbc/basics/transactions.html
- `java.sql.Connection` API (JDK 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/java/sql/Connection.html
- `java.sql` module summary (JDK 25): https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/module-summary.html
- HikariCP (config: autoCommit, transactionIsolation, leakDetectionThreshold, maxLifetime): https://github.com/brettwooldridge/HikariCP
- PostgreSQL — Transaction Isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- MySQL 8.4 — InnoDB Transaction Isolation Levels: https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html
