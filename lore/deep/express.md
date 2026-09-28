# express — deep dive

> On-demand companion to `lore/express.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Middleware & routing](#middleware-and-routing) · [Errors & async handling](#errors-and-async) · [Security & validation](#security-and-validation)

## Middleware & routing <a id="middleware-and-routing"></a>

Framework-specific lore. Assumes Node/JS/TS lore exists elsewhere. Verify the
installed major before applying: `express@5` (current stable, Node 18+) changed
path matching and async error handling vs `express@4`. Feature notes below name
the version that introduced/changed behavior — never assume earlier.

### Middleware order & next()

DO
- Register middleware in execution order — Express runs `app.use`/route handlers
  top-to-bottom, first match wins. Parsers and security headers go before routes.
- Call `next()` to pass control, or terminate with a response method
  (`res.send/json/end/sendFile/redirect/render/sendStatus`). Exactly one path.
- Scope middleware with a mount path when it shouldn't run globally:
  `app.use('/api', apiLimiter)`.
- Use `next('route')` to skip remaining handlers of the *current* route and jump
  to the next matching route (pre-condition gating).

DON'T
- Don't forget `next()` in a non-terminating middleware — the request hangs and
  never gets GC'd.
- Don't call `next()` *and* send a response, or send twice — throws
  "headers already sent".
- Don't place `express.static`/catch-all before routes you expect to win.

```js
app.use(express.json());                 // 1. parse body
app.use(helmet());                       // 2. security headers
app.use('/api', requireAuth, apiRouter); // 3. scoped auth + routes
app.use((req, res) => res.status(404).send('Not found')); // 4. 404 fallback
```

### Routing

DO
- Use `app.METHOD(path, ...handlers)` (`get/post/put/delete/patch/all`).
  Handlers may be a fn, an array of fns, or a mix — all behave like middleware.
- Chain methods on one path with `app.route('/book').get(...).post(...).put(...)`.
- Read named segments from `req.params`, query from `req.query`. Query string is
  NOT part of the route path and never matches against it.

DON'T
- Don't use `app.del()` — removed in v5. Use `app.delete()`.
- Don't rely on `req.param(name)` — removed in v5. Read `req.params` /
  `req.query` / `req.body` explicitly.
- Don't put regexp metacharacters inside a path string in v5 (see below).

```js
// /users/34/books/8989 -> { userId: '34', bookId: '8989' }
app.get('/users/:userId/books/:bookId', (req, res) => res.json(req.params));

// literal - and . delimit params: /flights/LAX-SFO -> {from:'LAX',to:'SFO'}
app.get('/flights/:from-:to', (req, res) => res.json(req.params));
```

### Path matching — Express 5 vs 4 (path-to-regexp v8)

Express 5 uses path-to-regexp **v8**. Param names must be word chars
`[A-Za-z0-9_]`. Reserved chars `( ) [ ] ? + ! *` must be escaped with `\`.

| Intent | Express 4 | Express 5 |
|---|---|---|
| Wildcard | `/*` (unnamed) | `/*splat` (named, **captured as array**) |
| Wildcard incl. root | `/*` | `/{*splat}` |
| Optional segment | `/:file.:ext?` | `/:file{.:ext}` |
| Alternation | `/[a\|b]/:x` string | array: `['/a/:x','/b/:x']` |

DO
- In v5, name every wildcard; `req.params.splat` is a **string array** of
  segments (e.g. `['images','logo.png']`), not a string.
- Prefer a real `RegExp` (`app.get(/.*fly$/, h)`) or a path array over cramming
  regex syntax into a string.

DON'T
- Don't port v4 `*` / `?` path syntax verbatim to v5 — it throws or misbehaves.
- Note: v5 `req.params` has a **null prototype** for string paths; unmatched
  optional params are omitted (not `''`/`undefined`).

### Router modularization & mounting

DO
- Build feature modules with `express.Router()` (a self-contained mini-app) and
  mount with `app.use('/birds', birdsRouter)`.
- Pass `express.Router({ mergeParams: true })` when a child router must read the
  parent mount's params (e.g. `/users/:id` -> nested router).
- Use `caseSensitive` / `strict` router options deliberately if `/Foo` vs `/foo`
  or trailing-slash distinctions matter.

DON'T
- Don't expect child routers to see parent `req.params` without `mergeParams`.

```js
const router = express.Router({ mergeParams: true });
router.use(timeLog);                       // router-scoped middleware
router.get('/', (req, res) => res.send('home'));
module.exports = router;
// app.js
app.use('/birds', router);                 // handles /birds and /birds/*
```

### Body parsers & static files (built-in since 4.16.0)

`express.json()`, `express.urlencoded()`, `express.text()`, `express.raw()`,
`express.static()` are built in — no `body-parser` dependency needed on 4.16+.

DO
- `app.use(express.json({ limit: '100kb' }))` — set a `limit` to cap payloads.
- For forms: `express.urlencoded({ extended: true })`. **v5 defaults `extended`
  to `false`** — set `true` explicitly if you need nested objects (`qs`).
- Serve assets with `express.static('public', { maxAge: '1d' })`; mount under a
  prefix (`app.use('/static', express.static('public'))`) to namespace.

DON'T
- Don't assume `req.body` is `{}` when unparsed — in v5 it's `undefined`. Guard
  before reading.
- Don't serve dotfiles by accident: v5 `static`/`sendFile` default
  `dotfiles: 'ignore'` (`.well-known` now 404s — opt in with `dotfiles:'allow'`).
- Don't set an unbounded body limit — DoS vector.

### Error handling

DO
- Define error middleware **last**, with the 4-arg signature
  `(err, req, res, next)` — arity is how Express detects it.
- Forward errors with `next(err)`; anything passed to `next` except the string
  `'route'` triggers error handling and skips non-error handlers.
- Chain handlers: `app.use(logErrors)` -> `app.use(clientErrorHandler)` ->
  `app.use(catchAll)`, each calling `next(err)` until one responds.
- When `res.headersSent`, delegate: `if (res.headersSent) return next(err)`.

DON'T
- Don't hand-wrap every async route in try/catch on **Express 5** — handlers
  returning a rejected Promise auto-forward to `next(err)`. On **Express 4** you
  MUST `.catch(next)` or manually `next(err)` — async throws are lost otherwise.
- Don't leak stack traces: the default handler hides `err.stack` only when
  `NODE_ENV=production`. Set it.

```js
// Express 5: async errors auto-forwarded
app.get('/user/:id', async (req, res) => {
  const user = await getUserById(req.params.id); // reject -> next(err)
  res.send(user);
});
app.use((err, req, res, next) => {               // 4 args, defined last
  if (res.headersSent) return next(err);
  res.status(err.status || 500).json({ error: 'Internal error' });
});
```

### Security (non-negotiable)

DO
- `app.use(helmet())` for security headers (CSP, HSTS, X-Content-Type-Options,
  removes `X-Powered-By`, etc.). Also `app.disable('x-powered-by')`.
- Validate/sanitize all input (`req.body/query/params`); parameterize DB access
  (defer ORM specifics to ORM lore) to block SQL injection.
- Rate-limit auth/expensive routes (`rate-limiter-flexible`); front with TLS.
- Cookies: `secure`, `httpOnly`, non-default session `name`; `express-session`
  needs a production store (not the in-memory default).
- Validate redirect targets before `res.redirect(req.query.url)` (open-redirect).
- `npm audit` / Snyk; never run Express 2.x/3.x (unmaintained).

DON'T
- Don't return raw errors/stack traces to clients. Custom 404 + error handler.
- Don't trust `Content-Type`; pin parser `type`/`limit`. Guard regex against
  ReDoS (`safe-regex`).

### Sources
- https://expressjs.com/en/guide/routing.html
- https://expressjs.com/en/guide/error-handling.html
- https://expressjs.com/en/guide/migrating-5.html
- https://expressjs.com/en/advanced/best-practice-security.html
- https://expressjs.com/en/api.html

## Errors & async handling <a id="errors-and-async"></a>

Framework-specifics only. Assume Node/JS/TS lore lives elsewhere. Verify your major
before trusting any snippet: `npm ls express` → Express **4** vs **5** changes async
behavior fundamentally. This is the single biggest 4→5 difference.

### The one fact that matters (version-adaptive)

- **Express 4**: async route handlers/middleware that `throw` or return a **rejected
  promise** are **NOT caught**. Uncaught → unhandled rejection → the request hangs and
  never reaches your error handler. You MUST forward manually.
- **Express 5**: handlers/middleware returning a promise **auto-call `next(value)` on
  reject/throw**. No wrapper needed. Verified: rejected promises route to the 4-arg
  error handler. (If no rejection value, Express passes a default `Error`.)
- **Both versions**: **synchronous** throws inside a handler ARE caught automatically.
  Only *async* is the gap.

### Async errors — DO

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

### Async errors — DON'T

- DON'T assume `async` throws are caught in **Express 4**. They are not.
- DON'T pass a non-error truthy value to `next()` expecting normal flow. Anything except
  the string `'route'` marks the request as an error and skips remaining non-error
  handlers. `next('route')` is the *only* non-error string (skips to next route).
- DON'T `next(err)` more than once per request, or after the response started — you can
  trigger the default handler and crash the response.
- DON'T rely on Express 5 auto-forwarding for a handler that returns nothing (no promise
  returned = nothing to catch). `return` the promise or mark the fn `async`.

### Central error handler (4 args) — DO

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

### Central error handler — DON'T

- DON'T give the handler 3 params — Express treats it as normal middleware and skips it
  on errors.
- DON'T place it before routes — errors thrown later won't reach it.
- DON'T write the response when `res.headersSent` — bail with `return next(err)`.

### 404 handling — DO

- Add a catch-all **non-error** middleware after all routes, before the error handler. A
  404 is "no route matched," not a thrown error.
  ```js
  app.use((req, res) => res.status(404).json({ error: 'Not Found' }));
  // ...then the 4-arg error handler
  ```
- Express 5 path syntax note (path-to-regexp v8): a bare `*` is invalid; wildcards must be
  **named** — use `/{*splat}` to match all. But for 404 you rarely need a path at all —
  an unpathed `app.use` catches everything unmatched.

### Production hygiene / security — DO

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

### Production hygiene — DON'T

- DON'T send `err.stack`, `err.message` verbatim, or internal error objects to clients in
  prod — leaks implementation detail.
- DON'T forget `NODE_ENV=production`; without it Express serves full stack traces.
- DON'T let async errors escape to `process` unhandled — in Express 4 an unwrapped async
  throw becomes an unhandledRejection, not an HTTP 500.

### Migration checklist (4 → 5)

- Remove `asyncHandler`/`.catch(next)` wrappers *only after* confirming handlers **return**
  their promise (are `async` or `return promise`).
- Callback-style errors still need manual `next(err)` — unchanged.
- Fix route paths for path-to-regexp v8: named wildcards (`/{*splat}`), optional segments
  via braces (`/:file{.:ext}`), and `? + * [] ()` are reserved literals (escape with `\`).

### Sources

- https://expressjs.com/en/guide/error-handling.html
- https://expressjs.com/en/guide/routing.html
- https://expressjs.com/en/advanced/best-practice-security.html
- context7 `/expressjs/express` (v5.1.0 / v5.2.0): async-reject forwarding test, asyncHandler, next(err) flow

## Security & validation <a id="security-and-validation"></a>

Senior-reviewer checklist. OWASP-aligned. Assumes node/js/ts lore exists separately. DB parameterization → defer to `lore/orm.md`.

Version cues (verify against package.json):
- **Express 5** (5.1.x is the current `npm install express` default; requires **Node 18+**): async handlers/middleware that reject/throw auto-forward to error middleware; `path-to-regexp` rewritten (named wildcards, no bare `*`, no inline regexp in path strings — cuts route-based ReDoS); `req.query` is a read-only getter; `express.urlencoded` `extended` defaults `false`; `express.static` `dotfiles` defaults `"ignore"`; `req.body` is `undefined` (not `{}`) when unparsed.
- **Express 4** (4.21.x maintenance): async errors are NOT auto-caught — you must `.catch(next)` / `next(err)`. Express 2/3 are EOL.

### Security headers (helmet)

DO
- `import helmet from 'helmet'; app.use(helmet())` first, before routes. Sets CSP, HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, COOP, CORP, frame-ancestors, etc.; removes `X-Powered-By`; disables the legacy `X-XSS-Protection`.
- Also `app.disable('x-powered-by')` explicitly (helmet already strips it; belt-and-suspenders if helmet is ever removed).
- Tune CSP for real apps: `helmet({ contentSecurityPolicy: { directives: { ... } } })`. The default CSP is strict and will block inline scripts/CDNs — configure, don't blanket-disable.

DON'T
- Don't disable CSP/HSTS wholesale to "fix" a broken page — scope directives.
- Don't rely on `X-XSS-Protection` or `X-Frame-Options` alone; prefer CSP `frame-ancestors`.

### CORS

DO
- Explicit allow-list; reflect a specific validated origin. `import cors from 'cors'`.
```js
app.use(cors({ origin: ['https://app.example.com'], credentials: true }));
```
- For dynamic lists use the function form `origin(origin, cb){ cb(null, allowed.includes(origin)) }`.
- Understand the boundary: **CORS is not access control.** Every request still reaches your handler — curl/Postman/servers ignore CORS. Protect with authn/authz.

DON'T
- **Never `origin: '*'` with `credentials: true`.** Browsers reject `ACAO: *` alongside credentials, and it defeats the point. Credentialed → explicit origin. Don't blindly reflect `req.header('Origin')` back either.

### Input validation & sanitization

Validate at the boundary; treat all of `req.body/query/params/headers/cookies` as hostile. Pick ONE library.

**express-validator** (v7.x): chains `body/query/param/cookie/header`, then `validationResult`, then `matchedData`.
```js
import { body, validationResult, matchedData } from 'express-validator';
app.post('/signup',
  body('email').isEmail().normalizeEmail(),
  body('password').isLength({ min: 12 }),
  body('name').trim().notEmpty().escape(),
  (req, res) => {
    const r = validationResult(req);
    if (!r.isEmpty()) return res.status(400).json({ errors: r.array() });
    const data = matchedData(req); // only validated fields — use THIS, not raw req.body
    // ...
  });
```
- `checkSchema({...})` for declarative schemas; append `.run(req)` when running manually/async.

**zod** (TS-first): parse into typed data; reject on failure.
```js
import { z } from 'zod';
const Body = z.object({ email: z.string().email(), age: z.number().int().min(0) });
const p = Body.safeParse(req.body);
if (!p.success) return res.status(400).json({ errors: p.error.issues });
// use p.data (typed, stripped of unknown keys)
```

DO
- Whitelist allowed fields; use `matchedData`/`safeParse` output downstream, never the raw request object (prevents mass-assignment).
- Set body size limits: `express.json({ limit: '100kb' })`.
- `trim()` BEFORE `notEmpty()`/length checks (order matters in chains).

DON'T
- Don't hand-roll regex validators on untrusted input (ReDoS) — if unavoidable, vet with `safe-regex`.
- Don't trust `Content-Type`; enforce it and reject unexpected types.
- Don't validate only on the client.

### Injection

DO
- Parameterize ALL DB access — bind params / prepared statements / ORM query builders. See `lore/orm.md` for JPA/jOOQ/MyBatis and the JS ORM lore (prisma/drizzle/sequelize/typeorm/mongoose) for driver-specific binding.
- MongoDB: cast/validate types; reject object-valued fields where a scalar is expected (blocks `{$gt:''}`-style NoSQL operator injection). Validation above already does this if schema types are strict.
- Validate/allow-list any user value used as a table/column/sort field (can't be bound).

DON'T
- Never string-concat or template user input into SQL/NoSQL/HQL, shell commands, or file paths.
- Never pass `req.query`/`req.body` objects straight into a Mongo filter without type-checking.

### Rate limiting & brute force

**express-rate-limit** (v7+):
```js
import { rateLimit } from 'express-rate-limit';
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 100,              // v7 renamed `max` → `limit`
  standardHeaders: 'draft-8',
  legacyHeaders: false,
});
app.use(limiter);
app.use('/auth', rateLimit({ windowMs: 15*60*1000, limit: 5 })); // stricter on login
```
DO
- Tighter limits on auth/password-reset endpoints; block on failed-attempts per (IP + username) — see `rate-limiter-flexible` for two-metric brute-force defense.
- Behind a proxy/LB set `app.set('trust proxy', n)` (n = number of trusted hops) so the real client IP is keyed. Get `n` wrong and you either key everyone as the proxy or trust spoofable `X-Forwarded-For`.
- Use a shared store (Redis/Memcached) for multi-instance deployments — the default memory store is per-process.

DON'T
- Don't `trust proxy` = `true` (trust-all) in production; it lets clients spoof IPs.

### Cookies & sessions

DO
- `express-session` (server-side store) for anything sensitive — the cookie holds only the session id. `cookie-session` serializes state INTO the cookie (client-readable, ≤ ~4KB) — small non-secret data only.
```js
app.set('trust proxy', 1);
app.use(session({
  name: 'sid',               // rename off the default `connect.sid` (fingerprinting)
  secret: process.env.SESSION_SECRET,
  resave: false, saveUninitialized: false,
  cookie: { httpOnly: true, secure: true, sameSite: 'lax', maxAge: 3600_000 },
}));
```
- `httpOnly` (blocks JS/XSS theft), `secure` (HTTPS only), `sameSite` (`lax`/`strict`, CSRF defense), short `maxAge`. Regenerate the session id on login (`req.session.regenerate`) to prevent fixation.
- Replace the default in-memory store with a real store (Redis/DB) in production.
- CSRF: for cookie-based auth add token protection (`csrf-csrf` / double-submit) or require `SameSite=strict` + custom header for state-changing routes.

DON'T
- Don't ship the default session cookie name or a hardcoded/committed secret.
- Don't set `secure: true` without TLS terminating correctly (cookie silently dropped) — pair with `trust proxy`.

### Error handling — no leaks

DO
- One 4-arg error handler LAST: `app.use((err, req, res, next) => {...})`. Log server-side; return a generic message + status to the client.
```js
app.use((err, req, res, next) => {
  if (res.headersSent) return next(err);
  req.log?.error(err);
  res.status(err.status || 500).json({ error: 'Internal Server Error' });
});
```
- Run with `NODE_ENV=production` — Express's default handler then hides stack traces (sends only the status message); non-production leaks `err.stack`.
- Express 4: wrap async handlers (`.catch(next)` or an asyncHandler wrapper). Express 5: async rejections auto-forward — still add the handler.
- Add a custom 404 before the error handler.

DON'T
- Never send `err.stack`, SQL errors, or internal paths to clients.
- Don't `throw` in async Express-4 handlers expecting Express to catch it — it won't.

### TLS & dependencies

Terminate TLS (reverse proxy / Let's Encrypt); HSTS via helmet. Run `npm audit` / Snyk in CI; watch the GitHub Advisory DB. Never expose HTTP in prod; never ignore transitive-dep CVEs.

### Sources
- https://expressjs.com/en/advanced/best-practice-security.html
- https://expressjs.com/en/guide/error-handling.html
- https://expressjs.com/en/guide/migrating-5.html
- https://expressjs.com/en/resources/middleware/cors.html
- https://expressjs.com/en/guide/routing.html
- https://helmetjs.github.io/
- https://express-rate-limit.github.io/ (express-rate-limit v7)
- https://express-validator.github.io/docs/ (v7.x)
- https://zod.dev/
- https://owasp.org/www-project-top-ten/
