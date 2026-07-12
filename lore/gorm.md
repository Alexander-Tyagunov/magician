# GORM — core

Version: GORM v2 = `gorm.io/gorm` + `gorm.io/driver/<db>`; open via `gorm.Open(driver.Open(dsn), &gorm.Config{})`. Legacy v1 (`github.com/jinzhu/gorm`) is EOL — don't start new code on it. Type-safe Generics API (`gorm.G[T](db)`) needs v1.30.0+.

DO
- Parameterize: `db.Where("name = ?", name)`, `db.Raw("... WHERE id = ?", id).Scan(&x)`, `db.Exec("...", args...)`. GORM binds `?` args safely.
- Check `errors.Is(err, gorm.ErrRecordNotFound)` after First/Take/Last (Find on empty is NOT an error).
- Scope every write with `Where`/primary key; GORM blocks global update/delete by default (`ErrMissingWhereClause`).
- Use `Select`/`Omit` to control columns; load relations explicitly with `Preload`/`Joins` (avoid N+1).
- Run real migrations with golang-migrate, goose, or Atlas (Atlas has official GORM provider).

DON'T
- NEVER `fmt.Sprintf` user input into Where/Raw/Exec/Order/Table — that's SQL injection. Column/table names can't be bound, so allowlist them.
- Don't ship `AutoMigrate` as prod source of truth: it adds tables/cols/indexes/FKs but NEVER drops columns and can't express data migrations. Dev/bootstrap only.
- Don't ignore returned errors or `.Error` on chained calls; don't reuse a `*gorm.DB` after a finisher without a fresh session.

Commands: `go get gorm.io/gorm` · `go get gorm.io/driver/postgres`

Deep dive when writing non-trivial gorm — read lore/gorm/{queries-associations-migrations}.md

Sources: gorm.io/docs/{index,query,migration,security}.html · pkg.go.dev/gorm.io/gorm
