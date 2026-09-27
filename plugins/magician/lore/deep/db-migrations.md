# db-migrations — deep dive

> On-demand companion to `lore/db-migrations.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Flyway](#flyway) · [Liquibase](#liquibase) · [Migration patterns & safety](#patterns-and-safety)

## Flyway <a id="flyway"></a>

Data-layer lore for an AI agent writing Flyway migrations. Java/framework lore lives elsewhere.
Flyway 10+ requires **JDK 17+** (stated since 10.0.0). The CLI/Docker distribution bundles its own JRE (e.g. 11.19.0 ships Java 25) — that is the shipped runtime, not your project's minimum. Defaults verified against Red Gate docs.

### Migration types & naming

Structure: `prefix` `VERSION` `separator` `DESCRIPTION` `suffix` → `V1.1__My_description.sql`.
Defaults: location `classpath:db/migration`, table `flyway_schema_history`, separator `__`, suffix `.sql`.

| Type | Prefix | Example | Runs |
|---|---|---|---|
| Versioned | `V` | `V2__add_orders.sql` | once, in version order, tracked |
| Repeatable | `R` (no version) | `R__refresh_views.sql` | (re)applied when checksum changes, after versioned |
| Undo | `U` | `U2__drop_orders.sql` | reverses matching `V` — **paid Teams/Enterprise** |

#### DO
- Use a monotonic version scheme the team agrees on: `V1`, `V2` or `V20260711_1400` (timestamps dodge merge collisions).
- Put views/functions/procedures/grants in **repeatable** (`R__`) migrations — idempotent, re-run on change, ordered by description.
- Write the SQL to be replayable on a fresh DB in the exact recorded order (same scripts, same order, every env).
- One logical change per versioned file; keep them small and forward-only.

#### DON'T
- **NEVER edit a migration already applied to any shared DB.** Flyway stores a checksum (**CRC32** for SQL) at apply time; changing the file → `CHECKSUM_MISMATCH` on next `validate`/`migrate` (`validateOnMigrate` is on by default, so `migrate` fails). Fix forward with a new `Vn` instead.
- Don't reuse or reorder version numbers, or rename an applied file — both break validation.
- Don't rely on undo migrations for prod rollback; they're paid, easy to get wrong, and don't cover repeatables. Prefer roll-forward.

### Checksum drift & repair

Mismatch error tells you the two options verbatim: *"Either revert the changes to the migration, or run repair to update the schema history."*
- **Revert the file** if the edit was accidental — restores the original checksum.
- `flyway repair` rewrites `flyway_schema_history` checksums to match current files **and** removes failed-migration rows. Only run when the SQL change is truly cosmetic (whitespace/comments) and already applied everywhere — it makes Flyway "forget" the drift.

### Baseline (adopting an existing DB)

For a non-empty DB with no history table:
- `flyway baseline` (or `baselineVersion`, default `1`) marks the DB as migrated up to that version; earlier `V`s are skipped.
- `baselineOnMigrate=true` auto-baselines on first `migrate` against a populated schema. Set `baselineVersion` so your first real migration is strictly greater.

```properties
flyway.baselineOnMigrate=true
flyway.baselineVersion=1
```

### Out-of-order & clean

- `outOfOrder` (default **false**): when false, a lower-version migration that appears after higher ones is **ignored** as too-late. Enable only for controlled hotfix backports; keep off in strict CI.
- **`clean` drops all objects in configured schemas.** Docs: *"Do not use against your production DB!"* `cleanDisabled` defaults to **true** since Flyway 9.0.0 — **keep it true in every non-throwaway env**. Only enable for local/test scratch DBs.

```properties
flyway.cleanDisabled=true   # never flip to false in prod/staging
```

### Java-based migrations

Use when SQL can't express it (data backfills, conditional logic, calling app code). File/class name follows the same convention: `V3__Anonymize`.

```java
package db.migration;
import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;
import java.sql.PreparedStatement;

public class V3__Anonymize extends BaseJavaMigration {
    public void migrate(Context context) throws Exception {
        // SECURITY: bind every value — NEVER concatenate into SQL (injection).
        try (PreparedStatement ps = context.getConnection()
                .prepareStatement("UPDATE person SET name = ? WHERE id = ?")) {
            // ... loop rows, ps.setString(1, name); ps.setInt(2, id); ps.addBatch();
            ps.executeBatch();
        }
    }
}
```

#### DO
- Extend `BaseJavaMigration`; implement `migrate(Context)`; get JDBC via `context.getConnection()`.
- Use `PreparedStatement` with bound params for every dynamic value.
- Let Flyway own the transaction — don't `commit()`/`close()` the provided connection.

#### DON'T
- **Don't build SQL by string concatenation of variable/user input** — the official tutorial's `"...WHERE id="+id` snippet is a SQL-injection anti-pattern; parameterize it.
- Don't do non-transactional/non-idempotent side effects (external calls) inside a migration.

### Framework & build integration

**Spring Boot** — put `org.flywaydb:flyway-core` (plus the DB module, e.g. `flyway-database-postgresql`, on Flyway 10+) on the classpath; Boot auto-runs `migrate` at startup. Configure via `spring.flyway.*` (mapped to `flyway.*`):
```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true
    clean-disabled: true
```
Boot 3.x = Jakarta baseline (Java 17+); Boot 2.x = javax/Java 8. Register Spring-managed Java migrations with `.javaMigrations(ctx.getBeansOfType(JavaMigration.class).values()...)`.

**Gradle** — `org.flywaydb.flyway` plugin; make classes build before Java migrations: `flywayMigrate.dependsOn classes`.

**Maven** — plugin `com.redgate.flyway:flyway-maven-plugin`; add `com.redgate.flyway:flyway-redgate-licensing` for Teams/Enterprise features (undo, etc.).

#### Cross-cutting DO / DON'T
- DO run `flyway validate` (or `info`) in CI before deploy to catch drift and pending/missing migrations.
- DO keep migrations in version control alongside app code; treat applied files as immutable.
- DON'T grant the app runtime user `clean`/DDL rights beyond what migrations need; run migrations with a dedicated migration user.

### Sources
- https://documentation.red-gate.com/flyway/
- https://documentation.red-gate.com/flyway/flyway-concepts/migrations
- https://documentation.red-gate.com/flyway/reference/commands/clean
- https://github.com/flyway/flyway (flyway-core defaults, Configuration, DbRepair, Flyway.migrate, release notes)
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Commands/Validate.md
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Commands/Undo.md
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Tutorials/Tutorial%20-%20Java-based%20Migrations.md
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Usage/API%20(Java).md
- https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html

## Liquibase <a id="liquibase"></a>

Version-controlled, cross-database schema migrations. A **changelog** is an ordered list of **changesets**; each changeset is applied once, tracked, and never mutated after it runs. Java-agnostic (CLI, Maven/Gradle, Spring Boot, Quarkus, Micronaut all embed it). Facts below verified against docs.liquibase.com (current major is **Liquibase 5.x**, e.g. v5.0.x; v4.33.0 is the newest 4.x line — the model is unchanged between them).

### Changelogs & changesets — DO
- DO pick one changelog format and stay consistent: **SQL** (`.sql`), **XML**, **YAML**, or **JSON**. Root changelog using `include`/`includeAll` must be XML/YAML/JSON (not formatted SQL).
- DO give every changeset a **unique `id` + `author`**. Identity = `id` + `author` + changelog file path (search-path relative). `id` need not be an integer and does NOT control run order — file order does.
- DO keep **one change type per changeset**. Multiple DDL statements in one changeset risk failed auto-commit leaving the DB in an unexpected state.
- DO use **formatted-SQL headers** in `.sql` files: first line `--liquibase formatted sql`, then `--changeset author:id`.
- DO set `logicalFilePath` on the changelog before moving/renaming a file — otherwise the path changes and every changeset looks new (re-runs).

```xml
<changeSet id="1" author="alex">
  <createTable tableName="app_user">
    <column name="id" type="bigint"><constraints primaryKey="true"/></column>
    <column name="email" type="varchar(255)"><constraints nullable="false" unique="true"/></column>
  </createTable>
</changeSet>
```
```sql
--liquibase formatted sql
--changeset alex:1
CREATE TABLE app_user (id BIGINT PRIMARY KEY, email VARCHAR(255) NOT NULL UNIQUE);
--rollback DROP TABLE app_user;
```

### Immutability & checksums — DON'T
- **DON'T ever edit a changeset that has already been applied.** Liquibase stores a checksum (MD5SUM column) and fails on next `update`:
  `Validation Failed: 1 change sets check sum ... was: 8:... but is now: 8:...`. Add a **new** changeset instead.
- Checksum reflects changeset *content*, not file bytes — pure formatting edits may keep the same checksum, but never rely on this.
- To fix a legitimate mismatch: null the MD5SUM row (in every environment), OR add a `validCheckSum` attribute (old or new value; in SQL it must be on its own line), OR run `liquibase clear-checksums` (wipes the WHOLE MD5SUM column — heavy-handed).
- For re-runnable objects (views, stored procs), DON'T copy into a new changeset each time — set `runOnChange="true"` so it redeploys when its text changes. `runAlways="true"` runs it on every update.

### Tracking tables — DO
- DO leave the tracking tables to Liquibase: **DATABASECHANGELOG** (one row per applied changeset: id, author, filename, MD5SUM, dateexecuted, orderexecuted, deployment_id, tag) and **DATABASECHANGELOGLOCK** (advisory lock preventing concurrent runs).
- **DATABASECHANGELOGHISTORY** (extra migration history) exists in **4.27.0+**.
- DON'T hand-edit these tables except the deliberate checksum-null fix above. A stuck lock: `liquibase release-locks`.

### Rollback — DO
- DO know that many change types **auto-generate** rollback (e.g. `createTable`, `addColumn`, `renameColumn`, `createIndex`). Types that destroy/insert data (`dropTable`, `delete`, `insert`, raw `sql`) do NOT — you must supply a `<rollback>` block.
- DO write explicit rollback for XML/YAML/JSON via `<rollback>` (or `rollback:` key); formatted SQL uses a `--rollback` comment line. Custom rollback blocks are NOT supported in modeled form inside formatted SQL.
- DO run by tag / count / date: `rollback <tag>`, `rollback-count <n>`, `rollback-to-date <YYYY-MM-DD>`. Rollback removes the corresponding DATABASECHANGELOG rows.
- DO inspect before applying: `rollback-sql`, `rollback-count-sql`, `future-rollback-sql` (SQL to revert not-yet-deployed changes — auditors' proof every change is reversible).
- DO validate reversibility in CI: `update-testing-rollback` (deploy → rollback in reverse → re-deploy).
- DON'T assume a rollback exists — if a change can't be safely reversed, give it an empty rollback deliberately (empty `<rollback/>`) so intent is explicit, not accidental.

### Contexts & labels — DO
- DO use **`context`** for *environments* (`context="test"` / `--changeset bob:1 context:test`); filter at runtime with **`--context-filter="test"`** (older `--contexts` deprecated at 4.23.1). Plain `update` with no filter runs ALL changesets regardless of context.
- DO use **`labels`** for feature/version tagging; filter with **`--label-filter`**. Same expression grammar, different axis.
- Expressions (changeset, 4.24.0+): `AND OR ! ( )` and `@`; comma = OR; precedence `! , AND , OR`. `@test` means "skip unless a context was explicitly provided."
- For multi-DBMS changelogs use the **`dbms`** precondition, NOT contexts.

### Preconditions — DO
- DO guard changesets with `<preConditions>` (local, per changeset) or a global block in the changelog (evaluated in the validation phase before any changeset runs). Since Liquibase 1.7.
- DO set **`onFail`** explicitly — default is **`HALT`**. Others: `WARN` (log, continue), `CONTINUE` (skip now, retry next run — changeset-only), `MARK_RAN` (skip but mark executed — changeset-only). `onError` takes the same values.
- Common types: `dbms` (`type=`), `tableExists`/`columnExists`, `changeSetExecuted`, `sqlCheck` (`expectedResult` + `sql`, must return one row/one value). `dbms` and `runningAs` are not available in formatted SQL.
- Combine with nestable `and`/`or`/`not` (default `and`); evaluation is lazy.

### SQL safety — NON-NEGOTIABLE
- DON'T build changeset SQL by concatenating runtime/user input — that is SQL injection. Changelogs are static, checked-in artifacts; keep untrusted values out entirely.
- For dynamic values in `sqlCheck` / `sql`, use Liquibase **changelog properties** (`${prop}` via `-D`/property files), not string-built values. `${}` substitution is literal — never interpolate untrusted input into a precondition or migration.
- Application data access is separate — see `lore/jdbc.md` (PreparedStatement) and `lore/orm.md` (bind params). Never route user input through migrations.

### Framework integration
- Spring Boot: `spring.liquibase.change-log=classpath:db/changelog/db.changelog-master.xml`; runs on startup. Quarkus: `quarkus.liquibase.migrate-at-start=true`. Micronaut: `io.micronaut.liquibase`. Prefer running migrations as an explicit deploy step in prod, not silently at boot, when multiple instances start concurrently (the LOCK table serializes them, but plan for it).

### Sources
- https://docs.liquibase.com/concepts/changelogs/home.html
- https://docs.liquibase.com/concepts/changelogs/changeset.html
- https://docs.liquibase.com/concepts/changelogs/changeset-checksums.html
- https://docs.liquibase.com/workflows/liquibase-community/using-rollback.html
- https://docs.liquibase.com/concepts/changelogs/attributes/contexts.html
- https://docs.liquibase.com/concepts/changelogs/preconditions.html
- https://docs.liquibase.com/concepts/tracking-tables/tracking-tables.html
- https://github.com/liquibase/liquibase

## Migration patterns & safety <a id="patterns-and-safety"></a>

Data-layer lore: writing/reviewing schema migrations. Java + framework lore live separately. Verified against Flyway, Liquibase, PostgreSQL, MySQL, JDBC, Hibernate 6 docs (see Sources).

### Core discipline

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

### Expand-contract (zero-downtime, backward-compatible)

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

### Transactional-DDL caveats (know your engine)

Whether a failed multi-statement migration auto-rolls-back depends entirely on the database. This dictates how you size migrations.

DO:
- **PostgreSQL — transactional DDL.** `CREATE/ALTER/DROP` run inside `BEGIN … COMMIT/ROLLBACK` and roll back atomically. Flyway wraps each migration in one transaction by default; lean on it.
- **MySQL / MariaDB — DDL auto-commits.** Per MySQL 8.0 docs, `CREATE/ALTER/DROP TABLE`, `CREATE/DROP INDEX`, `TRUNCATE`, `RENAME TABLE`, etc. "implicitly end any transaction" — a `ROLLBACK` does NOT undo them. So put **one DDL statement per migration** on MySQL; a mid-migration failure leaves a partial, non-rolled-back schema.
- Know the exceptions even on Postgres: `CREATE INDEX CONCURRENTLY`, `CREATE DATABASE`, `VACUUM`, `ALTER SYSTEM` cannot run inside a transaction block.

DON'T:
- Don't assume rollback safety on MySQL/Oracle. Liquibase warns bundling statements risks "failed auto-commit statements that can leave the database in an unexpected state."
- Don't wrap `CREATE INDEX CONCURRENTLY` in a transaction — Postgres errors: `CREATE INDEX CONCURRENTLY cannot run inside a transaction block`. Flyway: set `executeInTransaction=false` (default `true`) for that script; Liquibase: `runInTransaction="false"`.

### Big-table changes (locks & online DDL)

DO:
- On Postgres, build indexes without an `ACCESS EXCLUSIVE` write lock: `CREATE INDEX CONCURRENTLY idx_users_email ON users (email);` (slower, two scans, outside a transaction; a failure leaves an INVALID index — `DROP` and retry, or `REINDEX INDEX CONCURRENTLY`).
- On MySQL 8, prefer online DDL: `ALTER TABLE … , ALGORITHM=INPLACE, LOCK=NONE;` — verify the specific change supports it.
- Run backfills/large UPDATEs in bounded batches with commits between them, off the DDL transaction, throttled and idempotent.

DON'T:
- Don't run a plain `CREATE INDEX` or table-rewriting `ALTER` on a large hot table — it locks out writes for the duration.
- Don't co-locate a long backfill with DDL; a lock held for a multi-minute copy stalls the app.

### Framework schema generation (Hibernate/JPA)

DO:
- In production use `hibernate.hbm2ddl.auto=validate` (or `none`) and let Flyway/Liquibase own schema changes. The JPA-standard equivalent is `jakarta.persistence.schema-generation.database.action`.
- Namespace: **Hibernate 6.x → `jakarta.persistence.*`** (Jakarta Persistence 3.1, Java 11+ baseline; 17/21 supported). **Hibernate 5.x / Java 8 → `javax.persistence.*`** — the Jakarta EE 9 `javax`→`jakarta` break. Match imports to the major version; not interchangeable.

DON'T:
- Don't ship `hbm2ddl.auto=update`/`create`/`create-drop` to any shared env — `update` is not JPA-defined, diff-based, and silently drifts or destroys data.

### CI gates (make safety mechanical)

DO:
- Run `flyway validate` (checksums/order) or `liquibase validate` + `status` in CI; fail the build on drift or on an edited applied migration.
- Lint/dry-run migrations pre-merge; require review for any `DROP`, `NOT NULL`, or unbatched `UPDATE/DELETE`.
- Test the migration against a clone restored from production-shaped data, not an empty schema.

DON'T:
- Don't let a migration merge without proving it applies cleanly on a copy of real data.

### SQL safety — SQL injection (non-negotiable)

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

### Sources
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
