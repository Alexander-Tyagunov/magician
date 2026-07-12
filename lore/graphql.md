# GraphQL — core

DO run one DataLoader per request; batch fn returns an array the same length+order as keys (null/Error for misses) — kills N+1.
DON'T share a DataLoader across requests (cache leak).
DO disable introspection and error stack traces in production; mask internal errors via formatError (set includeStacktraceInErrorResponses:false).
DO cap query depth, complexity/cost, body size, and timeouts — untrusted queries are the attack surface; reject deep nesting, alias/batch abuse.
DO authenticate in the context fn and authorize per-resolver; validate every arg. Parameterize DB access (see ORM lore); never build queries from raw input.
DO keep csrfPrevention on (AS4+ default), set an explicit CORS allowlist, add helmet.
DON'T leak secrets/PII in the schema, errors, or logs. DON'T trust client IDs without an ownership check.
DO paginate lists (cursor/Relay connections). Choose nullability deliberately — a non-null field's error nulls its parent. Errors ship as HTTP 200 — check data.errors.

Version: Apollo Server 4+ ships no HTTP server — use startStandaloneServer or framework middleware (expressMiddleware). AS5 moved Express middleware to @as-integrations/express4|5. csrfPrevention on by default since v4.

Commands: `npm i @apollo/server graphql dataloader` · `npx graphql-codegen` · `npx get-graphql-schema URL > schema.graphql`

Deep dive when writing non-trivial graphql — read lore/graphql/{schema-design,resolvers-and-dataloader,server-and-security}.md
Sources: graphql.org/learn · apollographql.com/docs/apollo-server · github.com/graphql/dataloader
