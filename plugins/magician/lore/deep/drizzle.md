# drizzle — deep dive

> On-demand companion to `lore/drizzle.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Schema & queries](#schema-and-queries) · [Migrations & pitfalls](#migrations-and-pitfalls)

## Schema & queries <a id="schema-and-queries"></a>

JS/Node ORM. Distinct from the JVM `orm` lore. Assumes TS/Node lore exists separately.

**Version facts (verified 2026-07-11).** Stable `drizzle-orm@0.45.2`, `drizzle-kit@0.31.10` (`npm dist-tag: latest`). `v1.0` is in **beta/rc** (`1.0.0-rc.4`, `beta` tag = `1.0.0-beta.22`) — not GA. Fast-moving; re-verify before quoting API. The big v1.0 change is **Relational Queries v2 (RQB v2)**: `defineRelations` + `drizzle({ relations })` replaces the stable `relations()` + `drizzle({ schema })`. This doc targets **stable 0.45** (RQB v1) and flags v1 (RQB v2) deltas inline.

Drizzle = thin, typesafe, headless. "If you know SQL, you know Drizzle." Always emits exactly one SQL query per call.

### Schema: DO

- Pick the dialect builder: `pgTable` / `mysqlTable` / `sqliteTable` from `drizzle-orm/{pg,mysql,sqlite}-core`.
- Define once in TS; it's the source of truth. `drizzle-kit generate` → migrations, `drizzle-kit push` → dev sync.
```ts
import { pgTable, serial, text, integer, timestamp } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial().primaryKey(),
  name: text().notNull(),
  email: text().notNull().unique(),
  createdAt: timestamp().defaultNow(),
});
export const posts = pgTable('posts', {
  id: serial().primaryKey(),
  content: text().notNull(),
  authorId: integer().notNull().references(() => users.id),
});
```
- Column key = TS name; DB name comes from the string arg or is derived. Omit the string arg and set `casing: 'snake_case'` on `drizzle()` to auto-map camelCase → snake_case.
- Infer row types from the table — never hand-write them:
```ts
type User = typeof users.$inferSelect;   // row returned by SELECT
type NewUser = typeof users.$inferInsert; // shape accepted by INSERT
// equivalent generics: InferSelectModel<typeof users> / InferInsertModel<typeof users> from 'drizzle-orm'
```

### Schema: DON'T

- DON'T mix dialects in one schema — a `pgTable` won't run on a MySQL driver.
- DON'T hand-write `interface User {...}`; it drifts from the schema. Use `$inferSelect`/`$inferInsert`.
- DON'T rely on `push` for prod. `push` is dev-only; ship versioned migrations (`generate` + `migrate`).

### Two query APIs

Drizzle ships **both**. Choose per call.

#### 1. SQL-like builder (`db.select`) — DO

Mirrors SQL; explicit joins; you shape the result.
```ts
import { eq, and, desc, sql } from 'drizzle-orm';

await db.select().from(users).where(eq(users.id, 10));

await db.select({ id: users.id, post: posts.content })
  .from(users)
  .leftJoin(posts, eq(posts.authorId, users.id))
  .where(and(eq(users.id, 10), eq(posts.id, 1)))
  .orderBy(desc(users.createdAt))
  .limit(20);
```
- Joins: `innerJoin` / `leftJoin` / `rightJoin` / `fullJoin`. Result of a join = `{ users: {...}, posts: {...} | null }` — flat, one row per join row. You dedupe/nest manually.
- `insert`/`update`/`delete`: `db.insert(users).values({...}).returning()`, `db.update(users).set({...}).where(...)`, `db.delete(users).where(...)`. `returning()` is PG/SQLite; MySQL has no `RETURNING`.

#### 2. Relational queries (`db.query`, RQB) — DO

Nested typed results, no manual joins/mapping, still one SQL statement. Opt-in: declare relations and pass them at init.

**Stable 0.45 (RQB v1):**
```ts
import { relations } from 'drizzle-orm';
export const usersRelations = relations(users, ({ many }) => ({ posts: many(posts) }));
export const postsRelations = relations(posts, ({ one }) => ({
  author: one(users, { fields: [posts.authorId], references: [users.id] }),
}));

import * as schema from './schema';
const db = drizzle(client, { schema });   // relations live in schema

const result = await db.query.users.findMany({
  with: { posts: true },                        // nest relation; nest deeper with { posts: { with: {...} } }
  columns: { id: true, name: true },            // partial select (false=omit; true+false mixed → false ignored)
  where: (u, { eq }) => eq(u.id, 10),           // v1: callback (fields, operators) => condition
  orderBy: (u, { desc }) => [desc(u.createdAt)],
  limit: 20,
});
// findFirst() adds LIMIT 1
```

**v1.0 beta/rc (RQB v2) — delta:** use `defineRelations(schema, (r) => ({...}))` with `r.one`/`r.many` + `from`/`to` (many-to-many via `.through()`), pass `drizzle(url, { relations })`. `where`/`orderBy` become **object syntax** (`where: { id: 10 }`, `orderBy: { id: 'asc' }`); callback form only where a column ref is needed (`orderBy: (t) => sql\`${t.id} asc\``). Aggregations not allowed in `extras` — use core queries.

#### DON'T

- DON'T reach for `db.select` joins when you want a nested object graph — use RQB.
- DON'T assume `db.query` exists without wiring relations into `drizzle(...)`; it's silently empty otherwise.
- DON'T expect RQB to do arbitrary aggregation — that's core-query territory.

### Prepared statements — DO

Precompile once, run many; pass values via placeholders (also the parameterization path).
```ts
import { sql } from 'drizzle-orm';

const q = db.select().from(users)
  .where(eq(users.id, sql.placeholder('id')))
  .prepare('get_user');            // PG requires a unique name; MySQL/SQLite name optional
const u = await q.execute({ id: 10 });

// RQB
const p = db.query.users.findMany({ limit: sql.placeholder('l') }).prepare('list');
await p.execute({ l: 5 });
```
- SQLite driver: `.all()` / `.get()` / `.run()` instead of / alongside `.execute()`.

### SECURITY — raw SQL is the injection surface

Builder + placeholders parameterize automatically. The **`sql`** template tag is the escape hatch — misuse = SQLi.

**DO** — interpolate values through the tag (they become bound params):
```ts
const email = req.query.email;
await db.select().from(users).where(sql`${users.email} = ${email}`); // $1 bind — safe
await db.execute(sql`select * from users where id = ${sql.placeholder('id')}`);
```

**DON'T** — never build a `sql` string from user input:
```ts
sql.raw(`select * from users where email = '${email}'`);        // ⛔ raw = no escaping, SQLi
db.execute(sql.raw('... ' + userInput));                        // ⛔
sql`select * from ${sql.raw(userColumn)}`;                      // ⛔ identifier injection
```
Rules: values → `${value}` inside `sql\`\`` (bound) or `sql.placeholder`. `sql.raw()` / `sql.identifier()` embed **literally with zero escaping** — never pass user input to them; restrict identifiers to a server-side allow-list. Never string-concatenate into a query.

### Sources

- https://orm.drizzle.team/docs/overview
- https://orm.drizzle.team/docs/sql-schema-declaration
- https://orm.drizzle.team/docs/rqb
- https://orm.drizzle.team/docs/goodies
- https://orm.drizzle.team/docs/migrate/migrate-from-prisma
- https://www.npmjs.com/package/drizzle-orm (dist-tags: latest 0.45.2, beta 1.0.0-beta.22, rc 1.0.0-rc.4)
- https://www.npmjs.com/package/drizzle-kit (0.31.10)
- context7 `/websites/orm_drizzle_team`, `/websites/rqbv2_drizzle-orm-fe_pages_dev`

## Migrations & pitfalls <a id="migrations-and-pitfalls"></a>

JS/Node ORM (TypeScript-first). Distinct from the JVM `orm` lore. Fast-moving 0.3x
line — guidance dated **mid-2026: drizzle-orm 0.3x, drizzle-kit ~0.31.x**. Re-verify
API against orm.drizzle.team before asserting; a v1.0 Beta exists but 0.3x is current stable.

Schema is TypeScript (`pgTable`/`mysqlTable`/`sqliteTable`). `drizzle-kit` diffs schema
→ SQL. Two philosophies: **codebase-first** (TS schema is truth → apply to DB) and
**database-first** (`pull`/introspect DB → TS). Pick one direction per project.

### Two migration flows

- **generate + migrate** — versioned SQL files, tracked in DB. Use for production / teams / CI.
- **push** — diff TS schema straight to DB, no SQL files. Use for prototyping / local iteration.

`drizzle-kit` commands (run via `npx drizzle-kit <cmd>`, config in `drizzle.config.ts`):
`generate` · `migrate` · `push` · `pull` · `check` · `up` · `export` · `studio`.

### DO — generate/migrate as source of truth

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

### DON'T — the migration traps

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

### DO — connection & pooling per driver

Match the driver import to your runtime; each `drizzle-orm/<driver>` entrypoint owns pooling.

- **Serverful Postgres** — `drizzle-orm/node-postgres` (pg `Pool`) or `drizzle-orm/postgres-js`.
  DO reuse one `Pool`/client per process; size it to your DB's max connections.
- **Serverful MySQL** — `drizzle-orm/mysql2` with a `mysql2` pool.
- DO create the pool once at module load, not per-request (see serverless caveat below).

### DO — serverless (HTTP vs WebSocket)

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

### DON'T — serverless pooling traps

- DON'T open a classic TCP pool per invocation in a serverless function — connections leak
  and exhaust the DB. Prefer the HTTP driver (neon-http / planetscale-serverless) or a
  pooled endpoint (Neon pooler / PgBouncer). Reserve `Pool`/WebSocket for when you truly
  need multi-statement transactions.
- DON'T assume the HTTP drivers support interactive transactions — they don't; batch or
  restructure instead.

### SECURITY — raw SQL is the injection surface

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

### Sources

- https://orm.drizzle.team/docs/overview
- https://orm.drizzle.team/docs/kit-overview
- https://orm.drizzle.team/docs/migrations
- https://orm.drizzle.team/docs/sql
- https://orm.drizzle.team/docs/perf-queries
- https://orm.drizzle.team/docs/connect-neon
- https://orm.drizzle.team/docs/connect-planetscale
- context7 `/drizzle-team/drizzle-orm` (drizzle-kit_0.31.5), `/websites/orm_drizzle_team`
