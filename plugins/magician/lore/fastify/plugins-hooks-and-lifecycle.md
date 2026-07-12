# fastify — Plugins, hooks & encapsulation

Version-adaptive. Verify against your installed major. **Fastify 5 requires Node.js ≥ 20** (v4 ran on 18/older). API defaults differ between 4 and 5 — flagged inline.

---

## Plugins & encapsulation

Every `register()` creates a **new child scope** (a DAG). Routes, decorators, and hooks added inside are visible to that scope and its descendants — **never to the parent or siblings**. This is the core mental model; internalize it before touching hooks or decorators.

### DO
- Treat each plugin as an isolated context. Register shared things (db pools, auth decorators) at the top level or break encapsulation deliberately.
- Write async plugins: `async function (fastify, opts) { ... }`. Omit `done`.
- Use `prefix` to namespace routes: `fastify.register(routes, { prefix: '/v1' })`.
- Namespace plugin option keys to avoid collisions across plugins.
- `await fastify.ready()` before asserting the app is fully booted (all plugins loaded, hooks/decorators in place).
- Pass options as a **function** `(instance) => ({...})` when a plugin needs state produced by an earlier-registered plugin; it receives a copy of the instance at registration time and reads the latest state per registration order.

### DON'T
- DON'T expect a decorator/hook added inside `register()` to be visible to the parent — it won't be. Use `fastify-plugin` to break out.
- DON'T `await fastify.register(...)` if later code must still mutate that instance's scope. In **Fastify 5**, awaiting a register **finalizes encapsulation** — subsequent mutations won't reflect in the parent.
- DON'T mix callback and promise styles in one plugin. **Fastify 5 forbids** returning a Promise *and* calling `done` — pick one. Mixing caused double-invocation.
- DON'T rely on registration being lazy: plugins load in registration order via `avvio`, at `ready()`/`listen()`.

### Breaking encapsulation — `fastify-plugin`

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

## Lifecycle hooks

Request/reply hooks fire in this fixed order:

```
onRequest → preParsing → preValidation → preHandler → preSerialization → onSend → onResponse
                                     (onError fires on any thrown error, before the error handler)
```

`onTimeout` (socket `connectionTimeout`) and `onRequestAbort` (client disconnect) fire out-of-band.

### DO
- Prefer async hooks; **`done` is unavailable when async/returning a Promise**.
- Do auth/rate-limit in `onRequest` — earliest point, before body parsing. `request.body` is `undefined` here.
- Mutate/validate the parsed payload in `preValidation`/`preHandler`.
- Reshape the response object in `preSerialization`; reshape the serialized bytes in `onSend` (last chance to touch the payload — allowed types: `string`, `Buffer`, `stream`, `ReadableStream`, `Response`, `null`).
- Do metrics/logging in `onResponse` (response already sent).
- Register hooks **inside a plugin** to scope them; all request/reply hooks are encapsulated.
- Add per-route hooks in the route options — they run **last within their category**; arrays allowed.

### DON'T
- DON'T use arrow functions for hooks/handlers if you need `this` — arrows rebind it away from the Fastify instance.
- DON'T mutate the error in `onError` — it's for logging/headers only; you can't pass an error to `done`. Change errors in `setErrorHandler`.
- DON'T try to send a body in `onTimeout`/`onResponse` — the response is gone.
- DON'T assume `onRequestAbort` is reliable — client-disconnect detection isn't guaranteed.

### Application (server) hooks
- `onReady(done)` — after boot, before listening; can't add routes/hooks. Runs serially.
- `onListen(done)` — on listen; errors logged and ignored; skipped under `inject()`/`ready()`.
- `onClose(instance, done)` — release resources on `fastify.close()`; child hooks run before parent. **Only hook not encapsulated.**
- `preClose(done)` — server still listening; for WebSocket/SSE drain.
- `onRoute(routeOptions)` — **synchronous, no callback**; encapsulated. Tag added routes to avoid loops.
- `onRegister(instance, opts)` — on each new scope; **not called** for `fastify-plugin`-wrapped plugins.

---

## Decorators

Add reusable properties/methods to the instance, `Request`, or `Reply`. Declaring shape up front lets V8 keep objects monomorphic — decorate, don't ad-hoc assign.

### DO
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

### DON'T
- DON'T decorate `Request`/`Reply` with a **reference type** (object/array). **Fastify 5 throws** — the reference is shared across every request (memory leak + cross-request data bleed = security bug). Use a per-request `onRequest` assignment, a factory function `decorateRequest('obj', () => ({...}))`, or a getter.
- DON'T use arrow functions as decorator values that need `this`.
- DON'T redeclare the same decorator name in one scope — it throws (redeclaring inside a child `register` scope is fine and shadows locally).

---

## Validation & serialization (plugin-relevant)

### DO
- Attach JSON Schemas per route (`body`, `querystring`, `params`, response) — validation rejects bad input and serialization strips undeclared response fields (prevents accidental leakage).
- **Fastify 5**: supply a **full JSON Schema** including `type` (e.g. `type: 'object'`, `properties`, `required`). The v4 shorthand (`jsonShorthand`) is **removed**.
- Use a response schema to whitelist output fields — never serialize raw DB rows.
- Swap in a custom validator compiler (Zod/TypeBox/etc.) if you don't want raw AJV.

### DON'T
- DON'T rely on v4 defaults under v5:
  - `useSemicolonDelimiter` now defaults to **`false`** (semicolons no longer split querystrings).
  - `request.params` has **no prototype** — use `Object.hasOwn(req.params, 'x')`, not `req.params.hasOwnProperty` (hardens vs prototype pollution).
- DON'T leak stack traces — set a `setErrorHandler` that returns sanitized messages in production; Fastify hides 5xx internals but verify your handler doesn't echo `error.stack`.

### Fastify 5 API renames (bite plugins/hooks)
`request.context` → `request.routeOptions.config`/`.schema`; `request.routerPath` → `request.routeOptions.url`; `reply.getResponseTime()` → `reply.elapsedTime`; `reply.sent = true` → `reply.hijack()`; `reply.redirect(code, url)` → `reply.redirect(url, code)`; `request.connection` → `request.socket`; custom logger via `loggerInstance` (not `logger`). Resolve all v4 deprecation warnings **before** upgrading.

---

## Sources
- https://fastify.dev/docs/latest/Reference/Plugins/
- https://fastify.dev/docs/latest/Reference/Hooks/
- https://fastify.dev/docs/latest/Reference/Decorators/
- https://fastify.dev/docs/latest/Guides/Migration-Guide-V5/
- https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/
- https://github.com/fastify/fastify-plugin
