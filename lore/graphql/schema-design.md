# graphql — Schema design

Server-agnostic schema doctrine. Assumes JS/TS/Node lore exists elsewhere. Verify version facts against official docs before asserting.

## Schema-first vs code-first

**DO** pick one source of truth and enforce it.
- **Schema-first**: hand-write SDL, wire a resolver map. Apollo Server 5 (GA; behavior ~unchanged from v4, migrate in minutes; AS3 EOL Oct 2024). SDL is the contract.
- **Code-first**: derive SDL from typed code. NestJS 11 `@nestjs/graphql`: `@ObjectType`, `@Field`, `@InputType`, `@Resolver`, `@Query`, `@Mutation`, `@Args`; `GraphQLModule.forRoot<ApolloDriverConfig>({ driver: ApolloDriver, autoSchemaFile: true })` emits SDL in-memory.

**DO** design query-driven: model the schema on how clients consume data, not how the DB stores it.
**DON'T** leak persistence shape (join tables, FK columns, ORM entities) into the public graph.
**DON'T** mix both paradigms in one service — the generated vs handwritten SDL will drift.

## Nullability

Fields are **nullable by default**; `!` makes non-null. A non-null field that resolves to null errors and **null-bubbles** up to the nearest nullable parent.

```graphql
type Book { id: ID!  title: String!  author: Author }  # author may be null
```
List positions are independent: `[Book!]!` = non-null list of non-null items; `[Book]!` = non-null list that may contain nulls; `[Book!]` = nullable list, non-null items. Empty list is always valid.

**DO** make truly-always-present fields (`id`, timestamps) non-null.
**DON'T** blanket-`!` fields that touch a network/DB/downstream — one failure nukes the whole selection. Prefer nullable + a typed error, or a result union.
**DON'T** add `!` to an existing nullable field — that is a **breaking change** for clients.

## Naming

`camelCase` fields/args · `PascalCase` types, enums, interfaces, unions · `ALL_CAPS` enum values. Add Markdown descriptions (`"""..."""`) to every type/field — they drive tooling and discovery.

## Enums

**DO** use enums for closed, known sets; they serialize as strings and validate input for free.
**DON'T** use enums for open/user-extensible sets (tags, currencies you keep adding) — adding a value clients don't handle can break exhaustive switches; prefer a scalar there.

## Input types

`input` types carry structured args. Fields may only be scalars, enums, or other input types — **no output object types, no interfaces/unions, no resolvers**.
```graphql
input CreateBookInput { title: String!  authorId: ID! }
type Mutation { createBook(input: CreateBookInput!): CreateBookPayload! }
```
**DO** wrap mutation args in a single `input` for evolvability; return a dedicated `Payload` type.
**DON'T** blindly share one input across create and update (update usually wants all-optional). NestJS: derive with `PartialType(CreateInput)` under `@InputType()`.
**DON'T** reuse the same input between Query and Mutation "to save typing" — their needs diverge.

## Mutations

**DO** return the mutated entity (and affected siblings) so clients skip a refetch.
**DO** consider a `MutationResponse`-style payload (`success`, `message`/`code`, plus data) for uniform error handling. Top-level mutation fields resolve **serially** in listed order.

## Interfaces & unions

- **Interface** = shared field contract; implementers include all fields plus extras.
- **Union** = alternatives with no shared fields.
```graphql
interface Node { id: ID! }
type Textbook implements Node { id: ID!  courses: [Course!]! }
union SearchResult = Book | Author
```
Both need type resolution: schema-first `__resolveType` in the resolver map returns the concrete type name (invalid name → error). Clients select via inline fragments `... on Textbook { ... }`; request `__typename`.
**DO** use a `Result`/error union to model expected failures in the type system instead of throwing.
**DON'T** reach for unions when types share most fields — an interface reads better.

## Pagination — Relay cursor connections

**DO** standardize list pagination on the Relay Cursor Connections spec (stable across servers, tool-friendly).
```graphql
type BookConnection { edges: [BookEdge!]!  pageInfo: PageInfo! }
type BookEdge { node: Book!  cursor: String! }
type PageInfo {
  hasNextPage: Boolean!  hasPreviousPage: Boolean!
  startCursor: String    endCursor: String        # null when empty
}
type Query {
  books(first: Int, after: String, last: Int, before: String): BookConnection!
}
```
Forward: `first`/`after`. Backward: `last`/`before`. Cursors are **opaque** — clients pass them back verbatim; encode position server-side (e.g. base64 of a stable sort key), never expose raw offsets/IDs as the contract.
**DON'T** pass `first` and `last` together — ambiguous.
**DON'T** default to offset/limit for large or mutating datasets — offsets skip/duplicate rows under concurrent writes.
**DO** put connection-level metadata (`totalCount`) on the Connection type, not the edge.

## Versionless evolution

GraphQL clients select fields, so **evolve additively — do not version the endpoint** (`/v2` is an anti-pattern).
**DO**: add new optional fields/types/args; add nullable fields; add enum values (cautiously).
**DON'T** (breaking): remove/rename a field, type, arg, or enum value; add `!` to an existing nullable field; make a nullable arg required; narrow a return type.
Deprecate, don't delete:
```graphql
type Book { title: String!  name: String @deprecated(reason: "Use `title`.") }
```
`@deprecated(reason:)` applies to field & enum-value definitions everywhere; on argument & input-field definitions since the GraphQL Oct 2021 spec (confirm your server supports it). Code-first (NestJS): `@Field({ deprecationReason: '...' })`, `registerEnumType(E, { valuesMap: { OLD: { deprecationReason: '...' } } })`, or `@Directive('@deprecated(reason: "...")')`. Track field usage before removing.

## Avoid over-nesting

**DO** keep the graph shallow and let clients traverse relationships explicitly.
**DON'T** pre-nest deep object chains "for convenience" — deep default selections invite unbounded, expensive queries.
**DO** bound depth/cost in production: query-depth + complexity limits, pagination on every list, persisted queries where possible.

## N+1 / resolver performance

Naive per-field resolvers fire one DB call per parent row (N+1). **DO** batch with DataLoader: batch fn takes `keys[]`, returns a Promise of an array **same length and order** as keys (missing → `null`/`Error` at that index). **New loader per request** — loaders cache, so a shared instance leaks data across users. `load(key)` / `loadMany(keys)`.
```js
const userLoader = new DataLoader(async (ids) => {
  const rows = await db.users.byIds(ids);
  const map = new Map(rows.map(r => [r.id, r]));
  return ids.map(id => map.get(id) ?? null);   // preserve order
});
```

## Security (call out where relevant)

- **Validate/sanitize** every input arg at the resolver boundary; enum/scalar types are a first gate, not the whole check.
- **Parameterize** all DB access (defer ORM specifics to ORM lore) — never string-build queries from args.
- **Never leak internals**: Apollo Server only omits the `stacktrace` extension when `NODE_ENV=production` — it does **not** mask error messages by default. Add a `formatError` hook to redact internal messages, and wrap non-`GraphQLError` throwables as generic `INTERNAL_SERVER_ERROR`.
- **Transport hardening** at the HTTP layer (defer to framework lore): security headers (helmet), deliberate CORS allowlist, gate introspection/playground in prod.
- **Cost controls**: depth/complexity limits, pagination caps, timeouts, rate limiting — one crafted query can DoS an unbounded graph.
- **Never** expose secrets as fields; enforce authz in the resolver, not by hiding fields client-side.

## Sources

- https://graphql.org/learn/ (Schema & Types, Best Practices)
- https://spec.graphql.org/October2021/ (`@deprecated` locations)
- https://relay.dev/graphql/connections.htm (Cursor Connections spec)
- https://www.apollographql.com/docs/apollo-server (v5 GA; v4→v5; v3 EOL)
- https://www.apollographql.com/docs/apollo-server/schema/schema
- https://www.apollographql.com/docs/apollo-server/schema/unions-interfaces
- https://docs.nestjs.com/graphql/quick-start (code-first, ApolloDriver, autoSchemaFile)
- https://docs.nestjs.com/graphql/resolvers (`@Field` description/deprecationReason)
- https://docs.nestjs.com/graphql/unions-and-enums (`registerEnumType` valuesMap)
- https://docs.nestjs.com/graphql/directives (`@Directive('@deprecated')`)
- https://github.com/graphql/dataloader (batch order/length, per-request, load/loadMany)
