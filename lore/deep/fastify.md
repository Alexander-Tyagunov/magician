# fastify — deep dive

> On-demand companion to `lore/fastify.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Schema validation & serialization](#schema-and-serialization) · [Plugins, hooks & encapsulation](#plugins-hooks-and-lifecycle) · [Performance & testing](#performance-and-testing)

## Schema validation & serialization <a id="schema-and-serialization"></a>

Version baseline: **Fastify v5** (latest v5.9.x, requires Node.js >= 20). v5 ships **Ajv v8** for validation and **fast-json-stringify** for response serialization. Fastify v4 (v4.29.x) also uses Ajv 8; v3 used Ajv 6. Schemas use JSON Schema (docs target Draft 7).

Two independent jobs, one `schema` object:
- **Validate** incoming `body` / `querystring` / `params` / `headers` (Ajv).
- **Serialize** outgoing responses keyed by status code (fast-json-stringify) — a major throughput win AND a security boundary.

### DO — validate inputs via schema, never by hand

- Attach a `schema` to route options; let Fastify compile it. Four targets:
  ```js
  fastify.post('/user/:id', {
    schema: {
      params:      { type: 'object', properties: { id: { type: 'integer' } }, required: ['id'] },
      querystring: { type: 'object', properties: { q: { type: 'string' } } },
      headers:     { type: 'object', properties: { 'x-api-key': { type: 'string' } }, required: ['x-api-key'] },
      body:        { type: 'object', properties: { name: { type: 'string' } }, required: ['name'], additionalProperties: false }
    }
  }, handler)
  ```
  `query` is an alias for `querystring`. Failures auto-return **400** `{ statusCode, error, message }`; every validation error has `.statusCode === 400`.
- Set `additionalProperties: false` on body/params schemas to reject unexpected keys. Note the default Ajv config has `removeAdditional: true`, so extra props are stripped, not rejected, unless you set this.
- Trust `request.body`/`params`/`query` AFTER validation — Ajv coerces types (`coerceTypes: 'array'`) and applies `useDefaults`, so `?ids=1` becomes `{ ids: ["1"] }` for array schemas.
- Body validation runs only for `application/json` unless you use the `content` keyword to key schemas by MIME type:
  ```js
  body: { content: { 'application/json': { schema: {...} }, 'text/plain': { schema: { type: 'string' } } } }
  ```

### DON'T — hand-validate or trust unvalidated parsers

- DON'T write `if (!req.body.name) return reply.code(400)...`. Declare it `required` in the schema.
- DON'T register a custom content-type parser (regex) and forget a matching `content` schema — unmatched types are **parsed but not validated**. Add a catch-all schema (no `content`) or a `content` key per accepted type.
- DON'T enable `allErrors: true` or `jsonPointers: true` casually — documented DoS risk (CVE-2020-8192). Default `allErrors: false` is intentional.
- DON'T use Ajv `$async` for validation that hits a DB (DoS surface) — do that in a `preHandler` hook instead.
- DON'T pass user-supplied schemas to the compiler — schemas are application code compiled with `new Function()`.

### DO — serialize responses with a `response` schema (perf + security)

- Define output per status code. fast-json-stringify emits **only schema-defined fields** — this prevents accidental leakage of passwords, tokens, internal fields.
  ```js
  schema: {
    response: {
      200:     { type: 'object', properties: { id: { type: 'integer' }, name: { type: 'string' } } },
      '2xx':   { type: 'object', properties: { ok: { type: 'boolean' } } },
      default: { type: 'object', properties: { error: { type: 'string' } } }
    }
  }
  ```
  Keys: exact status (`'201'`), ranges (`'2xx'`, `'4xx'`), or `default` fallback. Per-content-type via nested `content` (supports `*/*`).
- Rely on serialization as a whitelist: a field absent from the response schema is never sent, even if present on the object you return. This is the primary defense against overexposing DB rows.

### DON'T — return raw objects without a response schema

- DON'T `reply.send(userRowFromDb)` on sensitive routes with no `response` schema — every column ships to the client. Define the response shape.
- DON'T assume validation and serialization share config — they're separate compilers (Ajv vs fast-json-stringify).

### DO — share schemas with `addSchema` + `$ref`

- Register reusable schemas (encapsulated to the instance/plugin scope):
  ```js
  fastify.addSchema({ $id: 'user', type: 'object', properties: { id: { type: 'integer' } } })
  // reference by root:
  fastify.get('/u', { schema: { response: { 200: { $ref: 'user#' } } } }, h)
  ```
- `$ref` resolution: `'#foo'` → local `$id: '#foo'`; `'#/definitions/foo'` → local `definitions.foo`; `'user#'` → shared schema by `$id`; `'user#/definitions/foo'` → shared schema's definition. `$ref` works in BOTH validator and serializer.
- Inspect with `getSchema(id)` / `getSchemas()`.

### DON'T — mix addSchema with a fully custom validator

- With a custom validator compiler, `fastify.addSchema` is not seen — register shared schemas on your Ajv instance directly.

### DO — use TypeScript type providers for end-to-end types

- `withTypeProvider<...>()` infers `request.body/query/params` types from the schema. Official providers follow `@fastify/type-provider-{name}`:
  - **TypeBox** — `@fastify/type-provider-typebox`, schemas are JSON Schema, no extra compilers needed:
    ```ts
    const app = Fastify().withTypeProvider<TypeBoxTypeProvider>()
    app.get('/r', { schema: { querystring: Type.Object({ foo: Type.Number() }) } }, (req) => req.query.foo)
    ```
  - **Zod** — `@fastify/type-provider-zod`; MUST wire both compilers:
    ```ts
    app.setValidatorCompiler(validatorCompiler)
    app.setSerializerCompiler(serializerCompiler)
    app.withTypeProvider<ZodTypeProvider>()
    ```
  - **json-schema-to-ts** — `@fastify/type-provider-json-schema-to-ts` (plain JSON Schema, `as const`).
- TypeBox needs no custom compiler (it IS JSON Schema); Zod does — don't forget to set both, or serialization falls back to default JSON.

### DO — customize errors deliberately

- `attachValidation: true` on a route puts the error in `req.validationError` (with raw `.validation`) instead of auto-400 — handle in-route.
- `setErrorHandler((err, req, reply) => ...)`: check `err.validation` (Ajv errors) and `err.validationContext` (value is `body`|`params`|`query`|`headers` — note the context value is `query`, not `querystring`).
- `setSchemaErrorFormatter((errors, dataVar) => Error)` (sync) to shape messages. `ajv-errors` enables per-field `errorMessage`; `ajv-i18n` localizes. Pin `ajv-errors` to the version matching your Fastify's Ajv (v8 on Fastify 4/5).
- Security: default 400 payloads include validator detail. Sanitize via `setErrorHandler` if messages might leak schema/internal info.

### Custom validators / other libraries

- `setValidatorCompiler(({ schema, method, url, httpPart }) => fn)`; use `httpPart` to apply different Ajv instances per target (e.g., disable `coerceTypes` for body only).
- Non-Ajv validators (Joi/yup): the compiled fn MUST return `{ value }` on success or `{ error }` on failure — **never throw** (throwing in async preValidation crashes the process).
- `setSerializerCompiler(...)` / `reply.serializer(fn)` for a custom serializer (must return a string).

### Sources

- https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/
- https://fastify.dev/docs/latest/Reference/Type-Providers/
- https://fastify.dev/docs/latest/ (version/Node baseline)
- https://github.com/fastify/fastify/blob/main/docs/Reference/Type-Providers.md (via context7)

## Plugins, hooks & encapsulation <a id="plugins-hooks-and-lifecycle"></a>

Version-adaptive. Verify against your installed major. **Fastify 5 requires Node.js ≥ 20** (v4 ran on 18/older). API defaults differ between 4 and 5 — flagged inline.

---

### Plugins & encapsulation

Every `register()` creates a **new child scope** (a DAG). Routes, decorators, and hooks added inside are visible to that scope and its descendants — **never to the parent or siblings**. This is the core mental model; internalize it before touching hooks or decorators.

#### DO
- Treat each plugin as an isolated context. Register shared things (db pools, auth decorators) at the top level or break encapsulation deliberately.
- Write async plugins: `async function (fastify, opts) { ... }`. Omit `done`.
- Use `prefix` to namespace routes: `fastify.register(routes, { prefix: '/v1' })`.
- Namespace plugin option keys to avoid collisions across plugins.
- `await fastify.ready()` before asserting the app is fully booted (all plugins loaded, hooks/decorators in place).
- Pass options as a **function** `(instance) => ({...})` when a plugin needs state produced by an earlier-registered plugin; it receives a copy of the instance at registration time and reads the latest state per registration order.

#### DON'T
- DON'T expect a decorator/hook added inside `register()` to be visible to the parent — it won't be. Use `fastify-plugin` to break out.
- DON'T `await fastify.register(...)` if later code must still mutate that instance's scope. In **Fastify 5**, awaiting a register **finalizes encapsulation** — subsequent mutations won't reflect in the parent.
- DON'T mix callback and promise styles in one plugin. **Fastify 5 forbids** returning a Promise *and* calling `done` — pick one. Mixing caused double-invocation.
- DON'T rely on registration being lazy: plugins load in registration order via `avvio`, at `ready()`/`listen()`.

#### Breaking encapsulation — `fastify-plugin`

Wrap a plugin in `fp()` so its decorators/hooks apply to the **parent** scope (shared utilities, db connections, auth). Match the wrapper major to Fastify: **`fastify-plugin` v6 → Fastify 5**, v4 → Fastify 4.

```js
const fp = require('fastify-plugin')
module.exports = fp(async function (fastify, opts) {
  fastify.decorate('db', await connect(opts.url))
}, {
  fastify: '5.x',                 // semver range guard
  name: 'app-db',                 // for dependency graph + collision check
  dependencies: ['app-config'],   // required plugin names (must be loaded)
  decorators: { fastify: ['config'] } // assert decorators exist at boot
})
```

- `fastify` metadata (v5): declare the supported Fastify range; boot fails on mismatch.
- `encapsulate: true` — keep the plugin encapsulated *but still* register a name / validate dependencies. Decorators stay private.
- `prefix` is **ignored** on an `fp`-wrapped plugin.

DON'T reach for the raw `Symbol.for('skip-override')` escape hatch — `fastify-plugin` handles it and gives you the version guard.

---

### Lifecycle hooks

Request/reply hooks fire in this fixed order:

```
onRequest → preParsing → preValidation → preHandler → preSerialization → onSend → onResponse
                                     (onError fires on any thrown error, before the error handler)
```

`onTimeout` (socket `connectionTimeout`) and `onRequestAbort` (client disconnect) fire out-of-band.

#### DO
- Prefer async hooks; **`done` is unavailable when async/returning a Promise**.
- Do auth/rate-limit in `onRequest` — earliest point, before body parsing. `request.body` is `undefined` here.
- Mutate/validate the parsed payload in `preValidation`/`preHandler`.
- Reshape the response object in `preSerialization`; reshape the serialized bytes in `onSend` (last chance to touch the payload — allowed types: `string`, `Buffer`, `stream`, `ReadableStream`, `Response`, `null`).
- Do metrics/logging in `onResponse` (response already sent).
- Register hooks **inside a plugin** to scope them; all request/reply hooks are encapsulated.
- Add per-route hooks in the route options — they run **last within their category**; arrays allowed.

#### DON'T
- DON'T use arrow functions for hooks/handlers if you need `this` — arrows rebind it away from the Fastify instance.
- DON'T mutate the error in `onError` — it's for logging/headers only; you can't pass an error to `done`. Change errors in `setErrorHandler`.
- DON'T try to send a body in `onTimeout`/`onResponse` — the response is gone.
- DON'T assume `onRequestAbort` is reliable — client-disconnect detection isn't guaranteed.

#### Application (server) hooks
- `onReady(done)` — after boot, before listening; can't add routes/hooks. Runs serially.
- `onListen(done)` — on listen; errors logged and ignored; skipped under `inject()`/`ready()`.
- `onClose(instance, done)` — release resources on `fastify.close()`; child hooks run before parent. **Only hook not encapsulated.**
- `preClose(done)` — server still listening; for WebSocket/SSE drain.
- `onRoute(routeOptions)` — **synchronous, no callback**; encapsulated. Tag added routes to avoid loops.
- `onRegister(instance, opts)` — on each new scope; **not called** for `fastify-plugin`-wrapped plugins.

---

### Decorators

Add reusable properties/methods to the instance, `Request`, or `Reply`. Declaring shape up front lets V8 keep objects monomorphic — decorate, don't ad-hoc assign.

#### DO
- `fastify.decorate('name', value, [deps])` — instance-level; bound as `this` in handlers.
- Initialize with the right empty shape: `''` for strings, `null` for objects/functions.
- For per-request state: decorate a placeholder, then set the real value in `onRequest`.
- Pass `dependencies` to fail fast at boot if a prerequisite decorator is missing.
- Use `hasDecorator` / `hasRequestDecorator` / `hasReplyDecorator` to guard.
- **Fastify 5+**: use `getDecorator(name)` / `setDecorator(name, value)` — throw `FST_ERR_DEC_UNDECLARED` on typos/missing, and support TS generics.

```js
async function userPlugin (app) {
  app.decorateRequest('user', null)       // placeholder shape
  app.addHook('onRequest', async (req) => {
    req.user = await authenticate(req)    // fresh per request
  })
}
```

#### DON'T
- DON'T decorate `Request`/`Reply` with a **reference type** (object/array). **Fastify 5 throws** — the reference is shared across every request (memory leak + cross-request data bleed = security bug). Use a per-request `onRequest` assignment, a factory function `decorateRequest('obj', () => ({...}))`, or a getter.
- DON'T use arrow functions as decorator values that need `this`.
- DON'T redeclare the same decorator name in one scope — it throws (redeclaring inside a child `register` scope is fine and shadows locally).

---

### Validation & serialization (plugin-relevant)

#### DO
- Attach JSON Schemas per route (`body`, `querystring`, `params`, response) — validation rejects bad input and serialization strips undeclared response fields (prevents accidental leakage).
- **Fastify 5**: supply a **full JSON Schema** including `type` (e.g. `type: 'object'`, `properties`, `required`). The v4 shorthand (`jsonShorthand`) is **removed**.
- Use a response schema to whitelist output fields — never serialize raw DB rows.
- Swap in a custom validator compiler (Zod/TypeBox/etc.) if you don't want raw AJV.

#### DON'T
- DON'T rely on v4 defaults under v5:
  - `useSemicolonDelimiter` now defaults to **`false`** (semicolons no longer split querystrings).
  - `request.params` has **no prototype** — use `Object.hasOwn(req.params, 'x')`, not `req.params.hasOwnProperty` (hardens vs prototype pollution).
- DON'T leak stack traces — set a `setErrorHandler` that returns sanitized messages in production; Fastify hides 5xx internals but verify your handler doesn't echo `error.stack`.

#### Fastify 5 API renames (bite plugins/hooks)
`request.context` → `request.routeOptions.config`/`.schema`; `request.routerPath` → `request.routeOptions.url`; `reply.getResponseTime()` → `reply.elapsedTime`; `reply.sent = true` → `reply.hijack()`; `reply.redirect(code, url)` → `reply.redirect(url, code)`; `request.connection` → `request.socket`; custom logger via `loggerInstance` (not `logger`). Resolve all v4 deprecation warnings **before** upgrading.

---

### Sources
- https://fastify.dev/docs/latest/Reference/Plugins/
- https://fastify.dev/docs/latest/Reference/Hooks/
- https://fastify.dev/docs/latest/Reference/Decorators/
- https://fastify.dev/docs/latest/Guides/Migration-Guide-V5/
- https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/
- https://github.com/fastify/fastify-plugin

## Performance & testing <a id="performance-and-testing"></a>

Node/JS/TS lore lives elsewhere; this is Fastify-specific. Current: **Fastify v5** (docs v5.9.x). v5 requires **Node.js ≥ 20**. v4 (Node ≥ 18) is EOL as of 2025 — treat new work as v5.

### Why Fastify is fast — DO

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

### Why Fastify is fast — DON'T

- DON'T enable Ajv `allErrors: true` on untrusted input — it does more work per request and eases DoS. It is `false` by default; keep it.
- DON'T return unschema'd large objects on hot paths and expect fast-json-stringify — no schema means fallback to `JSON.stringify`.
- DON'T rely on v4 schema shorthand: **`jsonShortHand` was removed in v5**. Every schema needs full JSON Schema incl. `type`.
- v5 note: Ajv `ajv-formats` now **enforces timezone** in `time`/`date-time`. Use `iso-time` / `iso-date-time` for optional TZ.

### Logging (pino) — DO / DON'T

- DO enable at construct time: `fastify({ logger: true })` or `{ logger: { level: 'info' } }`. Logging is **off by default** and **cannot be turned on at runtime**.
- DO log per-request via `request.log.info(...)`; outside handlers use `fastify.log`. Each request gets an auto request-id (`requestIdHeader`, `genReqId`).
- DO redact secrets with pino's low-overhead `redact`:
  ```js
  fastify({ logger: { redact: ['req.headers.authorization'], level: 'info' } })
  ```
- **v5 breaking:** a custom logger instance goes in **`loggerInstance`**, not `logger`. `logger` now only builds a pino logger.
- DON'T install `pino-pretty` in prod — it's a dev dependency; use `true` in prod, `pino-pretty` in dev, `false` in test.
- DON'T throw inside a log serializer — it can terminate the process. Body isn't available in the `req` serializer (runs before parse); log it in a `preHandler`.

### Don't block the event loop — DO / DON'T

- DON'T run CPU-heavy sync work (crypto, large JSON, image/PDF, sync fs) in a handler — it stalls every connection.
- DO offload to worker threads / child processes / a queue; keep handlers I/O-bound and `await`ed.
- DO shed load with **`@fastify/under-pressure`** (limits: `maxEventLoopDelay`, `maxHeapUsedBytes`, `maxRssBytes`, `maxEventLoopUtilization`) — returns `503` when thresholds trip.
- DO run behind a reverse proxy (Nginx/HAProxy) for TLS/redirects/scaling — direct internet exposure is an anti-pattern per the docs.
- DO listen on `0.0.0.0` in Kubernetes (default bind is `127.0.0.1`, so readiness probes fail otherwise).

### Reply lifecycle: return vs reply.send — DO / DON'T

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

### Testing with fastify.inject — DO / DON'T

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

### TypeScript type providers — DO / DON'T

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

### Version quick-ref

- **v5** (Node ≥ 20): `loggerInstance` for custom loggers; `jsonShortHand` removed; full JSON Schema required; `useSemicolonDelimiter` now **false**; `params` has no prototype (use `Object.hasOwn`); `request.socket` not `request.connection`; `.listen({ port })` only; reference-type decorators banned; native Diagnostics Channel.
- **v4** (Node ≥ 18, EOL): custom logger via `logger`; shorthand schema allowed; old `redirect(code, url)`.

### Sources

- https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/
- https://fastify.dev/docs/latest/Reference/Logging/
- https://fastify.dev/docs/latest/Reference/Reply/
- https://fastify.dev/docs/latest/Reference/Type-Providers/
- https://fastify.dev/docs/latest/Guides/Testing/
- https://fastify.dev/docs/latest/Guides/Recommendations/
- https://fastify.dev/docs/latest/Guides/Migration-Guide-V5/
- https://github.com/fastify/under-pressure
