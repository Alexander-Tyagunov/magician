# graphql — Server & security

Framework-specifics only. Assume Node/JS/TS lore lives elsewhere. **Verify your major first**:
`npm ls @apollo/server graphql-yoga graphql` — Apollo Server **v3 is EOL**; use **v4** (current)
or **v5**. Package is `@apollo/server` (the old `apollo-server` umbrella is v2/v3 only).

## Version facts that bite (Apollo)

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

## Server setup — DO

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

## Auth in context — DO

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

## Auth — DON'T

- DON'T throw in `context` to gate a **public** API — it blocks every field. Reserve
  context-level rejection for fully private APIs; use resolver/field checks otherwise.
- DON'T trust client-supplied IDs for ownership — verify `resource.ownerId === user.id`.
- DON'T do authz only in the gateway; resolvers are the real boundary.

## Error masking — DO (never leak internals)

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

## Error masking — DON'T

- DON'T return raw DB/ORM errors, SQL, file paths, or stack traces.
- DON'T echo field-suggestion hints ("Did you mean …") in prod — they leak schema shape
  (disable via graphql-armor `blockFieldSuggestions`).

## Introspection & landing page — DO / the debate

- `introspection` defaults `true`, **`false` when `NODE_ENV=production`** — keep it off in prod.
- **Debate**: disabling introspection is *obfuscation, not security* — schemas are guessable
  and field-suggestion leaks reveal types. Treat "disable introspection" as defense-in-depth,
  **not** a substitute for auth/authz and query-cost limits. If you need internal tooling,
  gate introspection by auth rather than a global flag.
- Prod landing page: use `ApolloServerPluginLandingPageProductionDefault()` or fully disable
  with `ApolloServerPluginLandingPageDisabled()` (`@apollo/server/plugin/disabled`).
- `csrfPrevention` is **on by default in v4+** (blocks simple GET/non-preflighted mutations);
  keep it on. Only widen `requestHeaders` for known non-Apollo clients.

## Depth / complexity / cost limiting — DO (mandatory)

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

## Rate limiting — DO

- Rate-limit at the HTTP edge (proxy / `express-rate-limit`) AND per-operation/field
  (envelop `useRateLimiter`, or per-field in resolvers keyed by user/IP).
- HTTP-level alone is weak: one POST can carry an expensive query — pair it with cost limits.

## Persisted queries — DO / DON'T

- **APQ** (`persistedQueries`, on by default; disable with `persistedQueries: false`) is a
  **bandwidth optimization** (client sends a hash) — it is **not** an allowlist and adds no security.
- For real hardening use a **trusted-documents / persisted-query safelist**: register the exact
  operations the client ships and **reject anything not on the list** in prod. This eliminates
  arbitrary queries — the strongest defense against query-cost abuse.

## General security — DON'T

- DON'T skip `helmet`, deliberate CORS, and TLS at the HTTP layer (see express/fastify lore).
- DON'T string-concat args into DB calls — parameterize (ORM lore).
- DON'T expose mutations without CSRF protection and input validation on every argument.

## Sources

- https://www.apollographql.com/docs/apollo-server/migration — v4→v5 breaking changes
- https://www.apollographql.com/docs/apollo-server/api/apollo-server — config defaults: introspection, persistedQueries, csrfPrevention, includeStacktraceInErrorResponses
- https://www.apollographql.com/docs/apollo-server/data/errors — formatError, ApolloServerErrorCode, unwrapResolverError
- https://www.apollographql.com/docs/apollo-server/security/authentication — auth in context, GraphQLError
- https://the-guild.dev/graphql/envelop/plugins — depth/rate/introspection plugins (Yoga/Envelop)
- https://escape.tech/graphql-armor/docs/getting-started — ApolloArmor / EnvelopArmor wiring
- https://graphql.org/learn/ — GraphQL spec fundamentals
