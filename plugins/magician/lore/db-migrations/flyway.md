# db-migrations — Flyway

Data-layer lore for an AI agent writing Flyway migrations. Java/framework lore lives elsewhere.
Flyway 10+ requires **JDK 17+** (stated since 10.0.0). The CLI/Docker distribution bundles its own JRE (e.g. 11.19.0 ships Java 25) — that is the shipped runtime, not your project's minimum. Defaults verified against Red Gate docs.

## Migration types & naming

Structure: `prefix` `VERSION` `separator` `DESCRIPTION` `suffix` → `V1.1__My_description.sql`.
Defaults: location `classpath:db/migration`, table `flyway_schema_history`, separator `__`, suffix `.sql`.

| Type | Prefix | Example | Runs |
|---|---|---|---|
| Versioned | `V` | `V2__add_orders.sql` | once, in version order, tracked |
| Repeatable | `R` (no version) | `R__refresh_views.sql` | (re)applied when checksum changes, after versioned |
| Undo | `U` | `U2__drop_orders.sql` | reverses matching `V` — **paid Teams/Enterprise** |

### DO
- Use a monotonic version scheme the team agrees on: `V1`, `V2` or `V20260711_1400` (timestamps dodge merge collisions).
- Put views/functions/procedures/grants in **repeatable** (`R__`) migrations — idempotent, re-run on change, ordered by description.
- Write the SQL to be replayable on a fresh DB in the exact recorded order (same scripts, same order, every env).
- One logical change per versioned file; keep them small and forward-only.

### DON'T
- **NEVER edit a migration already applied to any shared DB.** Flyway stores a checksum (**CRC32** for SQL) at apply time; changing the file → `CHECKSUM_MISMATCH` on next `validate`/`migrate` (`validateOnMigrate` is on by default, so `migrate` fails). Fix forward with a new `Vn` instead.
- Don't reuse or reorder version numbers, or rename an applied file — both break validation.
- Don't rely on undo migrations for prod rollback; they're paid, easy to get wrong, and don't cover repeatables. Prefer roll-forward.

## Checksum drift & repair

Mismatch error tells you the two options verbatim: *"Either revert the changes to the migration, or run repair to update the schema history."*
- **Revert the file** if the edit was accidental — restores the original checksum.
- `flyway repair` rewrites `flyway_schema_history` checksums to match current files **and** removes failed-migration rows. Only run when the SQL change is truly cosmetic (whitespace/comments) and already applied everywhere — it makes Flyway "forget" the drift.

## Baseline (adopting an existing DB)

For a non-empty DB with no history table:
- `flyway baseline` (or `baselineVersion`, default `1`) marks the DB as migrated up to that version; earlier `V`s are skipped.
- `baselineOnMigrate=true` auto-baselines on first `migrate` against a populated schema. Set `baselineVersion` so your first real migration is strictly greater.

```properties
flyway.baselineOnMigrate=true
flyway.baselineVersion=1
```

## Out-of-order & clean

- `outOfOrder` (default **false**): when false, a lower-version migration that appears after higher ones is **ignored** as too-late. Enable only for controlled hotfix backports; keep off in strict CI.
- **`clean` drops all objects in configured schemas.** Docs: *"Do not use against your production DB!"* `cleanDisabled` defaults to **true** since Flyway 9.0.0 — **keep it true in every non-throwaway env**. Only enable for local/test scratch DBs.

```properties
flyway.cleanDisabled=true   # never flip to false in prod/staging
```

## Java-based migrations

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

### DO
- Extend `BaseJavaMigration`; implement `migrate(Context)`; get JDBC via `context.getConnection()`.
- Use `PreparedStatement` with bound params for every dynamic value.
- Let Flyway own the transaction — don't `commit()`/`close()` the provided connection.

### DON'T
- **Don't build SQL by string concatenation of variable/user input** — the official tutorial's `"...WHERE id="+id` snippet is a SQL-injection anti-pattern; parameterize it.
- Don't do non-transactional/non-idempotent side effects (external calls) inside a migration.

## Framework & build integration

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

### Cross-cutting DO / DON'T
- DO run `flyway validate` (or `info`) in CI before deploy to catch drift and pending/missing migrations.
- DO keep migrations in version control alongside app code; treat applied files as immutable.
- DON'T grant the app runtime user `clean`/DDL rights beyond what migrations need; run migrations with a dedicated migration user.

## Sources
- https://documentation.red-gate.com/flyway/
- https://documentation.red-gate.com/flyway/flyway-concepts/migrations
- https://documentation.red-gate.com/flyway/reference/commands/clean
- https://github.com/flyway/flyway (flyway-core defaults, Configuration, DbRepair, Flyway.migrate, release notes)
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Commands/Validate.md
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Commands/Undo.md
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Tutorials/Tutorial%20-%20Java-based%20Migrations.md
- https://github.com/flyway/flyway/blob/main/documentation/Reference/Usage/API%20(Java).md
- https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html
