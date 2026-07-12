# DB Migrations — core

*Language-agnostic: Flyway/Liquibase are standalone tools — same rules from any JVM language (and non-JVM via CLI).*

DO
- Treat applied migrations as immutable: fix forward with a NEW migration; never edit/renumber/delete a committed or applied one (checksum breaks validate).
- One logical change per migration/changeset; version sequentially; keep idempotent where possible.
- Review every migration as destructive by default: back up, run in a transaction (DB permitting), test rollback before prod.
- Parameterize all dynamic SQL (`?` / PreparedStatement); NEVER concatenate user/runtime input into SQL — injection. Keep DDL scripts static, no interpolation.
- Split schema change from data backfill; batch large backfills off the hot path.

DON'T
- Don't run `flyway clean` or drop/truncate against a shared/prod DB.
- Don't inline env-specific values — use contexts/labels/placeholders.
- Don't assume auto-rollback: several DBs (e.g. MySQL) don't transact DDL.

Flyway: `V`__ versioned, `R`__ repeatable, `U`__ undo (paid); sep `__`; default `classpath:db/migration`; table `flyway_schema_history`. Cmds: migrate, info, validate, baseline, repair.
Liquibase: changelog + changesets keyed by id+author (XML/YAML/JSON/SQL); tables DATABASECHANGELOG(+LOCK); define rollback. Cmds: update, status, rollback, validate, changelog-sync.

Deep dive when writing non-trivial db-migrations — read lore/db-migrations/{flyway,liquibase,patterns-and-safety}.md

## Sources
documentation.red-gate.com/flyway; docs.liquibase.com; github.com/flyway/flyway
