# sequelize — deep dive

> On-demand companion to `lore/sequelize.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Models & queries](#models-and-queries) · [Migrations & pitfalls](#migrations-and-pitfalls)

## Models & queries <a id="models-and-queries"></a>

JS/Node ORM (promise-based) for Postgres, MySQL, MariaDB, SQLite, MSSQL, DB2, Snowflake, Oracle. Distinct from the JVM `orm` lore. Assumes JS/TS/Node lore exists separately.

**Versions (verify against sequelize.org).** v6 = current stable (`sequelize`, Node ≥10, TS ≥4.1). v7 = alpha only, package `@sequelize/core`, ESM/TS-first rewrite, Node ≥18, TS ≥5, connector libs auto-installed. DO NOT ship v7 to prod — it's pre-release. Snippets below are v6.

### Model definition

DO — pick one style; `init` (class) is preferred for TS/typing:

```js
// Class + init
class User extends Model {}
User.init(
  { id: { type: DataTypes.INTEGER, primaryKey: true, autoIncrement: true },
    email: { type: DataTypes.STRING, allowNull: false, unique: true } },
  { sequelize, modelName: 'user' } // needs the sequelize instance
);
// or functional: const User = sequelize.define('user', { ...attrs }, { ...opts });
```

- DO set `allowNull`/`unique`/`defaultValue`/`validate` per attribute. Validators run app-side, constraints in the DB — use both.
- Opts: `timestamps` (default true → `createdAt`/`updatedAt`), `paranoid: true` (soft delete via `deletedAt`, auto-excluded from finders), `underscored: true` (snake_case).
- DON'T use `sync({ force/alter })` in prod — it drops/mutates tables. Use migrations (sequelize-cli / umzug).

### Associations + eager loading + N+1

DO declare both sides; the FK lives on the model that `belongsTo`:

```js
User.hasMany(Post);      // adds userId to Post
Post.belongsTo(User);    // reads userId on Post
// belongsToMany needs a join table:
User.belongsToMany(Project, { through: 'UserProjects' });
```

- Eager load with `include` (one JOIN/subquery, no N+1):

```js
await User.findAll({ include: [{ model: Post, required: false }] });
// required:true → INNER JOIN (filters parents); required:false → LEFT JOIN
```

- Lazy load via generated mixins: `getPosts()`, `addPost()`, `setPosts()`, `createPost()`, `countPosts()`.

DON'T create the **N+1**: fetch a list then loop calling `getX()` per row.

```js
// BAD — 1 + N queries
const users = await User.findAll();
for (const u of users) u.posts = await u.getPosts();
// GOOD — one query
const users = await User.findAll({ include: Post });
```

- `limit` + hasMany `include` multiplies rows; use `separate: true` on the include (one extra query, no row blowup) or `duplicating: false`.

### Finder methods

All generate `SELECT`; return model instances unless `raw: true` (plain objects). `null` when not found (except `findAll` → `[]`).

- `findByPk(id)` — single row by PK.
- `findOne({ where })` — first match.
- `findAll({ where, order, limit, offset, attributes })` — array.
- `findOrCreate({ where, defaults })` → `[instance, created]`. Race-prone without a unique constraint; wrap in a transaction.
- `findAndCountAll({ where, limit, offset })` → `{ count, rows }` for pagination. With `group`, `count` becomes an array — handle both shapes.
- Aggregates: `count`, `max`, `min`, `sum`.

DO use `Op` for operators, never string-build WHERE:

```js
const { Op } = require('sequelize');
await Post.findAll({ where: { views: { [Op.gte]: 100 }, title: { [Op.like]: 'foo%' } } });
```

### Transactions

**Managed (preferred)** — auto commit on resolve, auto rollback on throw:

```js
await sequelize.transaction(async (t) => {
  await User.create({ ... }, { transaction: t });
  await Account.decrement('balance', { by: 10, transaction: t });
}); // throw inside → rollback; NEVER call t.commit()/t.rollback() here
```

**Unmanaged** — you own commit/rollback:

```js
const t = await sequelize.transaction();
try { await User.create({ ... }, { transaction: t }); await t.commit(); }
catch (e) { await t.rollback(); }
```

- DO thread `{ transaction: t }` into EVERY query in the txn — Sequelize does not do it implicitly. Miss it and that query runs outside the txn.
- DO enable CLS to auto-propagate: `Sequelize.useCLS(namespace)` (needs `cls-hooked`) — set before `new Sequelize`.
- DO set `isolationLevel` when needed: `Transaction.ISOLATION_LEVELS.SERIALIZABLE`. Use `lock: true` (+ `skipLocked`) for `SELECT ... FOR UPDATE`.
- DO fire side effects post-commit with `t.afterCommit(() => ...)` — skipped on rollback. From model hooks: `options.transaction?.afterCommit(...)`.

### Hooks

Lifecycle callbacks on **models, not instances**. Order: `beforeBulkCreate/Destroy/Update` → `beforeValidate` → (validate) → `afterValidate`/`validationFailed` → `beforeCreate/Update/Destroy/Save/Upsert` → (op) → `afterCreate/...` → `afterBulkCreate/...`.

```js
User.beforeCreate(async (user) => { user.password = await hash(user.password); });
// or User.addHook('beforeCreate','hashPw', fn); or via init({ hooks: { ... } })
```

- CRITICAL: `bulkCreate`/`update`/`destroy` fire only **bulk** hooks. Per-row hooks need `{ individualHooks: true }` — loads all rows into memory, watch perf.
- Hooks DON'T fire for: raw queries, QueryInterface, and cascade deletes (unless the association has `hooks: true`, which is legacy/discouraged). `SET NULL`/`SET DEFAULT` FK actions also skip hooks.
- DO pass `{ transaction: options.transaction }` inside hooks that hit the DB.

### Connection pooling

One `Sequelize` instance per process = one pool. DON'T `new Sequelize` per request.

```js
new Sequelize(db, user, pass, {
  pool: { max: 5, min: 0, acquire: 30000, idle: 10000 } // v6 example values
});
```

- `max`/`min` connections; `acquire` = max ms to wait for a conn before throwing; `idle` = ms before an idle conn is released. Serverless: keep `max` low and `idle`/`min` small.
- Multi-process: size so `max × processes` ≤ DB connection limit.
- Read replicas: `replication: { read: [...], write: {...} }` — writes and txns go to primary, reads round-robin the replicas.

### Raw queries — SECURITY (injection-prone escape hatch)

`sequelize.query()` bypasses the query builder. NEVER interpolate user input into the SQL string.

DO parameterize — `replacements` (Sequelize escapes + inlines) or `bind` (sent to DB separately from SQL text; can't be keywords/identifiers). Use one, not both:

```js
const { QueryTypes } = require('sequelize');
// bind params (preferred): $1 / $name
await sequelize.query('SELECT * FROM users WHERE status = $1',
  { bind: [status], type: QueryTypes.SELECT });
// replacements: :name or ? (arrays auto-expand for IN)
await sequelize.query('SELECT * FROM users WHERE id IN (:ids)',
  { replacements: { ids: [1, 2, 3] }, type: QueryTypes.SELECT });
```

- DON'T `` `... WHERE name = '${userInput}'` `` — classic SQLi.
- DANGER: `sequelize.literal('...')` emits its string as **raw, unescaped SQL** wherever embedded (where/order/attributes). NEVER put user input in `literal()`. Same for `Sequelize.col`/raw `order` strings built from input. If you need a dynamic column, whitelist against an allow-list of known names.
- `QueryTypes.SELECT` returns rows directly; default return is `[results, metadata]`.

### Sources

- https://sequelize.org/docs/v6/
- https://sequelize.org/docs/v6/core-concepts/model-basics/
- https://sequelize.org/docs/v6/core-concepts/assocs/
- https://sequelize.org/docs/v6/advanced-association-concepts/eager-loading/
- https://sequelize.org/docs/v6/core-concepts/model-querying-finders/
- https://sequelize.org/docs/v6/core-concepts/raw-queries/
- https://sequelize.org/docs/v6/other-topics/transactions/
- https://sequelize.org/docs/v6/other-topics/hooks/
- https://sequelize.org/docs/v6/other-topics/connection-pool/
- https://sequelize.org/docs/v6/other-topics/read-replication/
- https://sequelize.org/releases/

## Migrations & pitfalls <a id="migrations-and-pitfalls"></a>

JS/Node ORM. Distinct from the JVM `orm` lore (Hibernate/JPA). Assumes JS/TS/Node lore lives separately.

**Versions:** v6 is current **stable**. v7 is **alpha** (unreleased as of 2026-07) — full TS rewrite, ESM, core package renamed `@sequelize/core`, dialects split into their own packages (`@sequelize/sqlite3`, etc.), decorator model defs (`@Attribute` from `@sequelize/core/decorators-legacy`), Node `>=18`. Do NOT adopt v7 in production yet; write guidance against v6. sequelize-cli targets v6 migrations.

### Migrations & seeders — DO

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

### Migrations & seeders — DON'T

- DON'T edit a migration that has already run in any shared/prod environment. `SequelizeMeta` marks it done, so the edit never re-executes and DBs drift. Write a NEW migration to change course.
- DON'T `sync({ force: true })` in prod — it **DROPS** the table first. `sync({ alter: true })` is also destructive (inspects and mutates schema). Docs: force/alter are "destructive operations... not recommended for production-level software."
- DON'T rely on plain `sequelize.sync()` for evolving schemas — it only creates missing tables, never reconciles changes. Use migrations.
- DON'T leave a test-only `sync({ force })` unguarded. Gate with `match`: `sequelize.sync({ force: true, match: /_test$/ })` so it refuses non-test DBs.
- DON'T assume seeders roll back cleanly — `db:seed:undo` depends on your `down` (e.g. `bulkDelete`); with default `none` storage there's no history to undo against.

### Programmatic migrations (umzug) — DO

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

### Raw queries & injection — DON'T (SECURITY, non-negotiable)

- DON'T interpolate/concatenate user input into SQL strings. Ever.
- DON'T pass user input to `literal()`, `raw:`-verbatim order/group strings, or any verbatim option — they are inserted into SQL **unescaped**. Docs on the verbatim `group` string: "Use with caution and don't use with user generated content." Same hazard applies to `literal()`.
- DON'T build `order`/`group`/`where` fragments from request data via `literal()`. Allow-list column names against a fixed set instead.

### Raw queries & injection — DO (SECURITY)

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

### Sources

- https://sequelize.org/docs/v6/other-topics/migrations/
- https://sequelize.org/docs/v6/core-concepts/raw-queries/
- https://sequelize.org/docs/v6/core-concepts/model-basics/
- https://sequelize.org/docs/v6/core-concepts/model-querying-basics/
- https://sequelize.org/docs/v7/
- https://github.com/sequelize/umzug
