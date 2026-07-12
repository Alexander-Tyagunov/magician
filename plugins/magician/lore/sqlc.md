# sqlc — core

sqlc compiles annotated SQL into type-safe Go. You write SQL + schema; it generates parameterized code. Engines: `postgresql`, `mysql`, `sqlite`.

Version: sqlc 1.x, config `version: "2"` (v1 is legacy — don't start new projects on it).

DO
- Annotate every query: `-- name: GetAuthor :one` (`:one` `:many` `:exec` `:execresult`; pg also `:copyfrom` `:batchexec`).
- Use placeholders — pg `$1`, mysql/sqlite `?`. sqlc-generated code is already parameterized → injection-safe.
- Name dynamic params with `sqlc.arg('x')` / `sqlc.narg('x')` (nullable); keep all input as bound args.
- Set `sql_package` explicitly: `pgx/v5` (default `database/sql`; `pgx/v4` legacy). Prefer pgx/v5 for pg.
- Run `sqlc generate` in CI and `sqlc vet` to lint queries against schema.
- Commit generated files; regenerate on every SQL change (never hand-edit output).

DON'T
- Never build SQL by concatenating user input into `query.sql`, and never `fmt.Sprintf` a query string — sqlc can't parameterize identifiers (table/column names); refactor instead of interpolating.
- Don't treat `schema:` as a migration runner. sqlc READS schema/migrations to type queries; it does NOT apply them. Bring your own: goose / golang-migrate / Atlas.
- Don't rely on v1 config or mix engines in one spec without the `engine` field on overrides.

Commands: `sqlc generate` · `vet` · `diff` · `verify` · `compile` · `createdb` · `push` · `init` · `version`.

Deep dive when writing non-trivial sqlc — read lore/sqlc/{config-and-queries}.md

Sources: docs.sqlc.dev (getting-started, config, cli)
