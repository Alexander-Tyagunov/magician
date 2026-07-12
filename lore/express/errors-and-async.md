# express — Errors & async handling

Framework-specifics only. Assume Node/JS/TS lore lives elsewhere. Verify your major
before trusting any snippet: `npm ls express` → Express **4** vs **5** changes async
behavior fundamentally. This is the single biggest 4→5 difference.

## The one fact that matters (version-adaptive)

- **Express 4**: async route handlers/middleware that `throw` or return a **rejected
  promise** are **NOT caught**. Uncaught → unhandled rejection → the request hangs and
  never reaches your error handler. You MUST forward manually.
- **Express 5**: handlers/middleware returning a promise **auto-call `next(value)` on
  reject/throw**. No wrapper needed. Verified: rejected promises route to the 4-arg
  error handler. (If no rejection value, Express passes a default `Error`.)
- **Both versions**: **synchronous** throws inside a handler ARE caught automatically.
  Only *async* is the gap.

## Async errors — DO

- **Express 4**: wrap every `async` handler, or call `next(err)` yourself.
  ```js
  // asyncHandler wrapper — the canonical Express 4 pattern
  const asyncHandler = (fn) => (req, res, next) =>
    Promise.resolve(fn(req, res, next)).catch(next);

  app.get('/user/:id', asyncHandler(async (req, res) => {
    const user = await User.findById(req.params.id);
    res.json(user);
  }));
  ```
- **Express 5**: write the handler plainly — rejections auto-forward.
  ```js
  app.get('/user/:id', async (req, res) => {
    const user = await getUserById(req.params.id); // throw/reject → next(err) auto
    res.send(user);
  });
  ```
- **Callback-style async (both versions)**: forward the error explicitly — this is NOT a
  returned promise, so Express 5's auto-forwarding does not apply.
  ```js
  app.get('/', (req, res, next) => {
    fs.readFile('/nope', (err, data) => err ? next(err) : res.send(data));
  });
  ```
- Errors inside `setTimeout`/event callbacks: `try/catch` and `next(err)` — nothing
  forwards these automatically in any version.

## Async errors — DON'T

- DON'T assume `async` throws are caught in **Express 4**. They are not.
- DON'T pass a non-error truthy value to `next()` expecting normal flow. Anything except
  the string `'route'` marks the request as an error and skips remaining non-error
  handlers. `next('route')` is the *only* non-error string (skips to next route).
- DON'T `next(err)` more than once per request, or after the response started — you can
  trigger the default handler and crash the response.
- DON'T rely on Express 5 auto-forwarding for a handler that returns nothing (no promise
  returned = nothing to catch). `return` the promise or mark the fn `async`.

## Central error handler (4 args) — DO

- Error middleware is defined by its **arity: exactly `(err, req, res, next)`** (4
  params). Express detects it by argument count — omitting `next` breaks detection.
- Register it **last**, after all routes and other `app.use()`.
  ```js
  app.use((err, req, res, next) => {
    if (res.headersSent) return next(err); // delegate to default handler
    console.error(err.stack);               // log server-side only
    res.status(err.status || err.statusCode || 500)
       .json({ error: 'Internal Server Error' });
  });
  ```
- Chain specialized handlers by calling `next(err)` down the chain (log → client → catch-all):
  ```js
  app.use((err, req, res, next) => { console.error(err.stack); next(err); });
  app.use((err, req, res, next) => { req.xhr ? res.status(500).json({error:'failed'}) : next(err); });
  app.use((err, req, res, next) => { res.status(500).render('error', { error: err }); });
  ```
- When you DON'T call `next` in an error handler, you own writing+ending the response, or
  the request hangs and leaks (never GC'd).

## Central error handler — DON'T

- DON'T give the handler 3 params — Express treats it as normal middleware and skips it
  on errors.
- DON'T place it before routes — errors thrown later won't reach it.
- DON'T write the response when `res.headersSent` — bail with `return next(err)`.

## 404 handling — DO

- Add a catch-all **non-error** middleware after all routes, before the error handler. A
  404 is "no route matched," not a thrown error.
  ```js
  app.use((req, res) => res.status(404).json({ error: 'Not Found' }));
  // ...then the 4-arg error handler
  ```
- Express 5 path syntax note (path-to-regexp v8): a bare `*` is invalid; wildcards must be
  **named** — use `/{*splat}` to match all. But for 404 you rarely need a path at all —
  an unpathed `app.use` catches everything unmatched.

## Production hygiene / security — DO

- **Never leak stack traces to clients in prod.** The built-in default handler already
  suppresses `err.stack` when `NODE_ENV=production` (returns generic status-code HTML
  instead). Set `NODE_ENV=production`. Your custom handler must do the same: log the stack
  server-side, send a generic message to the client.
- Derive status from `err.status`/`err.statusCode`; the default handler forces anything
  outside 4xx/5xx to **500**.
- Override the default 404 and error responses to reduce fingerprinting (they expose
  Express-specific formatting).
- `app.use(helmet())` for security headers; helmet also removes `X-Powered-By`.
- Validate/sanitize all input; wrap URL/redirect parsing in `try/catch` and return 400 on
  bad input (defend against open redirects, XSS, ReDoS via `safe-regex`). Parameterize DB
  queries (defer ORM specifics to ORM lore).

## Production hygiene — DON'T

- DON'T send `err.stack`, `err.message` verbatim, or internal error objects to clients in
  prod — leaks implementation detail.
- DON'T forget `NODE_ENV=production`; without it Express serves full stack traces.
- DON'T let async errors escape to `process` unhandled — in Express 4 an unwrapped async
  throw becomes an unhandledRejection, not an HTTP 500.

## Migration checklist (4 → 5)

- Remove `asyncHandler`/`.catch(next)` wrappers *only after* confirming handlers **return**
  their promise (are `async` or `return promise`).
- Callback-style errors still need manual `next(err)` — unchanged.
- Fix route paths for path-to-regexp v8: named wildcards (`/{*splat}`), optional segments
  via braces (`/:file{.:ext}`), and `? + * [] ()` are reserved literals (escape with `\`).

## Sources

- https://expressjs.com/en/guide/error-handling.html
- https://expressjs.com/en/guide/routing.html
- https://expressjs.com/en/advanced/best-practice-security.html
- context7 `/expressjs/express` (v5.1.0 / v5.2.0): async-reject forwarding test, asyncHandler, next(err) flow
