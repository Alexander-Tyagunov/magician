# typeorm — deep dive

> On-demand companion to `lore/typeorm.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Entities & repositories](#entities-and-repositories) · [Migrations & pitfalls](#migrations-and-pitfalls)

## Entities & repositories <a id="entities-and-repositories"></a>

JS/Node ORM (TypeScript-first, decorator-based). Distinct from the JVM `orm` lore — no
JPA/Hibernate here. Assumes JS/TS/Node lore exists separately.

**Version reality (verify against typeorm.io):**
- **1.0.0** is current (latest release May 2026). It **removed** the deprecated
  `Connection` / `ConnectionOptions` — `DataSource` is now the only API.
- **0.3.x** (last 0.3.30) is legacy: introduced `DataSource`, kept `Connection` as
  deprecated, changed `findOne` to require an options object, added `*By` finders.
- **0.2.x** used `Connection` + `createConnection()`.
- Docs: current at `typeorm.io`; legacy 0.3 at `v0.typeorm.io`.

Requires `import "reflect-metadata"` at startup + `emitDecoratorMetadata`/
`experimentalDecorators` in tsconfig.

### DataSource (connection lifecycle)

DO — one DataSource, `initialize()` once at boot, reuse it.
```ts
import "reflect-metadata"
import { DataSource } from "typeorm"

export const AppDataSource = new DataSource({
  type: "postgres", host: "localhost", port: 5432,
  username: "root", password: "admin", database: "app",
  entities: [User, Photo],
  synchronize: false,   // see below
})
await AppDataSource.initialize()
```

- DON'T use `createConnection()` / `getConnection()` / `new Connection()` — 0.2 API,
  deprecated in 0.3, **removed in 1.0**. Migrate string configs from `ormconfig` to a
  `DataSource` object.
- DON'T set `synchronize: true` in production — it auto-alters schema and can drop data.
  Use migrations (`migrationsRun`, `dataSource.runMigrations()`) instead.
- DO list **every** entity in `entities` (or a glob) or its repository won't resolve.

### Entities

```ts
@Entity()                       // optional table name: @Entity("users")
export class User {
  @PrimaryGeneratedColumn() id: number
  @Column() firstName: string
  @Column({ type: "int", nullable: true }) age?: number
  @Column({ unique: true }) email: string
}
```
- `@PrimaryGeneratedColumn("uuid")` for UUID PKs; `@PrimaryColumn` for natural keys.
- DON'T rely on inferred types across DBs — set `type` explicitly for decimals, enums,
  json, timestamps.

### Repository vs EntityManager

- `AppDataSource.getRepository(User)` — entity-scoped, most common.
- `AppDataSource.manager` — one `EntityManager` for all entities; pass the entity as the
  first arg: `manager.find(User, {...})`. Same methods otherwise.
- DO prefer Repository for readability; use EntityManager inside transactions (below).

#### Repository API (0.3+/1.0)
```ts
const repo = AppDataSource.getRepository(User)
await repo.find({ where: { firstName: "Timber" }, take: 20, skip: 0 })
await repo.findOne({ where: { id }, relations: { photos: true } }) // needs options obj
await repo.findOneBy({ id })          // shorthand for equality only
await repo.save(user)                 // upsert: insert if new, update if has PK
await repo.insert({ email })          // pure INSERT, no reload, faster/bulk
await repo.update({ id }, { age: 30 })// bulk UPDATE by criteria, no entity load
await repo.delete(id)                 // bulk DELETE, no hooks/cascade load
await repo.remove(user)               // entity DELETE, runs cascades/hooks
await repo.count({ where: { age: 30 } })
```
- **0.3 break:** `findOne(id)` (bare value) and `findByIds` are gone. Use
  `findOne({ where })`, `findOneBy(where)`, `findBy`, `countBy`, `findOneByOrFail`.
- DO use `save` for entity graphs/cascades; use `insert`/`update`/`delete` for bulk
  set-based writes (they skip loading and lifecycle listeners).

### Relations

```ts
@Entity() class Photo {
  @ManyToOne(() => User, (u) => u.photos) user: User          // FK lives here
}
@Entity() class User {
  @OneToMany(() => Photo, (p) => p.user) photos: Photo[]
}
```
- Decorators: `@OneToOne`, `@OneToMany`, `@ManyToOne`, `@ManyToMany`.
- `@JoinColumn` — sets FK-owning side. **Required on `@OneToOne`**, optional on `@ManyToOne`.
- `@JoinTable` — **required** on the owning side of `@ManyToMany` (defines junction table).
- DO use arrow-thunks `() => User` to dodge circular-import/ordering issues.

#### Eager vs lazy
- `{ eager: true }` — loaded automatically by `find*` methods. **Only** works with
  `find*`, NOT QueryBuilder — there you must `leftJoinAndSelect`. Eager on one side only.
- Lazy — type the property `Promise<T[]>` and `await` it. Marked **experimental /
  non-standard**; avoid in hot paths (each access is a query).
- DON'T scatter `eager: true` broadly — every query drags the relation and its joins.

### N+1 — the cardinal sin

DON'T loop and touch relations per row (fires 1 + N queries):
```ts
const users = await repo.find()
for (const u of users) console.log((await u.photos).length) // ❌ N+1 (lazy)
```
DO fetch related data in one round trip:
```ts
await repo.find({ relations: { photos: true } })            // ✅ one query set
// or explicit joins via QueryBuilder:
await repo.createQueryBuilder("user")
  .leftJoinAndSelect("user.photos", "photo")
  .getMany()                                                 // ✅ single JOIN
```
- `leftJoin` joins for filtering only (no select); `leftJoinAndSelect` also hydrates.

### QueryBuilder

```ts
await AppDataSource.getRepository(User).createQueryBuilder("user")
  .where("user.name = :name", { name })                 // named param — bound/escaped
  .andWhere("user.id IN (:...ids)", { ids })            // array expansion
  .orderBy("user.id", "DESC").take(20)
  .getMany()                                            // getOne / getManyAndCount
```
- `getRawOne` / `getRawMany` return raw rows (aggregates, non-entity shapes).

### Transactions

DO wrap multi-write units; the callback commits on resolve, rolls back on throw:
```ts
await AppDataSource.transaction(async (manager) => {
  await manager.save(user)
  await manager.save(photo)          // use the passed manager, NOT repo/AppDataSource
})
```
- DON'T mix outer repositories inside a `transaction` callback — writes done via the
  outer DataSource run outside the transaction. Use the injected `manager`.
- Manual control via QueryRunner (isolation levels, savepoints):
```ts
const qr = AppDataSource.createQueryRunner()
await qr.connect(); await qr.startTransaction()
try { await qr.manager.save(user); await qr.commitTransaction() }
catch (e) { await qr.rollbackTransaction(); throw e }
finally { await qr.release() }        // ALWAYS release or you leak pool connections
```

### SECURITY — raw escape hatches (injection-prone)

TypeORM binds named params for you. The danger is **string building**.

- DON'T interpolate user input into a where string — SQL injection:
  `.where(`user.name = '${name}'`)`. DO bind: `.where("user.name = :name", { name })`.
  Same for `Raw()`, `.having()`, `.orderBy()` — never concatenate untrusted values.
- DON'T concat user input into `dataSource.query(...)` / `manager.query(...)`. DO use the
  parameters array: `await AppDataSource.query("... WHERE id = $1", [id])`.
- DON'T build column/table/`orderBy` identifiers from user input — can't be
  parameterized; validate against an allow-list.

### Sources
- https://typeorm.io/ (v1.0 announcement + entity quick-start)
- https://typeorm.io/docs/getting-started (DataSource, initialize, getRepository)
- https://typeorm.io/docs/working-with-entity-manager/repository-api (find/findOne/findOneBy/save/insert/update/delete/remove)
- https://typeorm.io/docs/relations/relations (relation + join decorators)
- https://typeorm.io/docs/relations/eager-and-lazy-relations (eager/lazy)
- https://typeorm.io/docs/query-builder/select-query-builder (param binding, injection warning)
- https://typeorm.io/docs/advanced-topics/transactions (transaction / QueryRunner)
- https://github.com/typeorm/typeorm/releases (1.0.0 latest, removed Connection; 0.3.30 legacy)

## Migrations & pitfalls <a id="migrations-and-pitfalls"></a>

JS/Node ORM (TypeScript-first). Distinct from the JVM `orm` lore. Assumes separate javascript/typescript/node lore. Facts verified against typeorm.io, current line **0.3.x**.

### Version awareness
- **0.3 broke the connection API.** `createConnection()` / `Connection` / `connection.close()` are replaced by `new DataSource(options)` + `dataSource.initialize()` / `dataSource.destroy()`. If you see `createConnection`, the code is 0.2-era or on a deprecated shim — migrate it.
- CLI in 0.3 takes a **DataSource file** via `-d`, not the old `ormconfig.json`.
- State the installed version before asserting API shape; verify against typeorm.io.

### synchronize — DO / DON'T
- **DON'T** set `synchronize: true` in production. It auto-alters/drops schema to match entities and **can destroy data** once real data exists. Docs: "using `synchronize: true` is unsafe once data exists."
- **DON'T** ship `dropSchema: true` outside throwaway test setup.
- **DO** keep `synchronize: false` and let **migrations** be the sole schema mechanism (dev included, once you have a schema you care about).
- **DO** gate any dev-only sync behind an env check — never a shared/staging DB.

```ts
// data-source.ts
export const AppDataSource = new DataSource({
  type: "postgres",
  synchronize: false,                 // migrations only
  migrations: [__dirname + "/migrations/**/*{.js,.ts}"],
  migrationsTableName: "migrations",  // tracking table (default "migrations")
  migrationsTransactionMode: "all",   // "all" | "each" | "none"
  // migrationsRun: true,             // optional: run pending on initialize()
})
```

### Migration workflow — DO / DON'T
CLI targets the DataSource with `-d`. In a TS project run through the bundled bin (`typeorm-ts-node-commonjs`) or via a package script.

```bash
# generate a migration by diffing entities against the live schema (needs -d)
typeorm migration:generate ./src/migrations/AddUser -d ./src/data-source.ts
# create an EMPTY migration to hand-write (no DB connection, no -d)
typeorm migration:create ./src/migrations/BackfillEmails
# apply all pending migrations
typeorm migration:run -d ./src/data-source.ts
# revert the LAST applied migration
typeorm migration:revert -d ./src/data-source.ts
# list migrations + executed/pending status
typeorm migration:show -d ./src/data-source.ts
```

- **DO** review generated SQL before committing — `migration:generate` diffs entities vs DB and can emit destructive `ALTER`/`DROP`. It is a draft, not gospel.
- **DO** implement a correct `down()` for every `up()`; `migration:revert` runs exactly one step. Untested `down()` = no real rollback.
- **DON'T** edit a migration that has already run in any shared environment. TypeORM records each executed migration in the `migrations` table by timestamp; editing an applied file causes drift (already-run files aren't re-applied). Instead **add a new migration**.
- **DON'T** renumber/rename or reorder applied migrations — ordering is the timestamp prefix.
- **DO** commit migrations to VCS and run them in CI/CD; prefer explicit `migration:run` over `migrationsRun: true` when you need control over timing.

```ts
export class AddUser1710000000000 implements MigrationInterface {
  async up(q: QueryRunner): Promise<void> {
    await q.query(`ALTER TABLE "user" ADD "email" varchar NOT NULL`)
  }
  async down(q: QueryRunner): Promise<void> {   // must actually reverse up()
    await q.query(`ALTER TABLE "user" DROP COLUMN "email"`)
  }
}
```

#### Transactions in migrations
- Default wraps migrations in a transaction. Modes: `migrationsTransactionMode: "all"` (one tx for the whole batch), `"each"` (per-migration), `"none"`.
- **DO** set `transaction = false` on a single migration for statements that can't run inside a tx (e.g. Postgres `CREATE INDEX CONCURRENTLY`). Per-migration override only takes effect under `each` or `none` mode.

```ts
export class AddIndex1710000000001 implements MigrationInterface {
  transaction = false
  async up(q: QueryRunner) { await q.query(`CREATE INDEX CONCURRENTLY idx ON post(name)`) }
  async down(q: QueryRunner) { await q.query(`DROP INDEX CONCURRENTLY idx`) }
}
```

### Connection pooling — DO / DON'T
- `initialize()` **opens the pool**; `destroy()` closes it. Create the DataSource **once** per process and reuse it — don't `initialize()` per request (pool exhaustion / leaks).
- **DO** size the pool with `poolSize`. Pass driver-specific pool/timeout knobs through `extra` (forwarded to the underlying driver, e.g. `node-postgres`/`mysql2`).
- **DO** use `maxQueryExecutionTime` to log slow queries.
- **DO** always `release()` a manually created `QueryRunner` in `finally` — an unreleased QueryRunner holds a pool connection.

```ts
new DataSource({ type: "postgres", poolSize: 10,
  extra: { max: 10, idleTimeoutMillis: 30000 },
  maxQueryExecutionTime: 1000 })
```

### SECURITY — SQL injection (NON-NEGOTIABLE)
TypeORM's Repository/QueryBuilder methods parameterize by default. The danger is **where-strings and raw `query()`**.

- **DON'T** concatenate user input into a where-string or into `.query()`. `` .where(`user.name = '${name}'`) `` and `` q.query(`... WHERE name='${name}'`) `` are injectable.
- **DO** use named parameters in QueryBuilder: `:name`, and `(:...list)` for arrays. Values via the object arg or `setParameter`.

```ts
// GOOD
repo.createQueryBuilder("user")
  .where("user.name = :name", { name })            // or .setParameter("name", name)
  .andWhere("user.id IN (:...ids)", { ids })
  .getMany()

// BAD — injectable
repo.createQueryBuilder("user").where(`user.name = '${name}'`)
```

- **DO** parameterize raw queries via the **second argument**. Placeholder syntax is **driver-specific**: postgres/cockroach `$1`; mysql/mariadb/sqlite/sap `?`; oracle `:1`; mssql `@0`; spanner `@param0`. Named `:name` (object arg) also works on drivers like mysql2.

```ts
// GOOD (postgres)
await dataSource.query("SELECT * FROM users WHERE name = $1 AND age = $2", [name, age])
// GOOD (named)
await dataSource.query("SELECT * FROM users WHERE name = :name", { name })
```

- **DON'T** interpolate untrusted input into identifiers (table/column names) or `ORDER BY` — parameters bind **values only**. Validate identifiers against an allow-list.
- **DON'T** trust `FindOptionsWhere` built from raw request bodies — cast/validate fields so a client can't inject unexpected operators or columns.

### Sources
- https://typeorm.io/docs/migrations/why
- https://typeorm.io/docs/migrations/setup
- https://typeorm.io/docs/migrations/generating
- https://typeorm.io/docs/migrations/faking
- https://typeorm.io/docs/migrations/status
- https://typeorm.io/docs/using-cli
- https://typeorm.io/docs/data-source/data-source-api
- https://typeorm.io/docs/data-source/data-source-options
- https://typeorm.io/docs/query-builder/select-query-builder
- https://typeorm.io/docs/working-with-entity-manager/repository-api
- https://typeorm.io/docs/working-with-entity-manager/entity-manager-api
- https://typeorm.io/docs/transactions
- https://typeorm.io/docs/releases/upgrading (0.2 → 0.3 DataSource migration)
