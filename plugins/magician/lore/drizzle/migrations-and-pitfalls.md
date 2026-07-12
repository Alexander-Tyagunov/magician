# drizzle — Migrations & pitfalls

JS/Node ORM (TypeScript-first). Distinct from the JVM `orm` lore. Fast-moving 0.3x
line — guidance dated **mid-2026: drizzle-orm 0.3x, drizzle-kit ~0.31.x**. Re-verify
API against orm.drizzle.team before asserting; a v1.0 Beta exists but 0.3x is current stable.

Schema is TypeScript (`pgTable`/`mysqlTable`/`sqliteTable`). `drizzle-kit` diffs schema
→ SQL. Two philosophies: **codebase-first** (TS schema is truth → apply to DB) and
**database-first** (`pull`/introspect DB → TS). Pick one direction per project.

## Two migration flows

- **generate + migrate** — versioned SQL files, tracked in DB. Use for production / teams / CI.
- **push** — diff TS schema straight to DB, no SQL files. Use for prototyping / local iteration.

`drizzle-kit` commands (run via `npx drizzle-kit <cmd>`, config in `drizzle.config.ts`):
`generate` · `migrate` · `push` · `pull` · `check` · `up` · `export` · `studio`.

## DO — generate/migrate as source of truth

- DO treat the `out` folder (`./drizzle`) as **the source of truth**. Each `generate`
  writes a `NNNN_name.sql` + a `snapshot.json` under `meta/`; the next `generate`
  diffs against those snapshots. Commit the whole folder.
- DO run `drizzle-kit generate` on every schema change, review the SQL, then apply with
  `drizzle-kit migrate` (or the runtime migrator).
- DO run migrations at runtime for zero-downtime / serverless deploys:
  ```ts
  import { drizzle } from 'drizzle-orm/node-postgres';
  import { migrate } from 'drizzle-orm/node-postgres/migrator';
  const db = drizzle(process.env.DATABASE_URL!);
  await migrate(db, { migrationsFolder: './drizzle' });
  ```
  `migrate()` is safe on every startup — it skips already-applied migrations (tracked in
  the `__drizzle_migrations` table; configurable via `migrations.table`/`migrations.schema`).
- DO run `drizzle-kit check` in CI to catch migration collisions (race conditions) across branches.
- DO name migrations and enable `breakpoints: true` (config) so multi-statement DDL splits
  correctly for engines that can't batch (e.g. SQLite/MySQL).

## DON'T — the migration traps

- DON'T edit a migration that has already been applied anywhere (CI, staging, prod). The
  migrator hashes applied files; changing one desyncs history. To fix a bad migration, add
  a **new** migration.
- DON'T hand-edit `snapshot.json` — regenerate. Use `drizzle-kit up` only to upgrade
  snapshot format after a drizzle-kit version bump.
- DON'T run `push` against production. `push` skips SQL files and can silently drop columns
  on destructive diffs. Reserve it for local/prototyping; use generate+migrate for prod.
- DON'T mix `push` and `generate` on the same DB — you lose a coherent migration history.
- DON'T forget `dialect` + `schema` in `drizzle.config.ts` (both mandatory). Minimal:
  ```ts
  import { defineConfig } from 'drizzle-kit';
  export default defineConfig({
    dialect: 'postgresql',
    schema: './src/schema.ts',
    out: './drizzle',
    dbCredentials: { url: process.env.DATABASE_URL! },
  });
  ```

## DO — connection & pooling per driver

Match the driver import to your runtime; each `drizzle-orm/<driver>` entrypoint owns pooling.

- **Serverful Postgres** — `drizzle-orm/node-postgres` (pg `Pool`) or `drizzle-orm/postgres-js`.
  DO reuse one `Pool`/client per process; size it to your DB's max connections.
- **Serverful MySQL** — `drizzle-orm/mysql2` with a `mysql2` pool.
- DO create the pool once at module load, not per-request (see serverless caveat below).

## DO — serverless (HTTP vs WebSocket)

- **Neon HTTP** — `drizzle-orm/neon-http`. Fastest for single, non-interactive queries. No
  session/interactive transactions.
  ```ts
  import { drizzle } from 'drizzle-orm/neon-http';
  const db = drizzle(process.env.DATABASE_URL!);
  ```
- **Neon WebSocket/Pool** — `drizzle-orm/neon-serverless`. Use when you need interactive
  transactions or a `pg` drop-in. In Node (no global `WebSocket`) set
  `neonConfig.webSocketConstructor = ws` and install `ws`+`bufferutil`.
- **PlanetScale (MySQL over HTTP)** — `drizzle-orm/planetscale-serverless` +
  `@planetscale/database`. Works serverless and serverful.
  ```ts
  import { drizzle } from 'drizzle-orm/planetscale-serverless';
  const db = drizzle({ connection: {
    host: process.env.DATABASE_HOST, username: process.env.DATABASE_USERNAME,
    password: process.env.DATABASE_PASSWORD } });
  ```

## DON'T — serverless pooling traps

- DON'T open a classic TCP pool per invocation in a serverless function — connections leak
  and exhaust the DB. Prefer the HTTP driver (neon-http / planetscale-serverless) or a
  pooled endpoint (Neon pooler / PgBouncer). Reserve `Pool`/WebSocket for when you truly
  need multi-statement transactions.
- DON'T assume the HTTP drivers support interactive transactions — they don't; batch or
  restructure instead.

## SECURITY — raw SQL is the injection surface

Drizzle's query builder and the `sql` template **parameterize by default**. The escape
hatch `sql.raw()` does not.

- DO use `sql`` `` — every `${value}` becomes a bound placeholder (`$1`/`?`), values travel
  in a separate array. Table/column refs auto-escape.
  ```ts
  import { sql } from 'drizzle-orm';
  await db.execute(sql`select * from ${users} where ${users.id} = ${id}`);
  // → select * from "users" where "users"."id" = $1  -- [id]
  ```
- DO use `sql.placeholder('x')` + `.prepare()` for reused prepared statements; pass values
  at `.execute({ x })`.
- **DON'T** `sql.raw()` with user input — it interpolates unescaped, reopening SQL injection:
  ```ts
  sql.raw(`select * from users where id = ${userInput}`); // ☠️ injectable
  sql`select * from users where id = ${userInput}`;       // ✅ parameterized
  ```
- DON'T build identifiers (table/column/ORDER BY direction) from raw user strings. Map
  untrusted input through an allow-list to known `Table`/`Column` objects, never via `sql.raw`.
- DON'T string-concatenate any user value into a `sql`` `` literal — put it in `${}` so it binds.

## Sources

- https://orm.drizzle.team/docs/overview
- https://orm.drizzle.team/docs/kit-overview
- https://orm.drizzle.team/docs/migrations
- https://orm.drizzle.team/docs/sql
- https://orm.drizzle.team/docs/perf-queries
- https://orm.drizzle.team/docs/connect-neon
- https://orm.drizzle.team/docs/connect-planetscale
- context7 `/drizzle-team/drizzle-orm` (drizzle-kit_0.31.5), `/websites/orm_drizzle_team`
