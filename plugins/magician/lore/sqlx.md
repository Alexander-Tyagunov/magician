# sqlx — core

sqlx (v1.4.0, MIT) extends `database/sql`; wraps `sql.DB/Tx/Stmt` as supersets — stdlib semantics unchanged. Driver: `github.com/jackc/pgx/v5` (Postgres 14+, Go 1.25+) via `pgx/v5/stdlib` adapter, or `pgxpool` for pgx-native pooling.

DO parameterize EVERY value: `?` (MySQL/SQLite) or `$1` (Postgres); pass args separately. `db.Rebind` converts `?`→`$N`. DON'T `fmt.Sprintf`/concat user input into SQL — bindvars are values only, they can't parameterize table/column/keyword names (validate those against an allowlist).
DO `Get(&x, q, a)` for one row, `Select(&xs, q, a)` for many; `Select` loads the WHOLE result into memory — stream large sets with `Queryx` + `StructScan`.
DO map columns with `db:"col"` tags on EXPORTED fields; unmapped column errors unless `db.Unsafe()`. Alias ambiguous joins with `AS`.
DO `NamedExec`/`NamedQuery` with `:name` from a struct or map for inserts/updates.
DO expand slices for `IN`: `q,args,_ := sqlx.In("... IN (?)", ids); q = db.Rebind(q)`.
DO `sqlx.Connect` (opens + pings, fails fast) over lazy `Open`; set `SetMaxOpenConns`/`SetConnMaxLifetime`.
DON'T look for built-in migrations — sqlx has none. Bring goose / golang-migrate / Atlas; never auto-create schema in prod.

Commands: `go get github.com/jmoiron/sqlx github.com/jackc/pgx/v5` · `go test ./...` · migrate via `goose`/`migrate`.

Deep dive when writing non-trivial sqlx — read lore/sqlx/{database-sql-and-pgx}.md

## Sources
jmoiron.github.io/sqlx · pkg.go.dev/github.com/jmoiron/sqlx · pkg.go.dev/database/sql · github.com/jackc/pgx
