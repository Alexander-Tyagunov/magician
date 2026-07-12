# graphql — Resolvers & the N+1 problem

The central GraphQL performance trap: a naive nested resolver fires one DB query per
parent row. DataLoader (per-request batch + cache) is the fix. JS/TS/Node lore is
separate; this is GraphQL/framework specifics.

## Resolver signature — DO

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

## Resolver signature — DON'T

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

## The N+1 problem — DO

- Recognize it: a list field (N parents) with a nested resolver that queries per parent →
  1 query for the list + N queries for children.
- Batch with DataLoader: collect the keys requested within one tick, issue ONE batched
  query (`WHERE id IN (...)` or equivalent), scatter results back.
- Also cache within the request: repeated `load(sameKey)` dedupes to one fetch.

## The N+1 problem — DON'T

- DON'T "fix" it with a giant join in the root resolver — that breaks GraphQL's per-field
  selection and defeats partial queries.
- DON'T reach for a request-scoped cache library; DataLoader gives you batch + memo free.

## DataLoader (graphql/dataloader, current v2.x — v2.2.3, Dec 2024) — DO

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

## DataLoader — DON'T (security-critical)

- DON'T share a DataLoader across requests or users. The per-instance cache will leak one
  user's data to another and serve stale reads. Create fresh loaders PER REQUEST, in the
  context factory. This is the #1 DataLoader bug.
- DON'T bake unscoped auth into a shared loader; build it per request with the caller's
  auth token in its closure.
- DON'T treat it as a Redis/Memcache replacement — it's a request-lifetime memo only.
- DON'T let the batch function return a differently-ordered/shorter array — keys then
  silently resolve to the wrong values.

## Context per request (Apollo Server) — DO

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

## Context per request (NestJS) — DO

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

## Security — DON'T

- DON'T trust `args` or headers: validate/sanitize input; parameterize DB access (ORM
  specifics live in ORM lore). Enforce authz in services, not just at the edge.
- DON'T leak internals: mask resolver errors in production (Apollo hides stack traces when
  `NODE_ENV=production`); never return raw DB/driver errors to clients.
- DON'T skip transport hardening: `helmet` headers, a deliberate CORS allow-list (never
  reflect arbitrary `Origin`), and depth/complexity/rate limits so one nested query can't
  fan out unbounded resolvers.

## Sources

- https://www.apollographql.com/docs/apollo-server/data/resolvers
- https://www.apollographql.com/docs/apollo-server/data/context
- https://www.apollographql.com/docs/apollo-server/migration
- https://github.com/graphql/dataloader
- https://the-guild.dev/graphql/dataloader
- https://docs.nestjs.com/graphql/resolvers-map
- https://docs.nestjs.com/graphql/quick-start
- https://graphql.org/learn/execution/
