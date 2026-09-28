# gorm — deep dive

> On-demand companion to `lore/gorm.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Queries, associations & migrations](#queries-associations-migrations)

## Queries, associations & migrations <a id="queries-associations-migrations"></a>

Scope: GORM **v2** (`gorm.io/gorm` + a `gorm.io/driver/*`). Legacy v1 is `github.com/jinzhu/gorm` — different import path, unmaintained. If you see `jinzhu/gorm`, you're on v1: APIs below (context, generics, `TranslateError`) differ or are absent. Assume the Go foundation lore covers `database/sql` basics.

### Setup / drivers

DO
- Open with a driver: `gorm.Open(postgres.Open(dsn), &gorm.Config{})`. Drivers: `gorm.io/driver/postgres`, `.../mysql`, `.../sqlite` (CGO).
- Configure the pool on the underlying `*sql.DB`: `sqlDB, _ := db.DB()` then `SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxLifetime`. GORM does not pool; `database/sql` does.
- Enable `&gorm.Config{TranslateError: true}` to get portable `gorm.ErrDuplicatedKey` / `gorm.ErrForeignKeyViolated` across dialects.

DON'T
- Don't reuse one `*gorm.DB` chain across goroutines mid-build. `db` is a session builder; scope per request via `db.WithContext(ctx)`.

### Models / tags

DO
- Tag with `gorm:"column:...;type:...;index;uniqueIndex;not null;default:..."`. Embed `gorm.Model` for `ID/CreatedAt/UpdatedAt/DeletedAt`.
- `DeletedAt gorm.DeletedAt` (with index) enables soft delete — deletes become `UPDATE ... SET deleted_at`, and reads auto-filter it. Use `db.Unscoped()` to bypass.

### Query — CRUD

DO
- Single row: `First` (order by PK asc, `LIMIT 1`), `Take` (no order), `Last` (PK desc). All return `ErrRecordNotFound` when empty.
- `Find(&slice)` for many; `Find(&one)` does **not** error on empty. Check `result.RowsAffected` / `result.Error`.
- Inline conditions: `db.First(&u, "id = ?", id)` or `db.First(&u, 10)`.
- Field-scoped chains: `Select`, `Order("age desc, name")`, `Limit`, `Offset`. Cancel with `Limit(-1)` / `Offset(-1)`.

DON'T
- Don't reuse a struct that already has its PK set as a query target — a stale PK becomes an extra `AND id = ?` and silently yields "not found". Zero the PK first.
- Don't treat `Find` like `First`: `Find` on a single object scans the whole table (non-deterministic, unindexed). Use `First` or `Limit(1)`.

### Save vs Updates — the zero-value trap

DO
- Partial update from a **map** → writes exactly the keys given, including zeros: `db.Model(&u).Updates(map[string]any{"name": "x", "active": false})`.
- Partial update from a **struct** → **only non-zero fields** are written (`0`, `""`, `false`, `nil` are skipped). To force zeros, name them: `db.Model(&u).Select("Name", "Active").Updates(u)`.
- Single column: `db.Model(&u).Update("age", 0)` (requires a WHERE — a PK on the model counts).

DON'T
- Don't expect `Updates(struct{Active:false})` to persist `false` — it's a zero value, it's dropped. This is the #1 GORM data bug. Use a map or `Select`.
- Don't reach for `Save` to do a partial update. `Save` writes **all** fields (`Select(*)`); with no PK it INSERTs, with a PK it full-UPDATEs, and if 0 rows match it falls back to `Create`. Prefer `Select("*").Updates(&u)` when you want "update all, never insert". `Save` + `Model` is undefined behavior.

### Associations & Preload (N+1)

DO
- Eager-load with `Preload("Orders").Preload("Profile").Find(&users)` — one query per association (`... WHERE user_id IN (...)`), avoiding N+1.
- Nested: `Preload("Orders.OrderItems.Product")`. All direct assocs: `Preload(clause.Associations)` (does **not** recurse into nested).
- Constrain a preload: `Preload("Orders", "state <> ?", "cancelled")` or `Preload("Orders", func(db *gorm.DB) *gorm.DB { return db.Order("amount DESC") })`.
- For **one-to-one** (`belongs to` / `has one`), prefer `Joins("Company")` — single LEFT JOIN, one round-trip, cheaper than Preload.

DON'T
- Don't loop and lazy-load per row — that's the N+1. Preload/Joins up front.
- Don't use `Joins`-preload for `has many` / `many2many` — join-preload is one-to-one only; row fan-out corrupts results. Use `Preload` there.

### Transactions

DO
- Prefer the closure: `db.Transaction(func(tx *gorm.DB) error { ... })`. Return non-nil → rollback; return nil → commit. Use `tx` inside, never the outer `db`.
- Nested transactions and `SavePoint("sp1")` / `RollbackTo("sp1")` are supported.
- Manual `db.Begin()` / `Commit()` / `Rollback()` only when the closure won't fit; pair with `defer` + `recover()` to roll back on panic.

DON'T
- Don't ignore the returned error — an un-checked create inside the closure that you don't `return` won't trigger rollback.
- Perf: high-volume writes not needing a wrapper txn → `SkipDefaultTransaction: true` (config or session); GORM otherwise wraps every write (~30% overhead).

### Context

DO
- Thread `ctx` through every call: `db.WithContext(ctx).Find(&users)`. It's goroutine-safe and enables cancellation.
- Enforce deadlines: `ctx, cancel := context.WithTimeout(...)`, `defer cancel()`, then `db.WithContext(ctx)`.

### Errors

DO
- Check the terminal `.Error`: `if err := db.First(&u, id).Error; err != nil { ... }`.
- Not found: `errors.Is(err, gorm.ErrRecordNotFound)` (from `First`/`Last`/`Take`).
- With `TranslateError: true`: `errors.Is(err, gorm.ErrDuplicatedKey)`, `gorm.ErrForeignKeyViolated`.

### Security — parameterize everything

DO
- `Where("name = ?", name)` and `Raw("... WHERE id = ?", id).Scan(&x)` / `Exec("... = ?", v)` — `?` binds the value, never interpolates.
- Map/struct/slice conditions bind automatically: `Where(map[string]any{...})`, `Where([]int{1,2})` → `IN (?)`.

DON'T
- Never `fmt.Sprintf`/concatenate user input into `Where`, `Raw`, `Exec`, `Order`, or `Select`. `?` covers **values**; for dynamic column/sort names, validate against an allowlist — placeholders can't parameterize identifiers.
- Watch string-PK lookups (`First(&u, userInput)`) — GORM's own docs flag these for injection care; prefer `First(&u, "id = ?", userInput)`.

### Migrations — AutoMigrate is DEV-ONLY

DO
- Dev/prototyping: `db.AutoMigrate(&User{}, &Order{})` — creates tables, missing columns, indexes, FKs; widens/relaxes some column types.
- Prod: use a **versioned** migration tool as the source of truth — `golang-migrate`, `pressly/goose`, or **Atlas** (Atlas can diff GORM models → versioned SQL). Review + apply in CI.
- Need programmatic DDL? Use the `db.Migrator()` interface (`CreateTable`, `AddColumn`, `DropColumn`, `HasIndex`, `RenameColumn`, ...).

DON'T
- Never let `AutoMigrate` own prod schema. It **won't drop unused columns** (by design, to protect data), won't cleanly reconcile renames (rename reads as drop+add → data loss risk) or index/constraint removals, and has no down-migrations or history. Silent drift ensues.
- Don't run `AutoMigrate` on every boot in prod — no ordering, no review, no rollback.

### Sources
- https://gorm.io/docs/connecting_to_the_database.html
- https://gorm.io/docs/query.html
- https://gorm.io/docs/update.html
- https://gorm.io/docs/preload.html
- https://gorm.io/docs/transactions.html
- https://gorm.io/docs/context.html
- https://gorm.io/docs/error_handling.html
- https://gorm.io/docs/migration.html
