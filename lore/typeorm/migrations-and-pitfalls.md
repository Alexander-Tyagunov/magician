# typeorm — Migrations & pitfalls

JS/Node ORM (TypeScript-first). Distinct from the JVM `orm` lore. Assumes separate javascript/typescript/node lore. Facts verified against typeorm.io, current line **0.3.x**.

## Version awareness
- **0.3 broke the connection API.** `createConnection()` / `Connection` / `connection.close()` are replaced by `new DataSource(options)` + `dataSource.initialize()` / `dataSource.destroy()`. If you see `createConnection`, the code is 0.2-era or on a deprecated shim — migrate it.
- CLI in 0.3 takes a **DataSource file** via `-d`, not the old `ormconfig.json`.
- State the installed version before asserting API shape; verify against typeorm.io.

## synchronize — DO / DON'T
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

## Migration workflow — DO / DON'T
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

### Transactions in migrations
- Default wraps migrations in a transaction. Modes: `migrationsTransactionMode: "all"` (one tx for the whole batch), `"each"` (per-migration), `"none"`.
- **DO** set `transaction = false` on a single migration for statements that can't run inside a tx (e.g. Postgres `CREATE INDEX CONCURRENTLY`). Per-migration override only takes effect under `each` or `none` mode.

```ts
export class AddIndex1710000000001 implements MigrationInterface {
  transaction = false
  async up(q: QueryRunner) { await q.query(`CREATE INDEX CONCURRENTLY idx ON post(name)`) }
  async down(q: QueryRunner) { await q.query(`DROP INDEX CONCURRENTLY idx`) }
}
```

## Connection pooling — DO / DON'T
- `initialize()` **opens the pool**; `destroy()` closes it. Create the DataSource **once** per process and reuse it — don't `initialize()` per request (pool exhaustion / leaks).
- **DO** size the pool with `poolSize`. Pass driver-specific pool/timeout knobs through `extra` (forwarded to the underlying driver, e.g. `node-postgres`/`mysql2`).
- **DO** use `maxQueryExecutionTime` to log slow queries.
- **DO** always `release()` a manually created `QueryRunner` in `finally` — an unreleased QueryRunner holds a pool connection.

```ts
new DataSource({ type: "postgres", poolSize: 10,
  extra: { max: 10, idleTimeoutMillis: 30000 },
  maxQueryExecutionTime: 1000 })
```

## SECURITY — SQL injection (NON-NEGOTIABLE)
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

## Sources
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
