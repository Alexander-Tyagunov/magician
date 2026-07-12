# prisma — Client queries & pitfalls

JS/Node ORM (TypeScript-first). Distinct from the JVM `orm` lore; assumes JS/TS/Node lore
exists separately. Verified vs prisma.io + Prisma 6.19 / 7.x (Jul 2026).

**Version map.** Prisma 5 & 6: engine-based, pool via connection-string params. **Prisma 7**
(latest, 7.6.x): **driver adapters default** for relational DBs — the JS driver owns pool + TLS,
so URL params like `connection_limit` **silently stop applying**. State major version first.

---

## Type-safe queries (findMany / where / select / include)

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

## Relations & the N+1 (include / relationLoadStrategy)

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

## Transactions ($transaction)

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

## Pagination (prefer cursor)

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

## Connection pool & serverless

DO
- **Prisma 5/6 (engine):** size via URL `?connection_limit=5&pool_timeout=10`. Default size `physical_cpus*2+1`; `pool_timeout` 10s, `connect_timeout` 5s.
- **Prisma 7 (adapter):** configure the pool on the **adapter**, not the URL (`connection_limit` ignored):
```ts
import { PrismaPg } from "@prisma/adapter-pg";
const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL,
  connectionTimeoutMillis: 5000, idleTimeoutMillis: 300000 }); // pg pool `max` default 10
export const prisma = new PrismaClient({ adapter });
```
- **Serverless/edge:** one `PrismaClient` per module (singleton; stash on `globalThis` in dev for hot-reload). Front the DB with a transaction-mode pooler (**PgBouncer** `?pgbouncer=true`; Neon `-pooler`) or **Prisma Accelerate** (managed pool + edge cache; `@prisma/extension-accelerate`). With PgBouncer, don't cache prepared statements (pg adapter: leave `statementNameGenerator` unset).

DON'T
- Don't `new PrismaClient()` per request/handler in serverless — exhausts DB connections.
- Don't carry v6 `connection_limit` URL params into v7 — symptom: pool exhaustion under load after upgrade.
- Don't exceed the database's own max connections across all instances.

---

## Raw SQL — SECURITY (non-negotiable)

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

## Sources
- https://www.prisma.io/docs/orm/prisma-client/queries/relation-queries
- https://www.prisma.io/docs/orm/prisma-client/queries/transactions
- https://www.prisma.io/docs/orm/prisma-client/queries/pagination
- https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries
- https://www.prisma.io/docs/orm/prisma-client/setup-and-configuration/databases-connections/connection-pool
- https://github.com/prisma/prisma (v6.19 / v7.x driver-adapter defaults, context7)
- https://github.com/blakeembrey/sql-template-tag (Prisma.sql / join / raw)
