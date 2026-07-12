# Sequelize — core digest

JS/Node ORM (not the JVM `orm` lore). Version cue: **v6 stable** (Node >=10). **v7 alpha** — package renamed `@sequelize/core`, per-dialect packages, Node >=18, decorator models (`@sequelize/core/decorators-legacy`); don't ship v7 to prod.

DO
- Parameterize raw SQL: `sequelize.query(sql, { replacements })` (`:name` / `?`, escaped by Sequelize) or `{ bind }` (`$1` / `$name`, sent separate from SQL text). Use one, not both.
- Set `type: QueryTypes.SELECT` to skip the `[results, metadata]` tuple.
- Build `where` with `Op` operators (`Op.and/or/like/in`), not string concat.
- Use `sequelize.fn`/`sequelize.col` for functions/columns (correct escaping).

DON'T
- Never interpolate user input into SQL strings, `literal()`, `where(literal(...))`, `order`, or `group` — `literal()` emits verbatim SQL = injection. Feed dynamic values via `replacements`/`bind` only.
- Don't pass untrusted objects straight into `where` — a crafted object injects operators/keys; whitelist fields first.
- Don't mix `replacements` and `bind` in one query (throws).
- Don't rely on `sync({ force/alter })` in prod — use migrations.

Commands (sequelize-cli): `sequelize db:migrate` · `db:migrate:undo` · `model:generate` · `migration:generate` · `seed:generate` · `db:seed:all`.

Deep dive when writing non-trivial sequelize — read lore/sequelize/{models-and-queries,migrations-and-pitfalls}.md

## Sources
sequelize.org/docs/v6/core-concepts/raw-queries · /model-querying-basics · sequelize.org/docs/v7 · github.com/sequelize/cli
