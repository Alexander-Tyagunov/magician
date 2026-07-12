# Kysely (core digest)

JS/Node TypeScript SQL query builder — a JS/Node ORM, distinct from the JVM `orm` lore. Assumes JS/TS/Node lore is separate.

Version: 0.28.x / 0.29.x (2026). TS 5.4+ with `strict`. 5 dialects: Postgres, MySQL, MSSQL, SQLite, PGlite. One `Kysely` instance per DB (singleton).

DO parameterize by default — the builder and the `sql` template tag bind `${x}` as params: ``sql`id = ${id}` `` → `id = $1`.
DO reference columns/identifiers via `ref`/`sql.ref`, `sql.id`, `sql.table`, or `db.dynamic` (type-checked, not raw text).
DO prefer the typed builder + `fn`/`eb` over the `sql` tag (least type-safe).
DO run schema changes via `Migrator.migrateToLatest()` from `kysely/migration`; keep migrations frozen-in-time (`Kysely<any>`).

DON'T pass user input to `sql.raw(str)` or `sql.lit(v)` — they emit text verbatim, unparameterized → SQL injection. Inject values only through `${}`.
DON'T build identifiers (table/column) from untrusted strings, even via `ref`/`id`/`dynamic` — identifier injection; allow-list them.
DON'T concatenate user input into any raw SQL string.

Commands: `npm i kysely <pg|mysql2|better-sqlite3>`; migrate/seed via `kysely-ctl`; generate DB types via `kysely-codegen` (both separate packages).

Deep dive when writing non-trivial kysely — read lore/kysely/{query-builder-and-types}.md

## Sources
kysely.dev/docs/{intro,getting-started,recipes/raw-sql,migrations}; context7 /kysely-org/kysely (0.28.3)
