# typeorm — Entities & repositories

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

## DataSource (connection lifecycle)

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

## Entities

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

## Repository vs EntityManager

- `AppDataSource.getRepository(User)` — entity-scoped, most common.
- `AppDataSource.manager` — one `EntityManager` for all entities; pass the entity as the
  first arg: `manager.find(User, {...})`. Same methods otherwise.
- DO prefer Repository for readability; use EntityManager inside transactions (below).

### Repository API (0.3+/1.0)
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

## Relations

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

### Eager vs lazy
- `{ eager: true }` — loaded automatically by `find*` methods. **Only** works with
  `find*`, NOT QueryBuilder — there you must `leftJoinAndSelect`. Eager on one side only.
- Lazy — type the property `Promise<T[]>` and `await` it. Marked **experimental /
  non-standard**; avoid in hot paths (each access is a query).
- DON'T scatter `eager: true` broadly — every query drags the relation and its joins.

## N+1 — the cardinal sin

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

## QueryBuilder

```ts
await AppDataSource.getRepository(User).createQueryBuilder("user")
  .where("user.name = :name", { name })                 // named param — bound/escaped
  .andWhere("user.id IN (:...ids)", { ids })            // array expansion
  .orderBy("user.id", "DESC").take(20)
  .getMany()                                            // getOne / getManyAndCount
```
- `getRawOne` / `getRawMany` return raw rows (aggregates, non-entity shapes).

## Transactions

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

## SECURITY — raw escape hatches (injection-prone)

TypeORM binds named params for you. The danger is **string building**.

- DON'T interpolate user input into a where string — SQL injection:
  `.where(`user.name = '${name}'`)`. DO bind: `.where("user.name = :name", { name })`.
  Same for `Raw()`, `.having()`, `.orderBy()` — never concatenate untrusted values.
- DON'T concat user input into `dataSource.query(...)` / `manager.query(...)`. DO use the
  parameters array: `await AppDataSource.query("... WHERE id = $1", [id])`.
- DON'T build column/table/`orderBy` identifiers from user input — can't be
  parameterized; validate against an allow-list.

## Sources
- https://typeorm.io/ (v1.0 announcement + entity quick-start)
- https://typeorm.io/docs/getting-started (DataSource, initialize, getRepository)
- https://typeorm.io/docs/working-with-entity-manager/repository-api (find/findOne/findOneBy/save/insert/update/delete/remove)
- https://typeorm.io/docs/relations/relations (relation + join decorators)
- https://typeorm.io/docs/relations/eager-and-lazy-relations (eager/lazy)
- https://typeorm.io/docs/query-builder/select-query-builder (param binding, injection warning)
- https://typeorm.io/docs/advanced-topics/transactions (transaction / QueryRunner)
- https://github.com/typeorm/typeorm/releases (1.0.0 latest, removed Connection; 0.3.30 legacy)
