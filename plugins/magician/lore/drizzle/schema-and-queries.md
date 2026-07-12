# drizzle — Schema & queries

JS/Node ORM. Distinct from the JVM `orm` lore. Assumes TS/Node lore exists separately.

**Version facts (verified 2026-07-11).** Stable `drizzle-orm@0.45.2`, `drizzle-kit@0.31.10` (`npm dist-tag: latest`). `v1.0` is in **beta/rc** (`1.0.0-rc.4`, `beta` tag = `1.0.0-beta.22`) — not GA. Fast-moving; re-verify before quoting API. The big v1.0 change is **Relational Queries v2 (RQB v2)**: `defineRelations` + `drizzle({ relations })` replaces the stable `relations()` + `drizzle({ schema })`. This doc targets **stable 0.45** (RQB v1) and flags v1 (RQB v2) deltas inline.

Drizzle = thin, typesafe, headless. "If you know SQL, you know Drizzle." Always emits exactly one SQL query per call.

## Schema: DO

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

## Schema: DON'T

- DON'T mix dialects in one schema — a `pgTable` won't run on a MySQL driver.
- DON'T hand-write `interface User {...}`; it drifts from the schema. Use `$inferSelect`/`$inferInsert`.
- DON'T rely on `push` for prod. `push` is dev-only; ship versioned migrations (`generate` + `migrate`).

## Two query APIs

Drizzle ships **both**. Choose per call.

### 1. SQL-like builder (`db.select`) — DO

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

### 2. Relational queries (`db.query`, RQB) — DO

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

### DON'T

- DON'T reach for `db.select` joins when you want a nested object graph — use RQB.
- DON'T assume `db.query` exists without wiring relations into `drizzle(...)`; it's silently empty otherwise.
- DON'T expect RQB to do arbitrary aggregation — that's core-query territory.

## Prepared statements — DO

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

## SECURITY — raw SQL is the injection surface

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

## Sources

- https://orm.drizzle.team/docs/overview
- https://orm.drizzle.team/docs/sql-schema-declaration
- https://orm.drizzle.team/docs/rqb
- https://orm.drizzle.team/docs/goodies
- https://orm.drizzle.team/docs/migrate/migrate-from-prisma
- https://www.npmjs.com/package/drizzle-orm (dist-tags: latest 0.45.2, beta 1.0.0-beta.22, rc 1.0.0-rc.4)
- https://www.npmjs.com/package/drizzle-kit (0.31.10)
- context7 `/websites/orm_drizzle_team`, `/websites/rqbv2_drizzle-orm-fe_pages_dev`
