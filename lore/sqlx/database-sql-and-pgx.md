# sqlx — database/sql, sqlx & pgx

Layers: stdlib `database/sql` (driver-agnostic pool + scan) → `github.com/jmoiron/sqlx` (thin struct-scan helpers over it) → `github.com/jackc/pgx/v5` (native Postgres driver, faster, own pool). Assumes the Go foundation lore exists separately.

Versions: `database/sql` tracks the Go toolchain (1.25/1.26 line). pgx current **v5** (v5.10.x), module `github.com/jackc/pgx/v5`, needs **Go 1.25+ / PostgreSQL 14+**. sqlx has no independent version — it wraps whatever `database/sql` + driver you pin. Legacy: pgx **v4** (`/v4`) is superseded — don't start new work on it.

## SECURITY — parameterize, always

- DO pass user values as **args**, never in the SQL string. Placeholders are driver-specific: `?` (mysql, sqlite) / `$1,$2` (postgres/pgx) / `:name` named (`sql.Named`, sqlx `NamedExec`, pgx `NamedArgs`).
- DON'T `fmt.Sprintf`/`+`-concatenate user input into SQL — that is the injection hole. This is unconditional.
- Identifiers (table/column names) **cannot** be bound by any of these libs. Never interpolate a raw identifier from user input — validate against a fixed allow-list, then use the constant.

```go
// GOOD
db.QueryContext(ctx, "SELECT id FROM users WHERE email=$1 AND org=$2", email, org)
// BAD — injection
db.QueryContext(ctx, "SELECT id FROM users WHERE email='"+email+"'")
```

## database/sql — the pool — DO

- DO treat `*sql.DB` as a **pool**, not a connection: safe for concurrent use, open **once** at startup, keep for app lifetime, `Close()` only on shutdown. Never open-per-request.
- DO configure the pool on that single handle:
  - `SetMaxOpenConns(n)` — cap total (default `0`=unlimited; set it or you can exhaust the DB's `max_connections`). go1.2.
  - `SetMaxIdleConns(n)` — idle kept warm (**default 2**; raise toward MaxOpen for hot paths). go1.1. Capped to MaxOpen.
  - `SetConnMaxLifetime(d)` — recycle conns (essential behind LBs/proxies; `0`=never). go1.6.
  - `SetConnMaxIdleTime(d)` — reap idle conns. go1.15.
- DO `db.PingContext(ctx)` after `Open` — `sql.Open` only validates the DSN, it doesn't dial.
- DO use context variants everywhere: `QueryContext`, `QueryRowContext`, `ExecContext`, `BeginTx` (go1.8) — cancellation propagates; cancelling a `BeginTx` context rolls back.
- DO watch `db.Stats()` (`WaitCount`/`WaitDuration` rising = pool too small).

```go
db, err := sql.Open("pgx", dsn)      // or "postgres", "mysql", "sqlite"
if err != nil { return err }
db.SetMaxOpenConns(25); db.SetMaxIdleConns(25); db.SetConnMaxLifetime(5*time.Minute)
if err := db.PingContext(ctx); err != nil { return err }
```

## database/sql — rows lifecycle — DO / DON'T

- DO `defer rows.Close()` immediately after a successful `Query*` — a leaked `Rows` holds its conn out of the pool.
- DO call `rows.Err()` **after** the `Next()` loop — `Next()` returns false on both EOF and error; without `Err()` you silently drop partial-read failures.
- DO handle `sql.ErrNoRows` from `QueryRow(...).Scan` explicitly — it's the "not found" signal, not a fatal error.
- DON'T ignore `Scan` errors or reuse `RawBytes` past the next `Next`/`Close`.

```go
rows, err := db.QueryContext(ctx, "SELECT id,name FROM u WHERE age>$1", n)
if err != nil { return err }
defer rows.Close()
for rows.Next() {
    var u User
    if err := rows.Scan(&u.ID, &u.Name); err != nil { return err }
    out = append(out, u)
}
return rows.Err()      // MUST check
```

## database/sql — NULLs & statements — DO

- DO use `sql.Null*` for nullable columns: `NullString`/`NullBool`/`NullFloat64`/`NullInt64`, `NullInt32`+`NullTime` (go1.13), `NullInt16`/`NullByte` (go1.17), generic `sql.Null[T]` (go1.22). Read `.Valid` before the value. Pointers (`*string`) also work.
- DO `defer stmt.Close()` on any `*sql.Stmt` from `Prepare*` — leaks server resources. Prepared stmts pay off only when reused many times; for one-shots just `QueryContext`. Don't use a `Tx`/`Conn` stmt after that Tx/Conn closes (bound to one conn).

## sqlx — struct scanning over database/sql — DO

- DO `sqlx.Connect` (opens **and** pings) at startup, or `sqlx.Open` (no ping, like stdlib). `sqlx.DB`/`Tx`/`Stmt` **embed** the stdlib types — every `database/sql` method still works; pool config is identical.
- DO map with the **`db:"col"`** struct tag; unset fields default to the lower-cased field name (override globally via `db.MapperFunc`).
- DO pick the right verb:
  - `Get(&dst, q, args...)` — exactly one row into a struct/scalar (returns `sql.ErrNoRows` if none).
  - `Select(&slice, q, args...)` — many rows into a slice. **Loads the entire result set into memory** — bound the query (`LIMIT`); for huge sets use `Queryx` + `StructScan` in a `Next()` loop.
  - `NamedExec` / `NamedQuery` — `:field` bindvars filled from a struct or `map[string]any`.
  - `Queryx`/`QueryRowx` → `StructScan`/`MapScan`/`SliceScan`.
- DO use `sqlx.In(q, args...)` to expand a slice into `IN (?,?,...)`, then `db.Rebind(q)` to convert `?`→`$1` for Postgres. `sqlx.In` works **only** with the `?` bindvar.

```go
type User struct { ID int `db:"id"`; Name string `db:"name"`; Bio sql.NullString `db:"bio"` }
var u User;  err := db.Get(&u, "SELECT id,name,bio FROM users WHERE id=$1", id)
var us []User; err = db.Select(&us, "SELECT id,name,bio FROM users LIMIT 100")
db.NamedExec("INSERT INTO users (name,bio) VALUES (:name,:bio)", u)

q, args, _ := sqlx.In("SELECT * FROM users WHERE id IN (?)", ids)
q = db.Rebind(q); db.Select(&us, q, args...)      // ? -> $1 for pg
```

## sqlx — DON'T

- DON'T rely on `Unsafe()` to paper over column/field mismatches — by default `StructScan` errors when a selected column has no destination field (a real bug signal). Only `Unsafe()` deliberately.
- DON'T `Select` unbounded result sets (OOM). DON'T `SELECT *` into a struct you don't control — column drift breaks scans.

## pgx v5 — native Postgres — DO

- DO use **`pgxpool`** for concurrent apps: `*pgx.Conn` is **not** concurrency-safe; `*pgxpool.Pool` is. `pgxpool.New(ctx, url)` or `ParseConfig`→edit→`NewWithConfig`. `Pool.Ping` after create (New returns before dialing).
- DO configure via `Config`: `MaxConns` (default max(4, `runtime.NumCPU()`)), `MinConns`, `MaxConnLifetime`, `MaxConnIdleTime`. Build config **only** from `ParseConfig`, then mutate.
- DO scan with generics — the ergonomic win over stdlib:
  - `pgx.CollectRows(rows, pgx.RowToStructByName[T])` → `[]T` (by column name; `db:"..."` tag, `db:"-"` skip; v5.1.0).
  - `pgx.CollectOneRow(rows, ...)` (→ `ErrNoRows` if none), `RowToAddrOfStructByName[T]`, `RowToStructByPos[T]`, `RowTo[T]`.
- DO release acquired conns: `Pool.Query` returns the conn when you `rows.Close()`; `Pool.QueryRow` when you `Scan`. Manual `Acquire` **requires** `conn.Release()` — prefer `Pool.AcquireFunc` (auto-release).
- DO use `Batch`+`SendBatch` (pipelined round-trips) and `CopyFrom` (bulk load) for throughput.
- DON'T mix drivers pointlessly: to reuse `database/sql`/sqlx code against pgx, register the **stdlib adapter** `github.com/jackc/pgx/v5/stdlib` (`sql.Open("pgx", dsn)`). For new Postgres-only code, the native pgx API is faster and richer.

```go
pool, err := pgxpool.New(ctx, os.Getenv("DATABASE_URL"))
defer pool.Close()
rows, _ := pool.Query(ctx, "SELECT id,name FROM users WHERE age>$1", n)
users, err := pgx.CollectRows(rows, pgx.RowToStructByName[User])   // []User
pool.QueryRow(ctx, "SELECT count(*) FROM users").Scan(&total)
```

## Transactions — DO

- DO `BeginTx(ctx, &sql.TxOptions{...})` (stdlib/sqlx) or `pool.Begin(ctx)` (pgx); always end with `Commit`/`Rollback`. `defer tx.Rollback()` after a successful begin is safe — no-op once committed. Post-terminal ops return `sql.ErrTxDone`. DON'T share one tx across goroutines — it's a single reserved connection.

## Migrations — bring your own

- database/sql, sqlx, and pgx have **no** migration engine. Use **golang-migrate**, **goose**, or **Atlas** as the versioned source of truth. (Contrast: GORM `AutoMigrate` is dev-only and never the prod source of truth — see gorm/ent lore.)

## Sources
- https://pkg.go.dev/database/sql
- https://go.dev/doc/database/ (Accessing databases guide)
- https://jmoiron.github.io/sqlx/
- https://pkg.go.dev/github.com/jmoiron/sqlx
- https://github.com/jackc/pgx
- https://pkg.go.dev/github.com/jackc/pgx/v5
- https://pkg.go.dev/github.com/jackc/pgx/v5/pgxpool
- https://pkg.go.dev/github.com/jackc/pgx/v5/stdlib
