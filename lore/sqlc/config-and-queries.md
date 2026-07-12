# sqlc — Config & generated queries

Compile-time codegen: you write SQL, `sqlc generate` emits type-safe Go. No runtime ORM, no reflection, no query builder. Generated code is fully parameterized (`$1` / `?`) — safe by construction. Current line: sqlc **1.x**, config **version "2"** (v1 config is legacy — don't start new projects on it). Assumes Go foundation lore exists separately.

Mental model: three inputs (`sqlc.yaml`, `schema.sql`, `query.sql`) → three outputs (`models.go`, `db.go`, `query.sql.go`). Migrations are NOT sqlc's job.

## Config (sqlc.yaml, version 2)

```yaml
version: "2"
sql:
  - engine: "postgresql"        # postgresql | mysql | sqlite
    queries: "./query"          # dir, single file, or list
    schema: "./schema"          # DDL / migration dir — CREATE TABLE, not data
    gen:
      go:
        package: "db"
        out: "internal/db"
        sql_package: "pgx/v5"   # pgx/v5 | pgx/v4 | database/sql (default)
        emit_json_tags: true
        emit_interface: true    # generates a Querier interface (mockable)
        emit_empty_slices: true # :many returns []T{} not nil
```

### DO
- DO pin `version: "2"`; it's the current schema.
- DO pick `engine` deliberately — it changes placeholder syntax and available features (`:copyfrom`/`:batch*` are pgx-only).
- DO set `sql_package: "pgx/v5"` for Postgres unless you have a reason to stay on `database/sql`. pgx is the current, actively developed Postgres driver.
- DO `emit_interface: true` when you need to mock the DB layer (`Querier`) in tests.
- DO `emit_empty_slices: true` so `:many` returns `[]T{}` (nil slices bite JSON encoders and callers).
- DO `emit_json_tags: true` if structs are serialized to JSON at the edge.
- DO point `schema` at the SAME DDL your migration tool applies — sqlc reads it statically to type queries; drift = wrong types or generate errors.
- DO commit generated `*.go` and re-run `sqlc generate` in CI to catch drift (`git diff --exit-code`).

### DON'T
- DON'T hand-edit generated files — regenerate.
- DON'T put `INSERT`/data or app logic in `schema` — it's DDL only.
- DON'T assume `emit_pointers_for_null_types`/`NullString` handling is default — nullable columns emit null-wrapper types (`pgtype.Text`, `sql.NullString`) unless you override.

## Queries (.sql with `-- name:` annotations)

Every query is preceded by `-- name: <MethodName> :<command>`. The command picks the Go signature.

```sql
-- name: GetAuthor :one
SELECT * FROM authors WHERE id = $1 LIMIT 1;

-- name: ListAuthors :many
SELECT * FROM authors ORDER BY name;

-- name: CreateAuthor :one
INSERT INTO authors (name, bio) VALUES ($1, $2) RETURNING *;

-- name: DeleteAuthor :exec
DELETE FROM authors WHERE id = $1;
```

Commands:
- `:one` → `(T, error)` — single row via `QueryRow`.
- `:many` → `([]T, error)` — slice via `Query`.
- `:exec` → `error` — no rows.
- `:execrows` → `(int64, error)` — affected row count.
- `:execresult` → `(sql.Result, error)`.
- `:execlastid` → `(int64, error)` — last insert id (MySQL/SQLite; Postgres uses `RETURNING` + `:one`).
- `:copyfrom` → bulk insert via Postgres COPY protocol (pgx only, much faster than N inserts).
- `:batchexec` / `:batchone` / `:batchmany` → pgx batch objects (Postgres + pgx/v4|v5 only).

### DO
- DO keep raw SQL in the `.sql` files — that's the whole point; queries are reviewed as SQL, tested against the schema.
- DO use `$1,$2` (Postgres) / `?` (MySQL, SQLite) placeholders. sqlc generates parameter binding; values are passed as driver args, never interpolated.
- DO name explicit params with `sqlc.arg('name')` (→ named Go arg) and nullable ones with `sqlc.narg('name')` (→ nullable arg).
- DO use `sqlc.slice('ids')` for dynamic `IN (...)` on MySQL/SQLite; slice must be non-empty (returns an error, not a panic). Not compatible with `emit_prepared_queries`.
- DO use `= ANY($1::bigint[])` with `pq.Array`/pgx array types for `IN` on Postgres.
- DO prefer explicit column lists over `SELECT *` for stable generated structs (avoids surprise columns / reorder churn).
- DO add `RETURNING *` + `:one` on inserts/updates when you need the persisted row.

### DON'T
- DON'T build SQL by concatenating user input anywhere — sqlc has no string-building API by design, so there's nothing to misuse. Keep it that way.
- DON'T interpolate identifiers (table/column names) from user input — placeholders bind VALUES only, not identifiers. Whitelist identifiers in Go if truly dynamic.
- `:batch*` is **Postgres + pgx only**. `:copyfrom` works on Postgres (pgx COPY) **and MySQL** (`LOAD DATA`, via `database/sql` + the mysql driver) — but not SQLite.

## Overrides & rename

Map DB types → Go types, or rename fields. Go-only feature.

```yaml
overrides:
  - db_type: "uuid"
    go_type:
      import: "github.com/google/uuid"
      type: "UUID"
  - db_type: "pg_catalog.timestamptz"
    nullable: true            # nullable/non-null are separate overrides
    go_type: { import: "gopkg.in/guregu/null.v4", package: "null", type: "Time" }
  - column: "authors.id"       # column form: table.column; wins over db_type
    go_type: "github.com/google/uuid.UUID"
```

- `go_type` short form = fully-qualified string; struct form = `import`/`package`/`type`/`pointer`/`slice`.
- `db_type` and `column` are mutually exclusive; `column` takes precedence.
- `nullable`/`unsigned` (MySQL) only apply to `db_type` overrides.
- Per-field: `go_struct_tag`; blanket tags: `emit_json_tags` / `emit_db_tags`.
- `rename:` maps column → struct field name (e.g. `spotify_url: "SpotifyURL"`).

## Migrations (bring your own)

sqlc does NOT run migrations — it only reads your DDL to type queries.

- DO manage schema with **golang-migrate**, **goose**, or **Atlas**. Point `schema:` at that migration dir (sqlc parses `CREATE TABLE`; up-only DDL).
- DO keep the migration source of truth and the `schema:` sqlc reads in sync — they're the same files.
- DON'T look for an AutoMigrate — there isn't one (that's GORM's dev-only trick). sqlc is codegen, not a runtime ORM.

## Security summary

- Generated code is parameterized end to end → injection-safe for VALUES by construction.
- The only injection surfaces you own: dynamic identifiers and any SQL you build outside sqlc. Whitelist identifiers; never hand-concat.
- `sqlc vet` runs CEL lint rules (e.g. `sqlc/db-prepare`) against queries in CI — use it to enforce policy.

## Sources
- https://docs.sqlc.dev/en/latest/reference/config.html
- https://docs.sqlc.dev/en/latest/reference/query-annotations.html
- https://docs.sqlc.dev/en/latest/tutorials/getting-started-postgresql.html
- https://docs.sqlc.dev/en/latest/howto/overrides.html
- https://docs.sqlc.dev/en/latest/howto/select.html
- https://docs.sqlc.dev/en/latest/index.html
