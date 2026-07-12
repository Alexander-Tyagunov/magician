# sequelize — Models & queries

JS/Node ORM (promise-based) for Postgres, MySQL, MariaDB, SQLite, MSSQL, DB2, Snowflake, Oracle. Distinct from the JVM `orm` lore. Assumes JS/TS/Node lore exists separately.

**Versions (verify against sequelize.org).** v6 = current stable (`sequelize`, Node ≥10, TS ≥4.1). v7 = alpha only, package `@sequelize/core`, ESM/TS-first rewrite, Node ≥18, TS ≥5, connector libs auto-installed. DO NOT ship v7 to prod — it's pre-release. Snippets below are v6.

## Model definition

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

## Associations + eager loading + N+1

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

## Finder methods

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

## Transactions

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

## Hooks

Lifecycle callbacks on **models, not instances**. Order: `beforeBulkCreate/Destroy/Update` → `beforeValidate` → (validate) → `afterValidate`/`validationFailed` → `beforeCreate/Update/Destroy/Save/Upsert` → (op) → `afterCreate/...` → `afterBulkCreate/...`.

```js
User.beforeCreate(async (user) => { user.password = await hash(user.password); });
// or User.addHook('beforeCreate','hashPw', fn); or via init({ hooks: { ... } })
```

- CRITICAL: `bulkCreate`/`update`/`destroy` fire only **bulk** hooks. Per-row hooks need `{ individualHooks: true }` — loads all rows into memory, watch perf.
- Hooks DON'T fire for: raw queries, QueryInterface, and cascade deletes (unless the association has `hooks: true`, which is legacy/discouraged). `SET NULL`/`SET DEFAULT` FK actions also skip hooks.
- DO pass `{ transaction: options.transaction }` inside hooks that hit the DB.

## Connection pooling

One `Sequelize` instance per process = one pool. DON'T `new Sequelize` per request.

```js
new Sequelize(db, user, pass, {
  pool: { max: 5, min: 0, acquire: 30000, idle: 10000 } // v6 example values
});
```

- `max`/`min` connections; `acquire` = max ms to wait for a conn before throwing; `idle` = ms before an idle conn is released. Serverless: keep `max` low and `idle`/`min` small.
- Multi-process: size so `max × processes` ≤ DB connection limit.
- Read replicas: `replication: { read: [...], write: {...} }` — writes and txns go to primary, reads round-robin the replicas.

## Raw queries — SECURITY (injection-prone escape hatch)

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

## Sources

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
