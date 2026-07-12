# ent (Go schema-as-code ORM)

Schema is Go code (ent/schema); `go generate ./ent` builds a typed client. Distinct from GORM/sqlc — verify vs entgo.io.
Version cue (2026-07): ent v0.14.6, still v0 (API stable-ish, no v1). Atlas is the migration engine. Pin exact version; re-check API.

DO
- Define entities as structs embedding ent.Schema with Fields()/Edges()/Indexes(); create via `ent new User`, then `go generate ./ent`.
- Regenerate after every schema change; commit generated ent/*. Treat generated code as read-only — never hand-edit.
- Query via typed predicates: client.User.Query().Where(user.NameEQ(x)).All(ctx) — generated, parameterized, safe.
- Transactions: client.Tx(ctx) or WithTx(ctx, client, fn); commit/rollback the tx.
- Prod migrations: Atlas versioned (generate + apply SQL files, committed & reviewed).

DON'T
- Never build predicates/SQL from raw string concatenation of user input; stick to generated predicates + args.
- Don't use client.Schema.Create (auto-migrate) as prod source of truth — it's append-only (won't drop cols/indexes) and dev-only.
- Don't enable WithDropColumn/WithDropIndex blindly; don't rely on auto-migrate to rename (it drops+adds).
- Don't use reserved schema names (e.g. Client).

Commands: ent new <Name> | go generate ./ent | atlas migrate diff | atlas migrate apply | client.Schema.Create (dev only)

Deep dive when writing non-trivial ent — read lore/ent/{schema-and-codegen}.md

## Sources
entgo.io/docs/{getting-started,schema-def,crud,migrate,versioned-migrations}; pkg.go.dev/entgo.io/ent
