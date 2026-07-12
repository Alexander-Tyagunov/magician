# fastify — Performance & testing

Node/JS/TS lore lives elsewhere; this is Fastify-specific. Current: **Fastify v5** (docs v5.9.x). v5 requires **Node.js ≥ 20**. v4 (Node ≥ 18) is EOL as of 2025 — treat new work as v5.

## Why Fastify is fast — DO

- DO attach a **response schema** per route. Fastify compiles it with `fast-json-stringify`, which is dramatically faster than `JSON.stringify` and strips fields not in the schema (prevents accidental data leaks).
  ```js
  fastify.get('/user/:id', {
    schema: {
      params: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
      response: { 200: { type: 'object', properties: { id: { type: 'string' }, name: { type: 'string' } } } }
    }
  }, handler)
  ```
- DO key response schemas by status code, or `'2xx'` / `default`. Content-type variants go under a `content` map.
- DO validate input with the built-in **Ajv v8** compiler (`body`, `querystring`, `params`, `headers`). It coerces types, applies defaults, and strips unknown props (`removeAdditional`) by default.
- DO prefer static/parametric routes on hot paths. RegExp routes and version constraints degrade the router.
- DO prefer Fastify **plugins/hooks** over generic Express-style middleware on perf-sensitive paths.

## Why Fastify is fast — DON'T

- DON'T enable Ajv `allErrors: true` on untrusted input — it does more work per request and eases DoS. It is `false` by default; keep it.
- DON'T return unschema'd large objects on hot paths and expect fast-json-stringify — no schema means fallback to `JSON.stringify`.
- DON'T rely on v4 schema shorthand: **`jsonShortHand` was removed in v5**. Every schema needs full JSON Schema incl. `type`.
- v5 note: Ajv `ajv-formats` now **enforces timezone** in `time`/`date-time`. Use `iso-time` / `iso-date-time` for optional TZ.

## Logging (pino) — DO / DON'T

- DO enable at construct time: `fastify({ logger: true })` or `{ logger: { level: 'info' } }`. Logging is **off by default** and **cannot be turned on at runtime**.
- DO log per-request via `request.log.info(...)`; outside handlers use `fastify.log`. Each request gets an auto request-id (`requestIdHeader`, `genReqId`).
- DO redact secrets with pino's low-overhead `redact`:
  ```js
  fastify({ logger: { redact: ['req.headers.authorization'], level: 'info' } })
  ```
- **v5 breaking:** a custom logger instance goes in **`loggerInstance`**, not `logger`. `logger` now only builds a pino logger.
- DON'T install `pino-pretty` in prod — it's a dev dependency; use `true` in prod, `pino-pretty` in dev, `false` in test.
- DON'T throw inside a log serializer — it can terminate the process. Body isn't available in the `req` serializer (runs before parse); log it in a `preHandler`.

## Don't block the event loop — DO / DON'T

- DON'T run CPU-heavy sync work (crypto, large JSON, image/PDF, sync fs) in a handler — it stalls every connection.
- DO offload to worker threads / child processes / a queue; keep handlers I/O-bound and `await`ed.
- DO shed load with **`@fastify/under-pressure`** (limits: `maxEventLoopDelay`, `maxHeapUsedBytes`, `maxRssBytes`, `maxEventLoopUtilization`) — returns `503` when thresholds trip.
- DO run behind a reverse proxy (Nginx/HAProxy) for TLS/redirects/scaling — direct internet exposure is an anti-pattern per the docs.
- DO listen on `0.0.0.0` in Kubernetes (default bind is `127.0.0.1`, so readiness probes fail otherwise).

## Reply lifecycle: return vs reply.send — DO / DON'T

- DO **return** the payload (or a promise) from an `async` handler — idiomatic and equivalent to `reply.send`.
  ```js
  fastify.get('/', async () => ({ hello: 'world' }))       // return
  fastify.get('/', async (req, reply) => { reply.send({ hello: 'world' }) }) // send
  ```
- DON'T mix both in one handler. If you use `reply.send`, don't also return a value; if returning, don't call `send`. For streams in async handlers you **must** `return reply.send(stream)` (or `await` it) so Fastify doesn't resolve early.
- DO reject/throw an object with `statusCode` (or `status`) + `message` to control error status; unhandled async rejection defaults to **500**.
- DO pass an `Error` to get a structured `{ error, code, message, statusCode }` body. Customize with `setErrorHandler` — but then **you own logging**. Never leak stack traces to clients.
- Streams: no `Content-Type` → `application/octet-stream`; streams bypass response schema validation (sent as-is).
- Use `reply.hijack()` to take over the raw response (skips hooks + Fastify handling); call before `send`. `reply.raw` (Node `http.ServerResponse`) skips cookies/serialization — use at your own risk.
- **v5 breaking:** `reply.redirect(url, code?)` (url first). `reply.getResponseTime()` removed → `reply.elapsedTime`. Mutating `reply.sent` forbidden → use `reply.hijack()`.

## Testing with fastify.inject — DO / DON'T

- DO test with **`fastify.inject()`** (built on `light-my-request`) — fake HTTP, no socket. It auto-awaits `ready()` so all plugins boot first.
  ```js
  const res = await app.inject({ method: 'GET', url: '/user/1', headers, payload })
  assert.equal(res.statusCode, 200)
  assert.deepEqual(res.json(), { id: '1', name: 'Ada' })
  ```
- DO split **`app.js`** (builds/returns the instance) from **`server.js`** (calls `listen`) so tests import the app without binding a port.
- DO `await app.close()` after each test (`t.after(...)`) to drain plugins/connections (`onClose` hooks fire).
- Callback, chainable (`.get('/').end(cb)`), and promise/await styles are all supported.
- For real-socket tests: `await app.ready()` + SuperTest(`app.server`), or `await app.listen()` + global `fetch`/undici (Node ≥ 18).

## TypeScript type providers — DO / DON'T

- DO use a type provider so JSON Schema drives request types — no manual route generics. Official wrappers: `@fastify/type-provider-typebox`, `@fastify/type-provider-json-schema-to-ts`, `@fastify/type-provider-zod`.
  ```ts
  import { TypeBoxTypeProvider } from '@fastify/type-provider-typebox'
  const app = fastify().withTypeProvider<TypeBoxTypeProvider>()
  app.get('/', { schema: { querystring: Type.Object({ q: Type.String() }) } },
    (req) => req.query.q) // typed
  ```
- DO call `withTypeProvider()` **again in each encapsulated scope/plugin** — provider types don't propagate globally.
- DO export a `FastifyInstance<..., TypeBoxTypeProvider>` alias to keep inference across files.
- **v5 note:** validator and serializer type providers are now **separate types** (shared in v4).
- Zod: import from `zod/v4` and set `validatorCompiler`/`serializerCompiler` explicitly.

## Version quick-ref

- **v5** (Node ≥ 20): `loggerInstance` for custom loggers; `jsonShortHand` removed; full JSON Schema required; `useSemicolonDelimiter` now **false**; `params` has no prototype (use `Object.hasOwn`); `request.socket` not `request.connection`; `.listen({ port })` only; reference-type decorators banned; native Diagnostics Channel.
- **v4** (Node ≥ 18, EOL): custom logger via `logger`; shorthand schema allowed; old `redirect(code, url)`.

## Sources

- https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/
- https://fastify.dev/docs/latest/Reference/Logging/
- https://fastify.dev/docs/latest/Reference/Reply/
- https://fastify.dev/docs/latest/Reference/Type-Providers/
- https://fastify.dev/docs/latest/Guides/Testing/
- https://fastify.dev/docs/latest/Guides/Recommendations/
- https://fastify.dev/docs/latest/Guides/Migration-Guide-V5/
- https://github.com/fastify/under-pressure
