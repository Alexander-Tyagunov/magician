# Fastify — core digest

Version cue: Fastify 5 (needs Node 20+). v5 vs v4: full JSON Schema required (must include `type`; `jsonShorthand` gone); `useSemicolonDelimiter` defaults false; custom logger via `loggerInstance`; `.listen({ port })` only; `reply.redirect(url, code?)`; params has null prototype (use `Object.hasOwn`); use `request.routeOptions.*`, `request.socket`, `reply.elapsedTime`.

DO define `schema` per route (`body`/`querystring`/`params`/`headers`) — Ajv 8 validates; share via `addSchema`+`$ref`.
DO add a response schema (`response['2xx']`) — fast-json-stringify speeds output AND blocks leaking fields absent from schema.
DO run DB/async checks in `preHandler`, never Ajv `$async` (DoS).
DO register `@fastify/helmet` (headers), `@fastify/cors` (explicit origins, not `*` with credentials), `@fastify/rate-limit`.
DO keep plugins encapsulated; use `fastify-plugin` to share decorators; await/return in async handlers.
DON'T set Ajv `allErrors:true` or trust user-supplied schemas (`new Function` → DoS/RCE).
DON'T use object/array decorator defaults (shared across requests) or mutate global per request.
DON'T leak stack traces — set `setErrorHandler`; log via built-in pino, not `console`.

Commands: `npm i fastify @fastify/helmet @fastify/cors @fastify/rate-limit` · `fastify start -l info app.js`.

Deep dive when writing non-trivial fastify — read lore/fastify/{schema-and-serialization,plugins-hooks-and-lifecycle,performance-and-testing}.md

## Sources
fastify.dev/docs/latest/ · /Reference/Validation-and-Serialization/ · /Guides/Migration-Guide-V5/
