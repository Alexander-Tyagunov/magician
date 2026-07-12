# db-migrations — Migration patterns & safety

Data-layer lore: writing/reviewing schema migrations. Java + framework lore live separately. Verified against Flyway, Liquibase, PostgreSQL, MySQL, JDBC, Hibernate 6 docs (see Sources).

## Core discipline

DO:
- Treat every applied migration as immutable. Roll forward with a new migration; never rewrite history.
- Make one logical change per migration/changeset. It isolates failures and keeps rollback tractable.
- Keep migrations additive-first: add before you remove.
- Version deterministically and let the tool enforce order (Flyway `V<version>__<desc>.sql`, e.g. `V001.002__NewTwitterColumn.sql`; Liquibase changeset keyed by `author:id` + changelog path).
- Adopt a forward-only mindset: assume you cannot cleanly `ROLLBACK` production DDL. Plan the reverse path as a new migration.

DON'T:
- Don't edit a migration that has run in any shared/permanent environment. Flyway stores a CRC32 checksum in `flyway_schema_history`; Liquibase stores an MD5 checksum. Any edit changes the checksum and `validate`/`update` fails ("differences in migration names, types or checksums are found").
- Don't use `flyway repair` (realigns checksums, clears failed rows) or checksum overrides to paper over an edit you shouldn't have made.
- Don't bundle unrelated DDL + risky DML in one migration.

## Expand-contract (zero-downtime, backward-compatible)

The only safe way to change a schema while old and new app code run concurrently. Never do a breaking rename/drop in one deploy.

DO — sequence a rename of `name` → `full_name` across deploys:
1. **Expand (additive, backward-compatible):** add `full_name` nullable. Deploy migration first; old code ignores it.
   ```sql
   ALTER TABLE users ADD COLUMN full_name varchar(255) NULL;
   ```
2. **Migrate + dual-write:** new app version writes both columns; backfill existing rows in batches (separate, non-blocking DML — see below).
3. **Contract:** once every running instance uses `full_name` and backfill is done, drop the old column in a later migration (`ALTER TABLE users DROP COLUMN name;`).

DO:
- Add columns nullable, or with a default, so existing INSERTs from old code still succeed.
- Add new tables/indexes before the code that reads them.
- Deploy schema change and app change as separate steps; a migration must be safe against the previously deployed code.

DON'T:
- Don't add a `NOT NULL` column with no default to a populated table in one step — old code's INSERTs break. Add nullable → backfill → add the constraint later.
- Don't drop/rename a column or table still referenced by any running instance.
- Don't add a `FOREIGN KEY` or `NOT NULL`/`CHECK` constraint before data satisfies it; validate then enforce.

## Transactional-DDL caveats (know your engine)

Whether a failed multi-statement migration auto-rolls-back depends entirely on the database. This dictates how you size migrations.

DO:
- **PostgreSQL — transactional DDL.** `CREATE/ALTER/DROP` run inside `BEGIN … COMMIT/ROLLBACK` and roll back atomically. Flyway wraps each migration in one transaction by default; lean on it.
- **MySQL / MariaDB — DDL auto-commits.** Per MySQL 8.0 docs, `CREATE/ALTER/DROP TABLE`, `CREATE/DROP INDEX`, `TRUNCATE`, `RENAME TABLE`, etc. "implicitly end any transaction" — a `ROLLBACK` does NOT undo them. So put **one DDL statement per migration** on MySQL; a mid-migration failure leaves a partial, non-rolled-back schema.
- Know the exceptions even on Postgres: `CREATE INDEX CONCURRENTLY`, `CREATE DATABASE`, `VACUUM`, `ALTER SYSTEM` cannot run inside a transaction block.

DON'T:
- Don't assume rollback safety on MySQL/Oracle. Liquibase warns bundling statements risks "failed auto-commit statements that can leave the database in an unexpected state."
- Don't wrap `CREATE INDEX CONCURRENTLY` in a transaction — Postgres errors: `CREATE INDEX CONCURRENTLY cannot run inside a transaction block`. Flyway: set `executeInTransaction=false` (default `true`) for that script; Liquibase: `runInTransaction="false"`.

## Big-table changes (locks & online DDL)

DO:
- On Postgres, build indexes without an `ACCESS EXCLUSIVE` write lock: `CREATE INDEX CONCURRENTLY idx_users_email ON users (email);` (slower, two scans, outside a transaction; a failure leaves an INVALID index — `DROP` and retry, or `REINDEX INDEX CONCURRENTLY`).
- On MySQL 8, prefer online DDL: `ALTER TABLE … , ALGORITHM=INPLACE, LOCK=NONE;` — verify the specific change supports it.
- Run backfills/large UPDATEs in bounded batches with commits between them, off the DDL transaction, throttled and idempotent.

DON'T:
- Don't run a plain `CREATE INDEX` or table-rewriting `ALTER` on a large hot table — it locks out writes for the duration.
- Don't co-locate a long backfill with DDL; a lock held for a multi-minute copy stalls the app.

## Framework schema generation (Hibernate/JPA)

DO:
- In production use `hibernate.hbm2ddl.auto=validate` (or `none`) and let Flyway/Liquibase own schema changes. The JPA-standard equivalent is `jakarta.persistence.schema-generation.database.action`.
- Namespace: **Hibernate 6.x → `jakarta.persistence.*`** (Jakarta Persistence 3.1, Java 11+ baseline; 17/21 supported). **Hibernate 5.x / Java 8 → `javax.persistence.*`** — the Jakarta EE 9 `javax`→`jakarta` break. Match imports to the major version; not interchangeable.

DON'T:
- Don't ship `hbm2ddl.auto=update`/`create`/`create-drop` to any shared env — `update` is not JPA-defined, diff-based, and silently drifts or destroys data.

## CI gates (make safety mechanical)

DO:
- Run `flyway validate` (checksums/order) or `liquibase validate` + `status` in CI; fail the build on drift or on an edited applied migration.
- Lint/dry-run migrations pre-merge; require review for any `DROP`, `NOT NULL`, or unbatched `UPDATE/DELETE`.
- Test the migration against a clone restored from production-shaped data, not an empty schema.

DON'T:
- Don't let a migration merge without proving it applies cleanly on a copy of real data.

## SQL safety — SQL injection (non-negotiable)

DO:
- Always parameterize. In JDBC use `PreparedStatement` with `?` placeholders and typed setters — bound input is "content of a parameter and never part of an SQL statement."
  ```java
  String sql = "UPDATE users SET full_name = ? WHERE id = ?";
  try (PreparedStatement ps = con.prepareStatement(sql)) {
      ps.setString(1, fullName);
      ps.setLong(2, userId);
      ps.executeUpdate();
  }
  ```
- Wrap multi-statement DML in an explicit transaction: `con.setAutoCommit(false)` … `con.commit()`/`con.rollback()` on failure.

DON'T:
- NEVER concatenate user input into SQL — `stmt.execute("... WHERE name = '" + userInput + "'")`. This is SQL injection: "nonvalidated string literals are concatenated into a dynamically built SQL statement and interpreted as code."
- Don't interpolate user input into repeatable-migration or ORM native-query strings either. Identifiers that can't be parameterized must be checked against a strict allow-list, never passed raw.

## Sources
- Flyway concepts — migrations & naming: https://documentation.red-gate.com/flyway/flyway-concepts/migrations
- Flyway versioned migrations (immutability, checksum): https://documentation.red-gate.com/flyway/flyway-concepts/migrations/versioned-migrations
- Flyway validate: https://documentation.red-gate.com/flyway/reference/commands/validate
- Flyway repair: https://documentation.red-gate.com/flyway/reference/commands/repair
- Flyway executeInTransaction: https://documentation.red-gate.com/flyway/reference/configuration/flyway-namespace/flyway-execute-in-transaction-setting
- Flyway GitHub: https://github.com/flyway/flyway
- Liquibase changeset (one change, immutability, runInTransaction): https://docs.liquibase.com/concepts/changelogs/changeset.html
- Liquibase best-practice FAQ: https://docs.liquibase.com/
- MySQL 8.0 statements causing implicit commit: https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html
- PostgreSQL CREATE INDEX (CONCURRENTLY): https://www.postgresql.org/docs/current/sql-createindex.html
- PostgreSQL BEGIN / transaction blocks: https://www.postgresql.org/docs/current/sql-begin.html
- JDBC PreparedStatement (SQL injection): https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html
- Hibernate 6.4 User Guide (jakarta namespace, Java baseline, schema gen): https://docs.hibernate.org/orm/6.4/userguide/html_single/Hibernate_User_Guide.html
