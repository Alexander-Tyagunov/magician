# graphql — deep dive

> On-demand companion to `lore/graphql.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Schema design](#schema-design) · [Resolvers & the N+1 problem](#resolvers-and-dataloader) · [Server & security](#server-and-security)

## Schema design <a id="schema-design"></a>

Server-agnostic schema doctrine. Assumes JS/TS/Node lore exists elsewhere. Verify version facts against official docs before asserting.

### Schema-first vs code-first

**DO** pick one source of truth and enforce it.
- **Schema-first**: hand-write SDL, wire a resolver map. Apollo Server 5 (GA; behavior ~unchanged from v4, migrate in minutes; AS3 EOL Oct 2024). SDL is the contract.
- **Code-first**: derive SDL from typed code. NestJS 11 `@nestjs/graphql`: `@ObjectType`, `@Field`, `@InputType`, `@Resolver`, `@Query`, `@Mutation`, `@Args`; `GraphQLModule.forRoot<ApolloDriverConfig>({ driver: ApolloDriver, autoSchemaFile: true })` emits SDL in-memory.

**DO** design query-driven: model the schema on how clients consume data, not how the DB stores it.
**DON'T** leak persistence shape (join tables, FK columns, ORM entities) into the public graph.
**DON'T** mix both paradigms in one service — the generated vs handwritten SDL will drift.

### Nullability

Fields are **nullable by default**; `!` makes non-null. A non-null field that resolves to null errors and **null-bubbles** up to the nearest nullable parent.

```graphql
type Book { id: ID!  title: String!  author: Author }  # author may be null
```
List positions are independent: `[Book!]!` = non-null list of non-null items; `[Book]!` = non-null list that may contain nulls; `[Book!]` = nullable list, non-null items. Empty list is always valid.

**DO** make truly-always-present fields (`id`, timestamps) non-null.
**DON'T** blanket-`!` fields that touch a network/DB/downstream — one failure nukes the whole selection. Prefer nullable + a typed error, or a result union.
**DON'T** add `!` to an existing nullable field — that is a **breaking change** for clients.

### Naming

`camelCase` fields/args · `PascalCase` types, enums, interfaces, unions · `ALL_CAPS` enum values. Add Markdown descriptions (`"""..."""`) to every type/field — they drive tooling and discovery.

### Enums

**DO** use enums for closed, known sets; they serialize as strings and validate input for free.
**DON'T** use enums for open/user-extensible sets (tags, currencies you keep adding) — adding a value clients don't handle can break exhaustive switches; prefer a scalar there.

### Input types

`input` types carry structured args. Fields may only be scalars, enums, or other input types — **no output object types, no interfaces/unions, no resolvers**.
```graphql
input CreateBookInput { title: String!  authorId: ID! }
type Mutation { createBook(input: CreateBookInput!): CreateBookPayload! }
```
**DO** wrap mutation args in a single `input` for evolvability; return a dedicated `Payload` type.
**DON'T** blindly share one input across create and update (update usually wants all-optional). NestJS: derive with `PartialType(CreateInput)` under `@InputType()`.
**DON'T** reuse the same input between Query and Mutation "to save typing" — their needs diverge.

### Mutations

**DO** return the mutated entity (and affected siblings) so clients skip a refetch.
**DO** consider a `MutationResponse`-style payload (`success`, `message`/`code`, plus data) for uniform error handling. Top-level mutation fields resolve **serially** in listed order.

### Interfaces & unions

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

### Pagination — Relay cursor connections

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

### Versionless evolution

GraphQL clients select fields, so **evolve additively — do not version the endpoint** (`/v2` is an anti-pattern).
**DO**: add new optional fields/types/args; add nullable fields; add enum values (cautiously).
**DON'T** (breaking): remove/rename a field, type, arg, or enum value; add `!` to an existing nullable field; make a nullable arg required; narrow a return type.
Deprecate, don't delete:
```graphql
type Book { title: String!  name: String @deprecated(reason: "Use `title`.") }
```
`@deprecated(reason:)` applies to field & enum-value definitions everywhere; on argument & input-field definitions since the GraphQL Oct 2021 spec (confirm your server supports it). Code-first (NestJS): `@Field({ deprecationReason: '...' })`, `registerEnumType(E, { valuesMap: { OLD: { deprecationReason: '...' } } })`, or `@Directive('@deprecated(reason: "...")')`. Track field usage before removing.

### Avoid over-nesting

**DO** keep the graph shallow and let clients traverse relationships explicitly.
**DON'T** pre-nest deep object chains "for convenience" — deep default selections invite unbounded, expensive queries.
**DO** bound depth/cost in production: query-depth + complexity limits, pagination on every list, persisted queries where possible.

### N+1 / resolver performance

Naive per-field resolvers fire one DB call per parent row (N+1). **DO** batch with DataLoader: batch fn takes `keys[]`, returns a Promise of an array **same length and order** as keys (missing → `null`/`Error` at that index). **New loader per request** — loaders cache, so a shared instance leaks data across users. `load(key)` / `loadMany(keys)`.
```js
const userLoader = new DataLoader(async (ids) => {
  const rows = await db.users.byIds(ids);
  const map = new Map(rows.map(r => [r.id, r]));
  return ids.map(id => map.get(id) ?? null);   // preserve order
});
```

### Security (call out where relevant)

- **Validate/sanitize** every input arg at the resolver boundary; enum/scalar types are a first gate, not the whole check.
- **Parameterize** all DB access (defer ORM specifics to ORM lore) — never string-build queries from args.
- **Never leak internals**: Apollo Server only omits the `stacktrace` extension when `NODE_ENV=production` — it does **not** mask error messages by default. Add a `formatError` hook to redact internal messages, and wrap non-`GraphQLError` throwables as generic `INTERNAL_SERVER_ERROR`.
- **Transport hardening** at the HTTP layer (defer to framework lore): security headers (helmet), deliberate CORS allowlist, gate introspection/playground in prod.
- **Cost controls**: depth/complexity limits, pagination caps, timeouts, rate limiting — one crafted query can DoS an unbounded graph.
- **Never** expose secrets as fields; enforce authz in the resolver, not by hiding fields client-side.

### Sources

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

## Resolvers & the N+1 problem <a id="resolvers-and-dataloader"></a>

The central GraphQL performance trap: a naive nested resolver fires one DB query per
parent row. DataLoader (per-request batch + cache) is the fix. JS/TS/Node lore is
separate; this is GraphQL/framework specifics.

### Resolver signature — DO

- Know the four positional args, in order: `(parent, args, contextValue, info)`.
  - `parent` — return value of the resolver one level up (aka `source`/`root`). Top-level
    fields get `rootValue`.
  - `args` — the field's GraphQL arguments, e.g. `{ id: "4" }`.
  - `contextValue` — per-operation shared object (auth, DataLoaders, db handles).
  - `info` — execution state (field name, path, selection set). Rarely needed.
- Return a value, `null`, an array (list fields only), or a `Promise` of any of those.
  `async` resolvers are first-class.
- Let default resolvers do trivial work: if `parent[fieldName]` exists Apollo returns it
  (calling it if it's a function). Only write a resolver when you must fetch/transform.
- Understand the chain: object fields resolve subfields until the query "bottoms out" at
  scalars; sibling subfields run in parallel — order is not guaranteed.

### Resolver signature — DON'T

- DON'T mutate `contextValue` destructively, or rely on resolver execution order / shared
  mutable module state between resolvers.
- DON'T put business logic in resolvers. Resolvers are a thin adapter: read args/context,
  call a service, return. Keep validation, authz rules, DB access, and orchestration in
  service/domain modules so they're testable and reusable outside GraphQL.

```ts
// thin resolver → delegate
Query: {
  user: (_p, { id }, { services, loaders }) => services.users.byId(id),
},
User: {
  posts: (user, _a, { loaders }) => loaders.postsByAuthor.load(user.id),
},
```

### The N+1 problem — DO

- Recognize it: a list field (N parents) with a nested resolver that queries per parent →
  1 query for the list + N queries for children.
- Batch with DataLoader: collect the keys requested within one tick, issue ONE batched
  query (`WHERE id IN (...)` or equivalent), scatter results back.
- Also cache within the request: repeated `load(sameKey)` dedupes to one fetch.

### The N+1 problem — DON'T

- DON'T "fix" it with a giant join in the root resolver — that breaks GraphQL's per-field
  selection and defeats partial queries.
- DON'T reach for a request-scoped cache library; DataLoader gives you batch + memo free.

### DataLoader (graphql/dataloader, current v2.x — v2.2.3, Dec 2024) — DO

- Construct: `new DataLoader(batchFn, options?)`. Each instance owns its own memo cache.
- Honor the batch-function contract exactly:
  - Input: an array of keys. Output: `Promise<Array>` (or sync `Array`).
  - The result array MUST be the same length AND same order as `keys`.
  - Represent a miss as `null`; represent a per-key failure as an `Error` value at that
    index (it gets cached). A fully rejected promise is NOT cached.
- Use the methods: `load(key) → Promise`, `loadMany(keys)` (always resolves; failures are
  `Error`s in-place), `clear(key)`, `clearAll()`, `prime(key, value)` (no-op if present).
- Reorder results to match input keys — the DB rarely returns rows in key order:

```ts
const usersLoader = new DataLoader(async (ids: readonly string[]) => {
  const rows = await db.user.findMany({ where: { id: { in: [...ids] } } });
  const byId = new Map(rows.map(r => [r.id, r]));
  return ids.map(id => byId.get(id) ?? null); // same length + order
});
```

- Tune with options when needed: `maxBatchSize`, `cache: false`, `cacheKeyFn` (stringify
  object keys), `batchScheduleFn` (custom window), `cacheMap`, `name` (APM label).
- After a mutation changes an entity, `loader.clear(id)` (or `.prime(id, fresh)`) so later
  reads in the same request don't return stale data.

### DataLoader — DON'T (security-critical)

- DON'T share a DataLoader across requests or users. The per-instance cache will leak one
  user's data to another and serve stale reads. Create fresh loaders PER REQUEST, in the
  context factory. This is the #1 DataLoader bug.
- DON'T bake unscoped auth into a shared loader; build it per request with the caller's
  auth token in its closure.
- DON'T treat it as a Redis/Memcache replacement — it's a request-lifetime memo only.
- DON'T let the batch function return a differently-ordered/shorter array — keys then
  silently resolve to the wrong values.

### Context per request (Apollo Server) — DO

- Apollo Server 5 is current (v4 EOL 2026-01-26; requires Node ≥ 20, graphql-js ≥ 16.11).
  The `context` function runs ONCE per request and returns the `contextValue`. This is the
  right place to build per-request DataLoaders and auth scope.

```ts
// Apollo Server 4 & 5 — expressMiddleware
app.use('/graphql', express.json(), expressMiddleware(server, {
  context: async ({ req }) => ({
    user: await authFromHeader(req.headers.authorization), // validate, don't trust
    loaders: createLoaders(),        // fresh per request
    services,
  }),
}));
```

- AS5 import change: `expressMiddleware` moved to `@as-integrations/express4` (or
  `express5`); in AS4 it was `@apollo/server/express4`. `startStandaloneServer` keeps its
  API but AS5 no longer runs on Express. AS5 also defaults
  `status400ForVariableCoercionErrors` to true — bad variables now 400, not 200.

### Context per request (NestJS) — DO

- Config: `GraphQLModule.forRoot<ApolloDriverConfig>({ driver: ApolloDriver, ... })` from
  `@nestjs/graphql` + `@nestjs/apollo`. Drivers: `ApolloDriver`, `ApolloFederationDriver`,
  `MercuriusDriver`. (The `@nestjs/apollo`/`@nestjs/mercurius` package split landed in
  `@nestjs/graphql` v10; current NestJS is v11.) Code-first uses `autoSchemaFile`.
- Resolver decorators: `@Resolver(() => Author)`, `@Query`, `@Mutation`, `@ResolveField`,
  `@Parent()`/`@Root()`, `@Args`, `@Context`, `@Info`. Inject services via the constructor.
- Per-request state: set a `context` factory in `GraphQLModule` options; read it via
  `@Context()` or the `CONTEXT` token. Build DataLoaders there. Prefer per-request loaders
  over `Scope.REQUEST` on hot providers (DI cost).

```ts
@Resolver(() => Author)
export class AuthorsResolver {
  constructor(private authors: AuthorsService) {}
  @Query(() => Author)
  author(@Args('id', { type: () => Int }) id: number) { return this.authors.byId(id); }
  @ResolveField(() => [Post])
  posts(@Parent() a: Author, @Context() ctx) { return ctx.loaders.postsByAuthor.load(a.id); }
}
```

### Security — DON'T

- DON'T trust `args` or headers: validate/sanitize input; parameterize DB access (ORM
  specifics live in ORM lore). Enforce authz in services, not just at the edge.
- DON'T leak internals: mask resolver errors in production (Apollo hides stack traces when
  `NODE_ENV=production`); never return raw DB/driver errors to clients.
- DON'T skip transport hardening: `helmet` headers, a deliberate CORS allow-list (never
  reflect arbitrary `Origin`), and depth/complexity/rate limits so one nested query can't
  fan out unbounded resolvers.

### Sources

- https://www.apollographql.com/docs/apollo-server/data/resolvers
- https://www.apollographql.com/docs/apollo-server/data/context
- https://www.apollographql.com/docs/apollo-server/migration
- https://github.com/graphql/dataloader
- https://the-guild.dev/graphql/dataloader
- https://docs.nestjs.com/graphql/resolvers-map
- https://docs.nestjs.com/graphql/quick-start
- https://graphql.org/learn/execution/

## Server & security <a id="server-and-security"></a>

Framework-specifics only. Assume Node/JS/TS lore lives elsewhere. **Verify your major first**:
`npm ls @apollo/server graphql-yoga graphql` — Apollo Server **v3 is EOL**; use **v4** (current)
or **v5**. Package is `@apollo/server` (the old `apollo-server` umbrella is v2/v3 only).

### Version facts that bite (Apollo)

- **v3→v4**: single package `@apollo/server`; you wire the web framework yourself.
  `apollo-server-express`/`ApolloServer.applyMiddleware` are gone → use `expressMiddleware`
  or `startStandaloneServer`. `server.start()` is now mandatory before serving.
- **v4→v5**: small upgrade. Requires **Node 20+** and **graphql.js 16.11+**. Express is no
  longer bundled — import `expressMiddleware` from the separate **`@as-integrations/express4`**
  (or `@as-integrations/express5`), not `@apollo/server/express4`. `startStandaloneServer` runs
  on Node's raw `http` (no Express). `status400ForVariableCoercionErrors` now defaults **true**
  (was 200 in v4). `precomputedNonce` landing-page option removed.
- v3 `ApolloError`/`toApolloError` are gone — throw `GraphQLError` with `extensions.code`
  (codes in `ApolloServerErrorCode` from `@apollo/server/errors`).

### Server setup — DO

- Start before middleware; put `cors()` + `express.json()` **before** `expressMiddleware`.
  ```ts
  // v4: import { expressMiddleware } from '@apollo/server/express4';
  // v5: import { expressMiddleware } from '@as-integrations/express4';
  import { ApolloServer } from '@apollo/server';
  import { ApolloServerPluginDrainHttpServer } from '@apollo/server/plugin/drainHttpServer';

  const server = new ApolloServer<MyContext>({
    typeDefs, resolvers,
    plugins: [ApolloServerPluginDrainHttpServer({ httpServer })],
  });
  await server.start();
  app.use('/graphql', cors(), express.json(),
    expressMiddleware(server, { context: async ({ req }) => makeCtx(req) }));
  ```
- Use `startStandaloneServer(server)` only for prototypes; move to `expressMiddleware`/Fastify
  once you need CORS tuning, body limits, health checks, or other routes. Keep
  `ApolloServerPluginDrainHttpServer` so in-flight ops finish on shutdown.

### Auth in context — DO

- Authenticate **in the `context` function** (runs per request; no cross-request leakage).
  Attach `user`/scopes; do authorization in resolvers.
  ```ts
  context: async ({ req }) => {
    const user = await getUser(req.headers.authorization ?? '');
    return { user };
  }
  ```
- Throw a typed `GraphQLError` with an HTTP status via `extensions.http`:
  ```ts
  throw new GraphQLError('Not authenticated',
    { extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } } });
  ```
- Field-level checks: inspect `contextValue.user`/roles in resolvers; short-circuit before
  data lookups so unauthorized paths never touch the DB.

### Auth — DON'T

- DON'T throw in `context` to gate a **public** API — it blocks every field. Reserve
  context-level rejection for fully private APIs; use resolver/field checks otherwise.
- DON'T trust client-supplied IDs for ownership — verify `resource.ownerId === user.id`.
- DON'T do authz only in the gateway; resolvers are the real boundary.

### Error masking — DO (never leak internals)

- `includeStacktraceInErrorResponses` defaults `true` but is **`false` when `NODE_ENV` is
  `production` or `test`** — so set `NODE_ENV=production`. Never force it `true` in prod.
- Mask unexpected errors with `formatError`; unwrap resolver-wrapped errors first:
  ```ts
  import { unwrapResolverError } from '@apollo/server/errors';
  formatError: (formatted, error) => {
    if (unwrapResolverError(error) instanceof DBError) return { message: 'Internal server error' };
    return formatted; // keep validation/user errors intact
  }
  ```
- Log the full error server-side; return a generic message + stable `extensions.code` to clients.

### Error masking — DON'T

- DON'T return raw DB/ORM errors, SQL, file paths, or stack traces.
- DON'T echo field-suggestion hints ("Did you mean …") in prod — they leak schema shape
  (disable via graphql-armor `blockFieldSuggestions`).

### Introspection & landing page — DO / the debate

- `introspection` defaults `true`, **`false` when `NODE_ENV=production`** — keep it off in prod.
- **Debate**: disabling introspection is *obfuscation, not security* — schemas are guessable
  and field-suggestion leaks reveal types. Treat "disable introspection" as defense-in-depth,
  **not** a substitute for auth/authz and query-cost limits. If you need internal tooling,
  gate introspection by auth rather than a global flag.
- Prod landing page: use `ApolloServerPluginLandingPageProductionDefault()` or fully disable
  with `ApolloServerPluginLandingPageDisabled()` (`@apollo/server/plugin/disabled`).
- `csrfPrevention` is **on by default in v4+** (blocks simple GET/non-preflighted mutations);
  keep it on. Only widen `requestHeaders` for known non-Apollo clients.

### Depth / complexity / cost limiting — DO (mandatory)

- A public GraphQL endpoint **must** cap query cost — nested/recursive queries are a DoS vector.
- Easiest: **GraphQL Armor** (works on Apollo Server and Yoga/Envelop):
  ```ts
  import { ApolloArmor } from '@escape.tech/graphql-armor';
  const armor = new ApolloArmor();               // maxDepth, maxAliases, maxDirectives,
  const p = armor.protect();                     // maxTokens, costLimit, characterLimit,
  new ApolloServer({ typeDefs, resolvers, ...p });// blockFieldSuggestions
  // merge with your own: plugins:[...p.plugins, mine], validationRules:[...p.validationRules, mine]
  ```
- Yoga/Envelop: per-plugin (`@escape.tech/graphql-armor-max-depth` → `maxDepthPlugin`),
  plus `useDisableIntrospection`, and rate limiting via envelop `useRateLimiter`.
- Set max depth (~7–10), a cost/complexity budget, alias & token caps, and a body-size limit
  (`express.json({ limit })`). Prefer static cost analysis over pure depth.

### Rate limiting — DO

- Rate-limit at the HTTP edge (proxy / `express-rate-limit`) AND per-operation/field
  (envelop `useRateLimiter`, or per-field in resolvers keyed by user/IP).
- HTTP-level alone is weak: one POST can carry an expensive query — pair it with cost limits.

### Persisted queries — DO / DON'T

- **APQ** (`persistedQueries`, on by default; disable with `persistedQueries: false`) is a
  **bandwidth optimization** (client sends a hash) — it is **not** an allowlist and adds no security.
- For real hardening use a **trusted-documents / persisted-query safelist**: register the exact
  operations the client ships and **reject anything not on the list** in prod. This eliminates
  arbitrary queries — the strongest defense against query-cost abuse.

### General security — DON'T

- DON'T skip `helmet`, deliberate CORS, and TLS at the HTTP layer (see express/fastify lore).
- DON'T string-concat args into DB calls — parameterize (ORM lore).
- DON'T expose mutations without CSRF protection and input validation on every argument.

### Sources

- https://www.apollographql.com/docs/apollo-server/migration — v4→v5 breaking changes
- https://www.apollographql.com/docs/apollo-server/api/apollo-server — config defaults: introspection, persistedQueries, csrfPrevention, includeStacktraceInErrorResponses
- https://www.apollographql.com/docs/apollo-server/data/errors — formatError, ApolloServerErrorCode, unwrapResolverError
- https://www.apollographql.com/docs/apollo-server/security/authentication — auth in context, GraphQLError
- https://the-guild.dev/graphql/envelop/plugins — depth/rate/introspection plugins (Yoga/Envelop)
- https://escape.tech/graphql-armor/docs/getting-started — ApolloArmor / EnvelopArmor wiring
- https://graphql.org/learn/ — GraphQL spec fundamentals
