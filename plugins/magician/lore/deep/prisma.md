# prisma — deep dive

> On-demand companion to `lore/prisma.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Schema & migrations](#schema-and-migrations) · [Client queries & pitfalls](#client-queries-and-pitfalls)

## Schema & migrations <a id="schema-and-migrations"></a>

JS/Node ORM (schema-first, codegen'd client). Distinct from the JVM `orm` lore. Verified vs prisma.io, current for Prisma 5/6 (2026-07). v7 diffs flagged — verify before asserting v7 specifics.

### Schema (`schema.prisma`)

DO
- Model app entities in `model` blocks; singular PascalCase names; map to snake_case DB with `@map`/`@@map` (`@@map("users")`).
- Give every model a unique identifier: `@id`/`@@id` or `@unique`/`@@unique`. Exactly one ID per model.
- Use `@default(autoincrement())` for Int PKs; `@default(uuid())`/`@default(cuid())` for string PKs; `@default(now())` + `@updatedAt` for timestamps.
- Composite key: `@@id([a, b])`; composite unique: `@@unique([authorId, title])`.
- Index hot query/filter/sort columns with `@@index([field])`. Prisma does NOT auto-index FKs on every DB — add `@@index` on relation scalars used in joins/filters.
- Use enums (`enum Role { USER ADMIN }`) where the DB supports them; `@map` renames enum values.
- Pin native column types with `@db.*` (`@db.VarChar(200)`, `@db.ObjectId`).
- Set the generator `output` path explicitly. In the new `prisma-client` generator (Rust-free) `output` is **required** and the client is no longer emitted into `node_modules`.

DON'T
- Don't combine `[]` and `?` — optional lists are unsupported.
- Don't expect `@@id` on MongoDB (not supported; single `@id @map("_id")` only).
- Don't over-index — each index costs writes.
- Don't hand-write the client; it's generated (`prisma generate`).

```prisma
model User {
  id    Int    @id @default(autoincrement())
  email String @unique
  posts Post[]
  role  Role   @default(USER)
  @@map("users")
}
```

### Relations

DO
- Declare both relation fields (they exist only at ORM level). FK is the relation *scalar* field (`authorId`), convention `field` + `Id`.
- Wire with `@relation(fields: [authorId], references: [id])` on the side holding the FK. Required for 1-1, 1-n, self-relations, disambiguation, and all MongoDB m-n.
- Disambiguate multiple relations between the same models with a matching `name` on both sides: `@relation("WrittenPosts")`.
- Prefer implicit m-n (Prisma manages the join table, cleaner API) when both models have a single `@id` and you need no extra join columns.
- Use explicit m-n (join model in schema) when you need payload columns, composite keys, or referential actions on the join.

DON'T
- Don't put referential actions on implicit m-n — use an explicit join table.
- Don't forget `@db.ObjectId` on both the model `@id` and the relation scalar for MongoDB ObjectId refs.

#### Referential actions (`onDelete`/`onUpdate`)
Values: `Cascade`, `Restrict`, `NoAction`, `SetNull` (optional relations only), `SetDefault` (needs `@default`).
Defaults: `onDelete` = `SetNull` (optional) / `Restrict` (required); `onUpdate` = `Cascade`.
- `relationMode = "foreignKeys"` (default, SQL): real DB FK constraints enforce integrity.
- `relationMode = "prisma"` (default on MongoDB; used for many serverless/edge + PlanetScale): Prisma *emulates* actions but enforces NO constraints — `NoAction` gives zero protection. Add `@@index` on relation scalars manually (no FK index created).
- DB gaps: MySQL/MongoDB lack real `SetDefault`; SQL Server lacks `Restrict` (use `NoAction`), forbids cascade cycles/multi-paths — break with explicit `NoAction`.

### Migrations

DO
- Iterate locally with `prisma migrate dev` — diffs schema (via shadow DB), creates + applies a timestamped migration, regenerates the client.
- Ship with `prisma migrate deploy` in CI/CD — applies pending migrations only. No drift detection, no shadow DB, no reset, no client generation.
- Customize a migration before it runs: `prisma migrate dev --create-only`, hand-edit the SQL, then `migrate dev` to apply.
- Recover a broken dev DB with `prisma migrate reset` (dev-only: drops, re-applies all, seeds).
- Commit the `prisma/migrations` dir (with `migration_lock.toml`) to version control.
- Run `prisma migrate status` / `prisma migrate resolve` to inspect/repair the `_prisma_migrations` ledger in prod.

DON'T
- **NEVER edit an already-applied migration.** `deploy` detects the checksum change and errors ("migrations have been modified since they were applied"). Add a new migration instead.
- Never run `migrate dev` or `migrate reset` against production — both are destructive dev commands.
- Don't rely on advisory lock behavior blindly — it has a fixed 10s timeout; on timeout just rerun (disable via `PRISMA_SCHEMA_DISABLE_ADVISORY_LOCK`, since 5.3.0).

### `db push` (prototyping ONLY)

DO — use to sync schema → DB fast during early prototyping with no migration history.
DON'T — never use `db push` in production or once you have a migration history; it creates no migration files and can silently drop data. Switch to `migrate dev` before shipping.

### generate & seeding

DO
- Run `prisma generate` after every schema change (auto-run by `migrate dev`).
- Seed via `prisma db seed`. Prisma 5/6: configure `prisma.seed` in `package.json` (`"seed": "tsx prisma/seed.ts"`); runs automatically after `migrate reset` / `migrate dev` (first apply). **Prisma 7: config moves to `prisma.config.ts` (`migrations.seed`), and automatic seeding on migrate is REMOVED — seed only runs on explicit `prisma db seed`.**
- Pass args after `--`: `prisma db seed -- --env dev`.

### Rust-free client / driver adapters / TypedSQL

- New `prisma-client` generator + `previewFeatures = ["queryCompiler", "driverAdapters"]` = Rust-free client (no query engine binary). The old `prisma-client-js` provider is deprecated and slated for removal. Verify GA status in current docs before recommending for prod.
- Driver adapters (`@prisma/adapter-pg`, `-neon`, `-libsql`, `-d1`, `-planetscale`) let the client run over a native/edge driver. In v7 `PrismaClient` MUST be constructed with an adapter.
- **TypedSQL** (`previewFeatures = ["typedSql"]`): put `.sql` files in `prisma/sql/`, run `prisma generate --sql`, import typed functions from `@prisma/client/sql`, execute with `$queryRawTyped(...)`. Fully typed inputs + results — prefer this over raw strings.

```ts
import { conversionByVariant } from '@prisma/client/sql'
const rows = await prisma.$queryRawTyped(conversionByVariant()) // typed
```

### Raw SQL — SECURITY (injection)

These libraries parameterize by default; the RAW escape hatches do NOT. Treat every raw call as an injection surface.

DO
- Use tagged-template `$queryRaw`/`$executeRaw` — variables are escaped and sent as prepared statements.
- Build dynamic-but-safe SQL with `Prisma.sql` and `Prisma.join` (e.g. `IN` lists): `Prisma.sql\`SELECT * FROM u WHERE id IN (${Prisma.join(ids)})\``.
- Prefer TypedSQL for anything nontrivial.

DON'T
- **NEVER interpolate user input into `$queryRawUnsafe` / `$executeRawUnsafe`** or into a hand-built tagged template via string concatenation — Prisma cannot escape it. Docs: "significant risk of making your code vulnerable to SQL injection." Pass values as separate `...values` args (`$1`, `$2` / `?`) instead.
- Never feed untrusted input to `Prisma.raw` — its contents are NOT escaped.
- Never use template vars for identifiers (table/column names) or keywords — values only. Dynamic identifiers force `Unsafe` + manual allow-listing.

```ts
// SAFE
await prisma.$queryRaw`SELECT * FROM "User" WHERE email = ${email}`
// DANGER — injectable
await prisma.$queryRawUnsafe(`SELECT * FROM "User" WHERE email = '${email}'`)
// SAFE Unsafe (parameterized)
await prisma.$queryRawUnsafe('SELECT * FROM "User" WHERE email = $1', email)
```

### Prisma 6 upgrade gotchas
- Node ≥ 18.18 / 20.9 / 22.11; TypeScript ≥ 5.1.
- `Bytes` fields: `Buffer` → `Uint8Array`.
- `NotFoundError` removed — `findUniqueOrThrow`/`findFirstOrThrow` now throw `PrismaClientKnownRequestError` code `P2025`.
- Reserved model names: `async`, `await`, `using`.
- Postgres implicit m-n: join-table unique index becomes a primary key — generate a dedicated migration right after upgrading.
- `fullTextSearch` GA on MySQL only; Postgres uses `fullTextSearchPostgres` preview.

### Sources
- https://www.prisma.io/docs/orm/prisma-schema/data-model/models
- https://www.prisma.io/docs/orm/prisma-schema/data-model/relations
- https://www.prisma.io/docs/orm/prisma-schema/data-model/relations/referential-actions
- https://www.prisma.io/docs/orm/prisma-migrate/workflows/development-and-production
- https://www.prisma.io/docs/orm/prisma-migrate/workflows/seeding
- https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries
- https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/typedsql
- https://www.prisma.io/docs/orm/more/upgrade-guides/upgrading-versions/upgrading-to-prisma-6
- https://www.prisma.io/docs/guides/upgrade-prisma-orm/v7

## Client queries & pitfalls <a id="client-queries-and-pitfalls"></a>

JS/Node ORM (TypeScript-first). Distinct from the JVM `orm` lore; assumes JS/TS/Node lore
exists separately. Verified vs prisma.io + Prisma 6.19 / 7.x (Jul 2026).

**Version map.** Prisma 5 & 6: engine-based, pool via connection-string params. **Prisma 7**
(latest, 7.6.x): **driver adapters default** for relational DBs — the JS driver owns pool + TLS,
so URL params like `connection_limit` **silently stop applying**. State major version first.

---

### Type-safe queries (findMany / where / select / include)

DO
- Let the generated client type results — `select`/`include` narrow the return type, no manual generics.
- `select` only needed columns (smaller rows). `where` operators: `equals`, `in`, `contains`, `gt/gte/lt/lte`, `AND/OR/NOT`, `mode:"insensitive"`.
```ts
const users = await prisma.user.findMany({
  where: { email: { endsWith: "@acme.io" }, active: true },
  select: { id: true, email: true, posts: { select: { title: true } } },
  orderBy: { createdAt: "desc" },
});
```

DON'T
- Don't put `include` **and** `select` at the **same level** — runtime error. Trim both via nested `select`.
- Don't `findMany()` then filter/map in JS what `where`/`select` does in SQL.
- Don't assume a relation is loaded — it's `undefined` unless `include`/`select`ed (TS enforces this).

---

### Relations & the N+1 (include / relationLoadStrategy)

DO
- Load relations eagerly in one call via `include` / nested `select` — the fix for N+1.
```ts
const users = await prisma.user.findMany({ include: { posts: true } }); // one logical read
```
- Filter/sort/paginate **inside** a relation instead of a second round-trip:
```ts
select: { posts: { where: { published: true }, orderBy: { title: "asc" }, take: 5 } }
```
- Count relations with `_count` (Prisma ≥ 3.0.1): `include: { _count: { select: { posts: true } } }`.
- Tune load strategy with `relationLoadStrategy` (Preview `relationJoins`; PostgreSQL, CockroachDB, MySQL):
  - `"join"` (default when enabled) → single query, LATERAL JOIN (PG) / correlated subquery (MySQL) + JSON aggregation.
  - `"query"` → one query per table, merged app-side (easier to scale; profile both).
```ts
generator client { previewFeatures = ["relationJoins"] } // then `prisma generate`
await prisma.user.findMany({ relationLoadStrategy: "join", include: { posts: true } });
```

DON'T
- Don't loop `findUnique` per parent. Beware the **Fluent API** (`prisma.user.findUnique(...).posts()`) — emits **two** queries; the `include` equivalent emits one.
- Don't over-`include` trees you don't render — you pay for every joined row.

---

### Transactions ($transaction)

Three tools: **nested writes** (dependent), **batch array** (independent), **interactive** (read-modify-write).

DO
- Nested writes for related creates — atomic, and they can pass generated IDs:
```ts
await prisma.user.create({ data: { email: "a@x.io", posts: { create: [{ title: "P1" }] } } });
```
- Batch array for independent ops (sequential, atomic):
```ts
const [rows, total] = await prisma.$transaction([prisma.post.findMany(), prisma.post.count()]);
```
- Interactive for logic between reads/writes — commit on return, rollback on throw. Use the `tx` client, not `prisma`:
```ts
await prisma.$transaction(async (tx) => {
  const a = await tx.account.update({ where: { id }, data: { balance: { decrement: 100 } } });
  if (a.balance < 0) throw new Error("insufficient");        // auto-rollback
  await tx.account.update({ where: { id: to }, data: { balance: { increment: 100 } } });
}, { maxWait: 5000, timeout: 10000, isolationLevel: Prisma.TransactionIsolationLevel.Serializable });
```
- Options: `maxWait` (acquire, default 2000ms), `timeout` (run, default 5000ms), `isolationLevel`. Under `Serializable`, retry on write-conflict/deadlock error **P2034**.

DON'T
- Don't call `prisma.*` inside an interactive callback — use `tx.*` or ops escape the tx.
- Don't do network/HTTP inside a tx — keep it short (holds a pooled connection; deadlock risk).
- Batch array can't pass an ID from op 1 to op 2 — use nested writes.
- `updateMany`/`deleteMany` don't support nested writes. MongoDB has no isolation levels.

---

### Pagination (prefer cursor)

DO — cursor (stable, scalable feeds/timelines):
```ts
const page = await prisma.post.findMany({
  take: 10, skip: 1, cursor: { id: lastId }, orderBy: { id: "asc" }, // orderBy REQUIRED
});
```
- First page: omit `cursor`/`skip`; carry the last row's id forward. Guard empty results.

DON'T
- Don't deep-offset large tables — `skip: N` (offset) cost grows with N. Offset only for small sets / jump-to-page UIs.
- Don't cursor without a **stable, unique** `orderBy` — ties skip/duplicate rows.

---

### Connection pool & serverless

DO
- **Prisma 5/6 (engine):** size via URL `?connection_limit=5&pool_timeout=10`. Default size `physical_cpus*2+1`; `pool_timeout` 10s, `connect_timeout` 5s.
- **Prisma 7 (adapter):** configure the pool on the **adapter**, not the URL (`connection_limit` ignored):
```ts
import { PrismaPg } from "@prisma/adapter-pg";
const adapter = new PrismaPg({ connectionString, // from app config, never a literal
  connectionTimeoutMillis: 5000, idleTimeoutMillis: 300000 }); // pg pool `max` default 10
export const prisma = new PrismaClient({ adapter });
```
- **Serverless/edge:** one `PrismaClient` per module (singleton; stash on `globalThis` in dev for hot-reload). Front the DB with a transaction-mode pooler (**PgBouncer** `?pgbouncer=true`; Neon `-pooler`) or **Prisma Accelerate** (managed pool + edge cache; `@prisma/extension-accelerate`). With PgBouncer, don't cache prepared statements (pg adapter: leave `statementNameGenerator` unset).

DON'T
- Don't `new PrismaClient()` per request/handler in serverless — exhausts DB connections.
- Don't carry v6 `connection_limit` URL params into v7 — symptom: pool exhaustion under load after upgrade.
- Don't exceed the database's own max connections across all instances.

---

### Raw SQL — SECURITY (non-negotiable)

Prisma parameterizes by default; **raw is the injection surface.**

DO
- Use the **tagged-template** `$queryRaw` / `$executeRaw` — variables become **prepared-statement** params, auto-escaped:
```ts
const email = req.query.email;
await prisma.$queryRaw`SELECT id, name FROM "User" WHERE email = ${email}`; // SAFE
```
- Compose safely: `Prisma.sql\`...\``, `Prisma.join(ids)` for `IN (...)`, `Prisma.empty` for conditional clauses.
```ts
await prisma.$queryRaw`SELECT * FROM "User" WHERE id IN (${Prisma.join(ids)})`;
```
- Cast explicitly (no implicit casts): `SELECT LENGTH(${n}::text)`. Type results: `$queryRaw<User[]>\`...\`` (else `unknown`).

DON'T
- **NEVER** interpolate user input into `$queryRawUnsafe` / `$executeRawUnsafe` — raw strings = SQL injection.
```ts
prisma.$queryRawUnsafe(`SELECT * FROM "User" WHERE name = '${name}'`); // ❌ INJECTION
```
- Don't `"..." + input` then pass to a raw method — concat defeats all protection.
- Don't wrap untrusted input in `Prisma.raw()` — **not** escaped; trusted query text only.
- Tagged-template vars are **data only** — not identifiers/table/column/keywords. Dynamic identifier? Allow-list it, never pass user text.
- If forced onto `$queryRawUnsafe`, use positional params (`$1`,`$2` PG / `?` MySQL) as extra args — never inline.

---

### Sources
- https://www.prisma.io/docs/orm/prisma-client/queries/relation-queries
- https://www.prisma.io/docs/orm/prisma-client/queries/transactions
- https://www.prisma.io/docs/orm/prisma-client/queries/pagination
- https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries
- https://www.prisma.io/docs/orm/prisma-client/setup-and-configuration/databases-connections/connection-pool
- https://github.com/prisma/prisma (v6.19 / v7.x driver-adapter defaults, context7)
- https://github.com/blakeembrey/sql-template-tag (Prisma.sql / join / raw)
