# db-migrations — Liquibase

Version-controlled, cross-database schema migrations. A **changelog** is an ordered list of **changesets**; each changeset is applied once, tracked, and never mutated after it runs. Java-agnostic (CLI, Maven/Gradle, Spring Boot, Quarkus, Micronaut all embed it). Facts below verified against docs.liquibase.com (current major is **Liquibase 5.x**, e.g. v5.0.x; v4.33.0 is the newest 4.x line — the model is unchanged between them).

## Changelogs & changesets — DO
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

## Immutability & checksums — DON'T
- **DON'T ever edit a changeset that has already been applied.** Liquibase stores a checksum (MD5SUM column) and fails on next `update`:
  `Validation Failed: 1 change sets check sum ... was: 8:... but is now: 8:...`. Add a **new** changeset instead.
- Checksum reflects changeset *content*, not file bytes — pure formatting edits may keep the same checksum, but never rely on this.
- To fix a legitimate mismatch: null the MD5SUM row (in every environment), OR add a `validCheckSum` attribute (old or new value; in SQL it must be on its own line), OR run `liquibase clear-checksums` (wipes the WHOLE MD5SUM column — heavy-handed).
- For re-runnable objects (views, stored procs), DON'T copy into a new changeset each time — set `runOnChange="true"` so it redeploys when its text changes. `runAlways="true"` runs it on every update.

## Tracking tables — DO
- DO leave the tracking tables to Liquibase: **DATABASECHANGELOG** (one row per applied changeset: id, author, filename, MD5SUM, dateexecuted, orderexecuted, deployment_id, tag) and **DATABASECHANGELOGLOCK** (advisory lock preventing concurrent runs).
- **DATABASECHANGELOGHISTORY** (extra migration history) exists in **4.27.0+**.
- DON'T hand-edit these tables except the deliberate checksum-null fix above. A stuck lock: `liquibase release-locks`.

## Rollback — DO
- DO know that many change types **auto-generate** rollback (e.g. `createTable`, `addColumn`, `renameColumn`, `createIndex`). Types that destroy/insert data (`dropTable`, `delete`, `insert`, raw `sql`) do NOT — you must supply a `<rollback>` block.
- DO write explicit rollback for XML/YAML/JSON via `<rollback>` (or `rollback:` key); formatted SQL uses a `--rollback` comment line. Custom rollback blocks are NOT supported in modeled form inside formatted SQL.
- DO run by tag / count / date: `rollback <tag>`, `rollback-count <n>`, `rollback-to-date <YYYY-MM-DD>`. Rollback removes the corresponding DATABASECHANGELOG rows.
- DO inspect before applying: `rollback-sql`, `rollback-count-sql`, `future-rollback-sql` (SQL to revert not-yet-deployed changes — auditors' proof every change is reversible).
- DO validate reversibility in CI: `update-testing-rollback` (deploy → rollback in reverse → re-deploy).
- DON'T assume a rollback exists — if a change can't be safely reversed, give it an empty rollback deliberately (empty `<rollback/>`) so intent is explicit, not accidental.

## Contexts & labels — DO
- DO use **`context`** for *environments* (`context="test"` / `--changeset bob:1 context:test`); filter at runtime with **`--context-filter="test"`** (older `--contexts` deprecated at 4.23.1). Plain `update` with no filter runs ALL changesets regardless of context.
- DO use **`labels`** for feature/version tagging; filter with **`--label-filter`**. Same expression grammar, different axis.
- Expressions (changeset, 4.24.0+): `AND OR ! ( )` and `@`; comma = OR; precedence `! , AND , OR`. `@test` means "skip unless a context was explicitly provided."
- For multi-DBMS changelogs use the **`dbms`** precondition, NOT contexts.

## Preconditions — DO
- DO guard changesets with `<preConditions>` (local, per changeset) or a global block in the changelog (evaluated in the validation phase before any changeset runs). Since Liquibase 1.7.
- DO set **`onFail`** explicitly — default is **`HALT`**. Others: `WARN` (log, continue), `CONTINUE` (skip now, retry next run — changeset-only), `MARK_RAN` (skip but mark executed — changeset-only). `onError` takes the same values.
- Common types: `dbms` (`type=`), `tableExists`/`columnExists`, `changeSetExecuted`, `sqlCheck` (`expectedResult` + `sql`, must return one row/one value). `dbms` and `runningAs` are not available in formatted SQL.
- Combine with nestable `and`/`or`/`not` (default `and`); evaluation is lazy.

## SQL safety — NON-NEGOTIABLE
- DON'T build changeset SQL by concatenating runtime/user input — that is SQL injection. Changelogs are static, checked-in artifacts; keep untrusted values out entirely.
- For dynamic values in `sqlCheck` / `sql`, use Liquibase **changelog properties** (`${prop}` via `-D`/property files), not string-built values. `${}` substitution is literal — never interpolate untrusted input into a precondition or migration.
- Application data access is separate — see `lore/jdbc.md` (PreparedStatement) and `lore/orm.md` (bind params). Never route user input through migrations.

## Framework integration
- Spring Boot: `spring.liquibase.change-log=classpath:db/changelog/db.changelog-master.xml`; runs on startup. Quarkus: `quarkus.liquibase.migrate-at-start=true`. Micronaut: `io.micronaut.liquibase`. Prefer running migrations as an explicit deploy step in prod, not silently at boot, when multiple instances start concurrently (the LOCK table serializes them, but plan for it).

## Sources
- https://docs.liquibase.com/concepts/changelogs/home.html
- https://docs.liquibase.com/concepts/changelogs/changeset.html
- https://docs.liquibase.com/concepts/changelogs/changeset-checksums.html
- https://docs.liquibase.com/workflows/liquibase-community/using-rollback.html
- https://docs.liquibase.com/concepts/changelogs/attributes/contexts.html
- https://docs.liquibase.com/concepts/changelogs/preconditions.html
- https://docs.liquibase.com/concepts/tracking-tables/tracking-tables.html
- https://github.com/liquibase/liquibase
