# ent — Schema-as-code & codegen

Go graph-ORM. Schemas are Go structs in `ent/schema`; `go generate ./ent` emits a type-safe client. Module path `entgo.io/ent` — pre-1.0 (no `/vN` suffix), so pin an exact version in `go.mod`. Assumes Go foundation lore elsewhere.

## Setup & codegen
DO
- Scaffold: `go run -mod=mod entgo.io/ent/cmd/ent new User Group` → writes `ent/schema/user.go`.
- Keep a `//go:generate` directive in `ent/generate.go`; run `go generate ./ent` after every schema change.
- Enable features on the generate directive: `go run -mod=mod entgo.io/ent/cmd/ent generate --feature privacy,sql/upsert ./schema`.
- Import driver + call `ent.Open(dialect, dsn)` (`github.com/lib/pq` / `jackc/pgx` for Postgres, `go-sql-driver/mysql`, `mattn/go-sqlite3`).

DON'T
- Don't hand-edit files under `ent/` outside `ent/schema/` — regen overwrites them.
- Don't forget `import _ "<proj>/ent/runtime"` in `main` when using schema `Hooks()` or `Policy()` (breaks the schema↔generated cycle; without it they silently don't register).

## Schema definition
Embed `ent.Schema`; each struct = one entity type. Imports: `entgo.io/ent`, `.../schema/field`, `.../schema/edge`, `.../schema/index`.

DO
- Fields: `field.String("name").NotEmpty()`, `field.Int("age").Positive()`, `field.String("nickname").Unique()`, `.Default(...)`, `.Optional()`, `.Nillable()`, `.Immutable()`, `.Sensitive()` (omit from output).
- Edges: `edge.To("pets", Pet.Type)` (owner) + `edge.From("owner", User.Type).Ref("pets").Unique()` (inverse). Self-ref: `edge.To("friends", User.Type)`.
- Indexes: `index.Fields("name", "age").Unique()`; edge-scoped uniqueness via `index.Fields(...).Edges(...)`.
- Mixins: factor shared fields/edges/indexes/hooks into a struct embedding `mixin.Schema` (`entgo.io/ent/schema/mixin`); list in the entity's `Mixin() []ent.Mixin`. Common use: `created_at`/`updated_at`, soft-delete.

DON'T
- Don't use reserved names (`Client`, etc.) as types — collides with generated internals; use a table-name annotation instead.
- Don't put mutually-inverse relations without matching `Ref(...)` — codegen errors or produces two unrelated edges.

## Query builders (type-safe, parameterized)
DO
- `client.User.Query().Where(user.NameEQ("a"), user.AgeGT(18)).Order(ent.Asc(user.FieldName)).All(ctx)`.
- Terminators: `.All(ctx)`, `.First(ctx)`, `.Only(ctx)` (exactly one, else error), `.Count(ctx)`, `.Exist(ctx)`, `.IDs(ctx)`.
- Edge predicates: `user.HasPetsWith(pet.NameEQ("x"))`. Traverse: `client.Group.Query().QueryAdmin().QueryPets().Only(ctx)`.
- Predicates come from the generated per-entity package (`ent/user`) — all values become bound args.

DON'T
- Don't reach for raw SQL to filter — the generated predicates are exhaustive and safe.

## Eager loading (kill N+1)
DO
- `WithX` per edge: `client.User.Query().WithPets().All(ctx)`; read via `u.Edges.Pets`.
- Filter/limit/nest inside: `.WithGroups(func(q *ent.GroupQuery){ q.Limit(5).WithUsers() })`.
- SQL dialects only. ent issues one extra batched query per edge (not per-row) — not a JOIN, but N+1-free.

DON'T
- Don't loop `q.QueryPets()` per parent row — that IS the N+1. Preload with `WithX` up front.
- Don't access `u.Edges.Pets` unloaded — it's empty/`nil`; use `.Edges.PetsOrErr()` when you must detect "not loaded."

## Transactions
DO
- Use the `WithTx` helper (from docs) wrapping `client.Tx(ctx)` → `fn(tx)` → `Commit`/`Rollback`, with `recover()` to roll back on panic.
- Pass `tx.Client()` to functions that expect `*ent.Client` — no signature changes.
- Isolation: `client.BeginTx(ctx, &sql.TxOptions{Isolation: ...})`.

DON'T
- Don't ignore `Rollback` errors; wrap them (`fmt.Errorf("%w: rollback: %v", err, rerr)`).
- Don't query edges off a created entity after commit without `entity.Unwrap()` — otherwise it still targets the closed tx (Unwrap on a non-tx entity panics).

## Hooks & privacy
DO
- Schema hooks: `func (Card) Hooks() []ent.Hook` with `hook.On(fn, ent.OpCreate|ent.OpUpdate)`; type-safe mutation via `hook.CardFunc`. Runtime hooks: `client.Use(...)` / `client.User.Use(...)` for logging/metrics/tracing.
- Filter ops: `hook.If`, `hook.Unless`, `hook.HasFields`, `hook.And/Or`. Order: `Use(f,g,h)` → `f(g(h(...)))`; runtime hooks run before schema hooks.
- Privacy (`--feature privacy`): `func (User) Policy() ent.Policy` returning `privacy.Policy{Query: ..., Mutation: ...}`. Rules return `privacy.Allow` / `privacy.Deny` / `privacy.Skip` (nil = skip to next). Use `privacy.DecisionContext(ctx, privacy.Allow)` to bypass, `privacy.FilterFunc` for viewer-scoped filtering.

DON'T
- Don't rely on app-layer checks alone for authz when privacy fits — policy is enforced on every op regardless of call site.
- Don't forget the `ent/runtime` import (above) — hooks/policies won't fire.

## Security — parameterization & escape hatches
- Generated builders + predicates are always parameterized. Safe by construction; no `fmt.Sprintf` into SQL anywhere.
DON'T
- Don't feed user input into raw escape hatches: `sql/modifier` (`.Modify()`, `sql.Expr`), `sql/execquery` (`client.QueryContext`/`ExecContext`), or predicate `sql.P` raw fragments. If unavoidable, use `?`/`$1` placeholders + args — never string-concatenate input.
- Don't build column/table names or `ORDER BY` from raw user input via modifiers — allow-list them.

## Migrations
- Dev/auto: `client.Schema.Create(ctx)` diffs schema → DB and applies directly. Convenience only.
DO (prod)
- Versioned migrations via Atlas. Simplest: `atlas migrate diff <name> --dir "file://ent/migrate/migrations" --to "ent://ent/schema" --dev-url "docker://postgres/16/dev"` (no feature flag needed).
- Or enable `--feature sql/versioned-migration`, generate `ent/migrate` diff code (`migrate.NamedDiff` / `schema.WithDir`), emit versioned `.sql` + `atlas.sum`.
- Apply: `atlas migrate apply --dir ... --url <dsn>`; gate CI with `atlas migrate lint` / `validate` / `status`. Other tool dirs via `sqltool.NewGooseDir`, `NewGolangMigrateDir`, etc.

DON'T
- Don't run `Schema.Create`/`AutoMigrate`-style auto-apply against production — no history, no review, can't express destructive/renaming steps safely. Versioned files are the source of truth.
- Don't hand-edit a migration without `atlas migrate hash` — a stale `atlas.sum` blocks apply.

## Sources
- https://entgo.io/docs/getting-started/
- https://entgo.io/docs/schema-def
- https://entgo.io/docs/traversals/
- https://entgo.io/docs/eager-load
- https://entgo.io/docs/transactions/
- https://entgo.io/docs/hooks
- https://entgo.io/docs/privacy
- https://entgo.io/docs/versioned-migrations
- https://entgo.io/docs/feature-flags/
