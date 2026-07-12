# Drizzle ORM (JS/Node lore)

JS/Node ORM — distinct from the JVM `orm` lore. Headless, SQL-first, TS schema, zero deps. Verify vs orm.drizzle.team.
Version cue (2026-07): stable drizzle-orm 0.45.x / drizzle-kit 0.31.x; v1.0 in RC. Fast-moving — pin exact versions, re-check API before use.

DO
- Define schema in TS (pgTable/mysqlTable/sqliteTable); import operators (eq, and, or, inArray, like) from drizzle-orm for `where`.
- Parameterize raw SQL by interpolation: sql`... where id = ${id}` → bound $1. Safe.
- Reuse queries via sql.placeholder('id') + .prepare() + .execute({ id }).
- Relational queries: drizzle(client, { schema }); db.query.users.findMany({ with: { posts: true } }).
- Migrations: `generate` then `migrate` (commit the SQL files). Compose conditional queries with .$dynamic().

DON'T
- NEVER pass user input to sql.raw() / sql.identifier() — inlined unescaped = SQL injection. Raw is for trusted, static fragments only.
- Never interpolate untrusted values into table/column identifiers.
- Don't run `drizzle-kit push` on production — it diffs+applies with no migration history; use generate+migrate.
- Don't assume v1.0 defineRelations / RQB v2 shapes on stable 0.4x.

Commands: drizzle-kit generate | migrate | push | pull | studio | check | up

Deep dive when writing non-trivial drizzle — read lore/drizzle/{schema-and-queries,migrations-and-pitfalls}.md

## Sources
orm.drizzle.team/docs/{overview,sql,rqb,kit-overview}; context7 drizzle-orm-docs; npm drizzle-orm/drizzle-kit
