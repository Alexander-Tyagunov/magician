# prisma — Schema & migrations

JS/Node ORM (schema-first, codegen'd client). Distinct from the JVM `orm` lore. Verified vs prisma.io, current for Prisma 5/6 (2026-07). v7 diffs flagged — verify before asserting v7 specifics.

## Schema (`schema.prisma`)

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

## Relations

DO
- Declare both relation fields (they exist only at ORM level). FK is the relation *scalar* field (`authorId`), convention `field` + `Id`.
- Wire with `@relation(fields: [authorId], references: [id])` on the side holding the FK. Required for 1-1, 1-n, self-relations, disambiguation, and all MongoDB m-n.
- Disambiguate multiple relations between the same models with a matching `name` on both sides: `@relation("WrittenPosts")`.
- Prefer implicit m-n (Prisma manages the join table, cleaner API) when both models have a single `@id` and you need no extra join columns.
- Use explicit m-n (join model in schema) when you need payload columns, composite keys, or referential actions on the join.

DON'T
- Don't put referential actions on implicit m-n — use an explicit join table.
- Don't forget `@db.ObjectId` on both the model `@id` and the relation scalar for MongoDB ObjectId refs.

### Referential actions (`onDelete`/`onUpdate`)
Values: `Cascade`, `Restrict`, `NoAction`, `SetNull` (optional relations only), `SetDefault` (needs `@default`).
Defaults: `onDelete` = `SetNull` (optional) / `Restrict` (required); `onUpdate` = `Cascade`.
- `relationMode = "foreignKeys"` (default, SQL): real DB FK constraints enforce integrity.
- `relationMode = "prisma"` (default on MongoDB; used for many serverless/edge + PlanetScale): Prisma *emulates* actions but enforces NO constraints — `NoAction` gives zero protection. Add `@@index` on relation scalars manually (no FK index created).
- DB gaps: MySQL/MongoDB lack real `SetDefault`; SQL Server lacks `Restrict` (use `NoAction`), forbids cascade cycles/multi-paths — break with explicit `NoAction`.

## Migrations

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

## `db push` (prototyping ONLY)

DO — use to sync schema → DB fast during early prototyping with no migration history.
DON'T — never use `db push` in production or once you have a migration history; it creates no migration files and can silently drop data. Switch to `migrate dev` before shipping.

## generate & seeding

DO
- Run `prisma generate` after every schema change (auto-run by `migrate dev`).
- Seed via `prisma db seed`. Prisma 5/6: configure `prisma.seed` in `package.json` (`"seed": "tsx prisma/seed.ts"`); runs automatically after `migrate reset` / `migrate dev` (first apply). **Prisma 7: config moves to `prisma.config.ts` (`migrations.seed`), and automatic seeding on migrate is REMOVED — seed only runs on explicit `prisma db seed`.**
- Pass args after `--`: `prisma db seed -- --env dev`.

## Rust-free client / driver adapters / TypedSQL

- New `prisma-client` generator + `previewFeatures = ["queryCompiler", "driverAdapters"]` = Rust-free client (no query engine binary). The old `prisma-client-js` provider is deprecated and slated for removal. Verify GA status in current docs before recommending for prod.
- Driver adapters (`@prisma/adapter-pg`, `-neon`, `-libsql`, `-d1`, `-planetscale`) let the client run over a native/edge driver. In v7 `PrismaClient` MUST be constructed with an adapter.
- **TypedSQL** (`previewFeatures = ["typedSql"]`): put `.sql` files in `prisma/sql/`, run `prisma generate --sql`, import typed functions from `@prisma/client/sql`, execute with `$queryRawTyped(...)`. Fully typed inputs + results — prefer this over raw strings.

```ts
import { conversionByVariant } from '@prisma/client/sql'
const rows = await prisma.$queryRawTyped(conversionByVariant()) // typed
```

## Raw SQL — SECURITY (injection)

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

## Prisma 6 upgrade gotchas
- Node ≥ 18.18 / 20.9 / 22.11; TypeScript ≥ 5.1.
- `Bytes` fields: `Buffer` → `Uint8Array`.
- `NotFoundError` removed — `findUniqueOrThrow`/`findFirstOrThrow` now throw `PrismaClientKnownRequestError` code `P2025`.
- Reserved model names: `async`, `await`, `using`.
- Postgres implicit m-n: join-table unique index becomes a primary key — generate a dedicated migration right after upgrading.
- `fullTextSearch` GA on MySQL only; Postgres uses `fullTextSearchPostgres` preview.

## Sources
- https://www.prisma.io/docs/orm/prisma-schema/data-model/models
- https://www.prisma.io/docs/orm/prisma-schema/data-model/relations
- https://www.prisma.io/docs/orm/prisma-schema/data-model/relations/referential-actions
- https://www.prisma.io/docs/orm/prisma-migrate/workflows/development-and-production
- https://www.prisma.io/docs/orm/prisma-migrate/workflows/seeding
- https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries
- https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/typedsql
- https://www.prisma.io/docs/orm/more/upgrade-guides/upgrading-versions/upgrading-to-prisma-6
- https://www.prisma.io/docs/guides/upgrade-prisma-orm/v7
