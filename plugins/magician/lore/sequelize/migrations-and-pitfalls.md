# sequelize — Migrations & pitfalls

JS/Node ORM. Distinct from the JVM `orm` lore (Hibernate/JPA). Assumes JS/TS/Node lore lives separately.

**Versions:** v6 is current **stable**. v7 is **alpha** (unreleased as of 2026-07) — full TS rewrite, ESM, core package renamed `@sequelize/core`, dialects split into their own packages (`@sequelize/sqlite3`, etc.), decorator model defs (`@Attribute` from `@sequelize/core/decorators-legacy`), Node `>=18`. Do NOT adopt v7 in production yet; write guidance against v6. sequelize-cli targets v6 migrations.

## Migrations & seeders — DO

- DO manage all prod schema change through migrations, not `sync`. Scaffold with `npx sequelize-cli init` (creates `config/`, `models/`, `migrations/`, `seeders/`).
- DO generate skeletons: `npx sequelize-cli migration:generate --name add-x` / `seed:generate --name demo-user`. Each file exports `up`/`down` (async, return a Promise).
- DO write a real `down` for every `up` so rollback works: `db:migrate:undo`, `db:migrate:undo:all`, `--to XXXX-name.js`.
- DO drive DDL through `queryInterface`: `createTable`, `dropTable`, `addColumn`, `removeColumn`, `changeColumn`, `addIndex`, `bulkInsert`/`bulkDelete` (seeders).
- DO wrap multi-step DDL in a transaction and pass `{ transaction }` to every op; commit/rollback yourself.

```js
module.exports = {
  async up(queryInterface, Sequelize) {
    const t = await queryInterface.sequelize.transaction();
    try {
      await queryInterface.addColumn('Person', 'petName',
        { type: Sequelize.DataTypes.STRING }, { transaction: t });
      await queryInterface.addIndex('Person', ['petName'],
        { unique: true, transaction: t });
      await t.commit();
    } catch (e) { await t.rollback(); throw e; }
  },
  async down(queryInterface) {
    await queryInterface.removeColumn('Person', 'petName');
  },
};
```

- DO relocate paths via `.sequelizerc` (`migrations-path`, `seeders-path`, `models-path`, `config`) rather than passing CLI flags every time.
- DO know the ledger: `db:migrate` records applied migrations in the **`SequelizeMeta`** table. Seeders are **not tracked by default** (`seederStorage: 'none'`) — set `seederStorage: 'sequelize'` (table `SequelizeData`) if you need repeatable, tracked seeds.

## Migrations & seeders — DON'T

- DON'T edit a migration that has already run in any shared/prod environment. `SequelizeMeta` marks it done, so the edit never re-executes and DBs drift. Write a NEW migration to change course.
- DON'T `sync({ force: true })` in prod — it **DROPS** the table first. `sync({ alter: true })` is also destructive (inspects and mutates schema). Docs: force/alter are "destructive operations... not recommended for production-level software."
- DON'T rely on plain `sequelize.sync()` for evolving schemas — it only creates missing tables, never reconciles changes. Use migrations.
- DON'T leave a test-only `sync({ force })` unguarded. Gate with `match`: `sequelize.sync({ force: true, match: /_test$/ })` so it refuses non-test DBs.
- DON'T assume seeders roll back cleanly — `db:seed:undo` depends on your `down` (e.g. `bulkDelete`); with default `none` storage there's no history to undo against.

## Programmatic migrations (umzug) — DO

- DO use **umzug** (v3.x, `up`/`down` per file) when you need migrations in-process (serverless, tests, deploy scripts) instead of the CLI. Track state with `SequelizeStorage` → same `SequelizeMeta` table.

```js
const { Umzug, SequelizeStorage } = require('umzug');
const umzug = new Umzug({
  migrations: { glob: 'migrations/*.js' },
  context: sequelize.getQueryInterface(),
  storage: new SequelizeStorage({ sequelize }),
  logger: console,
});
await umzug.up();
```

- DO use umzug's `resolve` to adapt sequelize-cli-style `(queryInterface, Sequelize)` migrations to umzug's context signature.

## Raw queries & injection — DON'T (SECURITY, non-negotiable)

- DON'T interpolate/concatenate user input into SQL strings. Ever.
- DON'T pass user input to `literal()`, `raw:`-verbatim order/group strings, or any verbatim option — they are inserted into SQL **unescaped**. Docs on the verbatim `group` string: "Use with caution and don't use with user generated content." Same hazard applies to `literal()`.
- DON'T build `order`/`group`/`where` fragments from request data via `literal()`. Allow-list column names against a fixed set instead.

## Raw queries & injection — DO (SECURITY)

- DO parameterize `sequelize.query` — two mutually exclusive mechanisms (pick one per query):
  - **`replacements`** — escaped and inlined by Sequelize before send. Named `:key` or positional `?`.
  - **`bind`** — sent to the DB separately from SQL text (`$1`/`$name`); values never touch the query string. Generally the safer default.

```js
const { QueryTypes } = require('sequelize');

// replacements (escaped)
await sequelize.query('SELECT * FROM projects WHERE status = :status', {
  replacements: { status: userStatus },
  type: QueryTypes.SELECT,
});

// bind (values sent out-of-band) — prefer this
await sequelize.query('SELECT * FROM projects WHERE status = $1', {
  bind: [userStatus],
  type: QueryTypes.SELECT,
});
```

- DO use `sequelize.fn()`, `sequelize.col()`, `sequelize.where()` for computed/aggregate SQL — they escape/quote appropriately, unlike `literal()`.
- DO pass `type: QueryTypes.SELECT` to skip the `[results, metadata]` destructure and get a clean row array.
- DO note PostgreSQL bind typecasting when needed: `$1::varchar`. All referenced binds must be supplied or Sequelize throws.

## Sources

- https://sequelize.org/docs/v6/other-topics/migrations/
- https://sequelize.org/docs/v6/core-concepts/raw-queries/
- https://sequelize.org/docs/v6/core-concepts/model-basics/
- https://sequelize.org/docs/v6/core-concepts/model-querying-basics/
- https://sequelize.org/docs/v7/
- https://github.com/sequelize/umzug
