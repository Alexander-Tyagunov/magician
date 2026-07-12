# kysely — Type-safe query builder

JS/Node lore (distinct from the JVM `orm` lore). Assumes TS/Node lore lives elsewhere.

Kysely is a **type-safe SQL query builder** (Knex-inspired), **NOT an ORM**: no entities,
no change-tracking, no lazy relations, no unit-of-work. You write SQL-shaped queries; TS
infers exact result types from your DB interface. Zero runtime overhead over the driver.

**Version:** current stable **0.29.3** (2026-07-05); `next` = 0.29.0-rc.0. The 0.27/0.28
line is prior. Requires **TypeScript ≥ 5.4** (5.9+ recommended) with `strict` mode ON —
without `strict`, type inference silently degrades. Runs on Node, Deno, Bun.

## DB interface types

The `Database` interface maps table name → table interface. Hand-write it, or generate it.

```typescript
import { ColumnType, Generated, GeneratedAlways, Insertable, Selectable, Updateable, JSONColumnType } from 'kysely'

interface PersonTable {
  id: Generated<number>                         // DB-generated; optional on insert
  created_at: GeneratedAlways<Date>             // never insertable/updatable
  first_name: string
  last_name: string | null                      // nullable column
  metadata: JSONColumnType<{ tags: string[] }>  // = ColumnType<T, string, string>
  updated_at: ColumnType<Date, string | undefined, string> // <Select, Insert, Update>
}
export interface Database { person: PersonTable }
export type Person = Selectable<PersonTable>     // result type
export type NewPerson = Insertable<PersonTable>  // insert type
export type PersonUpdate = Updateable<PersonTable>
```

- **DO** use nullable *types* (`string | null`), never optional *properties* (`?`) —
  Kysely decides optionality from `Generated`/`ColumnType`.
- **DO** use `Selectable/Insertable/Updateable<T>` as your app-facing types.
- **DON'T** use the raw table interface as a query result type — the docs forbid it.
- **`Generated<T>`** = DB fills it (optional on insert). **`GeneratedAlways<T>`** = you can
  never write it. **`ColumnType<S,I,U>`** = distinct select/insert/update types (`never` to forbid).

### Generating types (kysely-codegen)
```bash
npm i -D kysely-codegen
DATABASE_URL=postgres://user:pw@host/db npx kysely-codegen \
  --dialect postgres --out-file ./src/db/db.d.ts --camel-case
```
`--url` defaults to `env(DATABASE_URL)`; dialects: `postgres|mysql|sqlite|mssql|libsql|bun-sqlite`.
Config via `.kysely-codegenrc.json`. **DO** regenerate on every migration; stale types = false safety.

## Instantiate + dialects/pooling

```typescript
import { Kysely, PostgresDialect } from 'kysely'
import { Pool } from 'pg'
export const db = new Kysely<Database>({
  dialect: new PostgresDialect({ pool: new Pool({ /* host, database, max: 10 */ }) }),
})
```
Built-in dialects + drivers: **PostgresDialect** (`pg`), **MysqlDialect** (`mysql2`),
**MssqlDialect** (`tedious` + `tarn`), **SqliteDialect** (`better-sqlite3`), **PgliteDialect**
(`@electric-sql/pglite`). Pooling is the **driver's** job (pass a configured `Pool`).

- **DO** create **one** `Kysely` instance per DB (singleton); call `db.destroy()` on shutdown.
- **DON'T** `new Kysely` per request — you leak/exhaust pools.

## CRUD (queries are immutable — reassign when chaining conditionally)

```typescript
// SELECT
await db.selectFrom('person').selectAll().where('id', '=', id).executeTakeFirst()
await db.selectFrom('person').select(['id', 'first_name']).where('age', '>', 18).execute()
// INSERT (returning* is Postgres/SQLite; MySQL/MSSQL differ)
await db.insertInto('person').values(newPerson).returningAll().executeTakeFirstOrThrow()
// UPDATE
await db.updateTable('person').set({ last_name: 'X' }).where('id', '=', id).execute()
// DELETE
await db.deleteFrom('person').where('id', '=', id).execute()
```
- `execute()` → rows[]; `executeTakeFirst()` → row | undefined; `executeTakeFirstOrThrow()` → row | throws.
- **DON'T** write `q.where(...)` and drop the result — builders are immutable.
  Conditional build: `let q = db.selectFrom(...); if (cond) q = q.where(...)`.

## Joins

```typescript
await db.selectFrom('person')
  .innerJoin('pet', 'pet.owner_id', 'person.id')   // select() must come AFTER join
  .select(['person.id', 'pet.name as pet_name'])
  .execute()
```
`innerJoin | leftJoin | rightJoin | fullJoin`. `left/right/full` make the joined side's
columns **nullable** in the result type — TS forces you to handle `null`. CTEs via `.with('name', db => ...)`.

## Transactions

Prefer the **callback** form — auto-commit on resolve, auto-rollback on throw:
```typescript
await db.transaction().execute(async (trx) => {
  const p = await trx.insertInto('person').values(person).returning('id').executeTakeFirstOrThrow()
  await trx.insertInto('pet').values({ owner_id: p.id, name: 'Catto' }).execute()
})
// isolation: db.transaction().setIsolationLevel('serializable').execute(async trx => {...})
```
Manual/controlled form (`db.startTransaction().execute()` → `trx.commit()/rollback()`) exists
for cross-scope control — you own commit/rollback in try/catch.
- **DO** use `trx` for every statement inside; using `db` escapes the transaction.

## SECURITY — raw `sql` escape hatch

Ordinary values are **always parameterized** — `.where('id','=',userId)` is safe.
The `sql` template tag is safe **for values**: `${x}` becomes a bound parameter, never string-spliced.
```typescript
import { sql } from 'kysely'
sql<string>`concat(${ref('first_name')}, ' ', ${ref('last_name')})`  // safe
```

**Safe (parameterized):** `` sql`${value}` ``, `sql.val(value)`, `sql.join(array)`.
**DANGEROUS — splice raw string into SQL (injection if fed user input):**
`sql.raw(str)`, `sql.lit(value)`, `sql.ref(col)`, `sql.table(t)`, `sql.id(...ids)`.

Docs, verbatim, on `sql.raw` and `sql.lit`:
> "WARNING! Using this with unchecked inputs WILL lead to SQL injection vulnerabilities."

- **DON'T** interpolate user input into `sql.raw`/`sql.lit`/`sql.ref`/`sql.table`/`sql.id`. Ever.
- **DO** pass values as normal `${}` substitutions (parameters) — not `sql.lit`.
- **DO** whitelist identifiers if dynamic columns/tables are unavoidable: map user input
  to a fixed allow-list of literals, then pass the vetted constant to `sql.ref`/`sql.id`.
- **DON'T** build column/order-by names by string concat; validate against a known set first.

## Sources

- https://kysely.dev/docs/intro
- https://kysely.dev/docs/getting-started
- https://kysely.dev/docs/transactions
- https://kysely.dev/docs/recipes/raw-sql
- https://kysely.dev/docs/recipes/reusable-helpers
- https://kysely.dev/docs/examples/join/simple-inner-join
- https://kysely.dev/docs/examples/transactions/controlled-transaction
- https://kysely-org.github.io/kysely-apidoc/interfaces/Sql.html
- https://github.com/RobinBlomberg/kysely-codegen
- npm registry: `kysely@0.29.3` (dist-tags latest, 2026-07-05)
